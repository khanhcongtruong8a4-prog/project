"""Write a new, exclusive r3 review report from retained evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import csv
import json
import numpy as np
from panda_closed_loop.config import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    report = ROOT/'reports/p1_v1.2.2_r3'
    summary = json.loads((run/'summary.json').read_text())
    audit = json.loads((report/'engineering/evidence_audit.json').read_text())
    if not audit['overall_audit_pass']:
        raise ValueError('Resolve evidence audit failures before generating a report')
    cells = summary['cells']
    def write(name, text):
        with (report/name).open('x') as f:
            f.write(text)
    def table_file(name, rows):
        with (report/name).open('x', newline='') as f:
            writer = csv.DictWriter(f, list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    cell_rows, endpoint_rows, refinement_rows = [], [], []
    for c in cells:
        m, prep, end = c['a2']['metrics'], c['prehold'], c['endpoint']
        qp = end['QP']
        cell_rows.append({'cell': c['cell'], 'Delta_s': c['grid']['control_period_s'], 'h_s': c['grid']['rk4_step_s'],
                          'P1_completed': prep['completed'], 'endpoint_QP_status': qp['status'],
                          'endpoint_QP_strict_pass': qp['strict_pass'], 'A2_completed': c['a2']['completed'],
                          'A2_individual_cell_pass': c['a2']['passed'],
                          'max_hold_q_deviation_rad': max(prep['q_deviation_peak_rad']),
                          'max_hold_abs_qd_rad_s': max(prep['qd_peak_rad_s']),
                          'modeled_electrical_energy_J': m['modeled_electrical_energy_J'],
                          'duration_s': m['duration_s'], 'actual_terminal_position_error_m': m['actual_terminal_error_m'],
                          'maximum_intervention_Nm': m['maximum_intervention_Nm'],
                          'minimum_normalized_raw_slack': m['minimum_normalized_raw_slack'],
                          'max_normalized_primal': m['max_normalized_primal'],
                          'max_scaled_stationarity': m['max_scaled_stationarity'],
                          'minimum_observer_sample_slack_Nm': min(m['minimum_observer_envelope_slack_Nm'])})
        for j in range(7):
            endpoint_rows.append({'cell': c['cell'], 'joint_1_based': j+1,
                                  **{k: end['state'][k][j] for k in ['q', 'qd', 'z']},
                                  'dhat_Nm': qp['dhat'][j], 'varpi_Nm': qp['varpi'][j],
                                  'QP_candidate_tau_Nm': qp['candidate_tau'][j],
                                  'previous_applied_tau_Nm': end['previous_applied_torque'][j]})
    for comp in summary['refinement']['comparisons']:
        for name, m in comp['metrics'].items():
            refinement_rows.append({'cell_a': comp['cells'][0], 'cell_b': comp['cells'][1],
                                    'factor': comp['factor'], 'required': comp['required'], 'metric': name,
                                    'value_a': m['values'][0], 'value_b': m['values'][1],
                                    'absolute_difference': m['absolute_difference'], 'frozen_tolerance': m['tolerance'],
                                    'passed': m['passed']})
    table_file('A2_CELLS.csv', cell_rows)
    table_file('ACTUAL_ZERO_ENDPOINTS.csv', endpoint_rows)
    table_file('REFINEMENT.csv', refinement_rows)
    rel = '../../'+str(run.relative_to(ROOT))
    lines = []
    for c in cells:
        m = c['a2']['metrics']
        lines.append(f"| {c['cell']} | {1000*c['grid']['control_period_s']:g} | {1000*c['grid']['rk4_step_s']:g} | PASS | PASS | PASS | {m['modeled_electrical_energy_J']:.12f} | {1000*m['actual_terminal_error_m']:.9f} | {m['minimum_normalized_raw_slack']:.12f} |")
    refinements = []
    for comp in summary['refinement']['comparisons']:
        m = comp['metrics']['modeled_electrical_energy_J']
        label = comp['factor'] if comp['required'] else 'diagonal (disclosed)'
        refinements.append(f"| {comp['cells'][0]}–{comp['cells'][1]} | {label} | {m['absolute_difference']:.12g} | {m['tolerance']:.12g} | {comp['status']} |")
    max_speed = max(max(c['prehold']['qd_peak_rad_s']) for c in cells)
    max_q = max(max(c['prehold']['q_deviation_peak_rad']) for c in cells)
    max_endpoint_speed = max(float(np.max(abs(np.array(c['endpoint']['state']['qd'])))) for c in cells)
    max_stationarity = max(c['a2']['metrics']['max_scaled_stationarity'] for c in cells)
    max_correction = max(c['a2']['metrics']['maximum_intervention_Nm'] for c in cells)
    target_difference = max(d['norm_m'] for d in audit['target_differences_m'])
    text = f'''# P1-r3 / A2 numerical review

**P1 numerical hold: PASS in all four cells. Actual zero-endpoint QPs: PASS.
All four A2 cells finish and pass their individual checks. Aggregate A2:
FAIL, because both required control-period energy refinements exceed the
unchanged frozen threshold. A3, Level 1 and publication remain NO-GO.**

This is user-authorized simulation evidence. It does not supply an independent
reviewer signature, a true-ODE safety certificate, manuscript build confirmation
or a hardware execution result.

## Frozen design and authority

Work starts at `9eb1cba3d7dd850eacf2787c616f3d3e85273fcc` on `p1-v1.2.2`.
The explicit user instruction authorizing simulation development, versioned
policy changes and P1/A2 numerical testing is retained in the
[predeclared plan](../../policy/v1.2.2-r3/PREDECLARED_P1_R3_A2.json).
That authority was used to run these tests; independent signatures remain null.

Controller, policy amendment, harness, tests and input hashes were committed
before testing in `{summary['freeze_commit']}`. r2 did not contain numerical
computed-torque gains, so the new startup-only gains were explicitly selected
as an engineering design and frozen before any r3 trial: `Kp=562500 s^-2`,
`Kd=1218.75 s^-1` on every joint. The static-midpoint command is
`M(q)[Kp(qmid-q)-Kd*qd]+C(q,qd)*qd+g(q)+F(qd)-dhat`, torque-box projected at
the update and held for the complete control period. The nominal frozen
double-integrator poles are 0.25 at 1 ms; that design rationale is not a
nonlinear stability certificate.

The 0.156 s hold, 0.01 rad / 0.02 rad/s hold windows, model evaluator, approved
model parameters, disturbance, observer/barrier/tracking gains, limits,
reserves, QP settings, C4 grid and numerical thresholds were preserved.
The original Slotine–Li controller performs execution after the hold. The
observer is integrated continuously with q/qd by RK4 using actual held torque.
No truth input, observer reset, waveform reset, ideal clamp, softened row,
post-QP clipping, recovery or pass-conditioned retuning is used.

The original interpreted geometry run was interrupted for execution cost before
any completed cell; its partial evidence and signal-related engineering error
are retained in [the interrupted run](../../runs/p1_r3/frozen_51831ee/INTERRUPTION.json).
The same expression's scalar SX backend was separately frozen in
`{audit['backend_amendment_commit']}`. All five geometry outputs were
bitwise identical at all 154 retained poses before the completed run began.
See the [backend amendment](../../policy/v1.2.2-r3/BACKEND_AMENDMENT.md) and
[full comparison record]({rel}/backend_validation.json). The controller and
original test plan were unchanged.

## Applied-torque hold and actual endpoint

All four cells integrate from physical time -0.156 s to 0 without early abort.
Across them, maximum midpoint displacement is `{max_q:.12g} rad` and maximum
absolute speed is `{max_speed:.12g} rad/s`, within the original windows.
These checks include every RK4 stage/endpoint and component extrema of each
numerical cubic extension; they do not enclose true-ODE integration error.

The reference starts from each measured q/qd; z transfers byte-for-byte.
Maximum actual endpoint speed is `{max_endpoint_speed:.12g} rad/s`, rather
than an invented zero-velocity fixture. The observer retains its -0.156 s
epoch. At physical zero its propagated varpi is
`[0.193255129936747]*4 + [0.0266558799912754]*3 N m`.
All physical joint/manipulability h, psi1, speed and previous applied-torque
slacks pass. Each actual full 43-row QP is solved with the execution law and
the measured-state reference at zero; the same solve supplies the first
execution torque. Its minimum normalized raw slack is about 0.13161, with
zero normalized primal residual and scaled stationarity below `5.77e-12`.

[ACTUAL_ZERO_ENDPOINTS.csv](ACTUAL_ZERO_ENDPOINTS.csv) retains every q, qd, z,
dhat, propagated bound and candidate/applied torque. The original G/c rows,
scales, units, solver diagnostics and physical slacks are in each immutable
[cell record]({rel}/cell_0.json); equivalent records exist for cells 1–3.

## All four A2 cells

Each run uses the same predeclared 0.25 s quintic Hermite rule and offset
`[0.01,0,-0.01,0,0.01,0,0] rad`, instantiated from its own measured endpoint.
The target is each endpoint-relative flange target, with free orientation.
Coefficients and targets are logged. Largest cross-cell target separation is
`{target_difference:.12g} m`, disclosed before interpreting the comparison.
This is a non-optimized smoke reference, not Stage-1 planning or a free-time
optimization result.

| Cell | Delta ms | h ms | P1 | Actual endpoint QP | Individual A2 | Electrical energy J | Terminal error mm | Min normalized raw row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(lines)}

All cells finish at 0.25 s. Planned terminal errors are below `1.14e-17 m`;
actual terminal errors satisfy the fixed 1 mm criterion. All 1,500 applied
execution QPs retain nonnegative raw rows. Maximum reported normalized primal
is zero and maximum scaled stationarity is `{max_stationarity:.12g}` against
the unchanged `1e-9` limits. Maximum torque intervention is
`{max_correction:.12g} N m`; it meets the numerical zero-intervention
diagnostic only, not a certified solver-error bound. All retained physical
and analytic observer-envelope sample checks pass with no enlarged envelope.

Energy is the modeled, shared-bus non-regenerative electrical energy, with
smoothing after the joint sum and RK4 stage quadrature. It excludes preparation
and the separate w_t*T term. Full precision values are in
[A2_CELLS.csv](A2_CELLS.csv). Cold ProxQP statuses, iterations, residuals,
complementarity, duality gap, correction and wall-clock runtime are retained in
the compressed full traces.

## Required refinement result: FAIL

Every fixed-factor edge uses `max(absolute_tolerance,
1e-4*max(abs(metric_values)))`. All thresholds were frozen before tests.
The energy comparisons are:

| Cells | Refined factor | Energy difference J | Allowed J | Result |
| --- | --- | --- | --- | --- |
{chr(10).join(refinements)}

Duration, maximum intervention and minimum normalized raw slack pass every
required edge. Energy passes both h refinements and fails both Delta
refinements by approximately 4.35 times the tolerance. Thus the aggregate
numerical A2 result is FAIL even though all four individual runs pass.
Exit code 3 records this scientific rejection. No tolerance was enlarged,
candidate was retuned or extra refinement round was silently substituted.
See [all metric inequalities](REFINEMENT.csv) and the
[machine-readable summary]({rel}/summary.json).

## Engineering verification and preservation

- 12 new r3 contracts PASS: controller signs/inverse dynamics, nominal sampled
  poles, measured Hermite endpoints, exact transfer, strict negative-raw
  rejection, held torque, stop behavior, observer violation and refinement.
- 13 earlier signed-clock/preparation contracts and 15 earlier static-screen
  contracts PASS.
- Existing Action 3 validation PASS: 19 component tests, T28 raw-C checks and
  the preserved source/internal/Pinocchio/MuJoCo regressions. This was run with
  the existing pinned venv on a disposable source copy, not an independent
  review or a new cloud-machine reproduction. Its historical A2-refusal test
  remains expected; this r3 run has its separate explicit numerical authority.
- [Read-only evidence audit](engineering/evidence_audit.json) PASS: original
  frozen bytes, trace hashes, state transfer, raw QP-row arithmetic, propagated
  bounds, held inputs, stage energy quadrature and all refinement inequalities.
  All `{len(json.loads((ROOT/'policy/v1.2.2-r3/FROZEN_INPUTS.json').read_text())['files'])}`
  frozen files, including every original tracked research file, are unchanged.
- A mistakenly located initial regression wrote two generated report pointers.
  Its new outputs were retained, the original bytes restored, and a full rerun
  completed in the disposable copy. The [engineering note](engineering/mislocated_regression/NOTE.md)
  distinguishes that mistake from a candidate failure. All previous r2 failures,
  manuscript/workbook bytes, approved model parameters and human fields remain
  untouched.

## Scope and remaining work

P1 is now a passing **numerical** hold under the frozen controller, not a
verified continuous startup neighborhood or a hardware guarantee. Coupled
continuous observer evidence does not validate a real sampled/delayed observer
or the separately proposed Euler observer sensitivity. QP runtimes on this
host have medians about 1.4–1.5 ms, exceeding the simulated 0.5/1 ms periods;
no real-time execution claim is made.

Control-period energy convergence is the remaining numerical A2 failure.
A further study needs a newly predeclared refinement grid and must preserve
this failed result. Independent controls/theory signatures and build-revision
confirmation remain unset. The existing main.tex/Project.rar hash discrepancies
remain disclosed by the source audit; canonical equation files match. M1,
complete T27 and G2.5 remain open for later planning/comparison gates. A3,
Level 1 and publication remain NO-GO; no independent signature is generated.

## Reproduce

```bash
cd /workspace/project/panda_research
/workspace/panda-venv/bin/python tests/test_p1_r3.py --report /tmp/r3-contracts-new.json
/workspace/panda-venv/bin/python scripts/p1_r3_expanded.py
# The retained scientific result is exit 3, not an engineering crash.
/workspace/panda-venv/bin/python scripts/audit_p1_r3.py runs/p1_r3/expanded_a7891c3 --report /tmp/r3-audit-new.json
```

Use fresh output names; evidence files are created exclusively. The committed
freeze must be intact. No network, GUI, ROS, GPU or secret is required for these
numerical commands. The saved onboarding startup remains the older baseline;
the explicit commands above select this versioned P1/A2 workflow.
'''
    write('REVIEW_REMEDIATION.md', text)
    pointer = {'run_directory': str(run.relative_to(ROOT)), 'summary_sha256': digest(run/'summary.json'),
               'freeze_commit': summary['freeze_commit'], 'backend_amendment_commit': audit['backend_amendment_commit'],
               'P1_numerical_hold': summary['P1_numerical_hold'], 'A2_numerical': summary['A2_numerical'],
               'evidence_audit': 'PASS', 'independent_signature': None, 'A3': 'NO-GO'}
    with (ROOT/'reports/p1_r3_latest.json').open('x') as f:
        json.dump(pointer, f, indent=2)
        f.write('\n')
    print(report/'REVIEW_REMEDIATION.md')


if __name__ == '__main__':
    main()
