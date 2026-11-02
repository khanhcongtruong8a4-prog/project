"""Read-only audits of executed failed A2-Extended prefixes.

This never solves a QP, calls a plant stepper, applies torque or changes a
record. It recomputes functions at retained states and verifies logged RK4
arithmetic. A prefix-data audit PASS does not change scientific FAIL or the
incomplete horizon, and an abort distance is not terminal accuracy at T.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
from panda_dynamics import QMIN, QMAX, dual_harmonic_disturbance, disturbance_bounds
from panda_closed_loop.assembly import build_components
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.controller import SlotineLiController
from panda_closed_loop.observer import ObserverEnvelope
from panda_closed_loop.reference import ReferenceSample
from panda_closed_loop.p1_r3 import SampledComputedTorque, modeled_power
from panda_closed_loop.preparation import rk4_extension_coefficients, component_extrema
from panda_closed_loop.a2_extended import ExtendedReference
from panda_closed_loop.trace_archive import read_trace
from panda_closed_loop.logging import json_values

PLAN = ROOT/'policy/a2_extended_v1/A2_EXTENDED_PREDECLARATION.json'
FREEZE = ROOT/'policy/a2_extended_v1/FROZEN_INPUTS.json'


def write(path, value):
    with path.open('x') as f:
        json.dump(json_values(value), f, indent=2, allow_nan=False)
        f.write('\n')


def native_equal(a, b):
    return json_values(a) == json_values(b)


def state_vector(record):
    return np.r_[record['q'], record['qd'], record['z']]


class Checks:
    def __init__(self):
        self.rows = {}

    def add(self, name, passed, where=None, numeric_error=None):
        row = self.rows.setdefault(name, {'evaluations': 0, 'failed': 0})
        row['evaluations'] += 1
        if numeric_error is not None:
            row['max_absolute_reconstruction_error'] = max(row.get('max_absolute_reconstruction_error', 0.), float(numeric_error))
        if not passed:
            row['failed'] += 1
            row.setdefault('first_failure_location', where)

    @property
    def passed(self):
        return bool(self.rows) and all(v['failed'] == 0 for v in self.rows.values())


def statistics(vectors, delta):
    result = {}
    for name, rows in vectors.items():
        if not rows:
            result[name] = {'samples': 0, 'max_2norm_Nm': None, 'RMS_2norm_Nm': None}
            continue
        a = np.array(rows)
        norms = np.linalg.norm(a, axis=1)
        result[name] = {'samples': len(rows), 'max_2norm_Nm': float(np.max(norms)),
                        'RMS_2norm_Nm': float(np.sqrt(np.mean(norms**2))),
                        'time_weighted_RMS_2norm_Nm': float(np.sqrt(np.sum(delta*norms**2)/(len(rows)*delta))),
                        'component_max_abs_Nm': np.max(abs(a), axis=0),
                        'component_RMS_Nm': np.sqrt(np.mean(a*a, axis=0))}
    return {'definition': '7-joint Euclidean norm at applied control updates; Delta-weighted RMS over those fixed hold intervals.',
            'not_continuous_r_between_updates': True, 'statistics': result}


def sample_audit(system, envelope, sample, tau, checks, where, phase, minima):
    q, v, z = [np.array(sample[k]) for k in ['q', 'qd', 'z']]
    t = sample['physical_t_s']
    dhat = system.observer.estimate(q, v, z)
    vp = envelope.value(t)
    truth = dual_harmonic_disturbance(t, system.policy.raw['disturbance']['amplitude_fraction'])
    slack = vp-abs(truth-dhat)
    physical = system.barriers.entry_conditions(q, v, tau)
    tau_key = 'applied_tau' if phase == 'prehold' else 'tau_applied'
    checks.add(phase+'_held_input_at_each_sample', np.array_equal(sample[tau_key], tau), where)
    checks.add(phase+'_estimate_from_logged_q_qd_z', np.array_equal(dhat, sample['dhat']), where)
    checks.add(phase+'_original_signed_waveform_and_varpi', np.array_equal(truth, sample['truth_post_control_only'])
               and np.array_equal(vp, sample['varpi']), where)
    checks.add(phase+'_observer_slack_arithmetic', np.array_equal(slack, sample['observer_envelope_slack']), where)
    checks.add(phase+'_observer_raw_nonnegative', np.all(slack >= 0), where)
    checks.add(phase+'_physical_slack_arithmetic', native_equal(physical, sample['physical_slacks']), where)
    checks.add(phase+'_physical_raw_nonnegative', physical['passed'], where)
    minima['observer'] = np.minimum(minima['observer'], slack)
    for name, values in physical.items():
        if name == 'passed':
            continue
        if name not in minima['physical']:
            minima['physical'][name] = np.array(values)
        else:
            minima['physical'][name] = np.minimum(minima['physical'][name], values)


def rk4_audit(system, t0, t1, samples, tau, h, phase, checks, where):
    """Recompute derivatives at stored RK4 inputs, never integrate new motion."""
    x = state_vector(samples[0])
    if phase == 'execution':
        x = np.r_[x, 0.]
    ks = []
    for sample in samples[:4]:
        q, v, z = [np.array(sample[k]) for k in ['q', 'qd', 'z']]
        d = dual_harmonic_disturbance(sample['physical_t_s'], system.policy.raw['disturbance']['amplitude_fraction'])
        e = system.model.evaluate(q, v)
        acceleration = np.linalg.solve(e['M'], tau+d-e['C']@v-e['g']-e['F'])
        zdot = system.observer.derivative(q, v, z, tau)
        k = np.r_[v, acceleration, zdot]
        if phase == 'execution':
            k = np.r_[k, modeled_power(tau, v, system.policy.raw['energy'])]
        ks.append(k)
    expected = [x, x+h*ks[0]/2, x+h*ks[1]/2, x+h*ks[2], x+h*(ks[0]+2*ks[1]+2*ks[2]+ks[3])/6]
    for index, (predicted, actual) in enumerate(zip(expected, samples)):
        observed = state_vector(actual)
        error = float(np.max(abs(predicted[:21]-observed)))
        checks.add(phase+'_RK4_stage_and_endpoint_arithmetic', np.array_equal(predicted[:21], observed),
                   {**where, 'RK4_sample': index}, error)
    times = [t0, t0+h/2, t0+h/2, t0+h if phase == 'prehold' else t1, t1]
    checks.add(phase+'_RK4_times', all(a['physical_t_s'] == t for a, t in zip(samples, times)), where)
    dense = component_extrema(rk4_extension_coefficients(x, h, ks)[:, :14])
    energy = float(expected[-1][-1]) if phase == 'execution' else None
    return dense, energy


def audit_one(system, cell, folder, plan):
    checks = Checks()
    hold = read_trace(folder/cell['prehold']['trace']['file'], cell['prehold']['trace'])
    motion = read_trace(folder/cell['a2']['trace']['file'], cell['a2']['trace'])
    updates, steps = motion['updates'], motion['substeps']
    grid = cell['grid'];delta, h = grid['control_period_s'], grid['rk4_step_s']
    tpre = plan['T_pre_s']
    # Same signed physical clock as the run, not a reinitialized envelope.
    elapsed_envelope = ObserverEnvelope(system.policy.ko, *disturbance_bounds(system.policy.raw['disturbance']['amplitude_fraction']))
    class Envelope:
        def value(self, physical_t):return elapsed_envelope.value(physical_t+tpre)
    envelope = Envelope()
    minimum = {phase: {'observer': np.full(7, np.inf), 'physical': {}} for phase in ['prehold', 'execution']}
    qmid = (QMIN+QMAX)/2
    startup = SampledComputedTorque(system.model, plan['startup_controller']['kp_s_inverse_squared'], plan['startup_controller']['kd_s_inverse'])
    static_reference = ReferenceSample(qmid, np.zeros(7), np.zeros(7))
    checks.add('prehold_complete_count', cell['prehold']['completed'] and len(hold) == round(tpre/h))
    initial = hold[0]['state_before']
    expected_z = system.observer.initialize(qmid, np.zeros(7))
    checks.add('prehold_original_initialization', initial['physical_t_s'] == -tpre
               and np.array_equal(initial['q'], qmid) and np.array_equal(initial['qd'], np.zeros(7))
               and np.array_equal(initial['z'], expected_z))
    previous = None;held_tau = None
    for index, item in enumerate(hold):
        where = {'phase': 'prehold', 'substep': index, 't_s': item['physical_t0_s']}
        before, after = item['state_before'], item['state_after']
        checks.add('prehold_state_continuity', previous is None or before == previous, where)
        checks.add('prehold_record_times', before['physical_t_s'] == item['physical_t0_s']
                   and after['physical_t_s'] == item['physical_t1_s'], where)
        if item['substep_index'] == 0:
            estimate = system.observer.estimate(before['q'], before['qd'], before['z'])
            nominal, _ = startup.command(before['q'], before['qd'], static_reference, estimate)
            held_tau = np.clip(nominal, -system.barriers.taumax, system.barriers.taumax)
            checks.add('prehold_permitted_controller_and_actual_projection', np.array_equal(estimate, item['dhat_at_update'])
                       and np.array_equal(nominal, item['u_nom_at_update']), where)
        tau = np.array(item['tau_applied'])
        checks.add('prehold_ZOH_mapping', np.array_equal(tau, held_tau), where)
        samples = item['stage_and_endpoint_diagnostics']
        checks.add('prehold_record_samples_match_states', np.array_equal(state_vector(samples[0]), state_vector(before))
                   and np.array_equal(state_vector(samples[-1]), state_vector(after)), where)
        for n, sample in enumerate(samples):sample_audit(system, envelope, sample, tau, checks, {**where, 'sample': n}, 'prehold', minimum['prehold'])
        dense, _ = rk4_audit(system, item['physical_t0_s'], item['physical_t1_s'], samples, tau, h, 'prehold', checks, where)
        checks.add('prehold_cubic_extrema_reconstruction', native_equal(dense, item['dense_extension']), where)
        qpeak = np.maximum(abs(dense['minimum'][:7]-qmid), abs(dense['maximum'][:7]-qmid))
        vpeak = np.maximum(abs(dense['minimum'][7:14]), abs(dense['maximum'][7:14]))
        qpeak = np.maximum(qpeak, np.max([abs(np.array(s['q'])-qmid) for s in samples], axis=0))
        vpeak = np.maximum(vpeak, np.max([abs(np.array(s['qd'])) for s in samples], axis=0))
        checks.add('prehold_declared_windows', np.all(qpeak <= plan['q_radius_rad']) and np.all(vpeak <= plan['qd_radius_rad_s'])
                   and np.array_equal(qpeak, item['q_deviation_peak_rad']) and np.array_equal(vpeak, item['qd_peak_rad_s']), where)
        previous = after
    endpoint = cell['endpoint']
    checks.add('measured_zero_transfer_no_reset', previous == endpoint['state'] == cell['prehold']['state']
               and endpoint['state']['physical_t_s'] == 0. and endpoint['q_qd_z_transfer_exact']
               and not endpoint['observer_reset'] and not endpoint['clock_reset'])
    checks.add('first_QP_reuses_actual_endpoint_solve', all(updates[0][k] == endpoint['QP'][k]
               for k in ['q', 'qd', 'z', 'dhat', 'varpi', 'G', 'c', 'candidate_tau']))
    definition = plan['references'][cell['reference_id']]
    reference = ExtendedReference(endpoint['state']['q'], endpoint['state']['qd'], definition)
    checks.add('reference_fixed_from_actual_endpoint', np.array_equal(reference.coefficients, cell['a2']['reference_coefficients'])
               and np.array_equal(reference.target_q, cell['a2']['reference_target_q']))
    raw_controller = SlotineLiController(system.model, system.policy.lambdas, system.policy.kappa)
    old_raw = None;applied = [];negative_rows = [];unavailable = []
    vectors = {'u_minus_r': [], 'tau_minus_u': [], 'tau_minus_r': []}
    rejected = []
    for index, u in enumerate(updates):
        where = {'phase': 'execution_update', 'update': index, 't_s': u['physical_t_s']}
        r = reference.sample(u['physical_t_s'])
        raw, _ = raw_controller.command(u['q'], u['qd'], r, u['dhat'])
        correction = np.zeros(7) if old_raw is None else .5*(raw-old_raw)
        detail = u['tracking_errors']
        checks.add('actual_reference_and_digital_history', all(np.array_equal(getattr(r, k), u['reference'][k]) for k in ['q', 'qd', 'qdd'])
                   and np.array_equal(raw, detail['continuous_request_Nm']) and np.array_equal(raw+correction, u['u_nom'])
                   and np.array_equal(correction, detail['sampling_correction_Nm'])
                   and detail['sampling_update_index'] == index
                   and ((old_raw is None and detail['previous_continuous_request_Nm'] is None)
                        or np.array_equal(old_raw, detail['previous_continuous_request_Nm'])), where)
        old_raw = raw
        dhat = system.observer.estimate(u['q'], u['qd'], u['z'])
        vp = envelope.value(u['physical_t_s'])
        checks.add('update_actual_observer_and_original_bound', np.array_equal(dhat, u['dhat']) and np.array_equal(vp, u['varpi']), where)
        rows = system.barriers.rows(u['q'], u['qd'], u['dhat'], u['varpi'])
        checks.add('all_43_current_state_G_c_scales_names_units', len(rows.names) == 43
                   and np.array_equal(rows.G, u['G']) and np.array_equal(rows.c, u['c'])
                   and np.array_equal(rows.scales, u['row_scales']) and list(rows.names) == u['row_names'] and list(rows.units) == u['row_units'], where)
        checks.add('solver_settings_unchanged', u['diagnostics']['settings'] == system.policy.raw['solver']['QP_settings'], where)
        candidate = u['candidate_tau']
        if candidate is None:candidate = u['diagnostics'].get('tau_candidate')
        if candidate is not None:
            candidate = np.array(candidate);slacks = rows.slacks(candidate)
            saved = u['raw_slacks'] if u['raw_slacks'] is not None else u['diagnostics'].get('raw_slacks')
            checks.add('available_candidate_raw_slacks_exact', saved is not None and np.array_equal(slacks, saved), where)
            for j in np.where(slacks < 0)[0]:negative_rows.append({'update': index, 't_s': u['physical_t_s'],
                'row': rows.names[j], 'raw_value': float(slacks[j]), 'torque_applied': u['torque_applied']})
        else:
            slacks = None
            unavailable.append({'update': index, 't_s': u['physical_t_s'], 'status': u['status'],
                                'candidate_and_raw_solution_slacks': 'NOT_RETAINED_UNAVAILABLE',
                                'no_infeasibility_or_negative_row_inferred_from_absence': True})
        if u['torque_applied']:
            tau = np.array(u['candidate_tau']);applied.append(u)
            checks.add('all_applied_QPs_strict_raw_and_reported_T29', u['strict_pass'] and slacks is not None and np.all(slacks >= 0)
                       and u['diagnostics']['normalized_primal'] <= 1e-9 and u['diagnostics']['scaled_stationarity'] <= 1e-9, where)
            vectors['u_minus_r'].append(np.array(u['u_nom'])-raw)
            vectors['tau_minus_u'].append(tau-u['u_nom'])
            vectors['tau_minus_r'].append(tau-raw)
        else:
            rejected.append({'update': index, 't_s': u['physical_t_s'], 'status': u['status'],
                             'strict_pass': u['strict_pass'], 'candidate_retained': candidate is not None,
                             'sampling_u_minus_r_2norm_Nm': float(np.linalg.norm(np.array(u['u_nom'])-raw)),
                             'candidate_tau_minus_u_2norm_Nm': None if candidate is None else float(np.linalg.norm(candidate-u['u_nom'])),
                             'candidate_tau_minus_r_2norm_Nm': None if candidate is None else float(np.linalg.norm(candidate-raw)),
                             'candidate_NOT_APPLIED': True})
            checks.add('rejected_candidate_not_applied_or_strictly_accepted', not u['strict_pass'], where)
    checks.add('one_final_rejected_update_and_no_retry', len(rejected) == 1 and rejected[0]['update'] == len(updates)-1
               and len(applied)+1 == len(updates))
    checks.add('whole_applied_intervals_only_before_QP_stop', len(steps) == len(applied)*round(delta/h))
    previous = endpoint['state'];energy = 0.;minimum_row = np.inf;maximum_correction = 0.
    for u in applied:
        minimum_row = min(minimum_row, float(np.min(u['normalized_raw_slacks'])))
        maximum_correction = max(maximum_correction, float(np.linalg.norm(np.array(u['candidate_tau'])-u['u_nom'])))
    for index, step in enumerate(steps):
        where = {'phase': 'execution_substep', 'substep': index, 't_s': step['physical_t0_s']}
        tau = np.array(step['applied_tau']);samples = step['samples']
        period = step['control_period_index']
        checks.add('execution_ZOH_period_mapping', period < len(applied) and applied[period]['torque_applied']
                   and np.array_equal(tau, applied[period]['candidate_tau'])
                   and period == index//round(delta/h) and step['substep_index'] == index % round(delta/h), where)
        checks.add('execution_state_continuity', np.array_equal(state_vector(samples[0]), state_vector(previous))
                   and samples[0]['physical_t_s'] == previous['physical_t_s'], where)
        for n, sample in enumerate(samples):sample_audit(system, envelope, sample, tau, checks, {**where, 'sample': n}, 'execution', minimum['execution'])
        dense, increment = rk4_audit(system, step['physical_t0_s'], step['physical_t1_s'], samples, tau, h, 'execution', checks, where)
        checks.add('execution_cubic_extrema_reconstruction', native_equal(dense, step['dense_extension']), where)
        checks.add('execution_RK4_energy_increment', increment == step['modeled_electrical_energy_increment_J'], where,
                   abs(increment-step['modeled_electrical_energy_increment_J']))
        energy += increment
        previous = {**{k: samples[-1][k] for k in ['q', 'qd', 'z']}, 'physical_t_s': step['physical_t1_s']}
    final = cell['a2']['final_state'];last = updates[-1];stop = final['physical_t_s']
    checks.add('no_state_advance_after_rejected_QP', previous == final and last['physical_t_s'] == stop
               and np.array_equal(state_vector(last), state_vector(final))
               and stop == len(applied)*delta and cell['a2']['failure']['physical_t_s'] == stop
               and cell['a2']['failure']['reason'] == 'HARD_QP_FAILURE_NO_ADVANCE'
               and cell['a2']['failure']['no_additional_torque_applied'])
    checks.add('partial_scientific_failure_preserved', not cell['a2']['completed'] and not cell['a2']['passed']
               and not cell['a2']['metrics']['metrics_cover_completed_horizon'] and stop < reference.duration)
    metrics = cell['a2']['metrics']
    checks.add('prefix_metrics_arithmetic', energy == metrics['modeled_electrical_energy_J'] and stop == metrics['duration_s']
               and minimum_row == metrics['minimum_normalized_raw_slack']
               and maximum_correction == metrics['maximum_intervention_Nm'])
    target = system.geometry.evaluate(reference.target_q)['f']
    actual = system.geometry.evaluate(final['q'])['f']
    abort_distance = float(np.linalg.norm(actual-target))
    checks.add('abort_distance_field_arithmetic_NOT_terminal_accuracy', abort_distance == metrics['actual_terminal_error_m'])
    stats = statistics(vectors, delta)
    for name, values in stats['statistics'].items():
        recorded = cell['sampler_differences']['statistics'][name]
        checks.add('applied_prefix_all_three_difference_statistics', all(native_equal(values[k], recorded[k])
                   for k in ['max_2norm_Nm', 'RMS_2norm_Nm', 'component_max_abs_Nm', 'component_RMS_Nm']), name)
    original_negative = cell['negative_slacks']['negative_values']
    checks.add('reported_negative_candidates_preserved', len(negative_rows) == len(original_negative)
               and all(any(n['t_s'] == old['t_s'] and n['row'] == old['row'] and n['raw_value'] == old['value']
                           and n['torque_applied'] == old['torque_applied'] for n in negative_rows) for old in original_negative))
    return {'reference_id': cell['reference_id'], 'cell': cell['cell'], 'grid': grid,
            'prefix_data_audit_status': 'PASS' if checks.passed else 'FAIL', 'checks': checks.rows,
            'scientific_cell_outcome': 'FAIL_UNCHANGED', 'completed_horizon': False,
            'executed_prefix_s': stop, 'declared_horizon_s': reference.duration,
            'prehold_substeps_audited': len(hold), 'execution_substeps_audited': len(steps),
            'applied_QP_updates_audited': len(applied), 'rejected_updates': rejected,
            'retained_negative_candidate_rows': negative_rows, 'unavailable_solution_data': unavailable,
            'reported_KKT_scope': 'Reported stationarity/complementarity/duality metrics checked where available; dual vectors are not retained, so no independent stationarity reconstruction is claimed.',
            'sampler_applied_prefix': stats, 'prefix_energy_J': energy,
            'abort_distance_to_declared_final_target_m': abort_distance,
            'terminal_accuracy_at_T': 'NOT_EVALUATED_INCOMPLETE_HORIZON',
            'minimum_raw_slacks': minimum,
            'physical_slack_units': {'position_and_manip_h': 'first14 rad; last m^6', 'psi1': 'first14 rad/s; last m^6/s',
                                    'speed_upper': 'rad/s', 'speed_lower': 'rad/s', 'torque_upper': 'N m', 'torque_lower': 'N m',
                                    'observer': 'N m'},
            'direction_reversal_executed': bool(cell['reference_id'] == 'E3' and stop >= reference.boundaries[1]),
            'new_motion_performed': False, 'QP_resolves_performed': False,
            'true_ODE_continuous_certificate': False, 'independent_reviewer_signature': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cells', type=int, nargs='*')
    args = parser.parse_args();folder = args.run.resolve();out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = json.loads((folder/'run_started.json').read_text())
    plan = json.loads(PLAN.read_text());frozen = json.loads(FREEZE.read_text())
    if digest(PLAN) != start['plan_sha256'] or digest(FREEZE) != start['input_manifest_sha256']:
        raise ValueError('Recorded frozen plan or input manifest differs')
    core = ['src/panda_dynamics.py']+['src/panda_closed_loop/'+n+'.py' for n in
            ['config', 'assembly', 'controller', 'observer', 'barriers', 'preparation', 'p1_r3', 'p1_r4', 'a2_extended', 'trace_archive']]
    if any(digest(ROOT/n) != frozen['files'][n] for n in core):raise ValueError('Recorded physics/controller/auditor inputs differ')
    selected = args.cells if args.cells else [i for i in range(4) if not json.loads((folder/f'cell_{i}.json').read_text())['a2']['completed']]
    inputs = [PLAN, FREEZE, folder/'run_started.json']
    for i in selected:
        cell = json.loads((folder/f'cell_{i}.json').read_text())
        inputs += [folder/f'cell_{i}.json', folder/cell['prehold']['trace']['file'], folder/cell['a2']['trace']['file']]
    before = {str(p): digest(p) for p in inputs}
    policy = Policy.load();system = build_components(policy);system.geometry.function = system.geometry.function.expand()
    def forbidden(*a, **k):raise AssertionError('Read-only prefix audit must not solve a QP')
    system.qp.solve = forbidden
    results = []
    for i in selected:
        cell = json.loads((folder/f'cell_{i}.json').read_text())
        result = audit_one(system, cell, folder, plan)
        write(out/f'cell_{i}_prefix_audit.json', result);results.append(result)
        print(cell['reference_id'],i,result['prefix_data_audit_status'],f"scientific FAIL remains; prefix={result['executed_prefix_s']} s", flush=True)
    unchanged = all(digest(Path(n)) == h for n, h in before.items())
    summary = {'scope': 'READ_ONLY_EXECUTED_PREFIX_AUDIT_NOT_NEW_MOTION_OR_FULL_HORIZON_ACCEPTANCE',
               'run': str(folder.relative_to(ROOT)), 'created_utc': datetime.now(timezone.utc).isoformat(),
               'command': [sys.executable, *sys.argv], 'analysis_script_sha256': digest(Path(__file__)),
               'input_hashes': before, 'inputs_unchanged': unchanged,
               'all_prefix_data_audits_pass': unchanged and all(r['prefix_data_audit_status'] == 'PASS' for r in results),
               'scientific_cells_remain': 'FAIL / INCOMPLETE', 'results': results,
               'new_motion_performed': False, 'QP_resolves_performed': False, 'independent_signature': None}
    write(out/'summary.json', summary)
    return 0 if summary['all_prefix_data_audits_pass'] else 1


if __name__ == '__main__':raise SystemExit(main())
