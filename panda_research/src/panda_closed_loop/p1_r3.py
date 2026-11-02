"""Frozen r3 simulation tools; no hardware or independent-review authority.

The startup law is separate from the unchanged Slotine--Li execution law.
All true-disturbance access is confined to plant integration and diagnostics.
"""
from time import perf_counter
import numpy as np
from .contracts import scalar, vector
from .reference import ReferenceSample
from .a2_plan import quintic_reference_coefficients
from .preparation import component_extrema, rk4_extension_coefficients
from .stepper import ExecutionState


class SampledComputedTorque:
    """M(q)(Kp(q_ref-q)-Kd v)+C(q,v)v+g(q)+F(v)-dhat.

    Called only at control instants. The preparation harness projects once
    onto the physical torque box and supplies that same held input to the DOB.
    This is a distinct startup controller, not a gain change to the paper law.
    """
    def __init__(self, model, kp, kd):
        self.model = model
        self.kp = vector(kp, 'startup Kp s^-2')
        self.kd = vector(kd, 'startup Kd s^-1')
        if np.any(self.kp <= 0) or np.any(self.kd <= 0):
            raise ValueError('Startup gains must be positive')

    def command(self, q, qd, reference, dhat):
        q, v, dhat = vector(q, 'q'), vector(qd, 'qd'), vector(dhat, 'dhat')
        if not isinstance(reference, ReferenceSample):
            raise ValueError('Expected ReferenceSample')
        if np.any(reference.qd != 0) or np.any(reference.qdd != 0):
            raise ValueError('r3 startup requires a static reference')
        a = self.kp*(reference.q-q)-self.kd*v
        e = self.model.evaluate(q, v)
        tau = e['M']@a+e['C']@v+e['g']+e['F']-dhat
        return vector(tau, 'startup u_nom N m'), {'acceleration_command': a}

    def frozen_double_integrator_matrix(self, delta, joint=0):
        dt = scalar(delta, 'Delta', positive=True)
        kp, kd = self.kp[joint], self.kd[joint]
        return np.array([[1-.5*dt*dt*kp, dt-.5*dt*dt*kd],
                         [-dt*kp, 1-dt*kd]])


class QuinticMeasuredReference:
    """Predeclared Hermite rule, instantiated only from the measured endpoint."""
    def __init__(self, q, qd, offset, duration):
        self.duration = scalar(duration, 'reference duration', positive=True)
        self.coefficients = quintic_reference_coefficients(q, qd, offset, self.duration)
        self.target_q = vector(q, 'start q')+vector(offset, 'offset')

    def sample(self, t):
        t = scalar(t, 'reference physical t', nonnegative=True)
        if t > self.duration+1e-12:
            raise ValueError('Reference requested beyond its frozen horizon')
        s = min(t/self.duration, 1.)
        c = self.coefficients
        q = np.polynomial.polynomial.polyval(s, c)
        v = np.polynomial.polynomial.polyval(s, np.arange(1, 6)[:, None]*c[1:])/self.duration
        a = np.polynomial.polynomial.polyval(s, (np.arange(2, 6)*np.arange(1, 5))[:, None]*c[2:])/self.duration**2
        return ReferenceSample(q, v, a)


def strict_qp_check(system, state, envelope, reference):
    """Actual 43-row solve; reject every negative raw row before actuation.

    Keep the original solver and its outputs, including near-resolution failures.
    No clipping, solver retuning, second solve or fabricated recovery is used.
    """
    estimate = system.observer.estimate(state.q, state.qd, state.z)
    nominal, errors = system.controller.command(state.q, state.qd, reference.sample(state.t), estimate)
    varpi = envelope.value(state.t)
    rows = system.barriers.rows(state.q, state.qd, estimate, varpi)
    start = perf_counter()
    solved = system.qp.solve(nominal, rows)
    runtime = perf_counter()-start
    applied = solved.applied
    raw = rows.slacks(applied) if applied is not None else None
    passed = (len(rows.names) == 43 and not solved.stop_requested and raw is not None
              and np.all(raw >= 0)
              and solved.diagnostics.get('normalized_primal', np.inf) <= 1e-9
              and solved.diagnostics.get('scaled_stationarity', np.inf) <= 1e-9)
    record = {'physical_t_s': state.t, 'q': state.q, 'qd': state.qd, 'z': state.z,
              'dhat': estimate, 'varpi': varpi, 'u_nom': nominal,
              'reference': {'q': reference.sample(state.t).q, 'qd': reference.sample(state.t).qd,
                            'qdd': reference.sample(state.t).qdd},
              'tracking_errors': errors, 'status': solved.status, 'strict_pass': bool(passed),
              'solve_runtime_s': runtime, 'G': rows.G, 'c': rows.c,
              'row_names': rows.names, 'row_units': rows.units, 'row_scales': rows.scales,
              'raw_slacks': raw, 'normalized_raw_slacks': None if raw is None else raw/rows.scales,
              'candidate_tau': applied, 'diagnostics': solved.diagnostics,
              'torque_applied': False}
    return applied if passed else None, record


