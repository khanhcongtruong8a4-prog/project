# Combined Panda development status

Development version: 1.2.0. Latest run: `runs/20261031T192052470653Z`.
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
| A2 closed-loop smoke | BLOCKED pending qualified model/source acceptance and approved smoke settings |
| A3 comparative scenarios | NO-GO |
| Level 1 | NO-GO; verified global m1 and all theorem hypotheses remain pending |
| Publication-result claims | NO-GO |

The MuJoCo integration check is a plant-only DOP853 check, not a controller,
observer, safety-filter or control-period refinement test. No A2/shakedown,
A3 comparison, T27, G2.5 or interval certificate was executed. Human signatures
remain pending. M1/Scenario B/refinement documents remain proposals. The
workbook, full framework and decision brief are still required to resolve the
remaining equation-level and frozen-configuration choices.
