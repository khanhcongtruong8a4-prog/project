"""Second-order sampled torque requests and evidence-backed numerical A2 gate.

The continuous Slotine--Li law, safety QP, plant and observer are unchanged.
This version changes the execution sampling rule, not its physical gains.
"""
import gzip
import hashlib
import json
import numpy as np
from panda_dynamics import disturbance_bounds, dual_harmonic_disturbance
from .contracts import vector
from .controller import SlotineLiController
from .observer import ObserverEnvelope
from .reference import ReferenceSample
from .p1_r3 import compare_refinement, modeled_power


class AB2TorqueController:
    """Causal average request: u0=r0; uk=rk+(rk-r{k-1})/2.

    For smooth requests this approximates the interval-average torque to second
    order. It is a new digital realization, not an exact continuous controller
    or stability proof. No future state, true disturbance or future estimate is
    used. Each cell owns a fresh instance; preparation never touches its history.

    One command call per attempted QP update is mandatory. The endpoint solve
    is reused for the first application. A rejected QP ends the cell; there is
    no retry with consumed history or reuse of the instance for another cell.
    """
    def __init__(self, continuous_controller):
        self.continuous = continuous_controller
        self._previous = None
        self.updates = 0

    def command(self, q, qd, reference, dhat):
        raw, errors = self.continuous.command(q, qd, reference, dhat)
        raw = vector(raw, 'current continuous torque request')
        previous = None if self._previous is None else self._previous.copy()
        correction = np.zeros(7) if previous is None else .5*(raw-previous)
        proposal = vector(raw+correction, 'AB2 sampled interval torque request')
        index = self.updates
        self._previous = raw.copy()
        self.updates += 1
        return proposal, {**errors, 'continuous_request_Nm': raw,
                          'previous_continuous_request_Nm': previous,
                          'sampling_correction_Nm': correction,
                          'sampling_update_index': index,
                          'sampling_rule': 'BOOTSTRAP_CURRENT' if previous is None else 'AB2_CAUSAL_INTERVAL_AVERAGE'}


def _load_trace(out, record):
    p = out/record['file']
    payload = p.read_bytes()
    if hashlib.sha256(payload).hexdigest() != record['sha256']:
        raise ValueError('Trace file hash mismatch: '+str(p))
    raw = gzip.decompress(payload)
    if hashlib.sha256(raw).hexdigest() != record['uncompressed_json_sha256']:
        raise ValueError('Trace JSON hash mismatch: '+str(p))
    return json.loads(raw)


