# A2-Extended v4 — explicit velocity-barrier CONTROL-gain amendment

This is a new user-authorized numerical controller-policy design. All earlier
outcomes remain intact: v1 had protective QP stops; v2 and v3 completed all
individual cells but E3 failed refinement. Neither failed suite is called GO.
The original r4 narrow numerical GO and original source/policy bytes are
unchanged. The user authorized simulation development and versioned policy
changes, then explicitly requested all fixed E1/E2/E3 cells and refinement
checks to pass. That authority is recorded verbatim, without an invented
independent reviewer identity/signature.

The ONE new physical-control design value is velocity-CBF alpha_v: 5 to
10 s^-1, by a fixed factor of two. Alpha_v is a positive barrier feedback
gain, not a Gaz inertia/friction/dynamics parameter, physical speed/position/
torque/manipulability limit, observer bound or numerical pass tolerance.
Slotine-Li Lambda/kappa, observer Ko, position/manipulability alpha1/alpha2,
startup gains, model and all other policy values remain unchanged. The new
configuration changes only alpha_v and its honest schema/status metadata.

The robust speed rows remain exactly the same equations:
  +/- M^-1(tau+bias)+alpha_v*(vmax-/+qd)-abs(M^-1)*varpi >=0.
Doubling alpha_v expands instantaneous allowable robust acceleration inside
the same speed limits. This IS a different filter design; we do not claim
the alpha_v=5 inequalities or their approved-policy bytes are unchanged.
The v4 source adapter first loads/verifies the immutable original policy,
then admits only the declared gain/schema/status delta from a new file.
Original source_audit establishes the original model/policy provenance, not
independent acceptance of the new gain. New authority/hashes are separate.

Rationale: the original observer envelope plus alpha_v=5 made the fast E3
reference invoke the filter. v2's active instantaneous filter exposed
first-order period error. v3 interval-row sampling reduced energy error but
introduced period-dependent current-row minima and did not clear intervention
refinement. A positive speed-barrier gain is an ordinary design degree of
freedom. The factor-two rule provides acceleration headroom for the FIXED
reference without changing its amplitude, signs, duration, waypoint, initial
state construction or terminal tolerance. It is selected and frozen before
v4 motion, as a single common value for every cell/case. No further v4 gain
selection is permitted after results.

v4 uses the numerically qualified v2 CURRENT-STATE 43-row hard QP with its
1e-8 inward roundoff guard, isotropic scaling and tight solver targets.
There is NO v3 row extrapolation or extra 0.1 reserve. The original nominal
AB2 sampler, P1 transfer, actual observer/global clock, held torque, coupled
RK4 and energy model are unchanged. One cold query per scheduled update;
no retry, fallback, clipping or post-solve modification. The actual initial
full QP uses the actual endpoint and is reused for first actuation.

Every actual v4 raw row must be nonnegative; T29 primal/stationarity targets
stay 1e-9; all original physical/envelope/terminal checks and all six
refinement pairs stay unchanged. All twelve full motion cells are required.
Both dual scalings support read-only actual-QP KKT reconstruction. A separate
gain audit verifies identical G, unchanged nonvelocity c, and exactly the
declared speed-row c change. It explicitly retains all OLD alpha_v=5 shadow
negative slacks on v4 states/torques. Those are not concealed or mislabeled
as satisfied original-policy constraints; they are not actual v4 violations.

Ten pre-motion contracts passed. All 6000 retained v2 E3 states/nominal
requests were read-only screened under the fixed v4 gain, with positive
normalized raw minima above 0.693 and full actual QPs at each cell's worst
point. This is development evidence on OLD states, not v4 motion, optimized
reference selection, a future-state control signal or new M1 constants.
Its complete screen records are retained. The implementation, new policy,
tests, hashes and all prior motion evidence are committed before v4 motion.

The numerical result is scoped to this explicit amended filter and fixed
suite. It does not establish a sampled-data theorem, between-sample true-ODE
certification, hardware safety, positive full planner G2.5, usable M1 bounds,
official T27 completion, an A3 solve or publication interpretation. Independent
theory/controls decisions for the new design remain attributable only to
real supplied artifacts. No manuscript, workbook or original source is edited.
