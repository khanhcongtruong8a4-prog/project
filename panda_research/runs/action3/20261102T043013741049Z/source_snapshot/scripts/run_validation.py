"""Run both independent model checks, preserving every run and source file."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files():
    directories = ['src', 'tests', 'scripts', 'baseline', 'inputs', 'historical',
                   'sources', 'references', 'protocol', 'reviews', 'review_sheets', 'provenance']
    result = {str(p.relative_to(ROOT)): sha(p) for directory in directories
              for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and 'git_objects' not in p.parts and not any(part.endswith('.egg-info') for part in p.parts)}
    for name in ['pyproject.toml', 'requirements.lock.txt', 'requirements-docs.txt', 'README.md', 'INTEGRATION.md', 'CHANGELOG.md']:
        result[name] = sha(ROOT/name)
    return result


def preflight():
    for row in json.loads((ROOT/'provenance/preserved_files.json').read_text()):
        if sha(ROOT/row['file']) != row['sha256']:
            raise RuntimeError('Preserved input changed: ' + row['file'])
    identity = json.loads((ROOT/'provenance/source_git_verification.json').read_text())
    if not identity['overall_pass']:
        raise RuntimeError('Pinned source identity report is not PASS')
    for row in identity['checks']:
        blob = (ROOT/'sources'/row['file']).read_bytes()
        expected_commit = ('24d85ce4e648e2e894c832bfeee9b16711eb1a1a'
                           if row['repository'].endswith('FrankaEmikaPandaDynModel')
                           else 'ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98')
        if (row['actual_commit'] != expected_commit or row['sha256'] != hashlib.sha256(blob).hexdigest()
                or row['tree_blob_sha1'] != hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()):
            raise RuntimeError('Pinned source bytes/identity differ: ' + row['file'])


def status_document(run, record):
    passed = record['status'] == 'PASS_MODEL_VALIDATION_ONLY'
    text = f'''# Combined Panda development status

Dynamics baseline: 1.2.0; Action 3 extension: 1.2.1. Latest model run: `{run.relative_to(ROOT)}`.
Result: **{record['status']}**.
Runtime code SHA256: `{sha(ROOT/'src/panda_dynamics.py')}`.

This combines the newer normalized/validated numerical API and MuJoCo suite
with pinned primary-source checks, the exact protocol cases, independent
Pinocchio validation, provenance and protocol proposals from the remediation.

'''
    if passed:
        original = json.loads((run/'original_reproduction.json').read_text())
        internal = json.loads((run/'internal_checks.json').read_text())
        pin = json.loads((run/'external_dynamics.json').read_text())
        mj = json.loads((run/'mujoco_validation.json').read_text())
        text += f'''- Original historical suite: {original['passed']}/{original['check_count']} reproduced internal checks.
- Current suite: {len(internal['checks'])} internal checks PASS; full-limit friction grid and sampled eigenvalue extrema reported.
- Pinocchio: {pin['pose_count']} state cases, {pin['checks']} quantity/pose comparisons PASS.
- MuJoCo: {mj['pose_count']} identical state cases, {len(mj['checks'])} check groups PASS, including API regressions and plant-only work-energy integration.
- Primary-source checks: 70 inertial + 21 friction values and eight joint/frame rows PASS; unsigned sheets retained in the run.
- Five isolated model-error injections detected. Selected constants and CasADi model-construction AST unchanged; flat-vector outputs exactly preserved over 154 cases.
- Protected source, inputs, historical evidence, protocol proposals and human-review records unchanged during validation.

Both engines use the same 132 expanded states plus the original 22 protocol states.
The differing test/group counts are not counts of independent experiments.
'''
    text += '''
## Research gates

| Gate | Current state |
| --- | --- |
| A1 implementation | GO |
| A2 closed-loop smoke | HOLD; see v1.2.1 policy and Action 3 report for current blockers |
| A3 comparative scenarios | NO-GO |
| Level 1 | NO-GO; verified global m1 and all theorem hypotheses remain pending |
| Publication-result claims | NO-GO |

The MuJoCo integration check is a plant-only DOP853 check, not a controller,
observer, safety-filter or control-period refinement test. This runner validates
the preserved numerical model only; Action 3 component results are separate in
reports/ACTION3_REVIEW_HANDOFF.md. No official A2, A3 comparison, complete T27,
G2.5 or interval certificate is claimed. Supplied v1.2.1 owner policy now governs
gains/C1-C6 and includes the task workbook; it does not fill missing M1 bounds,
approve the observer discretization or manufacture independent signatures.
'''
    (ROOT/'reports/DEVELOPMENT_STATUS.md').write_text(text)


def main():
    now = datetime.now(timezone.utc)
    run = ROOT/'runs'/now.strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment['PANDA_EVIDENCE_DIR'] = str(run)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    record = {'start_utc': now.isoformat(), 'run_directory': str(run.relative_to(ROOT)),
              'python': sys.version, 'platform': platform.platform(), 'executable': sys.executable,
              'packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
              'commands': [], 'scope': 'MODEL VALIDATION ONLY; not closed-loop A2 or comparative experiments'}
    before = protected_files()
    record['code_and_input_hashes'] = before
    status = 0
    def execute(name, command):
        start = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        (run/(name+'.log')).write_text(result.stdout+result.stderr)
        record['commands'].append({'name': name, 'command': command, 'cwd': str(ROOT),
            'started_utc': start, 'finished_utc': datetime.now(timezone.utc).isoformat(),
            'exit_code': result.returncode, 'log': name+'.log'})
        print(name + ': ' + ('PASS' if result.returncode == 0 else 'FAIL'), flush=True)
        if result.returncode:
            raise RuntimeError(name+' failed; inspect '+str(run/(name+'.log')))
    try:
        preflight()
        execute('source_pdf_extraction', ['pdftotext', '-layout', str(ROOT/'sources/supplement.pdf'), str(run/'supplement_layout.txt')])
        steps = [('original_reproduction','run_reproduction.py',[]),
                 ('internal_checks','run_phase3a_tests.py',[]),
                 ('primary_sources','verify_primary_sources.py',[]),
                 ('pinocchio','compare_external_dynamics.py',[]),
                 ('model_error_detection','test_reference_sensitivity.py',[]),
                 ('mujoco','review_checks.py',['--include-protocol-cases']),
                 ('integration','verify_integration.py',[])]
        for name, filename, arguments in steps:
            execute(name, [sys.executable, str(ROOT/'tests'/filename), *arguments])
        execute('dependency_check', [sys.executable, '-m', 'pip', 'check'])
        preflight()
        after = protected_files()
        if before != after:
            changed = sorted(k for k in set(before)|set(after) if before.get(k) != after.get(k))
            raise RuntimeError('Validation modified protected files: '+', '.join(changed))
        record['protected_files_unchanged'] = True
        record['status'] = 'PASS_MODEL_VALIDATION_ONLY'
    except Exception as error:
        record.update(status='FAIL', error=str(error))
        status = 1
        print(error, file=sys.stderr)
    finally:
        record['finish_utc'] = datetime.now(timezone.utc).isoformat()
        (run/'verification_run.json').write_text(json.dumps(record, indent=2)+'\n')
        pointer = {'run_directory': str(run.relative_to(ROOT)), 'status': record['status'],
                   'verification_run_sha256': sha(run/'verification_run.json')}
        temporary = ROOT/'reports/latest.json.tmp'
        temporary.write_text(json.dumps(pointer, indent=2)+'\n')
        temporary.replace(ROOT/'reports/latest.json')
        status_document(run, record)
    print('Evidence:',run)
    raise SystemExit(status)


if __name__ == '__main__':
    main()
