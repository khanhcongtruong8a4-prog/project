# A2 r4: second-order sampled execution and numerical GO

The user requests: “Modify so that A2 pass and that A2 is a solid GO.” This
continues the explicit authorization for simulation development, versioned
policy changes and P1/A2 numerical tests. This amendment defines an evidence-
backed **A2 numerical simulation GO**. Independent reviewer signatures, a
hardware deployment and publication approval are not inferred from it.

The prior r3 result remains FAIL: its four individual cells pass but energy
changes by 1.1767e-4 J under control-period halving, above the 2.7068e-5 J
tolerance. Its model, gains, reference, 0.156 s preparation and all acceptance
thresholds remain fixed. No failed evidence is edited or reclassified.

## Change the execution sampling rule

Let `r_k` be the original continuous Slotine–Li torque request evaluated from
the measured state, current reference and DOB estimate. For execution only:

```
u_0 = r_0
u_k = r_k + 0.5 * (r_k - r_{k-1}), k >= 1
tau_k = original full 43-row current-state hard QP applied to u_k
```

The causal two-step quadrature is the Adams–Bashforth approximation to the
interval-average request. Smooth-request consistency is second order; the
first-current-value bootstrap contributes an O(Delta²) accumulated error.
This improves temporal sampling accuracy without altering the continuous law's
gains. It is a new digital realization, not the original r3 sampling policy,
a future-state predictor, a nonlinear stability proof or a continuous-time
safety certificate. Unit tests compare convergence to an analytic scalar
feedback solution and check affine-request integration.

Every cell has fresh execution history. Preparation uses the identical passing
r3 computed-torque controller; it never fills the new history. The actual
zero-endpoint solve bootstraps from its current request and is reused for the
first applied torque. There is one proposal per attempted QP update, with no
retry. Failure ends that cell and the instance is not reused. Log continuous
request, previous request, sampling correction, update index, QP correction
and actual applied torque separately. Do not conceal the new sampling correction
inside a zero-intervention claim.

All model parameters, disturbance, observer initialization and integration,
tracking/barrier/observer gains, limits, reserves, P1 windows, reference, torque
hold semantics, raw-negative-slack rule and numerical tolerances stay fixed.
The hard safety QP is evaluated at the actual current state, not an extrapolated
state, and its torque alone reaches the plant and observer.

## Predeclared numerical validation

The original four C4 cells are mandatory:

| Delta ms | h ms |
| --- | --- |
| 1 | 0.25 |
| 1 | 0.125 |
| 0.5 | 0.25 |
| 0.5 | 0.125 |

A second mandatory 2x2 cohort confirms the finer behavior:

| Delta ms | h ms |
| --- | --- |
| 0.5 | 0.125 |
| 0.5 | 0.0625 |
| 0.25 | 0.125 |
| 0.25 | 0.0625 |

The shared (0.5,0.125) result is reused within this one frozen run: seven
distinct cells, eight cohort entries. Every cell reruns the complete preparation,
actual endpoint QP and 0.25 s execution. Both cohorts must pass all four metric
inequalities on every fixed-factor edge, plus both diagonals. The diagonal
requirement strengthens the previous protocol; no threshold is relaxed.
No gain search, automatic smaller-grid substitution or additional candidate
is selected after testing. Retain a HOLD if this frozen design fails.

## Evidence-backed gate

`numerical_gate()` returns GO only when grid coverage is exact; all preparations,
actual endpoint QPs and full A2 executions pass; both cohorts pass refinement;
every trace passes a read-only audit; pinned versions and canonical model inputs
match; the new contract suite passes; prior passing model/component regression
inputs are byte-identical; and the committed freeze is unchanged.

The audit verifies compressed trace hashes and directly recomputes the original
continuous requests, causal history, all actual 43-row QP matrices/slacks,
physical sample slacks, signed waveform, propagated bounds, held torque and
electrical-energy quadrature. It checks exact state transfer at zero. T29
thresholds and all raw inequalities remain unchanged. An engineering error,
missing cell or incomplete audit means HOLD, never a nominal GO string.

The existing passing model/component regressions are reused only with matching
recorded source/input hashes; this is not described as a fresh rerun or an
independent review. The new sampling contracts and all seven physical-model
cells must actually execute. The geometry expansion again requires all five
outputs to be bitwise equal at all 154 retained configurations before cells.

## Freeze and reproduction

Commit the new controller, runner, contracts, plan and frozen input inventory
before tests. Every original tracked research file, including r2/r3 evidence,
is protected byte for byte. Evidence uses new exclusive files under `runs/p1_r4`.

```bash
cd /workspace/project/panda_research
/workspace/panda-venv/bin/python tests/test_p1_r4.py --report /tmp/r4-contracts-new.json
/workspace/panda-venv/bin/python scripts/p1_r4.py --contracts /tmp/r4-contracts-new.json
```

Exit 0 means the complete numerical gate is GO; exit 3 is scientific HOLD;
exit 1 is an engineering error. Numerical GO is scoped to this fixed simulation
and observer convention. Hardware timing, real sampled/delayed observer
guarantees, independent signatures, manuscript-build acceptance, M1, complete
T27, G2.5, A3, Level 1 and publication are separate, unchanged claims.