def modeled_power(tau, v, energy):
    """Shared-bus non-regenerative model, smoothing AFTER the joint sum."""
    tau, v = vector(tau, 'tau'), vector(v, 'v')
    kr = vector(energy['k_r'], 'k_r', nonnegative=True)
    z = float(np.sum(tau*v+kr*tau*tau))
    epsilon = scalar(energy['nonregenerative_smoothing']['epsilon_W'], 'epsilon W', positive=True)
    return .5*(z+np.hypot(z, epsilon))


def diagnostic_sample(system, envelope, plant_disturbance, t, x, tau):
    q, v, z = x[:7], x[7:14], x[14:21]
    estimate = system.observer.estimate(q, v, z)
    truth = vector(plant_disturbance(t), 'post-control diagnostic truth')
    varpi = envelope.value(t)
    return {'physical_t_s': t, 'q': q.copy(), 'qd': v.copy(), 'z': z.copy(),
            'tau_applied': tau, 'dhat': estimate, 'varpi': varpi,
            'truth_post_control_only': truth, 'observer_envelope_slack': varpi-abs(truth-estimate),
            'physical_slacks': system.barriers.entry_conditions(q, v, tau)}


def integrate_substep(system, state, tau, h, end_t, envelope, plant_disturbance):
    """Coupled RK4, plus consistent RK4 quadrature of modeled electrical power."""
    x = np.r_[state.q, state.qd, state.z, 0.]
    retained = []
    def derivative(t, sx):
        q, v, z = sx[:7], sx[7:14], sx[14:21]
        d = vector(plant_disturbance(t), 'plant-only disturbance')
        e = system.model.evaluate(q, v)
        acc = np.linalg.solve(e['M'], tau+d-e['C']@v-e['g']-e['F'])
        zdot = system.observer.derivative(q, v, z, tau)
        retained.append((t, sx.copy()))
        return np.r_[v, acc, zdot, modeled_power(tau, v, system.policy.raw['energy'])]
    t = state.t
    k1 = derivative(t, x)
    k2 = derivative(t+h/2, x+h*k1/2)
    k3 = derivative(t+h/2, x+h*k2/2)
    k4 = derivative(end_t, x+h*k3)
    after = x+h*(k1+2*k2+2*k3+k4)/6
    final = ExecutionState(after[:7], after[7:14], after[14:21], end_t)
    retained.append((end_t, after.copy()))
    samples = [diagnostic_sample(system, envelope, plant_disturbance, st, sx, tau) for st, sx in retained]
    dense = component_extrema(rk4_extension_coefficients(x, h, [k1, k2, k3, k4])[:, :14])
    checks = {'physical_samples': all(s['physical_slacks']['passed'] for s in samples),
              'observer_samples': all(np.all(s['observer_envelope_slack'] >= 0) for s in samples),
              'dense_joint_position': bool(np.all(dense['minimum'][:7] >= system.barriers.qmin)
                                           and np.all(dense['maximum'][:7] <= system.barriers.qmax)),
              'dense_joint_speed': bool(np.all(dense['minimum'][7:14] >= -system.barriers.vmax)
                                        and np.all(dense['maximum'][7:14] <= system.barriers.vmax))}
    return final, {'physical_t0_s': t, 'physical_t1_s': end_t, 'applied_tau': tau,
                   'modeled_electrical_energy_increment_J': float(after[-1]),
                   'samples': samples, 'dense_extension': dense, 'checks': checks}


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


def compare_refinement(cells, thresholds):
    """Four fixed-factor edges are mandatory; disclose both diagonal pairs."""
    absolute = {'modeled_electrical_energy_J': 'energy_abs_J', 'duration_s': 'duration_abs_s',
                'maximum_intervention_Nm': 'intervention_difference_abs_Nm',
                'minimum_normalized_raw_slack': 'normalized_slack_difference_abs'}
    comparisons = []
    full_grid = len(cells) == 4
    for i, j, factor in [(0, 1, 'h'), (2, 3, 'h'), (0, 2, 'Delta'), (1, 3, 'Delta'),
                          (0, 3, 'cross_diagonal'), (1, 2, 'cross_diagonal')]:
        available = full_grid and all(cells[k].get('a2', {}).get('completed') for k in [i, j])
        row = {'cells': [i, j], 'factor': factor, 'required': factor != 'cross_diagonal',
               'status': 'NOT_COMPARABLE_INCOMPLETE_HORIZON', 'metrics': {}}
        if available:
            for name, key in absolute.items():
                a, b = [cells[k]['a2']['metrics'][name] for k in [i, j]]
                limit = max(thresholds[key], thresholds['relative_refinement']*max(abs(a), abs(b)))
                difference = abs(a-b)
                row['metrics'][name] = {'values': [a, b], 'absolute_difference': difference,
                                        'tolerance': limit, 'passed': difference <= limit}
            row['status'] = 'PASS' if all(m['passed'] for m in row['metrics'].values()) else 'FAIL'
        comparisons.append(row)
    passed = full_grid and all(c.get('a2', {}).get('passed') for c in cells)
    passed = passed and all(c['status'] == 'PASS' for c in comparisons if c['required'])
    return {'passed': bool(passed), 'comparisons': comparisons,
            'rule': 'Each fixed-factor edge; max(absolute, relative*max(abs(values))). Diagonals disclosed separately.'}
