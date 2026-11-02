"""Signed-clock/hold contracts on explicit synthetic plants, not Panda evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from panda_closed_loop.preparation import (SignedClock,SignedObserverEnvelope,PreparationState,
    AppliedTorquePrehold,rk4_extension_coefficients,component_extrema,endpoint_diagnostics)
from panda_closed_loop.observer import MomentumObserver,DisturbanceBounds
from panda_closed_loop.controller import SlotineLiController
from panda_closed_loop.stepper import ExecutionState,HoldSchedule
from panda_closed_loop.barriers import BarrierEvaluator
from panda_closed_loop.qp import HardSafetyQP
from panda_closed_loop.config import Policy
from panda_closed_loop.a2_plan import check_plan


class IdentityPlant:
    def evaluate(self,q,qd=None):
        return {'M':np.eye(7),'C':np.zeros((7,7)),'g':np.zeros(7),'F':np.zeros(7)}


class ConstantGeometry:
    def evaluate(self,q):
        return {'W':1.,'gradient_W':np.zeros(7),'hessian_W':np.zeros((7,7))}


def system(dbar=1.):
    model=IdentityPlant();p=SimpleNamespace(ko=(20.,)*7)
    return SimpleNamespace(model=model,policy=p,observer=MomentumObserver(model,p.ko),
        controller=SlotineLiController(model,5*np.ones(7),10),
        bounds=DisturbanceBounds(dbar*np.ones(7),1.4*dbar*np.ones(7)),
        barriers=BarrierEvaluator(model,ConstantGeometry(),-np.ones(7),np.ones(7),2*np.ones(7),np.ones(7),.1,5,5,5),
        qp=HardSafetyQP(np.ones(7),Policy.load().raw['solver']['QP_settings']))


class PreparationTests(unittest.TestCase):
    def runner(self,sys=None,disturbance=None,duration=.002):
        return AppliedTorquePrehold(sys or system(),HoldSchedule(.001,.00025),duration,np.zeros(7),
            .01*np.ones(7),.02*np.ones(7),disturbance or (lambda t:.01*np.ones(7)))

    def test_signed_epoch_envelope_continuity_through_zero(self):
        clock=SignedClock(-.156)
        e=SignedObserverEnvelope(clock,20*np.ones(7),np.ones(7),1.4*np.ones(7))
        np.testing.assert_array_equal(e.value(-.156),np.ones(7))
        np.testing.assert_allclose(e.value(0),.07+.93*np.exp(-20*.156))
        self.assertTrue(np.all(e.value(.001)<e.value(0)))
        self.assertTrue(np.all(e.value(-.001)>e.value(0)))
        with self.assertRaises(ValueError):e.value(-.157)

    def test_original_nonnegative_execution_contract_is_preserved(self):
        with self.assertRaises(ValueError):ExecutionState(np.zeros(7),np.zeros(7),np.zeros(7),-.1)
        self.assertEqual(PreparationState(np.zeros(7),np.zeros(7),np.zeros(7),-.1).t,-.1)

    def test_signed_clock_and_state_reject_nonfinite_inputs(self):
        for t in [float('nan'),float('inf')]:
            with self.assertRaises(ValueError):SignedClock(t)
            with self.assertRaises(ValueError):PreparationState(np.zeros(7),np.zeros(7),np.zeros(7),t)
        state=PreparationState(np.zeros(7),np.zeros(7),np.zeros(7),0)
        with self.assertRaises(ValueError):state.z[0]=1

    def test_plant_gets_original_negative_clock_without_phase_restart(self):
        seen=[]
        def disturbance(t):seen.append(t);return .01*np.ones(7)
        r=self.runner(disturbance=disturbance);result=r.run()
        self.assertTrue(result.completed)
        self.assertEqual(min(seen),-.002);self.assertEqual(max(seen),0.)
        self.assertTrue(any(t<0 for t in seen))
        self.assertEqual(r.clock.observer_epoch,-.002)

    def test_observer_uses_saturated_applied_torque_and_plant_is_not_clamped(self):
        sys=system()
        sys.controller=SimpleNamespace(command=Mock(return_value=(1000*np.ones(7),{})))
        derivative=sys.observer.derivative;seen=[]
        def observe(q,v,z,tau):seen.append(tau.copy());return derivative(q,v,z,tau)
        sys.observer.derivative=observe
        r=self.runner(sys,lambda t:np.zeros(7),duration=.001);result=r.run()
        self.assertTrue(result.completed)
        for tau in seen:np.testing.assert_array_equal(tau,np.ones(7))
        np.testing.assert_allclose(result.state.qd,.001,atol=1e-15)
        np.testing.assert_allclose(result.state.q,.5*.001**2,atol=1e-15)
        self.assertTrue(np.any(result.state.q!=0))

    def test_zero_endpoint_transfer_preserves_measured_state_and_observer(self):
        runner=self.runner();result=runner.run();state=result.measured_state_at_zero()
        for k in ['q','qd','z']:np.testing.assert_array_equal(getattr(state,k),getattr(result.state,k))
        self.assertTrue(np.any(state.q!=0));self.assertTrue(np.any(state.qd!=0));self.assertTrue(np.any(state.z!=0))
        self.assertEqual(state.t,0.)
        np.testing.assert_allclose(runner.envelope.value(state.t),.07+.93*np.exp(-20*.002))

    def test_first_failed_substep_is_retained_without_zero_endpoint_or_retries(self):
        r=self.runner(system(100.),lambda t:100*np.ones(7));result=r.run()
        self.assertFalse(result.completed);self.assertEqual(result.decision,'FAIL_PREDECLARED_HOLD')
        self.assertEqual(len(result.trace),1);self.assertLess(result.state.t,0)
        self.assertIn('qd_tolerance',result.failure['failed_checks'])
        self.assertTrue(result.failure['no_further_torque_or_state_advance'])
        self.assertEqual(r.T_pre,.002)
        with self.assertRaises(ValueError):result.measured_state_at_zero()

    def test_abort_diagnostics_use_actual_state_elapsed_bound_and_all_43_rows(self):
        r=self.runner(system(100.),lambda t:100*np.ones(7));result=r.run()
        endpoint=endpoint_diagnostics(r.system,r,result)
        np.testing.assert_array_equal(endpoint['state']['qd'],result.state.qd)
        np.testing.assert_array_equal(endpoint['propagated_varpi'],r.envelope.value(result.state.t))
        self.assertFalse(np.array_equal(endpoint['propagated_varpi'],r.envelope.value(0.)))
        self.assertTrue(endpoint['QP_full_43_rows']);self.assertFalse(endpoint['valid_zero_time_endpoint'])
        self.assertFalse(endpoint['motion_started']);self.assertFalse(endpoint['official_A2_authorized'])
        self.assertEqual(endpoint['scope'],'ACTUAL_SIMULATED_ABORT_STATE_NOT_A_VALID_ZERO_ENDPOINT')

    def test_cubic_extrema_find_interior_violation_hidden_from_endpoints(self):
        c=np.array([[0.],[.12],[-.12],[0.]])
        result=component_extrema(c)
        self.assertAlmostEqual(result['maximum'][0],.03,places=15)
        self.assertIn(.5,result['checked_theta'][0])
        self.assertAlmostEqual(result['minimum'][0],0.)

    def test_rk4_extension_matches_step_endpoint_and_known_quadratic(self):
        k=np.array([[.12],[0.],[0.],[-.12]])
        c=rk4_extension_coefficients(np.array([0.]),1.,k)
        np.testing.assert_allclose(c[:,0],[0.,.12,-.12,0.],atol=1e-15)
        np.testing.assert_allclose(c.sum(axis=0),(k[0]+2*k[1]+2*k[2]+k[3])/6,atol=1e-15)
        with self.assertRaises(ValueError):component_extrema(np.full((4,1),np.nan))

    def test_declared_duration_must_align_without_silent_rounding(self):
        with self.assertRaises(ValueError):self.runner(duration=.0011)

    def test_failed_prehold_evidence_cannot_leave_checklist_at_untested_or_GO(self):
        policy=Policy.load()
        draft=json.loads((ROOT/'policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json').read_text())
        cells=[{'grid':g,'completed':False,'valid_zero_endpoint':False} for g in policy.raw['integration']['validation_grid']]
        prep={'summary':{'P1_numerical_hold':'FAIL','cells':cells},'clock_tests':{'overall_pass':True}}
        result=check_plan(draft,policy,preparation=prep)
        statuses={i['item']:i['status'] for i in result['items']}
        self.assertEqual(statuses['physical_prehold_dynamics'],'FAIL')
        self.assertEqual(statuses['signed_physical_prehold_clock'],'PASS')
        self.assertEqual(statuses['actual_zero_endpoint_full_QP'],'NOT TESTED')
        self.assertEqual(result['P1'],'FAIL_PREDECLARED_TORQUE_HOLD');self.assertEqual(result['official_A2'],'NO-GO')

    def test_summary_PASS_does_not_hide_missing_completed_C4_endpoints(self):
        policy=Policy.load()
        draft=json.loads((ROOT/'policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json').read_text())
        prep={'summary':{'P1_numerical_hold':'PASS','cells':[{'grid':policy.raw['integration']['validation_grid'][0],
            'completed':False,'valid_zero_endpoint':False}]}}
        self.assertEqual(check_plan(draft,policy,preparation=prep)['P1'],'FAIL_PREDECLARED_TORQUE_HOLD')


class Results(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.rows=[]
    def addSuccess(self,test):super().addSuccess(test);self.rows.append({'test':test.id(),'result':'PASS'})
    def addFailure(self,test,e):super().addFailure(test,e);self.rows.append({'test':test.id(),'result':'FAIL','traceback':self._exc_info_to_string(e,test)})
    def addError(self,test,e):super().addError(test,e);self.rows.append({'test':test.id(),'result':'ERROR','traceback':self._exc_info_to_string(e,test)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(PreparationTests))
    with a.report.open('x') as f:json.dump({'scope':'SYNTHETIC_DEVELOPMENT_CONTRACT_TESTS_NOT_PANDA_HOLD_OR_A2',
        'tests_run':result.testsRun,'overall_pass':result.wasSuccessful(),'checks':result.rows},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
