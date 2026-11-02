"""Causal sampled execution and fail-closed numerical A2 gate contracts."""
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
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.p1_r3 import QuinticMeasuredReference, strict_qp_check, run_a2_cell
from panda_closed_loop.p1_r4 import AB2TorqueController, numerical_gate
from panda_closed_loop.qp import QPResult
from panda_closed_loop.stepper import HoldSchedule
from test_p1_r3 import fixture, state, envelope, Results


class RawInput:
    def command(self, q, v, reference, dhat):
        return np.asarray(q).copy(), {}


def request(controller, raw):
    return controller.command(np.full(7, raw), np.zeros(7), None, np.zeros(7))


def engineering():
    return {k: True for k in ['frozen_inputs_unchanged', 'contracts_pass', 'base_regressions_match_current_inputs',
                              'geometry_equivalence_pass', 'pinned_versions_match', 'canonical_model_audit_pass']}


def complete_cells(plan):
    return [{'grid': grid, 'prehold': {'completed': True}, 'endpoint': {'valid_zero_endpoint': True},
             'audit': {'passed': True}, 'a2': {'completed': True, 'passed': True, 'metrics': {
                 'modeled_electrical_energy_J': 1., 'duration_s': .25,
                 'maximum_intervention_Nm': 0., 'minimum_normalized_raw_slack': .1}}}
            for grid in plan['C4_grid']]


