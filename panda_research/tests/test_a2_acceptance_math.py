"""Local algebraic checks for the unchanged AB2 / gain10 / guarded-QP design."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
from itertools import product
import numpy as np
from scipy.optimize import linprog
from panda_closed_loop.a2_acceptance import exact_qp_certificate,scientific_digest
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.a2_qp_v2 import BoundedGuardedQP
from panda_closed_loop.assembly import build_components
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.p1_r4 import AB2TorqueController
from test_p1_r3 import Results

EVIDENCE={}


class RawRequest:
    def command(self,q,v,reference,dhat):return np.asarray(q).copy(),{}


def command(controller,value):return controller.command(np.full(7,value),np.zeros(7),None,np.zeros(7))[0]


class AcceptanceMath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new=build_amended_system();cls.old=build_components()
        for s in [cls.new,cls.old]:s.geometry.function=s.geometry.function.expand()
        cls.cell=json.loads((ROOT/'runs/a2_extended_v4/E3_c02f908/cell_0.json').read_text())
        cls.u=cls.cell['endpoint']['QP']

    def test_AB2_affine_interval_average_after_bootstrap(self):
        for dt in [.001,.0005]:
            control=AB2TorqueController(RawRequest())
            for k in range(5):
                value=command(control,1+3*k*dt)
                if k:np.testing.assert_allclose(value,1+3*(k+.5)*dt,atol=5e-16,rtol=0)

    def test_AB2_quadratic_mean_error_has_minus_five_twelfths_coefficient(self):
        dt=.02;t=.3;control=AB2TorqueController(RawRequest())
        command(control,(t-dt)**2);actual=command(control,t*t)
        exact_average=((t+dt)**3-t**3)/(3*dt)
        np.testing.assert_allclose(actual-exact_average,-5/6*dt**2,atol=3e-16,rtol=0)

    def test_bootstrap_impulse_error_scales_as_Delta_squared(self):
        values=[]
        for dt in [.02,.01]:
            control=AB2TorqueController(RawRequest());u=command(control,2.)
            values.append(float(dt*u[0]-(2*dt+3/2*dt**2)))
        self.assertAlmostEqual(values[0]/values[1],4.,places=12)

    def test_observer_derivative_uses_exact_applied_torque_with_correct_sign(self):
        u=self.u;s=self.new;before=s.observer.derivative(u['q'],u['qd'],u['z'],np.zeros(7))
        delta=np.arange(1,8)*.01;after=s.observer.derivative(u['q'],u['qd'],u['z'],delta)
        np.testing.assert_allclose(after-before,-np.asarray(s.policy.ko)*delta,atol=5e-12,rtol=0)

    def test_gain10_speed_rows_match_direct_velocity_barrier_derivatives(self):
        s=self.new;u=self.u;v=np.asarray(u['qd']);e=s.model.evaluate(u['q'],v)
        N=np.linalg.solve(e['M'],np.eye(7));tau=np.asarray(u['candidate_tau']);bias=np.asarray(u['dhat'])-e['C']@v-e['g']-e['F']
        accel=N@(tau+bias);margin=abs(N)@np.asarray(u['varpi'])
        direct=np.r_[-accel+10*(s.barriers.vmax-v)-margin,accel+10*(s.barriers.vmax+v)-margin]
        actual=s.barriers.rows(u['q'],v,u['dhat'],u['varpi']).slacks(tau)[15:29]
        np.testing.assert_allclose(actual,direct,atol=2e-12,rtol=0)

    def test_box_error_bound_equals_minimum_over_all_128_current_point_corners(self):
        s=self.new;u=self.u;v=np.asarray(u['qd']);e=s.model.evaluate(u['q'],v)
        N=np.linalg.solve(e['M'],np.eye(7));vp=np.asarray(u['varpi'])
        corners=np.array(list(product([-1.,1.],repeat=7)))*vp
        lower=np.min(-N@corners.T,axis=1)
        np.testing.assert_allclose(lower,-abs(N)@vp,atol=2e-14,rtol=0)

    def test_gain_change_preserves_model_and_every_other_gain(self):
        self.assertEqual(self.new.policy.alpha_v,10.);self.assertEqual(self.old.policy.alpha_v,5.)
        for key in ['ko','lambdas','kappa','alpha1','alpha2']:
            self.assertEqual(getattr(self.new.policy,key),getattr(self.old.policy,key))
        q,v=self.u['q'],self.u['qd']
        for key in ['M','C','g','F']:
            np.testing.assert_array_equal(self.new.model.evaluate(q,v)[key],self.old.model.evaluate(q,v)[key])

    def test_guarded_QP_is_unweighted_physical_torque_projection_with_mixed_limits(self):
        G=np.zeros((1,7));G[0,[0,4]]=-1.
        rows=AffineRows(G,[1.],[1.],('coupled',),('test',));nom=np.zeros(7);nom[[0,4]]=2.
        with BoundedGuardedQP([87]*4+[12]*3) as qp:r=qp.solve(nom,rows)
        self.assertFalse(r.stop_requested)
        np.testing.assert_allclose(r.applied[[0,4]],(1.-1e-8)/2,atol=1e-8,rtol=0)

    def test_exact_recorded_QP_optimum_on_preserved_real_43_row_active_fixture(self):
        p=ROOT/'reports/a2_extended_v1/qp_bounds_evidence/run_v2/fixture_09.json';f=json.loads(p.read_text())
        rows=AffineRows(f['G'],f['c'],f['scales'],tuple(f['row_names']),tuple(f['row_units']))
        cert=exact_qp_certificate(f['nominal'],rows,[rows.names.index('v_lower_3')])
        self.assertTrue(cert['passed'])
        with BoundedGuardedQP([87]*4+[12]*3) as qp:r=qp.solve(f['nominal'],rows)
        EVIDENCE['preserved_real_43']={'input_sha256':digest(p),'certificate':cert,'query':json_values(r.__dict__),'torque_actuated':False}
        self.assertFalse(r.stop_requested)
        self.assertLessEqual(np.max(abs(r.applied/87.-cert['unique_optimum_y_float_display_only'])),1e-9)

    def test_exact_recorded_QP_optimum_on_active_v4_current_state_face(self):
        u=self.u;rows=self.new.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi']);j=rows.names.index('v_lower_3')
        den=87*np.linalg.norm(rows.G,axis=1);C=-87*rows.G/den[:,None];b=(rows.c-1e-8*rows.scales)/den
        other=[i for i in range(43) if i!=j]
        lp=linprog(np.r_[np.zeros(7),-1.],A_ub=np.c_[C[other],np.ones(42)],b_ub=b[other],
                   A_eq=np.r_[C[j],0.][None,:],b_eq=[b[j]],bounds=[(None,None)]*7+[(0,None)],method='highs')
        self.assertTrue(lp.success);self.assertGreater(lp.x[-1],1e-6)
        nominal=87*(lp.x[:7]+C[j]);cert=exact_qp_certificate(nominal,rows,[j])
        self.assertTrue(cert['passed'])
        with BoundedGuardedQP(self.new.barriers.taumax) as qp:r=qp.solve(nominal,rows)
        self.assertFalse(r.stop_requested);self.assertTrue(np.all(rows.slacks(r.applied)>=0))
        self.assertLessEqual(np.max(abs(r.applied/87.-cert['unique_optimum_y_float_display_only'])),1e-9)
        EVIDENCE['actual_v4_active_43']={'state':{k:u[k] for k in ['q','qd','dhat','varpi']},'G':rows.G.tolist(),'c':rows.c.tolist(),
            'scales':rows.scales.tolist(),'nominal':nominal.tolist(),'LP_eta':float(lp.x[-1]),'certificate':cert,
            'query':json_values(r.__dict__),'torque_actuated':False}

    def test_guard_can_remove_boundary_only_feasibility_and_must_stop(self):
        G=np.zeros((2,7));G[0,0]=1.;G[1,0]=-1.
        rows=AffineRows(G,[0.,0.],[1.,1.],('lower','upper'),('test','test'))
        with BoundedGuardedQP([87]*4+[12]*3) as qp:r=qp.solve(np.zeros(7),rows)
        self.assertIsNone(r.applied);self.assertTrue(r.stop_requested)

    def test_replay_digest_ignores_only_wall_time_and_detects_a_physical_change(self):
        a={'q':[1.],'solve_runtime_s':.01,'nested':{'tau':2.}}
        b={'q':[1.],'solve_runtime_s':3.,'nested':{'tau':2.}}
        self.assertEqual(scientific_digest(a),scientific_digest(b))
        b['nested']['tau']=2.0000000001
        self.assertNotEqual(scientific_digest(a),scientific_digest(b))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceMath))
    sources=['src/panda_closed_loop/a2_acceptance.py','tests/test_a2_acceptance_math.py',
             'src/panda_closed_loop/a2_qp_v2.py','src/panda_closed_loop/a2_policy_v4.py','src/panda_closed_loop/p1_r4.py']
    with args.report.open('x') as f:
        json.dump({'scope':'AUTOMATED_LOCAL_FRAMEWORK_AND_EXACT_RECORDED_QP_CHECKS; NOT_EXTERNAL_HUMAN_REVIEW_OR_LEVEL1',
            'tests_run':result.testsRun,'overall_pass':result.wasSuccessful(),'checks':result.rows,
            'source_hashes':{n:digest(ROOT/n) for n in sources},'active_QP_evidence':EVIDENCE,
            'model_or_experimental_parameter_changes':False,'external_signatures':None},f,indent=2,allow_nan=False);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