def audit_cell(cell, out, system, plan):
    """Recompute input history, actual endpoint rows, quadrature and bounds.

    All acceptance tests retain their exact original inequalities. The audit
    also requires exact reproduction of stored controller/row arithmetic.
    """
    checks = {}
    prep = cell.get('prehold', {})
    endpoint = cell.get('endpoint')
    execution = cell.get('a2', {})
    if not prep.get('completed') or not endpoint or not execution.get('completed'):
        return {'passed': False, 'checks': {'complete_prehold_endpoint_and_execution': False}}
    hold = _load_trace(out, prep['trace'])
    motion = _load_trace(out, execution['trace'])
    updates, steps = motion['updates'], motion['substeps']
    dt, h = cell['grid']['control_period_s'], cell['grid']['rk4_step_s']
    duration, tpre = plan['A2_reference']['duration_s'], plan['T_pre_s']
    checks['full_horizon_counts'] = (len(hold) == round(tpre/h) and len(steps) == round(duration/h)
                                      and len(updates) == round(duration/dt)
                                      and steps[-1]['physical_t1_s'] == duration)
    checks['actual_zero_state_and_first_QP_reuse'] = (
        hold[-1]['state_after'] == endpoint['state'] == prep['state']
        and endpoint['state']['physical_t_s'] == 0.
        and not endpoint['observer_reset'] and not endpoint['clock_reset']
        and all(updates[0][k] == endpoint['QP'][k] for k in ['q', 'qd', 'z', 'dhat', 'varpi', 'G', 'c', 'candidate_tau']))
    checks['hold_windows_and_checks'] = all(all(step['checks'].values()) for step in hold)
    checks['hold_peaks'] = (np.all(np.array(prep['q_deviation_peak_rad']) <= plan['q_radius_rad'])
                              and np.all(np.array(prep['qd_peak_rad_s']) <= plan['qd_radius_rad_s']))
    bounds = disturbance_bounds(system.policy.raw['disturbance']['amplitude_fraction'])
    envelope = ObserverEnvelope(system.policy.ko, *bounds)
    raw_controller = SlotineLiController(system.model, system.policy.lambdas, system.policy.kappa)
    previous = None
    requests_ok, rows_ok, all_raw_ok = True, True, True
    minimum_row, intervention, max_sampling = np.inf, 0., 0.
    max_primal, max_stationarity = 0., 0.
    for index, update in enumerate(updates):
        ref = ReferenceSample(**update['reference'])
        raw, _ = raw_controller.command(update['q'], update['qd'], ref, update['dhat'])
        correction = np.zeros(7) if previous is None else .5*(raw-previous)
        detail = update['tracking_errors']
        requests_ok &= (detail['sampling_update_index'] == index
                        and np.array_equal(raw, detail['continuous_request_Nm'])
                        and np.array_equal(raw+correction, update['u_nom'])
                        and np.array_equal(correction, detail['sampling_correction_Nm'])
                        and ((previous is None and detail['previous_continuous_request_Nm'] is None)
                             or np.array_equal(previous, detail['previous_continuous_request_Nm'])))
        previous = raw
        max_sampling = max(max_sampling, float(np.linalg.norm(correction)))
        rows = system.barriers.rows(update['q'], update['qd'], update['dhat'], update['varpi'])
        tau = np.array(update['candidate_tau'])
        actual_raw = rows.slacks(tau)
        rows_ok &= (len(rows.names) == 43 and np.array_equal(rows.G, update['G'])
                    and np.array_equal(rows.c, update['c'])
                    and np.array_equal(actual_raw, update['raw_slacks'])
                    and np.array_equal(rows.scales, update['row_scales']))
        all_raw_ok &= (np.all(actual_raw >= 0) and update['strict_pass'] and update['torque_applied']
                       and update['diagnostics']['normalized_primal'] <= 1e-9
                       and update['diagnostics']['scaled_stationarity'] <= 1e-9)
        minimum_row = min(minimum_row, float(np.min(actual_raw/rows.scales)))
        intervention = max(intervention, float(np.linalg.norm(tau-update['u_nom'])))
        max_primal = max(max_primal, update['diagnostics']['normalized_primal'])
        max_stationarity = max(max_stationarity, update['diagnostics']['scaled_stationarity'])
    checks.update(causal_controller_history=requests_ok, recomputed_all_43_QP_rows=rows_ok,
                  strict_nonnegative_rows_and_T29=all_raw_ok)
    state_ok, held_ok, envelope_ok, quadrature_ok = True, True, True, True
    min_observer = np.full(7, np.inf)
    energy = 0.
    for step in steps:
        tau = np.array(step['applied_tau'])
        held_ok &= np.array_equal(tau, updates[step['control_period_index']]['candidate_tau'])
        for sample in step['samples']:
            held_ok &= np.array_equal(tau, sample['tau_applied'])
            physical = system.barriers.entry_conditions(sample['q'], sample['qd'], tau)
            state_ok &= physical['passed'] and sample['physical_slacks']['passed']
            vp = envelope.value(sample['physical_t_s']+tpre)
            truth = dual_harmonic_disturbance(sample['physical_t_s'], system.policy.raw['disturbance']['amplitude_fraction'])
            slack = vp-abs(truth-sample['dhat'])
            envelope_ok &= (np.array_equal(vp, sample['varpi'])
                            and np.array_equal(truth, sample['truth_post_control_only']) and np.all(slack >= 0))
            min_observer = np.minimum(min_observer, slack)
        powers = [modeled_power(tau, s['qd'], system.policy.raw['energy']) for s in step['samples'][:4]]
        delta = h*(powers[0]+2*powers[1]+2*powers[2]+powers[3])/6
        quadrature_ok &= abs(delta-step['modeled_electrical_energy_increment_J']) <= 1e-16
        energy += delta
    metrics = execution['metrics']
    checks.update(physical_samples=state_ok, exact_ZOH_input=held_ok, original_observer_bound=envelope_ok,
                  RK4_energy_recalculation=quadrature_ok and abs(energy-metrics['modeled_electrical_energy_J']) <= 1e-13,
                  recomputed_metrics=(minimum_row == metrics['minimum_normalized_raw_slack']
                                      and intervention == metrics['maximum_intervention_Nm']
                                      and np.array_equal(min_observer, metrics['minimum_observer_envelope_slack_Nm'])))
    target = system.geometry.evaluate(execution['reference_target_q'])['f']
    actual = system.geometry.evaluate(execution['final_state']['q'])['f']
    checks['terminal_task'] = (np.linalg.norm(actual-target) <= plan['fixed_acceptance_thresholds']['actual_terminal_error_m']
                               and metrics['planned_terminal_error_m'] <= plan['fixed_acceptance_thresholds']['planned_terminal_error_m'])
    return {'passed': bool(all(checks.values())), 'checks': checks,
            'QP_updates': len(updates), 'stage_and_endpoint_samples': sum(len(s['samples']) for s in steps),
            'maximum_sampling_correction_Nm': max_sampling,
            'maximum_QP_correction_Nm': intervention,
            'maximum_normalized_primal': max_primal, 'maximum_scaled_stationarity': max_stationarity,
            'scope': 'ENGINEERING_RECOMPUTATION_NOT_INDEPENDENT_HUMAN_REVIEW'}


