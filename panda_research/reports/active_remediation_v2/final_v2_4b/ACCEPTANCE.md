# A2 polynomial-hold remediation v2.4b acceptance

**GO for the complete requested numerical A2 campaign.**

| Scope | Result |
|---|---|
| New active candidate closed-loop cells | 8/8 complete and independently audited |
| New refinement fields, including both diagonals | 48/48 PASS |
| T27 finite exact-oracle fixtures | 39/39 PASS (34 feasible, 5 infeasible) |
| Original A2 and A2-Extended regressions | 7 + 12 cells PASS |
| Original and extended refinement fields | 120/120 PASS |
| New mathematical, GL-audit and roundoff contracts | 9 + 3 + 3 PASS |
| Frozen regression mathematical contracts | 50 PASS |

The checkpoint f9278f2 was not recovered. Source was reconstructed additively from published 4e6335d. All 3,012 files at that base were checked byte for byte and are unchanged; dynamics, gains, disturbances, guards, original thresholds and historical failures remain preserved. Runtime source v2.4 and the separately versioned v2.4a/v2.4b verification corrections are included. No stored exact witness is used as a runtime fallback.

The raw result/log verdicts from the erroneous bitwise implicit-stage assertion remain unchanged. AUDIT_V2_4A.json independently verifies the identical actual polynomial torque and complete plant/DOB/power stage equations at the already frozen 1e-13 criterion. The first aggregation also remains preserved: all 48 refinements passed, but a logging identity failed by one ULP on a large positive slack. V2.4b uses a derived floating-point roundoff bound solely for that identity; every strict raw sign and 1e-9 KKT/feasibility target is retained. See the versioned audit policies and negative-control tests.

The authoritative machine-readable decisions are in ACCEPTANCE.json. Earlier failed prototype versions and the freshly reproduced legacy active-AB2 refinement failure remain failures; no history was rewritten.

## Separate limits

- Finite-grid constraints, sampled trajectories, collocation extrema and numerical KKT tolerances are not certified bounds on the true ODE trajectory.
- Hardware real-time deadlines are not qualified by this offline simulation.
- Certified global bounds and independent reviewer signatures are not invented.
- No official A3 comparison was performed. A3 and Level 1 remain NO-GO.

## Reproduction

Use the root README_A2_POLYNOMIAL_REMEDIATION.md and RUN_A2_POLYNOMIAL_REPRODUCTION.py. The default full run creates fresh evidence for all 39 T27 fixtures, 19 frozen regressions, eight new candidate cells and every refinement; it never substitutes archived passes. VERIFY_A2_POLYNOMIAL_PACKAGE.py checks exact delivered bytes.
