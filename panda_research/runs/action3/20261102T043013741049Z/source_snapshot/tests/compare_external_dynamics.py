"""Compare the target AD evaluator with independent source-built Pinocchio.

The target is imported only here, never in reference_model.py. Reference M is
CRBA and reference ID is RNEA on the source-generated URDF. No target helper
is used to build or evaluate the reference dynamics or kinematics.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from evidence_paths import evidence_dir
OUTPUT = evidence_dir()

from datetime import datetime, timezone
import csv
import hashlib
import json
import numpy as np
import pinocchio as pin
from reference_model import build_reference_urdf, reference_friction
from panda_dynamics import PandaDynamics, mdh_fk_numpy
from case_sets import all_cases, case_labels

ROOT = Path(__file__).resolve().parents[1]


def sample_cases():
    # Manifest supplies only the shared TEST DOMAIN, not reference model data.
    manifest = json.loads((ROOT/'baseline/model_manifest_v1.json').read_text())
    lower = np.array(manifest['joint_limits_qmin_rad'])
    upper = np.array(manifest['joint_limits_qmax_rad'])
    rng = np.random.default_rng(20261101)
    poses = np.vstack([np.zeros(7), (lower+upper)/2,
                       lower + .05*(upper-lower) + rng.random((20,7))*.9*(upper-lower)])
    velocities = rng.normal(0,.35,(22,7))
    accelerations = rng.normal(0,.4,(22,7))
    return poses, velocities, accelerations


def main():
    path = build_reference_urdf()
    model = pin.buildModelFromUrdf(str(path))
    model.gravity.linear = np.array([0., 0., -9.80665])
    assert model.nq == 7 and model.nv == 7
    assert list(model.names)[1:] == [f'panda_joint{i}' for i in range(1,8)]
    assert np.all(model.armature == 0)
    data = model.createData()
    target = PandaDynamics()
    cases = []
    diagnostics = []

    def compare(index, quantity, observed, reference, absolute, unit):
        a, b = np.asarray(observed), np.asarray(reference)
        error = np.abs(a-b)
        tolerances = absolute + 1e-9*np.abs(b)
        failures = np.argwhere((error > tolerances) | ~np.isfinite(error))
        record = {'pose_index': index, 'case_set':case_labels(index)[0], 'quantity': quantity, 'unit': unit,
                  'abs_tolerance': absolute, 'rel_tolerance': 1e-9,
                  'max_absolute_error': float(np.max(error)),
                  'max_tolerance_ratio': float(np.max(error/tolerances)),
                  'result': 'PASS' if not len(failures) else 'FAIL',
                  'failed_components': failures.tolist(), 'observed': a.tolist(), 'reference': b.tolist()}
        diagnostics.append(record)

    q_cases, qd_cases, qdd_cases = all_cases()
    for index, (q, qd, qdd) in enumerate(zip(q_cases, qd_cases, qdd_cases)):
        case_set, local_index, kind = case_labels(index)
        cases.append({'index': index, 'case_set':case_set, 'case_set_index':local_index, 'kind':kind,
                      'q_rad': q.tolist(), 'qd_rad_s': qd.tolist(), 'qdd_rad_s2': qdd.tolist()})
        value = target.evaluate(q, qd, qdd)
        pin.forwardKinematics(model, data, q, qd, qdd)
        pin.updateFramePlacements(model, data)
        poses, flange = mdh_fk_numpy(q)  # TARGET FK, never reference FK
        for link, (rotation, position) in enumerate(poses + [flange], 1):
            reference_pose = data.oMf[model.getFrameId(f'panda_link{link}')]
            compare(index, f'FK_link{link}_translation', position, reference_pose.translation, 1e-10, 'm')
            compare(index, f'FK_link{link}_rotation', rotation, reference_pose.rotation, 1e-10, 'dimensionless')
        compare(index, 'AD_flange_translation', value['flange'], data.oMf[model.getFrameId('panda_link8')].translation, 1e-10, 'm')
        mass_upper = pin.crba(model, data, q).copy()
        mass = np.triu(mass_upper) + np.triu(mass_upper, 1).T
        gravity = pin.computeGeneralizedGravity(model, data, q).copy()
        coriolis_velocity = pin.rnea(model, data, q, qd, np.zeros(7)).copy() - gravity
        inverse_rigid = pin.rnea(model, data, q, qd, qdd).copy()
        friction = reference_friction(qd)
        compare(index, 'M', value['M'], mass, 1e-9, 'kg m^2')
        # Section 2.3 specifies ID tolerance. Gravity and Cqd are torque
        # components: use the same 1e-8 Nm absolute and 1e-9 relative rule.
        compare(index, 'g', value['g'], gravity, 1e-8, 'N m')
        compare(index, 'Cqd', value['C'] @ qd, coriolis_velocity, 1e-8, 'N m')
        compare(index, 'friction', value['F'], friction, 1e-8, 'N m')
        compare(index, 'ID_friction_off', value['ID'] - value['F'], inverse_rigid, 1e-8, 'N m')
        compare(index, 'ID_friction_on', value['ID'], inverse_rigid + friction, 1e-8, 'N m')
        kinetic = pin.computeKineticEnergy(model, data, q, qd)
        potential = pin.computePotentialEnergy(model, data, q)
        # Additional, explicitly chosen diagnostics, not prescribed §2.3 thresholds.
        compare(index, 'kinetic_energy_extra', .5 * qd @ value['M'] @ qd, kinetic, 1e-9, 'J')
        compare(index, 'potential_energy_extra', value['U'], potential, 1e-8, 'J')
        saved_gravity = model.gravity.linear.copy()
        model.gravity.linear = -saved_gravity
        compare(index, 'reversed_gravity_sign', -value['g'], pin.computeGeneralizedGravity(model, data, q).copy(), 1e-8, 'N m')
        model.gravity.linear = np.zeros(3)
        compare(index, 'zero_gravity', np.zeros(7), pin.computeGeneralizedGravity(model, data, q).copy(), 1e-8, 'N m')
        model.gravity.linear = saved_gravity
    (OUTPUT/'external_cases.json').write_text(json.dumps({
        'seed': 20261101, 'rng': 'NumPy default_rng PCG64',
        'draw_order':'expanded132 original draw order, then exact protocol22 original draw order; see tests/case_sets.py',
        'case_sets':{'protocol22':22,'expanded132':132},
        'cases': cases}, indent=2)+'\n')
    summary = {}
    for item in diagnostics:
        group = summary.setdefault(item['quantity'], {'max_absolute_error': 0., 'max_tolerance_ratio': 0., 'failed_pose_indices': []})
        for key in ('max_absolute_error', 'max_tolerance_ratio'):
            group[key] = max(group[key], item[key])
        if item['result'] != 'PASS': group['failed_pose_indices'].append(item['pose_index'])
    overall = all(r['result']=='PASS' for r in diagnostics)
    report = {'run_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'PASS_EXTERNAL_NUMERICAL_REFERENCE' if overall else 'FAIL', 'overall_pass': overall,
              'reference': 'Pinocchio '+pin.__version__+' URDFDOM, CRBA/RNEA from independently parsed pinned source bytes',
              'source_boundary': 'reference_model.py imports neither target constants/transforms nor CasADi; see construction notes',
              'urdf_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'case_file_sha256': hashlib.sha256((OUTPUT/'external_cases.json').read_bytes()).hexdigest(),
              'relative_rule': 'elementwise |target-reference| <= absolute + 1e-9*abs(reference)',
              'pose_count': len(q_cases), 'case_sets':{'protocol22':22,'expanded132':132}, 'checks': len(diagnostics), 'summary': summary, 'per_case': diagnostics,
              'human_acceptance': 'PENDING SIGNATURE', 'interval_certification': 'NOT_RUN',
              'raw_C_matrix_compared': False}
    (OUTPUT/'external_dynamics.json').write_text(json.dumps(report, indent=2)+'\n')
    with (OUTPUT/'external_dynamics.csv').open('w', newline='') as stream:
        fields=['pose_index','quantity','unit','abs_tolerance','rel_tolerance','max_absolute_error','max_tolerance_ratio','result']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader(); writer.writerows(diagnostics)
    print(json.dumps({'status': report['status'], 'pose_count':len(q_cases), 'checks':len(diagnostics), 'summary': summary}, indent=2))
    if not overall: raise SystemExit(1)


if __name__ == '__main__':
    main()
