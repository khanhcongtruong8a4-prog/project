"""Exclusive, predeclared E1/E2/E3 numerical development campaign."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import shutil
import subprocess
import traceback
import numpy as np
from case_sets import all_cases
from panda_dynamics import QMIN, QMAX, dual_harmonic_disturbance
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.assembly import build_components
from panda_closed_loop.logging import json_values
from panda_closed_loop.stepper import HoldSchedule
from panda_closed_loop.preparation import AppliedTorquePrehold, endpoint_diagnostics
from panda_closed_loop.p1_r3 import SampledComputedTorque, strict_qp_check, run_a2_cell, compare_refinement
from panda_closed_loop.p1_r4 import AB2TorqueController
from panda_closed_loop.a2_extended import (ExtendedReference, reference_screen, entrance_pairs,
                                           audit_extended, difference_statistics, negative_slack_report, BoundedQP)
from panda_closed_loop.trace_archive import write_trace
from panda_closed_loop.a2_qp_v2 import BoundedGuardedQP, NUMERICAL_POLICY, audit_qp_numerics
from panda_closed_loop.trace_archive import read_trace

PLAN = 'policy/a2_extended_v2/A2_EXTENDED_PREDECLARATION.json'
FREEZE = 'policy/a2_extended_v2/FROZEN_INPUTS.json'


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(json_values(value), f, indent=2, allow_nan=False)
        f.write('\n')


def verify():
    f = json.loads((ROOT/FREEZE).read_text())
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(ROOT/FREEZE)], cwd=ROOT, text=True).strip()
    if not commit or subprocess.check_output(['git', 'show', f'{commit}:panda_research/{FREEZE}'], cwd=ROOT) != (ROOT/FREEZE).read_bytes():
        raise ValueError('Extended predeclaration must be committed before motion')
    changed = [n for n, h in f['files'].items() if digest(ROOT/n) != h]
    if changed:
        raise ValueError('Frozen input changed: '+', '.join(changed))
    plan = json.loads((ROOT/PLAN).read_text())
    p = Policy.load()
    if plan['C4_grid'] != p.raw['integration']['validation_grid'] or plan['fixed_acceptance_thresholds'] != p.raw['fixed_acceptance_thresholds']:
        raise ValueError('Original grid or thresholds changed')
    return plan, f, commit


def run_cell(system, plan, reference_id, index, out):
    schedule = HoldSchedule(plan['C4_grid'][index]['control_period_s'], plan['C4_grid'][index]['rk4_step_s'])
    local = replace(system, controller=AB2TorqueController(system.controller))
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', choices=['E1', 'E2', 'E3'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--contracts', type=Path, required=True)
    args = parser.parse_args()
    plan, frozen, commit = verify()
    contracts = json.loads(args.contracts.read_text())
    if not contracts.get('overall_pass') or contracts.get('tests_run', 0) < 1:
        raise ValueError('Executed passing contracts required')
    if any(digest(ROOT/n) != sha for n, sha in contracts['source_hashes'].items()):
        raise ValueError('Contract source differs from frozen implementation')
    out = args.output.resolve()
    if not out.is_relative_to((ROOT/'runs/a2_extended_v2').resolve()):
        raise ValueError('Exclusive output must be under runs/a2_extended_v2')
    out.mkdir(parents=True, exist_ok=False)
    before = {n: h for n, h in frozen['files'].items()}
    metadata = {'start_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'PREDECLARED_DEVELOPMENT_A2_EXTENDED_NOT_A3',
                'reference_id': args.reference, 'definition': plan['references'][args.reference],
                'command': [sys.executable, *sys.argv], 'cwd': str(ROOT), 'python': sys.version,
                'platform': platform.platform(), 'packages': {v.metadata['Name']: v.version for v in importlib.metadata.distributions()},
                'freeze_commit': commit, 'plan_sha256': digest(ROOT/PLAN), 'input_manifest_sha256': digest(ROOT/FREEZE),
                'physical_runs_executed_here': True, 'human_signatures': None, 'retuning': False, 'numerical_QP_amendment': NUMERICAL_POLICY}
    write(out/'run_started.json', metadata)
    for name in frozen['new_source_files']+[PLAN, FREEZE]:
        target = out/'source_snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
    cells, error, code = [], None, 1
    try:
        system = build_components()
        original, expanded = system.geometry.function, system.geometry.function.expand()
        geometry_checks = []
        for index, q in enumerate(all_cases()[0]):
            same = all(np.array_equal(a, b) for a, b in zip(original(q), expanded(q)))
            geometry_checks.append({'case': index, 'bitwise_equal': same})
            if not same:
                raise ValueError('Geometry backend changed')
        system.geometry.function = expanded
        write(out/'geometry_verification.json', geometry_checks)
        for index in range(4):
            try:
                with BoundedGuardedQP(system.barriers.taumax, NUMERICAL_POLICY, plan['QP_wall_time_budget_s']) as guarded:
                    cell_system = replace(system, qp=guarded)
                    cells.append(run_cell(cell_system, plan, args.reference, index, out))
            except Exception:
                item = {'cell': index, 'reference_id': args.reference, 'grid': plan['C4_grid'][index],
                        'engineering_error': traceback.format_exc(), 'a2': {'completed': False, 'passed': False},
                        'audit': {'passed': False}}
                write(out/f'cell_{index}_engineering_error.json', item)
                cells.append(item)
                print(f'{args.reference} cell {index}: ENGINEERING_ERROR', flush=True)
        refinement = compare_refinement(cells, plan['fixed_acceptance_thresholds'])
        passed = refinement['passed'] and all(c['status'] == 'PASS' for c in refinement['comparisons'])
        passed = passed and all(c.get('audit', {}).get('passed') for c in cells)
        engineering_error = any('engineering_error' in c for c in cells)
        result = {'reference_id': args.reference, 'outcome': 'PASS' if passed else 'NOT_VERIFIED' if engineering_error else 'FAIL',
                  'cells': cells, 'refinement': refinement, 'A3_executed': False, 'independent_signatures': None,
                  'baseline_result_unchanged': True, 'physical_or_controller_retuning_performed': False, 'numerical_solver_amended': True, 'numerical_QP_amendment': NUMERICAL_POLICY}
        write(out/'summary.json', result)
        code = 1 if engineering_error else 0 if passed else 3
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
    finally:
        changed = [n for n, h in before.items() if digest(ROOT/n) != h]
        if changed:
            code = 1
        metadata.update(finish_utc=datetime.now(timezone.utc).isoformat(), exit_code=code,
                        engineering_error=error, frozen_inputs_unchanged=not changed, changed_files=changed)
        write(out/'run_completed.json', metadata)
    print('Evidence:', out, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
