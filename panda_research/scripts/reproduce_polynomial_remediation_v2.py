"""Standalone/full-checkout reproduction. Never substitutes archived passes."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json,os,re,subprocess,copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone

def write(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bootstrap():
    # A fresh ZIP gets local provenance staging, never forged historical refs.
    if not (REPO/'.git').exists():
        subprocess.run(['git','init','-q','--initial-branch=local-remediation-reproduction'],cwd=REPO,check=True)
        subprocess.run(['git','-c','user.name=Local reproduction','-c','user.email=local@invalid','add','-f','panda_research/policy'],cwd=REPO,check=True)
        subprocess.run(['git','-c','user.name=Local reproduction','-c','user.email=local@invalid','commit','-q','-m','Local input staging only; not recovered historical provenance'],cwd=REPO,check=True)
    from panda_closed_loop.guarded_qp_final_v1 import verify_release
    verify_release()
    from run_polynomial_hold_v2_4 import verify
    verify()

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='reproduce_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    p.add_argument('--workers',type=int,choices=[1,2],default=2);p.add_argument('--verify-only',action='store_true');p.add_argument('--candidate-only',action='store_true');a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Invalid exclusive prefix')
    bootstrap()
    if a.verify_only:print('Protected source and native backend verified; no motion executed');return 0
    out=ROOT/'reports/active_remediation_v2/reproductions'/a.prefix;out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.setdefault('PANDA_COMPLETION_BUILD',str(ROOT/'native/build_completion_v2'))
    # For an unpacked source distribution, build the new generalized kernel if absent.
    build=Path(env['PANDA_COMPLETION_BUILD'])
    def run(name,cmd):
        with (out/(name+'.log')).open('x') as f:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
        print(name,'exit',r.returncode,flush=True);return {'name':name,'command':cmd,'exit_code':r.returncode}
    records=[]
    if not (build/'BUILD.json').exists():
        records.append(run('build_completion',[sys.executable,'scripts/build_polynomial_completion_v2.py','--output',str(build)]))
        if records[-1]['exit_code']:write(out/'summary.json',{'passed':False,'commands':records});return 3
    records.append(run('contracts',[sys.executable,'tests/test_polynomial_hold_v2_4.py']))
    records.append(run('audit_contracts',[sys.executable,'tests/test_gauss_execution_audit_v2_4a.py']))
    if records[-1]['exit_code']:write(out/'summary.json',{'passed':False,'commands':records});return 3
    if not a.candidate_only:
        records.append(run('T27_39',[sys.executable,'scripts/qualify_guarded_qp_strict_v1_1.py','--output',str(out/'T27')]))
        # This historical runner includes a deliberately preserved four-cell old
        # active campaign. Its aggregate exit 3 is not a new-candidate verdict.
        records.append(run('frozen_19_and_historical_active',[sys.executable,'scripts/replay_guarded_qp_reliability.py','--prefix',a.prefix]))
    pairs=[(case,i) for case in ['alpha5','alpha10'] for i in range(4)]
    def candidate(pair):
        case,i=pair;name=f'{a.prefix}_{case}_cell{i}'
        return run(name,[sys.executable,'scripts/run_polynomial_hold_v2_4.py','--case',case,'--cell',str(i),'--output',str(ROOT/'runs/active_remediation_v2'/name)])
    with ThreadPoolExecutor(max_workers=a.workers) as pool:records.extend(pool.map(candidate,pairs))
    from panda_closed_loop.p1_r3 import compare_refinement
    from audit_gauss_execution_v2_4a import audit_cell
    from panda_closed_loop.assembly import build_components
    from panda_closed_loop.a2_policy_v4 import build_amended_system
    policy=ROOT/'policy/active_remediation_v2/AUDIT_CORRECTION_V2_4A.json';af=json.loads(policy.read_text())
    if any(sha(ROOT/n)!=h for n,h in af['source_sha256'].items()):raise ValueError('Audit source differs')
    from run_polynomial_hold_v2_4 import plan_for
    result={}
    for case in ['alpha5','alpha10']:
        system=build_components() if case=='alpha5' else build_amended_system()
        cells=[]
        for i in range(4):
            folder=ROOT/'runs/active_remediation_v2'/f'{a.prefix}_{case}_cell{i}';c=json.loads((folder/'result.json').read_text())
            verification=audit_cell(folder,system,case);verification['audit_policy_sha256']=sha(policy)
            write(folder/'AUDIT_V2_4A.json',verification)
            c['original_runtime_result_passed']=c['a2']['passed'];c['verification_correction']=verification
            c['a2']['passed']=verification['passed'];c['audit']['passed']=verification['passed'];cells.append(c)
        refinement=compare_refinement(cells,plan_for(case)['fixed_acceptance_thresholds'])
        result[case]={'cells':cells,'refinement':refinement,'passed':all(c['a2']['passed'] and c['audit']['passed'] for c in cells) and all(r['status']=='PASS' for r in refinement['comparisons'])}
    passed=all(r['passed'] for r in result.values())
    regression=None;t27=None
    if not a.candidate_only:
        t27=json.loads((out/'T27/SUMMARY.json').read_text())
        regression=json.loads((ROOT/'reports/guarded_qp_reliability_v1'/a.prefix/'run_completed.json').read_text())
        passed=bool(passed and t27['overall_pass'] and t27['fixture_count']==39 and regression['A2_selected_cells_passed'] and regression['protected_inputs_unchanged'])
    write(out/'summary.json',{'overall_numerical_passed':passed,'frozen_regression':regression,'T27':t27,'candidates':result,'commands':records,'official_A3':False,'Level1':False,'certified_bound_claim':False})
    return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())
