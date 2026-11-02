"""Development QP accuracy and unknown-M1 provenance contracts, not A3."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json,time,unittest
import numpy as np
from panda_dynamics import QMIN,QMAX,TAUMAX
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.qp import HardSafetyQP
from panda_closed_loop.a3_qp_bounds import (M1DomainSpec,M1BoundRecord,M1BoundBundle,MissingM1Bound,
    synthetic_box_rows,diagnostic_qp,independent_linear_feasibility,active_face_fixture,screen_state)


def domain(**overrides):
    values=dict(q_lower=-np.ones(7),q_upper=np.ones(7),v_lower=-2*np.ones(7),v_upper=2*np.ones(7),
        a_lower=-3*np.ones(7),a_upper=3*np.ones(7),tube_q_radius=.1*np.ones(7),tube_v_radius=.2*np.ones(7),
        position_extension_rad=.01,estimator_method='SYNTHETIC_DOMAIN_CONTRACT_ONLY',seed=11,budget=32)
    return M1DomainSpec(**{**values,**overrides})


def bound(d=None,**overrides):
    d=d or domain()
    values=dict(name='Nbar_il',values=np.ones((7,7)),units='inverse_inertia',domain_sha256=d.sha256,
        evaluator_sha256='a'*64,evidence_level='SAMPLED_LEVEL_2_ESTIMATE',method='SYNTHETIC_BOUND_CONTRACT_ONLY',
        grid_sha256='b'*64,seed=d.seed,budget=d.budget)
    return M1BoundRecord(**{**values,**overrides})


class DeliberatelySlowDiagnostic:
    def solve(self,nominal,rows):
        time.sleep(5.)
        raise AssertionError('This deliberately slow worker should be terminated')


class QPBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=Policy.load();cls.system=build_components(cls.policy)
        cls.system.geometry.function=cls.system.geometry.function.expand()
        cls.qp=HardSafetyQP(TAUMAX,cls.policy.raw['solver']['QP_settings'])

    def test_unconstrained_box_solution_matches_projection(self):
        nominal=np.array([1.,-2.,3.,-4.,.1,.2,.3])
        r=diagnostic_qp(self.qp,nominal,synthetic_box_rows(TAUMAX),nominal)
        self.assertTrue(r['normalized_KKT_pass']);self.assertTrue(r['oracle_pass'])
        self.assertTrue(r['strict_raw_pass']);self.assertIsNone(r['actually_applied'])

    def test_multiple_active_coupled_constraints_have_analytic_optimum(self):
        G=np.zeros((2,7));G[0,:2]=1;G[1,2:4]=[1,-1]
        target=np.array([1.,-1.,.5,.5,0,0,0]);multipliers=np.array([3.,2.])
        rows=synthetic_box_rows(TAUMAX,G,-G@target,np.ones(2))
        r=diagnostic_qp(self.qp,target-G.T@multipliers,rows,target)
        self.assertTrue(r['normalized_KKT_pass']);self.assertTrue(r['oracle_pass'])
        self.assertTrue(r['independent_LP']['feasible'])
        if r['negative_raw_rows']:self.assertFalse(r['strict_raw_pass'])

    def test_redundant_active_rows_do_not_require_unique_dual(self):
        G=np.zeros((2,7));G[0,:2]=1;G[1,:2]=2
        rows=synthetic_box_rows(TAUMAX,G,np.zeros(2),np.array([1.,2.]))
        r=diagnostic_qp(self.qp,-G.T@np.ones(2),rows,np.zeros(7))
        self.assertTrue(r['normalized_KKT_pass']);self.assertTrue(r['oracle_pass'])

    def test_matched_row_rescaling_preserves_primal_problem(self):
        G=np.zeros((2,7));G[0,:2]=1;G[1,2:4]=[1,-1]
        target=np.array([1.,-1.,.5,.5,0,0,0]);nominal=target-G.T@np.array([3.,2.])
        result=[]
        for factors in [np.ones(2),np.array([2.**-20,2.**20])]:
            rows=synthetic_box_rows(TAUMAX,G*factors[:,None],(-G@target)*factors,factors)
            result.append(diagnostic_qp(self.qp,nominal,rows,target))
        self.assertTrue(all(x['oracle_pass'] and x['normalized_KKT_pass'] for x in result))
        np.testing.assert_allclose(result[0]['candidate_for_analysis_only'],result[1]['candidate_for_analysis_only'],atol=1e-10,rtol=0)

    def test_contradictory_halfspaces_are_infeasible_in_both_solvers(self):
        G=np.zeros((2,7));G[0,0]=1;G[1,0]=-1
        rows=synthetic_box_rows(TAUMAX,G,np.array([-2.,1.]),np.ones(2))
        r=diagnostic_qp(self.qp,np.zeros(7),rows)
        self.assertTrue(r['production_stop_requested']);self.assertIsNone(r['candidate_for_analysis_only'])
        self.assertEqual(r['independent_LP']['status_code'],2)

    def test_full_Panda_initial_43_rows_are_infeasible_under_initial_bound(self):
        s=self.system;q=(QMIN+QMAX)/2;rows=s.barriers.rows(q,np.zeros(7),np.zeros(7),s.bounds.magnitude)
        self.assertEqual(len(rows.names),43)
        r=diagnostic_qp(self.qp,s.model.evaluate(q)['g'],rows)
        self.assertTrue(r['production_stop_requested']);self.assertEqual(r['independent_LP']['status_code'],2)

    def test_actual_measured_endpoint_full_43_rows_and_active_face_oracle(self):
        source=json.loads((ROOT/'runs/p1_r4/fresh_2fe50b9/cell_0.json').read_text())['endpoint']['QP']
        rows=self.system.barriers.rows(source['q'],source['qd'],source['dhat'],source['varpi'])
        np.testing.assert_array_equal(rows.G,source['G']);np.testing.assert_array_equal(rows.c,source['c'])
        base=diagnostic_qp(self.qp,np.array(source['u_nom']),rows,np.array(source['u_nom']))
        self.assertTrue(base['oracle_pass']);self.assertTrue(base['strict_raw_pass'])
        fixture=active_face_fixture(rows,np.array(source['candidate_tau']))
        r=diagnostic_qp(self.qp,fixture['nominal'],rows,fixture['expected'])
        self.assertTrue(r['normalized_KKT_pass']);self.assertTrue(r['oracle_pass'])
        self.assertIsNone(r['actually_applied'])

    def test_screen_never_promotes_point_inverse_to_planner_bound(self):
        s=self.system
        r=screen_state(s,(QMIN+QMAX)/2,np.zeros(7),np.zeros(7),s.bounds.magnitude,'initial',{'type':'SYNTHETIC_POINT_SCREEN'})
        self.assertEqual(r['filter_point_status'],'FAIL_POINT_SCREEN')
        self.assertEqual(r['planner_status'],'INCOMPLETE_MISSING_COMMON_DOMAIN_M1')
        self.assertFalse(r['point_inverse_promoted_to_upper_bound']);self.assertFalse(r['official_G2_5_positive'])

    def test_domain_is_explicit_immutable_and_hash_is_reproducible(self):
        a,b=domain(),domain();self.assertEqual(a.sha256,b.sha256)
        with self.assertRaises(ValueError):a.q_lower[0]=5
        self.assertNotEqual(a.sha256,domain(seed=12).sha256)
        for overrides in [{'a_upper':None},{'v_upper':-3*np.ones(7)},{'seed':None},{'budget':0}]:
            with self.assertRaises(ValueError):domain(**overrides)

    def test_missing_bounds_never_become_zero_or_empty_approval(self):
        d=domain();bundle=M1BoundBundle(d,[],'a'*64)
        self.assertEqual(bundle.status()['status'],'INCOMPLETE')
        with self.assertRaises(MissingM1Bound):bundle.require('Nbar_il',(7,7),'inverse_inertia')
        with self.assertRaises(MissingM1Bound):bound(values=None)

    def test_bound_metadata_must_match_common_domain_evaluator_and_estimator(self):
        d=domain()
        for override in [{'domain_sha256':'c'*64},{'evaluator_sha256':'c'*64},{'seed':12},{'budget':33}]:
            with self.assertRaises(ValueError):M1BoundBundle(d,[bound(d,**override)],'a'*64)
        with self.assertRaises(ValueError):bound(values=np.full((7,7),np.nan))
        with self.assertRaises(ValueError):bound(evidence_level='CERTIFIED_BY_THIS_UNIT_TEST')

    def test_units_shape_and_mutation_guards_are_enforced(self):
        d=domain();b=M1BoundBundle(d,[bound(d)],'a'*64)
        value=b.require('Nbar_il',(7,7),'inverse_inertia')
        with self.assertRaises(ValueError):value[0,0]=0
        with self.assertRaises(ValueError):b.require('Nbar_il',(7,),'inverse_inertia')
        with self.assertRaises(ValueError):b.require('Nbar_il',(7,7),'wrong_units')
        with self.assertRaises(TypeError):b.records['Nbar_il']=bound(d)
        with self.assertRaises(AttributeError):b.domain=domain(seed=10)

    def test_complete_caller_records_are_not_certification_or_official_approval(self):
        d=domain();b=M1BoundBundle(d,[bound(d)],'a'*64)
        r=b.status(['Nbar_il'])
        self.assertEqual(r['status'],'INPUTS_PRESENT_UNVERIFIED_NO_OFFICIAL_APPROVAL')
        self.assertFalse(r['certified']);self.assertFalse(r['official_stage1_approved'])
        with self.assertRaises(ValueError):bound(name='m1',values=0.)

    def test_diagnostic_timeout_is_unknown_not_infeasible_or_an_applied_torque(self):
        rows=synthetic_box_rows(TAUMAX)
        r=diagnostic_qp(DeliberatelySlowDiagnostic(),np.zeros(7),rows,timeout_s=.05)
        self.assertEqual(r['status'],'DEVELOPMENT_TIMEOUT')
        self.assertTrue(r['production_stop_requested']);self.assertIsNone(r['actually_applied'])
        self.assertIsNone(r['candidate_for_analysis_only']);self.assertFalse(r['strict_raw_pass'])
        self.assertTrue(r['diagnostics']['timeout_is_not_infeasibility'])
        self.assertTrue(r['independent_LP']['feasible'])

    def test_bounded_diagnostic_can_complete_a_real_feasible_QP(self):
        nominal=np.array([1.,-2.,3.,-4.,.1,.2,.3])
        r=diagnostic_qp(self.qp,nominal,synthetic_box_rows(TAUMAX),nominal,timeout_s=15.)
        self.assertTrue(r['normalized_KKT_pass']);self.assertTrue(r['oracle_pass'])
        self.assertTrue(r['strict_raw_pass']);self.assertIsNone(r['actually_applied'])


class Results(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.rows=[]
    def addSuccess(self,test):super().addSuccess(test);self.rows.append({'test':test.id(),'result':'PASS'})
    def addFailure(self,test,err):super().addFailure(test,err);self.rows.append({'test':test.id(),'result':'FAIL','traceback':self._exc_info_to_string(err,test)})
    def addError(self,test,err):super().addError(test,err);self.rows.append({'test':test.id(),'result':'ERROR','traceback':self._exc_info_to_string(err,test)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    r=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(QPBoundsTests))
    with args.report.open('x') as f:
        json.dump(json_values({'scope':'A3_PREPARATION_DEVELOPMENT_CONTRACTS_NOT_OFFICIAL_COMPARISONS','tests_run':r.testsRun,
            'overall_pass':r.wasSuccessful(),'checks':r.rows,'source_sha256':digest(ROOT/'src/panda_closed_loop/a3_qp_bounds.py'),
            'test_sha256':digest(Path(__file__))}),f,indent=2);f.write('\n')
    raise SystemExit(0 if r.wasSuccessful() else 1)
