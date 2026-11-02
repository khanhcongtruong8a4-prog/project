# G2.5 screen report

Status: **INCOMPLETE — planner M1 missing; no official positive G2.5**.

Executed locally: 20 deterministic read-only points. Filter point passes: 15; filter point failures: 3; unresolved points: 2. Inputs are the approved initial midpoint, actual measured r4 endpoints at cells 0/2/3/6, fourteen one-joint +/-10%-range offsets, and an explicitly labeled asymptotic observer-floor point. Offset/floor fixtures are not manufactured plant endpoints. A QP diagnostic timeout is not called infeasibility.

Each point logs necessary paired speed/position inequalities, physical h/psi1 and speed/manipulability conditions, full 43-row ProxQP and separate LP classifications including torque/manipulability rows, and raw negatives. Bounds are the original initial bound, correctly propagated 0.156 s envelope, or its explicitly labeled analytic floor. No phase or gain changes occur.

Planner factor-two lower witnesses use |M(q)^-1| only as a LOWER witness for a containing common domain, never as an M1 upper bound. Omitted nonnegative margins can only make planning harder; the witness cannot establish feasibility. The actual planner-pair API refuses missing Nbar/separate Abar inputs and returns BLOCKED_MISSING_M1_BOUNDS. Filter-point passes cannot clear the planner G2.5 gate.

Node selection is fixed by code before screening; no plant/trajectory is advanced. Status is EXECUTED LOCALLY for these sampled points, not independently accepted, not full-grid/global feasibility and not an official G2.5 campaign or A3 comparison. Usable common-domain M1 and a frozen complete screen protocol remain needed.

Evidence: `reports/a2_extended_v1/qp_bounds_evidence/run_v2/g25_screens.json`. Human signatures: null.

## Specific unresolved points and lower witness

The joint-5 +/-10%-range offsets reach the 15-second ProxQP diagnostic limit. HiGHS separately classifies both linear constraint sets numerically feasible, but its candidate raw minima are about -1.78e-13 and -1.39e-13. Neither solver result establishes a strict admissible applied torque at those points. These two points remain INCOMPLETE, not infeasible and not accepted.

At the midpoint analytic observer floor, the factor-two planner LOWER witness fails velocity joints 1 and 3, with raw slacks -2.19068295399 and -2.47221167774 rad/s². This rules out that necessary inequality for any valid common bound whose domain contains this point; it is not a global impossibility theorem for all poses or a computed M1 upper bound. Additional planner margin terms cannot repair a failed lower witness. No gain, disturbance or theory amendment is selected here.

Point table: `qp_bounds_evidence/run_v2/G2_5_POINT_SUMMARY.csv`.
