# Protocol v1.1 — reviewer-remediation addendum, revision R1

Prepared 1 November 2026. **PROPOSAL — NOT APPROVED OR EXPERIMENT-FROZEN.**
This separate addendum addresses the full-package reviewer report. It proposes
replacements only for v1.1 TXT B2/D/F and DOCX 10.2/10.4/10.5, and additions to
v1.0 8.2. Original documents and the research workbook are unchanged. All other
v1.0 physical-model choices, T22 rules, disturbance, thresholds, and stop rules
remain in force. Numerical model validation does not approve experiments.

## 1. Evidence wording replacement (TXT D; DOCX 10.4)

The original 19 checks are internal checks. In-code literal checks are not Gaz
source-byte comparisons; in-code MDH/URDF lists share rotation helpers. The
Mdot/C, skew-power and ID-power checks share M derivatives and cannot validate
physical parameters; the gravity finite difference shares U. The finite-
difference Lagrange test checks the implementation using the same model.

New reproduction, source-table and external-library evidence is kept separately
in reports/. The external reference parses official Xacro joint elements and
Gaz author MATLAB parameters, cross-checks the revised supplement, and uses
Pinocchio CRBA/RNEA. It never uses the target's M, dM, U or transforms to form
reference outputs. These are ordinary numerical model comparisons, not a
qualified person's acceptance, hardware validation, or interval certification.

## 2. Proposed margin decision: M1 (TXT B2; DOCX 10.2)

Choose **M1: common precomputed model/tube constants**, frozen before Stage-1
optimization and held identical for all candidates and both margin methods.
Do not implement M2 candidate-local constant recomputation in this revision.
M1 fixes constants; the envelope functions and resulting margins can remain
time-varying and can depend on the candidate's state, rates and final time
through their declared formulas. Do not replace them with arbitrary static
reserves. M2 would need a new, approved inner/outer iteration, convergence
criterion and termination/failure policy; none is implicitly authorized here.

### Domain, computation, and update frequency

Use v1.0's enlarged position box Q = product[q_min-0.01, q_max+0.01] rad.
The velocity/acceleration domain, required tube extension, and the complete
constant vector K remain unselected: obtain their exact definitions from the
mathematical framework/manuscript and include them in the frozen registry.
K must include every model norm, inverse-inertia, derivative and tube constant
actually used; enumerate formula ID, unit, domain, method and evidence for each.
The current sampled min eigenvalue is not a global m1. Do not place it in a
certified inverse bound or call it a lower enclosure of M over Q.

For Level 2, compute a declared deterministic sample estimate on the frozen
domain, with independent seed and grid, before solving any candidate. The
grid/seed/budget must be selected and approved before computation; they remain
null in the proposal manifest. The estimates are common **NUMERICAL ESTIMATES
OF DOMAIN CONSTANTS**, not verified global bounds. For Level 1 use verified
outward-rounded enclosures over the entire domain and independently checked
m1>0, plus all other theorem hypotheses. Changing a constant, domain, gain or
evidence method creates a new protocol/configuration hash and restarts the
entire comparison set; no per-candidate or result-driven updates are permitted.

### Stage-1 NLP and circular-dependence handling

Let z denote the planner's original trajectory coefficients and final time T.
Let E(t; z, K) denote the manuscript's componentwise observer/position/velocity/
sliding/residual envelopes, evaluated using frozen K, gains, and initial bounds.
The missing manuscript/framework prevents approval of equation-level formulas:
E is a specification interface here, NOT an invented replacement control law.
Before implementation, attach each exact manuscript equation to its named
output and document the units and dependency graph; this remains an entry gate.

At **every NLP residual evaluation**, evaluate E with the current z and T and
then compute EVERY corresponding signed tightening (including chi_v, signed
torque margins, barrier margins and fixed numerical reserves) inside that
candidate's constraints. Never evaluate margins once at a warm start and reuse
them after z changes. Use analytic/AD-consistent derivatives of the same
residuals. K is an NLP parameter, never an optimization variable or a function
of the current solution. This removes a plan-to-K fixed-point loop; it does not
waive any algebraic dependence within E. Any additional circular dependency
found when the missing equations are loaded must be resolved and reviewed
before coding a planner or passing this gate.

