"""Read-only static P1 feasibility analysis. NO plant integration or A2 mode."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from datetime import datetime,timezone
import argparse
import hashlib
import itertools
import json
import os
import platform
import importlib.metadata
import numpy as np
from panda_dynamics import PandaDynamics,QMIN,QMAX,VMAX,TAUMAX,disturbance_bounds
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.assembly import build_components
from panda_closed_loop.reference import ReferenceSample
from panda_closed_loop.feasibility import pair_conditions,duration_for_pairs,q_grid,elapsed_envelope,planner_pair_screen,pointwise_planner_lower_witness


def serial(x):
    if hasattr(x,'tolist'):return x.tolist()
    if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    return x


def fixture_pass(solved):
    """Apply the draft's strict raw-slack rule as well as solver acceptance."""
    return (not solved.stop_requested
            and solved.diagnostics.get('exact_all_rows_nonnegative') is True)


def analyze(policy,intent):
    system=build_components(policy);q0=(QMIN+QMAX)/2
    raw=policy.raw;s=intent['screen'];dbar,rate=disturbance_bounds(raw['disturbance']['amplitude_fraction'])
    points=q_grid(q0,s['q_radius_rad']);width=QMAX-QMIN
    abs_N=[];entries=[]
    vrad=np.array(s['qd_radius_rad_s'])
    for q in points:
        N=np.linalg.solve(system.model.evaluate(q)['M'],np.eye(7));abs_N.append(abs(N))
        h,gradient,_=system.barriers.position_data(q)
        psi_min=policy.alpha1*h-np.abs(gradient)@vrad
        entries.append({'q_rad':q,'h_min':float(np.min(h)),'psi1_min_over_velocity_box':float(np.min(psi_min)),
                        'velocity_box_headroom':(VMAX-vrad),
                        'passed':bool(np.all(h>=0) and np.all(psi_min>=0) and np.all(vrad<=VMAX))})
    abs_N=np.array(abs_N)
    initial=pair_conditions(abs_N[0],dbar,width,VMAX,policy.alpha1,policy.alpha2,policy.alpha_v)
    full_initial_rows=system.barriers.rows(q0,np.zeros(7),np.zeros(7),dbar)
    initial_qp=system.qp.solve(system.model.evaluate(q0)['g'],full_initial_rows)
    B0=np.array([N@dbar for N in abs_N])
    rhs=np.minimum(policy.alpha_v*VMAX,policy.alpha1*policy.alpha2*width/2)
    duration=duration_for_pairs(B0,rhs,dbar,rate,policy.ko,policy.delta)
    result={'scope':'DEVELOPMENT_STATIC_NUMERICAL_SCREEN_NO_PLANT_NO_A2',
            'source_policy_sha256':digest(policy.path),'model_sha256':digest(ROOT/'src/panda_dynamics.py'),
            'predeclaration':intent,'initial_q0_rad':q0,'varpi0_Nm':dbar,
            'baseline_online_pairs':initial,'baseline_complete_QP_status':initial_qp.status,
            'baseline_complete_QP_stopped':initial_qp.stop_requested,
            'online_pair_derivation':{'velocity':'upper+lower = 2*alpha_v*vmax - 2*abs(N)*varpi; tau, bias and qdot cancel',
             'position':'upper+lower = alpha1*alpha2*joint_range - 2*abs(N)*varpi; tau, bias, q and linear qdot terms cancel; joint Hessians=0',
             'not_paired':'Manipulability and torque box require complete QP checks'},
            'duration_analysis':duration,'initial_entry_samples':entries,
            'planner_screen':planner_pair_screen(dbar,width,VMAX,policy.alpha1,policy.alpha2,policy.alpha_v,
                1e-4*width,raw['physical_parameters']['barrier_reserves']['velocity_CBF_delta_vB_rad_s2']),
            'planner_initial_pointwise_lower_witness':pointwise_planner_lower_witness(abs_N[0],dbar,width,VMAX,
                policy.alpha1,policy.alpha2,policy.alpha_v,1e-4*width,raw['physical_parameters']['barrier_reserves']['velocity_CBF_delta_vB_rad_s2']),
            'plant_integrations_performed':0,'P1_overall':'BLOCKED_PHYSICAL_PREHOLD_NOT_VERIFIED',
            'A2':'NO-GO','gains_changed':False,'disturbance_changed':False,'automatic_P2_fallback':False}
    pre=duration['proposed_T_pre_s']
    if pre is None:
        result['P1_candidate']={'status':'FAIL_NECESSARY_FLOOR_SCREEN','sampled_pair_screen_passed':False,
                               'complete_QP_fixture':{'status':'NOT_RUN','numerical_pass':None}}
        return result
    time_samples=[]
    for t in s['report_times_s']:
        varpi=elapsed_envelope(t,pre,policy.ko,dbar,rate)
        rows=[]
        for i,N in enumerate(abs_N):
            pairs=pair_conditions(N,varpi,width,VMAX,policy.alpha1,policy.alpha2,policy.alpha_v)
            rows.append({'q_index':i,'q_rad':points[i],**pairs})
        time_samples.append({'physical_t_s':t,'observer_elapsed_s':t+pre,'varpi_Nm':varpi,'q_samples':rows})
    vp0=elapsed_envelope(0.,pre,policy.ko,dbar,rate)
    pairs_ok=all(row['velocity']['passed'] and row['position']['passed'] for t in time_samples for row in t['q_samples'])
    entry_ok=all(row['passed'] for row in entries)
    qp_records=[]
    if pairs_ok and entry_ok:
        estimate_radius=dbar+vp0
        estimates=[np.zeros(7)]+[estimate_radius*np.array(signs) for signs in itertools.product([-1.,1.],repeat=7)]
        fixture=ReferenceSample(q0,np.zeros(7),np.zeros(7))
        for i,estimate in enumerate(estimates):
            nominal,_=system.controller.command(q0,np.zeros(7),fixture,estimate)
            rows=system.barriers.rows(q0,np.zeros(7),estimate,vp0)
            solved=system.qp.solve(nominal,rows)
            qp_records.append({'index':i,'estimate_Nm':estimate,'status':solved.status,
                               'numerical_pass':fixture_pass(solved),'applied_candidate':solved.applied,'diagnostics':solved.diagnostics})
    qp_pass=all(x['numerical_pass'] for x in qp_records) if qp_records else None
    candidate={'T_pre_s':pre,'continuous_ideal_varpi_at_zero_Nm':vp0,
               'sampled_pair_screen_passed':pairs_ok,'entry_conditions_at_declared_nodes':entry_ok,
               'time_samples':time_samples,'fixed_q_samples':len(points),
               'monotone_time_argument':'All gains common positive, varpi decreases componentwise; at each fixed node t=0 dominates the declared future window. This does not enclose all q in the continuous box.',
               'continuous_neighborhood_coverage':'NOT_ESTABLISHED','physical_hold':'NOT_TESTED',
               'complete_QP_fixture':{'scope':'Fixed midpoint and zero velocity only; unknown physical endpoint not asserted',
                   'estimate_box':'abs(dhat)<=dbar+varpi, from triangle inequality only; no injected truth',
                   'count':len(qp_records),'numerical_pass':qp_pass,'cases':qp_records,
                   'convexity_note':'At a fixed state constraints are affine in (tau,dhat). Vertex feasibility supports only the estimate box, numerically, not a q/qd tube certificate.'}}
    candidate['status']='PASS_SAMPLED_STATIC_SCREENS_PHYSICAL_HOLD_BLOCKED' if pairs_ok and entry_ok and qp_pass else 'FAIL_PREDECLARED_STATIC_SCREEN_NO_RETUNING'
    result['P1_candidate']=candidate
    result['preparation_envelope_samples']=[{'physical_t_s':t,'observer_elapsed_s':t+pre,
        'varpi_Nm':elapsed_envelope(t,pre,policy.ko,dbar,rate),
        'scope':'PREPARATION_OUTSIDE_A2_SAFETY_CLAIM_NO_PHYSICAL_EXECUTION'} for t in [-pre,-pre/2,0.]]
    floor=rate/np.array(policy.ko)
    result['observer_floor_Nm']=floor
    result['planner_floor_pointwise_lower_witness']=pointwise_planner_lower_witness(abs_N[0],floor,width,VMAX,
        policy.alpha1,policy.alpha2,policy.alpha_v,1e-4*width,raw['physical_parameters']['barrier_reserves']['velocity_CBF_delta_vB_rad_s2'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    out=args.output or ROOT/'runs/p1'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=out.resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Screen outputs must be in a new directory below project/runs')
    out.mkdir(parents=True,exist_ok=False)
    # No writes to model, policy, inputs or review records.
    predecl=ROOT/'policy/v1.2.2-draft/PREDECLARED_P1_DESIGN.json'
    expected=json.loads((ROOT/'provenance/p1_input_and_predeclaration_hashes.json').read_text())
    for name,sha in expected.items():
        if digest(ROOT/name)!=sha:raise ValueError('Predeclared design/input changed: '+name)
    policy=Policy.load();audit=policy.source_audit();intent=json.loads(predecl.read_text())
    started=datetime.now(timezone.utc).isoformat()
    result=analyze(policy,intent)
    result['predeclaration_sha256']=digest(predecl)
    result['source_audit']=audit
    (out/'screen.json').write_text(json.dumps(serial(result),indent=2,allow_nan=False)+'\n')
    manifest={str(p.relative_to(ROOT)):digest(p) for folder in ['src','tests','scripts','policy','inputs/p1_v1.2.2'] for p in (ROOT/folder).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and not any(x.endswith('.egg-info') for x in p.parts)}
    (out/'source_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
    metadata={'start_utc':started,'finish_utc':datetime.now(timezone.utc).isoformat(),
        'command':[sys.executable,*sys.argv],'cwd':str(ROOT),'python':sys.version,'platform':platform.platform(),
        'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'effective_approved_configuration_read_only':policy.raw,'predeclaration':intent,
        'source_hashes':manifest,'static_screen_plant_integrations':0,'official_A2_executed':False,
        'random_search_or_gain_sweep_performed':False}
    (out/'run_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    pointer={'run_directory':str(out.relative_to(ROOT)),'screen_sha256':digest(out/'screen.json')}
    (ROOT/'reports/p1_latest.json').write_text(json.dumps(pointer,indent=2)+'\n')
    print(json.dumps({'run_directory':pointer['run_directory'],'P1_overall':result['P1_overall'],
                     'duration':result['duration_analysis'],'candidate_status':result['P1_candidate']['status'],'A2':'NO-GO'},indent=2))


if __name__=='__main__':main()
