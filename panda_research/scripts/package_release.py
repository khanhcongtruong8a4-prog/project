"""Audit and archive the combined project after a passing validation run."""
from pathlib import Path
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED
import csv
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    checks = []
    def check(name, condition):
        checks.append({'check': name, 'result': 'PASS' if condition else 'FAIL'})
        if not condition:
            raise RuntimeError(name)
    pointer = read(ROOT/'reports/latest.json')
    run = ROOT/pointer['run_directory']
    record = read(run/'verification_run.json')
    check('Latest model validation PASS', pointer['status'] == record['status'] == 'PASS_MODEL_VALIDATION_ONLY')
    check('Latest run identity matches pointer', sha(run/'verification_run.json') == pointer['verification_run_sha256'])
    check('Every underlying command exited successfully', all(x['exit_code'] == 0 for x in record['commands']))
    check('Validation did not modify protected files', record['protected_files_unchanged'])
    for name, expected in record['code_and_input_hashes'].items():
        check('Validated file unchanged: '+name, sha(ROOT/name) == expected)
    current = read(ROOT/'provenance/development_manifest.json')
    check('Development runtime identity current', current['development_evaluator_sha256'] == sha(ROOT/'src/panda_dynamics.py'))
    original, internal = read(run/'original_reproduction.json'), read(run/'internal_checks.json')
    pin, mj = read(run/'external_dynamics.json'), read(run/'mujoco_validation.json')
    check('Original 19 checks reproduced', original['check_count'] == original['passed'] == 19)
    check('Current 19 internal checks pass', internal['overall_pass'] and len(internal['checks']) == 19)
    check('Pinocchio 154-case checks pass', pin['overall_pass'] and pin['pose_count'] == 154 and pin['checks'] == 154*27)
    check('MuJoCo 58 groups on 154 cases pass', mj['overall_pass'] and mj['pose_count'] == 154 and len(mj['checks']) == 58)
    check('API 81 shape variants pass', mj['checks']['API: acceleration shape variants']['comparisons'] == 81 and mj['checks']['API: acceleration shape variants']['passed'])
    check('API 51 invalid-input cases rejected', mj['checks']['API: reject malformed and nonfinite inputs']['cases'] == mj['checks']['API: reject malformed and nonfinite inputs']['rejected'] == 51)
    check('Integration and reference provenance pass', read(run/'integration_checks.json')['overall_pass'])
    check('Five physical-model errors detected', read(run/'reference_sensitivity.json')['overall_pass'])
    check('Primary source comparisons pass', read(run/'primary_source_checks.json')['overall_pass'])
    for name, count in [('T04b_inertial_70.csv', 70), ('T04b_friction_21.csv', 21), ('T06a_joint_frames_8.csv', 8)]:
        with (run/'review_sheets'/name).open() as stream:
            rows = list(csv.DictReader(stream))
        check('Unsigned review rows: '+name, len(rows) == count and all(not r['reviewer_signature'] and r['human_acceptance'] == 'PENDING SIGNATURE' for r in rows))
    check('MuJoCo per-comparison diagnostics checksum', mj['per_comparison_details']['sha256'] == sha(run/mj['per_comparison_details']['file']))
    proposal = read(ROOT/'protocol/proposed_frozen_configuration.json')
    check('Proposed protocol references current runtime', proposal['working_evaluator_sha256'] == sha(ROOT/'src/panda_dynamics.py'))
    check('No fabricated approval or A2 execution', all(x is None for x in proposal['approvals'].values()) and not proposal['integration']['A2_executed'])
    audit = {'audit_utc': datetime.now(timezone.utc).isoformat(), 'overall_pass': True,
             'check_count': len(checks), 'checks': checks, 'validated_run': str(run.relative_to(ROOT)),
             'gate_status': {'A1': 'GO', 'A2': 'BLOCKED', 'A3': 'NO-GO', 'Level_1': 'NO-GO', 'publication_results': 'NO-GO'}}
    (ROOT/'reports/release_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    def include(path):
        relative = path.relative_to(ROOT)
        return (path.is_file() and not any(part in ['.venv','__pycache__','git_objects','build','dist'] or part.endswith('.egg-info') for part in relative.parts)
                and relative.as_posix() != 'reports/artifact_index.json')
    files = sorted(p for p in ROOT.rglob('*') if include(p))
    index = [{'file': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files]
    (ROOT/'reports/artifact_index.json').write_text(json.dumps({'exclusions': ['.venv','__pycache__','git_objects','*.egg-info','build','dist','artifact index itself'], 'files': index}, indent=2)+'\n')
    files.append(ROOT/'reports/artifact_index.json')
    # Keep release artifacts outside the source tree so re-packaging never
    # recursively includes an earlier archive. Existing releases are preserved.
    output = Path('/workspace/outputs') if Path('/workspace/outputs').is_dir() else ROOT.parent/'releases'
    output.mkdir(exist_ok=True)
    archive = output/'IC2AI_Panda_Combined_v1.2.0_2026-11-01.zip'
    suffix = 2
    while archive.exists():
        archive = output/f'IC2AI_Panda_Combined_v1.2.0_2026-11-01_r{suffix}.zip'
        suffix += 1
    with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, 'panda_research/'+str(p.relative_to(ROOT)))
    with ZipFile(archive) as z:
        check('Release ZIP member CRCs', z.testzip() is None)
        for row in index:
            if hashlib.sha256(z.read('panda_research/'+row['file'])).hexdigest() != row['sha256']:
                raise RuntimeError('Archive hash mismatch: '+row['file'])
    checksum = sha(archive)
    archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n')
    print(json.dumps({'status': 'PASS_RELEASE_AUDIT', 'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': checksum, 'files': len(files), 'validated_run': str(run.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
