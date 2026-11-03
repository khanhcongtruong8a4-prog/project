"""Exclusive candidate run: 4 historical alpha5 + 4 half-second alpha10 cells."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,copy,hashlib,json,subprocess,traceback
from dataclasses import replace
from datetime import datetime,timezone
import numpy as np
from panda_dynamics import QMIN,QMAX,dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.a2_extended import ExtendedReference,reference_screen,entrance_pairs
from panda_closed_loop.p1_r3 import SampledComputedTorque,compare_refinement
from panda_closed_loop.preparation import AppliedTorquePrehold
from panda_closed_loop.stepper import HoldSchedule
from panda_closed_loop.trace_archive import write_trace,read_trace
from panda_closed_loop.logging import json_values
from panda_closed_loop.polynomial_hold_v2 import PolynomialHold,CompletionService,integrate,polynomial_peak,Stop
from reproduce_a2_acceptance import import_script

POLICY=ROOT/'policy/active_remediation_v2/PREDECLARATION.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):
    with Path(p).open('x') as f:json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')
def verify():
    p=json.loads(POLICY.read_text());bad=[n for n,h in p['source_sha256'].items() if sha(ROOT/n)!=h]
    if bad:raise ValueError('Frozen source differs: '+str(bad))
    bad=[n for n,h in p['protected_sha256'].items() if sha(ROOT/n)!=h]
    if bad:raise ValueError('Protected source differs: '+str(bad))
    commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(POLICY)],cwd=ROOT,text=True).strip()
    if not commit or subprocess.check_output(['git','show',commit+':panda_research/'+str(POLICY.relative_to(ROOT))],cwd=ROOT)!=POLICY.read_bytes():raise ValueError('Commit predeclaration before motion')
    return p,commit

def plan_for(case):
    m=import_script('candidate_input_'+case,'a2_extended_v2.py' if case=='alpha5' else 'a2_extended_v4.py')
    plan,_,_=m.verify();plan=copy.deepcopy(plan)
    if case=='alpha10':
        plan['references']['E3']['duration_s']=.5;plan['A2_reference']['duration_s']=.5
        plan['reference_screen_times_s']=[t*.5 for t in plan['reference_screen_times_s']]
    return plan

def audit(holds,steps,system):
    checks={'nonempty':bool(holds and steps),'projection_raw_and_KKT':True,'completion_full_guarded_KKT':True,
            'same_torque_to_plant_and_DOB':True,'gauss_stage_residual':True,'all_sampled_physical_observer_and_dense_checks':True}
    maxima={k:0. for k in ['completion_primal','completion_stationarity','completion_complementarity','stage_residual']}
    for hold in holds:
        d=hold['completion'];C=np.array(d['C']);b=np.array(d['b']);x=np.array(d['x']);dual=np.array(d['dual_full'])
        vals=[max(0.,float(np.max(C@x-b))),float(np.max(abs(x+C.T@dual))),float(np.max(abs(dual*(C@x-b))))]
        for k,v in zip(['completion_primal','completion_stationarity','completion_complementarity'],vals):maxima[k]=max(maxima[k],v)
        checks['completion_full_guarded_KKT'] &= (all(v<=1e-9 for v in vals) and np.all(dual>=-1e-9)
            and np.min(d['full_raw_normalized_slacks'])>=0 and np.min(d['full_guarded_normalized_slacks'])>=-1e-9)
        for q in hold['projection_queries']:
            r=q['query'];diag=r['diagnostics'];tau=np.array(r['applied']);raw=np.array(q['G'])@tau+q['c']
            checks['projection_raw_and_KKT'] &= (not r['stop_requested'] and np.all(raw>=0) and all(diag[k]<=1e-9 for k in ['normalized_primal','scaled_stationarity','guarded_normalized_primal','guarded_scaled_stationarity','guarded_complementarity']))
    for step in steps:
        checks['all_sampled_physical_observer_and_dense_checks'] &= all(step['checks'].values())
        checks['gauss_stage_residual'] &= step['stage_equation_residual']<=1e-13
        maxima['stage_residual']=max(maxima['stage_residual'],step['stage_equation_residual'])
        for stage,tau,k in zip(step['stage_state'],step['stage_torques'],step['stage_rhs']):
            zdot=system.observer.derivative(stage[:7],stage[7:14],stage[14:21],tau)
            checks['same_torque_to_plant_and_DOB'] &= np.array_equal(zdot,np.array(k)[14:21])
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':all(checks.values()),'checks':checks,'maxima':maxima,'scope':'FINITE_GRID_AND_NUMERICAL_COLLOCATION_NOT_TRUE_ODE_CERTIFICATION'}

def cell(case,index,out):
    frozen,commit=verify();plan=plan_for(case);system=build_components() if case=='alpha5' else build_amended_system()
    system.geometry.function=system.geometry.function.expand();grid=plan['C4_grid'][index];schedule=HoldSchedule(grid['control_period_s'],grid['rk4_step_s'])
    out.mkdir(parents=True,exist_ok=False)
    write(out/'started.json',{'utc':datetime.now(timezone.utc).isoformat(),'case':case,'cell':index,'freeze_commit':commit,'grid':grid,'plan':plan,'scope':'NEW_NUMERICAL_CANDIDATE_NOT_OFFICIAL_A3'})
    startup=replace(system,controller=SampledComputedTorque(system.model,plan['startup_controller']['kp_s_inverse_squared'],plan['startup_controller']['kd_s_inverse']))
    waveform=lambda t:dual_harmonic_disturbance(t,system.policy.raw['disturbance']['amplitude_fraction'])
    runner=AppliedTorquePrehold(startup,schedule,plan['T_pre_s'],(QMIN+QMAX)/2,plan['q_radius_rad'],plan['qd_radius_rad_s'],waveform)
    held=runner.run();prep=write_trace(out/'prehold.ctz',held.trace)
    holds=[];steps=[];failure=None;metrics={};a={'passed':False};state=None
    try:
        if not held.completed:raise Stop('PREHOLD_FAILED',{'failure':held.failure})
        state=held.measured_state_at_zero();reference=ExtendedReference(state.q,state.qd,plan['references']['E3'])
        screen=reference_screen(system,reference,plan['reference_screen_times_s']);pairs=entrance_pairs(system,state,runner.envelope.value(0.))
        if not screen['passed'] or not pairs['position']['passed'] or not pairs['velocity']['passed']:raise Stop('ENTRANCE_FAILED',{'screen':screen,'pairs':pairs})
        # Seed only from actual measured P1 endpoints at control-period spacing.
        history=[]
        for step in held.trace:
            t=step['state_after']['physical_t_s']
            if any(abs(t+j*schedule.delta)<1e-12 for j in range(4)):
                v=step['state_after'];history.append((t,np.r_[v['q'],v['qd'],v['z']]))
        history[-1]=(0.,np.r_[state.q,state.qd,state.z])
        energy=0.;intervention=0.;minraw=np.inf
        with CompletionService() as service:
            controller=PolynomialHold(system,service)
            for period in range(round(reference.duration/schedule.delta)):
                hold=controller.query(state,schedule.delta,history,runner.envelope,reference)
                hold['actuated']=True;holds.append(hold)
                intervention=max(intervention,polynomial_peak(hold['coefficients']-hold['nominal_coefficients']))
                minraw=min(minraw,float(np.min(hold['completion']['full_raw_normalized_slacks'])))
                for j in range(schedule.substeps):
                    end_t=(period*schedule.substeps+j+1)*schedule.h
                    if period*schedule.substeps+j+1==round(reference.duration/schedule.h):end_t=reference.duration
                    state,step=integrate(system,state,hold,schedule.h,end_t,runner.envelope,waveform)
                    step.update(control_period_index=period,substep_index=j);steps.append(step);energy+=step['modeled_electrical_energy_increment_J']
                    if not all(step['checks'].values()):raise Stop('SAMPLED_PHYSICAL_OR_OBSERVER_REJECTION',step['checks'])
                history.append((state.t,np.r_[state.q,state.qd,state.z]));history=history[-4:]
                if period%100==0:print(case,index,'t',state.t,'Imax',intervention,flush=True)
        error=float(np.linalg.norm(system.geometry.evaluate(state.q)['f']-system.geometry.evaluate(reference.target_q)['f']))
        planned=float(np.linalg.norm(system.geometry.evaluate(reference.sample(reference.duration).q)['f']-system.geometry.evaluate(reference.target_q)['f']))
        thresholds=plan['fixed_acceptance_thresholds'];passed=(state.t==reference.duration and error<=thresholds['actual_terminal_error_m'] and planned<=thresholds['planned_terminal_error_m'])
        metrics={'modeled_electrical_energy_J':energy,'duration_s':state.t,'maximum_intervention_Nm':intervention,
                 'minimum_normalized_raw_slack':float(minraw),'actual_terminal_error_m':error,'planned_terminal_error_m':planned}
        a=audit(holds,steps,system);passed=bool(passed and a['passed'])
    except Stop as e:failure={'reason':str(e),'record':e.record,'physical_t_s':None if state is None else state.t,'no_further_actuation':True};passed=False
    except Exception:failure={'engineering_error':traceback.format_exc(),'no_further_actuation':True};passed=False
    trace=write_trace(out/'execution.ctz',{'holds':holds,'substeps':steps})
    # Verify lossless serialization before reporting acceptance.
    restored=read_trace(out/trace['file'],trace)
    a['lossless_roundtrip_verified']=len(restored['holds'])==len(holds) and len(restored['substeps'])==len(steps)
    result={'case':case,'cell':index,'grid':grid,'a2':{'completed':failure is None and state is not None and state.t==plan['references']['E3']['duration_s'],
            'passed':passed,'failure':failure,'metrics':metrics,'trace':trace},'prehold':{'passed':held.completed,'trace':prep},'audit':a}
    verify();write(out/'result.json',result);print('RESULT',case,index,passed,failure and failure.get('reason'),flush=True)
    return 0 if passed else 3

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['alpha5','alpha10'],required=True);p.add_argument('--cell',type=int,choices=range(4),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    return cell(a.case,a.cell,a.output.resolve())
if __name__=='__main__':raise SystemExit(main())
