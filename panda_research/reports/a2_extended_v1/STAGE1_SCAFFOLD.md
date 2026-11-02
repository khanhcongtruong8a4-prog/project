# Stage 1 scaffold — development implementation, official solve HOLD

Status: **SOURCE VERIFIED against the unchanged runtime/manuscript mapping;
EXECUTED LOCALLY as development unit tests; not an independently accepted
planner and not an A3 comparison.** Human signature fields remain blank.

The new module is `src/panda_closed_loop/stage1_scaffold.py`. Existing Gaz source
bytes, `src/panda_dynamics.py`, policy documents, manuscript `.tex`, workbook,
controllers and original A2 evidence are unchanged.

## Implemented components

| Component | Implemented behavior | Practical limit |
| --- | --- | --- |
| `QuinticHermite` | Seven-joint q/qd/qdd boundary interpolation with normalized coefficients | A fixed diagnostic reference, not an optimizer |
| `QuinticBSpline` | Degree five, simple interior knots, six repeated endpoint knots; supplied 12-control-point policy gives 84 coefficients plus free T | No optimized plan has been computed |
| Derivative scaling | q uses normalized basis; qd divides by T; qdd divides by T² | Physical duration constraints are separate residuals |
| `PlanningMargins` | Explicit nonnegative b_u+, b_u−, chi_v, b_h and b_vB with domain/provenance SHA-256 and M1-only mode | Metadata validation is not validation of the supplied bound |
| `ConstantMarginProvider` | Typed development table; synthetic fixtures are marked `SYNTHETIC_TEST_ONLY` | Does not calculate tracking envelopes or dynamic M1 margins |
| Numerical evaluator | Planned inverse dynamics minus initial dhat; physical joint/manipulability h; signed tightened torque and speed rows; HOCBF/velocity CBF rows with original per-row reserves | Sampled residuals only; not continuous-domain feasibility |
| Electrical objective | Shared-bus sum of tau·qd + k_r tau², then one approved phi_epsilon smoothing; Gauss–Legendre quadrature on every nonzero spline span; add w_t T | Modeled electrical energy, not hardware measurement |
| `SymbolicPandaPlant` | Uses the existing AD mass/derivative/gravity/FK graph, frozen friction constants and unchanged geometry graph; differentiable CasADi adapter | Same model algebra, not a second independent model |
| Synthetic NLP graph | f(x), g(x), f-gradient, equality/inequality bounds; measured q/qd start, terminal qd=qdd=0 and three-coordinate FK terminal target, free orientation | Explicit synthetic constant margins only; no optimizer constructed |
| Readiness and solve guard | Structured missing-input/gate list; `solve_official` raises `Stage1NotReady` before any solver creation | Official A3 remains unauthorized and blocked |

The planner expression follows the canonical `eq_tau_p`, `eq_envelopes`,
`eq_beta_bounds`, `eq_margins` and `eq_planner` labels in
`sources/manuscript_v1.2.1/03_contribution.tex`. `source_map()` records their
actual source hashes and line locations. The planned torque has the required
**minus initial dhat** term. The objective smooths once after the joint sum.
The original acceleration-unit HOCBF reserve vector is mapped separately to
the 14 joint rows and the manipulability row; no position reserve is invented.

Each residual sample contains 72 inequalities: 15 physical h rows, 14 signed
torque rows, 14 signed tightened speed rows, 15 HOCBF rows and 14 signed
velocity-CBF rows. Physical joint h rows are an explicit redundant check, not
a new position reserve. Duration adds two inequalities. The start/terminal
constraints have 31 scalar equalities (7 q_start, 7 qd_start, 7 terminal qd,
7 terminal qdd and 3 terminal Cartesian coordinates).

## Executed validation

The initial suite of 13 tests passed and is retained as
`stage1/tests_initial.json` and `stage1/tests_initial.log`. An additional dynamic
graph comparison checks nonzero qd/qdd and the free-duration gradient against a
finite difference of the numerical objective. The final suite/report is
`stage1/tests_dynamic.json` with its full log. No test fixture failed in this
workstream. Test outcomes and exact counts must be read from those reports.

Coverage includes normalized B-spline partition/endpoints, exact linear-curve
free-duration scaling, general Hermite boundaries, 85-variable layout,
immutability/input rejection, shared-bus cancellation and copper losses,
span-wise quadrature, asymmetric margins/reserves, missing-M1 refusal and the
source adapter over all 154 retained model-validation cases. Numerical and
symbolic objectives/residuals are compared. Optimizer construction is mocked to
raise in guard tests, so an unintended optimizer call fails the tests.

These are development checks of the scaffold. They are not solver convergence,
KKT, multistart, grid-refinement, global-bound or planner–filter consistency
results. A static source-model fixture passing sampled inequalities is not
called a Stage 1 solution.

## Reproduce and inspect

From `/workspace/a2-extended/panda_research`:

```bash
/workspace/panda-venv/bin/python tests/test_stage1_scaffold.py --report /tmp/stage1-tests-new.json
/workspace/panda-venv/bin/python scripts/stage1_scaffold_check.py --report /tmp/stage1-readiness-new.json
```

Use new report names; output creation is exclusive. The original source/model
and pinned requirements remain required. No IPOPT/NLP solve, Scenario A/B/C
comparison, cold-start study or optimized objective was executed. The proposed
IPOPT settings are read unchanged from policy; `NLP_version` remains null and
the settings' validation status remains UNTESTED.

## M1 integration and next implementation test

The parallel `a3_qp_bounds.py` API exposes `M1DomainSpec`, `M1BoundRecord` and
`M1BoundBundle`. `Stage1Scaffold.readiness(bundle)` consumes its status. A
supplied record is an asserted numerical bound/provenance selector, never a
certificate. Missing common domains, derivative/inertia/tube bounds and tracking
envelopes cannot be replaced by point inverse values or fabricated zeros.

Before production planning, supply a reviewed common M1 domain and usable
numeric constants, implement/test the acyclic varpi→tracking tube→rho/beta→margin
construction and its symbolic free-T dependence, and validate the actual NLP
derivatives, solver, residual-grid policy, quadrature refinement and equal
10-cold-start protocol. The digital sampling correction also needs theory/
controls interpretation before the continuous theorem is applied to a sampled
plan. No supplied synthetic table or passing A2 smoke test resolves those gates.

Independent controls reviewer signature: null.

Independent theory reviewer signature: null.

Official A3 execution authorization: null.
