# Protocol v1.2.2 — DRAFT / OWNER APPROVAL PENDING

This is an unsigned proposal extending the immutable owner-approved v1.2.1
design. It provides no plant-prehold or official A2 execution authorization.
All new owner, controls, theory, build and execution-authorization fields are null.
The read-only reviewer assessment is not an independent numerical reproduction.

## Proposed startup amendment: P1

Explore observer settling during physical time [-0.156,0] s before motion.
The duration follows the analytically derived, previously declared rule in
[PREDECLARED_P1_DESIGN.json](PREDECLARED_P1_DESIGN.json). It is not a successful
physical-hold result. Use the same global disturbance clock with t_ref=0, the
actually applied torque, and continuous observer state/envelope through zero.
No ideal clamp, reaction torque or observer/disturbance reset is allowed.

The preparation controller is the unchanged Slotine–Li law at a stationary
midpoint reference, projected onto the physical torque box. That saturation
belongs only to the proposed preparation controller; never clip an online
hard-QP solution. The proposed hold must keep each joint within 0.01 rad of
midpoint and 0.02 rad/s throughout. Preparation is outside the A2 safety claim.
No such hold has been simulated or established. The existing runtime's signed
preparation-clock adapter is not implemented. Therefore **P1 is BLOCKED**.

At zero retain actual measured q,qd,z and propagated varpi. Check the actual
endpoint's h,psi1,velocity,manipulability and full 43-row QP before motion.
The midpoint/zero-velocity fixtures cannot substitute for that measurement.
Failure preserves NO-GO; no automatic duration extension or alternate gains.

## Proposed A2 reference and duration

Use a nonoptimized quintic Hermite joint reference on [0,0.25] s, with
q_start,qd_start equal to the measured P1 endpoint, initial reference
acceleration zero, offset [0.01,0,-0.01,0,0.01,0,0] rad, and terminal reference
velocity/acceleration zero. With s=t/T and dq=offset:

`q_ref(s)=c0+c1*s+c2*s^2+c3*s^3+c4*s^4+c5*s^5`, where
`c0=q_start`, `c1=T*qd_start`, `c2=0`, `c3=10*dq-6*T*qd_start`,
`c4=-15*dq+8*T*qd_start`, `c5=6*dq-3*T*qd_start`.

The Cartesian target is flange FK(q_start+dq), orientation free. Planned
terminal position error must be <=1e-6 m and actual error <=1e-3 m. This is a
proposed short component smoke task; the Stage-1 free-time planning bounds
0.5<=T<=10 s remain unchanged and are not used by this reference. It is not
Scenario A, a selected T22 task or an optimized trajectory.

Record endpoint, target and all polynomial coefficients for each C4 cell.
The measured endpoints can differ between cells; disclose those differences
and obtain controls approval of the comparison before any run. No common
endpoint is manufactured by resetting the plant state.

## Observer and failure semantics

Primary proposal: integrate q,qd,z together in RK4, with the actually applied
torque held over each control period. A separately labeled sampled-observer
sensitivity proposes one forward-Euler z update per control period, using
sampled q,qd,z and the same held applied torque. Its exact definition and
acceptance are in `observer_proposal.sampled_sensitivity_definition` of the JSON.
It is not implemented or run. Neither convention supplies a certified physical
sampled-observer error bound; a numerical violation of varpi must be disclosed
and cannot be repaired by enlarging the envelope after a run.

Hard-QP infeasibility or a rejected solve records **A2 FAIL**. In development,
raise the stop before actuation/state advance and return no torque candidate.
This says nothing about the safety of zero torque on hardware. Recovery remains
disabled: K_b and gamma are null, and no new recovery law is implemented.

## C4 refinement and acceptance

Retain all four owner-approved pairings:

| Control period Delta (ms) | RK4 h (ms) | Substeps m |
| --- | --- | --- |
| 1 | 0.25 | 4 |
| 1 | 0.125 | 8 |
| 0.5 | 0.25 | 2 |
| 0.5 | 0.125 | 4 |

Later approval **C4 supersedes** the older T25 h=Delta/4 default for the m=2
cell. Keep observer/hold conventions explicit for each Delta; use the same
T_pre and predeclared rules rather than selecting a separate duration per cell.

Preserve every v1.2.1 threshold. Compare h at fixed Delta and Delta at fixed h;
report cross-diagonal comparisons too. Each metric difference must be <=
max(its approved absolute tolerance, 1e-4*max(abs(metric values))). Metrics and
absolute tolerances are energy 1e-6 J, duration 1e-6 s, maximum torque correction
1e-7 N m and minimum normalized raw slack 1e-6. The 1e-6 N m zero-intervention
criterion remains a numerical diagnostic; this nonoptimized A2 does not assume
the filter should be inactive. Log and report interventions without retuning.

Physical state, raw row, applied torque, observer-envelope, QP and terminal
criteria are explicit in `A2_acceptance_proposal`. Any negative raw CBF slack
is FAIL even when normalized solver residuals satisfy 1e-9. Post-control truth
may diagnose observer error but may never influence a command, screen selection
or initial condition. Record retained plant stages as sampled checks; no
between-sample safety or Level 1 certification follows. Full T27 remains open.

## M1 scope and preserved baseline

The proposed nonoptimized A2 uses the validated local model and legitimate
varpi, with full online QP checks. Planner-only M1 bounds are not unconditional
entry requirements. All remain open for A3 and Stage-1 references; if that
reference is chosen instead, its actual M1 bounds and plan are required.
The reference decision itself requires explicit owner/controls approval.

Model, gains, initial disturbance magnitude/rate, reserves, row scales, energy,
solver settings, C1–C6 choices and equation files remain unchanged. No arbitrary
zero replaces a missing bound. Policy approval must never be inferred from
successful static arithmetic or a generated checklist.

The canonical 02/03 files match their approved hashes. main.tex and Project.rar
still differ from approved hashes; the draft records both versions and leaves
build acceptance null. No manuscript/source archive or old evidence is edited.

## Decisions and authorization

A1 component development GO. P1 BLOCKED pending actual holding validity and
reviewed execution support. Official A2 NO-GO; A3, Level 1 and publication NO-GO.
Follow the three human actions in
[NEXT_THREE_ACTIONS.md](../../reports/p1_v1.2.2/NEXT_THREE_ACTIONS.md).
This addendum itself never authorizes a prehold, A2 or a paper experiment.
