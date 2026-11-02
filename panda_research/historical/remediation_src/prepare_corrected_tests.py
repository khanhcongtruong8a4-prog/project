"""Apply small, reviewable label/reporting fixes to copies of the original code."""
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Unexpected baseline text count for {old!r}')
    return text.replace(old, new, 1)


def main():
    model = (ROOT / 'baseline/panda_dynamics.py').read_text()
    model = replace_once(model, 'Independent NumPy MDH product reference;', 'Internal NumPy MDH product (shared constants/helpers);')
    model = replace_once(model, 'Separate source-level original-franka_ros URDF translation/rpy list.',
                         'In-code URDF-origin transcription; shares rotation helpers, not source bytes.')
    (ROOT / 'src/panda_dynamics.py').write_text(model)
    text = (ROOT / 'baseline/run_phase3a_tests.py').read_text()
    edits = [
        ('disturbance_bounds,TAUMAX)', 'disturbance_bounds,TAUMAX,VMAX)'),
        ('T04b author-code c1z convention', 'Internal literal regression: c1z convention'),
        ('Compared with Gaz pinned MATLAB DynPars2VREP.m (the source table prints asterisk, not measured zero).',
         'Compares a code constant to a literal only; primary-source verification is a separate report. Table c1z is an asterisk.'),
        ('T04b author-code joint2 phi1', 'Internal literal regression: joint2 phi1'),
        ('Compared with pinned get_FrictionTorque.m, not rounded from incorrect alternate sources.',
         'Compares a code constant to a literal only; does not read author MATLAB bytes.'),
        ('small_eig=[];skew=[]', 'small_eig=[];large_eig=[];skew=[]'),
        ('small_eig.append(np.linalg.eigvalsh(M)[0])',
         'small_eig.append(np.linalg.eigvalsh(M)[0]); large_eig.append(np.linalg.eigvalsh(M)[-1])'),
        ('T06a MDH vs pinned-URDF link and flange positions', 'Internal MDH vs in-code URDF-origin positions'),
        ('22 poses, independently implemented NumPy kinematic products; conventions and model-level identity only.',
         '22 poses; common rotation helpers and transcribed constants. Not an independent source or dynamics check.'),
        ('T06a MDH vs pinned-URDF rotations', 'Internal MDH vs in-code URDF-origin rotations'),
        ('22 poses; no hand/tool fixed transform added.', '22 poses; shared helpers; no hand/tool transform added.'),
        ('Christoffel C constructed from CasADi auto-differentiated M.',
         'Internal indexing identity: Mdot and C use the same dM/dq; cannot validate physical parameters.'),
        ("add('Phase3a mechanical skew power identity',max(energy),1e-10)",
         "add('Phase3a mechanical skew power identity',max(energy),1e-10,'Internal shared-derivative identity only.')"),
        ("add('Phase3a gravity equals numeric potential gradient',max(grav),5e-8)",
         "add('Phase3a gravity equals numeric potential gradient',max(grav),5e-8,'Finite difference of the same U; not independent gravity validation.')"),
        ('Phase3a Cqdot vs independently finite-differenced Lagrange form', 'Phase3a Cqdot vs finite-differenced same-model Lagrange form'),
        ("add('Phase3a inverse-dynamics power consistency',max(kinetic),1e-10)",
         "add('Phase3a inverse-dynamics power consistency',max(kinetic),1e-10,'Internal shared-M/shared-derivative identity only.')"),
        ('vv=np.linspace(-2,2,101)[:,None]*np.ones((1,N))',
         'vv=np.linspace(-1,1,261)[:,None]*VMAX[None,:]'),
        ("add('Phase3a friction dissipation on velocity grid',max(0,float(-np.min(vv*fp))),0)",
         "add('Phase3a friction dissipation on velocity grid',max(0,float(-np.min(vv*fp))),0,'261 equally spaced velocities per joint, inclusive -VMAX..+VMAX; rad/s.')"),
        ("'max_sampled_joint_inertia_eigenvalue':None,", "'max_sampled_joint_inertia_eigenvalue':max(large_eig),\n      'friction_grid':{'points_per_joint':261,'min_rad_s':(-VMAX).tolist(),'max_rad_s':VMAX.tolist()},"),
        ('NOT_RUN: pinocchio unavailable; independent library ID remains pending',
         'NOT_RUN_BY_THIS_SCRIPT: see reports/external_dynamics.json for the separately constructed reference'),
        ("'checks':RECORD}", "'checks':[dict(r,evidence_class=classification(i),external_validation=False) for i,r in enumerate(RECORD)]}"),
        ('SEED=20261101', 'from run_reproduction import classification\n\nSEED=20261101'),
        ("outpath=Path(__file__).parent/'phase3a_test_report.json'", "outpath=Path(__file__).resolve().parents[1]/'reports/corrected_internal_tests.json'"),
    ]
    for old, new in edits:
        text = replace_once(text, old, new)
    (ROOT / 'src/run_phase3a_tests.py').write_text(text)
    patches = []
    for name in ('panda_dynamics.py', 'run_phase3a_tests.py'):
        patches.extend(difflib.unified_diff((ROOT/'baseline'/name).read_text().splitlines(keepends=True),
            (ROOT/'src'/name).read_text().splitlines(keepends=True),
            fromfile='baseline/'+name, tofile='src/'+name))
    (ROOT / 'reports/code_changes.patch').write_text(''.join(patches))


if __name__ == '__main__':
    main()
