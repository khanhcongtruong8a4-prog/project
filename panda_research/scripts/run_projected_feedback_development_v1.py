"""Predeclared development candidate or supplementary Delta ladder; no A3."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
import argparse,json,subprocess,traceback
from dataclasses import replace
from datetime import datetime,timezone
import numpy as np
from panda_dynamics import QMIN,QMAX,dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.stepper import HoldSchedule
from panda_closed_loop.preparation import AppliedTorquePrehold,endpoint_diagnostics
from panda_closed_loop.p1_r3 import SampledComputedTorque,compare_refinement
from panda_closed_loop.projected_feedback_ab2_v1 import strict_qp_check,run_a2_cell,BoundedProjectedFeedbackAB2QP,VERSION
from panda_closed_loop.projected_feedback_audit_v1 import audit_candidate as audit_extended
from panda_closed_loop.a2_qp_reliable_v1_1 import BoundedGuardedQP
from panda_closed_loop.a2_qp_v2 import NUMERICAL_POLICY,audit_qp_numerics
from panda_closed_loop.a2_extended import ExtendedReference,reference_screen,entrance_pairs,difference_statistics,negative_slack_report
from panda_closed_loop.trace_archive import write_trace

def write(p,d):
    with Path(p).open('x') as f:json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')

def run_cell(system, plan, reference_id, index, out):
    schedule = HoldSchedule(plan['C4_grid'][index]['control_period_s'], plan['C4_grid'][index]['rk4_step_s'])
    local = system
    startup = replace(system, controller=SampledComputedTorque(system.model,
        plan['startup_controller']['kp_s_inverse_squared'], plan['startup_controller']['kd_s_inverse']))
    waveform = lambda t: dual_harmonic_disturbance(t, system.policy.raw['disturbance']['amplitude_fraction'])
    runner = AppliedTorquePrehold(startup, schedule, plan['T_pre_s'], (QMIN+QMAX)/2,
                                  plan['q_radius_rad'], plan['qd_radius_rad_s'], waveform)
    print(f'{reference_id} cell {index}: P1 starts', flush=True)
    held = runner.run()
    hold_trace = write_trace(out/f'cell_{index}_prehold.ctz', held.trace)
    record = {'reference_id': reference_id, 'cell': index, 'grid': plan['C4_grid'][index],
              'prehold': {'completed': held.completed, 'decision': held.decision, 'failure': held.failure,
                          'state': held.state.record(), 'last_applied_torque': held.last_applied_torque,
                          'q_deviation_peak_rad': np.max([v['q_deviation_peak_rad'] for v in held.trace], axis=0),
                          'qd_peak_rad_s': np.max([v['qd_peak_rad_s'] for v in held.trace], axis=0),
                          'trace': hold_trace},
              'endpoint': None, 'a2': {'completed': False, 'passed': False, 'status': 'NOT_RUN_FAILED_P1'},
              'audit': {'passed': False, 'scope': 'NO_COMPLETED_EXECUTION'},
              'independent_controls_signature': None, 'independent_theory_signature': None}
    if not held.completed:
        record['actual_abort_QP_diagnostics'] = endpoint_diagnostics(local, runner, held)
        write(out/f'cell_{index}.json', record)
        return json_values(record)
    state = held.measured_state_at_zero()
    reference = ExtendedReference(state.q, state.qd, plan['references'][reference_id])
    _, endpoint_qp = strict_qp_check(local, state, runner.envelope, reference)
    physical = system.barriers.entry_conditions(state.q, state.qd, held.last_applied_torque)
    pairs = entrance_pairs(system, state, runner.envelope.value(0.))
    screen = reference_screen(system, reference, plan['reference_screen_times_s'])
    entrance = (physical['passed'] and endpoint_qp['strict_pass'] and pairs['position']['passed']
                and pairs['velocity']['passed'] and screen['passed'])
    record['endpoint'] = {'state': held.state.record(), 'physical_slacks': physical,
                          'previous_applied_torque': held.last_applied_torque, 'QP': endpoint_qp,
                          'observer_elapsed_s': runner.clock.elapsed(0.), 'varpi': runner.envelope.value(0.),
                          'valid_zero_endpoint': bool(physical['passed'] and endpoint_qp['strict_pass']),
                          'q_qd_z_transfer_exact': all(np.array_equal(getattr(state, k), getattr(held.state, k)) for k in ['q', 'qd', 'z']),
                          'observer_reset': False, 'clock_reset': False,
                          'necessary_pairs': pairs, 'reference_screen': screen,
                          'entrance_passed': bool(entrance), 'reference_coefficients': reference.coefficients,
                          'reference_boundaries_s': reference.boundaries, 'reference_target_q': reference.target_q}
    if not entrance:
        record['a2'].update(status='NOT_RUN_FAILED_ENTRANCE', failure={'reason': 'PREDECLARED_ENTRANCE_FAILURE_NO_ACTUATION'})
        write(out/f'cell_{index}.json', record)
        return json_values(record)
    motion = run_a2_cell(local, state, schedule, runner.envelope, reference, waveform, endpoint_qp)
    trace = {'updates': motion.pop('updates'), 'substeps': motion.pop('trace')}
    motion['trace'] = write_trace(out/f'cell_{index}_execution.ctz', trace)
    motion['status'] = 'PASS_NUMERICAL_CELL' if motion['passed'] else 'FAIL_NUMERICAL_CELL'
    record['a2'] = motion
    record['sampler_differences'] = difference_statistics(trace['updates'])
    record['negative_slacks'] = negative_slack_report(trace)
    record = json_values(record)
    if motion['completed']:
        record['audit'] = audit_extended(record, out, system, plan)
        extra = audit_qp_numerics(trace['updates'], system.barriers.taumax)
        record['audit']['versioned_QP_numerics'] = extra
        record['audit']['checks']['recomputed_both_QP_KKT_scalings_with_duals'] = extra['passed']
        record['audit']['passed'] = record['audit']['passed'] and extra['passed']
    else:
        record['audit'] = {'passed': False, 'scope': 'INCOMPLETE_HORIZON',
                           'lossless_trace_roundtrip': True, 'failure_preserved': True}
    write(out/f'cell_{index}.json', record)
    print(f"{reference_id} cell {index}: {motion['status']}; t={motion['final_state']['physical_t_s']:.6f}; audit={record['audit']['passed']}", flush=True)
    return json_values(record)

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['candidate','ladder'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    freeze=ROOT/'policy/pre_a3_blockers_v1/DEVELOPMENT_PREDECLARATION.json';f=json.loads(freeze.read_text())
    for name,h in f['candidate_sources_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Frozen candidate source changed: '+name)
    commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(freeze)],cwd=ROOT,text=True).strip()
    if not commit:raise ValueError('Commit candidate policy before motion')
    plan=json.loads((ROOT/'policy/a2_extended_v2/A2_EXTENDED_PREDECLARATION.json').read_text())
    if a.mode=='ladder':
        # This is a separately labeled convergence diagnostic, never replacement
        # of the original C4 grid, thresholds or failed historical comparisons.
        plan['C4_grid']=f['supplementary_ladder_grid']
        global strict_qp_check,run_a2_cell,audit_extended
        from panda_closed_loop.p1_r3 import strict_qp_check,run_a2_cell
        from panda_closed_loop.a2_extended import audit_extended
        from panda_closed_loop.p1_r4 import AB2TorqueController
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    write(out/'run_started.json',{'start_utc':datetime.now(timezone.utc).isoformat(),'mode':a.mode,'freeze_commit':commit,
        'predeclaration_sha256':digest(freeze),'policy':'LEGACY_ALPHA5_E3_DEVELOPMENT_ONLY',
        'model_gains_guard_safety_constraints_thresholds_changed':False,'official_A3':False,'external_signatures':None})
    system=build_components();system.geometry.function=system.geometry.function.expand();cells=[]
    for index in range(len(plan['C4_grid'])):
        try:
            wrapper=BoundedProjectedFeedbackAB2QP if a.mode=='candidate' else BoundedGuardedQP
            with wrapper(system.barriers.taumax,NUMERICAL_POLICY,15.) as qp:
                current=replace(system,qp=qp)
                if a.mode=='ladder':current=replace(current,controller=AB2TorqueController(system.controller))
                cells.append(run_cell(current,plan,'E3',index,out))
        except Exception:
            failure={'cell':index,'engineering_error':traceback.format_exc(),'a2':{'completed':False,'passed':False},'audit':{'passed':False}}
            write(out/f'cell_{index}_engineering_error.json',failure);cells.append(failure)
    refinement=compare_refinement(cells,plan['fixed_acceptance_thresholds']) if a.mode=='candidate' else None
    passed=all(c['a2']['passed'] and c['audit']['passed'] for c in cells)
    if refinement is not None:passed=passed and all(x['status']=='PASS' for x in refinement['comparisons'])
    write(out/'summary.json',{'mode':a.mode,'outcome':'PASS' if passed else 'FAIL','cells':cells,'refinement':refinement,
        'not_a_replacement_for_historical_C4':True,'A3_executed':False,'Level1':False,'human_signatures':None})
    write(out/'run_completed.json',{'finish_utc':datetime.now(timezone.utc).isoformat(),'outcome':'PASS' if passed else 'FAIL',
        'engineering_errors':any('engineering_error' in c for c in cells)})
    return 0 if passed else 3

if __name__=='__main__':raise SystemExit(main())
