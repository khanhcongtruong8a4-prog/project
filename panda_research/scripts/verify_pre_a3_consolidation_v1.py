"""Verify preserved A2 inputs, public solver API and technical planner stop."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,hashlib
from panda_closed_loop.guarded_qp_final_v1 import verify_release,GuardedHardQP
from panda_closed_loop.a2_qp_reliable_v1_1 import GuardedHardQP as QualifiedQP
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.m1_common_domain_v1 import NumericalM1Registry
from panda_closed_loop.pre_a3_entry_gate_v1 import require_planner_entry,PlannerEntryBlocked

def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    source=json.loads((ROOT/'policy/pre_a3_blockers_v1/PROTECTED_INPUTS.json').read_text())
    changed=[n for n,h in source['protected_source_sha256'].items() if sha(ROOT.parent/n)!=h]
    release=verify_release();registry=NumericalM1Registry(json.loads((ROOT/'reports/pre_a3_blockers_v1/m1_registry/M1_REGISTRY.json').read_text()))
    system=build_amended_system();endpoint=json.loads((ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_0.json').read_text())['endpoint']['QP']
    blocked=False;reason=None
    try:require_planner_entry(system,endpoint,registry)
    except PlannerEntryBlocked as error:blocked=True;reason=error.reason
    baseline=json.loads((ROOT/'reports/pre_a3_blockers_v1/UNCHANGED_A2_REAUDIT.json').read_text())
    T27=json.loads((ROOT/'reports/pre_a3_blockers_v1/t27_regression/SUMMARY.json').read_text())
    checks={'all_previous_files_preserved':not changed,'public_QP_is_qualified_implementation':GuardedHardQP is QualifiedQP,
        'all_19_original_selected_A2_results_reaudited_unchanged':baseline['decisions']['A2_SELECTED_FROZEN_SCOPE']=='GO',
        'strict_T27_39_passed':T27['overall_pass'] and T27['fixture_count']==39,
        'planner_entry_fail_closed_for_actual_matched_start':blocked and reason=='FULL_INITIAL_SPEED_PAIR_CONSTRAINTS_INFEASIBLE'}
    data={'passed':all(checks.values()),'checks':checks,'preserved_files':len(source['protected_source_sha256']),'changed_files':changed,
        'solver_release':release,'planner_stop_reason':reason,'new_19_cell_physical_rerun_claimed':False,
        'A2_scope':'Existing frozen 19-cell physical results reaudited, with protected code and trace bytes unchanged.',
        'independent_external_signatures':None,'official_A3_or_Level1_claimed':False}
    with a.output.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    print(json.dumps({'passed':data['passed'],'checks':checks,'preserved_files':data['preserved_files']},indent=2))
    return 0 if data['passed'] else 3

if __name__=='__main__':raise SystemExit(main())
