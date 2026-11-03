"""Versioned development sampler for the unchanged projected continuous law.

sigma_k=P_Ck(r_k), u_k=r_k+(sigma_k-sigma_{k-1})/2, tau_k=P_Ck(u_k).
Bootstrap uses u_0=r_0. In an inactive region sigma=r and this is the original
AB2 rule. As Delta tends to zero the realized map tends to P_C(r). Moving
active faces can still reduce order: no second-order or stability theorem is
claimed. Every actual torque satisfies the original guarded current-state QP.

The raw-feedback solve is never a fallback. A failure of either required
solve stops the query. The combined two-kernel query has the SAME 15 s budget.
"""
import multiprocessing as mp
import numpy as np
from .a2_qp_reliable_v1_1 import GuardedHardQP
from .a2_qp_reliable_v1 import BoundedGuardedQP as OriginalBoundedQP
from .a2_qp_v2 import NUMERICAL_POLICY
from .qp import QPResult
from .p1_r3 import strict_qp_check as original_strict_check

VERSION='PROJECTED_FEEDBACK_AB2_V1_DEVELOPMENT_CANDIDATE'


class ProjectedFeedbackAB2QP:
    def __init__(self,limits):
        self.kernel=GuardedHardQP(limits);self.previous=None;self.index=0
    def solve(self,raw,rows):
        raw=np.asarray(raw,dtype=float);first=self.kernel.solve(raw,rows)
        if first.stop_requested:
            first.diagnostics['candidate_sampler_failure_stage']='RAW_FEEDBACK_QP'
            first.diagnostics['combined_kernel_solves']=1
            return first
        sigma=first.applied.copy();previous=None if self.previous is None else self.previous.copy()
        correction=np.zeros(7) if previous is None else .5*(sigma-previous)
        target=raw+correction
        final=first if previous is None else self.kernel.solve(target,rows)
        raw_diagnostics=dict(first.diagnostics)
        final.diagnostics.update(candidate_sampler_version=VERSION,digital_update_index=self.index,
            raw_request_Nm=raw.tolist(),current_filtered_feedback_Nm=sigma.tolist(),
            previous_filtered_feedback_Nm=None if previous is None else previous.tolist(),
            digital_request_Nm=target.tolist(),sampling_correction_Nm=correction.tolist(),
            raw_feedback_QP_diagnostics=raw_diagnostics,
            raw_feedback_query_actuated_separately=False,
            combined_kernel_solves=1 if previous is None else 2,
            combined_query_wall_budget_s=15.,no_fallback=True)
        if not final.stop_requested:self.previous=sigma;self.index+=1
        return final


def _worker(connection,limits):
    qp=ProjectedFeedbackAB2QP(limits)
    try:
        connection.send('READY')
        while True:
            payload=connection.recv()
            if payload is None:break
            connection.send(qp.solve(*payload))
    finally:connection.close()


class BoundedProjectedFeedbackAB2QP(OriginalBoundedQP):
    def __enter__(self):
        ctx=mp.get_context('spawn');self.connection,child=ctx.Pipe()
        self.process=ctx.Process(target=_worker,args=(child,self.taumax),daemon=True)
        self.process.start();child.close()
        if not self.connection.poll(self.timeout_s) or self.connection.recv()!='READY':
            self.close();raise RuntimeError('Combined QP worker did not initialize')
        return self


def strict_qp_check(system,state,envelope,reference):
    tau,record=original_strict_check(system,state,envelope,reference)
    diagnostic=record['diagnostics']
    if 'digital_request_Nm' in diagnostic:
        # The original loop's metric remains ||tau-u_nom||. Its recorded nominal
        # is the explicitly declared target of the FINAL QP, not the raw r.
        raw=record['u_nom'];record['u_nom']=diagnostic['digital_request_Nm']
        record['tracking_errors'].update(continuous_request_Nm=raw,
            previous_filtered_feedback_Nm=diagnostic['previous_filtered_feedback_Nm'],
            current_filtered_feedback_Nm=diagnostic['current_filtered_feedback_Nm'],
            sampling_correction_Nm=diagnostic['sampling_correction_Nm'],
            sampling_update_index=diagnostic['digital_update_index'],
            sampling_rule=VERSION)
    return tau,record


# The integration and acceptance-metric loop below is copied verbatim from
# preserved p1_r3.py. Only its module-level QP query binding is versioned.
from .p1_r3 import integrate_substep

