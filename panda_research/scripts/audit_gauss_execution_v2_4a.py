"""Versioned post-run audit; preserves every original result and trace byte."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json
from datetime import datetime,timezone
import numpy as np
from panda_dynamics import dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.trace_archive import read_trace
from panda_closed_loop.gauss_execution_audit_v2_4a import audit_step
from run_polynomial_hold_v2_4 import verify,plan_for

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def audit_cell(path,system,case):
    original=path/'result.json';c=json.loads(original.read_text());a=c['a2'];checks=c['audit'].get('checks',{})
    allowed={'same_torque_to_plant_and_DOB'}
    failed={k for k,v in checks.items() if not v}
    eligible=(a['completed'] and a['failure'] is None and c['prehold']['passed'] and bool(checks) and failed<=allowed)
    if not eligible:return {'passed':False,'original_result_sha256':sha(original),'reason':'NOT_THE_PREDECLARED_DIAGNOSTIC_ONLY_FAILURE','original_failed_checks':sorted(failed)}
    t=a['trace'];trace=read_trace(path/t['file'],t);holds=trace['holds'];steps=trace['substeps'];grid=c['grid'];plan=plan_for(case)
    expected=plan['references']['E3']['duration_s'];thresholds=plan['fixed_acceptance_thresholds'];m=a['metrics']
    counts=len(holds)==round(expected/grid['control_period_s']) and len(steps)==round(expected/grid['rk4_step_s'])
    metrics=(m['duration_s']==expected and m['actual_terminal_error_m']<=thresholds['actual_terminal_error_m'] and m['planned_terminal_error_m']<=thresholds['planned_terminal_error_m'])
    waveform=lambda t:dual_harmonic_disturbance(t,system.policy.raw['disturbance']['amplitude_fraction'])
    maxima={k:0. for k in ['h_scaled_full_RHS_defect','stage_equation_defect','endpoint_equation_defect']};passed=bool(counts and metrics);bad=[]
    for i,step in enumerate(steps):
        hold=holds[step['control_period_index']];step=dict(step,prescribed_h=grid['rk4_step_s']);v=audit_step(system,hold,step,waveform)
        passed &= v['passed'] and all(step['checks'].values())
        for k in maxima:maxima[k]=max(maxima[k],v[k])
        if not v['passed']:bad.append({'substep':i,**v})
    return {'version':'GL_EXECUTION_VERIFICATION_V2_4A','passed':bool(passed),'original_result_sha256':sha(original),'trace_sha256':t['sha256'],
            'original_result_passed':a['passed'],'original_failed_checks':sorted(failed),'trajectory_resimulated_or_changed':False,
            'complete_counts':counts,'original_terminal_thresholds_passed':bool(metrics),'substeps_audited':len(steps),'maxima':maxima,
            'failed_steps':bad,'criterion':1e-13,'criterion_frozen_before_motion':True,
            'scope':'RECOMPUTED_IDENTICAL_ACTUAL_TORQUE_AND_FULL_PLANT_DOB_POWER_STAGE_EQUATIONS_NOT_CERTIFIED_ODE_BOUNDS'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['alpha5','alpha10'],required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    policy=ROOT/'policy/active_remediation_v2/AUDIT_CORRECTION_V2_4A.json';frozen=json.loads(policy.read_text())
    if any(sha(ROOT/n)!=h for n,h in frozen['source_sha256'].items()):raise ValueError('Audit correction differs')
    verify();system=build_components() if a.case=='alpha5' else build_amended_system();system.geometry.function=system.geometry.function.expand()
    result=audit_cell(a.input.resolve(),system,a.case);result['audit_policy_sha256']=sha(policy);result['utc']=datetime.now(timezone.utc).isoformat()
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:result[k] for k in ['passed','maxima','substeps_audited']},indent=2));return 0 if result['passed'] else 3
if __name__=='__main__':raise SystemExit(main())
