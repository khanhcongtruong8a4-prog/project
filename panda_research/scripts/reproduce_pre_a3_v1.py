"""Reproduce the new numerical work or development dynamics from a compact ZIP.

The small numerical package needs no historical raw-trace download. The task
evidence ZIP additionally restores the exact traces used by the legacy
diagnosis. The prior complete historical archive remains a separate annex.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json,platform,re,subprocess
from datetime import datetime,timezone

def load(p):return json.loads(Path(p).read_text())
def write(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()

def verify_package():
    manifest=REPO/'PRE_A3_PACKAGE_MANIFEST.json'
    if manifest.exists():
        bad=[n for n,h in load(manifest)['files'].items() if sha(REPO/n)!=h['sha256']]
        if bad:raise ValueError('Package bytes differ: '+str(bad[:10]))
    from panda_closed_loop.guarded_qp_final_v1 import verify_release
    release=verify_release()
    import panda_closed_loop.guarded_qp_final_v1 as implementation
    if not Path(implementation.__file__).is_relative_to(ROOT):raise ValueError('Loaded unrelated source tree')
    return release

def restore_traces(scratch):
    if not (REPO/'evidence').is_dir():raise ValueError('Legacy trace diagnosis needs the task evidence ZIP, not the small numerical subset')
    from archive_evidence import restore
    restored=restore(REPO/'evidence',REPO,scratch)
    for n,r in load(REPO/'PRE_A3_SOURCE_MANIFEST.json')['encoded_CTZ'].items():
        if sha(REPO/n)!=r['sha256']:raise ValueError('Restored trace differs: '+n)
    return len(restored['files'])

def local_git():
    if not (REPO/'.git').exists():
        subprocess.run(['git','init','-q','--initial-branch=local-pre-a3-reproduction'],cwd=REPO,check=True)
        for k,v in [('user.name','Local Pre A3 Reproduction'),('user.email','local-reproduction@invalid')]:subprocess.run(['git','config',k,v],cwd=REPO,check=True)
        files=['panda_research/policy/pre_a3_blockers_v1/DEVELOPMENT_PREDECLARATION.json','panda_research/policy/pre_a3_blockers_v1/M1_PREDECLARATION.json']
        subprocess.run(['git','add','-f','--',*files],cwd=REPO,check=True)
        subprocess.run(['git','commit','-q','-m','LOCAL reproduction input staging, not historical provenance or independent verification'],cwd=REPO,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--verify-only',action='store_true');g.add_argument('--run-numerics',action='store_true')
    g.add_argument('--run-dynamics',action='store_true');g.add_argument('--diagnose-legacy',action='store_true')
    p.add_argument('--restore',action='store_true');p.add_argument('--scratch',type=Path)
    p.add_argument('--prefix',default='fresh_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Unsafe exclusive output prefix')
    release=verify_package()
    if a.restore or a.diagnose_legacy:print('Exact CTZ restored',restore_traces(a.scratch),flush=True)
    if not (a.run_numerics or a.run_dynamics or a.diagnose_legacy):
        from panda_closed_loop.a2_policy_v4 import build_amended_system
        system=build_amended_system()
        print(json.dumps({'package_and_source_verified':True,'model_assembly_from_packaged_inputs_passed':True,'alpha_v':system.policy.alpha_v,
            'solver_build':release['backend']['library_sha256'],'new_motion':False,'A3':'NO-GO','Level1':False},indent=2));return 0
    out=ROOT/f'reports/pre_a3_blockers_v1/reproductions/{a.prefix}';out.mkdir(parents=True,exist_ok=False)
    started={'start_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],'python':sys.version,
        'platform':platform.platform(),'source_root':str(ROOT),'scope':'LOCAL_REPRODUCTION_NOT_EXTERNAL_REVIEW',
        'official_A3':False,'external_signatures':None}
    write(out/'run_started.json',started)
    def run(name,command):
        with (out/(name+'.log')).open('x') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        return result.returncode
    codes={};comparison={}
    if a.diagnose_legacy:
        codes['legacy_diagnosis']=run('legacy_diagnosis',[sys.executable,'scripts/diagnose_active_filter_v1.py','--output',str(out/'legacy_diagnosis')])
    elif a.run_dynamics:
        local_git();jobs=[]
        for mode in ['candidate','ladder']:
            command=[sys.executable,'scripts/run_projected_feedback_development_v1.py','--mode',mode,
                '--output',str(ROOT/f'runs/pre_a3_blockers_v1/{a.prefix}_{mode}')]
            with (out/(mode+'.log')).open('x') as log:child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((mode,child))
        for mode,child in jobs:codes[mode]=child.wait()
        fresh_candidate=load(ROOT/f'runs/pre_a3_blockers_v1/{a.prefix}_candidate/summary.json')
        fresh_ladder=load(ROOT/f'runs/pre_a3_blockers_v1/{a.prefix}_ladder/summary.json')
        comparison['candidate_remains_failed_with_original_thresholds']=fresh_candidate['outcome']=='FAIL'
        comparison['all_candidate_cells_complete_and_audited']=len(fresh_candidate['cells'])==4 and all(c['a2']['completed'] and c['audit']['passed'] for c in fresh_candidate['cells'])
        comparison['ladder_cells_complete']=fresh_ladder['outcome']=='PASS' and len(fresh_ladder['cells'])==2
        original_candidate=load(ROOT/'runs/pre_a3_blockers_v1/projected_feedback_candidate/summary.json')
        original_ladder=load(ROOT/'runs/pre_a3_blockers_v1/original_AB2_delta_ladder/summary.json')
        comparison['candidate_recorded_metrics_exact']=all(x['a2']['metrics']==y['a2']['metrics'] for x,y in zip(original_candidate['cells'],fresh_candidate['cells']))
        comparison['ladder_recorded_metrics_exact']=all(x['a2']['metrics']==y['a2']['metrics'] for x,y in zip(original_ladder['cells'],fresh_ladder['cells']))
        # A failed experiment is retained as a failure; this is a reproduction
        # success condition, never a promotion of the candidate to GO.
    else:
        tests=[('candidate_contracts','tests/test_projected_feedback_v1.py'),('M1_contracts','tests/test_m1_common_v1.py')]
        jobs=[]
        for name,script in tests:
            command=[sys.executable,script,'--report',str(out/(name+'.json'))]
            with (out/(name+'.log')).open('x') as log:child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((name,child))
        tcommand=[sys.executable,'scripts/qualify_guarded_qp_strict_v1_1.py','--output',str(out/'T27')]
        with (out/'T27.log').open('x') as log:child=subprocess.Popen(tcommand,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        jobs.append(('T27',child))
        for name,child in jobs:codes[name]=child.wait()
        if any(c!=0 for c in codes.values()):write(out/'FAILED_CONTRACTS.json',codes);return 3
        codes['M1_registry']=run('M1_registry',[sys.executable,'scripts/build_m1_registry_v1.py','--output',str(out/'M1')])
        if codes['M1_registry']!=0:write(out/'FAILED_REGISTRY.json',codes);return 3
        codes['G2_5']=run('G2_5',[sys.executable,'scripts/screen_g25_final_policy_v1.py','--registry',str(out/'M1/M1_REGISTRY.json'),'--output',str(out/'G2_5')])
        original=load(ROOT/'reports/pre_a3_blockers_v1/m1_registry/M1_REGISTRY.json');fresh=load(out/'M1/M1_REGISTRY.json')
        comparison['all_14_registry_entries_exact']=original['entries']==fresh['entries']
        comparison['training_and_heldout_grid_sha256_exact']=original['grid_sha256']==fresh['grid_sha256']
        comparison['heldout_exceedances_exact']=original['heldout_exceedances']==fresh['heldout_exceedances']
        tq=load(out/'T27/SUMMARY.json');comparison['T27_39_pass']=tq['overall_pass'] and tq['fixture_count']==39
        screen=load(out/'G2_5/SUMMARY.json');comparison['G2_5_NO_GO_reproduced']=screen['G2_5_decision']=='NO-GO'
        comparison['all_1212_filter_point_solves_pass']=sum(x['filter_point_QPs_passed'] for x in screen['results'])==1212
        from panda_closed_loop.a2_policy_v4 import build_amended_system
        from panda_closed_loop.m1_common_domain_v1 import NumericalM1Registry
        from panda_closed_loop.pre_a3_entry_gate_v1 import require_planner_entry,PlannerEntryBlocked
        endpoint=load(ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_0.json')['endpoint']['QP']
        blocked=False
        try:require_planner_entry(build_amended_system(),endpoint,NumericalM1Registry(fresh))
        except PlannerEntryBlocked:blocked=True
        comparison['planner_entry_gate_stops_before_solve']=blocked
    passed=all(comparison.values()) and (all(c==0 for c in codes.values()) if not a.run_dynamics else codes.get('candidate')==3 and codes.get('ladder')==0)
    write(out/'REPRODUCTION_RESULT.json',{'reproduction_passed':passed,'exit_codes':codes,'comparison':comparison,
        'finish_utc':datetime.now(timezone.utc).isoformat(),'active_filter_candidate_adopted':False,
        'G2_5_and_A3_readiness':'NO-GO','Level1':False,'human_independent_signatures':None})
    print(json.dumps({'reproduction_passed':passed,'comparison':comparison,'G2_5_and_A3':'NO-GO'},indent=2))
    return 0 if passed else 3

if __name__=='__main__':raise SystemExit(main())