class R4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json').read_text())

    def test_bootstrap_uses_only_current_request_and_fresh_cells_have_no_history(self):
        first = AB2TorqueController(RawInput())
        tau, info = request(first, 2.)
        np.testing.assert_array_equal(tau, np.full(7, 2.))
        self.assertIsNone(info['previous_continuous_request_Nm'])
        request(first, 8.)
        fresh = AB2TorqueController(RawInput())
        tau, info = request(fresh, 3.)
        np.testing.assert_array_equal(tau, np.full(7, 3.))
        self.assertEqual(info['sampling_update_index'], 0)

    def test_affine_torque_request_integral_is_exact_after_bootstrap(self):
        controller = AB2TorqueController(RawInput())
        dt = .001
        for k in range(5):
            tau, info = request(controller, 1+2*k*dt)
            if k:
                expected_mean = 1+2*(k+.5)*dt
                np.testing.assert_allclose(tau, expected_mean, atol=2e-16)
                self.assertEqual(info['sampling_rule'], 'AB2_CAUSAL_INTERVAL_AVERAGE')

    def test_sampled_linear_feedback_converges_to_analytic_solution_at_second_order(self):
        def error(n):
            controller = AB2TorqueController(RawInput())
            x, dt = 1., 1/n
            for _ in range(n):
                tau, _ = request(controller, -x)
                x += dt*tau[0]
            return abs(x-np.exp(-1.))
        ratio = error(100)/error(200)
        self.assertGreater(ratio, 3.7)
        self.assertLess(ratio, 4.3)

    def test_invalid_request_does_not_consume_history(self):
        controller = AB2TorqueController(RawInput())
        with self.assertRaises(ValueError): request(controller, np.nan)
        self.assertEqual(controller.updates, 0)
        tau, info = request(controller, 2.)
        self.assertIsNone(info['previous_continuous_request_Nm'])

    def test_history_copies_inputs_and_diagnostics(self):
        controller = AB2TorqueController(RawInput())
        _, first = request(controller, 2.)
        first['continuous_request_Nm'][:] = 900.
        tau, second = request(controller, 4.)
        np.testing.assert_array_equal(tau, np.full(7, 5.))
        np.testing.assert_array_equal(second['previous_continuous_request_Nm'], np.full(7, 2.))

    def test_endpoint_QP_is_not_recomputed_or_consumed_twice(self):
        system = fixture()
        system.controller = AB2TorqueController(system.controller)
        # Keep this history/endpoint test inside the synthetic 1 N m box.
        # The Panda reference remains the independently frozen 0.01 rad task.
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.full(7, 1e-7), .004)
        _, endpoint = strict_qp_check(system, state(), envelope(), ref)
        self.assertEqual(system.controller.updates, 1)
        out = run_a2_cell(system, state(), HoldSchedule(.001, .00025), envelope(), ref,
                          lambda t: np.zeros(7), endpoint)
        self.assertTrue(out['passed'])
        self.assertEqual(system.controller.updates, 4)
        self.assertEqual([u['tracking_errors']['sampling_update_index'] for u in out['updates']], list(range(4)))
        self.assertEqual(out['updates'][0]['candidate_tau'].tolist(), endpoint['candidate_tau'].tolist())

    def test_QP_failure_stops_without_retry_or_extra_state_advance(self):
        system = fixture()
        system.controller = AB2TorqueController(system.controller)
        ref = QuinticMeasuredReference(np.zeros(7), np.zeros(7), np.zeros(7), .003)
        _, endpoint = strict_qp_check(system, state(), envelope(), ref)
        system.qp.solve = Mock(return_value=QPResult(None, 'PRIMAL_INFEASIBLE', True, {}))
        out = run_a2_cell(system, state(), HoldSchedule(.001, .00025), envelope(), ref,
                          lambda t: np.zeros(7), endpoint)
        self.assertFalse(out['passed'])
        self.assertEqual(out['final_state']['physical_t_s'], .001)
        self.assertEqual(system.controller.updates, 2)
        system.qp.solve.assert_called_once()
        self.assertFalse(out['updates'][-1]['torque_applied'])

    def test_GO_requires_both_complete_cohorts_and_no_missing_engineering_fields(self):
        cells = complete_cells(self.plan)
        self.assertEqual(numerical_gate(cells, self.plan, engineering())['status'], 'GO')
        self.assertEqual(numerical_gate(cells[:4], self.plan, engineering())['status'], 'HOLD')
        self.assertEqual(numerical_gate(cells, self.plan, {'only_this': True})['status'], 'HOLD')
        cells[-1]['audit']['passed'] = False
        self.assertEqual(numerical_gate(cells, self.plan, engineering())['status'], 'HOLD')

    def test_four_individual_passes_cannot_hide_refinement_failure(self):
        cells = complete_cells(self.plan)
        cells[2]['a2']['metrics']['modeled_electrical_energy_J'] = 1.01
        gate = numerical_gate(cells, self.plan, engineering())
        self.assertEqual(gate['status'], 'HOLD')
        self.assertFalse(gate['checks']['original_C4_all_refinements'])

    def test_completed_prehold_without_endpoint_or_execution_cannot_be_GO(self):
        cells = complete_cells(self.plan)
        cells[0]['endpoint'] = None
        self.assertEqual(numerical_gate(cells, self.plan, engineering())['status'], 'HOLD')
        cells = complete_cells(self.plan)
        cells[0]['a2']['completed'] = False
        self.assertEqual(numerical_gate(cells, self.plan, engineering())['status'], 'HOLD')

    def test_GO_has_explicit_numerical_scope_and_never_manufactures_signatures(self):
        gate = numerical_gate(complete_cells(self.plan), self.plan, engineering())
        self.assertEqual(gate['status'], 'GO')
        self.assertEqual(gate['scope'], 'USER_AUTHORIZED_LEVEL_2_A2_SIMULATION_ONLY')
        self.assertIsNone(gate['independent_controls_signature'])
        self.assertIsNone(gate['independent_theory_signature'])
        self.assertEqual(gate['A3'], 'NO-GO')

    def test_original_C4_thresholds_and_passing_startup_are_preserved(self):
        p = Policy.load().raw
        r3 = json.loads((ROOT/'policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json').read_text())
        self.assertEqual(self.plan['C4_grid'][:4], p['integration']['validation_grid'])
        self.assertEqual(self.plan['fixed_acceptance_thresholds'], p['fixed_acceptance_thresholds'])
        for key in ['startup_controller', 'T_pre_s', 'q_radius_rad', 'qd_radius_rad_s', 'A2_reference']:
            self.assertEqual(self.plan[key], r3[key])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(R4Tests))
    with args.report.open('x') as f:
        json.dump({'scope': 'R4_ENGINEERING_CONTRACTS_NOT_INDEPENDENT_SIGNOFF', 'tests_run': result.testsRun,
                   'overall_pass': result.wasSuccessful(), 'checks': result.rows,
                   'source_sha256': digest(ROOT/'src/panda_closed_loop/p1_r4.py'),
                   'test_sha256': digest(Path(__file__)),
                   'plan_sha256': digest(ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json')}, f, indent=2)
        f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
