# Action 3 component development — v1.2.1

This implements the uploaded Action 3 assignment. The numerical Panda runtime
`src/panda_dynamics.py` is unchanged from v1.2.0. Current components live under
`src/panda_closed_loop/`. This is a verification/development release, not an
approved A2 execution or a production-certified controller.

## Source and configuration authority

The exact supplied policy package is under policy/v1.2.1. Its JSON and all
manifest-listed files are checksum-verified. Typed Policy loads the approved
gains, limits/reserves, clock and QP settings read-only. The original workbook
cells are parsed directly from XLSX and compared to the supplied provenance CSV.
Policy v1.2.1, rather than prior v1.1/M1 proposals, governs the design choices.

The equation files `02_mm&nc.tex` and `03_contribution.tex` match policy hashes.
`Project.rar` itself and `main.tex` do not. Their actual/expected hashes are
reported; canonical equation implementation is allowed, while whole-manuscript
build revision acceptance stays open. No manuscript or workbook was edited.

## Commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python scripts/action3.py preflight
.venv/bin/python scripts/action3.py validate
.venv/bin/python scripts/action3.py a2
```

The last command deliberately exits **2** and writes an explicit refusal with
blockers. There is no `--force` bypass. Validation exits nonzero on unexpected
test/regression failures. Every command creates a new runs/action3/ directory
with effective configuration, dependency versions, hashes, source snapshots,
audit, equation crosswalk, M1 registry and stage gates. `validate` runs the full
existing dynamics/source/Pinocchio/MuJoCo workflow as well as new component tests.
The existing model runner remains separately callable.

## Implemented components

| Module | Scope |
| --- | --- |
| config | Typed, immutable-by-copy policy; source/cell audit; explicit null-input blockers |
| observer | p=M qd, dhat=z+Ko p, correct applied-torque zdot; analytic continuous ideal envelope |
| controller | e=qp-q, s=edot+Lambda e, positive kappa M s; no alternate error-sign law |
| reference | Constant-velocity measured-state fixture; no optimized trajectory |
| geometry | Base-frame flange Jv (3x7), W=det(Jv Jv^T), AD gradient/Hessian |
| barriers | 15 position-level rows, 14 speed rows, 14 torque rows with Protocol v1.0 T29 units/scales |
| qp | Dense ProxQP 0.7.2, exact policy settings, dimensionless theta/objective, measured KKT diagnostics |
| stepper | Held applied torque, controller/QP once per Delta, coupled RK4 for q/qd/z, global disturbance clock |
| margins | Available one-sided allowances and canonical abs(alpha_v-Lambda) algebraic interface only |
| readiness | Equation-to-code mapping, missing M1 registry and A2/A3 gates |

The online robust rows match manuscript eq_robust_cbf. T16 planner reserves
are exposed with per-barrier units; they are not silently subtracted from the
execution hard QP. No missing bound is replaced by zero. Recovery needs K_b,
gamma and explicit semantics, so it is disabled. Solver or hard-QP failure
returns no torque and triggers a protective-stop/replan request; zero torque
is not asserted to be safe. Box projection is tested separately, not used as
an unapproved fallback.

## Numerical conventions and evidence

Ko=20I, Lambda=5I, kappa=10, alpha gains=5 and the 2% dual harmonic come from
the policy. True injected disturbance is private to the plant; observer and
controller take state, model, estimates and actual torque only. Test/reference
oracles may use truth, and logs label that use explicitly.

The chosen component observer convention integrates z with the physical plant
stage states in RK4 while holding applied torque. This is an explicit proposed
numerical convention, not approval of the null policy observer-update field.
No real sensor delay or discrete-envelope theorem is claimed. Controller and
QP are never reevaluated inside an RK4 substep. Replanning preserves z/time
and the propagated bound. ProxQP starts cold at each component solve; future
warm-start policy remains unapproved.

Tests retain negative raw slacks. A small normalized solver residual is not
formal invariance; negative physical torque slack rejects a candidate rather
than being silently clipped. Fixture KKT tests do not complete T27. Synthetic
2x2 timing tests implement the policy schedule but do not count as A2 refinement.

T28 compares raw target C with an explicit Christoffel reference formed from
five-point differences of independent source-built Pinocchio mass matrices.
Three step sizes and the exact original 22 states are checked. Cqd/RNEA and
Mdot-C-C^T are additional diagnostics. Raw Pinocchio C agreement is reported,
not assumed by library convention. Finite-difference/sample limitations remain.

## Critical result and remaining gates

At approved q0 midpoint and zero velocity, varpi0=0.02*tau_max makes several
paired robust speed rows contradictory: abs(M^-1) varpi0 exceeds alpha_v vmax.
The implemented QP reports infeasible and the harness stops before advancing.
The detailed point-specific evidence is a component fixture, not a G2.5 screen
or a theorem about all configurations. No gain/bound/disturbance was retuned.

M1 constant values, velocity/acceleration domains, tube extension, estimator
grid/seed/budget, derivative bounds and observer discretization approval remain
open. Current input therefore cannot produce an official A2 run. A1 is GO;
A2 is HOLD/NO-GO; A3, Level 1 and publication remain NO-GO. Owner acceptance
is not an independent reviewer signature. Refer to reports/ACTION3_REVIEW_HANDOFF.md
and its immutable run for actual test counts and exactly three next actions.
