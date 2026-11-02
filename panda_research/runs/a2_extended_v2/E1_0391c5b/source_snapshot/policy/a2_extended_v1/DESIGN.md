# A2-Extended v1 — fixed three-case numerical experiment

This extends the smoke-test scope; it does not replace the original r4 0.25 s
record or grant A3 authority. The user explicitly adopted the attached plan.
The original full checkout, raw evidence and clean baseline reproduction are
available. All original tracked files, policies, sources and earlier failures
remain byte-identical to commit45d1ada. A separate worktree/branch is used.

Before any extended motion, commit the plan, runner, reference implementation,
contracts, codec and SHA-256 input inventory. Declare exactly E1/E2/E3, each1s,
and exactly four original C4 cells per case. No indefinite extension or
results-guided reference selection is permitted. No finer cohort is selected.

The amplitude rule is `a_i=min(.02*(QMAX_i-QMIN_i),.12 rad)`. The original
midpoint Jacobian's unique largest translational column is joint2. E1 commands
its +0.070512 rad net transfer. E2 commands j2(+0.070512),j4(-0.06004),
j6(+0.0754) together. E3 commands j3(+0.115892),j5(-0.115892) by0.5s,
then returns to its actual initial configuration by1s. E1 tests a single
commanded transfer, E2 tests serial-chain coupling and E3 tests reversal.
The deterministic choices use physical joint widths and the frozen geometry;
they are not claims of guaranteed feasibility.

Each reference starts from its own measured P1 endpoint q and qd. Every segment
is a quintic Hermite polynomial with zero start/end reference acceleration.
The first starts with actual qd; later segments start/end with reference qd=0.
Thus E3 is mathematically twice continuously differentiable at its turnaround;
floating evaluation errors at the boundary are tested and disclosed. Unselected
coordinates have the small Hermite transients required to match nonzero measured
initial velocities, not an invented static clamp. All terminal qd/qdd are zero
for the reference only; actual states remain measured simulated values.

The P1 controller,0.156s signed preparation, tolerances, model, friction,
disturbance, global clock, observer, gains, complete43-row current-state QP,
digital AB2 rule, actual torque hold and RK4 mathematics are unchanged.
Reuse original r3 integration and r4 controller/auditor code; new code provides
reference selection and a lossless trace-loader adapter. No new theorem term,
M1 number, fallback, clipping or controller truth input is added.

After each newly executed P1, record actual h,psi1,speed,manipulability,
previous torque, legitimate elapsed envelope and necessary paired conditions.
Solve the full initial hard QP even for diagnostic entrance rejection.
Screen the reference at the101 frozen time nodes including both endpoints and
the E3 join. This checks reference physical state/h/psi1 only; planner margins
and full trajectory feasibility are not inferred. Failed entrance/screen stops
that cell before motion. Subsequent QP or raw safety/envelope failures retain
the first failed attempted step and stop; no later torque/state advance occurs.

Run each of (Delta,h) in ms: (1,.25),(1,.125),(.5,.25),(.5,.125).
Per-cell completion, physical constraints, all original raw QP rows >=0,
analytic observer-bound sample slack >=0, T29 metrics and terminal accuracy
must pass. Retain1mm actual Cartesian and1e-6m planned terminal limits.
Compare energy,duration,max||tau-u|| and minimum normalized raw row on both
fixed-factor directions and both diagonals with exactly the approved tolerances.
A raw negative fails even near floating resolution. All outcomes are legitimate:
PASS,PARTIAL,FAIL; missing/engineering-failed checks are NOT VERIFIED.

Store all continuous requests r, digital requests u, applied tau, state/observer/
reference/errors, signed diagnostic truth, physical/QP/envelope slacks, KKT
metrics, dense numerical extrema and solver/timing metadata. The lossless
columnar codec stores all these original nested values with explicit schemas
and exact roundtrip checks. Report max/RMS||u-r||,||tau-u||,||tau-r|| separately.
Small QP correction supports only a claim relative to digital u. Mathematical
continuous-time results do not automatically transfer to the sampled scheme.

The unchanged r4 mathematical auditor is rebound to a copied globals mapping
whose sole change is the lossless trace loader; source and audit bytecode are
unchanged. Additional checks compare logged reference samples to the frozen
polynomials and explicitly list every retained negative raw slack. Interpolant
extrema and discrete sample checks do not enclose true-ODE integration error.

A separate clean checkout and fresh pinned venv reproduce the old baseline;
this is engineering reproduction, not another human's signature. Parallel T27,
G2.5,M1 and Stage1 work is development preparation only. No official A3 scenario
comparisons, independent approval, hardware safety, Level1 or publication claim
is authorized. Review requests and signature fields remain unsigned.

The read-only preparation campaign exposed occasional stalling QP queries.
Before extended motion, freeze a15s engineering query wall budget. Execute the
identical cold HardSafetyQP in an isolated per-cell service, preserving its
settings and IEEE data. Timeout yields UNKNOWN/no torque/no retry, not a claim
of primal infeasibility. This bounds hangs while retaining previous steps and
the attempted failed query. Production equivalence and no-fallback contracts
are tested; this is instrumentation rather than changed physics or tolerances.
