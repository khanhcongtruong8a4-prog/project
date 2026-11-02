"""Exact gain-only amendment and actual-state QP contracts before v4 motion."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
import numpy as np
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.a2_policy_v4 import load_amended_policy,build_amended_system,audit_gain_amendment,AMENDMENT
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_qp_v2 import GuardedHardQP
from panda_closed_loop.trace_archive import read_trace
from panda_closed_loop.logging import json_values
from test_p1_r3 import Results


class PolicyV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Policy.load();cls.amended=load_amended_policy()
        cls.old=build_components();cls.new=build_amended_system()
        for s in [cls.old,cls.new]:s.geometry.function=s.geometry.function.expand()
        folder=ROOT/'runs/a2_extended_v2/E3_0391c5b';cell=json.loads((folder/'cell_0.json').read_text())
        updates=read_trace(folder/cell['a2']['trace']['file'],cell['a2']['trace'])['updates']
        cls.u=updates[max(range(len(updates)),key=lambda i:np.linalg.norm(np.array(updates[i]['candidate_tau'])-updates[i]['u_nom']))]

    def test_only_gain_schema_and_honest_status_change(self):
        a=self.base.raw;b=self.amended.raw
        self.assertEqual(a['gains']['alpha_v'],5.);self.assertEqual(b['gains']['alpha_v'],10.)
        b['gains']['alpha_v']=a['gains']['alpha_v'];b['schema_version']=a['schema_version'];b['status']=a['status']
        self.assertEqual(a,b)

    def test_original_configuration_bytes_unchanged(self):
        from panda_closed_loop.config import POLICY_SHA256
        self.assertEqual(digest(self.base.path),POLICY_SHA256)
        self.assertEqual(self.base.path,self.amended.path)

    def test_physical_parameters_and_all_acceptance_tolerances_identical(self):
        for key in ['physical_parameters','fixed_acceptance_thresholds','disturbance','energy','integration']:
            self.assertEqual(self.base.raw[key],self.amended.raw[key])

    def test_all_other_controller_observer_and_barrier_gains_unchanged(self):
        for key in ['lambdas','kappa','ko','alpha1','alpha2']:
            self.assertEqual(getattr(self.base,key),getattr(self.amended,key))

    def test_actual_G_and_nonvelocity_c_identical(self):
        u=self.u;a=self.old.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi']);b=self.new.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        np.testing.assert_array_equal(a.G,b.G);np.testing.assert_array_equal(a.c[:15],b.c[:15]);np.testing.assert_array_equal(a.c[29:],b.c[29:])
        self.assertEqual(len(b.names),43)

    def test_velocity_c_change_is_exact_declared_design_equation(self):
        u=self.u;a=self.old.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi']);b=self.new.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        expected=5.*np.r_[self.new.barriers.vmax-np.array(u['qd']),self.new.barriers.vmax+np.array(u['qd'])]
        np.testing.assert_allclose(b.c[15:29]-a.c[15:29],expected,atol=5e-13,rtol=0)

    def test_physical_entry_limits_not_relaxed(self):
        u=self.u
        self.assertEqual(json_values(self.old.barriers.entry_conditions(u['q'],u['qd'],u['u_nom'])),
                         json_values(self.new.barriers.entry_conditions(u['q'],u['qd'],u['u_nom'])))

    def test_old_active_request_has_full_new_QP_and_positive_raw_rows(self):
        u=self.u;rr=self.new.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        r=GuardedHardQP(self.new.barriers.taumax).solve(u['u_nom'],rr)
        self.assertFalse(r.stop_requested);self.assertTrue(np.all(rr.slacks(r.applied)>0))
        self.assertLess(np.linalg.norm(r.applied-u['u_nom']),1e-9)

    def test_original_alpha5_negatives_are_shadowed_explicitly(self):
        u=self.u;rr=self.new.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        r=GuardedHardQP(self.new.barriers.taumax).solve(u['u_nom'],rr)
        update={**u,'G':rr.G,'c':rr.c,'candidate_tau':r.applied,'raw_slacks':rr.slacks(r.applied)}
        audit=audit_gain_amendment([update],self.new)
        self.assertTrue(audit['passed']);self.assertGreater(audit['old_alpha5_shadow_negative_count'],0)
        self.assertTrue(audit['old_policy_satisfaction_not_asserted'])

    def test_references_grid_thresholds_and_nominal_sampler_remain_frozen(self):
        old=json.loads((ROOT/'policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json').read_text())
        new=json.loads((ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json').read_text())
        for key in ['references','C4_grid','fixed_acceptance_thresholds','startup_controller','T_pre_s','q_radius_rad',
                    'qd_radius_rad_s','execution_sampling','observer_semantics','seed']:
            self.assertEqual(old[key],new[key])
        self.assertEqual(new['barrier_gain_amendment'],AMENDMENT)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(PolicyV4Tests))
    sources=['src/panda_closed_loop/a2_policy_v4.py','tests/test_a2_policy_v4.py','scripts/a2_extended_v4.py',
             'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json','policy/a2_extended_v4/AMENDED_POLICY_CONFIGURATION.json']
    with args.report.open('x') as f:json.dump({'scope':'PRE_MOTION_GAIN_AMENDMENT_CONTRACTS_NO_V4_MOTION','tests_run':result.testsRun,
          'overall_pass':result.wasSuccessful(),'checks':result.rows,'source_hashes':{n:digest(ROOT/n) for n in sources}},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
