"""Completion optimality/unknown handling tests, independent of saved witnesses."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest
from time import perf_counter
import numpy as np
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.polynomial_hold_v2 import complete,CompletionService,VALIDATION_NODES,Stop,predict,polynomial_peak

class Contracts(unittest.TestCase):
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
