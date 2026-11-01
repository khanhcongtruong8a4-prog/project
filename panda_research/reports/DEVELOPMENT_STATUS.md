# Combined Panda development status

Dynamics baseline: 1.2.0; Action 3 extension: 1.2.1. Latest model run: `runs/20261101T153805083504Z`.
Result: **PASS_MODEL_VALIDATION_ONLY**.
Runtime code SHA256: `9a0f100459c93f59ba75133fc682f111505909627de3bf29bb0bf823b64f025d`.

This combines the newer normalized/validated numerical API and MuJoCo suite
with pinned primary-source checks, the exact protocol cases, independent
Pinocchio validation, provenance and protocol proposals from the remediation.

- Original historical suite: 19/19 reproduced internal checks.
- Current suite: 19 internal checks PASS; full-limit friction grid and sampled eigenvalue extrema reported.
- Pinocchio: 154 state cases, 4158 quantity/pose comparisons PASS.
- MuJoCo: 154 identical state cases, 58 check groups PASS, including API regressions and plant-only work-energy integration.
- Primary-source checks: 70 inertial + 21 friction values and eight joint/frame rows PASS; unsigned sheets retained in the run.
- Five isolated model-error injections detected. Selected constants and CasADi model-construction AST unchanged; flat-vector outputs exactly preserved over 154 cases.
- Protected source, inputs, historical evidence, protocol proposals and human-review records unchanged during validation.

Both engines use the same 132 expanded states plus the original 22 protocol states.
The differing test/group counts are not counts of independent experiments.

## Research gates

| Gate | Current state |
| --- | --- |
| A1 implementation | GO |
| A2 closed-loop smoke | HOLD; see v1.2.1 policy and Action 3 report for current blockers |
| A3 comparative scenarios | NO-GO |
| Level 1 | NO-GO; verified global m1 and all theorem hypotheses remain pending |
| Publication-result claims | NO-GO |

The MuJoCo integration check is a plant-only DOP853 check, not a controller,
observer, safety-filter or control-period refinement test. This runner validates
the preserved numerical model only; Action 3 component results are separate in
reports/ACTION3_REVIEW_HANDOFF.md. No official A2, A3 comparison, complete T27,
G2.5 or interval certificate is claimed. Supplied v1.2.1 owner policy now governs
gains/C1-C6 and includes the task workbook; it does not fill missing M1 bounds,
approve the observer discretization or manufacture independent signatures.