def numerical_gate(cells, plan, engineering):
    """A GO is computed from complete evidence, including the confirmation grid."""
    expected = plan['C4_grid']
    checks = {
        'explicit_numerical_authority': plan['authorization']['P1_A2_numerical_testing'] is True,
        'exact_grid_coverage': len(cells) == len(expected) and [c.get('grid') for c in cells] == expected,
        'every_prehold_and_endpoint': bool(cells) and all(c.get('prehold', {}).get('completed')
            and (c.get('endpoint') or {}).get('valid_zero_endpoint') for c in cells),
        'every_full_A2_cell': bool(cells) and all(c.get('a2', {}).get('completed') and c.get('a2', {}).get('passed') for c in cells),
        'every_trace_audited': bool(cells) and all(c.get('audit', {}).get('passed') for c in cells),
        'two_declared_cohorts': (set(plan.get('cohorts', {})) == {'original_C4', 'finer_confirmation'}
            and all(len(v) == 4 and len(set(v)) == 4 for v in plan.get('cohorts', {}).values())),
        'engineering_prerequisites': all(engineering.get(k) is True for k in [
            'frozen_inputs_unchanged', 'contracts_pass', 'base_regressions_match_current_inputs',
            'geometry_equivalence_pass', 'pinned_versions_match', 'canonical_model_audit_pass']),
    }
    cohorts = {}
    for name, indices in plan['cohorts'].items():
        available = len(cells) == len(expected) and len(indices) == 4 and all(0 <= i < len(cells) for i in indices)
        result = compare_refinement([cells[i] for i in indices] if available else [], plan['fixed_acceptance_thresholds'])
        cohorts[name] = result
        # The additional diagonal requirement is stricter than the old protocol.
        checks[name+'_all_refinements'] = result['passed'] and all(c['status'] == 'PASS' for c in result['comparisons'])
    passed = all(checks.values())
    return {'status': 'GO' if passed else 'HOLD', 'A2_numerical': 'PASS' if passed else 'FAIL',
            'scope': 'USER_AUTHORIZED_LEVEL_2_A2_SIMULATION_ONLY', 'checks': checks, 'cohorts': cohorts,
            'independent_controls_signature': None, 'independent_theory_signature': None,
            'independently_approved_experiment': 'NOT_CLAIMED', 'hardware_real_time': 'NOT_VALIDATED',
            'A3': 'NO-GO', 'publication': 'NO-GO'}
