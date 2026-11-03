"""Separately predeclared alpha_v=10 ACTIVE challenge, unchanged AB2 runtime.

This harder half-second E3 is NOT a replacement for any frozen A2 cell and
is NOT a new controller candidate. All actual torques use the final guarded
QP, the original strict checks and the identical held plant/DOB input.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
import argparse, copy, hashlib, json, subprocess, traceback
from dataclasses import replace
from datetime import datetime, timezone
import numpy as np
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.guarded_qp_final_v1 import BoundedGuardedQP
from panda_closed_loop.a2_qp_reliable_v1 import NUMERICAL_POLICY
from panda_closed_loop.guarded_qp_native_v1 import backend_record
from panda_closed_loop.p1_r3 import compare_refinement
from panda_closed_loop.logging import json_values
from panda_closed_loop.a2_acceptance import read_recorded_trace
from reproduce_a2_acceptance import import_script

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, d):
    with Path(p).open('x') as f:
        json.dump(json_values(d), f, indent=2, allow_nan=False); f.write('\n')

def verify():
    path = ROOT/'policy/active_sampled_data_v1/ALPHA10_CHALLENGE_FREEZE.json'
    frozen = json.loads(path.read_text())
    for name, expected in frozen['implementation_sha256'].items():
        if sha(ROOT/name) != expected: raise ValueError('Challenge source changed: '+name)
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(path)], cwd=ROOT, text=True).strip()
    if not commit or subprocess.check_output(['git', 'show', commit+':panda_research/'+str(path.relative_to(ROOT))], cwd=ROOT) != path.read_bytes():
        raise ValueError('Commit challenge freeze before running')
    contract = json.loads((ROOT/'policy/active_sampled_data_v1/BASELINE_HYPOTHESIS_CONTRACT.json').read_text())
    if backend_record()['library_sha256'] != contract['native_solver_sha256']: raise ValueError('Changed solver binary')
    return contract, commit

def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    contract, commit = verify()
    module = import_script('challenge_frozen_v4', 'a2_extended_v4.py')
    original, _, original_commit = module.verify()
    plan = copy.deepcopy(original)
    challenge = contract['intended_alpha10_active_challenge']
    ratio = challenge['duration_s']/original['references']['E3']['duration_s']
    plan['references']['E3']['duration_s'] = challenge['duration_s']
    plan['A2_reference']['duration_s'] = challenge['duration_s']
    plan['reference_screen_times_s'] = [float(t*ratio) for t in original['reference_screen_times_s']]
    assert plan['C4_grid'] == challenge['grid']
    assert plan['fixed_acceptance_thresholds'] == contract['original_fixed_acceptance_thresholds']
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    write(out/'run_started.json', {'start_utc':datetime.now(timezone.utc).isoformat(), 'freeze_commit':commit,
        'original_v4_freeze_commit':original_commit, 'scope':'SEPARATE_HARDER_ACTIVE_ALPHA10_AB2_CHALLENGE_NOT_A2_OR_A3',
        'not_a_runtime_candidate':True, 'plan':plan, 'backend':backend_record(), 'python':sys.version,
        'physical_model_gains_disturbance_guards_thresholds_changed':False, 'reference_duration_changed_only_in_new_case':True,
        'independent_signatures':None})
    system = build_amended_system(); system.geometry.function = system.geometry.function.expand(); cells=[]
    for index in range(4):
        try:
            with BoundedGuardedQP(system.barriers.taumax, NUMERICAL_POLICY, plan['QP_wall_time_budget_s']) as qp:
                cells.append(module.run_cell(replace(system, qp=qp), plan, 'E3', index, out))
        except Exception:
            failed={'cell':index,'engineering_error':traceback.format_exc(),'a2':{'completed':False,'passed':False},'audit':{'passed':False}}
            write(out/f'cell_{index}_engineering_error.json', failed); cells.append(failed)
    nontrivial=[]
    for cell in cells:
        updates = read_recorded_trace(out,cell['a2']['trace'])['updates'] if 'trace' in cell['a2'] else []
        I = np.array([np.linalg.norm(np.array(u['candidate_tau'])-u['u_nom']) for u in updates if u['strict_pass']])
        peak = float(np.max(I)) if len(I) else None
        active_duration = float(np.count_nonzero(I>0.001)*plan['C4_grid'][cell['cell']]['control_period_s'])
        nontrivial.append({'cell':cell['cell'],'peak_tau_minus_u_Nm':peak,'duration_above_0p001_Nm_s':active_duration,
                          'passed':bool(peak is not None and peak>0.01 and active_duration>=0.005)})
    refinement = compare_refinement(cells,plan['fixed_acceptance_thresholds'])
    physics = all(c['a2'].get('passed',False) and c['audit'].get('passed',False) for c in cells)
    passed = bool(physics and all(c['passed'] for c in nontrivial) and refinement['passed'])
    write(out/'summary.json',{'cells':cells,'nontriviality':nontrivial,'refinement':refinement,'per_cell_physics_audits_passed':physics,
        'overall_pass':passed, 'not_a_candidate_acceptance':True,'not_frozen_A2':True,'A3':False,'Level1':False,'signatures':None})
    verify(); write(out/'run_completed.json',{'finish_utc':datetime.now(timezone.utc).isoformat(),'overall_pass':passed})
    return 0 if passed else 3

if __name__=='__main__': raise SystemExit(main())
