"""Pre-motion qualification of causal QP row sampling and final raw gating."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
import numpy as np
from panda_closed_loop.a2_qp_v3 import IntervalHardQP,BoundedIntervalQP,interval_rows,audit_interval_numerics,SAMPLING_QP_POLICY
from panda_closed_loop.a2_qp_v2 import GuardedHardQP
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values
from test_p1_r3 import Results


def face(c):
    g=np.zeros((1,7));g[0,0]=-1.
    return AffineRows(g,[c],[1.],('moving_face',),('test units',))


class IntervalQPTests(unittest.TestCase):
    def test_bootstrap_is_actual_tightened_43_or_fixture_rows(self):
        rr=face(1.);actual=interval_rows(rr,None)
        np.testing.assert_array_equal(actual.G,rr.G)
        np.testing.assert_array_equal(actual.c,rr.c-.1*rr.scales)

    def test_moving_affine_face_exact_causal_interval_average(self):
        for dt in [.001,.0005]:
            q=IntervalHardQP(np.full(7,87.));q.solve(np.full(7,2.),face(1.))
            r=q.solve(np.full(7,2.),face(1.+dt))
            self.assertFalse(r.stop_requested)
            self.assertAlmostEqual(r.applied[0],1.+1.5*dt-.1-1e-8,places=9)
            self.assertGreater(min(r.diagnostics['raw_slacks']),0.)

    def test_constant_rows_equal_fixed_tightening_objective(self):
        rr=face(1.);q=IntervalHardQP(np.full(7,87.))
        a=q.solve(np.full(7,2.),rr);b=q.solve(np.full(7,2.),rr)
        c=GuardedHardQP(np.full(7,87.)).solve(np.full(7,2.),interval_rows(rr,None))
        np.testing.assert_array_equal(a.applied,b.applied);np.testing.assert_array_equal(a.applied,c.applied)

    def test_final_current_hard_row_violation_stops_not_repaired(self):
        nom=np.r_[10.,np.zeros(6)]
        q=IntervalHardQP(np.full(7,87.));q.solve(nom,face(-1.))
        r=q.solve(nom,face(.1))
        self.assertTrue(r.stop_requested);self.assertIsNone(r.applied)
        self.assertEqual(r.status,'CURRENT_RAW_ROW_REJECTION')
        self.assertGreater(r.diagnostics['negative_raw_row_count'],0)
        self.assertFalse(r.diagnostics['post_solve_repair'])

    def test_separate_actual_QP_and_current_raw_rows_retained(self):
        q=IntervalHardQP(np.full(7,87.));q.solve(np.full(7,2.),face(1.))
        r=q.solve(np.full(7,2.),face(1.01));d=r.diagnostics
        self.assertNotEqual(d['raw_slacks'],d['actual_QP_diagnostics']['raw_slacks'])
        self.assertAlmostEqual(d['actual_QP_rows']['c'][0],.915)
        self.assertEqual(d['sampling_QP_index'],1)

    def test_read_only_audit_reconstructs_histories_rows_and_duals(self):
        q=IntervalHardQP(np.full(7,87.));updates=[]
        for i,rr in enumerate([face(1.),face(1.001),face(1.002)]):
            nom=np.full(7,2.);r=q.solve(nom,rr)
            updates.append(json_values({'G':rr.G,'c':rr.c,'row_scales':rr.scales,'row_names':rr.names,
                'row_units':rr.units,'u_nom':nom,'candidate_tau':r.applied,'raw_slacks':rr.slacks(r.applied),
                'diagnostics':r.diagnostics,'torque_applied':True,'tracking_errors':{'sampling_update_index':i}}))
        a=audit_interval_numerics(updates,np.full(7,87.));self.assertTrue(a['passed'])
        updates[1]['diagnostics']['previous_current_rows']['c'][0]+=.01
        self.assertFalse(audit_interval_numerics(updates,np.full(7,87.))['passed'])

    def test_worker_history_matches_same_two_queries_direct(self):
        q=IntervalHardQP(np.full(7,87.));nom=np.full(7,2.)
        with BoundedIntervalQP(np.full(7,87.)) as worker:
            for rr in [face(1.),face(1.001)]:
                a=q.solve(nom,rr);b=worker.solve(nom,rr)
                np.testing.assert_array_equal(a.applied,b.applied)
                self.assertEqual(a.diagnostics,b.diagnostics)

    def test_separate_cells_have_fresh_history(self):
        a=IntervalHardQP(np.full(7,87.));a.solve(np.full(7,2.),face(1.))
        b=IntervalHardQP(np.full(7,87.));r=b.solve(np.full(7,2.),face(1.01))
        self.assertIsNone(r.diagnostics['previous_current_rows']);self.assertEqual(r.diagnostics['sampling_QP_index'],0)

    def test_changed_policy_or_row_identity_is_rejected(self):
        d=dict(SAMPLING_QP_POLICY);d['fixed_inward_reserve_original_row_scale']=.01
        with self.assertRaises(ValueError):BoundedIntervalQP(np.ones(7),d)
        rr=face(1.);other=AffineRows(rr.G,rr.c,rr.scales,('different',),rr.units)
        with self.assertRaises(ValueError):interval_rows(rr,other)

    def test_immutable_reference_gain_grid_threshold_and_AB2_nominal(self):
        original=json.loads((ROOT/'policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json').read_text())
        new=json.loads((ROOT/'policy/a2_extended_v3/A2_EXTENDED_PREDECLARATION.json').read_text())
        for key in ['references','C4_grid','fixed_acceptance_thresholds','startup_controller','T_pre_s',
                    'q_radius_rad','qd_radius_rad_s','execution_sampling','observer_semantics','seed']:
            self.assertEqual(original[key],new[key])
        self.assertEqual(new['digital_QP_sampling_amendment'],SAMPLING_QP_POLICY)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(IntervalQPTests))
    sources=['src/panda_closed_loop/a2_qp_v3.py','tests/test_a2_qp_v3.py','scripts/a2_extended_v3.py',
             'policy/a2_extended_v3/A2_EXTENDED_PREDECLARATION.json']
    with args.report.open('x') as f:
        json.dump({'scope':'PRE_MOTION_CAUSAL_INTERVAL_QP_CONTRACTS_NO_PANDA_MOTION','tests_run':result.testsRun,
            'overall_pass':result.wasSuccessful(),'checks':result.rows,'source_hashes':{n:digest(ROOT/n) for n in sources}},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
