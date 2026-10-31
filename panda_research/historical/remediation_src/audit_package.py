"""Check evidence, preserve original identities and produce a delivery archive."""
from pathlib import Path
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads((ROOT/path).read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results=[]
    def check(name,condition):
        results.append({'check':name,'result':'PASS' if condition else 'FAIL'})
        if not condition:raise AssertionError(name)
    original=load('reports/original_reproduction.json')
    corrected=load('reports/corrected_internal_tests.json')
    check('Original 19 checks reproduced with actual exit status zero',original['exit_code']==0 and original['check_count']==19 and original['passed']==19)
    check('Historical pass/fail outcomes agree',original['historical_result_agreement'])
    check('All original checks explicitly classified internal',all(not c['external_validation'] for c in original['checks']))
    check('Corrected 19 checks pass',len(corrected['checks'])==19 and corrected['overall_pass'])
    check('Maximum eigenvalue computed and positive',isinstance(corrected['max_sampled_joint_inertia_eigenvalue'],float) and corrected['max_sampled_joint_inertia_eigenvalue']>0)
    check('Full-limit friction grid inclusive for each joint',corrected['friction_grid']['points_per_joint']==261 and corrected['friction_grid']['max_rad_s']==[2.175]*4+[2.61]*3)
    ext=load('reports/external_dynamics.json')
    cases=load('reports/external_cases.json')
    check('22 exact external cases and case digest',len(cases['cases'])==22 and ext['case_file_sha256']==digest(ROOT/'reports/external_cases.json'))
    check('594 external quantity/pose comparisons completed',ext['overall_pass'] and len(ext['per_case'])==594 and len(ext['summary'])==27)
    for r in ext['per_case']:
        a=np.asarray(r['observed']);b=np.asarray(r['reference'])
        threshold=r['abs_tolerance']+r['rel_tolerance']*np.abs(b)
        error=np.abs(a-b)
        if not (np.all(np.isfinite(error)) and np.all(error<=threshold) and r['result']=='PASS'):
            raise AssertionError(f"External report recheck failed for {r['pose_index']}/{r['quantity']}")
    check('External numeric diagnostics independently re-evaluated from stored component values',True)
    check('Raw C matrices not compared',ext['raw_C_matrix_compared'] is False)
    for name,count in [('T04b_inertial_70.csv',70),('T04b_friction_21.csv',21),('T06a_joint_frames_8.csv',8)]:
        with (ROOT/'review_sheets'/name).open() as f:rows=list(csv.DictReader(f))
        check(name+' exact row count',len(rows)==count)
        check(name+' reviewer fields blank',all(not r['reviewer_name'] and not r['reviewer_date'] and not r['reviewer_signature'] and r['human_acceptance']=='PENDING SIGNATURE' for r in rows))
    check('Primary source comparisons pass',load('reports/primary_source_checks.json')['overall_pass'])
    controls=load('reports/reference_sensitivity.json')
    check('Five deliberately corrupted models detected',len(controls['controls'])==5 and controls['overall_pass'])
    check('Physical model executable AST unchanged',load('reports/evaluator_semantics.json')['same_executable_AST'])
    baseline=load('reports/baseline_hashes.json')
    for r in baseline['zip_members']:check('Unchanged baseline '+r['file'],digest(ROOT/'baseline'/r['file'])==r['sha256'])
    for r in baseline['uploaded_inputs']:
        check('Unchanged input copy '+r['name'],digest(ROOT/'inputs'/r['name'])==r['sha256'])
        original_path=Path(r['path'])
        if original_path.exists():check('Unchanged original attachment '+r['name'],digest(original_path)==r['sha256'])
    m=load('baseline/model_manifest_v1.json')
    claims=[]
    for field,path in [('module_sha256','baseline/panda_dynamics.py'),('test_script_sha256','baseline/run_phase3a_tests.py'),('numerical_report_sha256','baseline/phase3a_test_report.json')]:
        actual=digest(ROOT/path)
        check('Manifest '+field,m[field]==actual)
        claims.append({'field':field,'expected':m[field],'actual':actual,'result':'PASS'})
    check('Original protocol matches manifest input hash',digest(ROOT/'inputs/Action_2026-10-31.docx')==m['input_file_sha256']['Action_2026-10-31.docx'])
    claims.append({'field':'canonical_config_sha256','result':'NOT_RECOMPUTED',
                   'reason':'Original canonical serialization/artifact not supplied; this digest is not treated as an independently reproduced experiment freeze'})
    (ROOT/'reports/manifest_hash_claims.json').write_text(json.dumps(claims,indent=2)+'\n')
    check('Original approvals remain null',all(v is None for v in m['approvals'].values()))
    identity=load('reports/source_git_verification.json')
    check('All nine pinned source and attribution files verified',identity['overall_pass'] and len(identity['checks'])==9)
    for row in identity['checks']:
        blob=(ROOT/'sources'/row['file']).read_bytes()
        check('Pinned source '+row['file'],row['actual_commit']==row['expected_commit']
              and row['tree_blob_sha1']==hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
              and row['sha256']==hashlib.sha256(blob).hexdigest())
    proposal=load('protocol/proposed_frozen_configuration.json')
    check('Proposed freeze unapproved and incomplete',all(v is None for v in proposal['approvals'].values()) and proposal['margin_mode']['constant_values'] is None)
    check('Scenario B proposal hash fixed before comparative runs',proposal['scenario_B']['sha256']==digest(ROOT/'protocol/scenario_b_target_suite_PROPOSED.json') and not load('protocol/scenario_b_target_suite_PROPOSED.json')['comparison_runs_executed'])
    check('No A2 performed',proposal['integration']['A2_executed'] is False)
    check('All model-workflow commands succeeded',load('reports/verification_run.json')['status']=='PASS_MODEL_EVIDENCE_WORKFLOW_ONLY' and all(r['exit_code']==0 for r in load('reports/verification_run.json')['commands']))
    for name in ['protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.docx','review_sheets/HUMAN_REVIEW_SIGNATURES.docx']:
        with ZipFile(ROOT/name) as z:
            check('Valid DOCX archive '+name,z.testzip() is None)
            ET.fromstring(z.read('word/document.xml'))
    for name in ['README.md','CHANGELOG.md','reports/REVIEWER_RESPONSE.md','reports/reviewer_issue_disposition.csv',
                 'protocol/unresolved_decisions.csv','reports/stage_gates.json','requirements.lock.txt']:
        check('Required deliverable '+name,(ROOT/name).is_file() and (ROOT/name).stat().st_size>0)
    (ROOT/'reports/package_audit.json').write_text(json.dumps({'audit_utc':datetime.now(timezone.utc).isoformat(),
        'overall_pass':True,'check_count':len(results),'checks':results},indent=2)+'\n')
    def included(path):
        relative=path.relative_to(ROOT)
        return path.is_file() and '.venv' not in relative.parts and '__pycache__' not in relative.parts and 'git_objects' not in relative.parts and relative.as_posix()!='reports/artifact_index.json'
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    index=[{'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in files]
    (ROOT/'reports/artifact_index.json').write_text(json.dumps({'exclusions':['.venv','__pycache__','sources/git_objects','artifact_index.json itself'],
        'files':index},indent=2)+'\n')
    files.append(ROOT/'reports/artifact_index.json')
    output=ROOT.parent/'outputs'
    output.mkdir(exist_ok=True)
    archive=output/'IC2AI_2027_Reviewer_Remediation_2026-11-01.zip'
    suffix=2
    while archive.exists():
        archive=output/f'IC2AI_2027_Reviewer_Remediation_2026-11-01_r{suffix}.zip';suffix+=1
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for p in files:z.write(p,'IC2AI_2027_Remediation/'+str(p.relative_to(ROOT)))
    with ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('Delivery ZIP integrity failure')
        saved=json.loads(z.read('IC2AI_2027_Remediation/reports/artifact_index.json'))
        for row in saved['files']:
            if hashlib.sha256(z.read('IC2AI_2027_Remediation/'+row['file'])).hexdigest()!=row['sha256']:
                raise RuntimeError('Delivery ZIP member hash mismatch: '+row['file'])
    checksum=digest(archive)
    archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n')
    print(json.dumps({'audit':'PASS','checks':len(results),'archive':str(archive),'members':len(files),
        'bytes':archive.stat().st_size,'sha256':checksum,'archive_member_hashes_verified':True},indent=2))


if __name__=='__main__':main()
