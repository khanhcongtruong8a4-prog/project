# Execution readiness after policy approval

**Authority:** Project-owner approval of source/model evidence and study policy, 2026-11-01. No simulation conducted during this update.

| Stage | Decision | Still required |
|---|---|---|
| A1 implementation | GO | Continue building tests and closed-loop modules |
| A2 smoke test | HOLD | Implement/test observer + Slotine–Li + QP + RK4; register held-torque and observer update semantics; define complete M1 domains/constants; satisfy reviewer sign-off rules where required |
| A3 Level 2 comparisons | NO-GO | A2 pass, T27 solver validation, G2.5 feasibility, task suite frozen, experiment manifest/solver versions locked |
| Level 1 certificate | NO-GO | Verified m1 and all interval/tube/trajectory bounds; all-time theorem assumptions |
| Section IV publication | NO-GO | Verified experiment evidence and independently reviewed reporting |

## Shortest next implementation assignments

1. **Codex:** integrate closed-loop DOB, Slotine–Li, robust QP, RK4, and a raw-C reference regression under the approved baseline. Produce tests and a ready-to-run A2 command, but do not label a pipeline shakedown as accepted A2 evidence.
2. **Controls/theory:** enumerate the M1 constants/domains and T23 candidate-wise maximum computation in a machine-checkable equation registry, with source hashes, units, and sampling/verification method.
3. **Experimental lead:** finish T22/T29 task and metric freeze; predeclare exact solver versions and budgets; after independent review, proceed A2 → T27/G2.5 → A3 in this order.

**No unsupplied numerical bounds or experiment success claims have been invented.**
