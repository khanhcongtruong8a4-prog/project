"""Small source-only distribution: unchanged numerical functions, explicit I/O adapter.

Historical trace-integrity gates are NOT passed on absent data. The full archive
is optional for reviewing old bytes; fresh numerical replays need no old runs.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,copy,hashlib,importlib.metadata,json,os,re,subprocess
from datetime import datetime,timezone
from types import FunctionType
from dataclasses import replace


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,d):
    from panda_closed_loop.logging import json_values
    with Path(p).open('x') as f:json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')
def verify_bundle():
    manifest=REPO/'COMPACT_MANIFEST.json'
    if not manifest.is_file():raise ValueError('Use the extracted compact distribution')
    a=load(manifest)
    for n,r in a['files'].items():
        p=REPO/n
        if not p.is_file() or p.stat().st_size!=r['size'] or sha(p)!=r['sha256']:raise ValueError('Compact input mismatch: '+n)
    if tuple(sys.version_info[:3])!=(3,12,14):raise ValueError('Pinned Python 3.12.14 required for exact original checks')
    for line in (ROOT/'requirements-compact.lock.txt').read_text().splitlines():
        if '==' in line:
            n,v=line.split('==',1)
            if importlib.metadata.version(n)!=v:raise ValueError('Pinned dependency differs: '+n)
    return a

def bootstrap():
    a=verify_bundle()
    os.environ['PANDA_COMPLETION_BUILD']=str(ROOT/'native/build_completion_v2')
    os.environ['PANDA_GUARDED_QP_BUILD']=str(ROOT/'native/build_guarded_qp_v1')
    if not (REPO/'.git').exists():
        subprocess.run(['git','init','-q','--initial-branch=local-compact-source-staging'],cwd=REPO,check=True)
        subprocess.run(['git','add','-f','panda_research/policy'],cwd=REPO,check=True)
        subprocess.run(['git','-c','user.name=Local compact reproduction','-c','user.email=local@invalid','commit','-q','-m','Local normative-input staging, not recovered historical provenance'],cwd=REPO,check=True)
    from run_polynomial_hold_v2_4 import verify
    from panda_closed_loop.guarded_qp_final_v1 import verify_release
    verify();verify_release()
    return a


def plan_for(case):
    """Same normative plans; old archive byte checks are separately NOT_RUN."""
    from panda_closed_loop.config import Policy
    folder='a2_extended_v2' if case=='alpha5' else 'a2_extended_v4'
    plan=load(ROOT/f'policy/{folder}/A2_EXTENDED_PREDECLARATION.json')
    p=Policy.load().raw
    if plan['C4_grid']!=p['integration']['validation_grid'] or plan['fixed_acceptance_thresholds']!=p['fixed_acceptance_thresholds']:raise ValueError('Original grid/thresholds changed')
    if case=='alpha10':
        plan['references']['E3']['duration_s']=.5;plan['A2_reference']['duration_s']=.5
        plan['reference_screen_times_s']=[t*.5 for t in plan['reference_screen_times_s']]
    return plan


def bind_plan_loader(function):
    """Only the plan-file verification I/O binding changes, never math code."""
    g=dict(function.__globals__);g['plan_for']=plan_for
    clone=FunctionType(function.__code__,g,function.__name__,function.__defaults__,function.__closure__)
    if clone.__code__ is not function.__code__:raise ValueError('Changed runtime bytecode')
    return clone


def candidate(case,index,out):
    import run_polynomial_hold_v2_4 as original
    import audit_gauss_execution_v2_4a as stage
    import summarize_polynomial_remediation_v2_4b as full
    from panda_closed_loop.assembly import build_components
    from panda_closed_loop.a2_policy_v4 import build_amended_system
    raw_exit=bind_plan_loader(original.cell)(case,index,out)
    c=load(out/'result.json')
    system=build_components() if case=='alpha5' else build_amended_system()
    cert=bind_plan_loader(stage.audit_cell)(out,system,case)
    cert['audit_policy_sha256']=sha(ROOT/'policy/active_remediation_v2/AUDIT_CORRECTION_V2_4A.json')
    kkt=bind_plan_loader(full.independent_trace_audit)(out,c,case) if cert['passed'] else {'passed':False}
    passed=bool(cert['passed'] and kkt['passed'] and kkt.get('genuine_activity_passed',False))
    write(out/'COMPACT_VERIFIED_RESULT.json',{'passed':passed,'raw_runner_exit':raw_exit,'stage_audit':cert,'independent_full_KKT':kkt,
          'original_result_sha256':sha(out/'result.json'),'runtime_mathematics_changed':False,'plan_loader_scope':'HASHED_SOURCE_AND_NORMATIVE_INPUTS','old_archived_trace_integrity_gate':'NOT_RUN_OMITTED_FROM_COMPACT','official_A3':False,'Level1':False})
    normalized=copy.deepcopy(c);normalized['original_runtime_result_passed']=c['a2']['passed'];normalized['a2']['passed']=passed;normalized['audit']['passed']=passed
    return normalized


def run_tests(out):
    out.mkdir(parents=True,exist_ok=False);results=[]
    jobs=[('completion','tests/test_polynomial_hold_v2_4.py',9,False),('GL_audit','tests/test_gauss_execution_audit_v2_4a.py',3,False),
          ('slack_identity','tests/test_slack_audit_v2_4b.py',3,False),('original_r4','tests/test_p1_r4.py',14,True),
          ('preserved_QP','tests/test_a2_qp_v2.py',14,True),('v4_gain','tests/test_a2_policy_v4.py',10,True),
          ('corrected_QP_math','tests/test_guarded_qp_reliable_math.py',12,True)]
    for name,file,count,report in jobs:
        cmd=[sys.executable,file]+(['--report',str(out/(name+'.json'))] if report else [])
        with (out/(name+'.log')).open('x') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if report:d=load(out/(name+'.json'));actual=d['tests_run'];passed=r.returncode==0 and d['overall_pass'] and actual==count
        else:
            text=(out/(name+'.log')).read_text();m=re.search(r'Ran (\d+) tests?',text);actual=int(m.group(1)) if m else 0;passed=r.returncode==0 and actual==count
        results.append({'suite':name,'passed':bool(passed),'tests_run':actual});print(name,'PASS' if passed else 'FAIL',actual,flush=True)
    with (out/'T27.log').open('x') as f:r=subprocess.run([sys.executable,'scripts/qualify_guarded_qp_strict_v1_1.py','--output',str(out/'T27')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    t=load(out/'T27/SUMMARY.json');good=r.returncode==0 and t['fixture_count']==39 and t['overall_pass']
    results.append({'suite':'T27','passed':bool(good),'tests_run':t['fixture_count']})
    passed=all(x['passed'] for x in results);write(out/'TESTS.json',{'passed':passed,'suites':results,'tests_executed':sum(x['tests_run'] for x in results)})
    return passed


def original_regressions(out):
    """Cold original-seven equations/auditor; no false old-archive GO."""
    import numpy as np
    from reproduce_a2_acceptance import import_script
    from panda_closed_loop.assembly import build_components
    from panda_closed_loop.p1_r4 import AB2TorqueController,audit_cell
    from panda_closed_loop.p1_r3 import compare_refinement
    from case_sets import all_cases
    module=import_script('compact_original_r4','p1_r4.py');plan=load(ROOT/module.PLAN)
    if not module.verify_regression_evidence():raise ValueError('Original component/source hash regression metadata failed')
    system=build_components();original=system.geometry.function;expanded=original.expand()
    if not all(all(np.array_equal(x,y) for x,y in zip(original(q),expanded(q))) for q in all_cases()[0]):raise ValueError('Geometry equivalence failure')
    system.geometry.function=expanded;out.mkdir(parents=True,exist_ok=False);cells=[]
    for i in range(7):
        local=replace(system,controller=AB2TorqueController(system.controller));module.legacy.run_cell(local,plan,i,out)
        cell=load(out/f'cell_{i}.json');cell['audit']=audit_cell(cell,out,system,plan);cells.append(cell)
    cohorts={name:compare_refinement([cells[i] for i in ids],plan['fixed_acceptance_thresholds']) for name,ids in plan['cohorts'].items()}
    passed=all(c['a2']['passed'] and c['audit']['passed'] for c in cells) and all(all(c['status']=='PASS' for c in v['comparisons']) for v in cohorts.values())
    write(out/'SUMMARY.json',{'numerical_replay_passed':bool(passed),'cells':cells,'cohorts':cohorts,'original_full_archive_integrity_gate':'NOT_RUN_OMITTED_FROM_COMPACT'})
    return bool(passed)


def extended_regressions(out):
    from reproduce_a2_acceptance import import_script
    from panda_closed_loop.a2_policy_v4 import build_amended_system
    from panda_closed_loop.guarded_qp_final_v1 import BoundedGuardedQP
    from panda_closed_loop.p1_r3 import compare_refinement
    module=import_script('compact_extended_v4','a2_extended_v4.py');plan=load(ROOT/module.PLAN)
    system=build_amended_system();system.geometry.function=system.geometry.function.expand();results={}
    for ref in ['E1','E2','E3']:
        folder=out/ref;folder.mkdir(parents=True,exist_ok=False);cells=[]
        for i in range(4):
            with BoundedGuardedQP(system.barriers.taumax) as qp:cells.append(module.run_cell(replace(system,qp=qp),plan,ref,i,folder))
        refinement=compare_refinement(cells,plan['fixed_acceptance_thresholds']);passed=all(c['a2']['passed'] and c['audit']['passed'] for c in cells) and all(r['status']=='PASS' for r in refinement['comparisons'])
        results[ref]={'passed':bool(passed),'cells':cells,'refinement':refinement}
    write(out/'SUMMARY.json',{'numerical_replay_passed':all(r['passed'] for r in results.values()),'references':results,'original_full_archive_integrity_gate':'NOT_RUN_OMITTED_FROM_COMPACT'})
    return all(r['passed'] for r in results.values())


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--verify-only',action='store_true');g.add_argument('--all',action='store_true');g.add_argument('--candidate',choices=['alpha5','alpha10'])
    p.add_argument('--cell',type=int,choices=range(4),default=0);p.add_argument('--prefix',default='compact_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Invalid prefix')
    manifest=bootstrap()
    if a.verify_only:
        print('Verified compact source/normative inputs/native backend. Historical bulk-trace integrity: NOT RUN (omitted).');return 0
    out=ROOT/'runs/compact_delivery'/a.prefix;out.mkdir(parents=True,exist_ok=False)
    if a.candidate:
        r=candidate(a.candidate,a.cell,out/f'{a.candidate}_cell{a.cell}');passed=r['a2']['passed']
    else:
        passed=run_tests(out/'tests')
        if a.all and passed:
            passed=original_regressions(out/'original_7') and passed
            passed=extended_regressions(out/'extended_12') and passed
            from panda_closed_loop.p1_r3 import compare_refinement
            cohorts={}
            for case in ['alpha5','alpha10']:
                cells=[candidate(case,i,out/f'{case}_cell{i}') for i in range(4)];r=compare_refinement(cells,plan_for(case)['fixed_acceptance_thresholds'])
                ok=all(c['a2']['passed'] for c in cells) and all(x['status']=='PASS' for x in r['comparisons']);cohorts[case]={'passed':bool(ok),'refinement':r};passed=bool(passed and ok)
            write(out/'CANDIDATE_REFINEMENTS.json',cohorts)
    write(out/'SUMMARY.json',{'passed':bool(passed),'scope':'SOURCE_ONLY_FRESH_NUMERICAL_REPLAY','old_archive_integrity_gate':'NOT_RUN_OMITTED_FROM_COMPACT',
          'source_release':manifest['scientific_source_commit'],'current_simulations_reexecuted':bool(a.all or a.candidate),'prior_passes_substituted_for_current_results':False,'official_A3':False,'Level1':False})
    print('COMPACT NUMERICAL REPLAY','PASS' if passed else 'FAIL',flush=True);return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())
