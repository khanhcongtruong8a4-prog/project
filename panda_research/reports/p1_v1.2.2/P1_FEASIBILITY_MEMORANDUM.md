# P1 feasibility memorandum — DRAFT / OWNER APPROVAL PENDING

**P1 overall: BLOCKED. Official A2: NO-GO.** Static sampled online checks pass;
the actual applied-torque prehold, end state, signed execution clock and numerical
observer envelope are not verified. No physical or plant prehold was executed.

## Frozen inputs and ordering

The candidate design was written at `2026-11-01T16:57:42.949507+00:00`
before the screen run `runs/p1/20261101T171712576665Z`. Its SHA-256 is
`4f59db4cd77376ed78978fa2c0b5c0ab9644cf7b672ceff031fb3a76eeb9d936`. The prescribed state set is the physical
joint midpoint plus all 128 sign corners at ±0.01 rad per joint; velocity radius
0.02 rad/s per joint. Report times are 0, 0.125 and 0.25 s. No favorable state
selection, gain sweep, plant trial, disturbance query or duration retry was used.
The accepted r2 ZIP and v1.2.1 policy are immutable references in the draft manifest.

## Exact necessary online conditions

Let `N=M(q)^-1`, `B=abs(N)*varpi`. For a linear joint barrier, its Hessian is zero.
Adding each upper and lower row cancels torque, bias, q and the linear velocity
terms. Thus the exact paired sums are:

`velocity: 2*alpha_v*vmax - 2*B >= 0`;
`position: alpha1*alpha2*(qmax-qmin) - 2*B >= 0`.

Both reduce to `B <= RHS`, in rad/s². They are necessary only. At the original
startup they fail for velocity joints 1,3,4,5,6,7 and position joints 1,3. Worst
violations are 84.460672698 and
22.903172698 rad/s².
The complete baseline QP correctly reports `QPSolverOutput.PROXQP_PRIMAL_INFEASIBLE`.
No solver tuning can repair that algebraic contradiction.

## Analytic duration, selected once

At physical time `-T_pre`, initialize `dhat=0`, `z=-Ko*M(q)*qd`, `varpi=dbar`.
For common `Ko=20/s` and `dbar1=1.4*dbar/s`, observer elapsed time is
`s=physical_t+T_pre` and

`varpi(s)=dbar*[f+(1-f)*exp(-20*s)]`, `f=0.07`.

At each predeclared node/joint let `R=min(alpha_v*vmax,alpha1*alpha2*range/2)`.
The smallest ratio `R/B_initial` is `0.112086426911` at node
122, joint 3. It exceeds the floor
fraction. The analytic critical time is `0.15477296493` s. The previously
declared rounding rule `ceil(Tcritical/Delta)*Delta+Delta`, with Delta=0.001 s,
gives **T_pre=0.156 s**. This duration was not increased after
the complete-QP check. If the ratio were <=f, no finite duration would be returned.

At physical time zero the ideal continuous envelope is
`[0.19325512993674698, 0.19325512993674698, 0.19325512993674698, 0.19325512993674698, 0.026655879991275444, 0.026655879991275444, 0.026655879991275444]` N m. It is not reset at zero.
It decreases componentwise, so at each *fixed* q node the t=0 pair check covers
the future declared [0,0.25] s window. This is not an enclosure of all q in the
continuous neighborhood or of the future moving robot.

## Numerical evidence and limits

All 129 nodes pass both pairs at all three report times. Minimum online pair
slacks are 0.0989890646 (velocity) and 35.7564542 (position)
rad/s². All declared-node entry h and worst-case psi1 over the velocity box
are nonnegative; minimum h=0.022036687 (mixed physical
barrier units, not a normalized distance) and minimum psi1=0.109670634
(mixed derivative units). See each row's scale/units in the original barrier
implementation rather than comparing mixed raw magnitudes.

