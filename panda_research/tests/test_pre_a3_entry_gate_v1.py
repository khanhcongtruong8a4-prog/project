"""Entry-gate contract fixtures; synthetic variants never authorize a plan."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,copy,json,unittest
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.m1_common_domain_v1 import NumericalM1Registry
from panda_closed_loop.pre_a3_entry_gate_v1 import require_planner_entry,PlannerEntryBlocked
from panda_closed_loop.config import digest
from test_p1_r3 import Results

class EntryGateContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system=build_amended_system()
        cls.record=json.loads((ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_0.json').read_text())['endpoint']['QP']
        cls.table=json.loads((ROOT/'reports/pre_a3_blockers_v1/m1_registry/M1_REGISTRY.json').read_text())
    def test_actual_start_stops_for_mathematical_pair_infeasibility(self):
        with self.assertRaises(PlannerEntryBlocked) as c:require_planner_entry(self.system,self.record,NumericalM1Registry(self.table))
        self.assertEqual(c.exception.reason,'FULL_INITIAL_SPEED_PAIR_CONSTRAINTS_INFEASIBLE')
    def test_synthetic_zero_varpi_entry_does_not_hide_failed_finite_audit(self):
        fixture=copy.deepcopy(self.record);fixture['varpi']=[0.]*7
        with self.assertRaises(PlannerEntryBlocked) as c:require_planner_entry(self.system,fixture,NumericalM1Registry(self.table))
        self.assertEqual(c.exception.reason,'COMMON_DOMAIN_NUMERICAL_BOUND_AUDIT_FAILED')
    def fixture(self):
        # Explicit unit fixture only: no on-disk registry or actual bound changes.
        record=copy.deepcopy(self.record);record['varpi']=[0.]*7
        document=copy.deepcopy(self.table);document['scope']='SYNTHETIC_GATE_CONTRACT_ONLY'
        for row in document['heldout_exceedances'].values():row['component_count']=0
        return record,NumericalM1Registry(document)
    def test_synthetic_finite_gate_pass_is_not_level1_or_full_A3(self):
        record,registry=self.fixture();answer=require_planner_entry(self.system,record,registry)
        self.assertTrue(answer['finite_numerical_bound_audit_pass']);self.assertFalse(answer['certified'])
        self.assertGreater(sum(d['component_count'] for d in self.table['heldout_exceedances'].values()),0)
    def test_certified_use_requires_a_separate_qualified_bound_suite(self):
        record,registry=self.fixture()
        with self.assertRaises(PlannerEntryBlocked) as c:require_planner_entry(self.system,record,registry,require_certified=True)
        self.assertEqual(c.exception.reason,'CERTIFIED_DOMAIN_BOUNDS_UNAVAILABLE')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(EntryGateContracts))
    names=['src/panda_closed_loop/pre_a3_entry_gate_v1.py','tests/test_pre_a3_entry_gate_v1.py']
    with a.report.open('x') as f:json.dump({'overall_pass':result.wasSuccessful(),'tests_run':result.testsRun,'checks':result.rows,
        'source_hashes':{n:digest(ROOT/n) for n in names},'synthetic_unit_fixtures_not_experimental_evidence':True,
        'original_registry_or_experimental_bound_modified':False,'official_A3_executed':False,'Level1':False},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
