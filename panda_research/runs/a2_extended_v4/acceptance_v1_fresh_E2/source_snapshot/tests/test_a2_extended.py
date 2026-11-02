"""Pre-motion contracts for fixed references, causality accounting and raw signs."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import json
import unittest
from unittest.mock import Mock
import numpy as np
from panda_dynamics import QMIN, QMAX
from panda_closed_loop.a2_extended import ExtendedReference, difference_statistics, negative_slack_report, BoundedQP
from panda_closed_loop.qp import HardSafetyQP
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest, Policy
from panda_closed_loop.assembly import build_components
from test_p1_r3 import Results


class ExtendedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT/'policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json').read_text())
        cls.q = (QMIN+QMAX)/2+np.arange(7)*1e-5
        cls.v = np.arange(7)*1e-5

    def test_amplitudes_are_the_fixed_joint_range_rule(self):
        np.testing.assert_array_equal(self.plan['selection_rule']['amplitude_rad'], np.minimum(.02*(QMAX-QMIN), .12))
        self.assertEqual(list(self.plan['references']), ['E1', 'E2', 'E3'])
        self.assertEqual(self.plan['motion_cell_count'], 12)

    def test_E1_joint_is_selected_from_frozen_geometry_before_motion(self):
        s = build_components()
        norms = np.linalg.norm(s.geometry.evaluate((QMIN+QMAX)/2)['Jv'], axis=0)
        self.assertEqual(int(np.argmax(norms))+1, 2)
        np.testing.assert_allclose(norms, self.plan['selection_rule']['midpoint_Jv_column_norm_m_per_rad'], atol=1e-15)

    def test_all_references_match_actual_initial_q_velocity_acceleration(self):
        for definition in self.plan['references'].values():
            r = ExtendedReference(self.q, self.v, definition).sample(0.)
            np.testing.assert_array_equal(r.q, self.q)
            np.testing.assert_array_equal(r.qd, self.v)
            np.testing.assert_array_equal(r.qdd, np.zeros(7))

    def test_declared_targets_and_stationary_terminal_reference(self):
        for definition in self.plan['references'].values():
            r = ExtendedReference(self.q, self.v, definition)
            end = r.sample(1.)
            np.testing.assert_allclose(end.q, self.q+definition['waypoint_offsets_rad'][-1], atol=1e-14)
            np.testing.assert_allclose(end.qd, 0., atol=1e-13)
            np.testing.assert_allclose(end.qdd, 0., atol=1e-12)

    def test_E3_is_C2_at_fixed_turn_and_reverses_direction(self):
        r = ExtendedReference(self.q, self.v, self.plan['references']['E3'])
        c0, c1 = r.coefficients
        for derivative in range(3):
            left = np.polynomial.polynomial.polyval(1., np.polynomial.polynomial.polyder(c0, derivative, axis=0))/.5**derivative
            right = np.polynomial.polynomial.polyval(0., np.polynomial.polynomial.polyder(c1, derivative, axis=0))/.5**derivative
            np.testing.assert_allclose(left, right, atol=2e-12)
        self.assertGreater(r.sample(.25).qd[2], 0.)
        self.assertLess(r.sample(.75).qd[2], 0.)
        self.assertGreater(abs(r.sample(.5).q[2]-self.q[2]), .05)

    def test_single_and_coordinated_net_transfers_are_distinct(self):
        e1, e2 = [np.array(self.plan['references'][k]['waypoint_offsets_rad'][-1]) for k in ['E1','E2']]
        self.assertEqual(np.count_nonzero(e1), 1)
        self.assertEqual(np.count_nonzero(e2), 3)
        self.assertGreater(np.linalg.norm(e2-e1), .05)

    def test_nonselected_coordinates_keep_measured_velocity_transients(self):
        r = ExtendedReference(self.q, self.v, self.plan['references']['E1'])
        self.assertNotEqual(r.sample(.1).q[4], self.q[4])
        self.assertEqual(r.sample(0.).qd[4], self.v[4])

    def test_reference_rejects_nonfinite_or_outside_horizon(self):
        r = ExtendedReference(self.q, self.v, self.plan['references']['E1'])
        for t in [-.01, float('nan'), float('inf'), 1.01]:
            with self.assertRaises(ValueError): r.sample(t)

    def test_invalid_phase_boundaries_and_waypoints_are_rejected(self):
        definition = dict(self.plan['references']['E3'])
        definition['normalized_boundaries'] = [0., .5, .4]
        with self.assertRaises(ValueError): ExtendedReference(self.q, self.v, definition)
        definition = dict(self.plan['references']['E1'])
        definition['waypoint_offsets_rad'] = [[0.]*7,[0.]*6]
        with self.assertRaises(ValueError): ExtendedReference(self.q, self.v, definition)

    def test_small_QP_correction_is_not_zero_continuous_correction(self):
        updates = []
        for value in [.1,.2]:
            digital = np.zeros(7);digital[0] = value
            updates.append({'torque_applied': True, 'candidate_tau': digital,
                            'u_nom': digital, 'tracking_errors': {'continuous_request_Nm': np.zeros(7)}})
        s = difference_statistics(updates)['statistics']
        self.assertEqual(s['tau_minus_u']['max_2norm_Nm'], 0.)
        self.assertEqual(s['tau_minus_r']['max_2norm_Nm'], .2)
        self.assertAlmostEqual(s['u_minus_r']['RMS_2norm_Nm'], np.sqrt(.025))

    def test_negative_raw_candidate_and_stage_slacks_are_not_tolerated_or_hidden(self):
        motion = {'updates': [{'raw_slacks': [-1e-18], 'row_names': ['test_row'], 'physical_t_s': 0., 'torque_applied': False}],
                  'substeps': [{'samples': [{'physical_t_s': .00025, 'physical_slacks': {'h': [-1e-12], 'passed': False},
                                             'observer_envelope_slack': [-1e-14,0.,0.,0.,0.,0.,0.]}]}]}
        r = negative_slack_report(motion)
        self.assertEqual(r['negative_count'], 3)
        self.assertFalse(r['negative_values'][0]['torque_applied'])
        self.assertTrue(all(v['value'] < 0 for v in r['negative_values']))

    def test_grid_thresholds_and_startup_are_original_unchanged(self):
        base = json.loads((ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json').read_text())
        self.assertEqual(self.plan['C4_grid'], Policy.load().raw['integration']['validation_grid'])
        self.assertEqual(self.plan['fixed_acceptance_thresholds'], base['fixed_acceptance_thresholds'])
        for name in ['startup_controller','T_pre_s','q_radius_rad','qd_radius_rad_s','execution_sampling','observer_semantics']:
            self.assertEqual(self.plan[name], base[name])

    def test_bounded_service_preserves_production_QP_solution(self):
        limits = np.ones(7)
        rows = AffineRows(np.vstack([-np.eye(7), np.eye(7)]), np.ones(14), np.ones(14),
                          tuple(str(i) for i in range(14)), tuple('Nm' for _ in range(14)))
        settings = Policy.load().raw['solver']['QP_settings']
        direct = HardSafetyQP(limits, settings).solve(np.full(7,.2), rows)
        with BoundedQP(limits, settings, 15.) as service:
            guarded = service.solve(np.full(7,.2), rows)
        self.assertEqual(guarded.status, direct.status)
        np.testing.assert_array_equal(guarded.applied, direct.applied)
        self.assertEqual(guarded.diagnostics, direct.diagnostics)

    def test_wall_timeout_is_unknown_and_never_a_fallback_torque(self):
        service = BoundedQP(np.ones(7), Policy.load().raw['solver']['QP_settings'], .01)
        service.process = Mock()
        service.connection = Mock()
        service.connection.poll.return_value = False
        result = service.solve(np.zeros(7), None)
        self.assertIsNone(result.applied)
        self.assertTrue(result.stop_requested)
        self.assertEqual(result.status, 'SOLVER_WALL_TIMEOUT_UNKNOWN')
        self.assertEqual(result.diagnostics['classification'], 'UNKNOWN_NOT_INFEASIBLE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExtendedTests))
    sources = ['src/panda_closed_loop/a2_extended.py','tests/test_a2_extended.py',
               'src/panda_closed_loop/trace_archive.py','policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json']
    with args.report.open('x') as f:
        json.dump({'scope': 'PRE_MOTION_ENGINEERING_CONTRACTS_NO_PANDA_EXTENDED_PLANT_RUN',
                   'tests_run': result.testsRun, 'overall_pass': result.wasSuccessful(), 'checks': result.rows,
                   'source_hashes': {n:digest(ROOT/n) for n in sources}}, f, indent=2)
        f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
