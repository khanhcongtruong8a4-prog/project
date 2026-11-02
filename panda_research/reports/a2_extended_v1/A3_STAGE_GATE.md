# A3 stage gate — preparation only, NO-GO

**Official A3 Scenario A/B/C comparisons are not authorized or executed.**
The attached task authorizes development scaffolding and A2-Extended numerical
experiments. It does not authorize final planner comparisons, independent
signatures, Level 1 certification or publication statements.

This gate separates the implementation status from the evidence/approval
needed to begin a later study. A2-Extended outcomes and the clean-checkout
baseline reproduction must be taken from their actual final reports; the
scaffold does not predeclare their success or turn them into human acceptance.

| Gate | Current status and evidence owner | Required artifact/pass criterion |
| --- | --- | --- |
| Existing narrow numerical A2 | Baseline r4 reports GO; fresh reproduction is a separate workstream | Inspect/reproduce the exact seven cells with full raw traces and unchanged inputs; retain scientific and engineering failures |
| Independent A2 acceptance | NOT DOCUMENTED; controls reviewer | Real signed acceptance of source, initialization, numerical definitions and reproduced raw evidence; no self-issued signature |
| A2-Extended E1/E2/E3 | Pending the executed suite report; controls/numerical lead | Frozen three-case definitions, all mandatory C4 cells, raw audits and unchanged two-axis/diagonal criteria; report PASS/PARTIAL/FAIL honestly |
| Digital sampler interpretation | OPEN; theory and controls reviewers | Written decision on r4 u=r+0.5Δr realization and the separate u−r, tau−u and tau−r measurements; identify the scope of continuous-time claims |
| T27 | Development fixtures in parallel workstream; official acceptance OPEN | Accepted active-set/feasibility/scaling/precision coverage with representative HOCBF matrices and recorded solver residuals |
| Positive G2.5 | OPEN; numerical/theory lead | Deterministic filter and planner checks including factor-two tightening; a necessary point screen alone cannot clear the planner gate |
| Usable M1 domain and margins | INCOMPLETE; theory/numerical lead | Frozen common q/qd/qdd/tube domains; traceable non-fabricated inertia/inverse/derivative/barrier bounds and full tracking/residual envelope construction |
| Stage 1 structure | Implemented and unit-tested DEVELOPMENT scaffold | Numerical/symbolic free-time objective and residuals tested, but a real dynamic M1 symbolic provider and production solve are still absent |
| Stage 1 solver validation | NOT EXECUTED; optimization/numerical lead | Source-aligned real margins; checked derivatives, KKT/feasibility, NLP version/settings/budget/warm starts, quadrature/grid refinement and failing-case handling |
| T22 scenario A task | Not frozen as an executable task | Complete task selection, target, feasibility/terminal rules and exact plan/configuration hashes before optimization comparisons |
| Scenario B method-independent suite | Proposed suite/source bytes retained, no comparison run | Reviewed common target manifest, matched tasks and objective/failure aggregation, shared seeds before either method runs |
| Equal initialization protocol | Not executable/frozen | Ten common cold starts for all compared methods, explicit stored starts/seeds; supplemental three cross seeds labeled separately |
| Complete comparison manifest | Missing; owner and responsible reviewers | Signed and hashed final common model/domain/margin/task/solver/budget/settings manifest, no post-result selection |
| Official A3 authority | NOT GRANTED in this task | Explicit later written authority after prerequisite evidence and human decisions are actually present |
| Level 1 certification | NO-GO | Verified continuous-domain bounds, all theorem assumptions and numerical/sampled implementation justification; sampled passes do not provide this |

## Executable inspection

```bash
cd /workspace/a2-extended/panda_research
/workspace/panda-venv/bin/python scripts/stage1_scaffold_check.py --report /tmp/a3-stage1-readiness-new.json
```

The inspection records the canonical equation hashes, missing M1 quantities,
policy's unchanged solver proposals and explicit blockers. It constructs no
optimizer. `Stage1Scaffold.solve_official()` fails closed even when supplied
synthetic test margins exist. The whole A3 gate cannot be cleared by changing a
printed label, by owner acceptance alone, or by a successful nonoptimized A2
tracking trajectory.

No manuscript, primary Gaz source, workbook or signed policy was rewritten.
There is no new theorem, optimized plan, comparative result or publication
claim from this preparation work.

Independent controls signature: null.

Independent theory signature: null.

Build-revision acceptance: null.

Written A3 comparison authority: null.
