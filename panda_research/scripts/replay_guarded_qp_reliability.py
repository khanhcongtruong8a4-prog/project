"""Frozen experiment replay with only the declared solver sign correction.

The original seven-cell protocol retains its original solver. The twelve
alpha_v=10 cells receive the corrected guarded backend, with their frozen
configuration unchanged. A separate four-cell alpha_v=5 E3 campaign probes
active-filter refinement and cannot be counted as an A2-v4 success.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,importlib.metadata,importlib.util,json,platform,re,subprocess,traceback
from dataclasses import replace
from datetime import datetime,timezone
import numpy as np
from reproduce_a2_acceptance import verify_inputs as verify_original_inputs,git_metadata,import_script
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.a2_qp_reliable_v1 import BoundedGuardedQP,NUMERICAL_POLICY
from panda_closed_loop.guarded_qp_native_v1 import backend_record
from panda_closed_loop.p1_r3 import compare_refinement

POLICY=ROOT/'policy/guarded_qp_reliability_v1/PREDECLARATION.json'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')

def verify():
    plan=load(POLICY)
    for manifest in ['policy/guarded_qp_reliability_v1/PROTECTED_INPUTS.json']:
        data=load(ROOT/manifest)
        bad=[n for n,h in data['protected_source_sha256'].items() if sha(REPO/n)!=h]
        if bad:raise ValueError('Preserved source changed: '+str(bad[:10]))
    bad=[n for n,h in plan['implementation_sha256'].items() if sha(ROOT/n)!=h]
    if bad:raise ValueError('Frozen remediation implementation changed: '+str(bad))
    expected=(POLICY.parent/'PREDECLARATION.json.sha256').read_text().split()[0]
    if sha(POLICY)!=expected:raise ValueError('Remediation predeclaration differs')
    verify_original_inputs(load(ROOT/'policy/a2_acceptance_v1/PREDECLARATION.json'))
    original=import_script('original_frozen_r4','p1_r4.py');v4=import_script('v4_frozen','a2_extended_v4.py')
    original.verify();v4.verify()
    if not original.verify_regression_evidence():raise ValueError('Original regression evidence differs')
    commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(POLICY)],cwd=ROOT,text=True).strip()
    if not commit or subprocess.check_output(['git','show',commit+':panda_research/'+str(POLICY.relative_to(ROOT))],cwd=ROOT)!=(POLICY).read_bytes():
        raise ValueError('Remediation policy must be committed before motion')
    backend=backend_record()
    if backend['library_sha256']!=plan['tested_backend_sha256']:raise ValueError('Frozen tested backend differs; qualify a rebuilt backend separately')
    return plan,commit

def scenario(name,prefix):
    plan,commit=verify();active=name=='active_E3';ref='E3' if active else name[-2:]
    module=import_script('frozen_active_v2' if active else 'frozen_extended_v4','a2_extended_v2.py' if active else 'a2_extended_v4.py')
    experiment,frozen,original_commit=module.verify()
    out=ROOT/f'runs/guarded_qp_reliability_v1/{prefix}_{name}';out.mkdir(parents=True,exist_ok=False)
    meta={'start_utc':datetime.now(timezone.utc).isoformat(),'scenario':name,'original_policy':module.PLAN,
        'original_freeze_commit':original_commit,'remediation_freeze_commit':commit,'predeclaration_sha256':sha(POLICY),
        'backend':backend_record(),'python':sys.version,'platform':platform.platform(),
        'physical_model_controller_observer_barrier_reference_guard_gains_changed':False,
        'new_cold_initialization_or_solver_tolerances':False,'user_authorized_simulation':True,
        'scope':'LOCAL_NUMERICAL_REPLAY_NOT_A3_OR_LEVEL1','independent_signatures':None}
    write(out/'run_started.json',meta);cells=[];error=None
    try:
        system=build_components() if active else build_amended_system()
        system.geometry.function=system.geometry.function.expand()
        for index in range(4):
            try:
                with BoundedGuardedQP(system.barriers.taumax,NUMERICAL_POLICY,experiment['QP_wall_time_budget_s']) as qp:
                    cells.append(module.run_cell(replace(system,qp=qp),experiment,ref,index,out))
            except Exception:
                failure={'cell':index,'engineering_error':traceback.format_exc(),'a2':{'completed':False,'passed':False},'audit':{'passed':False}}
                write(out/f'cell_{index}_engineering_error.json',failure);cells.append(failure)
        refinement=compare_refinement(cells,experiment['fixed_acceptance_thresholds'])
        passed=all(c.get('audit',{}).get('passed',False) and c['a2']['passed'] for c in cells)
        passed=bool(passed and refinement['passed'] and all(c['status']=='PASS' for c in refinement['comparisons']))
        summary={'scenario':name,'reference_id':ref,'outcome':'PASS' if passed else 'FAIL','cells':cells,
            'refinement':refinement,'A3_executed':False,'independent_signatures':None,
            'configuration_changed':False,'only_solver_sign_correction':True,'active_filter_scope':active}
        write(out/'summary.json',summary)
    except Exception:error=traceback.format_exc();passed=False;print(error,file=sys.stderr)
    verify()
    meta.update(finish_utc=datetime.now(timezone.utc).isoformat(),passed=passed,engineering_error=error,
                protected_inputs_unchanged=True)
    write(out/'run_completed.json',meta);return 0 if passed else 3

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='reliability_v1_fresh')
    p.add_argument('--scenario',choices=['v4_E1','v4_E2','v4_E3','active_E3'])
    p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Unsafe exclusive prefix')
    if a.verify_only:
        plan,commit=verify();print(json.dumps({'verified':True,'freeze_commit':commit,'new_motion':False,'backend':backend_record()['library_sha256']}));return 0
    if a.scenario:return scenario(a.scenario,a.prefix)
    plan,commit=verify();out=ROOT/f'reports/guarded_qp_reliability_v1/{a.prefix}';out.mkdir(parents=True,exist_ok=False)
    start={'start_utc':datetime.now(timezone.utc).isoformat(),'freeze_commit':commit,'prefix':a.prefix,
        'command':[sys.executable,*sys.argv],'environment_packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'backend':backend_record(),'historical_failures_preserved':True,'independent_signatures':None}
    write(out/'run_started.json',start);contracts={}
    for name,script,count in plan['contract_suites']:
        report=out/(name+'.json')
        with (out/(name+'.log')).open('x') as log:
            run=subprocess.run([sys.executable,'tests/'+script,'--report',str(report)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        data=load(report);contracts[name]={'exit_code':run.returncode,'tests':data['tests_run'],'passed':run.returncode==0 and data['overall_pass'] and data['tests_run']==count}
    write(out/'CONTRACTS.json',contracts)
    if not all(r['passed'] for r in contracts.values()):return 1
    commands={'original_A2':[sys.executable,'scripts/p1_r4.py','--contracts',str(out/'original_r4.json'),
                    '--output',f'runs/p1_r4/{a.prefix}_original_r4']}
    for name in ['v4_E1','v4_E2','v4_E3','active_E3']:
        commands[name]=[sys.executable,'scripts/replay_guarded_qp_reliability.py','--prefix',a.prefix,'--scenario',name]
    write(out/'commands.json',commands);jobs=[]
    for name,cmd in commands.items():
        with (out/(name+'_physical.log')).open('x') as f:child=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        jobs.append((name,child))
    codes={}
    for name,child in jobs:codes[name]=child.wait();print(name,'exit',codes[name],flush=True)
    verify();start.update(finish_utc=datetime.now(timezone.utc).isoformat(),exit_codes=codes,
        A2_selected_cells_passed=all(codes[n]==0 for n in ['original_A2','v4_E1','v4_E2','v4_E3']),
        active_filter_refinement_passed=codes['active_E3']==0,protected_inputs_unchanged=True)
    write(out/'run_completed.json',start)
    return 0 if all(c==0 for c in codes.values()) else 3

if __name__=='__main__':raise SystemExit(main())
