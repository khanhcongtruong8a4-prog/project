"""r3 controller, exact transfer, strict actuation and refinement contracts."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np
from panda_closed_loop.config import Policy
from panda_closed_loop.controller import SlotineLiController
from panda_closed_loop.barriers import BarrierEvaluator
from panda_closed_loop.observer import MomentumObserver, DisturbanceBounds
from panda_closed_loop.preparation import AppliedTorquePrehold, SignedClock, SignedObserverEnvelope
from panda_closed_loop.qp import HardSafetyQP, QPResult
from panda_closed_loop.reference import ReferenceSample
from panda_closed_loop.stepper import ExecutionState, HoldSchedule
from panda_closed_loop.p1_r3 import (SampledComputedTorque, QuinticMeasuredReference, strict_qp_check,
                                    integrate_substep, run_a2_cell, compare_refinement, modeled_power)


class IdentityPlant:
    def evaluate(self, q, qd=None):
        return {'M': np.eye(7), 'C': np.zeros((7, 7)), 'g': np.zeros(7), 'F': np.zeros(7)}


class ConstantGeometry:
    def evaluate(self, q):
        return {'f': np.asarray(q)[:3].copy(), 'W': 1.,
                'gradient_W': np.zeros(7), 'hessian_W': np.zeros((7, 7))}


def fixture():
    policy = Policy.load()
    model, geometry = IdentityPlant(), ConstantGeometry()
    barrier = BarrierEvaluator(model, geometry, -np.ones(7), np.ones(7),
                               np.ones(7), np.ones(7), .1, 5, 5, 5)
    return SimpleNamespace(policy=policy, model=model, geometry=geometry, barriers=barrier,
                           observer=MomentumObserver(model, policy.ko),
                           controller=SlotineLiController(model, policy.lambdas, policy.kappa),
                           qp=HardSafetyQP(np.ones(7), policy.raw['solver']['QP_settings']),
                           bounds=DisturbanceBounds(np.ones(7), 1.4*np.ones(7)))


def state():
    return ExecutionState(np.zeros(7), np.zeros(7), np.zeros(7), 0.)


def envelope():
    return SignedObserverEnvelope(SignedClock(-.156), np.full(7, 20.), np.ones(7), np.full(7, 1.4))


class R3Tests(unittest.TestCase):
    def test_computed_torque_has_correct_inverse_dynamics_and_feedback_signs(self):
        e = {'M': np.diag(np.arange(1., 8.)), 'C': .03*np.ones((7, 7)),
             'g': np.arange(7.), 'F': .1*np.ones(7)}
        model = SimpleNamespace(evaluate=lambda q, v: e)
        c = SampledComputedTorque(model, 8*np.ones(7), 3*np.ones(7))
        q, v, dhat = np.arange(7.)/100, np.arange(7.)/10, .2*np.ones(7)
        ref = ReferenceSample(np.ones(7), np.zeros(7), np.zeros(7))
        tau, info = c.command(q, v, ref, dhat)
        acc = np.linalg.solve(e['M'], tau+dhat-e['C']@v-e['g']-e['F'])
        np.testing.assert_allclose(acc, 8*(ref.q-q)-3*v)
        np.testing.assert_allclose(info['acceleration_command'], acc)

    def test_nominal_sampled_poles_derive_frozen_gains_and_both_c4_periods_stable(self):
        plan = json.loads((ROOT/'policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json').read_text())
        p = plan['startup_controller']
        r, delta = p['design_pole'], p['design_period_s']
        kp, kd = (1-r)**2/delta**2, (3-2*r-r*r)/(2*delta)
        np.testing.assert_array_equal(p['kp_s_inverse_squared'], np.full(7, kp))
        np.testing.assert_array_equal(p['kd_s_inverse'], np.full(7, kd))
        c = SampledComputedTorque(IdentityPlant(), np.full(7, kp), np.full(7, kd))
        np.testing.assert_allclose(np.sort(np.linalg.eigvals(c.frozen_double_integrator_matrix(delta))), [r, r], atol=1e-8)
        for dt in [.001, .0005]:
            self.assertTrue(np.all(abs(np.linalg.eigvals(c.frozen_double_integrator_matrix(dt))) < 1))

    def test_startup_rejects_moving_reference_and_nonfinite_or_nonpositive_gains(self):
        c = SampledComputedTorque(IdentityPlant(), np.ones(7), np.ones(7))
        with self.assertRaises(ValueError):
            c.command(np.zeros(7), np.zeros(7), ReferenceSample(np.zeros(7), np.ones(7), np.zeros(7)), np.zeros(7))
        for bad in [np.zeros(7), np.full(7, np.nan), np.ones(6)]:
            with self.assertRaises(ValueError): SampledComputedTorque(IdentityPlant(), bad, np.ones(7))

    def test_quintic_matches_measured_initial_and_terminal_conditions(self):
        q, v, offset = np.arange(7.)/100, np.arange(7.)/200, np.full(7, .01)
        ref = QuinticMeasuredReference(q, v, offset, .25)
        start, end = ref.sample(0.), ref.sample(.25)
        np.testing.assert_array_equal(start.q, q)
        np.testing.assert_array_equal(start.qd, v)
        np.testing.assert_array_equal(start.qdd, np.zeros(7))
        np.testing.assert_allclose(end.q, q+offset, atol=1e-15)
        np.testing.assert_allclose(end.qd, 0, atol=1e-15)
        np.testing.assert_allclose(end.qdd, 0, atol=1e-14)
        with self.assertRaises(ValueError): ref.sample(-.001)
        with self.assertRaises(ValueError): ref.sample(.251)

    def test_strict_full_qp_rejects_negative_raw_row_even_when_solver_accepts(self):
        system = fixture()
        # A deliberately bad solver result passes normalized T29 tolerance,
        # but violates a raw torque row. It must never reach the plant.
        system.qp = SimpleNamespace(solve=lambda u, r: QPResult(
            np.full(7, 1+1e-12), 'PROXQP_SOLVED', False,
            {'normalized_primal': 1e-12, 'scaled_stationarity': 0.}))
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.zeros(7), .002)
        tau, check = strict_qp_check(system, state(), envelope(), ref)
        self.assertIsNone(tau)
        self.assertFalse(check['strict_pass'])
        self.assertEqual(check['G'].shape, (43, 7))
        self.assertLess(np.min(check['raw_slacks']), 0.)
        self.assertFalse(check['torque_applied'])

    def test_exact_zero_transfer_no_observer_or_clock_reinitialization(self):
        system = fixture()
        system.controller = SampledComputedTorque(system.model, np.ones(7), np.ones(7))
        runner = AppliedTorquePrehold(system, HoldSchedule(.001, .00025), .002, np.zeros(7),
                                      np.full(7, .01), np.full(7, .02), lambda t: np.full(7, .01))
        result = runner.run()
        self.assertTrue(result.completed)
        transferred = result.measured_state_at_zero()
        for key in ['q', 'qd', 'z']:
            np.testing.assert_array_equal(getattr(result.state, key), getattr(transferred, key))
        self.assertTrue(np.any(transferred.z != 0))
        self.assertEqual(runner.clock.elapsed(0.), .002)
        self.assertTrue(np.all(runner.envelope.value(.001) < runner.envelope.value(0.)))

    def test_held_torque_plant_and_dob_share_exact_input_for_every_stage(self):
        system = fixture()
        observer_derivative = system.observer.derivative
        system.observer.derivative = Mock(wraps=observer_derivative)
        tau = np.full(7, .2)
        after, log = integrate_substep(system, state(), tau, .00025, .00025, envelope(), lambda t: np.zeros(7))
        np.testing.assert_allclose(after.qd, tau*.00025, atol=1e-16)
        np.testing.assert_allclose(after.q, tau*.00025**2/2, atol=1e-16)
        self.assertEqual(system.observer.derivative.call_count, 4)
        for call in system.observer.derivative.call_args_list:
            np.testing.assert_array_equal(call.args[-1], tau)
        self.assertEqual(len(log['samples']), 5)
        self.assertTrue(all(log['checks'].values()))

    def test_shared_bus_power_and_rk4_quadrature_do_not_sum_per_joint_smoothing(self):
        system = fixture()
        zero = np.zeros(7)
        epsilon = system.policy.raw['energy']['nonregenerative_smoothing']['epsilon_W']
        self.assertEqual(modeled_power(zero, zero, system.policy.raw['energy']), epsilon/2)
        _, log = integrate_substep(system, state(), zero, .00025, .00025, envelope(), lambda t: zero)
        self.assertAlmostEqual(log['modeled_electrical_energy_increment_J'], .00025*epsilon/2, places=18)

    def test_failed_endpoint_cannot_advance_or_receive_torque(self):
        system = fixture()
        system.qp.solve = Mock(side_effect=AssertionError('No solve after failed endpoint'))
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.zeros(7), .002)
        out = run_a2_cell(system, state(), HoldSchedule(.001, .00025), envelope(), ref,
                          lambda t: np.zeros(7), {'strict_pass': False})
        self.assertFalse(out['passed'])
        self.assertEqual(out['final_state']['physical_t_s'], 0.)
        self.assertEqual(out['trace'], [])
        system.qp.solve.assert_not_called()

    def test_later_qp_failure_stops_before_next_period_actuation(self):
        system = fixture()
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.zeros(7), .002)
        _, endpoint = strict_qp_check(system, state(), envelope(), ref)
        system.qp.solve = Mock(return_value=QPResult(None, 'PRIMAL_INFEASIBLE', True, {}))
        out = run_a2_cell(system, state(), HoldSchedule(.001, .00025), envelope(), ref,
                          lambda t: np.zeros(7), endpoint)
        self.assertFalse(out['completed'])
        self.assertEqual(out['final_state']['physical_t_s'], .001)
        self.assertEqual(len(out['trace']), 4)
        self.assertEqual(len(out['updates']), 2)
        self.assertFalse(out['updates'][-1]['torque_applied'])
        self.assertEqual(out['failure']['reason'], 'HARD_QP_FAILURE_NO_ADVANCE')

    def test_observer_envelope_violation_is_retained_without_bound_enlargement(self):
        system = fixture()
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.zeros(7), .002)
        env = envelope()
        _, endpoint = strict_qp_check(system, state(), env, ref)
        out = run_a2_cell(system, state(), HoldSchedule(.001, .00025), env, ref,
                          lambda t: np.full(7, 100.), endpoint)
        self.assertFalse(out['passed'])
        self.assertEqual(len(out['trace']), 1)
        self.assertIn('observer_samples', out['failure']['failed_checks'])
        self.assertLess(np.min(out['metrics']['minimum_observer_envelope_slack_Nm']), 0)

    def test_refinement_checks_all_edges_and_never_passes_missing_or_failed_cells(self):
        thresholds = Policy.load().raw['fixed_acceptance_thresholds']
        metrics = {'modeled_electrical_energy_J': 1., 'duration_s': .25,
                   'maximum_intervention_Nm': 0., 'minimum_normalized_raw_slack': .1}
        cells = [{'a2': {'completed': True, 'passed': True, 'metrics': dict(metrics)}} for _ in range(4)]
        check = compare_refinement(cells, thresholds)
        self.assertTrue(check['passed'])
        self.assertEqual(len([c for c in check['comparisons'] if c['required']]), 4)
        cells[3]['a2']['metrics']['modeled_electrical_energy_J'] = 1.01
        self.assertFalse(compare_refinement(cells, thresholds)['passed'])
        cells[3]['a2']['completed'] = False
        self.assertIn('NOT_COMPARABLE', compare_refinement(cells, thresholds)['comparisons'][1]['status'])
        self.assertFalse(compare_refinement(cells[:3], thresholds)['passed'])


class Results(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append({'test': test.id(), 'result': 'PASS'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append({'test': test.id(), 'result': 'FAIL', 'traceback': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append({'test': test.id(), 'result': 'ERROR', 'traceback': self._exc_info_to_string(err, test)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(R3Tests))
    with args.report.open('x') as stream:
        json.dump({'scope': 'ENGINEERING_CONTRACTS_NOT_INDEPENDENT_REVIEW', 'tests_run': result.testsRun,
                   'overall_pass': result.wasSuccessful(), 'checks': result.rows}, stream, indent=2)
        stream.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