The complete **43-row** QP is numerically feasible for 129 fixed fixtures
at q=midpoint, qd=0: estimate zero and all 128 corners of
`abs(dhat)<=dbar+varpi(0)`. This estimate box follows from the triangle inequality;
it uses no disturbance truth. The full checks include position, velocity,
manipulability and torque rows. At a fixed state these constraints are affine
in (tau,dhat); feasible vertex witnesses support numerical feasibility of the
estimate box. They do not establish feasibility over a continuous q/qd tube,
the unmeasured physical hold endpoint or the subsequent trajectory. Full T27
is not completed by these fixtures.

Per-joint LHS/RHS/slack/units and source are in [online_pairs_per_joint.csv](online_pairs_per_joint.csv).
Full solver diagnostics and per-node states are in [screen.json](evidence/static_screen/screen.json).
No plant acceleration function or disturbance waveform is called by this tool;
the unit test patches both to fail on access.

## Proposed physical prehold: not executed and not yet justified

Use the existing Slotine–Li controller with fixed q_ref=midpoint, qd_ref=qdd_ref=0
and existing gains. Project that *preparation controller's* command componentwise
onto ±tau_max. Apply exactly that saturated torque to
`M*qdd+C*qd+g+F=tau_hold+d(physical_t)`. The DOB must use that same applied
torque. Integrate q,qd,z continuously with held torque; do not reset z/dhat or
the disturbance clock at zero. The prephase is outside the A2 safety claim and
does not use the initially infeasible hard QP. No kinematic clamp, reaction
torque, artificial q reset or fabricated disturbance estimate is allowed.

Required tolerance throughout the hold: abs(q-midpoint)<=0.01 rad and
abs(qd)<=0.02 rad/s per joint; applied torque remains in the physical box.
These tolerances have **not** been verified. Finite torque saturation alone
does not establish hold stability, trajectory safety or observer-envelope
validity with discrete measurements/numerics. No holding dynamics were simulated.

At zero measure actual q,qd,z and keep propagated varpi. Reject an out-of-window
endpoint. Recompute h,psi1,manipulability,speed and complete 43-row QP there;
do not claim q(0)=midpoint or qd(0)=0. Initialize the proposed reference at that
measured state. The current execution-state/epoch contracts reject negative
times: a reviewed signed-clock adapter is **not implemented**. The mathematical
elapsed-time map in the screen is not such an adapter or an authorization.

## Planner remains separate and blocked

The actual planner pair tool needs M1 Nbar and Abar domain bounds, which remain
null. It reports **BLOCKED_MISSING_M1_BOUNDS**. No point abs(N) is substituted
as a certified or sampled upper bound. An explicitly separate conditional
*lower witness* uses the requirement that any valid domain bound including the
midpoint must dominate its absolute entries. The reviewer factor-two lower
condition fails in all velocity joints at startup, and in joints 1 and 3 even
at the observer floor: LHS 13.065683 and 13.347212 versus RHS 10.875 rad/s².
Therefore waiting longer alone cannot restore that tightened planner at this
point under these unchanged gains/disturbance. This is conditional on a domain
including the point, not a computed M1 registry or a global impossibility theorem.

The source also retains the nonnegative Nbar*rho_r / Abar*rho_r term. At matched
reference initialization chi=0 but rho_r(0)=varpi(0), giving a factor-three
lower witness; it is reported separately, not silently dropped. The implemented
M1-input arithmetic is a necessary lower-margin screen and explicitly omits
nonnegative beta/tube terms. A pass would never establish full planner feasibility.

## Failure modes and disposition

P1 is blocked by physical hold validity, continuous state coverage or actual
endpoint checks, signed-clock execution support, numerical observer validity,
and human policy/review decisions. If any predeclared condition fails, retain
the failure; do not extend T_pre, select another q0 or relax a threshold.
P2 would require reviewing both alpha_v and alpha1*alpha2 plus the newly nonzero
abs(alpha_v-lambda)*chi_v and planner margins. P3 needs scientific justification
for a different disturbance; P4 needs new manuscript/theory review. All are
UNAPPROVED alternatives; none is implemented or automatically selected.

A1 component development GO. P1 BLOCKED. Official A2, A3, Level 1 and publication
NO-GO. The next authorized work is the human disposition described in
[NEXT_THREE_ACTIONS.md](NEXT_THREE_ACTIONS.md), not an A2 launch.
