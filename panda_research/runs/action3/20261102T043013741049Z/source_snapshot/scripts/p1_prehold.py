"""Frozen DEVELOPMENT P1 simulation. No official A2 or post-hold motion mode."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from datetime import datetime,timezone
import argparse
import importlib.metadata
import json
import platform
import numpy as np
from panda_dynamics import QMIN,QMAX,dual_harmonic_disturbance
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.assembly import build_components
from panda_closed_loop.stepper import HoldSchedule
from panda_closed_loop.preparation import AppliedTorquePrehold,endpoint_diagnostics
from panda_closed_loop.logging import json_values

PLAN_SHA='11590d10a554d88907095d15a3fb13d0872d29c534eeffe70e0da2788b0d36d4'


def write(path,value):
    with path.open('x') as f:json.dump(json_values(value),f,indent=2,allow_nan=False);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    plan_path=ROOT/'policy/v1.2.2-r2-draft/PREDECLARED_DEVELOPMENT_PREHOLD.json'
    if digest(plan_path)!=PLAN_SHA:raise ValueError('Frozen plan changed; no automatic rerun/retuning')
    for path,sha in json.loads((ROOT/'provenance/p1_r2_prehold_input_hashes.json').read_text()).items():
        if digest(ROOT/path)!=sha:raise ValueError('Frozen input changed: '+path)
    plan=json.loads(plan_path.read_text());policy=Policy.load()
    if plan['C4_grid']!=policy.raw['integration']['validation_grid']:raise ValueError('C4 grid mismatch')
    out=(args.output or ROOT/'runs/p1_prehold'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):raise ValueError('Outputs must be below runs/')
    out.mkdir(parents=True,exist_ok=False)
    before={str(p.relative_to(ROOT)):digest(p) for folder in ['src','scripts','tests','policy','inputs/p1_review_2026_11_02','provenance']
        for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    metadata={'start_utc':datetime.now(timezone.utc).isoformat(),'scope':'DEVELOPMENT_PREHOLD_MODEL_SIMULATION_NOT_A2',
        'command':[sys.executable,*sys.argv],'cwd':str(ROOT),'python':sys.version,'platform':platform.platform(),
        'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'source_hashes':before,'frozen_plan':plan,'frozen_plan_sha256':PLAN_SHA,
        'source_audit':policy.source_audit(),'human_signatures':None,'official_A2_executed':False}
    write(out/'run_started.json',metadata)
    system=build_components(policy);cells=[]
    for i,grid in enumerate(plan['C4_grid']):
        runner=AppliedTorquePrehold(system,HoldSchedule(grid['control_period_s'],grid['rk4_step_s']),plan['T_pre_s'],
            (QMIN+QMAX)/2,plan['q_radius_rad'],plan['qd_radius_rad_s'],
            lambda t:dual_harmonic_disturbance(t,policy.raw['disturbance']['amplitude_fraction']))
        result=runner.run();endpoint=endpoint_diagnostics(system,runner,result)
        record={'cell':i,'grid':grid,'decision':result.decision,'completed':result.completed,
            'failure':result.failure,'actual_terminal_state':result.state.record(),'endpoint_diagnostics':endpoint,
            'trace':result.trace,'q_deviation_peak_rad':np.max([t['q_deviation_peak_rad'] for t in result.trace],axis=0),
            'qd_peak_rad_s':np.max([t['qd_peak_rad_s'] for t in result.trace],axis=0),
            'true_ODE_continuous_neighborhood_verified':False,'motion_started':False}
        name=f'cell_{i}.json';write(out/name,record)
        cells.append({k:record[k] for k in ['cell','grid','decision','completed','failure','q_deviation_peak_rad','qd_peak_rad_s']})
        cells[-1].update(record_file=name,valid_zero_endpoint=endpoint['valid_zero_time_endpoint'],
            terminal_QP_status=endpoint['QP_status'],terminal_QP_strict_pass=endpoint['QP_strict_pass'])
        print(f'cell {i}: {result.decision}; terminal t={result.state.t:.9f}',flush=True)
    all_pass=all(c['completed'] and c['valid_zero_endpoint'] for c in cells)
    summary={'scope':'DEVELOPMENT_PREHOLD_NOT_OFFICIAL_A2','frozen_plan_sha256':PLAN_SHA,'cells':cells,
        'P1_numerical_hold':'PASS' if all_pass else 'FAIL','P1_verified_startup':'NOT_APPROVED',
        'A1':'GO','A2':'NO-GO','A3':'NO-GO','Level_1':'NO-GO','publication':'NO-GO',
        'retuning_performed':False,'duration_gains_disturbance_changed':False,
        'continuous_true_ODE_proof':False,'full_A2_execution_performed':False,'independent_reviewer_signature':None}
    write(out/'summary.json',summary)
    metadata.update(finish_utc=datetime.now(timezone.utc).isoformat(),
        protected_inputs_unchanged=all(digest(ROOT/p)==h for p,h in before.items()),
        P1_numerical_hold=summary['P1_numerical_hold'])
    write(out/'run_completed.json',metadata)
    pointer={'run_directory':str(out.relative_to(ROOT)),'summary_sha256':digest(out/'summary.json'),
        'P1_numerical_hold':summary['P1_numerical_hold'],'A2':'NO-GO'}
    (ROOT/'reports/p1_prehold_latest.json').write_text(json.dumps(pointer,indent=2)+'\n')
    print(json.dumps(pointer,indent=2))
    return 0 if all_pass else 3


if __name__=='__main__':raise SystemExit(main())
