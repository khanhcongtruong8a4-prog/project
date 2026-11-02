"""Finalize an explicitly scoped A2 policy from recovered and replayed evidence.

No printed label can clear a missing cell, changed parameter, mismatched trace
or undeclared failed required test. The disclosed hybrid-QP probe remains FAIL
and blocks broader solver qualification; it is never represented as a pass.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,hashlib,json,subprocess
from datetime import datetime,timezone
from panda_closed_loop.a2_acceptance import read_recorded_trace
from panda_closed_loop.a2_extended import difference_statistics
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values


def write(path,value):
    with path.open('x') as f:
        if isinstance(value,str):f.write(value.rstrip()+'\n')
        else:json.dump(json_values(value),f,indent=2,allow_nan=False);f.write('\n')


def csv_write(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prefix',required=True);args=parser.parse_args()
    out=ROOT/'reports/a2_acceptance_v1';run=out/args.prefix
    plan=json.loads((ROOT/'policy/a2_acceptance_v1/PREDECLARATION.json').read_text())
    end=json.loads((run/'run_completed.json').read_text());comparisons=json.loads((run/'REPLAY_COMPARISON.json').read_text())
    contracts=json.loads((run/'contracts_summary.json').read_text());math=json.loads((run/'framework_math.json').read_text())
    recovery=json.loads((out/'RECOVERY_INITIAL.json').read_text())
    preserved=[]
    for name,h in plan['protected_source_sha256'].items():
        ok=(REPO/name).is_file() and digest(REPO/name)==h
        preserved.append({'file':name,'sha256':h,'unchanged':ok})
    checks={'complete_recovery_of_prior_118_traces':recovery['all_original_CTZ_bytes_reconstructed'] and len(recovery['files'])==118,
       'fresh_replay_finished_without_error':end['engineering_error'] is None,
       'all_four_selected_replay_processes_exit0':set(end['physical_exit_codes'])=={'original_A2','E1','E2','E3'} and all(c==0 for c in end['physical_exit_codes'].values()),
       'all_19_cells_and_complete_scientific_traces_exact':sum(len(s['cells']) for s in comparisons.values())==19 and all(c['passed'] for s in comparisons.values() for c in s['cells']),
       'original_two_cohorts_and_all_v4_pairs_pass':all(s['passed'] for s in comparisons.values()),
       'all_applicable_frozen_contracts_pass':all(s['required_A2_scope_pass'] for s in contracts.values()),
       'all_2018_prior_source_files_unchanged':len(preserved)==2018 and all(s['unchanged'] for s in preserved),
       'all_verification_code_still_frozen':all(digest(REPO/n)==h for n,h in plan['verification_code_sha256'].items()),
       'replay_self_report_matches_derived_checks':end['technical_pass'] and end['protected_inputs_unchanged']}
    go=all(checks.values());status='GO' if go else 'HOLD'
    probe=math['active_QP_evidence']['preserved_real_43'];failures=[r for r in math['checks'] if r['result']!='PASS']
    actual_v4=math['active_QP_evidence']['actual_v4_active_43']
    blocker={'id':'GUARDED_QP_LEGACY_ALPHA5_ACTIVE_FACE_FALSE_INFEASIBILITY',
       'status':'CONFIRMED_FAILED_NUMERICAL_PROBE_RETAINED',
       'selected_protocols':'Original alpha5 A2 uses ORIGINAL solver; v4 uses alpha10 guarded solver. The failed hybrid is neither selected runtime.',
       'solver_result':probe['query']['status'],'stop_requested':probe['query']['stop_requested'],
       'exact_represented_QP_optimum_exists':probe['certificate']['passed'],'torque_actuated':probe['torque_actuated'],
       'affected_claim':'GENERAL_GUARDED_QP_DOMAIN_QUALIFICATION_AND_OFFICIAL_T27; NOT_RETROACTIVE_FAILURE_OF_THE_REPRODUCED_FIXED_CELLS',
       'exact_remedies':[
          'Keep the fail-closed stop and report solver failure/UNKNOWN unless an independently checked infeasibility certificate establishes an empty represented set.',
          'Develop a separately versioned solver algorithm/initialization/status-verification implementation that completes this exact fixed feasible matrix. Keep H,g,C,b, guard, gains, references and acceptance thresholds unchanged.',
          'Qualify it against the stored exact-rational optimum and active/scaled/redundant feasible/infeasible matrices, then repeat the unchanged frozen A2 suites before extending the accepted solver scope. Do not actuate the diagnostic witness as an undeclared fallback.'],
       'general_qualification_gate':'HOLD','production_v4_changed':False}
    write(out/'GUARDED_QP_BLOCKER.json',blocker)
    write(out/'PROTECTED_SOURCE_INTEGRITY.json',{'source_commit':plan['input_source_commit'],'all_unchanged':all(x['unchanged'] for x in preserved),'files':preserved})
    rows=[];samplers=[]
    for ref,comparison in comparisons.items():
        folder=ROOT/comparison['replay_run'];summary=json.loads((folder/'summary.json').read_text())
        for cell,c in zip(summary['cells'],comparison['cells']):
            m=cell['a2']['metrics'];trace=read_recorded_trace(folder,cell['a2']['trace'])
            stats=difference_statistics(trace['updates'])
            row={'protocol':ref,'cell':cell['cell'],'Delta_s':cell['grid']['control_period_s'],'h_s':cell['grid']['rk4_step_s'],
                 'complete':cell['a2']['completed'],'audit_pass':cell['audit']['passed'],'exact_scientific_replay':c['passed'],
                 'energy_J':m['modeled_electrical_energy_J'],'terminal_error_mm':1000*m['actual_terminal_error_m'],
                 'minimum_normalized_raw_slack':m['minimum_normalized_raw_slack'],'maximum_intervention_Nm':m['maximum_intervention_Nm'],
                 'maximum_primal':m['max_normalized_primal'],'maximum_stationarity':m['max_scaled_stationarity'],
                 'prehold_scientific_sha256':c['trace_comparison']['prehold']['replay_scientific_sha256'],
                 'execution_scientific_sha256':c['trace_comparison']['a2']['replay_scientific_sha256']}
            rows.append(row);srow={'protocol':ref,'cell':cell['cell'],'updates':stats['updates']}
            for name,values in stats['statistics'].items():
                srow[name+'_maximum_2norm_Nm']=values['max_2norm_Nm'];srow[name+'_RMS_2norm_Nm']=values['RMS_2norm_Nm']
            samplers.append(srow)
    csv_write(out/'REPRODUCTION_CELLS.csv',rows);csv_write(out/'SAMPLER_MAX_RMS.csv',samplers)
    v4rows=[r for r in rows if r['protocol']!='original_A2']
    source_base=ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json';source_v4=ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json'
    final={'schema':'IC2AI_2027_VERIFIED_A2_POLICY_V1','version':'A2-verified-1.0.0','finalized_utc':datetime.now(timezone.utc).isoformat(),
       'status':'FROZEN_SCOPED_NUMERICAL_ACCEPTANCE_GO' if go else 'FROZEN_POLICY_ACCEPTANCE_HOLD',
       'numerical_gate':status,'acceptance_scope':'ONLY_ORIGINAL_R4_SEVEN_CELLS_AND_A2_EXTENDED_V4_THREE_FIXED_REFERENCES_ORIGINAL_C4',
       'authority':{'source':'DIRECT_USER_CONSULTATION_AND_PROCEED_AUTHORIZATION','additional_administrative_approval_required':False,
          'consultation_status':'USER_REPORTED','external_reviewer_identity':None,'external_signature_artifact':None,
          'interpretation':'User authorizes proceeding and scoped release after mathematical/technical verification; no outside verification or signature is invented.'},
       'protocols':{
          'original_A2_r4':{'source_commit':plan['original_baseline_commit'],'predeclaration_sha256':digest(source_base),'alpha_v_s_inverse':5.,'solver':'ORIGINAL_HARD_QP_UNCHANGED','duration_s':.25,'cells':7,'cohorts':['original_C4','finer_confirmation']},
          'A2_Extended_v4':{'control_freeze_commit':plan['v4_motion_freeze_commit'],'predeclaration_sha256':digest(source_v4),
             'amended_configuration_sha256':digest(ROOT/'policy/a2_extended_v4/AMENDED_POLICY_CONFIGURATION.json'),
             'alpha_v_s_inverse':10.,'nominal_sampler':'u0=r0; uk=1.5*rk-0.5*r_previous','solver':'V2_CURRENT_STATE_GUARDED_QP',
             'roundoff_guard_in_original_row_scale':1e-8,'duration_s':1.,'references':['E1','E2','E3'],'cells':12,'all_refinement_pairs':18,'all_metric_comparisons':72}},
       'acceptance_checks':checks,'all_parameters_and_original_sources_preserved':all(preserved_row['unchanged'] for preserved_row in preserved),
       'exact_replay':{'cells':19,'excluded_fields':['solve_runtime_s'],'exclusion_reason':'Measured solver wall time only. No scientific field excluded.',
           'all_metrics_states_and_full_scientific_traces_equal':checks['all_19_cells_and_complete_scientific_traces_exact']},
       'verification_level':'SOURCE_VERIFIED_AND_EXECUTED_LOCALLY_FRESH_CHECKOUT_FRESH_PINNED_ENVIRONMENT_ON_SAME_HOST',
       'new_machine_or_independent_human_reproduction_claimed':False,'all_development_tests_pass':all(r['passed'] for r in contracts.values()),
       'failed_diagnostic_test_count':len(failures),'failed_diagnostic_tests':failures,
       'guarded_QP_general_qualification':'HOLD_CONFIRMED_COUNTEREXAMPLE','active_v4_recorded_QP_exact_certificate_pass':actual_v4['certificate']['passed'],
       'continuous_sampled_data_theorem_transfer':'NOT_PROVED_OR_CLAIMED','original_manuscript_or_theorem_rewritten':False,
       'official_A3_comparisons':'NOT_STARTED_NOT_AUTHORIZED','Level1_certification':'NOT_ESTABLISHED_NO_GO',
       'previous_failed_experiments':'PRESERVED_UNCHANGED','independent_controls_signature':None,'independent_theory_signature':None,
       'evidence':{'replay_report':str((run/'REPLAY_COMPARISON.json').relative_to(ROOT)),
          'replay_report_sha256':digest(run/'REPLAY_COMPARISON.json'),'recovery_proof_sha256':digest(out/'RECOVERY_INITIAL.json'),
          'math_contract_report_sha256':digest(run/'framework_math.json'),'mathematical_scope_sha256':digest(ROOT/'policy/a2_acceptance_v1/MATHEMATICAL_CONSISTENCY.md')}}
    p=ROOT/'policy/a2_verified_v1';p.mkdir(exist_ok=False);write(p/'FINAL_A2_POLICY.json',final)
    (p/'FINAL_A2_POLICY.json.sha256').write_text(digest(p/'FINAL_A2_POLICY.json')+'  FINAL_A2_POLICY.json\n')
    write(out/'A2_READINESS_DECISION.json',final)
    write(out/'A2_READINESS_DECISION.md',f'''# A2 numerical readiness: {status} for the precisely verified scope

Original A2 r4: seven cells freshly reproduced with all original/finer-cohort
checks. A2-Extended v4: E1/E2/E3 all reproduced across four C4 cells each,
with all 18 pairs / 72 metrics. All 19 metrics/state/complete scientific
trace comparisons are exact when only solver wall time is excluded.
These are local replays in a fresh checkout and pinned environment on the
same machine, not externally independent verification. All {len(preserved)}
prior tracked source/evidence files remain unchanged.

Worst v4 terminal error: {max(r['terminal_error_mm'] for r in v4rows):.12g} mm.
Minimum v4 normalized actual raw slack: {min(r['minimum_normalized_raw_slack'] for r in v4rows):.12g}.
Maximum v4 scaled stationarity: {max(r['maximum_stationarity'] for r in v4rows):.12g}.
Full endpoint QPs, all scheduled updates and retained RK4 samples were audited.

The existing AB2 nominal sampler, alpha_v=10 v4 speed-barrier design and
guarded current-state QP are frozen, without new gains, guard/tolerance,
reference, duration, model or energy changes. The positive-gain barrier and
QP transformations are checked mathematically. AB2 is a causal request
sampler; no continuous-theorem transfer is inferred. Three separate torque
differences, with per-cell max/RMS, are in SAMPLER_MAX_RMS.csv.

**One extra numerical solver probe FAILS and remains FAIL.** A preserved
alpha5 active fixture has an exact represented-QP optimum, but the guarded
solver reports infeasibility and stops with no torque. The selected original
alpha5 protocol uses its original solver, and v4 uses alpha10, so this hybrid
probe is outside both frozen experiment definitions. That scope separation
and known failure were explicitly predeclared before these fresh replays.
It blocks general guarded-QP/T27 qualification; it is not hidden, marked
passed, or used as a reason to erase successful unchanged numerical runs.
See GUARDED_QP_BLOCKER.json for the exact witness and remedy requirements.

User consultation/authorization is recorded. Additional administrative
approval is not requested. Attributable external reviewer names/signatures
were not supplied and remain null. Earlier pending-approval wording in
preserved historical reports is not a new administrative block here.

The final versioned policy is policy/a2_verified_v1/FINAL_A2_POLICY.json.
Its numerical GO is limited to the listed fixed experiments. General QP
qualification remains HOLD. Official A3 comparisons were not started and
remain NO-GO; Level1 certification is not established.
''')
    write(out/'REPRODUCIBILITY.md','''# Exact replay and standalone ZIP reproduction

The verification predeclaration was committed before the fresh 19-cell motion
replay. Original model, controllers, policies, references, thresholds, clocks
and integration source files were not edited. Original unchanged CLI runners
executed every new P1 and motion; no old trajectory was substituted for a run.
Commands, stdout/stderr, package/platform inventory, source hashes and exit
codes are in the replay directory.

Exact comparison covers all state, observer, reference, controller, QP matrix,
dual/solver-result, slack, stage/endpoint, energy and metric data retained in
the P1/execution traces. Only solve_runtime_s is removed as nondeterministic
instrumentation; no physical value gets a new tolerance. Refinement uses the
original unchanged inequalities separately. Metadata paths, timestamps and
outer archive compression timestamps are not simulated physical data.

Use Python3.12.14 on the recorded Linux environment and the unmodified pinned
requirements plus setuptools80.9.0. Exact bytes of compressed containers were
verified using zlib1.3.2. A differing compression runtime must not be silently
treated as identical evidence. The supplied dependency lock pins versions;
it is not a distribution-hashed lock.

The complete ZIP includes every old protected input and failed experiment,
not only the earlier overlay. Its restore tools reconstruct original bytes
and refuse different existing files. RUN_REPRODUCTION.py restores inputs,
then the original runners' full pre-motion SHA checks execute. A ZIP without
Git metadata gets a clearly labeled LOCAL input-staging commit solely to run
those unchanged checks. This is not a fabricated historical commit, signature
or independent machine reproduction. In a full Git checkout no such staging
is needed. The historical source/control commit IDs remain separately recorded.

The standalone restore/bootstrap/frozen-input checks and archive integrity are
verified during delivery. The fresh physical replays were executed in a clean
Git checkout; their data are included rather than claiming a second unrun
physical execution from the final downloaded ZIP.
''')
    print('Scoped A2 numerical technical policy',status,'general guarded-QP qualification HOLD',flush=True)
    return 0 if go else 3


if __name__=='__main__':raise SystemExit(main())
