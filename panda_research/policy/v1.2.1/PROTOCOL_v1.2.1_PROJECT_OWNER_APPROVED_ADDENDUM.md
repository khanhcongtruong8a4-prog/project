# IC2AI 2027 — Approved protocol-policy addendum v1.2.1

**Recorded 1 November 2026.** Owner approved the configuration/protocol in chat and delegated C1–C6 decisions. This addendum supersedes only the unresolved *policy choices* in the staged Actions 1–2 package, not the original model equations or the verification requirements in Protocol v1.0/v1.1.

## Approved decisions

**C1 — Evidence and margins.** Adopt common-domain margin mode **M1**. All fixed domain/tube constants must be established once, prior to optimization, and shared by both planners. During any NLP evaluation, compute the current candidate's time-varying envelopes using those frozen constants. Both dynamic and candidate-wise constant-margin comparisons use *Level 2 sampled numerical estimates* until rigorous verification establishes Level 1. Sampled maxima cannot be called verified suprema or used to assert theoretical noninferiority of numeric solvers.

**C2 — Fair comparisons.** Primary Scenario B uses ten identical cold starts per method, with a common budget and failure reporting. Three common cross-seeds may be used only in an explicitly labeled secondary re-optimization/sensitivity analysis; never use asymmetric cross-seeding to claim independent performance improvement.

**C3 — Intervention.** Retain maximum 2-norm intervention <= 1e-6 Nm as a numerical pass criterion. Record primal, stationarity, duality/accuracy diagnostics separately. Passing tolerance does not certify true solver error. T27 remains an execution gate.

**C4 — Refinement.** Primary RK4 with held controls uses (Delta,h)=(1,0.25) ms. Validate all four pairings (1,0.25), (1,0.125), (0.5,0.25), and (0.5,0.125) ms. Keep observer updates and zero-order-hold control semantics consistent with each Delta. Report refinement by h and by Delta independently. Apply preexisting T29 tolerance rules without enlarging them after seeing traces.

**C5 — Canonical manuscript.** Freeze the uploaded `Project.rar` source version with hashes in `manuscript_source_hashes.json` as the current *reference version*. The current `03_contribution.tex` explicitly uses `|alpha_v-lambda_i| chi_v` and the shared-bus smoothing `phi_epsilon(z)=0.5*(z+sqrt(z^2+epsilon^2))`; implement those exact expressions. The scalar `delta_h` in the manuscript is interpreted as a barrier-indexed reserve vector with T16 units for simulation. This records the protocol interpretation; it does *not* silently correct manuscript text or certify that all theorem assumptions have been satisfied. A future theory-owner review must reconcile notation before Level 1/publication.

**C6 — Actual task source and T29.** Use exact cells of the supplied `Tasks_2026.xlsx` for T09/T10/T11/T14/T15/T16/T23/T25/T27/T30. Use Protocol v1.0 §8.1 for T29 row scales and numerical acceptance because no T29 tab is included in that task workbook; `T29_approved_protocol_row_scales.csv` records this source. Do not attribute those T29 rows to a nonexistent signed worksheet. Store all source hashes and exact cell provenance.

## Approved study choices

- Seven-body Gaz Panda, smooth Gaz friction, c1z=0, no added hand/payload/rotor inertia; flange TCP and free orientation.
- Time-only dual-harmonic injected disturbance with magnitude `0.02*tau_max_i` and analytic rate limits; global clock not reset on replanning.
- K_o=20I, Lambda=5I, kappa=10, alpha1=alpha2=alpha_v=5 (specified units as task workbook).
- w_min=0.1*w(q0); T16 reserves: `delta_tau=0.0012 Nm`, `delta_v=0.0002175 rad/s`, joint-HOCBF reserve `1e-4*(qmax_i-qmin_i)/(1s)^2`, manip-HOCBF reserve `1e-4*w_min^2/(1s)^2`, velocity-CBF reserve `0.0002175 rad/s^2`.
- Modeled rather than physically calibrated energy: `k_r=[0.001,0.001,0.001,0.001,0.003,0.003,0.003] W/(Nm)^2`, time weight 1 W, epsilon=0.01 W, smooth positive part of *summed* bus power, with coefficient sensitivity at multipliers {0,0.5,1,2}.
- Quintic 12-control-point spline, clamped knot vector from T25, T in [0.5,10] s, IPOPT/MUMPS initial options from T25 and dense ProxQP initial settings from T27. These are **design selections**, not demonstrations of solver feasibility or real-time performance.

## Outstanding execution blockers — not waived by approval

1. Define M1 common domain, velocity/acceleration ranges, tube extension, all derivative/tube constants and the estimator grid/seed/budget; verify provenance and no candidate-dependent changes. Define candidate-wise maximum computation and its nondifferentiable-optimizer handling before NLP programming.
2. Implement and unit-test closed-loop DOB, Slotine–Li, HOCBF-QP, integrator, apply-torque observer update, and raw-C T28 consistency. Obtain actual tested QP behavior rather than relying on tolerances on paper.
3. Freeze actual T22 selected task/Scenario B test set and complete baseline fairness procedures; test A2 and two-factor refinement; T27 and G2.5 must pass before A3. All pre-experiment settings, including solver versions, seeds and budgets, must be hashed.
4. Record any independent qualified human reviewer signatures if the publication team demands that level of acceptance. Project-owner approval is not a substitute.

**Readiness: A1 GO, A2 NOT YET AUTHORIZED, A3/Level 1/publication NO-GO.**
