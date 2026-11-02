"""Independent data audit for the development projected-feedback sampler."""
import numpy as np
from .a2_acceptance import read_recorded_trace,scientific_digest
from .a2_qp_v2 import audit_qp_numerics,NUMERICAL_POLICY
from .p1_r3 import modeled_power
from .reference import ReferenceSample


def raw_kernel_kkt(update):
    d=update['diagnostics']['raw_feedback_QP_diagnostics'];G=np.array(update['G']);c=np.array(update['c']);sc=np.array(update['row_scales'])
    sigma=np.array(update['diagnostics']['current_filtered_feedback_Nm']);r=np.array(update['tracking_errors']['continuous_request_Nm'])
    den=87*np.linalg.norm(G,axis=1);den=np.where(den>0,den,1.)
    C=-87*G/den[:,None];b=(c-1e-8*sc)/den;z=np.array(d['dual_scaled']);y=sigma/87.
    return bool(np.all(G@sigma+c>=0) and np.all(abs(sigma)<=np.array([87]*4+[12]*3))
        and max(0.,np.max(C@y-b))<=1e-9 and np.max(abs(y-r/87.+C.T@z))<=1e-9
        and np.all(z>=-1e-9) and np.max(abs(z*(C@y-b)))<=1e-9
        and d['settings']==NUMERICAL_POLICY and d['cold_solves']==1
        and d['normalized_primal']<=1e-9 and d['scaled_stationarity']<=1e-9)


def audit_candidate(cell,out,system,plan):
    trace=read_recorded_trace(out,cell['a2']['trace']);updates=trace['updates'];steps=trace['substeps']
    checks={'original_endpoint_QP_reused':all(updates[0][k]==cell['endpoint']['QP'][k] for k in ['q','qd','z','dhat','varpi','G','c','candidate_tau']),
        'controller_history_and_final_target':True,'raw_feedback_KKT_and_signs':True,'current_model_rows_exact':True,
        'all_actual_held_torques_match_final_QP':True,'all_stage_physical_envelope_and_dense_checks':True,
        'power_quadrature_uses_actual_held_torque':True,'combined_query_count_and_budget':True,
        'no_raw_feedback_fallback':True}
    previous=None;delta=cell['grid']['control_period_s'];h=cell['grid']['rk4_step_s'];substeps=round(delta/h)
    for k,u in enumerate(updates):
        d=u['diagnostics'];r,_=system.controller.command(u['q'],u['qd'],ReferenceSample(**u['reference']),u['dhat'])
        sigma=np.array(d['current_filtered_feedback_Nm']);correction=np.zeros(7) if previous is None else .5*(sigma-previous)
        checks['controller_history_and_final_target'] &= bool(np.array_equal(r,u['tracking_errors']['continuous_request_Nm'])
            and np.array_equal(r+correction,u['u_nom']) and d['digital_update_index']==k
            and (d['previous_filtered_feedback_Nm'] is None if previous is None else np.array_equal(previous,d['previous_filtered_feedback_Nm'])))
        previous=sigma
        checks['raw_feedback_KKT_and_signs'] &= raw_kernel_kkt(u)
        rows=system.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        checks['current_model_rows_exact'] &= np.array_equal(rows.G,u['G']) and np.array_equal(rows.c,u['c'])
        checks['combined_query_count_and_budget'] &= d['combined_kernel_solves']==(1 if k==0 else 2) and d['combined_query_wall_budget_s']==15.
        checks['no_raw_feedback_fallback'] &= d['no_fallback'] and not d['raw_feedback_query_actuated_separately']
    for j,s in enumerate(steps):
        tau=np.array(s['applied_tau']);checks['all_actual_held_torques_match_final_QP'] &= np.array_equal(tau,updates[j//substeps]['candidate_tau'])
        checks['all_stage_physical_envelope_and_dense_checks'] &= all(s['checks'].values())
        checks['all_stage_physical_envelope_and_dense_checks'] &= all(sample['physical_slacks']['passed'] and np.all(np.array(sample['observer_envelope_slack'])>=0) for sample in s['samples'])
        values=[modeled_power(tau,np.array(sample['qd']),system.policy.raw['energy']) for sample in s['samples'][:4]]
        energy=h*(values[0]+2*values[1]+2*values[2]+values[3])/6
        checks['power_quadrature_uses_actual_held_torque'] &= np.isclose(energy,s['modeled_electrical_energy_increment_J'],rtol=1e-12,atol=1e-14)
    checks['full_horizon_counts']=len(updates)==round(1/delta) and len(steps)==round(1/h) and cell['a2']['final_state']['physical_t_s']==1.
    final=audit_qp_numerics(updates,system.barriers.taumax);checks['final_kernel_original_and_guarded_KKT']=final['passed']
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':all(checks.values()),'checks':checks,'final_kernel_numerics':final,
        'scope':'LOCAL_VERSIONED_SAMPLER_AUDIT_TWO_DECLARED_KERNELS_NO_EXTERNAL_SIGNATURE',
        'historical_acceptance_thresholds_unchanged':True}
