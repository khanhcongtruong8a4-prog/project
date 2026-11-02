# A2-Extended v3 — explicit causal interval QP controller amendment

The user's continuing numerical-development authority covers the goal of all
three fixed cases passing every original cell/refinement condition. This new
version addresses a substantive digital realization issue exposed by v2:
all twelve individual cells passed, but E3 energy and maximum intervention
failed Delta refinement on both edges and both diagonals. Those complete raw
runs and failed comparisons are preserved. v1 failures and the original narrow
r4 numerical GO are also unchanged. No successful label is substituted for
any historical result.

In v2, the causal interval-average nominal request u was filtered against
instantaneous start-of-interval G,c. When a constraint is active, that mixes
two different time representations and can introduce first-order control-period
error. The new digital controller samples the affine QP data with the same
causal two-step rule: B0=B_current, Bk=B_current+0.5(B_current-B_previous),
for B=G,c. The nominal r/u controller and all its physical gains are unchanged.
This is a new sampled QP realization, not a numerical tolerance repair or a
claim of equivalence to the original instantaneous continuous-time QP.

The actual solved 43-row QP has G_interval tau+c_interval >=
(0.1+1e-8)*original_row_scale. The 0.1 is an explicit, fixed engineering
inward reserve for the causal interval realization; 1e-8 is the v2 roundoff
guard. The extra reserve makes this digital optimization problem stricter.
It is a design constant, NOT a certified M1 drift bound or between-sample
safety certificate. It was selected and frozen before any v3 motion, without
altering a trajectory, duration, amplitude, gain or pass threshold.

After that ONE cold query, every ORIGINAL actual-current-state inequality
G_current tau+c_current >=0 is separately recomputed with no tolerance
exception. Any negative, missing solve, nonfinite candidate, T29 failure or
physical/observer failure ends the cell. No alternative candidate is tried.
Only the final QP candidate is held; no clipping, extrapolation after the QP,
backup controller, hidden projection or disturbance-truth input is used.

The actual initial query is the complete 43-row tightened current-state QP:
there is no past row at bootstrap. It is reused for the first application.
Later queries use only original current rows and the previous measured rows.
History is fresh per cell, isolated from preparation and consumed once per
attempt; a failure ends that history. There is no future state/reference or
observer reset. Actual q,qd,z, the signed disturbance clock and legitimate
elapsed observer envelope transfer unchanged from a fresh P1 in each cell.

All original raw G,c, names, scales and slacks are logged alongside the actual
solved interval QP, previous-row inputs, both dual scalings and residuals.
The original numerical T29 thresholds (1e-9 primal/stationarity) apply to the
ACTUAL declared digital QP. We do not falsely assert original-instantaneous-QP
stationarity. All original current-state physical rows have their separate
exact nonnegative sign gate. The extra audit recomputes both facts and the
entire causal row history, without solving another QP.

Pre-motion development consists of ten analytic/causality/sign/history/
worker/immutability contracts and read-only queries of all 6000 retained v2
E3 matrices. The latter retain their OLD states and requests, actuate no torque
and are not v3 closed-loop or refinement evidence. All pass. The new source,
policy, tests, this design, prior evidence and input hashes are committed
before any of the twelve new v3 motion cells.

The full original C4 is rerun for E1/E2/E3, and all four fixed-factor edges
and two diagonals must pass unchanged metrics/inequalities. No finer cohort
is substituted. The reference polynomials, actual-endpoint construction,
model/inertias/friction, disturbance, observer, startup, Slotine-Li gains,
AB2 nominal rule, ZOH, RK4 and energy model remain unchanged. A computed
PASS is scoped to this versioned digital controller and these fixed cases.

There is no new continuous/sampled stability theorem, original manuscript
rewrite, official T27 completion, A3 solve, hardware validation or Level 1
certificate. The user's acceptance statement is retained verbatim; no
external reviewer name/signature is invented. Publication interpretation of
this digital QP amendment needs a separately attributable controls/theory
decision. Scientific FAIL remains possible and must be retained.
