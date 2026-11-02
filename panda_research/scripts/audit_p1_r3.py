"""Read-only audit of retained r3 evidence, separate from scientific acceptance.

Audit PASS means the evidence and reported calculations agree. A2 refinement
may still FAIL. This is engineering verification, never an independent signature.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import gzip
import hashlib
import json
import numpy as np
from panda_dynamics import disturbance_bounds
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.observer import ObserverEnvelope
from panda_closed_loop.p1_r3 import modeled_power


def audit(run):
    checks = []
    def check(name, passed, **details):
        checks.append({'check': name, 'passed': bool(passed), **details})
    plan = json.loads((ROOT/'policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json').read_text())
    frozen = json.loads((ROOT/'policy/v1.2.2-r3/FROZEN_INPUTS.json').read_text())
    policy = Policy.load()
    start = json.loads((run/'run_started.json').read_text())
    end = json.loads((run/'run_completed.json').read_text())
    summary = json.loads((run/'summary.json').read_text())
    backend = json.loads((run/'backend_validation.json').read_text())
    changed = [p for p, sha in frozen['files'].items() if digest(ROOT/p) != sha]
    check('original_and_frozen_input_bytes', not changed and end['frozen_inputs_unchanged'],
          checked_count=len(frozen['files']), changed=changed)
    check('geometry_backend_bitwise_regression', backend['passed'] and len(backend['poses']) == 154
          and all(p['bitwise_equal_all_five_outputs'] and max(p['max_absolute_errors']) == 0 for p in backend['poses']))
    check('plan_and_freeze_hashes', start['plan_sha256'] == digest(ROOT/'policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json')
          and start['freeze_sha256'] == digest(ROOT/'policy/v1.2.2-r3/FROZEN_INPUTS.json'))
    check('no_independent_signature_inferred', summary['independent_signatures'] is None and start['human_signatures'] is None)
    cells = [json.loads((run/f'cell_{i}.json').read_text()) for i in range(4)]
    check('exact_all_four_C4_cells', [c['grid'] for c in cells] == plan['C4_grid'])
    magnitude, rate = disturbance_bounds(policy.raw['disturbance']['amplitude_fraction'])
    envelope = ObserverEnvelope(policy.ko, magnitude, rate)
    targets, endpoint_metrics, cell_metrics = [], [], []
    def read_trace(record):
        path = run/record['file']
        blob = gzip.decompress(path.read_bytes())
        check('trace_hash_'+path.name, digest(path) == record['sha256']
              and hashlib.sha256(blob).hexdigest() == record['uncompressed_json_sha256'])
        return json.loads(blob)

    for i, cell in enumerate(cells):
        prep = cell['prehold']
        trace = read_trace(prep['trace'])
        complete = prep['completed']
        check(f'cell_{i}_P1_completion_reporting', complete == (prep['decision'] == 'PASS_NUMERICAL_HOLD_ONLY'))
        if not complete:
            check(f'cell_{i}_no_motion_after_failed_P1', not cell['a2']['completed'] and not cell['a2']['passed'])
            continue
        endpoint = cell['endpoint']
        qs = endpoint['state']
        check(f'cell_{i}_actual_zero_state_transfer', qs['physical_t_s'] == 0.
              and trace[-1]['state_after'] == qs and prep['state'] == qs
              and endpoint['q_qd_z_transfer_exact'] and not endpoint['observer_reset'])
        check(f'cell_{i}_prehold_tolerances', np.all(np.array(prep['q_deviation_peak_rad']) <= plan['q_radius_rad'])
              and np.all(np.array(prep['qd_peak_rad_s']) <= plan['qd_radius_rad_s'])
              and all(all(t['checks'].values()) for t in trace))
        qp = endpoint['QP']
        tau = np.array(qp['candidate_tau']) if qp['candidate_tau'] is not None else None
        raw = np.array(qp['G'])@tau+qp['c'] if tau is not None else None
        expected_varpi = envelope.value(plan['T_pre_s'])
        check(f'cell_{i}_propagated_zero_envelope', np.array_equal(qp['varpi'], expected_varpi)
              and np.array_equal(prep['propagated_varpi'], expected_varpi)
              and prep['observer_elapsed_s'] == plan['T_pre_s'])
        strict = (raw is not None and len(raw) == 43 and np.all(raw >= 0)
                  and qp['diagnostics'].get('normalized_primal', np.inf) <= 1e-9
                  and qp['diagnostics'].get('scaled_stationarity', np.inf) <= 1e-9)
        check(f'cell_{i}_actual_endpoint_43_row_QP', strict == qp['strict_pass'],
              strict_numerical_pass=bool(strict), status=qp['status'],
              minimum_raw_slack=float(min(raw)) if raw is not None else None)
        endpoint_metrics.append({'cell': i, 'q': qs['q'], 'qd': qs['qd'], 'z': qs['z'],
                                 'dhat': qp['dhat'], 'varpi': qp['varpi'], 'tau_candidate': qp['candidate_tau'],
                                 'min_normalized_raw_slack': float(np.min(raw/qp['row_scales'])) if raw is not None else None,
                                 'normalized_primal': qp['diagnostics'].get('normalized_primal'),
                                 'scaled_stationarity': qp['diagnostics'].get('scaled_stationarity')})
        execution = cell['a2']
        motion = read_trace(execution['trace'])
        updates, steps = motion['updates'], motion['substeps']
        if not execution['completed']:
            check(f'cell_{i}_incomplete_A2_cannot_pass', not execution['passed'])
            continue
        first = updates[0]
        check(f'cell_{i}_first_applied_QP_is_endpoint_solve', first['physical_t_s'] == 0.
              and all(first[k] == qp[k] for k in ['q', 'qd', 'z', 'dhat', 'varpi', 'candidate_tau', 'G', 'c'])
              and first['torque_applied'])
        check(f'cell_{i}_complete_horizon_counts', len(steps) == round(.25/cell['grid']['rk4_step_s'])
              and len(updates) == round(.25/cell['grid']['control_period_s'])
              and steps[-1]['physical_t1_s'] == .25 and execution['final_state']['physical_t_s'] == .25)
        rows_ok, held_ok, physical_ok, observer_ok, quadrature_ok = True, True, True, True, True
        min_raw, correction, energy = np.inf, 0., 0.
        min_observer = np.full(7, np.inf)
        runtime, gap, comp = [], [], []
        for update in updates:
            tau = np.array(update['candidate_tau'])
            raw = np.array(update['G'])@tau+update['c']
            scale = np.array(update['row_scales'])
            rows_ok &= (len(raw) == 43 and np.all(raw >= 0) and update['strict_pass']
                        and update['diagnostics']['normalized_primal'] <= 1e-9
                        and update['diagnostics']['scaled_stationarity'] <= 1e-9
                        and np.array_equal(raw, update['raw_slacks']))
            min_raw = min(min_raw, float(np.min(raw/scale)))
            correction = max(correction, float(np.linalg.norm(tau-update['u_nom'])))
            runtime.append(update['solve_runtime_s'])
            gap.append(abs(update['diagnostics']['duality_gap']))
            comp.append(update['diagnostics']['complementarity'])
        for step in steps:
            tau = np.array(step['applied_tau'])
            u = updates[step['control_period_index']]['candidate_tau']
            held_ok &= np.array_equal(tau, u) and len(step['samples']) == 5
            samples = step['samples']
            for sample in samples:
                held_ok &= np.array_equal(sample['tau_applied'], tau)
                physical_ok &= all(np.all(np.asarray(v) >= 0) for k, v in sample['physical_slacks'].items() if k != 'passed')
                vp = envelope.value(sample['physical_t_s']+plan['T_pre_s'])
                slack = vp-abs(np.array(sample['truth_post_control_only'])-sample['dhat'])
                observer_ok &= np.array_equal(vp, sample['varpi']) and np.all(slack >= 0)
                min_observer = np.minimum(min_observer, slack)
            h = cell['grid']['rk4_step_s']
            power = [modeled_power(tau, s['qd'], policy.raw['energy']) for s in samples[:4]]
            delta = h*(power[0]+2*power[1]+2*power[2]+power[3])/6
            quadrature_ok &= abs(delta-step['modeled_electrical_energy_increment_J']) <= 1e-16
            energy += delta
        check(f'cell_{i}_every_QP_original_raw_rows_and_reported_residuals', rows_ok)
        check(f'cell_{i}_ZOH_identical_applied_torque_all_stages', held_ok)
        check(f'cell_{i}_raw_physical_and_observer_sample_slacks', physical_ok and observer_ok)
        metrics = execution['metrics']
        check(f'cell_{i}_metrics_recomputed_from_trace', quadrature_ok
              and abs(energy-metrics['modeled_electrical_energy_J']) <= 1e-13
              and min_raw == metrics['minimum_normalized_raw_slack']
              and correction == metrics['maximum_intervention_Nm']
              and np.array_equal(min_observer, metrics['minimum_observer_envelope_slack_Nm']))
        check(f'cell_{i}_terminal_acceptance_reporting', execution['passed'] ==
              (metrics['planned_terminal_error_m'] <= 1e-6 and metrics['actual_terminal_error_m'] <= .001))
        targets.append((i, np.array(metrics['target_flange_m'])))
        cell_metrics.append({'cell': i, 'QP_count': len(updates), 'stage_and_endpoint_count': 5*len(steps),
                             'maximum_absolute_duality_gap': max(gap), 'maximum_complementarity': max(comp),
                             'QP_runtime_s_min_median_max': [min(runtime), float(np.median(runtime)), max(runtime)]})
    # Independently reapply the frozen refinement inequalities from stored metrics.
    thresholds = plan['fixed_acceptance_thresholds']
    keys = {'modeled_electrical_energy_J': 'energy_abs_J', 'duration_s': 'duration_abs_s',
            'maximum_intervention_Nm': 'intervention_difference_abs_Nm',
            'minimum_normalized_raw_slack': 'normalized_slack_difference_abs'}
    refinement_matches = True
    for comparison in summary['refinement']['comparisons']:
        i, j = comparison['cells']
        if comparison['status'].startswith('NOT_COMPARABLE'):
            refinement_matches &= not (cells[i]['a2']['completed'] and cells[j]['a2']['completed'])
            continue
        passed = True
        for name, absolute in keys.items():
            a, b = [cells[k]['a2']['metrics'][name] for k in [i, j]]
            tolerance = max(thresholds[absolute], thresholds['relative_refinement']*max(abs(a), abs(b)))
            metric = comparison['metrics'][name]
            ok = abs(a-b) <= tolerance
            refinement_matches &= (ok == metric['passed'] and tolerance == metric['tolerance']
                                   and abs(a-b) == metric['absolute_difference'])
            passed &= ok
        refinement_matches &= (comparison['status'] == ('PASS' if passed else 'FAIL'))
    check('frozen_refinement_thresholds_and_all_edges', refinement_matches
          and len([c for c in summary['refinement']['comparisons'] if c['required']]) == 4)
    numerical_pass = (all(c['prehold']['completed'] and c['endpoint']['valid_zero_endpoint'] and c['a2']['passed'] for c in cells)
                      and all(c['status'] == 'PASS' for c in summary['refinement']['comparisons'] if c['required']))
    check('aggregate_does_not_hide_refinement_failure', summary['A2_numerical'] == ('PASS' if numerical_pass else 'FAIL'))
    # T29 reserve/row-scale arithmetic only, without adding planner reserves to QP rows.
    scales = np.array(cells[0]['endpoint']['QP']['row_scales']) if cells[0]['endpoint'] else None
    reserve_ratio = None
    if scales is not None:
        p = policy.raw['physical_parameters']
        reserves = np.r_[p['eta_delta']*scales[:15]/p['normalization_time_s']**2,
                         np.full(14, p['barrier_reserves']['velocity_CBF_delta_vB_rad_s2']),
                         np.full(14, p['torque_reserve_Nm'])]
        reserve_ratio = float(np.min(reserves/scales))
        check('T29_supplied_reserve_to_row_scale_arithmetic', reserve_ratio > thresholds['minimum_reserve_to_row_scale_strictly_greater_than'])
    target_differences = [{'cells': [i, j], 'norm_m': float(np.linalg.norm(a-b))}
                          for n, (i, a) in enumerate(targets) for j, b in targets[n+1:]]
    return {'scope': 'READ_ONLY_ENGINEERING_EVIDENCE_AUDIT_NOT_INDEPENDENT_SIGNOFF',
            'run_directory': str(run.relative_to(ROOT)), 'freeze_commit': start['freeze_commit'],
            'backend_amendment_commit': backend['amendment_commit'],
            'overall_audit_pass': all(c['passed'] for c in checks), 'checks': checks,
            'A2_numerical': summary['A2_numerical'], 'endpoint_diagnostics': endpoint_metrics,
            'cell_trace_diagnostics': cell_metrics, 'target_differences_m': target_differences,
            'minimum_T29_reserve_to_scale': reserve_ratio, 'independent_signature': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run.resolve())
    with args.report.open('x') as f:
        json.dump(json_values(result), f, indent=2, allow_nan=False)
        f.write('\n')
    print('Engineering evidence audit:', 'PASS' if result['overall_audit_pass'] else 'FAIL')
    print('A2 numerical result:', result['A2_numerical'])
    raise SystemExit(0 if result['overall_audit_pass'] else 1)
