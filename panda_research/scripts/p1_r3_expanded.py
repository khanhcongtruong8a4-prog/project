"""Recorded geometry execution-backend amendment; frozen r3 law is unchanged.

Expand the identical CasADi MX expression into scalar SX operations. Require
bitwise equality of every geometry output on all 154 retained regression poses
before running the original frozen runner. No changed tolerances or dynamics.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import shutil
import subprocess
from time import perf_counter
import numpy as np
from case_sets import all_cases
from panda_closed_loop.config import digest

MANIFEST = 'policy/v1.2.2-r3/BACKEND_FROZEN_INPUTS.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    freeze = json.loads((ROOT/MANIFEST).read_text())
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(ROOT/MANIFEST)], cwd=ROOT, text=True).strip()
    committed = subprocess.check_output(['git', 'show', f'{commit}:panda_research/{MANIFEST}'], cwd=ROOT)
    if committed != (ROOT/MANIFEST).read_bytes():
        raise ValueError('Backend amendment must be committed before testing')
    for name, sha in freeze['files'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Backend frozen input changed: '+name)
    out = (args.output or ROOT/'runs/p1_r3'/datetime.now(timezone.utc).strftime('expanded_%Y%m%dT%H%M%S%fZ')).resolve()
    if not out.is_relative_to((ROOT/'runs/p1_r3').resolve()) or out.exists():
        raise ValueError('Use a fresh runs/p1_r3 output')
    spec = importlib.util.spec_from_file_location('frozen_r3_runner', ROOT/'scripts/p1_r3.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.verify_freeze()
    build = runner.build_components
    backend_record = {'scope': 'GEOMETRY_EXECUTION_BACKEND_EQUIVALENCE_NOT_INDEPENDENT_MODEL_VALIDATION',
                      'amendment_commit': commit, 'manifest_sha256': digest(ROOT/MANIFEST),
                      'controller_or_policy_values_changed': False, 'poses': [], 'passed': False}

    def expanded_components(policy):
        system = build(policy)
        original = system.geometry.function
        start = perf_counter()
        expanded = original.expand()
        backend_record['expansion_s'] = perf_counter()-start
        for i, q in enumerate(all_cases()[0]):
            start = perf_counter()
            a = original(q)
            original_s = perf_counter()-start
            start = perf_counter()
            b = expanded(q)
            expanded_s = perf_counter()-start
            errors = [float(np.max(abs(np.asarray(x)-np.asarray(y)))) for x, y in zip(a, b)]
            same = all(np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a, b))
            backend_record['poses'].append({'index': i, 'q': q, 'bitwise_equal_all_five_outputs': same,
                                           'max_absolute_errors': errors,
                                           'original_runtime_s': original_s, 'expanded_runtime_s': expanded_s})
            if not same:
                raise ValueError(f'Expanded geometry differs at retained pose {i}; no numerical run permitted')
            if (i+1) % 22 == 0:
                print(f'geometry equivalence: {i+1}/154 bitwise PASS', flush=True)
        backend_record['passed'] = len(backend_record['poses']) == 154
        if not backend_record['passed']:
            raise ValueError('Missing geometry equivalence cases')
        system.geometry.function = expanded
        return system

    runner.build_components = expanded_components
    # Keep the original CLI, exclusivity, immutable traces and actual exit code.
    sys.argv = [sys.argv[0], '--output', str(out)]
    code = 1
    try:
        code = runner.main()
    finally:
        if out.exists():
            runner.write(out/'backend_validation.json', backend_record)
            for name in list(freeze['files'])+[MANIFEST]:
                target = out/'backend_snapshot'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/name, target)
            if any(digest(ROOT/name) != sha for name, sha in freeze['files'].items()):
                raise ValueError('Backend input changed during execution')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