Require the full error tube to remain in K's declared domain, and enforce the
same terminal, physical, barrier, initial h/psi1, solver and residual conditions
as v1.0. A candidate outside the domain is rejected, not extrapolated. On a
normalized transcription time s in [0,1], use t=T*s explicitly; the grid size,
degree, knot policy, interpolation and derivative convention belong in the
manifest and are currently null. Prefer direct envelope evaluation at every
NLP and residual-check node; interpolation is not evidence of a between-node
upper bound. For a separately tabulated envelope, use a nonnegative per-cell
upper value only when a declared cell bound justifies it. Otherwise label it
sampled and test direct values at independent midpoints; any new violation
rejects the candidate and triggers recorded uniform refinement of all methods.
Level 1 requires verified between-node bounds. Level 2 node/midpoint checks
are numerical evidence only, even after convergence.

### Matching constant-envelope baseline

For EACH baseline candidate z, compute its own E(t; z, K), then use the
componentwise maxima over that candidate's FULL horizon for every matching
envelope, including chi_v. Compute signed torque and barrier tightenings from
these replaced envelopes and the same frozen reserves and formulas. Evaluate
these maxima inside the candidate's NLP residuals, not as constants copied
from the dynamic method's final plan. An epigraph implementation must impose
all envelope sample inequalities and certify the declared maximum rule after
the solve; unverified epigraph slack cannot establish an exact maximum.
T23 must approve the exact manuscript maximum construction, ordering of the
maximum and margin operations, and its derivative/nonsmooth solver treatment.
These equation-level details remain pending with the missing framework.

Both methods use the SAME K, evidence level, grids, interpolation rules,
between-node checks, tolerances, objective, gains, disturbance, multistarts,
budgets and failure reporting. A sampled maximum is not a verified supremum.
No feasible-set or optimizer-superiority claim follows from a numerical solve.

## 3. Scenario B fairness addition (v1.0 7 and 8.2; TXT B2)

Keep the original deterministic, proposal-conditioned T22 selection rule for
Scenario A, including logging every rejection and freezing its task/plan before
baselines. Because it conditions on the proposed planner, that task is unsuitable
as the sole unbiased Scenario B suite; disclose that selection bias explicitly.

For Scenario B, propose the separate ordered target list generated by
prepare_scenario_b_suite.py: 64 scrambled Sobol points in seven joint fractions
0.05..0.95, seed 20261102, from scipy Sobol random_base2(m=6). Map each to the
flange; remove ONLY distance below 0.10 m from the midpoint start and duplicate
targets within 1e-6 m. Orientation is free and initial velocity is zero. Include
every remaining target; no pressure, margin-method, feasibility or optimizer
outcome is used to select it. Keep all skipped indices and geometric reasons.

The generated JSON and hash fix this proposal before either method is tested;
the team must approve it and freeze it with all shared parameters before A3.
Kinematic reachability is not dynamic feasibility or a safety claim. Report
both methods' failures, timeouts and infeasibility per target, plus paired
metrics on jointly successful cases with the denominator stated. Do not replace
failed targets, hide failures or regenerate a seed after seeing outcomes.
Keep v1.0 delta_J/epsilon_J and modeled-energy units unchanged. Comparative
and multistart seeds, all initial guesses, start count, budget, solver version,
warm-start policy and aggregation plan are unselected and must be frozen
BEFORE either method runs. They are explicit nulls, not hidden defaults.

## 4. T29 integrator AND control-period refinement (addition to v1.0 8.2)

Two independent refinements are required; h/h2 alone is insufficient.

1. Fix control period Delta and zero-order hold, gains, initialization and
   the SAME frozen plan. Compare integration steps h and h/2; split integration
   at every control update and discontinuity, without moving their times.
2. With a passing fine integration rule, compare control periods Delta and
   Delta/2 and include the corresponding h/2 and h/4 integration pair at the
   refined control period. Recompute the controller, DOB and QP at the new
   update times; keep gains, disturbance clock, model and plan unchanged.
   Evaluate both traces on a prespecified common physical-time validation grid.
   Re-evaluating a controller at more nodes on the same held torque trace does
   NOT count as control-period refinement.

Propose fixed-step RK4 for continuous plant/DOB integration with held applied
torque and controller/QP updates at the frozen Delta. Exact sampled DOB/filter
ordering, state used for QP, and update semantics require controls review and
remain null in the manifest. Set h=Delta/m for a frozen integer m>=4. Initial
Delta, m and validation grid remain null until selected. Use float64. Do not
substitute a simulator default or rely on adaptive-step defaults. If another
integrator is selected, freeze its algorithm, rtol/atol, dense output and
event policy first; no such alternative is approved here.

