"""Reproduce the frozen original A2 and v4 without modifying their runners.

Works in a full Git checkout or a fully restored standalone package. A ZIP
gets an explicitly labeled LOCAL Git input-staging commit so the ORIGINAL
runners' pre-motion Git checks remain enabled. It is not historic provenance
or an independent reviewer signature. All protected source bytes are checked.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
import argparse,hashlib,importlib.metadata,importlib.util,json,platform,re,shutil,subprocess,traceback
from datetime import datetime,timezone
from panda_closed_loop.a2_acceptance import compare_cell
from panda_closed_loop.p1_r3 import compare_refinement

PLAN=ROOT/'policy/a2_acceptance_v1/PREDECLARATION.json'


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def load(path):return json.loads(Path(path).read_text())


def verify_inputs(plan):
    bad=[n for n,h in plan['protected_source_sha256'].items() if not (REPO/n).is_file() or sha(REPO/n)!=h]
    bad += [n for n,h in plan['verification_code_sha256'].items() if sha(REPO/n)!=h]
    if bad:raise ValueError('Protected input differs/missing: '+', '.join(bad[:20]))
    if list(sys.version_info[:3])!=plan['python_version']:raise ValueError('Pinned Python version differs')
    for name,version in plan['required_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Pinned package differs: '+name)
    expected=(PLAN.parent/'PREDECLARATION.json.sha256').read_text().split()[0]
    if sha(PLAN)!=expected:raise ValueError('Verification predeclaration checksum differs')
    return len(plan['protected_source_sha256'])


def git_metadata():
    initialized=False
    if not (REPO/'.git').exists():
        if not shutil.which('git'):raise ValueError('Git is required for the original frozen-runner checks')
        subprocess.run(['git','init','-q','--initial-branch=local-a2-reproduction'],cwd=REPO,check=True)
        for key,value in [('user.name','A2 Local Reproduction'),('user.email','local-reproduction@invalid')]:
            subprocess.run(['git','config',key,value],cwd=REPO,check=True)
        paths=['panda_research/policy/v1.2.2-r4/FROZEN_INPUTS.json',
               'panda_research/policy/a2_extended_v4/FROZEN_INPUTS.json',
               'panda_research/policy/a2_acceptance_v1/PREDECLARATION.json']
        subprocess.run(['git','add','-f','--',*paths],cwd=REPO,check=True)
        subprocess.run(['git','commit','-q','-m','Local reproduction input staging only; historic provenance is separately recorded'],cwd=REPO,check=True)
        initialized=True
    top=subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=REPO,text=True).strip()
    if Path(top).resolve()!=REPO.resolve():raise ValueError('Unrelated enclosing Git repository')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    return {'git_head':head,'local_ZIP_input_staging_created':initialized,
            'scope':'LOCAL_REPRODUCTION_METADATA_NOT_AN_EXTERNAL_SIGNATURE_OR_HISTORIC_COMMIT_RECONSTRUCTION'}


def import_script(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def compare_runs(prefix):
    result={};r4=load(ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json')
    old=ROOT/'runs/p1_r4/fresh_2fe50b9';new=ROOT/f'runs/p1_r4/{prefix}_original_r4'
    a,b=load(old/'summary.json'),load(new/'summary.json')
    cells=[compare_cell(x,y,old,new) for x,y in zip(a['cells'],b['cells'])]
    cohorts={name:compare_refinement([b['cells'][i] for i in indices],r4['fixed_acceptance_thresholds'])
             for name,indices in r4['cohorts'].items()}
    result['original_A2']={'cells':cells,'cohorts':cohorts,'replayed_gate':b['gate'],
      'passed':len(cells)==7 and all(c['passed'] for c in cells) and b['gate']['status']=='GO'
           and all(all(r['status']=='PASS' for r in v['comparisons']) for v in cohorts.values()),
      'original_run':str(old.relative_to(ROOT)),'replay_run':str(new.relative_to(ROOT))}
    policy=load(ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json')
    for ref in ['E1','E2','E3']:
        old=ROOT/f'runs/a2_extended_v4/{ref}_c02f908';new=ROOT/f'runs/a2_extended_v4/{prefix}_{ref}'
        a,b=load(old/'summary.json'),load(new/'summary.json')
        cells=[compare_cell(x,y,old,new) for x,y in zip(a['cells'],b['cells'])]
        refinements=compare_refinement(b['cells'],policy['fixed_acceptance_thresholds'])
        result[ref]={'cells':cells,'refinements':refinements,'replayed_outcome':b['outcome'],
            'passed':len(cells)==4 and all(c['passed'] for c in cells) and b['outcome']=='PASS'
                    and all(r['status']=='PASS' for r in refinements['comparisons']),
            'original_run':str(old.relative_to(ROOT)),'replay_run':str(new.relative_to(ROOT))}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',default='replay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.prefix):raise ValueError('Unsafe exclusive run prefix')
    plan=load(PLAN);verified=verify_inputs(plan);gitinfo=git_metadata()
    original=import_script('frozen_original_r4_runner','p1_r4.py');v4=import_script('frozen_v4_runner','a2_extended_v4.py')
    _,_,old_commit=original.verify();_,_,v4_commit=v4.verify()
    if not original.verify_regression_evidence():raise ValueError('Original regression evidence/input hashes differ')
    if args.verify_only:
        print(json.dumps({'verified_protected_files':verified,'original_freeze_checks_pass':True,
            'v4_freeze_checks_pass':True,'recorded_original_runner_freeze_commit':old_commit,
            'recorded_v4_runner_freeze_commit':v4_commit,'new_motion_executed':False,**gitinfo},indent=2));return 0
    out=ROOT/f'reports/a2_acceptance_v1/{args.prefix}';out.mkdir(parents=True,exist_ok=False)
    metadata={'start_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
      'cwd':str(ROOT),'python':sys.version,'platform':platform.platform(),'predeclaration_sha256':sha(PLAN),
      'packages':{x.metadata['Name']:x.version for x in importlib.metadata.distributions()},
      'git':gitinfo,'verification_status':'EXECUTED_LOCALLY_SAME_HOST_NEW_ENV_NOT_EXTERNAL_REVIEW',
      'physical_replay_executed':True,'model_or_experimental_parameters_changed':False,
      'original_runner_freeze_commit':old_commit,'v4_runner_freeze_commit':v4_commit,
      'independent_reviewer_signature':None}
    write(out/'run_started.json',metadata)
    contracts={};jobs=[];codes={};error=None;comparison=None;passed=False
    try:
        for name,script,count in plan['contract_suites']:
            report=out/(name+'.json');command=[sys.executable,'tests/'+script,'--report',str(report)]
            with (out/(name+'.log')).open('x') as f:
                run=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            data=load(report);contracts[name]={'return_code':run.returncode,'report':str(report.relative_to(ROOT)),
                'tests_run':data['tests_run'],'passed':run.returncode==0 and data['overall_pass'] and data['tests_run']==count}
            failures=[r for r in data.get('checks',[]) if r.get('result')!='PASS']
            diagnostic=plan['diagnostic_only_math_test'] if name=='framework_math' else None
            def is_diagnostic(r):
                probe=data.get('active_QP_evidence',{}).get('preserved_real_43',{})
                q=probe.get('query',{})
                return (diagnostic is not None and r.get('test','').rsplit('.',1)[-1]==diagnostic
                    and r.get('result')=='FAIL' and probe.get('certificate',{}).get('passed') is True
                    and q.get('status')=='QPSolverOutput.PROXQP_PRIMAL_INFEASIBLE'
                    and q.get('stop_requested') is True and q.get('applied') is None
                    and probe.get('torque_actuated') is False)
            required=(contracts[name]['passed'] or (name=='framework_math' and data['tests_run']==count
                and bool(failures) and all(is_diagnostic(r) for r in failures)))
            contracts[name]['required_A2_scope_pass']=required
            contracts[name]['diagnostic_failures_retained']=failures
            print('contracts',name,'all_pass',contracts[name]['passed'],'required_A2_scope',required,flush=True)
            if not required:raise ValueError('Required scoped contract did not pass: '+name)
        write(out/'contracts_summary.json',contracts)
        commands={'original_A2':[sys.executable,'scripts/p1_r4.py','--contracts',str(out/'original_r4.json'),
                      '--output',f'runs/p1_r4/{args.prefix}_original_r4']}
        for ref in ['E1','E2','E3']:
            commands[ref]=[sys.executable,'scripts/a2_extended_v4.py','--reference',ref,'--contracts',str(out/'v4_gain.json'),
                           '--output',f'runs/a2_extended_v4/{args.prefix}_{ref}']
        write(out/'commands.json',commands)
        for name,command in commands.items():
            with (out/(name+'_physical.log')).open('x') as f:
                child=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            jobs.append((name,child))
        for name,child in jobs:
            codes[name]=child.wait();print('physical',name,'exit',codes[name],flush=True)
        write(out/'physical_exit_codes.json',codes)
        comparison=compare_runs(args.prefix);write(out/'REPLAY_COMPARISON.json',comparison)
        verify_inputs(plan)
        passed=all(c['required_A2_scope_pass'] for c in contracts.values()) and all(c==0 for c in codes.values()) and all(c['passed'] for c in comparison.values())
    except Exception:
        error=traceback.format_exc();print(error,file=sys.stderr,flush=True)
    finally:
        for name,child in jobs:
            if child.poll() is None:
                # Retain completed workers; no replacement/rerun of a failed cell.
                codes[name]=child.wait()
        unchanged=True
        try:verify_inputs(plan)
        except Exception:unchanged=False
        passed=bool(passed and unchanged)
        metadata.update(finish_utc=datetime.now(timezone.utc).isoformat(),technical_pass=passed,
            protected_inputs_unchanged=unchanged,physical_exit_codes=codes,engineering_error=error,
            administrative_approval_required=False,external_independent_evidence_claimed=False,
            all_development_contracts_pass=bool(contracts) and all(c['passed'] for c in contracts.values()),
            guarded_QP_general_qualification='HOLD_KNOWN_LEGACY_ALPHA5_ACTIVE_FIXTURE_COUNTEREXAMPLE')
        write(out/'run_completed.json',metadata)
    print('Technical replay acceptance', 'PASS' if passed else 'FAIL',flush=True)
    return 0 if passed else 3


if __name__=='__main__':raise SystemExit(main())
