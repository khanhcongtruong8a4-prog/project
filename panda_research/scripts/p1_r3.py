"""Run the committed, frozen P1-r3 and all four A2 numerical cells once.

Exit 0: all numerical criteria pass; 3: retained scientific rejection;
1: invalid freeze or engineering error. Never edits old evidence or approvals.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import traceback
import numpy as np
from panda_dynamics import QMIN, QMAX, dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.preparation import AppliedTorquePrehold
from panda_closed_loop.stepper import HoldSchedule
from panda_closed_loop.p1_r3 import (SampledComputedTorque, QuinticMeasuredReference,
                                    strict_qp_check, run_a2_cell, compare_refinement)

PLAN = 'policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json'
FREEZE = 'policy/v1.2.2-r3/FROZEN_INPUTS.json'


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(json_values(value), f, indent=2, allow_nan=False)
        f.write('\n')


def write_compressed(path, value):
    # Canonical compact JSON and deterministic gzip header. Exclusive creation.
    payload = json.dumps(json_values(value), separators=(',', ':'), allow_nan=False).encode()
    with Path(path).open('xb') as f:
        f.write(gzip.compress(payload, mtime=0))
    return {'file': Path(path).name, 'sha256': digest(path),
            'uncompressed_json_sha256': hashlib.sha256(payload).hexdigest()}


def verify_freeze():
    path = ROOT/FREEZE
    freeze = json.loads(path.read_text())
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(path)], cwd=ROOT, text=True).strip()
    if not commit:
        raise ValueError('Commit the complete controller/test plan freeze before any test')
    committed = subprocess.check_output(['git', 'show', f'{commit}:panda_research/{FREEZE}'], cwd=ROOT)
    if committed != path.read_bytes():
        raise ValueError('Frozen manifest differs from its committed pre-test version')
    for name, sha in freeze['files'].items():
        source = (ROOT/name).resolve()
        if not source.is_relative_to(ROOT) or digest(source) != sha:
            raise ValueError('Frozen input changed: '+name)
    plan = json.loads((ROOT/PLAN).read_text())
    policy = Policy.load()
    if plan['C4_grid'] != policy.raw['integration']['validation_grid']:
        raise ValueError('C4 grid changed')
    if plan['fixed_acceptance_thresholds'] != policy.raw['fixed_acceptance_thresholds']:
        raise ValueError('Acceptance thresholds changed')
    if not plan['authorization']['P1_A2_numerical_testing']:
        raise ValueError('Numerical execution authority missing')
    return plan, freeze, commit


def run_cell(system, plan, index, out):
    grid = plan['C4_grid'][index]
    schedule = HoldSchedule(grid['control_period_s'], grid['rk4_step_s'])
    controller = SampledComputedTorque(system.model, plan['startup_controller']['kp_s_inverse_squared'],
                                       plan['startup_controller']['kd_s_inverse'])
    startup_system = replace(system, controller=controller)
    waveform = lambda t: dual_harmonic_disturbance(t, system.policy.raw['disturbance']['amplitude_fraction'])
    runner = AppliedTorquePrehold(startup_system, schedule, plan['T_pre_s'], (QMIN+QMAX)/2,
                                  plan['q_radius_rad'], plan['qd_radius_rad_s'], waveform)
    print(f'cell {index}: starting frozen P1-r3', flush=True)
    result = runner.run()
    prehold = {'decision': result.decision, 'completed': result.completed, 'failure': result.failure,
               'state': result.state.record(), 'last_applied_torque': result.last_applied_torque,
               'observer_elapsed_s': runner.clock.elapsed(result.state.t),
               'propagated_varpi': runner.envelope.value(result.state.t),
               'q_deviation_peak_rad': np.max([t['q_deviation_peak_rad'] for t in result.trace], axis=0),
               'qd_peak_rad_s': np.max([t['qd_peak_rad_s'] for t in result.trace], axis=0),
               'minimum_observer_envelope_slack_Nm': np.min([s['observer_envelope_slack']
                   for t in result.trace for s in t['stage_and_endpoint_diagnostics']], axis=0),
               'trace': write_compressed(out/f'cell_{index}_prehold_trace.json.gz', result.trace)}
    record = {'cell': index, 'grid': grid, 'prehold': prehold, 'endpoint': None,
              'a2': {'completed': False, 'passed': False, 'status': 'NOT_RUN_INVALID_PREHOLD'},
              'true_ODE_neighborhood_certified': False, 'independent_signatures': None}
    if result.completed:
        state = result.measured_state_at_zero()
        ref_config = plan['A2_reference']
        reference = QuinticMeasuredReference(state.q, state.qd, ref_config['joint_offset_rad'], ref_config['duration_s'])
        _, endpoint_qp = strict_qp_check(system, state, runner.envelope, reference)
        physical = system.barriers.entry_conditions(state.q, state.qd, result.last_applied_torque)
        record['endpoint'] = {'state': result.state.record(), 'previous_applied_torque': result.last_applied_torque,
                              'physical_slacks': physical, 'QP': endpoint_qp,
                              'valid_zero_endpoint': bool(physical['passed'] and endpoint_qp['strict_pass']),
                              'q_qd_z_transfer_exact': all(np.array_equal(getattr(state, key), getattr(result.state, key))
                                                          for key in ['q', 'qd', 'z']),
                              'observer_reset': False, 'clock_reset': False,
                              'reference_coefficients': reference.coefficients,
                              'reference_target_q': reference.target_q}
        execution = run_a2_cell(system, state, schedule, runner.envelope, reference, waveform, endpoint_qp)
        trace = {'updates': execution.pop('updates'), 'substeps': execution.pop('trace')}
        execution['trace'] = write_compressed(out/f'cell_{index}_a2_trace.json.gz', trace)
        execution['status'] = 'PASS_NUMERICAL_CELL' if execution['passed'] else 'FAIL_NUMERICAL_CELL'
        record['a2'] = execution
    else:
        # Diagnose the actual abort, without presenting it as a zero endpoint.
        from panda_closed_loop.preparation import endpoint_diagnostics
        record['abort_diagnostics'] = endpoint_diagnostics(system, runner, result)
    write(out/f'cell_{index}.json', record)
    print(f"cell {index}: P1 {result.decision}; A2 {record['a2']['status']}", flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    plan, freeze, commit = verify_freeze()
    now = datetime.now(timezone.utc)
    out = (args.output or ROOT/'runs/p1_r3'/now.strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    if not out.is_relative_to((ROOT/'runs/p1_r3').resolve()):
        raise ValueError('Outputs must be below runs/p1_r3/')
    out.mkdir(parents=True, exist_ok=False)
    metadata = {'start_utc': now.isoformat(), 'scope': 'USER_AUTHORIZED_P1_A2_NUMERICAL_TESTING',
                'command': [sys.executable, *sys.argv], 'cwd': str(ROOT),
                'python': sys.version, 'platform': platform.platform(),
                'packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
                'base_commit': plan['base_commit'], 'freeze_commit': commit,
                'freeze_sha256': digest(ROOT/FREEZE), 'plan_sha256': digest(ROOT/PLAN),
                'human_signatures': None, 'retuning_performed': False}
    write(out/'run_started.json', metadata)
    # Small executable snapshot, plus the complete frozen input inventory.
    for name in freeze['new_implementation_files']+[PLAN, FREEZE]:
        dest = out/'source_snapshot'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, dest)
    cells, error, code = [], None, 1
    try:
        policy = Policy.load()
        write(out/'source_audit.json', policy.source_audit())
        system = build_components(policy)
        for index in range(4):
            # Cell-local engineering failures never silently omit the others.
            try:
                cells.append(run_cell(system, plan, index, out))
            except Exception:
                row = {'cell': index, 'grid': plan['C4_grid'][index],
                       'engineering_error': traceback.format_exc(),
                       'a2': {'completed': False, 'passed': False, 'status': 'ENGINEERING_ERROR'}}
                write(out/f'cell_{index}_error.json', row)
                cells.append(row)
                print(f'cell {index}: ENGINEERING_ERROR', flush=True)
        comparison = compare_refinement(cells, policy.raw['fixed_acceptance_thresholds'])
        all_prehold = all(c.get('prehold', {}).get('completed') for c in cells)
        all_endpoint = all(c.get('endpoint') and c['endpoint']['valid_zero_endpoint'] for c in cells)
        passed = all_prehold and all_endpoint and comparison['passed']
        errors = any('engineering_error' in c for c in cells)
        summary = {'scope': metadata['scope'], 'base_commit': plan['base_commit'], 'freeze_commit': commit,
                   'cells': cells, 'P1_numerical_hold': 'PASS' if all_prehold else 'FAIL',
                   'actual_zero_endpoint_QPs': 'PASS' if all_endpoint else 'FAIL_OR_UNAVAILABLE',
                   'A2_numerical': 'PASS' if passed else 'FAIL', 'refinement': comparison,
                   'A2_independently_reviewed_experiment': 'NOT_CLAIMED',
                   'A3': 'NO-GO', 'M1': 'OPEN_UNCHANGED', 'T27_complete': 'NOT_RUN',
                   'G2.5': 'NOT_RUN', 'Level_1': 'NO-GO', 'publication': 'NO-GO',
                   'independent_signatures': None, 'retuning_performed': False,
                   'true_ODE_continuous_proof': False,
                   'sampled_observer_sensitivity': 'NOT_RUN_SEPARATE_CONVENTION_NOT_AUTHORIZED_BY_THIS_FROZEN_PLAN'}
        write(out/'summary.json', summary)
        code = 1 if errors else 0 if passed else 3
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
    finally:
        changed = [name for name, sha in freeze['files'].items() if digest(ROOT/name) != sha]
        metadata.update(finish_utc=datetime.now(timezone.utc).isoformat(),
                        frozen_inputs_unchanged=not changed, changed_frozen_inputs=changed,
                        engineering_error=error, exit_code=code)
        if changed:
            code = metadata['exit_code'] = 1
        write(out/'run_completed.json', metadata)
    print('Evidence:', out, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
