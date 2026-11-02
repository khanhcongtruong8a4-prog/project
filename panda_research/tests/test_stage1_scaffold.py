"""Development scaffold verification; no NLP optimization or A3 comparison."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import importlib.metadata
import json
import platform
import unittest
from unittest.mock import patch
import numpy as np
from panda_dynamics import QMIN, QMAX
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import digest
from panda_closed_loop.reference import ReferenceSample
from panda_closed_loop.stage1_scaffold import (QuinticHermite, QuinticBSpline, PlanningMargins,
    ConstantMarginProvider, MissingPlanningMargin, Stage1NotReady, Stage1Scaffold,
    SymbolicPandaPlant, normalized_quadrature, shared_bus_power)
from case_sets import all_cases


def synthetic_margins(**overrides):
    data = {'b_u_plus': np.zeros(7), 'b_u_minus': np.zeros(7), 'chi_v': np.zeros(7),
            'b_h': np.zeros(15), 'b_vB': np.zeros(7), 'scope': 'SYNTHETIC_TEST_ONLY',
            'domain_sha256': '0'*64, 'provenance_sha256': '1'*64}
    return PlanningMargins(**(data|overrides))


class ScaffoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = build_components()
        cls.system.geometry.function = cls.system.geometry.function.expand()
        cls.scaffold = Stage1Scaffold(cls.system)
        cls.qmid = (QMIN+QMAX)/2
        cls.knots = np.array(cls.system.policy.raw['solver']['NLP_quintic_knots_normalized'])

    def constant_spline(self, T=1.):
        return QuinticBSpline(np.tile(self.qmid, (12, 1)), self.knots, T)

    def test_clamped_quintic_partition_and_endpoint_basis(self):
        p = self.constant_spline()
        for s in np.linspace(0, 1, 21):
            self.assertAlmostEqual(float(np.sum(p.basis(s))), 1., places=14)
            self.assertTrue(np.all(p.basis(s) >= 0))
        np.testing.assert_array_equal(p.basis(0), np.r_[1., np.zeros(11)])
        np.testing.assert_array_equal(p.basis(1), np.r_[np.zeros(11), 1.])

    def test_free_time_scaling_matches_exact_linear_bspline_curve(self):
        greville = np.array([np.mean(self.knots[i+1:i+6]) for i in range(12)])
        direction = np.arange(1., 8.)/100
        cp = self.qmid+greville[:, None]*direction
        a, b = QuinticBSpline(cp, self.knots, 1.), QuinticBSpline(cp, self.knots, 2.)
        x, y = a.sample(.3), b.sample(.6)
        np.testing.assert_allclose(x.q, self.qmid+.3*direction, atol=1e-14)
        np.testing.assert_allclose(x.q, y.q, atol=1e-14)
        np.testing.assert_allclose(x.qd, direction, atol=1e-14)
        np.testing.assert_allclose(y.qd, direction/2, atol=1e-14)
        np.testing.assert_allclose(x.qdd, 0, atol=1e-13)
        np.testing.assert_allclose(y.qdd, x.qdd/4, atol=1e-14)

    def test_general_hermite_matches_all_six_boundary_conditions(self):
        q0, q1 = self.qmid, self.qmid+np.arange(7.)/100
        v0, a0, v1, a1 = np.full(7, .03), np.full(7, -.02), np.zeros(7), np.zeros(7)
        curve = QuinticHermite.from_boundary(q0, v0, a0, q1, v1, a1, 1.3)
        for actual, expected in [(curve.sample(0).q, q0), (curve.sample(0).qd, v0),
                                 (curve.sample(0).qdd, a0), (curve.sample(1.3).q, q1),
                                 (curve.sample(1.3).qd, v1), (curve.sample(1.3).qdd, a1)]:
            np.testing.assert_allclose(actual, expected, atol=2e-14)

    def test_decision_layout_is_84_coefficients_plus_free_time(self):
        p = self.constant_spline(1.7)
        decision = p.decision_vector()
        self.assertEqual(decision.shape, (85,))
        restored = QuinticBSpline.from_decision(decision, self.knots)
        np.testing.assert_array_equal(restored.control_points, p.control_points)
        self.assertEqual(restored.duration, 1.7)

    def test_invalid_curves_and_mutation_are_rejected(self):
        p = self.constant_spline()
        for points, knots, T in [(p.control_points, self.knots, 0.),
                                 (np.full((12, 7), np.nan), self.knots, 1.),
                                 (p.control_points, self.knots[:-1], 1.)]:
            with self.assertRaises(ValueError): QuinticBSpline(points, knots, T)
        with self.assertRaises(ValueError): p.control_points[0, 0] = 9
        with self.assertRaises(ValueError): p.sample(1.1)

    def test_shared_bus_smoothing_is_after_sum_and_includes_copper_losses(self):
        energy = json.loads(json.dumps(self.system.policy.raw['energy']))
        energy['k_r'] = [0.]*7
        tau = np.r_[1., -1., np.zeros(5)]
        v = np.r_[1., 1., np.zeros(5)]
        epsilon = energy['nonregenerative_smoothing']['epsilon_W']
        self.assertEqual(shared_bus_power(tau, v, energy), epsilon/2)
        self.assertGreater(shared_bus_power(tau, v, self.system.policy.raw['energy']), epsilon/2)

    def test_gauss_quadrature_integrates_over_all_nonzero_spans(self):
        grid = normalized_quadrature(self.constant_spline().spans, 16)
        self.assertAlmostEqual(sum(w for _, w in grid), 1., places=14)
        self.assertAlmostEqual(sum(w*s**10 for s, w in grid), 1/11, places=14)
        self.assertEqual(len(grid), 7*16)

    def test_missing_or_invalid_m1_cannot_be_silently_zeroed(self):
        p = self.constant_spline()
        target = self.system.geometry.evaluate(self.qmid)['f']
        with self.assertRaises(MissingPlanningMargin):
            self.scaffold.evaluate(p, self.qmid, np.zeros(7), target, np.zeros(7), None, [0., 1.])
        with self.assertRaises(ValueError): synthetic_margins(mode='M2_CANDIDATE_DEPENDENT')
        with self.assertRaises(ValueError): synthetic_margins(b_h=np.zeros(14))
        with self.assertRaises(ValueError): synthetic_margins(scope='CERTIFIED_BY_THIS_TEST')

    def test_planned_torque_minus_initial_dhat_and_signed_reserves(self):
        sample = ReferenceSample(self.qmid, np.zeros(7), np.zeros(7))
        dhat = np.full(7, .1)
        margins = synthetic_margins(b_u_plus=np.full(7, .2), b_u_minus=np.full(7, .3),
                                    chi_v=np.full(7, .01), b_h=np.full(15, .04), b_vB=np.full(7, .05))
        tau, residual = self.scaffold.residual_sample(sample, dhat, margins)
        expected = self.system.model.evaluate(self.qmid)['g']-dhat
        np.testing.assert_allclose(tau, expected, atol=1e-14)
        limits = self.system.barriers.taumax
        np.testing.assert_allclose(residual['torque_upper'], limits-tau-.2-.0012)
        np.testing.assert_allclose(residual['torque_lower'], limits+tau-.3-.0012)
        self.assertEqual(residual['hocbf'].shape, (15,))
        self.assertEqual(residual['physical_position_and_manip_h'].shape, (15,))
        np.testing.assert_allclose(residual['speed_upper'], self.system.barriers.vmax-.01-.0002175)

    def test_symbolic_source_adapter_matches_frozen_numeric_model_at_154_cases(self):
        adapter = SymbolicPandaPlant(self.system.model, self.system.geometry)
        poses, velocities, accelerations = all_cases()
        worst = 0.
        for q, v, a in zip(poses, velocities, accelerations):
            ID, flange, W, gradient, hessian = adapter.function(q, v, a)
            expected = self.system.model.evaluate(q, v, a)
            geom = self.system.geometry.evaluate(q)
            for actual, value in [(np.array(ID).ravel(), expected['ID']), (np.array(flange).ravel(), expected['flange']),
                                   (np.array(W).ravel(), np.array([geom['W']])),
                                   (np.array(gradient).ravel(), geom['gradient_W']), (np.array(hessian), geom['hessian_W'])]:
                worst = max(worst, float(np.max(abs(actual-value))))
                np.testing.assert_allclose(actual, value, atol=1e-10, rtol=1e-11)
        self.assertLess(worst, 1e-10)

    def test_numerical_static_objective_has_correct_free_duration_and_task_constraints(self):
        p = self.constant_spline(1.)
        target = self.system.geometry.evaluate(self.qmid)['f']
        result = self.scaffold.evaluate(p, self.qmid, np.zeros(7), target, np.zeros(7),
                                      ConstantMarginProvider(synthetic_margins()), [0., .5, 1.])
        expected_power = shared_bus_power(self.system.model.evaluate(self.qmid)['g'], np.zeros(7), self.system.policy.raw['energy'])
        self.assertAlmostEqual(result['electrical_energy_J'], expected_power, places=12)
        self.assertAlmostEqual(result['objective_J'], expected_power+1., places=12)
        self.assertTrue(result['all_sampled_inequalities_nonnegative'])
        self.assertFalse(result['A3_GO'])
        for value in result['equalities'].values(): np.testing.assert_allclose(value, 0, atol=1e-12)

    def test_symbolic_nlp_graph_matches_numerical_values_without_calling_optimizer(self):
        p = self.constant_spline()
        target = self.system.geometry.evaluate(self.qmid)['f']
        margins = ConstantMarginProvider(synthetic_margins())
        numerical = self.scaffold.evaluate(p, self.qmid, np.zeros(7), target, np.zeros(7), margins, [0., .5, 1.])
        with patch('casadi.nlpsol', side_effect=AssertionError('No optimizer may be constructed')):
            graph = self.scaffold.build_symbolic_fixture(p, self.qmid, np.zeros(7), target, np.zeros(7), margins, [0., .5, 1.])
            objective, g, derivative = graph['function'](p.decision_vector())
        self.assertEqual(graph['equality_count'], 31)
        self.assertEqual(graph['inequality_count'], 2+3*72)
        self.assertAlmostEqual(float(objective), numerical['objective_J'], places=11)
        np.testing.assert_allclose(np.array(g).ravel()[:31], 0, atol=1e-12)
        self.assertTrue(np.all(np.array(g).ravel()[31:] >= 0))
        expected_dT = numerical['objective_J']/p.duration
        self.assertAlmostEqual(float(derivative[-1]), expected_dT, places=10)

    def test_dynamic_symbolic_residuals_and_free_time_derivative_match_numerical_evaluator(self):
        offset = np.array([.001, 0., -.001, 0., .001, 0., 0.])
        fractions = np.r_[np.zeros(3), np.linspace(.1, .9, 6), np.ones(3)]
        p = QuinticBSpline(self.qmid+fractions[:, None]*offset, self.knots, 1.2)
        target = self.system.geometry.evaluate(self.qmid+offset)['f']
        margins, nodes = ConstantMarginProvider(synthetic_margins()), [0., .2, .5, .8, 1.]
        numerical = self.scaffold.evaluate(p, self.qmid, np.zeros(7), target, np.zeros(7), margins, nodes)
        graph = self.scaffold.build_symbolic_fixture(p, self.qmid, np.zeros(7), target, np.zeros(7), margins, nodes)
        objective, g, derivative = graph['function'](p.decision_vector())
        expected = np.concatenate([*numerical['equalities'].values(), numerical['duration_slacks'],
                                   *[v for record in numerical['samples'] for v in record['residuals'].values()]])
        np.testing.assert_allclose(np.array(g).ravel(), expected, atol=1e-10, rtol=1e-11)
        self.assertAlmostEqual(float(objective), numerical['objective_J'], places=11)
        eps = 1e-5
        sides = [self.scaffold.evaluate(QuinticBSpline(p.control_points, self.knots, p.duration+sign*eps),
                    self.qmid, np.zeros(7), target, np.zeros(7), margins, nodes)['objective_J'] for sign in [-1, 1]]
        finite_difference = (sides[1]-sides[0])/(2*eps)
        self.assertAlmostEqual(float(derivative[-1]), finite_difference, delta=1e-7)

    def test_official_solver_is_blocked_with_missing_inputs_and_no_signature_invention(self):
        readiness = self.scaffold.readiness()
        self.assertEqual(readiness['status'], 'HOLD')
        self.assertIsNone(readiness['human_signatures'])
        self.assertIn('M1_NUMERICAL_BOUND_REGISTRY_INCOMPLETE', readiness['blockers'])
        with patch('casadi.nlpsol', side_effect=AssertionError('No optimizer may be constructed')):
            with self.assertRaises(Stage1NotReady): self.scaffold.solve_official()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ScaffoldTests))
    record = {'scope': 'STAGE1_DEVELOPMENT_SCAFFOLD_NO_NLP_SOLVE_NO_A3_COMPARISON', 'tests_run': result.testsRun,
              'overall_pass': result.wasSuccessful(), 'failed': [{'test': str(t), 'traceback': e} for t, e in result.failures+result.errors],
              'source_sha256': digest(ROOT/'src/panda_closed_loop/stage1_scaffold.py'),
              'test_sha256': digest(Path(__file__)), 'python': sys.version, 'platform': platform.platform(),
              'packages': {n: importlib.metadata.version(n) for n in ['numpy', 'scipy', 'casadi']},
              'official_optimizer_called': False, 'independent_signature': None}
    with args.report.open('x') as f: json.dump(record, f, indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
