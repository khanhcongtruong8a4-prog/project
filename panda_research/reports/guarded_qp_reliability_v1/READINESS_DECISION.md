# IC2AI 2027 A2 readiness decision

| Scope | Decision | Executed evidence |
|---|---|---|
| Frozen A2 | **GO** | Original 7/7 and corrected v4 12/12 cells; all 120 refinement metric checks pass |
| General guarded-QP / active-filter qualification | **NO-GO** | Pointwise solver checks pass; legacy alpha_v=5 E3 active-filter refinement fails 8/24 metric checks |
| T27 numerical regression | **GO, finite tested scope** | Same 39 fixtures pass strict solution/infeasibility classification with separate exact certificates |
| A3 readiness | **NO-GO** | Active-filter refinement limits and incomplete common-domain M1/planner G2.5 evidence |

The solver defect is a sign error in ProxQP 0.7.2's support-function test.
`negative_part` returns min(z,0), but the infeasibility code subtracts its
lower-bound contribution. On the preserved 43-row case this creates a false
Farkas trigger with support -3.31e17. A two-sign local patch solves the same
represented guarded QP in 84 iterations. The original solver fails at 50.
Exact rational KKT checks and a separately initialized SLSQP solve verify the
unique feasible optimum. The SLSQP/exact witness never enters the runtime.
See ROOT_CAUSE.md, native/build_guarded_qp_v1/applied.patch and the full
counterexample JSON.

The patch is frozen before tests at eb31006. The separate 9bed176 extension
classifies an impossible zero-normal inequality exactly without producing a
torque; all other problems call unchanged v1. Its strict 39-fixture rerun
covers 34 feasible optima and 5 exact infeasibility certificates. The earlier
v1 zero-normal MAX_ITER result remains preserved. The actual 23 motion cells
use the v1 sign correction; the v1.1 classifier is separately qualified.

All model parameters, Slotine–Li gains, AB2 digital controller, observer,
HOCBF rows, guard values, references, schedules and acceptance thresholds are
unchanged. Every actual endpoint QP and every completed trajectory is audited.
All 2,262 pre-task files retain their original SHA-256, including earlier
failed experiments. The original seven full scientific traces match exactly.
The corrected v4 prehold traces also match exactly; its motion comparisons
use the tolerances declared before testing. The largest physical torque
difference from the original v4 evidence is 3.91e-14 Nm. Full corrected traces
are not described as bit-identical to traces from a different solver binary.

Across v4, maximum actual terminal error is 0.525345 mm, minimum normalized
raw slack is 0.660765, and maximum scaled stationarity is 5.00e-16. All selected
A2 refinements pass, including both diagonal comparisons. No negative raw
slack is accepted and no failed, unverified or timed-out torque is actuated.

The extra four alpha_v=5 E3 cells all complete and pass their raw-row/KKT
trajectory audits. Their h-only refinements pass. Delta/diagonal energy
errors reach 4.19669e-4 J (allowed about 1.17286e-4 J), and peak-intervention
errors reach 1.51027e-3 Nm (allowed about 1.30721e-5 Nm). These eight failures
reproduce the earlier limitation after the solver correction. They are not
silently counted as v4 success. ALL_REFINEMENTS.csv lists every exact value
and required tolerance; NUMERICAL_CELLS.csv lists all 23 cells.

The exact remedy for broader acceptance is to satisfy every listed failing
comparison under those original criteria and separately complete/provenance
check the M1 bundle and both G2.5 screens. This task identified no further
validated solver-only correction that would remove the active-filter Delta
sensitivity. The framework is preserved; no controller/observer/barrier
redesign or parameter/tolerance change is presented as a remedy already proven.

ACCEPTANCE_DECISIONS.json is the versioned numerical policy, with scoped
claims, source freeze IDs and evidence hashes. The aggregate 23-cell process
returns exit 3 because the separate active-filter campaign fails; the selected
19-cell A2 decision is GO. Treating that aggregate exit as universal success
would erase a real failure.

Verification is automated local work on this same host. User consultation
and authorization are not independent verification signatures; those fields
remain blank. No Level 1 certification or official A3 comparison is claimed.
The newly mentioned detailed prompt and REVIEW (1).zip were not mounted; the
visible instructions and preserved repository evidence define this work.

The complete ZIP includes exact recoverable source/history/trajectory bytes.
The small QP_REPRODUCTION.zip independently reruns the 39 solver fixtures and
includes source and reports, while omitting the large raw-motion archive.
RUN_REMEDIATION.py --verify-only restores and verifies the complete package;
--qp-only reruns strict T27 without restoring raw traces; --run executes the
original seven, v4 twelve and separate active-filter four with fresh outputs.
