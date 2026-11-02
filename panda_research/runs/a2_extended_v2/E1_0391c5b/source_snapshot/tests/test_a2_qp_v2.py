"""Analytic, infeasible, scaling and actual-matrix qualification before motion."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
from unittest.mock import Mock
import numpy as np
from panda_closed_loop.a2_qp_v2 import GuardedHardQP,BoundedGuardedQP,NUMERICAL_POLICY
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from test_p1_r3 import Results


def rows(G,c,scales=None):
    G=np.asarray(G,dtype=float);n=len(G)
    return AffineRows(G,c,np.ones(n) if scales is None else scales,
                      tuple(f'fixture_{i}' for i in range(n)),tuple('test units' for _ in range(n)))


def box():return rows(np.vstack([-np.eye(7),np.eye(7)]),np.ones(14))


class NumericalQPTests(unittest.TestCase):
    def setUp(self):self.qp=GuardedHardQP(np.ones(7))

    def test_interior_objective_minimizer(self):
        nom=np.linspace(-.3,.3,7);r=self.qp.solve(nom,box())
        self.assertFalse(r.stop_requested)
        np.testing.assert_allclose(r.applied,nom,atol=2e-9,rtol=0)

    def test_upper_active_analytic_solution_and_strict_sign(self):
        r=self.qp.solve(np.full(7,2.),box())
        self.assertFalse(r.stop_requested)
        np.testing.assert_allclose(r.applied,np.full(7,1.-1e-8),atol=2e-10,rtol=0)
        self.assertGreater(min(r.diagnostics['raw_slacks']),0.)

    def test_lower_active_analytic_solution_and_strict_sign(self):
        r=self.qp.solve(np.full(7,-2.),box())
        self.assertFalse(r.stop_requested)
        np.testing.assert_allclose(r.applied,np.full(7,-1.+1e-8),atol=2e-10,rtol=0)
        self.assertGreater(min(r.diagnostics['raw_slacks']),0.)

    def test_coupled_active_face_projection(self):
        g=np.zeros((1,7));g[0,:2]=-1
        rr=rows(g,[1.]);r=GuardedHardQP(np.full(7,87.)).solve(np.r_[2.,2.,np.zeros(5)],rr)
        self.assertFalse(r.stop_requested)
        np.testing.assert_allclose(r.applied[:2],np.full(2,(1.-1e-8)/2),atol=1e-9,rtol=0)
        self.assertGreater(rr.slacks(r.applied)[0],0.)

    def test_infeasible_rows_stop_without_candidate(self):
        g=np.zeros((2,7));g[0,0]=1.;g[1,0]=-1.
        r=self.qp.solve(np.zeros(7),rows(g,[-1.,0.]))
        self.assertTrue(r.stop_requested);self.assertIsNone(r.applied)

    def test_zero_normal_infeasible_row_stops(self):
        r=self.qp.solve(np.zeros(7),rows(np.zeros((1,7)),[-1.]))
        self.assertTrue(r.stop_requested);self.assertIsNone(r.applied)

    def test_equivalent_positive_row_scaling(self):
        g=np.vstack([-np.eye(7),np.eye(7)]);rr=box()
        # Integer powers preserve the represented rows exactly; noninteger
        # powers had changed the rounded coefficients by one ulp (v1 log).
        scale=np.ldexp(np.ones(14),np.linspace(-20,20,14).astype(int))
        transformed=rows(g*scale[:,None],scale,scale)
        a=self.qp.solve(np.full(7,2.),rr);b=self.qp.solve(np.full(7,2.),transformed)
        self.assertFalse(a.stop_requested or b.stop_requested)
        np.testing.assert_array_equal(a.applied,b.applied)

    def test_original_T29_gradient_independently_recomputed(self):
        rr=box();nom=np.full(7,2.);r=self.qp.solve(nom,rr)
        dual=np.array(r.diagnostics['dual_original'])
        gradient=(r.applied-nom)/87.**2+(-rr.G/rr.scales[:,None]).T@dual
        self.assertLessEqual(np.max(abs(gradient)),1e-9)
        self.assertLessEqual(r.diagnostics['normalized_primal'],1e-9)

    def test_cold_repeat_is_exact(self):
        a=self.qp.solve(np.full(7,2.),box());b=self.qp.solve(np.full(7,2.),box())
        np.testing.assert_array_equal(a.applied,b.applied)
        self.assertEqual(a.diagnostics,b.diagnostics)

    def test_actual_five_failed_matrix_regressions(self):
        files=sorted((ROOT/'reports/a2_extended_v1/actual_extended_qp_diagnostics').glob('E*_cell_*.json'))
        self.assertEqual(len(files),5)
        for p in files:
            with self.subTest(matrix=p.stem):
                before=digest(p);u=json.loads(p.read_text())['last_attempted_update']
                rr=AffineRows(u['G'],u['c'],u['row_scales'],u['row_names'],u['row_units'])
                r=GuardedHardQP([87]*4+[12]*3).solve(u['u_nom'],rr)
                self.assertFalse(r.stop_requested)
                self.assertTrue(np.all(rr.slacks(r.applied)>=0))
                self.assertLessEqual(r.diagnostics['scaled_stationarity'],1e-9)
                self.assertEqual(digest(p),before)

    def test_worker_matches_direct_solution_and_diagnostics(self):
        rr=box();nom=np.full(7,2.)
        direct=self.qp.solve(nom,rr)
        with BoundedGuardedQP(np.ones(7)) as worker:r=worker.solve(nom,rr)
        np.testing.assert_array_equal(r.applied,direct.applied)
        self.assertEqual(r.diagnostics,direct.diagnostics)

    def test_timeout_is_unknown_with_no_actuation(self):
        service=BoundedGuardedQP(np.ones(7));service.process=Mock();service.connection=Mock()
        service.connection.poll.return_value=False
        result=service.solve(np.zeros(7),box())
        self.assertTrue(result.stop_requested);self.assertIsNone(result.applied)
        self.assertEqual(result.diagnostics['classification'],'UNKNOWN_NOT_INFEASIBLE')

    def test_settings_are_frozen_no_retry_or_projection(self):
        altered=dict(NUMERICAL_POLICY);altered['eps_abs']=1e-9
        with self.assertRaises(ValueError):GuardedHardQP(np.ones(7),altered)
        with self.assertRaises(ValueError):BoundedGuardedQP(np.ones(7),timeout_s=.01)
        self.assertFalse(NUMERICAL_POLICY['retry']);self.assertFalse(NUMERICAL_POLICY['post_QP_projection'])

    def test_new_motion_definitions_and_thresholds_equal_v1(self):
        old=json.loads((ROOT/'policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json').read_text())
        new=json.loads((ROOT/'policy/a2_extended_v2/A2_EXTENDED_PREDECLARATION.json').read_text())
        for key in ['references','C4_grid','fixed_acceptance_thresholds','startup_controller','T_pre_s',
                    'q_radius_rad','qd_radius_rad_s','execution_sampling','observer_semantics','seed']:
            self.assertEqual(new[key],old[key])
        self.assertEqual(new['numerical_QP_amendment'],NUMERICAL_POLICY)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(NumericalQPTests))
    sources=['src/panda_closed_loop/a2_qp_v2.py','tests/test_a2_qp_v2.py','scripts/a2_extended_v2.py',
             'policy/a2_extended_v2/A2_EXTENDED_PREDECLARATION.json']
    with args.report.open('x') as f:
        json.dump({'scope':'PRE_MOTION_ANALYTIC_AND_RETAINED_MATRIX_QUALIFICATION_NOT_PANDA_MOTION',
                   'tests_run':result.testsRun,'overall_pass':result.wasSuccessful(),'checks':result.rows,
                   'source_hashes':{n:digest(ROOT/n) for n in sources}},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
