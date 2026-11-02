"""Numerical/algebraic screen tests, not plant rollout or human review."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse
import copy
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from panda_closed_loop.config import Policy
from panda_closed_loop.feasibility import pair_conditions,duration_for_pairs,q_grid,elapsed_envelope,planner_pair_screen,pointwise_planner_lower_witness
from panda_closed_loop.readiness import m1_registry
from panda_closed_loop.a2_plan import quintic_reference_coefficients,check_plan
from panda_closed_loop.assembly import build_components
from panda_dynamics import QMIN,QMAX,VMAX,TAUMAX,disturbance_bounds,PandaDynamics
import p1_feasibility


class Screens(unittest.TestCase):
    def test_diagonal_fixture_exact_pair_thresholds_and_units(self):
        result=pair_conditions(2*np.eye(7),.3*np.ones(7),4*np.ones(7),np.ones(7),2,3,.5)
        np.testing.assert_allclose(result['velocity']['lhs'],.6)
        np.testing.assert_allclose(result['velocity']['rhs'],.5)
        np.testing.assert_allclose(result['position']['rhs'],12)
        self.assertFalse(result['velocity']['passed']);self.assertTrue(result['position']['passed'])
        self.assertEqual(result['position']['unit'],'rad/s^2')

    def test_actual_position_and_velocity_row_sums_cancel_torque_bias_and_velocity(self):
        system=build_components();q=(QMIN+QMAX)/2;vp=.02*TAUMAX
        N=abs(np.linalg.solve(system.model.evaluate(q)['M'],np.eye(7)))
        pairs=pair_conditions(N,vp,QMAX-QMIN,VMAX,5,5,5)
        for scale in [-.2,.3]:
            v=scale*np.linspace(-1,1,7);tau=scale*np.arange(1,8);estimate=scale*np.ones(7)
            rows=system.barriers.rows(q,v,estimate,vp).slacks(tau)
            np.testing.assert_allclose(rows[:7]+rows[7:14],2*np.array(pairs['position']['slack']),atol=3e-12)
            np.testing.assert_allclose(rows[15:22]+rows[22:29],2*np.array(pairs['velocity']['slack']),atol=3e-12)
        self.assertEqual(pairs['velocity']['violating_joints_1_based'],[1,3,4,5,6,7])
        self.assertEqual(pairs['position']['violating_joints_1_based'],[1,3])

    def test_shared_gain_duration_is_analytic_and_rounded_once(self):
        b=10*np.ones((2,7));rhs=2*np.ones(7)
        result=duration_for_pairs(b,rhs,np.ones(7),1.4*np.ones(7),20*np.ones(7),.001)
        expected=-np.log((.2-.07)/.93)/20
        self.assertAlmostEqual(result['critical_s'],expected,places=14)
        self.assertAlmostEqual(result['proposed_T_pre_s'],(np.ceil(expected/.001)+1)*.001)
        t=result['proposed_T_pre_s'];vp=elapsed_envelope(0,t,np.full(7,20.),np.ones(7),1.4*np.ones(7))
        self.assertTrue(np.all(10*vp<rhs))

    def test_floor_failure_never_returns_a_fake_duration_or_fallback(self):
        result=duration_for_pairs(10*np.ones((1,7)),.5*np.ones(7),np.ones(7),1.4*np.ones(7),20*np.ones(7),.001)
        self.assertEqual(result['status'],'NO_FINITE_DURATION_ABOVE_FLOOR')
        self.assertIsNone(result['proposed_T_pre_s'])

    def test_signed_clock_envelope_does_not_restart_at_zero(self):
        dbar,rate=disturbance_bounds();pre=.2
        np.testing.assert_array_equal(elapsed_envelope(-pre,pre,np.full(7,20.),dbar,rate),dbar)
        v0=elapsed_envelope(0,pre,np.full(7,20.),dbar,rate)
        self.assertTrue(np.all(v0<dbar))
        self.assertTrue(np.all(elapsed_envelope(.1,pre,np.full(7,20.),dbar,rate)<v0))
        with self.assertRaises(ValueError):elapsed_envelope(-pre-.01,pre,np.full(7,20.),dbar,rate)

    def test_state_grid_is_fixed_and_no_favorable_state_selection(self):
        center=np.arange(7);radii=.01*np.ones(7);q=q_grid(center,radii)
        self.assertEqual(q.shape,(129,7));np.testing.assert_array_equal(q[0],center)
        np.testing.assert_allclose(q[1],center-radii);np.testing.assert_allclose(q[-1],center+radii)

    def test_planner_factor_two_and_missing_bounds_remain_blocked(self):
        args=(.2*np.ones(7),4*np.ones(7),np.ones(7),2,3,5,.01*np.ones(7),.02)
        blocked=planner_pair_screen(*args)
        self.assertEqual(blocked['status'],'BLOCKED_MISSING_M1_BOUNDS')
        self.assertFalse(blocked['point_abs_N_substituted_as_upper_bound'])
        result=planner_pair_screen(*args,Nbar=np.eye(7),Abar_plus=np.eye(7),Abar_minus=np.eye(7))
        np.testing.assert_allclose(result['velocity']['lhs'],.42)
        np.testing.assert_allclose(result['position']['lhs'],.41)
        self.assertFalse(result['full_planner_computed'])

    def test_lower_witness_is_not_routed_through_upper_bound_screen(self):
        with patch('panda_closed_loop.feasibility.planner_pair_screen',side_effect=AssertionError('No Nbar substitution')):
            w=pointwise_planner_lower_witness(np.eye(7),.2*np.ones(7),4*np.ones(7),np.ones(7),2,3,5,.01*np.ones(7),.02)
        self.assertFalse(w['point_abs_N_substituted_as_upper_bound'])
        np.testing.assert_allclose(w['reviewer_factor_two']['velocity_lhs'],.42)
        np.testing.assert_allclose(w['matched_reference_start_factor_three']['velocity_lhs'],.62)

    def test_invalid_nonfinite_bounds_are_rejected(self):
        args=[np.eye(7),np.ones(7),4*np.ones(7),np.ones(7),2,3,5]
        for index,bad in [(0,np.full((7,7),np.nan)),(1,-np.ones(7)),(2,np.zeros(7)),(3,np.ones(6)),(4,0),(6,np.inf)]:
            modified=list(args);modified[index]=bad
            with self.assertRaises(ValueError):pair_conditions(*modified)

    def test_M1_flags_are_conditional_not_universal_A2_blockers(self):
        policy=Policy.load()
        for kind,required in [(None,None),('stage1_tightened',True),('nonoptimized_measured_state',False)]:
            self.assertTrue(all(x['required_for_A2_entry']==required for x in m1_registry(policy,kind)['entries']))
            self.assertTrue(all(x['required_for_A3_stage1'] for x in m1_registry(policy,kind)['entries']))
        self.assertFalse(any(x.startswith('M1_MISSING') for x in policy.a2_blockers('nonoptimized_measured_state')))
        self.assertTrue(any(x.startswith('M1_MISSING') for x in policy.a2_blockers('stage1_tightened')))
        self.assertIn('OFFICIAL_A2_EXECUTION_NOT_AUTHORIZED',policy.a2_blockers('nonoptimized_measured_state'))

    def test_nonoptimized_quintic_matches_measured_start_and_endpoint(self):
        q=np.linspace(-.1,.1,7);v=np.linspace(-.01,.01,7);dq=.01*np.ones(7);T=.25
        c=quintic_reference_coefficients(q,v,dq,T)
        np.testing.assert_allclose(c[0],q);np.testing.assert_allclose(c[1]/T,v)
        np.testing.assert_allclose(c.sum(axis=0),q+dq,atol=1e-15)
        np.testing.assert_allclose(sum(i*c[i] for i in range(1,6))/T,0,atol=3e-15)
        np.testing.assert_allclose(sum(i*(i-1)*c[i] for i in range(2,6))/T**2,0,atol=1e-13)

    def test_plan_checker_does_not_equate_completeness_to_approval(self):
        intent=json.loads((ROOT/'policy/v1.2.2-draft/PREDECLARED_P1_DESIGN.json').read_text())
        draft={'A2_execution_reference':intent['reference_proposal'],'observer_proposal':intent['observer_proposal'],
               'failure_semantics':intent['failure_semantics'],'integration':Policy.load().raw['integration']}
        result=check_plan(draft,Policy.load())
        self.assertEqual(result['official_A2'],'NO-GO')
        self.assertEqual(next(x for x in result['items'] if x['item']=='planner_only_M1_inputs')['required'],False)
        self.assertTrue(any(x['status']=='AWAITING HUMAN REVIEW' for x in result['items']))

    def test_complete_draft_and_missing_or_nonfinite_fields(self):
        draft=json.loads((ROOT/'policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json').read_text())
        result=check_plan(draft,Policy.load())
        self.assertFalse(any(i['status']=='FAIL' for i in result['items']))
        missing=copy.deepcopy(draft);del missing['A2_acceptance_proposal']['observer_envelope']
        self.assertEqual(next(i for i in check_plan(missing,Policy.load())['items'] if i['item']=='acceptance_metric_definitions')['status'],'FAIL')
        bad=copy.deepcopy(draft);bad['A2_execution_reference']['duration_s']=float('nan')
        self.assertEqual(next(i for i in check_plan(bad,Policy.load())['items'] if i['item']=='reference_numeric_fields')['status'],'FAIL')
        self.assertEqual(check_plan(bad,Policy.load())['official_A2'],'NO-GO')

    def test_tolerance_accepted_solver_cannot_mask_a_negative_raw_fixture_slack(self):
        accepted=SimpleNamespace(stop_requested=False,diagnostics={'exact_all_rows_nonnegative':True})
        negative=SimpleNamespace(stop_requested=False,diagnostics={'exact_all_rows_nonnegative':False})
        rejected=SimpleNamespace(stop_requested=True,diagnostics={'exact_all_rows_nonnegative':True})
        self.assertTrue(p1_feasibility.fixture_pass(accepted))
        self.assertFalse(p1_feasibility.fixture_pass(negative))
        self.assertFalse(p1_feasibility.fixture_pass(rejected))

    def test_screen_calls_neither_plant_acceleration_nor_disturbance_truth(self):
        intent=json.loads((ROOT/'policy/v1.2.2-draft/PREDECLARED_P1_DESIGN.json').read_text())
        with (patch.object(PandaDynamics,'acceleration',side_effect=AssertionError('No integration')),
              patch('panda_closed_loop.assembly.dual_harmonic_disturbance',side_effect=AssertionError('No truth'))):
            result=p1_feasibility.analyze(Policy.load(),intent)
        self.assertEqual(result['plant_integrations_performed'],0)
        self.assertFalse(result['automatic_P2_fallback'])
        self.assertEqual(result['P1_overall'],'BLOCKED_PHYSICAL_PREHOLD_NOT_VERIFIED')


class Results(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.rows=[]
    def addSuccess(self,test):super().addSuccess(test);self.rows.append({'test':test.id(),'result':'PASS'})
    def addFailure(self,test,e):super().addFailure(test,e);self.rows.append({'test':test.id(),'result':'FAIL','traceback':self._exc_info_to_string(e,test)})
    def addError(self,test,e):super().addError(test,e);self.rows.append({'test':test.id(),'result':'ERROR','traceback':self._exc_info_to_string(e,test)})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(Screens))
    args.report.write_text(json.dumps({'scope':'NON_PLANT_STATIC_SCREEN_UNIT_TESTS_NOT_A2','tests_run':result.testsRun,
        'overall_pass':result.wasSuccessful(),'checks':result.rows},indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
