"""Read the current numerical A2 gate and fail closed on missing/changed evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import json
import importlib.metadata
from panda_closed_loop.config import digest
from panda_closed_loop.p1_r4 import numerical_gate


def status():
    pointer = json.loads((ROOT/'reports/a2_current.json').read_text())
    run = (ROOT/pointer['run_directory']).resolve()
    if not run.is_relative_to((ROOT/'runs/p1_r4').resolve()):
        raise ValueError('Unexpected current run path')
    for name, sha in pointer['evidence_sha256'].items():
        if digest(run/name) != sha:
            raise ValueError('Current evidence hash mismatch: '+name)
    start = json.loads((run/'run_started.json').read_text())
    end = json.loads((run/'run_completed.json').read_text())
    manifest_path = ROOT/'policy/v1.2.2-r4/FROZEN_INPUTS.json'
    if digest(manifest_path) != start['manifest_sha256']:
        raise ValueError('Current freeze differs from qualified freeze')
    freeze = json.loads(manifest_path.read_text())
    if any(digest(ROOT/n) != h for n, h in freeze['files'].items()):
        raise ValueError('A qualified input or retained source trace changed')
    if end['exit_code'] != 0 or not end['frozen_inputs_unchanged']:
        raise ValueError('Qualification did not complete with unchanged inputs')
    plan_path = ROOT/'policy/v1.2.2-r4/PREDECLARED_A2_R4.json'
    if digest(plan_path) != start['plan_sha256']:
        raise ValueError('Qualified numerical plan changed')
    plan = json.loads(plan_path.read_text())
    if any(importlib.metadata.version(n) != v for n, v in plan['required_versions'].items()):
        raise ValueError('Current package versions differ from the qualified versions')
    summary = json.loads((run/'summary.json').read_text())
    for cell in summary['cells']:
        for phase in ['prehold', 'a2']:
            trace = cell[phase]['trace']
            if digest(run/trace['file']) != trace['sha256']:
                raise ValueError('Qualified trace changed')
    gate = numerical_gate(summary['cells'], plan, summary['engineering'])
    if gate != json.loads((run/'gate.json').read_text()):
        raise ValueError('Recomputed gate differs from recorded gate')
    return gate


if __name__ == '__main__':
    try:
        gate = status()
        print(json.dumps(gate, indent=2))
        raise SystemExit(0 if gate['status'] == 'GO' else 3)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(json.dumps({'status': 'HOLD', 'scope': 'NUMERICAL_A2', 'integrity_error': str(error)}, indent=2))
        raise SystemExit(1)