For BOTH refinements preserve v1.0's criteria:

- J and each planned/executed modeled energy: absolute difference <= 1e-6 J
  + 1e-4 times the larger absolute value.
- T: <= 1e-6 s + 1e-4 times the larger absolute value.
- Maximum intervention: <= 1e-7 N m + 1e-4 times the larger maximum.
- Each normalized slack minimum: <= 1e-6 + 1e-4 times the larger absolute
  minimum. Keep every unnormalized signed minimum and raw negative value.

On the same fixed plan, planned J, planned energy and T may be identical; state
that explicitly and do not count these trivial equalities as execution evidence.
All underlying physical and envelope slacks must separately be nonnegative;
each QP update must meet measured normalized primal and scaled stationarity
residuals <=1e-9, successful status, frozen row scales, and T27 numerical accuracy.
Reserves/row-scale must exceed 1e-7. Zero-intervention threshold remains
1e-6 N m. Actual terminal Cartesian error must be <=1e-3 m, with planned error
<=1e-6 m. Refinement agreement never overrides an underlying safety/QP failure.

Propose at most three uniform refinement rounds, preserving all runs and
failure reasons. On failure, halve the affected steps under the recorded rule;
do not retune gains, excitation, weights or thresholds to obtain agreement.
If still failing, A2 FAIL / A3 NO-GO and diagnose. The round budget is a proposal
requiring approval, not a test already executed. Retain configuration hashes,
all update times, traces, QP statuses/residuals, metrics and comparison JSON.
Convergence does not prove sampled-controller safety or all-time bounds.

## 5. Retained disturbance, initialization and tracker mapping

d_i(t)=a_i[0.6 sin(omega(t-t_ref)+phi_i)+0.4 cos(2 omega(t-t_ref)+phi_i)],
a_i=0.02 tau_max,i, omega=1 rad/s, t_ref=0 s, phi_i=2 pi(i-1)/7.
Analytic bounds: dbar_i=a_i N m; dbar1_i=1.4 a_i omega N m/s.
Retain the global time through replanning. Do not use the older 1% cosine.
p=M(q)qd; dhat=z+K_o p; z(t0)=-K_o M(q0)qd0; varpi_i0=dbar_i.
Use applied torque in the observer, preserve z and propagated varpi on replan,
and match the measured reference state. Never reset the observer bound to zero.

Task mapping from the review/handoff (workbook not supplied for reinspection):
T10 K_o; T11 Lambda/kappa; T14 HOCBF alpha gains; T07 motor-data search;
T08 electrical-literature audit; T09 modeled-energy wording and k_r sensitivity.
Gear ratio/rotor inertia do not determine R, k_t or calibrated k_r. The current
energy objective remains MODELED; no electrical coefficient is invented here.

## 6. Entry gates and signatures (TXT F; DOCX 10.5)

A1 implementation can continue. External source/model checks are technical
evidence only. A2 is BLOCKED until a qualified independent reviewer accepts the
dynamics/source mapping and signs the required T04b/T06a sheets, the remaining
smoke-test settings are selected, and controls approves the execution plan.
No A2 or shakedown has been run in this remediation. A3 remains NO-GO until
external ID agreement, signed source/frame checks, passing A2 with BOTH
refinements, T27, positive G2.5, M1 decision, complete signed+hashed v1.1,
T22 frozen before baselines, and the Scenario B suite/solver policy are frozen.
Level 1 additionally needs verified global m1>0 and every theorem hypothesis.
Publication-result claims remain NO-GO. A sampled eigenvalue is not m1.

Team lead name/date/signature: __________________ / __________ / __________
Independent dynamics reviewer: _________________ / __________ / __________
T04b second-person reviewer: ___________________ / __________ / __________
T06a second-person reviewer: ___________________ / __________ / __________
Controls reviewer: _____________________________ / __________ / __________
T22/T29 approver: ______________________________ / __________ / __________

All signatures are pending. Use the unresolved-decision register and proposed
manifest; do not treat the preparation date, generated hashes or this document
as team approval. Obtain missing framework/workbook inputs before finalizing
the exact NLP/envelope map, constants, gains, solver policy or comparative runs.
