# Independent P1 review remediation — r2

**The frozen P1 candidate FAILS its declared development hold tolerance.**
A1 component development remains GO. P1 as verified startup is NOT APPROVED;
official A2, A3, Level 1 and publication remain NO-GO.

The review's accepted analytical screen is preserved. Its 0.156 s settling
duration and 129 midpoint QP results do not imply a viable torque hold.
The current user request authorizes engineering remediation; no owner/theory/
controls startup selection, policy signature or official A2 authority is inferred.

## Applied-torque development result

Before the first Panda prehold integration, the new test plan froze the old
duration, gains, waveform, tolerances and all four C4 cells. The controller is
the existing Slotine–Li static-midpoint law, torque-box projected only during
preparation. The plant and DOB receive the same actual held torque. The plant
uses the original negative physical disturbance time. There is no ideal clamp,
reaction torque, injected-truth controller input, observer reset or retry.

All four cells stop at physical time -0.15475 s: elapsed 0.00125 s after starting
at -0.156 s. Actual endpoint speeds already exceed the 0.02 rad/s limit:

| Cell | Delta ms | h ms | abs(qd3) rad/s | abs(qd7) rad/s | Abort physical time s | Hold / actual-state QP |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 0.25 | 0.020561709623 | 0.020236936418 | -0.15475000 | FAIL / PRIMAL_INFEASIBLE |
| 1 | 1 | 0.125 | 0.020561709591 | 0.020236941296 | -0.15475000 | FAIL / PRIMAL_INFEASIBLE |
| 2 | 0.5 | 0.25 | 0.020657415434 | 0.021310718429 | -0.15475000 | FAIL / PRIMAL_INFEASIBLE |
| 3 | 0.5 | 0.125 | 0.020657415397 | 0.021310723851 | -0.15475000 | FAIL / PRIMAL_INFEASIBLE |

These are measured simulated abort states, not q(0) or an ideal midpoint fixture.
Their correctly propagated envelope has only 1.25 ms elapsed, not 0.156 s.
The full 43-row QP is PRIMAL_INFEASIBLE in each case. No candidate QP torque is
applied and no post-hold motion/reference execution occurs. There is no valid
zero-time endpoint and no successful P1 procedure to approve under these settings.
Do not extend the duration, enlarge tolerance or increase gains retrospectively.

Every attempted RK4 substep also checks all extrema of its cubic continuous
extension, retained RK4 stages and endpoints. This covers the numerical cubic's
components; it is not a verified error enclosure for the true ODE. The actual
violating endpoints are sufficient to reject the development candidate without
claiming a continuous-state invariance proof or a verified neighborhood.

## Findings and disposition

| Review item | Disposition | Evidence / remaining work |
| --- | --- | --- |
| Blocker 1: missing applied-torque hold | TESTED — FROZEN CANDIDATE REJECTED | All four model cells fail the unchanged speed tolerance after 1.25 ms; [summary](evidence/prehold/summary.json). A different startup needs a new human decision. |
| Blocker 2: signed execution clock | RESOLVED FOR DEVELOPMENT | Signed adapter, unchanged applied torque, no phase/observer reset, transfer guards and continuity tests implemented; [tests](evidence/signed_clock_and_hold_tests.json). Policy approval is separate. |
| Blocker 3: continuous neighborhood / measured endpoint | PARTIAL, NOT CERTIFIED | Continuous cubic extrema and actual sampled abort states checked. The candidate has a counterexample; no completed zero endpoint or true-ODE neighborhood proof is claimed. |
| Blocker 4: QP only at midpoint | PARTIAL | Complete 43-row QPs evaluated at actual nonzero-speed abort states with actual elapsed bounds; all infeasible. Successful post-hold/A2 execution cannot follow this failed hold. |
| Blocker 5: draft/human/build/reproduction gates | BLOCKED ON HUMAN DECISIONS | New r2 draft and checklist supplied; all human fields remain null. Fresh-environment engineering reproduction is recorded separately and is not independent reviewer signoff. |
| Blocker 6: planner M1 / observer floor | BLOCKED, KEPT SEPARATE | M1 remains absent and factor-two lower speed witness still fails joints 1,3 at the floor. No bound or planner success is fabricated. |
| F1 | PARTIAL | Frozen physical-model test is now performed and fails; leads/owner must select and predeclare a revised startup or alternative. |
| F2 | PARTIAL | Actual-state QP diagnostics added, definitions/C4 retained; failed hold provides no valid endpoint for finalizing execution. |
| F3 | BLOCKED ON INDEPENDENT REVIEW | Supply clean engineering checks and build hashes; genuine controls/theory signatures, build confirmation and written A2 authority must come from responsible humans. |

Implementation: `src/panda_closed_loop/preparation.py:16`, `src/panda_closed_loop/preparation.py:95`, `src/panda_closed_loop/preparation.py:184`.
The previous analytical proposal and accepted source/evidence bytes remain unchanged.
