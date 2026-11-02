# A2 numerical GO — r4

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
is `0.00281078060735 N m`; maximum subsequent QP correction is
`3.80438081038e-09 N m`. A small QP intervention does not conceal the
sampling change relative to the original continuous request.

## All cells and both cohorts

| Cell | Delta ms | h ms | P1 | Actual endpoint QP | Full A2 + audit | Electrical energy J | Terminal error mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 0.25 | PASS | PASS | PASS | 0.270793012980 | 0.411170736 |
| 1 | 1 | 0.125 | PASS | PASS | PASS | 0.270793013122 | 0.411170737 |
| 2 | 0.5 | 0.25 | PASS | PASS | PASS | 0.270794866098 | 0.411150210 |
| 3 | 0.5 | 0.125 | PASS | PASS | PASS | 0.270794866240 | 0.411150211 |
| 4 | 0.5 | 0.0625 | PASS | PASS | PASS | 0.270794866248 | 0.411150211 |
| 5 | 0.25 | 0.125 | PASS | PASS | PASS | 0.270795326139 | 0.411145031 |
| 6 | 0.25 | 0.0625 | PASS | PASS | PASS | 0.270795326147 | 0.411145031 |

Original C4 uses cells `[0,1,2,3]`. Finer confirmation uses `[3,4,5,6]`,
sharing one identical cell within each full run. Every motion lasts 0.25 s.
Each reference uses its own measured prehold q/qd and unchanged Hermite rule;
z and the observer epoch transfer without reset. The hold remains 0.156 s,
with the original 0.01 rad / 0.02 rad/s windows.

| Energy convergence check | Difference J | Unchanged allowed J | Result |
| --- | --- | --- | --- |
| Original C4, Delta 1 → 0.5 ms at h=0.25 ms | 1.85311726258e-06 | 2.70794866098e-05 | PASS |
| Finer confirmation, Delta 0.5 → 0.25 ms at h=0.125 ms | 4.59899068606e-07 | 2.70795326139e-05 | PASS |

The original-grid energy difference is about
`14.61` times below its limit;
the finer-grid difference is about
`58.88` times below its limit.
Both h refinements in both cohorts pass. Duration, maximum QP intervention and
minimum normalized raw slack also pass every fixed-factor and diagonal
comparison. All full-precision metric inequalities are in
[REFINEMENT.csv](REFINEMENT.csv). No tolerance was relaxed to obtain GO.

## Gate evidence

- Seven complete preparations and actual zero endpoints; no midpoint/zero-speed
  fixture substitutes for a measured state. All original h, psi1,
  manipulability, speed, held-torque and observer-envelope sample tests pass.
- `4000` applied execution QPs with all 43 original raw rows nonnegative.
  Minimum normalized raw row is `0.131613420082`. Maximum normalized primal is
  zero and maximum scaled stationarity is `6.0315194679e-12`, below
  the unchanged `1e-9` thresholds. No post-QP clipping or fallback is applied.
- `80000` retained execution stage/endpoint samples audited. Audits
  verify trace hashes, original controller requests, causal history, actual
  QP matrices and slacks, signed waveform, propagated bounds, exact held input,
  physical sample conditions and RK4 electrical-energy quadrature.
- Maximum actual terminal position error is `0.411170737 mm`, below
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
  checks are true in [gate.json](../../runs/p1_r4/fresh_2fe50b9/gate.json).

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
end to end in a fresh process at `runs/p1_r4/fresh_2fe50b9`. It completed
with exit 0 and every cell audit passing. The fresh run exactly reproduces every checked cell metric, measured zero state and final state of the first physical execution.
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
[summary.json](../../runs/p1_r4/fresh_2fe50b9/summary.json), [A2_CELLS.csv](A2_CELLS.csv) and
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
