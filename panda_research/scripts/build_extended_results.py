"""Derive versioned tables and sampler reports from immutable cell evidence.

No plant integration, QP solve, acceptance change or evidence rewrite occurs.
All outputs are exclusive; use a new destination for a later reporting revision.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,io,json,hashlib
from datetime import datetime,timezone
from panda_closed_loop.config import digest
from panda_closed_loop.p1_r3 import compare_refinement


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        if isinstance(value,str):f.write(value.rstrip()+'\n')
        else:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def table_csv(path,rows):
    stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(path,stream.getvalue())


def number(x):return '—' if x is None else format(x,'.12g')


def reference_outcome(summary,thresholds):
    cells=summary['cells'];refinement=compare_refinement(cells,thresholds)
    if refinement!=summary['refinement']:raise ValueError('Stored refinement differs from recomputation')
    complete=len(cells)==4 and all(c['prehold']['completed'] and c['endpoint']['entrance_passed']
         and c['a2']['completed'] and c['a2']['passed'] and c['audit']['passed'] for c in cells)
    return ('PASS' if complete and refinement['passed'] and all(c['status']=='PASS' for c in refinement['comparisons']) else 'FAIL'),refinement


def build(version,run_suffix):
    out=ROOT/'reports'/('a2_extended_'+version)
    plan_path=ROOT/'policy'/('a2_extended_'+version)/'A2_EXTENDED_PREDECLARATION.json'
    plan=json.loads(plan_path.read_text());records={};outcomes={};refinements={};inputs={str(plan_path.relative_to(ROOT)):digest(plan_path)}
    for ref in ['E1','E2','E3']:
        folder=ROOT/'runs'/('a2_extended_'+version)/(ref+'_'+run_suffix)
        s=json.loads((folder/'summary.json').read_text());done=json.loads((folder/'run_completed.json').read_text())
        if not done['frozen_inputs_unchanged'] or done['engineering_error']:raise ValueError('Unresolved engineering/integrity failure')
        expected,refinement=reference_outcome(s,plan['fixed_acceptance_thresholds'])
        if expected!=s['outcome']:raise ValueError('Printed reference outcome disagrees with evidence')
        records[ref]=s;outcomes[ref]=expected;refinements[ref]=refinement
        for p in [folder/'summary.json',folder/'run_started.json',folder/'run_completed.json']:
            inputs[str(p.relative_to(ROOT))]=digest(p)
    aggregate='PASS' if all(v=='PASS' for v in outcomes.values()) else 'PARTIAL' if 'PASS' in outcomes.values() else 'FAIL'
    cells=[];negative=[];sampler=[];refrows=[];table=[]
    for ref,s in records.items():
        for c in s['cells']:
            a=c['a2'];m=a['metrics'];completed=a['completed'];failure=a['failure'] or {}
            row={'reference':ref,'cell':c['cell'],'Delta_s':c['grid']['control_period_s'],'h_s':c['grid']['rk4_step_s'],
                 'prehold_pass':c['prehold']['completed'],'actual_entrance_pass':c['endpoint']['entrance_passed'],
                 'completed':completed,'cell_pass':a['passed'],'full_horizon_audit_pass':c['audit']['passed'],
                 'executed_duration_s':m['duration_s'],'execution_energy_J':m['modeled_electrical_energy_J'],
                 'energy_is_full_horizon':completed,'terminal_error_at_T_m':m['actual_terminal_error_m'] if completed else None,
                 'abort_distance_to_final_target_m':m['actual_terminal_error_m'] if not completed else None,
                 'maximum_QP_intervention_Nm':m['maximum_intervention_Nm'],
                 'minimum_normalized_raw_slack':m['minimum_normalized_raw_slack'],
                 'maximum_normalized_primal':m['max_normalized_primal'],
                 'maximum_scaled_stationarity':m['max_scaled_stationarity'],
                 'negative_slack_count':c['negative_slacks']['negative_count'],
                 'failure_reason':failure.get('reason',''),'failure_QP_status':failure.get('status','')}
            cells.append(row)
            table.append(f"| {ref} | {c['cell']} | {row['Delta_s']*1000:g}/{row['h_s']*1000:g} | {'PASS' if a['passed'] and c['audit']['passed'] else 'FAIL'} | {number(m['duration_s'])} | {number(m['modeled_electrical_energy_J'])}{'' if completed else ' prefix'} | {number(row['terminal_error_at_T_m']*1000 if completed else None)} | {number(row['abort_distance_to_final_target_m']*1000 if not completed else None)} |")
            for n in c['negative_slacks']['negative_values']:negative.append({'reference':ref,'cell':c['cell'],**n})
            st=c['sampler_differences'];sr={'reference':ref,'cell':c['cell'],'completed_horizon':completed,
                  'executed_duration_s':m['duration_s'],'applied_updates':st['updates']}
            for name,d in st['statistics'].items():
                sr[name+'_max_2norm_Nm']=d['max_2norm_Nm'];sr[name+'_RMS_2norm_Nm']=d['RMS_2norm_Nm']
            sampler.append(sr)
        for comparison in refinements[ref]['comparisons']:
            for metric,result in comparison['metrics'].items() or {'INCOMPLETE_HORIZON':{}}.items():
                refrows.append({'reference':ref,'cell_i':comparison['cells'][0],'cell_j':comparison['cells'][1],
                    'factor':comparison['factor'],'status':comparison['status'],'metric':metric,
                    'value_i':result.get('values',[None,None])[0],'value_j':result.get('values',[None,None])[1],
                    'absolute_difference':result.get('absolute_difference'),'tolerance':result.get('tolerance'),
                    'metric_pass':result.get('passed'),'mandatory_for_this_suite':True})
    table_csv(out/'A2_EXTENDED_CELLS.csv',cells);table_csv(out/'A2_EXTENDED_REFINEMENT.csv',refrows)
    table_csv(out/'SAMPLER_DIFFERENCES.csv',sampler)
    write(out/'ALL_NEGATIVE_SLACKS.json',{'version':version,'negative_count':len(negative),'values':negative,
          'rule':'Every negative fails; rejected candidates are never described as applied torque.'})
    summary={'version':version,'created_utc':datetime.now(timezone.utc).isoformat(),'suite_outcome':aggregate,
        'numerical_gate':'GO' if aggregate=='PASS' else 'NO-GO','reference_outcomes':outcomes,
        'mandatory_motion_cells':12,'completed_cells':sum(c['completed'] for c in cells),
        'passing_cells':sum(c['cell_pass'] and c['full_horizon_audit_pass'] for c in cells),
        'refinements':refinements,'negative_count':len(negative),'all_inputs_unchanged':True,
        'baseline_original_numerical_outcome':'GO_UNCHANGED','independent_reviewer_signature':None,
        'user_acceptance_statement':plan.get('authority',{}).get('user_acceptance_statement') if isinstance(plan.get('authority'),dict) else None,
        'external_signature_artifact_supplied':False,'official_A3_executed':False,'Level1_certified':False,
        'analysis_source_sha256':digest(Path(__file__)),'evidence_inputs':inputs}
    write(out/'A2_EXTENDED_SUITE.json',summary)
    if version=='v4':
        shadows=[]
        for ref,s in records.items():
            for c in s['cells']:
                shadows.extend({'reference':ref,'cell':c['cell'],**n} for n in c['audit']['barrier_gain_amendment']['old_alpha5_shadow_negatives'])
        write(out/'OLD_ALPHA5_SHADOW_NEGATIVES.json',{'negative_count':len(shadows),'values':shadows,
              'scope':'UNUSED_OLD_DESIGN_ALPHA5_SHADOW; actual_v4_alpha10_raw_negatives_are_separately_reported',
              'old_policy_satisfaction_claimed':False})
    lines=[f'# A2-Extended {version}: {aggregate}; numerical gate {summary["numerical_gate"]}',
        '',f'Computed from twelve separately prepared fixed cells: E1 **{outcomes["E1"]}**, E2 **{outcomes["E2"]}**, E3 **{outcomes["E3"]}**. '
        'This is local numerical simulation evidence. The original r4 result and every earlier failure remain unchanged.',
        '',f'Predeclaration SHA-256: `{digest(plan_path)}`. Motion source freeze: `{run_suffix}`. '+
        ('All original grids, reference amplitudes/durations, model, P1/Slotine-Li/observer gains, observer/disturbance semantics, energy model and pass tolerances were retained. '
         'Velocity-CBF alpha_v changes 5→10 in the explicit amendment below.' if version=='v4' else
         'All original grids, reference amplitudes/durations, model, gains, observer/disturbance semantics, energy model and acceptance inequalities were retained.'),
        '', '| Case | Cell | Delta/h ms | Cell+audit | Executed s | Energy J | Terminal error at 1 s mm | Abort distance mm |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',*table,'',
        'Incomplete-cell energy is only the executed-prefix integral. Its distance to the declared final target is an abort-state diagnostic; it is never terminal accuracy at T. '
        'The legacy raw metric key `actual_terminal_error_m` exists for both completed and aborted runs; the CSV above separates their meanings.',
        '', '## Every refinement pair', '',
        '| Case | 0–1 (h) | 2–3 (h) | 0–2 (Delta) | 1–3 (Delta) | 0–3 diagonal | 1–2 diagonal |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for ref in records:
        values=['PASS' if c['status']=='PASS' else 'INCOMPLETE' if c['status'].startswith('NOT_COMPARABLE') else 'FAIL' for c in refinements[ref]['comparisons']]
        lines.append('| '+ref+' | '+' | '.join(values)+' |')
    lines += ['', 'All four fixed-factor edges and both diagonals must pass for a reference GO. Each checks energy, elapsed duration, max ||tau-u|| and minimum normalized raw row using '
       '`abs(a-b) <= max(approved_absolute, 1e-4*max(abs(a),abs(b)))`. Absolute floors remain energy 1e-6 J, duration 1e-6 s, intervention 1e-7 N m and normalized slack 1e-6. '
       'Actual terminal position tolerance remains 1 mm and planned 1e-6 m. A raw negative remains a failure at any magnitude.',
       '', '`A2_EXTENDED_REFINEMENT.csv` retains every numerical pair, threshold and metric result. `ALL_NEGATIVE_SLACKS.json` lists every retained negative. '
       'Each completed cell has the unchanged r4 mathematical trace audit with only the lossless input loader adapted. '
       'Full P1/update/RK4 stage/endpoint logs, original matrices/slacks, state/observer signals, references, r/u/tau, signed analysis-only truth, energy and source/environment/command metadata are retained in the run directories.', '']
    if version=='v1':
        lines += ['## Failed outcomes retained', '',
          'E1 cell 1 stopped at 0.998 s on PROXQP_PRIMAL_INFEASIBLE. Separate HiGHS and exact-dyadic interior-witness analysis demonstrates strict feasibility of its stored affine coefficients. '
          'The solver status is therefore not evidence that the recorded feasible set is empty. There was no fallback, retry or subsequent state advance.',
          '', 'E3 cells 0/1/2 stopped at 0.095/0.076/0.0925 s on solved candidates with negative v_upper_3 rows. Cell 3 stopped at 0.020 s on MAX_ITER_REACHED, with no returned candidate. '
          'All four stopped before the 0.5 s reversal. The reversal profile is defined but its physical second phase was not exercised in v1.',
          '', 'Every executed failed prefix was subsequently audited read-only, including controller/observer/43-row reconstruction, original signs, actual held inputs, RK4 stage and endpoint arithmetic, cubic interpolant extrema, all physical/envelope samples, '
          'energy and fail-closed continuity. All five prefix-data audits PASS. This does not provide a completed horizon or change a scientific FAIL. '
          'See `prefix_audits/` and `ACTUAL_EXTENDED_QP_DIAGNOSTICS.md`. The diagnostic witnesses are not new actuation or exact-model certificates.',
          '', 'The later user authorized a separate numerical-solver correction. v2 has a new pre-motion commit, policy and full separate run directories. No v1 case was overwritten or relabeled.']
    elif version in ['v2','v4']:
        lines += ['## Declared numerical correction and stronger audit', '',
          'The v2 amendment solves with isotropic physical-torque scaling, positive Euclidean row scaling, a 1e-8 original-normalized inward constraint guard, eps_abs 1e-12 and a checked duality gap. '
          'All 43 ORIGINAL raw inequalities still gate application. This is an explicit new numerical constraint tightening and solver realization, not an unchanged original solver claim. '
          'There is one cold query per update, no post-QP projection, retry, warm-start history or fallback.',
          '', 'Both original-T29 and guarded-problem primal/stationarity residuals, guarded complementarity and dual signs are recomputed from retained dual vectors for every completed update. '
          'The original mathematical controller/plant/audit rules and raw zero-negative criterion also pass only when the records show that. '
          'The guard is a numerical target, with measured floating residual, not a certified solver-error bound.',
          '', 'All 14 pre-motion v2 contracts passed after correcting an invalid exact-invariance fixture: its initial noninteger powers changed the input coefficients by one ulp. '
          'That failed log remains alongside the corrected integer-power fixture. The five original failed matrices passed read-only v2 qualification before any new motion.',
          '', 'The user acceptance statement is recorded in the new predeclaration. External reviewer identity/signature artifacts were not supplied; those fields remain null. '
          'Numerical acceptance, user acceptance and independently evidenced controls/theory review are distinct records.']
    else:
        lines += ['## Explicit causal digital QP amendment', '',
          'v2 completed all twelve individual cells, but E3 failed energy and intervention refinement on both Delta edges and both diagonals. '
          'The complete failed-refinement evidence remains in `../a2_extended_v2/`. It was not relabeled, removed or used to reduce a reference or relax an acceptance threshold.',
          '', 'v3 retains the same nominal AB2 request u and applies the same causal interval rule to G and c: bootstrap uses current rows, then B_interval=B_current+0.5(B_current-B_previous). '
          'The single actual 43-row QP targets G_interval*tau+c_interval >= (0.1+1e-8)*original_row_scale. '
          'The fixed 0.1 is an explicit engineering inward reserve, not a certified M1 drift constant. This changes the digital safety-QP realization and is scoped/versioned as such.',
          '', 'Before any returned torque can be applied, all 43 ORIGINAL current-state inequalities G_current*tau+c_current >=0 are separately recomputed with no tolerance exception. '
          'Only the exact QP candidate is held; no post-QP extrapolation, clipping, retry or backup actuation occurs. The full bootstrap QP is solved at the actual P1 endpoint and reused for the first application.',
          '', 'The unchanged 1e-9 T29 numerical targets apply to the ACTUAL declared interval QP. Its retained duals and causal row history are recomputed by the extra audit, '
          'alongside the original current-state hard-row audit. Original-instantaneous-QP stationarity is not falsely claimed for a different optimization problem. '
          'The actual solved G/c and the original current G/c are both retained for every update.',
          '', 'All ten v3 pre-motion contracts and 6000 read-only v2 E3-matrix queries passed before the v3 freeze. Those read-only old-state queries are development qualification, '
          'not v3 motion or refinement results. This report uses only the separately executed complete v3 campaign for its outcome.',
          '', 'This is a local numerical result for the explicit new sampled controller and fixed references, not a retroactive GO for v1/v2 or proof of the original continuous-time theorem. '
          'The user acceptance statement is retained verbatim; no external reviewer identity or signature artifact has been invented.']
    if version=='v4':
        lines += ['', '## Explicit velocity-barrier gain change', '',
          'This numerical GO, if computed above, is for the v4 filter design: velocity-CBF alpha_v doubles from 5 to 10 s^-1. '
          'It expands the robust acceleration admissibility inside the SAME physical speed limits. It is a controller/barrier policy change, '
          'not a preserved-alpha_v5 claim, a physical-model edit or a change of pass tolerances. The new configuration is separately frozen; original approved policy bytes remain intact.',
          '', 'All other gains, observer envelope, P1 procedure, fixed references, C4 grid, terminal tolerances and refinement thresholds remain unchanged. '
          'The actual QP is the qualified v2 CURRENT-STATE guarded QP. There is no v3 interval-row correction or added 0.1 reserve. '
          'The ten pre-motion v4 contracts and 6000 old-state nominal-feasibility screens passed before the new freeze; they are not counted as v4 motion evidence.',
          '', 'For transparency, each full cell audit also evaluates all OLD alpha_v5 rows on the v4 states and applied torques. '
          'Any negative shadow values remain in `audit.barrier_gain_amendment.old_alpha5_shadow_negatives`. They are explicitly unused OLD-POLICY diagnostics; '
          'we do not claim the old filter design passed this new motion. Actual v4 negative raw rows still fail without any tolerance exception.',
          '', 'v1, v2 and v3 outcomes stay PARTIAL/NO-GO for their full suites. Their complete failed/aborted traces and all failed comparisons remain in the package. '
          'This separates a new successful design, when actually shown, from retrospectively approving an earlier failed experiment.']
    lines += ['', '## Repeatability and limits', '',
      'The original seven-cell 0.25 s baseline was reproduced exactly in a separate clean checkout/fresh pinned venv on the same machine; see `../a2_extended_v1/BASELINE_REPRODUCTION.md`. '
      'Each new extension cell was executed once. Refinement is a resolution comparison, not repeated independent reproduction. No unexecuted repeat run is claimed.',
      '', 'The C2 reversal, fixed references and pointwise audits do not establish all-time true-ODE safety, a sampled-data theorem, hardware behavior, optimized planner/filter consistency, A3 readiness or Level 1 certification. '
      'Sampler interpretation requires the separately attributable theory/controls decision in `SAMPLER_THEORY_SCOPE.md` and `REVIEW_REQUEST.md`.']
    write(out/'A2_EXTENDED_RESULTS.md','\n'.join(lines))
    base=json.loads((ROOT/'reports/a2_extended_v1/baseline_reproduction/BASELINE_SAMPLER_DIFFERENCES.json').read_text())
    sampler_lines=['# Digital sampler: measured quantities and claim scope','',
       '`src/panda_closed_loop/controller.py:SlotineLiController.command` computes the continuous-law request r_k. '
       '`src/panda_closed_loop/p1_r4.py:AB2TorqueController.command` computes u_0=r_0 and u_k=r_k+0.5*(r_k-r_(k-1)). '
       '`p1_r3.py:strict_qp_check` passes u_k to the full QP; `run_a2_cell` holds only the returned accepted tau_k and the same torque feeds the observer.',
       '', 'The half-difference is a causal two-step sampling correction that approximates the interval-average request to second order for smooth requests. '
       'It has fresh history per cell, one update per attempted solve and no future state, future estimate or disturbance-truth input. '
       'It is a changed digital realization of the continuous request, not an established sampled-data stability proof.',
       '', 'All entries below are seven-joint Euclidean norms in N m at APPLIED updates. RMS is sqrt(mean(||difference||_2^2)); constant Delta makes this the ZOH-time-weighted RMS over that cell\'s ACTUALLY executed duration. '
       'Aborted rows cover only the prefix. They do not include a rejected candidate and do not measure unobserved continuous r(t) between updates.',
       '', '| Cohort/cell | Executed s | max u−r | RMS u−r | max tau−u | RMS tau−u | max tau−r | RMS tau−r |',
       '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for c in base['cells']:
        vals=[c[name][k] for name in ['sampling_u_minus_r','QP_tau_minus_u','total_tau_minus_r'] for k in ['max','RMS']]
        sampler_lines.append(f"| Original fresh/{c['cell']} | 0.25 | "+' | '.join(number(x) for x in vals)+' |')
    for sr in sampler:
        vals=[sr[name+'_'+k+'_2norm_Nm'] for name in ['u_minus_r','tau_minus_u','tau_minus_r'] for k in ['max','RMS']]
        sampler_lines.append(f"| {version} {sr['reference']}/{sr['cell']} | {number(sr['executed_duration_s'])}{'' if sr['completed_horizon'] else ' prefix'} | "+' | '.join(number(x) for x in vals)+' |')
    sampler_lines += ['', 'Detailed component max/RMS and exact machine values remain in each cell JSON and the baseline sampler JSON; the derived CSV includes every extension max/RMS pair. '
       'The fresh baseline maximum digital correction is about 0.00281078060735 N m; maximum filter correction is about 3.80438081038e-9 N m. '
       'Thus a nearly inactive QP relative to u does not establish negligible difference from continuous r. The three vector norms do not add as scalar equalities.',
       '', 'The baseline phrase zero intervention is an approved numerical diagnostic for ||tau-u|| <= 1e-6 N m. It is relative to the QP input u. '
       'It cannot establish tau=r, a solver error bound, continuous-law equivalence, or a whole-suite zero-intervention claim where E3 activates the filter.',
       '', 'Transferring continuous-time claims would require a reviewed sampled-data analysis with consistent sampler/hold/controller histories, observer discretization and error envelopes, '
       'sampling/delay/jitter assumptions, integration error enclosures, model regularity/domain bounds, and intersample constraint/tracking margins. '
       'None is proved by these measured differences. No manuscript or theorem was silently rewritten.',
       '', 'The user has supplied acceptance in the conversation; the exact statement is retained in the v2 predeclaration. No attributable external theory/controls signature artifact was supplied. '
       'The written review request remains unsigned until a real reviewer supplies their decision. This limits publication interpretation without erasing valid numerical runs.']
    if version=='v3':
        sampler_lines += ['', '## v3 safety-QP sampling scope', '',
          '`src/panda_closed_loop/a2_qp_v3.py:interval_rows` samples the original affine G/c with the SAME causal half-difference, with a fresh history per cell. '
          '`IntervalHardQP.solve` executes the tightened interval QP and then independently requires all original current-state raw rows nonnegative. '
          '`audit_interval_numerics` reconstructs both row sets, actual-QP dual KKT residuals and history without a resolve. '
          'No future reference, predicted state or true disturbance is an input.',
          '', 'Consequently tau-u describes the intervention of THIS versioned sampled QP, including its explicitly declared engineering reserve. '
          'It is not the intervention of the original instantaneous continuous-time projection. '
          'The extra constraint margin is not a verified drift enclosure; original current-row passes remain sampled numerical checks. '
          'The sampler reviewer must address the row correction and reserve as well as u-r before drawing Section IV conclusions.']
    if version=='v4':
        sampler_lines += ['', '## v4 barrier-gain scope', '',
          'The nominal r/u sampler is unchanged. `a2_policy_v4.py` admits only alpha_v 5→10 and honest configuration metadata; '
          'the actual QP uses CURRENT-state rows, v2 numerical scaling/roundoff guard and the original unchanged T29/strict raw acceptance thresholds. '
          'The v3 interval-row sampler is absent. Thus tau-u is intervention relative to digital u under this explicit amended speed-barrier design.',
          '', 'The gain audit retains original-alpha5 shadow negatives separately. A v4 PASS does not assert satisfaction of the previous alpha5 filter. '
          'The physical limits and Gaz model are unchanged. This versioned gain amendment and the nominal AB2 realization still need attributable theory/controls interpretation before publication claims.']
    write(out/'SAMPLER_THEORY_SCOPE.md','\n'.join(sampler_lines))
    write(out/'REVIEW_REQUEST.md',f'''# Requested theory / controls decision — unsigned

Numerical scope: A2-Extended {version}, frozen at {run_suffix}; computed outcome {aggregate}.
The original seven-cell baseline has a separate same-machine clean-checkout reproduction.
The user acceptance statement is recorded separately, without an invented reviewer identity.

Please provide a written decision on whether the causal r4 correction
u_0=r_0; u_k=r_k+0.5(r_k-r_(k-1)) is an admissible digital realization for
the intended A2 interpretation and eventual Section IV claims. Assess the
separate u−r, tau−u and tau−r tables, actual observer/hold timing, numerical
QP amendment where applicable, constraints and failure/refinement evidence.
Specify assumptions, allowed numerical claims, missing sampled-data analysis
and any restrictions on publication interpretation. A numerical PASS alone
cannot supply a proof or someone else's acceptance.

This is a concrete reviewer handoff artifact. No named reviewer/contact was
provided, so no external message was sent and no response is invented.

Controls reviewer name: null
Controls decision: null
Controls dated signature / artifact hash: null
Theory reviewer name: null
Theory decision: null
Theory dated signature / artifact hash: null
''')
    print(f'{version}: {outcomes}; suite {aggregate}; {summary["numerical_gate"]}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',choices=['v1','v2','v3','v4'],required=True)
    parser.add_argument('--run-suffix',required=True)
    args=parser.parse_args();build(args.version,args.run_suffix)
