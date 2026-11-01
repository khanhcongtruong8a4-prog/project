"""Audit and package Action 3 evidence without implying official A2 approval."""
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib
import json
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())


def main():
    pointer=read(ROOT/'reports/action3_latest.json');run=ROOT/pointer['run_directory']
    record=read(run/'run.json')
    if pointer['status']!='PASS_COMPONENTS_AND_REGRESSIONS_A2_HOLD' or pointer['run_sha256']!=sha(run/'run.json'):
        raise RuntimeError('No current completed passing component/regression run')
    if not all(c['matched_expected_exit'] for c in record['commands']) or not record['protected_files_unchanged']:
        raise RuntimeError('Unexpected command failure or mutated protected files')
    for name,expected in record['code_and_input_hashes'].items():
        if sha(ROOT/name)!=expected:raise RuntimeError('Validated file changed: '+name)
    component=read(run/'component_tests.json');t28=read(run/'t28_raw_c.json')
    if not component['overall_pass'] or component['tests_run']<1 or not t28['overall_pass']:
        raise RuntimeError('Missing passing component/T28 tests')
    point=component['diagnostics']['PANDA_APPROVED_INITIAL_COMPONENT']
    if point['feasibility']!='FAIL_INFEASIBLE_WITH_APPROVED_INITIAL_VARPI' or not point['safe_stop_correct']:
        raise RuntimeError('Initial-point infeasibility/stop evidence missing or mislabeled')
    legacy_pointer=read(run/'legacy_run_pointer.json');legacy=ROOT/legacy_pointer['run_directory']
    if legacy_pointer['status']!='PASS_MODEL_VALIDATION_ONLY':raise RuntimeError('Dynamics/source regression failed')
    shutil.copy2(run/'REVIEW_HANDOFF.md',ROOT/'REVIEW_HANDOFF.md')
    changes=[]
    # Audit the actual worktree relative to the accepted v1.2.0 commit.
    for command in [['git','ls-files','--modified','-z'],['git','ls-files','--others','--exclude-standard','-z']]:
        output=subprocess.check_output(command,cwd=ROOT).split(b'\0')
        for name in output:
            if name:
                p=ROOT/name.decode()
                if p.is_file() and not any(x in p.parts for x in ['.venv','__pycache__']):
                    changes.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size})
    changes=list({x['path']:x for x in changes}.values())
    (ROOT/'reports/action3_change_manifest.json').write_text(json.dumps({'base_commit':'671c4b654cda758f2710068ca8d1fd5339c527c1',
        'files':sorted(changes,key=lambda x:x['path'])},indent=2)+'\n')
    audit={'status':'PASS_REPRODUCIBLE_COMPONENT_PACKAGE_A2_HOLD','audit_utc':datetime.now(timezone.utc).isoformat(),
        'run':str(run.relative_to(ROOT)),'component_tests':component['tests_run'],'T28_pose_step_comparisons':len(t28['per_case']),
        'original_dynamics_tests':read(legacy/'original_reproduction.json')['passed'],
        'current_internal_tests':len(read(legacy/'internal_checks.json')['checks']),
        'Pinocchio_states':read(legacy/'external_dynamics.json')['pose_count'],
        'MuJoCo_states':read(legacy/'mujoco_validation.json')['pose_count'],
        'initial_point_filter_feasibility':'FAIL_INFEASIBLE; stopped before advancing',
        'official_A2':'NOT_RUN; entry command refused with exit 2','A3':'NOT_RUN','complete_T27':'NOT_RUN','G2.5':'NOT_RUN','Level_1':'NOT_RUN',
        'preserved_source_policy_and_human_records':True}
    (ROOT/'reports/action3_release_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    def include(path):
        p=path.relative_to(ROOT)
        return path.is_file() and not any(x in ['.venv','__pycache__','git_objects','dist','build'] or x.endswith('.egg-info') for x in p.parts) and p.as_posix()!='reports/action3_artifact_index.json'
    files=sorted(p for p in ROOT.rglob('*') if include(p))
    index=[{'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    (ROOT/'reports/action3_artifact_index.json').write_text(json.dumps({'files':index,'self_hash_excluded':True},indent=2)+'\n')
    files.append(ROOT/'reports/action3_artifact_index.json')
    output=Path('/workspace/outputs');output.mkdir(exist_ok=True)
    archive=output/'IC2AI_Panda_Action3_v1.2.1_2026-11-01.zip';number=2
    while archive.exists():
        archive=output/f'IC2AI_Panda_Action3_v1.2.1_2026-11-01_r{number}.zip';number+=1
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for p in files:z.write(p,'panda_research/'+str(p.relative_to(ROOT)))
    with ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('Archive CRC failure')
        for row in index:
            if hashlib.sha256(z.read('panda_research/'+row['file'])).hexdigest()!=row['sha256']:
                raise RuntimeError('Archive member checksum failure: '+row['file'])
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'audit':audit},indent=2))


if __name__=='__main__':main()
