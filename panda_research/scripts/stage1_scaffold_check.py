"""Inspect Stage 1 scaffold dependencies; never run an optimizer or comparison."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import subprocess
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import digest
from panda_closed_loop.stage1_scaffold import Stage1Scaffold


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    system = build_components()
    record = Stage1Scaffold(system).readiness()
    record.update(recorded_utc=datetime.now(timezone.utc).isoformat(),
                  git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  source_sha256=digest(ROOT/'src/panda_closed_loop/stage1_scaffold.py'),
                  test_sha256=digest(ROOT/'tests/test_stage1_scaffold.py'),
                  approved_model_sha256=digest(ROOT/'src/panda_dynamics.py'),
                  policy_sha256=digest(system.policy.path), python=sys.version, platform=platform.platform(),
                  packages={n: importlib.metadata.version(n) for n in ['numpy', 'scipy', 'casadi']},
                  command=[sys.executable, *sys.argv], cwd=str(ROOT),
                  verification_status='STATICALLY_CHECKED_AND_UNIT_TESTED_SCAFFOLD; OFFICIAL_SOLVE_NOT_VERIFIED')
    with args.report.open('x') as f:
        json.dump(record, f, indent=2)
        f.write('\n')
    print(json.dumps({'Stage1': record['status'], 'blocker_count': len(record['blockers']),
                      'official_solver_executed': False, 'report': str(args.report)}, indent=2))


if __name__ == '__main__':
    main()
