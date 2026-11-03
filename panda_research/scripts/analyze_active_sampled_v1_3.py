"""Read-only, full-history attribution; no torque from this file is actuated."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse, json, hashlib, csv, time, shutil
from panda_closed_loop.active_sampled_clock_v1 import common_energy_indices
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from panda_dynamics import dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.reference import ReferenceSample
from panda_closed_loop.a2_extended import ExtendedReference
from panda_closed_loop.guarded_qp_final_v1 import GuardedHardQP
from panda_closed_loop.a2_acceptance import read_recorded_trace
from panda_closed_loop.active_sampled_analysis_v1 import (SpeedMaterialDerivative,
    face_expansion,reference_jerk,reconstruct_electrical_energy)
from panda_closed_loop.logging import json_values

def write(p,d):
    with Path(p).open('x') as f: json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(a): return np.linalg.norm(a,axis=-1)
def transitions(t,dual,names,threshold):
    sets=[tuple(np.flatnonzero(d>threshold)) for d in dual]
    events=[{'previous_t_s':float(t[k-1]),'t_s':float(t[k]),'from':[names[i] for i in sets[k-1]],
             'to':[names[i] for i in sets[k]]} for k in range(1,len(t)) if sets[k]!=sets[k-1]]
    return sets,events

def cell_analysis(folder,out,index,alpha10):
    begin=time.perf_counter(); folder=Path(folder);out=Path(out)
    # The independent baseline replay writes each final JSON only after its
    # trace and audit. Wait for that publication; never inspect a partial trace.
    while not (folder/f'cell_{index}.json').exists():
        if time.perf_counter()-begin>3600: raise TimeoutError('Baseline cell not published')
        time.sleep(2)
    cell=json.loads((folder/f'cell_{index}.json').read_text())
    trace=read_recorded_trace(folder,cell['a2']['trace']); U=trace['updates']; S=trace['substeps']
    sys=build_amended_system() if alpha10 else build_components()
    sys.geometry.function=sys.geometry.function.expand()
    operator=SpeedMaterialDerivative(sys);qp=GuardedHardQP(sys.barriers.taumax)
    t=np.array([u['physical_t_s'] for u in U]);n=len(t);delta=cell['grid']['control_period_s']
    r=np.array([u['tracking_errors']['continuous_request_Nm'] for u in U])
    u=np.array([v['u_nom'] for v in U]);tau=np.array([v['candidate_tau'] for v in U])
    dual=np.array([v['diagnostics']['dual_scaled'] for v in U]);names=U[0]['row_names']
    state=np.array([v['q']+v['qd']+v['z'] for v in U]);dhat=np.array([v['dhat'] for v in U])
    rawsigma=[];rawdual=[];raw_kkt=[];counter=[];fixed=[];raw_projection_failures=[];hypo_bad=[]
    for k,v in enumerate(U):
        rows=AffineRows(v['G'],v['c'],v['row_scales'],tuple(names),tuple(v['row_units']))
        query=qp.solve(r[k],rows)
        if query.stop_requested or query.applied is None:
            raw_projection_failures.append({'index':k,'status':query.status});raise ValueError('Read-only projection unqualified; no fabricated value')
        rawsigma.append(query.applied);rawdual.append(query.diagnostics['dual_scaled'])
        raw_kkt.append([query.diagnostics['guarded_normalized_primal'],query.diagnostics['guarded_scaled_stationarity']])
        if k:
            hypothetical=query.applied+.5*(query.applied-rawsigma[k-1])
            slacks=rows.slacks(hypothetical)/rows.scales
            hypo_bad.append(float(np.min(slacks)))
            counter.append(hypothetical)
            prior_at_current=qp.solve(r[k-1],rows)
            if prior_at_current.stop_requested:raise ValueError('Fixed-set diagnostic projection unqualified')
            fixed.append(query.applied+.5*(query.applied-prior_at_current.applied))
        else:
            hypo_bad.append(float(np.min(rows.slacks(query.applied)/rows.scales)))
            counter.append(query.applied);fixed.append(query.applied)
    sigma=np.asarray(rawsigma);rawdual=np.asarray(rawdual);counter=np.asarray(counter);fixed=np.asarray(fixed)
    sets,events=transitions(t,dual,names,1e-10);rawsets,rawevents=transitions(t,rawdual,names,1e-10)
    _,events8=transitions(t,dual,names,1e-8)
    definition=json.loads((ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json' if alpha10 else ROOT/'policy/a2_extended_v2/A2_EXTENDED_PREDECLARATION.json').read_text())['references']['E3']
    definition['duration_s']=cell['a2']['final_state']['physical_t_s']
    reference=ExtendedReference(np.array(cell['endpoint']['state']['q']),np.array(cell['endpoint']['state']['qd']),definition)
    boundaries=[e['t_s'] for e in events]+[e['t_s'] for e in rawevents]+list(reference.boundaries)
    arrays={key:np.full((n,7),np.nan) for key in ['dr','dsigma','missing_normal','missing_rotation','AB2_defect','feedback_AB2_defect']}
    normal_velocity=np.full((n,14),np.nan);gram=np.full(n,np.nan);eligible=np.zeros(n,dtype=bool)
    projections_error=[];ad_value_error=[];finite_differences=[];exclusions={}
    all_ds=[];positive_normal=[]
    for k,v in enumerate(U):
        if not rawsets[k]:
            exclusions['inactive']=exclusions.get('inactive',0)+1;continue
        if any(i<15 or i>=29 for i in rawsets[k]):
            exclusions['non_speed_active_family']=exclusions.get('non_speed_active_family',0)+1;continue
        act=np.array(rawsets[k])-15;lam=87*rawdual[k,15:29]
        data=operator.evaluate(state[k,:7],state[k,7:14],state[k,14:],reference.sample(float(t[k])),
            reference_jerk(reference,float(t[k])),np.array(v['varpi']),
            -np.asarray(sys.observer.gains)*(np.array(v['varpi'])-sys.bounds.rate/np.asarray(sys.observer.gains)),sigma[k],
            dual_harmonic_disturbance(float(t[k]),sys.policy.raw['disturbance']['amplitude_fraction']))
        rows=AffineRows(v['G'],v['c'],v['row_scales'],tuple(names),tuple(v['row_units']))
        norms=np.linalg.norm(rows.G[15:29],axis=1)
        ad_value_error.append([float(np.max(abs(data['A']+rows.G[15:29]/norms[:,None]))),
            float(np.max(abs(data['b']-(rows.c[15:29]-1e-8*rows.scales[15:29])/norms))),float(np.max(abs(data['r']-r[k])))])
        f=face_expansion(data['A'],data['b'],r[k],data['dA'],data['db'],data['dr'],act,lam)
        gram[k]=f['gram_condition'];projections_error.append(float(np.max(abs(f['sigma']-sigma[k]))))
        normal_velocity[k,act]=f['normal_speed']
        for key in arrays:arrays[key][k]=data[key] if key=='dr' else f[key]
        reasons=[]
        if sets[k]!=rawsets[k]:reasons.append('digital_raw_active_sets_differ')
        if np.any(lam[act]<=1e-6):reasons.append('not_strictly_complementary_at_declared_margin')
        if f['gram_condition']>=1e6:reasons.append('ill_conditioned_Gram')
        if min(abs(t[k]-b) for b in boundaries)<=2*delta+1e-12:reasons.append('near_active_or_reference_event')
        for reason in reasons:exclusions[reason]=exclusions.get(reason,0)+1
        if reasons:continue
        eligible[k]=True;all_ds.append(f);positive_normal.append(bool(np.any(f['normal_speed']>0)))
        if k%50==0:
            for eps in [1e-6,3e-7]:
                points=[];ok=True
                for sign in [-1,1]:
                    xx=state[k]+sign*eps*data['xdot'];tt=float(t[k]+sign*eps)
                    dh=sys.observer.estimate(xx[:7],xx[7:14],xx[14:])
                    # This is an offline attribution direction, never a predictor actuated by the controller.
                    vp=np.exp(-sys.observer.gains*(tt+.156))*sys.bounds.magnitude-np.expm1(-sys.observer.gains*(tt+.156))*sys.bounds.rate/sys.observer.gains
                    rr,_=sys.controller.command(xx[:7],xx[7:14],reference.sample(tt),dh)
                    rows2=sys.barriers.rows(xx[:7],xx[7:14],dh,vp);qq=qp.solve(rr,rows2)
                    if qq.stop_requested:ok=False;break
                    acts=tuple(np.flatnonzero(np.array(qq.diagnostics['dual_scaled'])>1e-10))
                    if acts!=rawsets[k]:ok=False;break
                    points.append(qq.applied)
                if ok:
                    fd=(points[1]-points[0])/(2*eps)
                    finite_differences.append({'index':k,'t_s':float(t[k]),'epsilon_s':eps,
                        'max_abs_derivative_difference_Nm_s':float(np.max(abs(fd-f['dsigma']))),
                        'relative_vector_difference':float(norm(fd-f['dsigma'])/max(norm(f['dsigma']),1e-30))})
    energy=sys.policy.raw['energy'];quadrature=reconstruct_electrical_energy(S,energy['k_r'],energy['nonregenerative_smoothing']['epsilon_W'])
    stage_times=[];stage_raw=[];stage_guarded=[];stage_observer=[];stage_index=[]
    for si,step in enumerate(S):
        for ki,s in enumerate(step['samples']):
            rows=sys.barriers.rows(s['q'],s['qd'],s['dhat'],s['varpi'])
            sl=rows.slacks(step['applied_tau'])/rows.scales
            stage_times.append(s['physical_t_s']);stage_raw.append(sl);stage_guarded.append(sl-1e-8)
            stage_observer.append(s['observer_envelope_slack']);stage_index.append([si,ki])
    stage_times=np.array(stage_times);stage_raw=np.array(stage_raw);stage_guarded=np.array(stage_guarded)
    minimum=np.unravel_index(np.argmin(stage_raw),stage_raw.shape)
    I=norm(tau-u);J=norm(tau-r);peak=int(np.argmax(I));fit=None
    if 0<peak<n-1:
        coef=np.polyfit(t[peak-1:peak+2]-t[peak],I[peak-1:peak+2],2);vertex=-coef[1]/(2*coef[0])
        if coef[0]<0 and abs(vertex)<delta:
            fit={'time_s':float(t[peak]+vertex),'peak_Nm':float(np.polyval(coef,vertex)),
                 'increase_Nm':float(np.polyval(coef,vertex)-I[peak]),'diagnostic_only':True}
    bad=np.where(np.min(stage_raw,axis=1)<0)[0];badexamples=[]
    for j in bad[:10]:
        badexamples.append({'t_s':float(stage_times[j]),'substep_and_stage':stage_index[j],
            'negative_rows':[names[i] for i in np.flatnonzero(stage_raw[j]<0)],'minimum_normalized_raw':float(np.min(stage_raw[j]))})
    regular_fixed_errors=norm(tau-fixed)[eligible]
    result={'cell':index,'grid':cell['grid'],'alpha_v':sys.barriers.alpha_v,'metrics':cell['a2']['metrics'],
        'original_cell_audit_pass':cell['audit']['passed'],'original_physics_pass':cell['a2']['passed'],
        'source_execution_sha256':sha(folder/cell['a2']['trace']['file']),'updates':n,
        'max_tau_minus_u_Nm':float(np.max(I)),'max_tau_minus_r_Nm':float(np.max(J)),
        'dual_activity_threshold_y':1e-10,'active_updates':sum(bool(s) for s in sets),'transitions':events,
        'activity_threshold_1e8_transitions':events8,'raw_projection_transitions':rawevents,
        'raw_projection_failed_queries':raw_projection_failures,'raw_projection_max_KKT_residuals':np.max(raw_kkt,axis=0),
        'peak_time_s':float(t[peak]),'quadratic_peak_diagnostic':fit,
        'read_only_counterfactuals':{'torque_actuated':False,
            'first_order_request':'sigma=P_Ck(r_k); per-point only, not a fresh first-order plant trajectory',
            'post_filter_AB2_negative_raw_queries':int(np.count_nonzero(np.array(hypo_bad)<0)),
            'post_filter_AB2_minimum_normalized_raw_slack':float(min(hypo_bad)),
            'post_filter_AB2_max_commutator_Nm':float(np.max(norm(tau-counter))),
            'fixed_current_set_AB2_commutator_regular_max_Nm':float(np.max(regular_fixed_errors)) if len(regular_fixed_errors) else None},
        'smooth_face':{'eligible_updates':int(np.sum(eligible)),'excluded_reason_counts_not_disjoint':exclusions,
            'physical_dual_min_for_regular_analysis_Nm':1e-6,'max_Gram_condition':float(np.nanmax(gram)) if np.any(np.isfinite(gram)) else None,
            'max_AD_value_discrepancies_A_b_r':np.max(ad_value_error,axis=0) if ad_value_error else None,
            'max_projection_KKT_closed_form_difference_Nm':max(projections_error,default=None),
            'positive_outward_required_normal_updates':sum(positive_normal),
            'max_missing_normal_Nm_s':float(np.max(norm(arrays['missing_normal'][eligible]))) if np.any(eligible) else None,
            'max_missing_rotation_Nm_s':float(np.max(norm(arrays['missing_rotation'][eligible]))) if np.any(eligible) else None,
            'max_AB2_defect_Nm_s':float(np.max(norm(arrays['AB2_defect'][eligible]))) if np.any(eligible) else None,
            'finite_difference_crosschecks':finite_differences},
        'electrical_quadrature':{k:v for k,v in quadrature.items() if k not in ['increments','mechanical_W','loss_W','power_W']},
        'stage_raw_rows':{'samples':len(stage_times),'row_count':43,'minimum_normalized_raw':float(stage_raw[minimum]),
            'minimum_row':names[minimum[1]],'minimum_time_s':float(stage_times[minimum[0]]),
            'negative_raw_sample_count':int(len(bad)),'negative_raw_row_value_count':int(np.count_nonzero(stage_raw<0)),
            'minimum_guarded_normalized':float(np.min(stage_guarded)),'examples':badexamples,
            'scope':'READ_ONLY_RK4_STAGE_AND_INTEGRATED_NODE_ESTIMATES; NOT_BETWEEN_SAMPLE_CERTIFICATE; no new safety waiver'},
        'wall_time_s':time.perf_counter()-begin,'signatures':None,'no_actuation':True}
    np.savez_compressed(out/f'cell_{index}_operators.npz',t=t,r=r,u=u,tau=tau,sigma=sigma,
        state=state,dhat=dhat,dual_scaled=dual,raw_projection_dual_scaled=rawdual,
        current_row_A=-np.array([v['G'] for v in U])/np.linalg.norm(np.array([v['G'] for v in U]),axis=2)[:,:,None],
        row_b=np.array([(np.array(v['c'])-1e-8*np.array(v['row_scales']))/np.linalg.norm(v['G'],axis=1) for v in U]),
        normalized_raw_slacks=np.array([v['normalized_raw_slacks'] for v in U]),
        read_only_postfilter_AB2=counter,read_only_fixed_set_AB2=fixed,eligible=eligible,gram_condition=gram,
        normal_speed=normal_velocity,energy_t=np.array([s['physical_t1_s'] for s in S]),
        energy_increments=quadrature['increments'],bus_mechanical_W=quadrature['mechanical_W'],
        bus_loss_W=quadrature['loss_W'],bus_nonregenerative_W=quadrature['power_W'],
        stage_t=stage_times,stage_index=np.array(stage_index),stage_raw_normalized=stage_raw,
        stage_guarded_normalized=stage_guarded,stage_observer_slack_Nm=np.array(stage_observer),**arrays)
    write(out/f'cell_{index}.json',result)
    print('analyzed',index,'regular',int(np.sum(eligible)),'stage-negative',len(bad),flush=True)
    return result

def aggregate(out,results):
    arrays=[np.load(out/f'cell_{i}_operators.npz',allow_pickle=False) for i in range(4)];pairs=[]
    for i,j in [(0,1),(2,3),(0,2),(1,3),(0,3),(1,2)]:
        x,y=arrays[i],arrays[j];ratio=round(len(y['t'])/len(x['t']))
        if not np.allclose(x['t'],y['t'][::ratio],rtol=0,atol=1e-14):raise ValueError('Not common clock')
        diff={key:float(np.max(abs(x[key]-y[key][::ratio]))) for key in ['r','u','tau','sigma','dhat']}
        diff.update({key:float(np.max(abs(x['state'][:,a:b]-y['state'][::ratio,a:b]))) for key,a,b in [('q_rad',0,7),('qd_rad_s',7,14),('z_Nm',14,21)]})
        ix,iy=common_energy_indices(x['energy_t'],y['energy_t'])
        et=x['energy_t'][ix];E1=np.cumsum(x['energy_increments']);E2=np.cumsum(y['energy_increments'])
        dE=E1[ix]-E2[iy]
        pairs.append({'cells':[i,j],'common_update_max_component_difference':diff,
            'cumulative_energy_difference_at_0p1s_J':{str(t):float(dE[np.searchsorted(et,t,side='right')-1]) for t in np.arange(.1,et[-1]+1e-9,.1)},
            'final_energy_difference_J':float(dE[-1])})
        np.savez_compressed(out/f'aligned_{i}_{j}.npz',t=x['t'],
            **{key+'_difference':x[key]-y[key][::ratio] for key in ['r','u','tau','sigma','state','dhat']},
            energy_t=et,cumulative_energy_difference_J=dE)
    write(out/'SUMMARY.json',{'scope':'LOCAL_READ_ONLY_MATERIAL_DERIVATIVE_AND_STAGE_DIAGNOSTICS',
        'cells':results,'aligned_pairs':pairs,'thresholds_changed':False,'A3':False,'Level1':False,'independent_signatures':None})

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reuse-cells',type=Path);p.add_argument('--alpha10',action='store_true');p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    write(a.output/'run_started.json',{'input':str(a.input.resolve()),'python':sys.version,'no_actuation':True,
        'analysis_source_sha256':sha(__file__),'module_sha256':sha(ROOT/'src/panda_closed_loop/active_sampled_analysis_v1.py')})
    if a.reuse_cells:
        results=[]
        for i in range(4):
            for suffix in ['.json','_operators.npz']:
                shutil.copy2(a.reuse_cells/f'cell_{i}{suffix}',a.output/f'cell_{i}{suffix}')
            results.append(json.loads((a.output/f'cell_{i}.json').read_text()))
        write(a.output/'PER_CELL_PROVENANCE.json',{'computed_by':'analyze_active_sampled_v1_2.py','copied_exact_bytes_from':str(a.reuse_cells),'aggregation_only_repaired':True})
    else:
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            futures=[pool.submit(cell_analysis,a.input,a.output,i,a.alpha10) for i in range(4)]
            results=[f.result() for f in futures]
    aggregate(a.output,results)

if __name__=='__main__':main()
