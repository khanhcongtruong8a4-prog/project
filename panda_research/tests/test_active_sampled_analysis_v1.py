"""Independent analytic moving-face examples, not production mirror tests."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest
import numpy as np
from panda_closed_loop.active_sampled_analysis_v1 import face_expansion,reconstruct_electrical_energy

class AnalysisTests(unittest.TestCase):
    def test_expanding_face_exact_first_order_lower_bound(self):
        # x'=tau, tau<=t, r=2. Any current-point-feasible hold has tau_k<=t_k.
        for n in [20,40,80,160]:
            delta=1/n; integral=sum(k*delta*delta for k in range(n))
            self.assertAlmostEqual(.5-integral,.5*delta,places=13)
        f=face_expansion(np.array([[1.]]),np.array([.3]),np.array([2.]),
                         np.array([[0.]]),np.array([1.]),np.array([0.]),[0],np.array([1.7]))
        self.assertAlmostEqual(f['dsigma'][0],1.)
        self.assertAlmostEqual(f['AB2_defect'][0],-1.)
        self.assertGreater((np.array([[1.]])@(f['sigma']+.001*f['dsigma'])-np.array([.3]))[0],0.)

    def test_rotating_face_derivative_against_closed_form(self):
        t=.23; A=np.array([[np.cos(t),np.sin(t)]]); dA=np.array([[-np.sin(t),np.cos(t)]])
        r=np.array([2.,.3]); b=np.array([.2]); db=np.array([.4]); dr=np.array([.1,-.2])
        lam=A@r-b
        f=face_expansion(A,b,r,dA,db,dr,[0],lam)
        def sigma(s):
            a=np.array([[np.cos(t+s),np.sin(t+s)]]); rr=r+s*dr; bb=b+s*db
            return rr-a.T.reshape(2)*(a@rr-bb)[0]
        derivative=(sigma(1e-5)-sigma(-1e-5))/(2e-5)
        np.testing.assert_allclose(f['dsigma'],derivative,rtol=1e-8,atol=1e-9)
        np.testing.assert_allclose(f['feedback_AB2_defect'],-f['missing_normal'],atol=1e-14)

    def test_fixed_face_ab2_leading_defect_cancels(self):
        f=face_expansion(np.array([[1.,0.]]),np.array([0.]),np.array([2.,.3]),
                         np.zeros((1,2)),np.zeros(1),np.array([.2,.4]),[0],np.array([2.]))
        np.testing.assert_allclose(f['AB2_defect'],0,atol=1e-14)

    def test_rank_deficiency_rejected(self):
        with self.assertRaises(ValueError):
            face_expansion(np.array([[1.],[1.]]),np.zeros(2),np.ones(1),np.zeros((2,1)),np.zeros(2),np.zeros(1),[0,1],np.ones(2))

    def test_shared_bus_nonregenerative_not_per_joint_rectification(self):
        tau=np.array([1.,1.,0.,0.,0.,0.,0.]);v=[2.,-3.,0.,0.,0.,0.,0.]
        samples=[{'qd':v,'tau_applied':tau} for _ in range(5)]
        power=.5*(-.8+np.hypot(-.8,.01))
        step={'applied_tau':tau,'samples':samples,'physical_t0_s':0.,'physical_t1_s':.1,
              'modeled_electrical_energy_increment_J':.1*power}
        result=reconstruct_electrical_energy([step],np.full(7,.1),.01)
        self.assertAlmostEqual(result['sum_J'],.1*power,places=15)
        self.assertEqual(result['max_hold_mismatch_Nm'],0.)
        self.assertLess(result['sum_J'],.001)

    def test_material_derivative_matches_unmodified_model_and_rows(self):
        from panda_dynamics import QMIN,QMAX
        from panda_closed_loop.assembly import build_components
        from panda_closed_loop.reference import ReferenceSample
        from panda_closed_loop.active_sampled_analysis_v1 import SpeedMaterialDerivative
        sys=build_components(); q=(QMIN+QMAX)/2;v=np.array([.1,-.2,.3,-.15,.12,.2,-.1])
        z=sys.observer.initialize(q,v)+.01;varpi=sys.bounds.magnitude*.2
        ref=ReferenceSample(q+.01,v+.02,np.full(7,.03));jerk=np.full(7,.02)
        dh=sys.observer.estimate(q,v,z);r,_=sys.controller.command(q,v,ref,dh)
        direction=SpeedMaterialDerivative(sys)
        data=direction.evaluate(q,v,z,ref,jerk,varpi,np.full(7,-.1),r,np.zeros(7))
        rows=sys.barriers.rows(q,v,dh,varpi);n=np.linalg.norm(rows.G[15:29],axis=1)
        np.testing.assert_allclose(data['r'],r,rtol=1e-12,atol=2e-12)
        np.testing.assert_allclose(data['A'],-rows.G[15:29]/n[:,None],rtol=1e-12,atol=2e-12)
        np.testing.assert_allclose(data['b'],(rows.c[15:29]-1e-8*rows.scales[15:29])/n,rtol=1e-12,atol=2e-12)
        values=[];eps=2e-7
        for sign in [-1,1]:
            x=np.r_[q,v,z]+sign*eps*data['xdot']
            rr=ReferenceSample(ref.q+sign*eps*ref.qd,ref.qd+sign*eps*ref.qdd,ref.qdd+sign*eps*jerk)
            hh=sys.observer.estimate(x[:7],x[7:14],x[14:])
            raw,_=sys.controller.command(x[:7],x[7:14],rr,hh)
            rows2=sys.barriers.rows(x[:7],x[7:14],hh,varpi-sign*eps*.1)
            nn=np.linalg.norm(rows2.G[15:29],axis=1)
            values.append(np.r_[(-rows2.G[15:29]/nn[:,None]).flatten(order='F'),(rows2.c[15:29]-1e-8*rows2.scales[15:29])/nn,raw])
        fd=(values[1]-values[0])/(2*eps)
        ad=np.r_[data['dA'].flatten(order='F'),data['db'],data['dr']]
        np.testing.assert_allclose(ad,fd,rtol=2e-5,atol=2e-5)

if __name__=='__main__': unittest.main(verbosity=2)
