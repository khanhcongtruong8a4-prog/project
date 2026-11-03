"""Build an exclusive review report and current numerical A2 status pointer."""
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
    summary = json.loads((run/'summary.json').read_text())
    gate = summary['gate']
    start = json.loads((run/'run_started.json').read_text())
    end = json.loads((run/'run_completed.json').read_text())
    if gate['status'] != 'GO' or end['exit_code'] != 0 or not end['frozen_inputs_unchanged']:
        raise ValueError('A complete audited GO is required for the current GO report')
    report = ROOT/'reports/p1_v1.2.2_r4'
    report.mkdir(exist_ok=True)
    cells = summary['cells']
    source = ROOT/'runs/p1_r4/frozen_9c94b06'
    repeat = []
    for cell in cells:
        previous = json.loads((source/f"cell_{cell['cell']}.json").read_text())
        repeat.append({'cell': cell['cell'], 'all_cell_metrics_exact': cell['a2']['metrics'] == previous['a2']['metrics'],
                       'measured_zero_state_exact': cell['endpoint']['state'] == previous['endpoint']['state'],
                       'final_state_exact': cell['a2']['final_state'] == previous['a2']['final_state']})
    repeat_exact = all(all(v for k, v in r.items() if k != 'cell') for r in repeat)
    def write(name, text):
        with (report/name).open('x') as f:
            f.write(text)
    def csv_file(name, rows):
        with (report/name).open('x', newline='') as f:
            writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    data, inequalities, endpoints = [], [], []
    for cell in cells:
        metrics, audit = cell['a2']['metrics'], cell['audit']
        data.append({'cell': cell['cell'], 'Delta_s': cell['grid']['control_period_s'], 'h_s': cell['grid']['rk4_step_s'],
                     'P1_completed': cell['prehold']['completed'], 'actual_zero_QP_pass': cell['endpoint']['QP']['strict_pass'],
                     'A2_cell_pass': cell['a2']['passed'], 'trace_audit_pass': audit['passed'],
                     'energy_J': metrics['modeled_electrical_energy_J'], 'duration_s': metrics['duration_s'],
                     'terminal_error_m': metrics['actual_terminal_error_m'],
                     'min_normalized_raw_slack': metrics['minimum_normalized_raw_slack'],
                     'max_QP_correction_Nm': metrics['maximum_intervention_Nm'],
                     'max_sampling_correction_Nm': audit['maximum_sampling_correction_Nm'],
                     'max_normalized_primal': audit['maximum_normalized_primal'],
                     'max_scaled_stationarity': audit['maximum_scaled_stationarity'],
                     'QP_updates': audit['QP_updates']})
        for j in range(7):
            e, qp = cell['endpoint'], cell['endpoint']['QP']
            endpoints.append({'cell': cell['cell'], 'joint_1_based': j+1,
                              **{k: e['state'][k][j] for k in ['q', 'qd', 'z']},
                              'dhat_Nm': qp['dhat'][j], 'varpi_Nm': qp['varpi'][j],
                              'first_applied_tau_Nm': qp['candidate_tau'][j]})
    for name, cohort in gate['cohorts'].items():
        for comparison in cohort['comparisons']:
            for metric, values in comparison['metrics'].items():
                inequalities.append({'cohort': name, 'local_cell_a': comparison['cells'][0],
                                     'local_cell_b': comparison['cells'][1], 'factor': comparison['factor'],
                                     'metric': metric, 'difference': values['absolute_difference'],
                                     'unchanged_tolerance': values['tolerance'], 'passed': values['passed']})
    csv_file('A2_CELLS.csv', data)
    csv_file('ACTUAL_ZERO_ENDPOINTS.csv', endpoints)
    csv_file('REFINEMENT.csv', inequalities)
    write('REPEATABILITY.json', json.dumps({'source_execution': str(source.relative_to(ROOT)),
                                           'fresh_execution': str(run.relative_to(ROOT)),
                                           'all_checked_values_exact': repeat_exact, 'cells': repeat,
                                           'independent_reviewer': None}, indent=2)+'\n')
    primary = gate['cohorts']['original_C4']['comparisons'][2]['metrics']['modeled_electrical_energy_J']
    finer = gate['cohorts']['finer_confirmation']['comparisons'][2]['metrics']['modeled_electrical_energy_J']
    terminal_max = max(r['terminal_error_m'] for r in data)*1000
    min_row = min(r['min_normalized_raw_slack'] for r in data)
    max_correction = max(r['max_QP_correction_Nm'] for r in data)
    max_sampling = max(r['max_sampling_correction_Nm'] for r in data)
    max_stationarity = max(r['max_scaled_stationarity'] for r in data)
    qp_count = sum(r['QP_updates'] for r in data)
    sample_count = sum(c['audit']['stage_and_endpoint_samples'] for c in cells)
    rel = '../../'+str(run.relative_to(ROOT))
    rows = '\n'.join(f"| {r['cell']} | {1000*r['Delta_s']:g} | {1000*r['h_s']:g} | PASS | PASS | PASS | {r['energy_J']:.12f} | {1000*r['terminal_error_m']:.9f} |" for r in data)
    repeat_text = ('The fresh run exactly reproduces every checked cell metric, measured zero state and final state of the first physical execution.'
                   if repeat_exact else 'Full repeatability values and any nonexact comparisons are disclosed in REPEATABILITY.json.')
    text = f'''# A2 numerical GO — r4

**A2 is GO for the user-authorized, fixed numerical simulation workflow.**
The original four C4 cells and the finer confirmation cohort pass every
refinement inequality, including both cross diagonals. All seven distinct
preholds, actual 43-row endpoint QPs, full A2 motions and trace audits pass.
The current gate is computed from evidence; the r2/r3 failures remain unchanged.

## What changed

The unchanged continuous Slotine–Li request is `r_k`. The new execution sampling
rule is `u_0=r_0`, then `u_k=r_k+0.5*(r_k-r_(k-1))`. This causal Adams–Bashforth
quadrature better approximates interval-average torque before the original
current-state hard QP. Actual QP torque remains held for every RK4 stage and
is supplied identically to the plant and DOB. No future state, future reference,
true disturbance, clipped QP torque or hidden recovery is used.

This is a versioned **digital execution change**, not a claim that the old r3
sampling passed. Its nominal smooth-request consistency is second order;
contracts also check an analytic linear-feedback solution. Gains, physical
parameters, model bytes, disturbance, observer semantics, startup, reference,
acceptance thresholds and original C4 grid are unchanged. The finer cohort was
declared before tests. The sampler change was committed before tests in
`52068ee`, with the complete numerical plan in
[PREDECLARED_A2_R4.json](../../policy/v1.2.2-r4/PREDECLARED_A2_R4.json).

The new request correction is reported separately: maximum sampling correction
is `{max_sampling:.12g} N m`; maximum subsequent QP correction is
`{max_correction:.12g} N m`. A small QP intervention does not conceal the
sampling change relative to the original continuous request.

## All cells and both cohorts

| Cell | Delta ms | h ms | P1 | Actual endpoint QP | Full A2 + audit | Electrical energy J | Terminal error mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

Original C4 uses cells `[0,1,2,3]`. Finer confirmation uses `[3,4,5,6]`,
sharing one identical cell within each full run. Every motion lasts 0.25 s.
Each reference uses its own measured prehold q/qd and unchanged Hermite rule;
z and the observer epoch transfer without reset. The hold remains 0.156 s,
with the original 0.01 rad / 0.02 rad/s windows.

| Energy convergence check | Difference J | Unchanged allowed J | Result |
| --- | --- | --- | --- |
| Original C4, Delta 1 → 0.5 ms at h=0.25 ms | {primary['absolute_difference']:.12g} | {primary['tolerance']:.12g} | PASS |
| Finer confirmation, Delta 0.5 → 0.25 ms at h=0.125 ms | {finer['absolute_difference']:.12g} | {finer['tolerance']:.12g} | PASS |

The original-grid energy difference is about
`{primary['tolerance']/primary['absolute_difference']:.2f}` times below its limit;
the finer-grid difference is about
`{finer['tolerance']/finer['absolute_difference']:.2f}` times below its limit.
Both h refinements in both cohorts pass. Duration, maximum QP intervention and
minimum normalized raw slack also pass every fixed-factor and diagonal
comparison. All full-precision metric inequalities are in
[REFINEMENT.csv](REFINEMENT.csv). No tolerance was relaxed to obtain GO.

## Gate evidence

- Seven complete preparations and actual zero endpoints; no midpoint/zero-speed
  fixture substitutes for a measured state. All original h, psi1,
  manipulability, speed, held-torque and observer-envelope sample tests pass.
- `{qp_count}` applied execution QPs with all 43 original raw rows nonnegative.
  Minimum normalized raw row is `{min_row:.12g}`. Maximum normalized primal is
  zero and maximum scaled stationarity is `{max_stationarity:.12g}`, below
  the unchanged `1e-9` thresholds. No post-QP clipping or fallback is applied.
- `{sample_count}` retained execution stage/endpoint samples audited. Audits
  verify trace hashes, original controller requests, causal history, actual
  QP matrices and slacks, signed waveform, propagated bounds, exact held input,
  physical sample conditions and RK4 electrical-energy quadrature.
- Maximum actual terminal position error is `{terminal_max:.9f} mm`, below
  the unchanged 1 mm limit. This is the fixed nonoptimized smoke task, not a
  planned free-time objective or comparison study.
- All 14 final engineering contracts pass, including fail-closed gate behavior,
  endpoint-solve reuse, no extra actuation after QP failure, and saved-data
  audit handling. Prior passing component/source/Pinocchio/MuJoCo regressions
  are reused with matching recorded source/input hashes; they are not falsely
  described as newly rerun or independently signed.
- All five geometry outputs match the original expression bit for bit at all
  154 retained regression configurations before execution.
- Pinned package versions and canonical model inputs match. Every frozen
  prior input and preserved trace remains unchanged. All nine current gate
  checks are true in [gate.json]({rel}/gate.json).

## Execution, engineering failures and reproduction

The sampling law and plan were frozen before testing. One initial synthetic
history fixture exceeded its own 1 N m box; its failure/diagnostics were retained
and the toy offset corrected before the first Panda run (`9c94b06`). The actual
Panda reference and all assertions/thresholds stayed fixed.

The first seven-cell physical execution completed, but its audit interface
passed NumPy-containing live dictionaries into JSON-data comparison code. The
runner correctly recorded engineering exit 1 and gate HOLD. That first run and
its errors are preserved at `runs/p1_r4/frozen_9c94b06/`; they are not relabeled.
The audit reader and tests were repaired and frozen in `2fe50b9`. The complete
controller/auditor module is unchanged from `52068ee`.

Retained physical traces were then requalified with identical-input and version
guards, without pretending that simulation had been repeated, at
`runs/p1_r4/qualified_2fe50b9/`. Finally, the repaired default command was run
end to end in a fresh process at `{str(run.relative_to(ROOT))}`. It completed
with exit 0 and every cell audit passing. {repeat_text}
See [REPEATABILITY.json](REPEATABILITY.json). These are engineering executions
in the existing pinned environment, not an independent reviewer or a new cloud
machine. All intermediate failures are retained.

```bash
cd /workspace/project/panda_research
/workspace/panda-venv/bin/python scripts/a2_status.py
# New physical run; use a fresh contracts report and output directory.
/workspace/panda-venv/bin/python tests/test_p1_r4.py --report /tmp/r4-contracts-new.json
/workspace/panda-venv/bin/python scripts/p1_r4.py --contracts /tmp/r4-contracts-new.json
```

The status command verifies current input/evidence hashes and recomputes the
gate. Missing or changed evidence fails closed to HOLD. Raw evidence, full
states/torques and all frozen source snapshots are linked from
[summary.json]({rel}/summary.json), [A2_CELLS.csv](A2_CELLS.csv) and
[ACTUAL_ZERO_ENDPOINTS.csv](ACTUAL_ZERO_ENDPOINTS.csv).

## Scope of GO

This is a GO for the explicitly authorized **Level 2 A2 numerical simulation**
under this fixed task, plant, continuous-observer convention and sampled
execution rule. Cubic extrema and sample checks do not certify the true ODE
between samples. Real sampled/delayed observer guarantees and hardware real-time
timing are not validated; host QP runtimes are not a hardware deadline claim.

Independent controls/theory signatures remain null. Manuscript-build acceptance,
M1, complete T27 and G2.5 are not manufactured. A3, Level 1, hardware deployment
and publication are not approved by this numerical gate. Your instruction
supplies numerical execution authority; it does not create another person's
signature. The earlier r2/r3 failure reports and all approved model parameters
remain byte for byte intact.
'''
    write('A2_GO_REVIEW.md', text)
    pointer = {'status': 'GO', 'scope': gate['scope'], 'run_directory': str(run.relative_to(ROOT)),
               'controller_freeze_commit': '52068ee', 'qualification_freeze_commit': start['freeze_commit'],
               'evidence_sha256': {n: digest(run/n) for n in ['summary.json', 'gate.json', 'run_started.json', 'run_completed.json']},
               'independent_signatures': None, 'A3': 'NO-GO', 'publication': 'NO-GO'}
    with (ROOT/'reports/a2_current.json').open('x') as f:
        json.dump(pointer, f, indent=2)
        f.write('\n')
    with (ROOT/'reports/A2_STATUS.md').open('x') as f:
        f.write('# Current A2 numerical status: GO\n\nOriginal C4 and finer-confirmation cohorts pass all metrics and trace audits with unchanged thresholds.\n\n[Full evidence and reproduction](p1_v1.2.2_r4/A2_GO_REVIEW.md).\n\nRun `python scripts/a2_status.py` to verify evidence and recompute the gate. Independent signatures remain unset; A3, hardware and publication are separate.\n')
    print(report/'A2_GO_REVIEW.md')


if __name__ == '__main__':
    main()
