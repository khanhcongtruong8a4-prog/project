"""Frozen r4 numerical A2: original C4 grid plus mandatory confirmation grid.

The r3 failure remains immutable. Exit 0 requires audited numerical GO;
exit 3 retains a scientific HOLD and exit 1 denotes an engineering error.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import traceback
import numpy as np
from case_sets import all_cases
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.p1_r4 import AB2TorqueController, audit_cell, numerical_gate

PLAN = 'policy/v1.2.2-r4/PREDECLARED_A2_R4.json'
FREEZE = 'policy/v1.2.2-r4/FROZEN_INPUTS.json'
spec = importlib.util.spec_from_file_location('preserved_r3_runner', ROOT/'scripts/p1_r3.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def verify():
    freeze = json.loads((ROOT/FREEZE).read_text())
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(ROOT/FREEZE)], cwd=ROOT, text=True).strip()
    if not commit or subprocess.check_output(['git', 'show', f'{commit}:panda_research/{FREEZE}'], cwd=ROOT) != (ROOT/FREEZE).read_bytes():
        raise ValueError('Commit the complete new freeze before tests')
    if any(digest(ROOT/n) != h for n, h in freeze['files'].items()):
        raise ValueError('A frozen r4 or previous input changed')
    plan = json.loads((ROOT/PLAN).read_text())
    policy = Policy.load()
    if (plan['C4_grid'][:4] != policy.raw['integration']['validation_grid']
            or plan['fixed_acceptance_thresholds'] != policy.raw['fixed_acceptance_thresholds']):
        raise ValueError('The original C4 grid or thresholds changed')
    return plan, freeze, commit


def verify_regression_evidence():
    """Reuse the completed unchanged-input regression; do not invent a rerun."""
    folder = ROOT/'reports/p1_v1.2.2_r3/engineering'
    action = json.loads((folder/'action3/run.json').read_text())
    baseline = json.loads((folder/'legacy/verification_run.json').read_text())
    if action['status'] != 'PASS_COMPONENTS_AND_REGRESSIONS_A2_HOLD' or baseline['status'] != 'PASS_MODEL_VALIDATION_ONLY':
        return False
    # The new implementation has its own contracts. Every input that the old
    # component/model regressions exercised must still have the recorded hash.
    hashes = {**action['code_and_input_hashes'], **baseline['code_and_input_hashes']}
    return bool(hashes) and all(digest(ROOT/n) == h for n, h in hashes.items())


def load_saved_cell(out, index):
    """Audit the serialized evidence boundary, not NumPy-containing objects."""
    return json.loads((out/f'cell_{index}.json').read_text())


def validate_reuse(source, plan):
    """Allow audit repair without pretending that motion was rerun.

    Only this runner's evidence-interface code and its tests may differ.
    Every physical-model, controller, numerical-gate and plan byte must match
    the actual execution's preserved inventory. Trace hashes are checked by
    the same unchanged audit. Partial/missing grids cannot be reused.
    """
    source = source.resolve()
    if not source.is_relative_to((ROOT/'runs/p1_r4').resolve()):
        raise ValueError('Retained execution must be under runs/p1_r4')
    start = json.loads((source/'run_started.json').read_text())
    end = json.loads((source/'run_completed.json').read_text())
    if not end['frozen_inputs_unchanged'] or start['plan_sha256'] != digest(ROOT/PLAN):
        raise ValueError('Retained execution has changed inputs or a different plan')
    old = json.loads((source/'source_snapshot'/FREEZE).read_text())
    interface_files = {'scripts/p1_r4.py', 'tests/test_p1_r4.py'}
    changed = [n for n, h in old['files'].items() if n not in interface_files and digest(ROOT/n) != h]
    if changed:
        raise ValueError('Retained physical/controller input differs: '+', '.join(changed))
    if any(start['packages'].get(n) != v or importlib.metadata.version(n) != v
           for n, v in plan['required_versions'].items()):
        raise ValueError('Retained execution package versions differ')
    for index, grid in enumerate(plan['C4_grid']):
        if load_saved_cell(source, index)['grid'] != grid:
            raise ValueError('Retained physical cell grid differs')
    return {'source_run': str(source.relative_to(ROOT)), 'source_freeze_commit': start['freeze_commit'],
            'source_started_sha256': digest(source/'run_started.json'),
            'source_completed_sha256': digest(source/'run_completed.json'),
            'matching_original_inputs': len(old['files'])-len(interface_files),
            'allowed_evidence_interface_changes': sorted(interface_files),
            'controller_model_plan_and_threshold_bytes_unchanged': True,
            'physical_simulation_reexecuted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--contracts', type=Path, required=True)
    parser.add_argument('--reuse-executed-cells', type=Path,
                        help='Requalify a complete identical-input execution after an evidence-interface repair')
    args = parser.parse_args()
    plan, freeze, commit = verify()
    reuse = validate_reuse(args.reuse_executed_cells, plan) if args.reuse_executed_cells else None
    contracts = json.loads(args.contracts.read_text())
    contracts_pass = (contracts.get('overall_pass') is True and contracts.get('tests_run', 0) >= 12
                      and len(contracts.get('checks', [])) == contracts.get('tests_run')
                      and all(c.get('result') == 'PASS' for c in contracts.get('checks', []))
                      and contracts.get('source_sha256') == digest(ROOT/'src/panda_closed_loop/p1_r4.py')
                      and contracts.get('test_sha256') == digest(ROOT/'tests/test_p1_r4.py')
                      and contracts.get('plan_sha256') == digest(ROOT/PLAN))
    if not contracts_pass:
        raise ValueError('Passing contract evidence for the frozen source/tests/plan is required')
    out = (args.output or ROOT/'runs/p1_r4'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    if not out.is_relative_to((ROOT/'runs/p1_r4').resolve()):
        raise ValueError('Use runs/p1_r4 for exclusive evidence')
    out.mkdir(parents=True, exist_ok=False)
    policy = Policy.load()
    metadata = {'start_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'USER_AUTHORIZED_A2_NUMERICAL_R4',
                'command': [sys.executable, *sys.argv], 'cwd': str(ROOT), 'python': sys.version,
                'platform': platform.platform(), 'freeze_commit': commit,
                'plan_sha256': digest(ROOT/PLAN), 'manifest_sha256': digest(ROOT/FREEZE),
                'packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
                'prior_failures_preserved': True, 'independent_signatures': None,
                'parameter_or_threshold_retuning_after_freeze': False,
                'physical_execution_provenance': reuse or {'physical_simulation_reexecuted': True}}
    legacy.write(out/'run_started.json', metadata)
    legacy.write(out/'contracts.json', contracts)
    for n in freeze['new_files']+[FREEZE]:
        target = out/'source_snapshot'/n
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/n, target)
    cells, error, code = [], None, 1
    try:
        audit = policy.source_audit()
        legacy.write(out/'source_audit.json', audit)
        system = build_components(policy)
        original, expanded = system.geometry.function, system.geometry.function.expand()
        poses = []
        for index, q in enumerate(all_cases()[0]):
            a, b = original(q), expanded(q)
            equal = all(np.array_equal(x, y) for x, y in zip(a, b))
            poses.append({'index': index, 'q': q, 'all_outputs_bitwise_equal': equal})
            if not equal:
                raise ValueError('Geometry backend mismatch before cells')
        legacy.write(out/'geometry_equivalence.json', {'poses': poses, 'passed': len(poses) == 154})
        system.geometry.function = expanded
        for index, grid in enumerate(plan['C4_grid']):
            try:
                # Each cell has fresh history; its own preparation swaps in the
                # unchanged startup controller and does not consume this history.
                local = replace(system, controller=AB2TorqueController(system.controller))
                if reuse:
                    source = args.reuse_executed_cells.resolve()
                    cell = load_saved_cell(source, index)
                    shutil.copy2(source/f'cell_{index}.json', out/f'cell_{index}.json')
                    for phase in ['prehold', 'a2']:
                        record = cell.get(phase, {}).get('trace')
                        if record:
                            shutil.copy2(source/record['file'], out/record['file'])
                else:
                    legacy.run_cell(local, plan, index, out)
                cell = load_saved_cell(out, index)
                if cell.get('a2', {}).get('completed'):
                    cell['audit'] = audit_cell(cell, out, system, plan)
                else:
                    cell['audit'] = {'passed': False, 'reason': 'INCOMPLETE_CELL'}
                legacy.write(out/f'cell_{index}_audit.json', cell['audit'])
                cells.append(cell)
                print(f"cell {index}: evidence audit {'PASS' if cell['audit']['passed'] else 'FAIL'}", flush=True)
            except Exception:
                cell = {'cell': index, 'grid': grid, 'engineering_error': traceback.format_exc(),
                        'a2': {'completed': False, 'passed': False}, 'audit': {'passed': False}}
                legacy.write(out/f'cell_{index}_engineering_error.json', cell)
                cells.append(cell)
                print(f'cell {index}: ENGINEERING_ERROR', flush=True)
        engineering = {
            'frozen_inputs_unchanged': all(digest(ROOT/n) == h for n, h in freeze['files'].items()),
            'contracts_pass': contracts_pass,
            'base_regressions_match_current_inputs': verify_regression_evidence(),
            'geometry_equivalence_pass': len(poses) == 154,
            'pinned_versions_match': all(importlib.metadata.version(n) == v for n, v in plan['required_versions'].items()),
            'canonical_model_audit_pass': audit['canonical_equations_match']}
        gate = numerical_gate(cells, plan, engineering)
        legacy.write(out/'gate.json', gate)
        legacy.write(out/'summary.json', {'freeze_commit': commit, 'plan_sha256': digest(ROOT/PLAN),
                     'cells': cells, 'engineering': engineering, 'gate': gate,
                     'previous_r3_A2_result': 'FAIL_PRESERVED', 'retuning_performed': False})
        code = 1 if any('engineering_error' in c for c in cells) else 0 if gate['status'] == 'GO' else 3
        print('Numerical A2 gate:', gate['status'], flush=True)
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
    finally:
        changed = [n for n, h in freeze['files'].items() if digest(ROOT/n) != h]
        if changed:
            code = 1
        metadata.update(finish_utc=datetime.now(timezone.utc).isoformat(), exit_code=code,
                        frozen_inputs_unchanged=not changed, changed_inputs=changed, engineering_error=error)
        legacy.write(out/'run_completed.json', metadata)
    print('Evidence:', out, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
