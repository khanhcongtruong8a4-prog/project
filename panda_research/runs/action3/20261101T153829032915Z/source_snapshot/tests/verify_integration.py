"""Validate model identity, shared case sets, reference provenance and migration."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from evidence_paths import evidence_dir
OUTPUT = evidence_dir()
import ast
import importlib.util
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation
from case_sets import protocol_cases, expanded_cases, all_cases
from reference_model import source_parameters, source_joint_data
import panda_dynamics as current

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    checks = []
    def check(name, condition):
        checks.append({'check': name, 'result': 'PASS' if condition else 'FAIL'})
        if not condition:
            raise AssertionError(name)
    original = load_module('original_identity', ROOT / 'baseline/panda_dynamics.py')
    for name in ['MASS', 'COM', 'INERTIA6', 'A_DH', 'ALPHA_DH', 'D_DH', 'FLANGE_Z', 'GRAVITY',
                 'PHI1', 'PHI2', 'PHI3', 'QMIN', 'QMAX', 'VMAX', 'TAUMAX']:
        check('Unchanged selected model constant: ' + name,
              np.array_equal(np.asarray(getattr(original, name)), np.asarray(getattr(current, name))))
    def constructor(path):
        tree = ast.parse(path.read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'PandaDynamics')
        return ast.dump(next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '__init__'))
    check('CasADi model-construction AST unchanged',
          constructor(ROOT/'baseline/panda_dynamics.py') == constructor(ROOT/'src/panda_dynamics.py'))
    # Original script's case-generation expressions, using the same constants
    # checked above. No claim of an independent dynamics reference is made here.
    original_cases = load_module('original_case_generation', ROOT / 'baseline/run_phase3a_tests.py')
    check('Exact original protocol22 q/qd/qdd sequences',
          all(np.array_equal(a, b) for a, b in zip(protocol_cases(),
              [original_cases.Q_CASES, original_cases.QD_CASES, original_cases.QDD_CASES])))
    supplied = np.load(ROOT/'baseline/panda_review/review_test_report.samples.npz', allow_pickle=False)
    check('Exact supplied expanded132 sample sequences',
          all(np.array_equal(a, supplied[k]) for a, k in zip(expanded_cases(), ['q', 'qd', 'qdd'])))
    pin_cases = json.loads((OUTPUT/'external_cases.json').read_text())['cases']
    mj_cases = np.load(OUTPUT/'mujoco_validation.samples.npz', allow_pickle=False)
    for i, key in enumerate(['q', 'qd', 'qdd']):
        pin_key = ['q_rad', 'qd_rad_s', 'qdd_rad_s2'][i]
        check('Both engines use identical 154-case ' + key,
              np.array_equal(all_cases()[i], mj_cases[key]) and
              np.array_equal(all_cases()[i], np.array([row[pin_key] for row in pin_cases])))
    om, cm = original.PandaDynamics(), current.PandaDynamics()
    maxima = {}
    for q, v, a in zip(*all_cases()):
        before, after = om.evaluate(q, v, a), cm.evaluate(q, v, a)
        for key in before:
            error = float(np.max(np.abs(np.asarray(before[key]) - np.asarray(after[key]))))
            maxima[key] = max(maxima.get(key, 0.), error)
    check('Flat-vector numerical results preserved over all 154 cases', all(x == 0 for x in maxima.values()))
    pars, joints = source_parameters(), source_joint_data()
    xml = ET.parse(ROOT/'references/mujoco/reference_model.xml').getroot()
    source_comparisons = []
    for i, body in enumerate(xml.find('worldbody').iter('body')):
        inertial = body.find('inertial')
        xx, yy, zz, xy, xz, yz = np.fromstring(inertial.get('fullinertia'), sep=' ')
        rotation = Rotation.from_quat(np.fromstring(body.get('quat', '1 0 0 0'), sep=' '), scalar_first=True).as_matrix()
        errors = {
            'mass_kg': abs(float(inertial.get('mass')) - pars['mass'][i]),
            'COM_m': float(np.max(np.abs(np.fromstring(inertial.get('pos'), sep=' ') - pars['com'][i]))),
            'COM_inertia_kg_m2': float(np.max(np.abs([xx, xy, xz, yy, yz, zz] - pars['inertia6'][i]))),
            'joint_origin_m': float(np.max(np.abs(np.fromstring(body.get('pos'), sep=' ') - joints[i]['xyz']))),
            'joint_rotation': float(np.max(np.abs(rotation - Rotation.from_euler('xyz', joints[i]['rpy']).as_matrix())))}
        source_comparisons.append({'link': i+1, 'errors': errors})
        check('Independent MJCF constants/origin match pinned sources: link ' + str(i+1), all(x <= 1e-14 for x in errors.values()))
    check('MJCF fixed flange matches pinned Xacro',
          np.array_equal(np.fromstring(xml.find('.//site').get('pos'), sep=' '), joints[7]['xyz']))
    check('MJCF gravity matches selected convention', xml.find('option').get('gravity') == '0 0 -9.80665')
    suite = json.loads((ROOT/'protocol/scenario_b_target_suite_PROPOSED.json').read_text())
    check('Scenario B is a proposal, with no method comparisons executed', suite['approval'] is None and not suite['comparison_runs_executed'])
    check('Production source regeneration has been removed', not (ROOT/'scripts/prepare_corrected_tests.py').exists())
    report = {'overall_pass': True, 'checks': checks, 'flat_input_max_errors': maxima,
              'physical_model_constructor_unchanged': True, 'API_guards_intentionally_change_executable_code': True,
              'MJCF_source_comparisons': source_comparisons,
              'human_acceptance': 'PENDING SIGNATURE', 'closed_loop_A2': 'NOT_RUN'}
    (OUTPUT/'integration_checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS:', len(checks), 'integration checks; nominal model preserved, API fixes retained.')


if __name__ == '__main__':
    main()
