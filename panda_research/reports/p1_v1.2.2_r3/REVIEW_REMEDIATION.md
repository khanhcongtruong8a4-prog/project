# P1-r3 / A2 numerical review

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
before testing in `51831ee5ace0af4f9f04114b5b8a5d56820cc531`. r2 did not contain numerical
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
`a7891c38da0769d278137a1dca207a3c10b15a19`. All five geometry outputs were
bitwise identical at all 154 retained poses before the completed run began.
See the [backend amendment](../../policy/v1.2.2-r3/BACKEND_AMENDMENT.md) and
[full comparison record](../../runs/p1_r3/expanded_a7891c3/backend_validation.json). The controller and
original test plan were unchanged.

## Applied-torque hold and actual endpoint

All four cells integrate from physical time -0.156 s to 0 without early abort.
Across them, maximum midpoint displacement is `3.14268156556e-05 rad` and maximum
absolute speed is `0.0165027832173 rad/s`, within the original windows.
These checks include every RK4 stage/endpoint and component extrema of each
numerical cubic extension; they do not enclose true-ODE integration error.

The reference starts from each measured q/qd; z transfers byte-for-byte.
Maximum actual endpoint speed is `3.70480095463e-05 rad/s`, rather
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
[cell record](../../runs/p1_r3/expanded_a7891c3/cell_0.json); equivalent records exist for cells 1–3.

## All four A2 cells

Each run uses the same predeclared 0.25 s quintic Hermite rule and offset
`[0.01,0,-0.01,0,0.01,0,0] rad`, instantiated from its own measured endpoint.
The target is each endpoint-relative flange target, with free orientation.
Coefficients and targets are logged. Largest cross-cell target separation is
`3.08851358505e-10 m`, disclosed before interpreting the comparison.
This is a non-optimized smoke reference, not Stage-1 planning or a free-time
optimization result.

| Cell | Delta ms | h ms | P1 | Actual endpoint QP | Individual A2 | Electrical energy J | Terminal error mm | Min normalized raw row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 0.25 | PASS | PASS | PASS | 0.270564575695 | 0.410242047 | 0.131613420082 |
| 1 | 1 | 0.125 | PASS | PASS | PASS | 0.270564575839 | 0.410242048 | 0.131613420097 |
| 2 | 0.5 | 0.25 | PASS | PASS | PASS | 0.270682245738 | 0.410685235 | 0.131623645539 |
| 3 | 0.5 | 0.125 | PASS | PASS | PASS | 0.270682245881 | 0.410685236 | 0.131623645555 |

All cells finish at 0.25 s. Planned terminal errors are below `1.14e-17 m`;
actual terminal errors satisfy the fixed 1 mm criterion. All 1,500 applied
execution QPs retain nonnegative raw rows. Maximum reported normalized primal
is zero and maximum scaled stationarity is `6.01679773712e-12` against
the unchanged `1e-9` limits. Maximum torque intervention is
`3.79509512706e-09 N m`; it meets the numerical zero-intervention
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
| 0–1 | h | 1.4466017273e-10 | 2.70564575839e-05 | PASS |
| 2–3 | h | 1.43412837161e-10 | 2.70682245881e-05 | PASS |
| 0–2 | Delta | 0.000117670043361 | 2.70682245738e-05 | FAIL |
| 1–3 | Delta | 0.000117670042114 | 2.70682245881e-05 | FAIL |
| 0–3 | diagonal (disclosed) | 0.000117670186774 | 2.70682245881e-05 | FAIL |
| 1–2 | diagonal (disclosed) | 0.000117669898701 | 2.70682245738e-05 | FAIL |

Duration, maximum intervention and minimum normalized raw slack pass every
required edge. Energy passes both h refinements and fails both Delta
refinements by approximately 4.35 times the tolerance. Thus the aggregate
numerical A2 result is FAIL even though all four individual runs pass.
Exit code 3 records this scientific rejection. No tolerance was enlarged,
candidate was retuned or extra refinement round was silently substituted.
See [all metric inequalities](REFINEMENT.csv) and the
[machine-readable summary](../../runs/p1_r3/expanded_a7891c3/summary.json).

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
  All `865`
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
