"""Completion optimality/unknown handling tests, independent of saved witnesses."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest
from time import perf_counter
import numpy as np
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.polynomial_hold_v2_3 import complete,CompletionService,VALIDATION_NODES,Stop,predict,polynomial_peak

class Contracts(unittest.TestCase):
    def test_gauss_constant_acceleration_and_quadratic_dense_adapter(self):
        from types import SimpleNamespace as NS
        from panda_closed_loop.polynomial_hold_v2_3 import integrate
        from panda_closed_loop.stepper import ExecutionState
        observer=NS(estimate=lambda q,v,z:np.zeros(7),derivative=lambda q,v,z,tau:np.zeros(7))
        model=NS(evaluate=lambda q,v:{'M':np.eye(7),'C':np.zeros((7,7)),'g':np.zeros(7),'F':np.zeros(7)})
        barriers=NS(qmin=np.full(7,-100.),qmax=np.full(7,100.),vmax=np.full(7,100.),entry_conditions=lambda q,v,tau:{'passed':True})
        system=NS(observer=observer,model=model,barriers=barriers,policy=NS(raw={'energy':{'k_r':[0]*7,'nonregenerative_smoothing':{'epsilon_W':1.}}}))
        state=ExecutionState(np.zeros(7),np.zeros(7),np.zeros(7),0.)
        co=np.zeros((4,7));co[0]=1.;hold={'t0':0.,'delta':1.,'coefficients':co}
        final,step=integrate(system,state,hold,.01,.01,NS(value=lambda t:np.ones(7)),lambda t:np.zeros(7))
        np.testing.assert_allclose(final.q,.00005,atol=1e-16)
        np.testing.assert_allclose(final.qd,.01,atol=1e-16)
        self.assertTrue(all(step['checks'].values()))

    def test_full_polytope_kkt(self):
        # Constant term is feasible. The cubic seed violates interior/end rows.
        base=np.zeros((4,7));base[1,0]=-2.
        G=np.zeros((1,7));G[0,0]=1.
        rows=[AffineRows(G,np.array([1.]),np.ones(1),('lower',),('Nm',)) for _ in VALIDATION_NODES]
        with CompletionService() as service:p,a=complete(base,rows,service,perf_counter()+15.)
        self.assertTrue(a['accepted']);self.assertEqual(a['all_rows_verified'],9)
        C,b,x,d=[np.array(a[k]) for k in ['C','b','x','dual_full']]
        self.assertLessEqual(max(0.,np.max(C@x-b)),1e-9)
        self.assertLessEqual(np.max(abs(x+C.T@d)),1e-9)
        self.assertLessEqual(np.max(abs(d*(C@x-b))),1e-9)
        for s,row in zip(VALIDATION_NODES,rows):self.assertTrue(np.all(row.slacks(np.polynomial.polynomial.polyval(s,p))>=0))
    def test_original_row_scaling_resolution(self):
        base=np.zeros((4,7));base[1,0]=-2e-9
        G=np.zeros((1,7));G[0,0]=1.
        rows=[AffineRows(G,np.array([1e-8]),np.ones(1),('near_guard',),('Nm',)) for _ in VALIDATION_NODES]
        with CompletionService() as service:p,a=complete(base,rows,service,perf_counter()+15.)
        self.assertTrue(a['accepted'])
        self.assertLessEqual(a['residuals']['original_scale_guarded_violation'],1e-9)
    def test_computed_support_and_full_kkt(self):
        from panda_closed_loop.polynomial_hold_v2_3 import support_kkt
        C=np.array([[1.,0.],[0.,1.],[1.,1.],[-1.,0.]])
        b=np.array([-1.,-2.,-2.,5.])
        x,d,h=support_kkt(C,b,perf_counter()+15.)
        np.testing.assert_allclose(x,[-1.,-2.],atol=1e-12)
        self.assertLessEqual(np.max(C@x-b),1e-12)
        self.assertLessEqual(np.max(abs(x+C.T@d)),1e-12)
        self.assertTrue(np.all(d>=0))
    def test_inconsistent_constant_stops(self):
        G=np.zeros((1,7));rows=[AffineRows(G,np.array([-1.]),np.ones(1),('impossible',),('Nm',)) for _ in VALIDATION_NODES]
        with CompletionService() as service:
            with self.assertRaises(Stop):complete(np.zeros((4,7)),rows,service,perf_counter()+15.)
    def test_expired_query_stops(self):
        G=np.zeros((1,7));rows=[AffineRows(G,np.array([1.]),np.ones(1),('constant',),('Nm',)) for _ in VALIDATION_NODES]
        with self.assertRaises(Stop):complete(np.zeros((4,7)),rows,None,perf_counter()-1.)
    def test_measured_cubic_predictor(self):
        history=[(t,np.full(21,t**3-2*t+5)) for t in [-3.,-2.,-1.,0.]]
        np.testing.assert_allclose(predict(history,.5),.5**3-1+5,atol=1e-13)
        with self.assertRaises(Stop):predict(history[:3],.5)
    def test_interior_polynomial_peak(self):
        p=np.zeros((4,7));p[1,0]=4.;p[2,0]=-4.
        self.assertAlmostEqual(polynomial_peak(p),1.,places=13)
if __name__=='__main__':unittest.main(verbosity=2)
