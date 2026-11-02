from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
import numpy as np
from panda_closed_loop.projected_feedback_ab2_v1 import ProjectedFeedbackAB2QP
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.qp import QPResult
from panda_closed_loop.config import digest
from test_p1_r3 import Results

def upper(b):
    G=np.zeros((1,7));G[0,0]=-1.;return AffineRows(G,[b],[1.],('upper',),('test',))

class CandidateContracts(unittest.TestCase):
    def test_inactive_affine_request_recovers_original_AB2(self):
        qp=ProjectedFeedbackAB2QP([87]*4+[12]*3)
        for k in range(4):
            r=np.ones(7)*(1+.01*k);q=qp.solve(r,upper(10.))
            self.assertFalse(q.stop_requested)
            np.testing.assert_allclose(q.applied,r+(0 if k==0 else .005),atol=1e-10,rtol=0)
    def test_moving_active_face_rejects_unsafe_unprojected_AB2(self):
        qp=ProjectedFeedbackAB2QP([87]*4+[12]*3);r=np.zeros(7);r[0]=2.
        a=qp.solve(r,upper(.2));b=qp.solve(r,upper(.3));self.assertFalse(a.stop_requested or b.stop_requested)
        sigma=np.array(b.diagnostics['current_filtered_feedback_Nm']);prev=np.array(b.diagnostics['previous_filtered_feedback_Nm'])
        self.assertLess(upper(.3).slacks(sigma+.5*(sigma-prev))[0],0.)
        self.assertGreaterEqual(upper(.3).slacks(b.applied)[0],0.)
        self.assertEqual(b.diagnostics['combined_kernel_solves'],2)
    def test_infeasible_raw_query_never_advances_history_or_returns_torque(self):
        G=np.zeros((2,7));G[:,0]=[1,-1];rows=AffineRows(G,[-1.,0.],[1.,1.],('lower','upper'),('test','test'))
        qp=ProjectedFeedbackAB2QP([87]*4+[12]*3);a=qp.solve(np.zeros(7),rows)
        self.assertTrue(a.stop_requested);self.assertIsNone(a.applied);self.assertIsNone(qp.previous);self.assertEqual(qp.index,0)
    def test_failed_final_query_cannot_fallback_to_verified_raw_query(self):
        qp=ProjectedFeedbackAB2QP([87]*4+[12]*3);self.assertFalse(qp.solve(np.zeros(7),upper(1.)).stop_requested)
        original=qp.kernel.solve;calls=[];previous=qp.previous.copy()
        def fail_second(nom,rows):
            calls.append(1)
            return original(nom,rows) if len(calls)==1 else QPResult(None,'INJECTED_FINAL_FAILURE',True,{})
        qp.kernel.solve=fail_second;q=qp.solve(np.ones(7)*.1,upper(1.))
        self.assertTrue(q.stop_requested);self.assertIsNone(q.applied);np.testing.assert_array_equal(qp.previous,previous)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(CandidateContracts))
    data={'overall_pass':result.wasSuccessful(),'tests_run':result.testsRun,'checks':result.rows,
        'source_hashes':{n:digest(ROOT/n) for n in ['src/panda_closed_loop/projected_feedback_ab2_v1.py','tests/test_projected_feedback_v1.py']},'Level1':False}
    with a.report.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
