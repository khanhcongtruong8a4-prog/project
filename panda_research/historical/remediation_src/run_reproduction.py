"""Re-run original tests in a copy; baseline/ and historical results stay intact."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def classification(index):
    if index in (0, 1):
        return 'INTERNAL_LITERAL_REGRESSION'
    if index in (4, 5, 6):
        return 'INTERNAL_SHARED_KINEMATIC_IMPLEMENTATION'
    if index in (9, 10, 14):
        return 'INTERNAL_SHARED_DERIVATIVE_IDENTITY'
    if index in (11, 12):
        return 'INTERNAL_SHARED_MODEL_FINITE_DIFFERENCE'
    return 'INTERNAL_NUMERICAL_OR_ANALYTIC_CORROBORATION'


def main():
    run_dir = ROOT / 'runs' / 'original'
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in ('panda_dynamics.py', 'run_phase3a_tests.py'):
        shutil.copy2(ROOT / 'baseline' / name, run_dir / name)
    command = [sys.executable, str(run_dir / 'run_phase3a_tests.py')]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=run_dir, capture_output=True, text=True)
    (ROOT / 'logs/original_reproduction.log').write_text(result.stdout + result.stderr)
    old = json.loads((ROOT / 'baseline/phase3a_test_report.json').read_text())
    output = run_dir / 'phase3a_test_report.json'
    report = {'command': command, 'cwd': str(run_dir), 'start_utc': started,
              'finish_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
              'environment': {'python': sys.version, 'platform': platform.platform()},
              'scope': 'REPRODUCED INTERNAL CHECKS, not external dynamics validation or human sign-off',
              'source_copies_sha256': {n: hashlib.sha256((run_dir / n).read_bytes()).hexdigest()
                                       for n in ('panda_dynamics.py', 'run_phase3a_tests.py')}}
    if result.returncode == 0 and output.exists():
        fresh = json.loads(output.read_text())
        report['raw_result'] = str(output.relative_to(ROOT))
        report['environment']['libraries'] = fresh['environment']
        report['checks'] = []
        for index, (a, b) in enumerate(zip(old['checks'], fresh['checks'])):
            report['checks'].append({'original_test': b['test'], 'result': b['result'],
                'measured_max': b['measured_max'], 'threshold': b['pass_threshold'],
                'historical_measured_max': a['measured_max'], 'historical_result': a['result'],
                'evidence_class': classification(index), 'external_validation': False})
        report['check_count'] = len(fresh['checks'])
        report['passed'] = sum(c['result'] == 'PASS' for c in fresh['checks'])
        report['historical_result_agreement'] = all(a['result'] == b['result'] and a['test'] == b['test']
            for a, b in zip(old['checks'], fresh['checks'])) and len(old['checks']) == len(fresh['checks'])
        report['status'] = 'PASS_REPRODUCED_INTERNAL_ONLY' if fresh['overall_pass'] else 'FAIL'
    else:
        report['status'] = 'FAILED_TO_REPRODUCE'
    (ROOT / 'reports/original_reproduction.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