def run_a2_cell(system, state, schedule, envelope, reference, plant_disturbance, endpoint_check):
    """One frozen cell, first-failure stop with every attempted step retained."""
    duration = reference.duration
    periods = round(duration/schedule.delta)
    if abs(duration-periods*schedule.delta) > 1e-12 or state.t != 0.:
        raise ValueError('A2 requires aligned duration and a measured zero-time state')
    initial = system.barriers.entry_conditions(state.q, state.qd)
    updates, trace, failure = [], [], None
    energy, min_raw, intervention = 0., np.inf, 0.
    max_primal, max_stationarity = 0., 0.
    min_envelope = np.full(7, np.inf)
    if not initial['passed'] or not endpoint_check['strict_pass']:
        failure = {'reason': 'INVALID_ACTUAL_ZERO_ENDPOINT', 'physical_t_s': 0.}
    for period in range(periods if failure is None else 0):
        # Reuse the actual endpoint solve at t=0; never resample/reset its state.
        if period == 0:
            update = dict(endpoint_check)
            tau = update['candidate_tau']
        else:
            tau, update = strict_qp_check(system, state, envelope, reference)
        updates.append(update)
        if tau is None or not update['strict_pass']:
            failure = {'reason': 'HARD_QP_FAILURE_NO_ADVANCE', 'physical_t_s': state.t,
                       'status': update['status'], 'no_additional_torque_applied': True}
            break
        min_raw = min(min_raw, float(np.min(update['normalized_raw_slacks'])))
        intervention = max(intervention, float(np.linalg.norm(tau-update['u_nom'])))
        max_primal = max(max_primal, update['diagnostics']['normalized_primal'])
        max_stationarity = max(max_stationarity, update['diagnostics']['scaled_stationarity'])
        update['torque_applied'] = True
        for j in range(schedule.substeps):
            index = period*schedule.substeps+j
            end_t = duration if index+1 == periods*schedule.substeps else (index+1)*schedule.h
            state, step = integrate_substep(system, state, tau, schedule.h, end_t, envelope, plant_disturbance)
            step.update(control_period_index=period, substep_index=j)
            trace.append(step)
            energy += step['modeled_electrical_energy_increment_J']
            for sample in step['samples']:
                min_envelope = np.minimum(min_envelope, sample['observer_envelope_slack'])
            if not all(step['checks'].values()):
                failure = {'reason': 'A2_NUMERICAL_ACCEPTANCE_FAILURE', 'physical_t_s': state.t,
                           'failed_checks': [k for k, v in step['checks'].items() if not v],
                           'no_further_torque_or_state_advance': True}
                break
        if failure:
            break
    completed = failure is None and state.t == duration
    target = system.geometry.evaluate(reference.target_q)['f']
    actual = system.geometry.evaluate(state.q)['f']
    planned = system.geometry.evaluate(reference.sample(duration).q)['f']
    planned_error, actual_error = float(np.linalg.norm(planned-target)), float(np.linalg.norm(actual-target))
    thresholds = system.policy.raw['fixed_acceptance_thresholds']
    terminal_ok = (planned_error <= thresholds['planned_terminal_error_m']
                   and actual_error <= thresholds['actual_terminal_error_m'])
    passed = completed and terminal_ok
    if completed and not terminal_ok:
        failure = {'reason': 'TERMINAL_TASK_TOLERANCE', 'physical_t_s': duration}
    metrics = {'modeled_electrical_energy_J': energy, 'duration_s': state.t,
               'maximum_intervention_Nm': intervention,
               'minimum_normalized_raw_slack': float(min_raw) if np.isfinite(min_raw) else None,
               'max_normalized_primal': max_primal if updates else None,
               'max_scaled_stationarity': max_stationarity if updates else None,
               'minimum_observer_envelope_slack_Nm': min_envelope if trace else None,
               'planned_terminal_error_m': planned_error, 'actual_terminal_error_m': actual_error,
               'target_flange_m': target, 'zero_intervention_diagnostic': intervention <= thresholds['zero_intervention_Nm'],
               'control_updates_attempted': len(updates), 'substeps_attempted': len(trace),
               'metrics_cover_completed_horizon': completed,
               'energy_scope': 'EXECUTION_ONLY_RK4_SHARED_BUS_ELECTRICAL_MODEL_NO_TIME_PENALTY'}
    return {'completed': completed, 'passed': passed, 'failure': failure, 'metrics': metrics,
            'final_state': {'q': state.q, 'qd': state.qd, 'z': state.z, 'physical_t_s': state.t},
            'initial_physical_slacks': initial, 'reference_coefficients': reference.coefficients,
            'reference_target_q': reference.target_q, 'updates': updates, 'trace': trace}
