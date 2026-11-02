"""Reproducible model review, external-engine comparison, and plant smoke test.

Run: python review_checks.py
This does not implement or validate the paper's planner, observer, or HOCBF QP.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from evidence_paths import evidence_dir
OUTPUT = evidence_dir()

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import platform
import sys
import time
import xml.etree.ElementTree as ET

import casadi
import mujoco
import numpy as np
import scipy
from scipy.integrate import solve_ivp
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import panda_dynamics as pd

CHECKS = {}
DETAILS = []
CASE_INDEX = None


def close(name, actual, reference, atol, rtol=0.0):
    actual, reference = np.asarray(actual), np.asarray(reference)
    if actual.shape != reference.shape:
        raise AssertionError(f'{name}: shape {actual.shape} != {reference.shape}')
    error = np.abs(actual - reference)
    allowed = atol + rtol * np.abs(reference)
    ratio = float(np.max(error / allowed))
    row = CHECKS.setdefault(name, {
        'passed': True, 'atol': atol, 'rtol': rtol,
        'max_absolute_error': 0.0, 'max_tolerance_ratio': 0.0, 'comparisons': 0,
    })
    finite = bool(np.all(np.isfinite(error)))
    row['passed'] &= finite and bool(np.all(error <= allowed))
    row['max_absolute_error'] = max(row['max_absolute_error'], float(np.max(error)))
    row['max_tolerance_ratio'] = max(row['max_tolerance_ratio'], ratio)
    row['comparisons'] += 1
    DETAILS.append({'state_index': CASE_INDEX, 'check': name,
                    'max_absolute_error': float(np.max(error)),
                    'max_tolerance_ratio': ratio, 'atol': atol, 'rtol': rtol,
                    'passed': finite and bool(np.all(error <= allowed))})


def condition(name, passed, **details):
    CHECKS[name] = {'passed': bool(passed), **details}


def load_original():
    spec = importlib.util.spec_from_file_location('original_model', HERE.parent / 'baseline/panda_dynamics.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reference():
    """Preserve the independently transcribed COM tensors through MJCF import.

    MuJoCo 3.3.7's fullinertia decomposition loses enough precision to fail the
    protocol's tight M/ID tolerances. Diagonalize the XML's tensors explicitly,
    then verify the compiled tensors against those same source tensors. This
    does not obtain reference inertias from the implementation being tested.
    """
    root = ET.parse(HERE.parent / 'references/mujoco/reference_model.xml').getroot()
    raw = mujoco.MjModel.from_xml_path(str(HERE.parent / 'references/mujoco/reference_model.xml'))
    tensors, import_errors = [], []
    for i, inertial in enumerate(root.iter('inertial'), 1):
        xx, yy, zz, xy, xz, yz = np.fromstring(inertial.attrib.pop('fullinertia'), sep=' ')
        tensor = np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        tensors.append(tensor)
        rot = np.zeros(9)
        mujoco.mju_quat2Mat(rot, raw.body_iquat[i])
        reconstructed = rot.reshape(3, 3) @ np.diag(raw.body_inertia[i]) @ rot.reshape(3, 3).T
        import_errors.append(float(np.max(np.abs(reconstructed - tensor))))
        values, axes = np.linalg.eigh(tensor)
        if np.linalg.det(axes) < 0:
            axes[:, 0] *= -1
        quat = Rotation.from_matrix(axes).as_quat(scalar_first=True)
        inertial.set('diaginertia', ' '.join(format(x, '.17g') for x in values))
        inertial.set('quat', ' '.join(format(x, '.17g') for x in quat))
    xml = ET.tostring(root, encoding='unicode')
    (OUTPUT / 'reference_model_precise.xml').write_text(xml, encoding='utf-8')
    model = mujoco.MjModel.from_xml_string(xml)
    for i, tensor in enumerate(tensors, 1):
        rot = np.zeros(9)
        mujoco.mju_quat2Mat(rot, model.body_iquat[i])
        rot = rot.reshape(3, 3)
        close('Reference: compiled COM tensors match independent XML constants',
              rot @ np.diag(model.body_inertia[i]) @ rot.T, tensor, 5e-15)
    return model, {'direct_fullinertia_import_max_body_errors_kg_m2': import_errors,
                   'method_used': 'explicit NumPy eigh of independent XML tensors, then diaginertia/quat; compiled tensors rechecked',
                   'production_model_or_tolerances_changed': False}


def api_regressions(model, original):
    q = (pd.QMIN + pd.QMAX) / 2
    v = np.linspace(-0.12, 0.16, 7)
    a = np.linspace(-0.3, 0.4, 7)
    d = np.linspace(-0.1, 0.1, 7)
    tau = model.evaluate(q, v, a)['ID'] - d
    forms = (lambda x: x, lambda x: x.reshape(7, 1), lambda x: x.reshape(1, 7))
    for fq, fv, ft, fd in itertools.product(forms, repeat=4):
        out = model.acceleration(fq(q), fv(v), ft(tau), fd(d))
        close('API: acceleration shape variants', out, a, 1e-10)
    for form in forms:
        close('API: friction shape variants', pd.friction(form(v)), pd.friction(v), 1e-15)
        close('API: FK shape variants', pd.mdh_fk_numpy(form(q))[1][1], pd.mdh_fk_numpy(q)[1][1], 1e-14)
    invalid = [0.0, np.zeros(6), np.zeros((7, 2)), np.full(7, np.nan), np.full(7, np.inf)]
    rejected, total = 0, 0
    for bad in invalid:
        calls = [lambda: model.evaluate(bad), lambda: model.evaluate(q, bad),
                 lambda: model.evaluate(q, v, bad), lambda: model.acceleration(q, v, bad),
                 lambda: model.acceleration(q, v, tau, bad), lambda: pd.friction(bad),
                 lambda: pd.mdh_fk_numpy(bad), lambda: pd.urdf_fk_numpy(bad)]
        for call in calls:
            total += 1
            try:
                call()
            except ValueError:
                rejected += 1
    for bad in (-0.02, np.nan, np.inf, [0.02]):
        for call in (lambda: pd.disturbance_bounds(bad), lambda: pd.dual_harmonic_disturbance(0.0, bad)):
            total += 1
            try:
                call()
            except ValueError:
                rejected += 1
    for bad in (np.nan, np.inf, [0.0]):
        total += 1
        try:
            pd.dual_harmonic_disturbance(bad)
        except ValueError:
            rejected += 1
    condition('API: reject malformed and nonfinite inputs', rejected == total, rejected=rejected, cases=total)
    om = original.PandaDynamics()
    observations = {}
    for name, call in {
        'column_velocity_acceleration': lambda: om.acceleration(q, v[:, None], tau, d),
        'column_torque_acceleration': lambda: om.acceleration(q, v, tau[:, None], d),
        'column_disturbance_acceleration': lambda: om.acceleration(q, v, tau, d[:, None]),
        'column_velocity_friction': lambda: original.friction(v[:, None]),
    }.items():
        try:
            observations[name] = {'returned_shape': list(call().shape), 'expected_shape': [7]}
        except Exception as exc:
            observations[name] = {'exception': repr(exc)}
    observations['negative_amplitude_bounds'] = [x.tolist() for x in original.disturbance_bounds(-0.02)]
    condition('Regression: original broadcasting defect reproduced',
              all(observations[k].get('returned_shape') == [7, 7] for k in list(observations)[:4]))
    return om, observations


def main():
    global CASE_INDEX
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--random-poses', type=int, default=128)
    parser.add_argument('--seed', type=int, default=20261101)
    parser.add_argument('--report', type=Path, default=OUTPUT / 'mujoco_validation.json')
    parser.add_argument('--include-protocol-cases', action='store_true')
    args = parser.parse_args()
    if args.random_poses < 20:
        parser.error('--random-poses must be at least 20')
    start = time.perf_counter()
    rng = np.random.default_rng(args.seed)
    model = pd.PandaDynamics()
    original = load_original()
    om, bugs = api_regressions(model, original)
    reference, import_diagnostic = load_reference()
    data = mujoco.MjData(reference)
    condition('Reference: exactly seven frictionless hinge coordinates', reference.nq == 7 and reference.nv == 7
              and np.all(reference.dof_armature == 0) and np.all(reference.dof_damping == 0)
              and np.all(reference.dof_frictionloss == 0))
    poses = [np.zeros(7), (pd.QMIN + pd.QMAX) / 2, pd.QMIN.copy(), pd.QMAX.copy()]
    poses.extend(rng.uniform(pd.QMIN, pd.QMAX, size=(args.random_poses, 7)))
    velocities = rng.uniform(-pd.VMAX, pd.VMAX, size=(len(poses), 7))
    accelerations = rng.uniform(-3, 3, size=(len(poses), 7))
    if args.include_protocol_cases:
        from case_sets import protocol_cases
        pq, pv, pa = protocol_cases()
        poses = np.vstack([poses, pq])
        velocities = np.vstack([velocities, pv])
        accelerations = np.vstack([accelerations, pa])
    eigen_min, eigen_max, triangle_slack = float('inf'), -float('inf'), float('inf')
    for values in pd.INERTIA6:
        ev = np.linalg.eigvalsh(pd.inertia_tensor(values))
        condition(f'Body tensor {len([k for k in CHECKS if k.startswith("Body tensor")])+1}: SPD', np.min(ev) > 0,
                  eigenvalues=ev.tolist())
        triangle_slack = min(triangle_slack, float(ev[0] + ev[1] - ev[2]))
    condition('Body inertia principal triangle inequalities', triangle_slack > 0, minimum_slack=triangle_slack)
    for index, (q, v, a) in enumerate(zip(poses, velocities, accelerations)):
        CASE_INDEX = index
        e = model.evaluate(q, v, a)
        old = om.evaluate(q, v, a)
        for key in e:
            close(f'Flat-input behavior preserved: {key}', np.asarray(e[key]), np.asarray(old[key]), 1e-14)
        ev = np.linalg.eigvalsh(e['M'])
        eigen_min, eigen_max = min(eigen_min, float(ev[0])), max(eigen_max, float(ev[-1]))
        close('M symmetry', e['M'], e['M'].T, 5e-12)
        mdot = np.einsum('ijk,k->ij', e['dM'], v)
        close('Internal C construction: Mdot = C + CT (shared dM)', mdot, e['C'] + e['C'].T, 3e-10)
        close('Skew power identity', np.asarray(v @ (mdot - 2*e['C']) @ v), np.asarray(0.0), 1e-9)
        close('Forward/inverse dynamics and disturbance sign', model.acceleration(q, v, e['ID'] - 0.1, np.full(7, 0.1)), a, 1e-10)
        qrot = q.copy(); qrot[0] += 0.4
        close('q1 invariance of M', model.evaluate(qrot)['M'], e['M'], 1e-10)
        mechanical_power = v @ e['M'] @ a + 0.5 * v @ mdot @ v + e['g'] @ v
        close('Inverse-dynamics mechanical power', np.asarray(v @ (e['ID'] - e['F'])), np.asarray(mechanical_power), 1e-9)
        data.qpos[:] = q
        data.qvel[:] = v
        mujoco.mj_forward(reference, data)
        refM = np.zeros((7, 7))
        mujoco.mj_fullM(reference, refM, data.qM)
        close('MuJoCo: mass matrix', e['M'], refM, 1e-9, 1e-9)
        close('MuJoCo: kinetic energy', np.asarray(0.5*v@e['M']@v), np.asarray(data.energy[1]), 1e-9, 1e-9)
        close('MuJoCo: potential energy', np.asarray(e['U']), np.asarray(data.energy[0]), 1e-8, 1e-9)
        close('MuJoCo: Coriolis-centrifugal plus gravity', e['C'] @ v + e['g'], data.qfrc_bias.copy(), 1e-8, 1e-9)
        close('MuJoCo: flange FK', e['flange'], data.site_xpos[0].copy(), 1e-10, 1e-9)
        poses_mdh, flange = pd.mdh_fk_numpy(q)
        poses_urdf, _ = pd.urdf_fk_numpy(q)
        for i, ((R, p), (Ru, pu)) in enumerate(zip(poses_mdh, poses_urdf)):
            close('NumPy: MDH vs URDF link positions', p, pu, 1e-10, 1e-9)
            close('NumPy: MDH vs URDF link rotations', R, Ru, 1e-10, 1e-9)
            close('MuJoCo: link positions', p, data.xpos[i+1].copy(), 1e-10, 1e-9)
            close('MuJoCo: link rotations', R, data.xmat[i+1].reshape(3, 3).copy(), 1e-10, 1e-9)
        close('CasADi vs NumPy flange', e['flange'], flange[1], 1e-10, 1e-9)
        # mj_inverse uses the specified qacc; Gaz friction is external to MJCF.
        data.qacc[:] = a
        mujoco.mj_inverse(reference, data)
        close('MuJoCo: full inverse dynamics including Gaz friction', e['ID'], data.qfrc_inverse.copy() + e['F'], 1e-8, 1e-9)
        data.qvel[:] = 0
        mujoco.mj_forward(reference, data)
        close('MuJoCo: gravity independently isolated', e['g'], data.qfrc_bias.copy(), 1e-8, 1e-9)
        data.qvel[:] = v
        data.qfrc_applied[:] = e['ID'] - e['F']
        mujoco.mj_forward(reference, data)
        close('MuJoCo: forward dynamics', data.qacc.copy(), a, 1e-8, 1e-9)
        data.qfrc_applied[:] = 0
        if index < 16:
            step = 2e-6
            dMfd = np.zeros((7, 7, 7)); gfd = np.zeros(7)
            for k in range(7):
                dq = np.zeros(7); dq[k] = step
                plus, minus = model.evaluate(q+dq), model.evaluate(q-dq)
                dMfd[:, :, k] = (plus['M'] - minus['M']) / (2*step)
                gfd[k] = (plus['U'] - minus['U']) / (2*step)
            close('Finite differences: dM tensor layout and values', e['dM'], dMfd, 5e-8)
            close('Finite differences: gravity potential gradient', e['g'], gfd, 5e-8)
    CASE_INDEX = None
    condition('Sampled M positive definite (not global certificate)', eigen_min > 0,
              min_sampled_eigenvalue=eigen_min, max_sampled_eigenvalue=eigen_max, states=len(poses))
    close('Friction at zero', pd.friction(np.zeros(7)), np.zeros(7), 1e-15)
    min_friction_power = float('inf')
    for speed in np.linspace(-5, 5, 1001):
        v = np.full(7, speed)
        F = pd.friction(v)
        # Independent transcription of the pinned author logistic expression.
        p1 = np.array([.54615,.87224,.64068,1.2794,.83904,.30301,.56489])
        p2 = np.array([5.1181,9.0657,10.136,5.5903,8.3469,17.133,10.336])
        p3 = np.array([.039533,.025882,-.04607,.036194,.026226,-.021047,.0035526])
        Fref = p1/(1+np.exp(-p2*(v+p3))) - p1/(1+np.exp(-p2*p3))
        close('Friction vs author logistic formula', F, Fref, 1e-14)
        min_friction_power = min(min_friction_power, float(np.min(v*F)))
    condition('Component friction dissipation on velocity grid', min_friction_power >= 0, minimum=min_friction_power)
    disturbance_stats = []
    phi = 2*np.pi*np.arange(7)/7
    for amplitude in (0.0, .01, .02, .04):
        bound, rate = pd.disturbance_bounds(amplitude)
        max_magnitude = np.zeros(7); max_rate = np.zeros(7)
        for t in np.linspace(0, 2*np.pi, 2001):
            d = pd.dual_harmonic_disturbance(t, amplitude)
            derivative = amplitude*pd.TAUMAX*(.6*np.cos(t+phi)-.8*np.sin(2*t+phi))
            max_magnitude = np.maximum(max_magnitude, np.abs(d))
            max_rate = np.maximum(max_rate, np.abs(derivative))
        condition(f'Disturbance bounds corroboration at amplitude {amplitude}',
                  np.all(max_magnitude <= bound+1e-12) and np.all(max_rate <= rate+1e-12))
        disturbance_stats.append({'amplitude': amplitude, 'bounds': bound.tolist(), 'rate_bounds': rate.tolist(),
                                  'sampled_magnitudes': max_magnitude.tolist(), 'sampled_rates': max_rate.tolist()})
    q0 = (pd.QMIN + pd.QMAX)/2
    v0 = np.linspace(-.02, .02, 7)
    tau_hold = model.evaluate(q0)['g']
    close('Static gravity equilibrium', model.acceleration(q0, np.zeros(7), tau_hold), np.zeros(7), 1e-12)
    E0 = .5*v0 @ model.evaluate(q0)['M'] @ v0 + model.evaluate(q0)['U']
    def rhs(t, state):
        q, v = state[:7], state[7:14]
        d = pd.dual_harmonic_disturbance(t)
        e = model.evaluate(q, v)
        a = np.linalg.solve(e['M'], tau_hold+d-e['C']@v-e['g']-e['F'])
        power = v@(tau_hold+d-e['F'])
        return np.r_[v, a, power]
    smokes = []
    for max_step in (.001, .0005):
        sol = solve_ivp(rhs, (0, .25), np.r_[q0, v0, 0.], method='DOP853', rtol=1e-10, atol=1e-12,
                        max_step=max_step, dense_output=True)
        condition(f'Plant-only integration succeeds at h={max_step}', sol.success)
        final = sol.y[:, -1]
        e = model.evaluate(final[:7], final[7:14])
        balance = .5*final[7:14]@e['M']@final[7:14]+e['U']-E0-final[14]
        close(f'Integrated plant work-energy balance at h={max_step}', np.asarray(balance), np.asarray(0.), 1e-8)
        smokes.append({'max_step_s': max_step, 'duration_s': .25, 'nfev': sol.nfev,
                       'energy_balance_error_J': float(balance), 'final_state_and_work': final.tolist()})
    close('Plant smoke h/h2 final-state convergence', np.array(smokes[0]['final_state_and_work']),
          np.array(smokes[1]['final_state_and_work']), 1e-8, 1e-7)
    # Diagnostic computation cost only, with validation enabled; not a realtime benchmark.
    count = 100
    bench_start = time.perf_counter()
    for _ in range(count):
        model.evaluate(q0, v0)
    mean_ms = 1000*(time.perf_counter()-bench_start)/count
    versions = {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
                'casadi': casadi.__version__, 'mujoco': mujoco.__version__, 'platform': platform.platform()}
    np.savez_compressed(args.report.with_suffix('.samples.npz'), q=np.array(poses), qd=velocities, qdd=accelerations)
    report = {
        'run_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'model-level numerical validation and plant-only integration',
        'overall_pass': all(row['passed'] for row in CHECKS.values()),
        'environment': versions, 'seed': args.seed, 'pose_count': len(poses),
        'pose_policy':'expanded132 set, then exact protocol22 set when requested',
        'case_sets':{'expanded':args.random_poses+4,'protocol22':22 if args.include_protocol_cases else 0},
        'human_acceptance':'PENDING SIGNATURE',
        'closed_loop_A2':'NOT_RUN',
        'checks': CHECKS, 'original_api_defects': bugs, 'disturbance_checks': disturbance_stats,
        'reference_import_diagnostic': import_diagnostic,
        'plant_smoke': smokes, 'mean_evaluate_ms_diagnostic': mean_ms,
        'elapsed_seconds': time.perf_counter()-start,
        'hashes': {str(path.relative_to(HERE.parent)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
            HERE.parent/'src/panda_dynamics.py', HERE.parent/'baseline/panda_dynamics.py',
            HERE.parent/'references/mujoco/reference_model.xml', OUTPUT/'reference_model_precise.xml',
            HERE/'review_checks.py', HERE.parent/'requirements.lock.txt')},
        'not_validated': ['paper closed-loop observer/controller/HOCBF QP', 'planner and comparative scenarios',
                          'certified whole-domain m1', 'interval bounds and all-time residuals',
                          'sample-and-hold safety', 'hardware model fidelity or physical electrical energy'],
    }
    detail_path = args.report.with_suffix('.details.csv')
    with detail_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(DETAILS[0]))
        writer.writeheader()
        writer.writerows(DETAILS)
    report['per_comparison_details'] = {'file': detail_path.name, 'rows': len(DETAILS),
        'sha256': hashlib.sha256(detail_path.read_bytes()).hexdigest(),
        'state_index_policy': 'expanded cases first; then exact protocol22; empty index for non-state-specific checks'}
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    for name, row in report['checks'].items():
        row['evidence_class'] = ('EXTERNAL_NUMERICAL_MUJOCO' if name.startswith('MuJoCo:') else 'REFERENCE_IMPORT_CHECK' if name.startswith('Reference:') else 'API_REGRESSION' if name.startswith(('API:', 'Regression:')) else 'PLANT_ONLY_NUMERICAL' if 'plant' in name.lower() else 'INTERNAL_OR_TRANSCRIBED_FORMULA_CHECK')
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    failed = [key for key, row in CHECKS.items() if not row['passed']]
    print(json.dumps({'passed': report['overall_pass'], 'checks': len(CHECKS), 'poses': len(poses),
                      'failed': failed, 'seconds': report['elapsed_seconds'], 'report': str(args.report)}, indent=2))
    return 0 if report['overall_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
