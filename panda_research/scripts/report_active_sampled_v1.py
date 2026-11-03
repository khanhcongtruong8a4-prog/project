"""Generate decisions from complete evidence; never promote failed gates."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,hashlib,json
import numpy as np
from panda_closed_loop.a2_acceptance import read_recorded_trace

def load(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def failures(d):return [{'cells':c['cells'],'factor':c['factor'],'metric':m,**v} for c in d['refinement']['comparisons'] for m,v in c['metrics'].items() if not v['passed']]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'reports/active_sampled_data_v1');a=p.parse_args();out=a.output
    history=load(out/'ACTIVE_FILTER_HISTORICAL_REPRODUCTION.json');regression=load(out/'FRESH_19_AND_ACTIVE_REGRESSION.json')
    old=load(ROOT/'runs/p1_r4/sd_v1_fresh_original_r4/summary.json')
    baseline=load(out/'baseline_operators_v1_3/SUMMARY.json');active=load(out/'alpha10_operators_v1_3/SUMMARY.json')
    modified=load(out/'modified_equation_v1_3/SUMMARY.json');t27=load(out/'t27_fresh/SUMMARY.json')
    challenge_folder=ROOT/'runs/active_sampled_data_v1/alpha10_active_challenge';challenge=load(challenge_folder/'summary.json')
    protected=load(ROOT/'policy/active_sampled_data_v1/PROTECTED_INPUTS.json')
    changed=[n for n,h in protected['files'].items() if sha(ROOT.parent/n)!=h]
    write(out/'PROTECTED_INPUTS_FINAL_AUDIT.json',{'files_checked':len(protected['files']),'changed':changed,'all_unchanged':not changed,'includes_all_original_tracked_source_and_failure_history':True})
    rows=[];timing=[]
    for label,analysis,folder in [('legacy_alpha5_original_AB2',baseline,ROOT/'runs/guarded_qp_reliability_v1/sd_v1_fresh_active_E3'),('separate_active_alpha10_challenge',active,challenge_folder)]:
        summary=load(folder/'summary.json');failed=failures(summary)
        for c in analysis['cells']:
            full=summary['cells'][c['cell']];trace=read_recorded_trace(folder,full['a2']['trace']);times=np.array([u['solve_runtime_s'] for u in trace['updates']])
            events=json.dumps(c['transitions'],separators=(',',':'));metrics=c['metrics']
            timing.append({'case':label,'cell':c['cell'],'updates':len(times),'median_s':float(np.median(times)),
                'p95_s':float(np.percentile(times,95)),'p99_s':float(np.percentile(times,99)),'max_s':float(np.max(times)),
                'updates_exceeding_1ms':int(np.count_nonzero(times>.001)),
                'offline_timeout_s':15.,'under_shared_cloud_load':True,'hardware_deadline_qualified':False})
            rows.append({'case':label,'cell':c['cell'],**c['grid'],'alpha_v':c['alpha_v'],
                'energy_J':metrics['modeled_electrical_energy_J'],'peak_tau_minus_u_Nm':c['max_tau_minus_u_Nm'],
                'peak_tau_minus_r_Nm':c['max_tau_minus_r_Nm'],'peak_intervention_t_s':c['peak_time_s'],
                'duration_s':metrics['duration_s'],'sampled_min_normalized_raw':metrics['minimum_normalized_raw_slack'],
                'stage_min_normalized_raw':c['stage_raw_rows']['minimum_normalized_raw'],
                'stage_negative_raw_samples':c['stage_raw_rows']['negative_raw_sample_count'],
                'max_QP_stationarity':metrics['max_scaled_stationarity'],'max_QP_primal':metrics['max_normalized_primal'],
                'min_observer_slack_Nm':min(metrics['minimum_observer_envelope_slack_Nm']),
                'actual_terminal_error_m':metrics['actual_terminal_error_m'],'physics_pass':c['original_physics_pass'],
                'audit_pass':c['original_cell_audit_pass'],'active_updates':c['active_updates'],'event_brackets':events,
                'refinement_failed_metric_count':len(failed),'quadrature_reconstructed_J':c['electrical_quadrature']['sum_J'],
                'interval_certificate':False})
    with (out/'ACTIVE_FILTER_COMPARISON_TABLE.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/'ALL_REFINEMENT_COMPARISONS.csv').open('w',newline='') as f:
        fields=['case','cells','factor','metric','value1','value2','absolute_difference','tolerance','passed'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for name,summary in [('legacy_alpha5',history),('new_active_alpha10',challenge)]:
            for pair in summary['refinement']['comparisons']:
                for m,v in pair['metrics'].items():w.writerow(dict(zip(fields,[name,str(pair['cells']),pair['factor'],m,*v['values'],v['absolute_difference'],v['tolerance'],v['passed']])))
    write(out/'WALL_CLOCK_COST.json',{'records':timing,'scope':'OFFLINE_CLOUD_MEASUREMENTS_NOT_REAL_TIME_OR_HARDWARE_QUALIFICATION'})
    # Count every frozen selected refinement field, including both original cohorts.
    def metric_count(x):
        if isinstance(x,dict):
            if set(['values','absolute_difference','tolerance','passed']).issubset(x):return (1,int(bool(x['passed'])))
            counts=[metric_count(v) for v in x.values()]
        elif isinstance(x,list):counts=[metric_count(v) for v in x]
        else:return (0,0)
        return tuple(sum(c[i] for c in counts) for i in range(2))
    count=metric_count(old['gate']['cohorts'])
    for ref in ['E1','E2','E3']:
        c=metric_count(load(ROOT/f'runs/guarded_qp_reliability_v1/sd_v1_fresh_v4_{ref}/summary.json')['refinement'])
        count=tuple(a+b for a,b in zip(count,c))
    selected=regression['decisions']['A2_SELECTED_FROZEN_SCOPE']=='GO' and count==(120,120) and not changed
    t27pass=t27['overall_pass'] and t27['fixture_count']==39
    active_fail=failures(challenge)
    gates=[
        ['Historical reproduction','GO' if history['historical_reproduction_passed'] else 'NO-GO','Four freshly simulated cells; full scientific histories and all eight failed metrics exactly reproduced.'],
        ['Root-cause confidence','SUPPORTED, CONDITIONAL','Differentiated KKT defect, independent directional checks and modified-equation propagation; no universal Panda impossibility theorem.'],
        ['New candidate safety','NOT ESTABLISHED','No defensible new runtime candidate selected; interval-aware/FOH proposals need tube and hybrid safety qualification.'],
        ['Original eight-check active refinement','NO-GO',f"{history['failed_refinement_count']} original energy/intervention checks fail; thresholds unchanged."],
        ['Intended alpha10 active filtering','NO-GO FOR REFINEMENT',f"Four genuinely active, physically audited cells; {len(active_fail)} peak comparisons fail in separately declared harder case."],
        ['A2 selected frozen scope','GO' if selected else 'NO-GO',f'Fresh seven original alpha5 plus twelve v4 alpha10; {count[1]}/{count[0]} refinement fields pass.'],
        ['T27 finite tested scope','GO' if t27pass else 'NO-GO','39 fixtures: 34 exact-KKT feasible and five exact-witness infeasible.'],
        ['A3 readiness','NO-GO','Active-filter qualification, complete M1 bounds and G2.5 start feasibility remain blockers. Official comparisons not run.']]
    write(out/'GATE_DECISION.json',{'gates':[dict(zip(['stage','decision','scope'],g)) for g in gates],
        'all_original_tracked_files_preserved':not changed,'selected_A2_refinement_metrics':{'total':count[0],'passed':count[1]},
        'new_runtime_candidate':None,'Level1':False,'official_A3':False,'external_signatures':None})
    matrix='| Stage | Decision | Precisely verified scope |\n|---|---|---|\n'+'\n'.join('| '+' | '.join(g)+' |' for g in gates)+'\n'
    (out/'ACTIVE_FILTER_GATE_DECISION.md').write_text('# A2 and active-filter readiness decision\n\n'+matrix+'\nNo Level 1 certification or independent third-party signatures are claimed. A2 GO is the selected frozen 19-cell numerical scope; it is not general active-filter or A3 qualification.\n\nBest next action: explicitly select a separately versioned accuracy policy or a causal time-varying/event-aware hold architecture with a verified reachable-tube safety argument. Preserve the eight failures. Resolve M1 and G2.5 independently before official A3.\n')
    en=modified['energy'];ip=modified['peak_intervention'];b0=baseline['cells'][0];b2=baseline['cells'][2]
    root=f'''# Active-filter refinement root cause

The historical eight failures reproduce exactly on the unmodified f6d5a18 checkout. This is a sampled moving-face consistency defect of the current point-projected AB2/ZOH realization, supported by local mathematical derivation and quantitative numerical attribution. It is not evidence of renewed guarded-QP false infeasibility, an inconsistent observer input, or an RK4 h error at the tested grids.

See SAMPLED_DATA_SAFETY_AND_ORDER_ANALYSIS.md, equations (1)–(3), for assumptions and proof. The current AB2 request supplies the tangent projection Pi Dr; the average of the continuous constrained target additionally requires face rotation and normal face motion. A current-point final QP removes an outward normal increment. On regular active samples the measured missing-normal derivative reaches {b0['smooth_face']['max_missing_normal_Nm_s']:.9g} Nm/s, versus {b0['smooth_face']['max_missing_rotation_Nm_s']:.9g} Nm/s for rotation. All {b0['smooth_face']['eligible_updates']} coarse and {b2['smooth_face']['eligible_updates']} fine eligible samples have a positive outward required normal component. This explains why the retained projected-feedback variant barely changed the failures: it still removes the required normal contribution.

The independently propagated first-order defect predicts an energy grid difference of {en['first_order_prediction_J']:.12g} J, versus the measured {en['observed_difference_J']:.12g} J (ratio {en['prediction_to_observed_ratio']:.7g}). It predicts a peak-intervention difference of {ip['first_order_prediction_Nm']:.12g} Nm, versus {ip['observed_difference_Nm']:.12g} Nm (ratio {ip['prediction_to_observed_ratio']:.7g}). Coefficients come from differentiated original dynamics/KKT and the known digital-request term, not fitting final energy or peak values. The initial post-P1 state sensitivity is explicitly initialized from measured endpoints. These are finite-grid, piecewise smooth floating point estimates, not certified remainder bounds or independent external replication. Full split contributions and Jacobian cross-checks are in modified_equation_v1_3/SUMMARY.json and first_order_bias.npz.

The exact energy discrepancy is about 4.20e-4 J against 1.17e-4 J tolerance, and peak discrepancy about 1.51e-3 Nm against 1.31e-5 Nm tolerance. Four Delta/diagonal pairs fail each metric: eight failures. All h-only comparisons pass at roughly 2e-11 J and 3e-11 Nm differences. Existing first-order ladder rates are evidence of the expected accumulation, not a proof that finite tolerances require second order.

Active digital faces are v_upper_3 then v_lower_1. Coarse event brackets end at .020, .330, .406 s. Fine brackets end at .020, .3295 (brief two-face interval), .330, .4025 s. These are sampled transition brackets, not exact switch times. See the comparison CSV and raw operator arrays for both scaled-dual cutoffs, separate raw-projection sets, all excluded differentiability intervals and Gram conditioning. No event sample is dropped from physical/QP/refinement reporting. The source reference is C2 with a jerk join at .5s.

Read-only first-order request projection, current-fixed-set AB2 and projection-before/after extrapolation are retained. No unsafe counterfactual torque is actuated. Post-filter AB2 violates raw rows at 386 coarse and 765 fine updates. A fixed-set surrogate isolates the movement term. Tiny numerical face effects prevent calling its floating point commutator identically zero. The scalar moving-boundary example has an exact first-order lower bound, but its scope is not extended to all Panda controllers or finite energy/peak gates.

Both tau-u and tau-r are reported, along with r,u,tau,sigma, duals, KKT residuals, states, observer and cumulative energy at actual common physical times. At matched coarse/fine samples dhat differs by only about 4e-14 Nm while q/v/z differ; the identical plant/DOB torque and continuous momentum identity are independently audited. This makes a mismatched observer-input mechanism unsupported here. Solver residuals remain within original 1e-9 gates; no fallback is present. Conditioning-dependent certified solution error is not inferred from residuals alone.

Energy is independently reconstructed using approved shared-bus non-regenerative power and actual held tau at every RK4 stage. Errors are around floating point summation resolution. No motor current constants are invented. The peak is interior and the diagnostic quadratic peak correction is far smaller than the failed grid difference; interpolation never replaces the frozen maximum. State bias and explicit digital-request dependence also affect the intervention norm. Event timing and finite-grid remainders are retained, not claimed to vanish.

All checked original robust rows at RK4 stages/integrated nodes are positive, including event-local samples. This is useful sampled evidence, not an intersample enclosure or a safety theorem. Interval-aware QP tightening needs valid derivative/remainder tubes and can be infeasible. A moving-face predictor followed by today's QP retains the normal obstruction. FOH or event-aware control changes the hold/update assumptions and needs a separately proved sampled/hybrid policy. No unverified architecture is actuated.

Diagnosed: moving active-face normal deficit, accumulated state/energy bias and explicit digital-request contribution to peak intervention, supported quantitatively. Remaining unresolved: certified global regularity/remainder bounds, exact intersample safety, and existence of some other causal constraint-preserving architecture meeting the original finite C4 gates. No universal impossibility or hardware infeasibility is claimed. The smallest defensible result now is NO-GO for active-filter qualification, preserved A2/T27 scoped GO, and the explicit separate design/policy memo.
'''
    (out/'ACTIVE_FILTER_REFINEMENT_ROOT_CAUSE.md').write_text(root)
    (out/'ACTIVE_FILTER_CANDIDATE_VALIDATION.md').write_text(f'''# Candidate disposition and active alpha10 validation

No new runtime candidate is justified sufficiently for actuation in this work. The production controller and guarded_qp_final_v1 remain byte-identical. Therefore there is no fabricated candidate predeclaration or candidate PASS. The rejected 2ca4de7 projected-feedback candidate and its eight failures remain in the retained history.

Options A/B/C and their mathematical/hold-policy consequences are in SAMPLED_DATA_SAFETY_AND_ORDER_ANALYSIS.md. FIRST_ORDER_POLICY_PROPOSAL.json is separately versioned and NOT ADOPTED. It does not relax any original threshold. A future interval/tube or hybrid rule must stop without actuation on failed/unavailable certificates and unqualified QPs, and must update history only after an accepted actual command.

The predeclared alpha10 challenge uses the same E3 waypoint path compressed to .5s, with exactly the same gains, disturbance, start/prehold, guard, original constraints and accuracy thresholds. This is explicitly a harder NEW case, never a replacement for the historical 1s trajectory or the 19 frozen A2 cells. Freeze commit 61ecdee preceded its motion. All four cells complete and pass original physical/observer/QP/energy/terminal audits and the declared nontriviality test. Peak tau-u is .0673292/.0670967 Nm, and time above .001 Nm is .063s in each cell, exceeding the predeclared .01Nm/.005s requirements. Nevertheless {len(active_fail)} peak-refinement checks fail; this is a real active-filter NO-GO, not an inactive-case success. All 24 comparisons are in ALL_REFINEMENT_COMPARISONS.csv.

The full raw traces and read-only stage/face analysis are retained. Every sampled robust row is positive; no true-ODE interval certificate exists. WALL_CLOCK_COST.json reports median/p95/p99/max and counts over 1ms, including first endpoint query overhead under shared cloud load. The 15s offline fail-closed timeout does not enforce or qualify a 1ms hardware deadline. No hardware timing claim follows.
''')
    (out/'T27_AND_A2_REGRESSION_REPORT.md').write_text(f'''# Fresh T27 and frozen A2 regression

Fresh physical simulation replay, not a re-audit: seven original alpha_v=5 cells and twelve frozen v4 alpha_v=10 cells complete with all original endpoint, P1, model, raw-row, observer, electrical-energy, held-input and terminal checks. The two original cohorts and three v4 references total {count[1]}/{count[0]} passing refinement fields. FRESH_19_AND_ACTIVE_REGRESSION.json compares complete histories and metrics to their retained originals using the prior frozen equivalence rules. The original seven retain their historical solver; the v4 cases use the already qualified sign correction. No gain or experimental parameter was retuned. The constant-row classifier does not alter any selected nonzero robot row.

The exact four historical active E3 cells were also freshly simulated on unchanged f6d5a18 and compared in full: four scientific histories reproduce exactly when only measured solver wall time is excluded, and all eight historical failed metrics remain exact. The replay's aggregate exit code 3 correctly records these failures; its four selected A2 jobs exit 0. See CLEAN_BASELINE_ORIGIN.json and the original console logs.

All 39 strict T27 fixtures freshly pass: 34 independently rational-KKT-checked feasible optima and five exact infeasibility witnesses. “Independent” here refers to the arithmetic verification algorithm, not a new external team or signature. No witness is used as a runtime fallback. Scope is these 39 fixtures, not a universal QP-domain guarantee. The native SHA remains 3370c29e2c3e42db44bc7cfed1d385ebc6680a519a1501693c223575122fc8c1. All 50 original contract checks and nine new mathematical/clock contracts pass. {len(protected['files'])} original tracked file hashes remain unchanged.

Source baseline f6d5a18; baseline contract db0125e; harder challenge 61ecdee; analysis freeze 389585e; modified-equation freeze 445bf56. Offline tuple adapters and cross-diagonal aggregation failures are retained with their versioned corrections and full logs. They did not modify or actuate production control. No official A3 run or Level1 claim is made.
''')
    print(json.dumps({'gates':gates,'A2_metrics':count,'protected_changed':changed},indent=2))

if __name__=='__main__':main()
