# T27 development status

Status: **PARTIAL — official gate OPEN**.

Executed locally: 18 read-only QP fixtures using unchanged ProxQP 0.7.2 settings. Coverage includes inactive and torque-active boxes, two coupled active constraints with an analytic KKT optimum, redundant active faces, matched row rescaling over a 2^40 span, contradictory halfspaces, an impossible physical torque demand, the original infeasible 43-row midpoint, four actual r4 post-prehold matrices, a constructed active face of an actual 43-row matrix, float32-input quantization with a float64 solver, and identical-matrix consistency under the four schedule labels.

An independent SciPy HiGHS LP cross-checks linear feasibility. It is numerical evidence, not a certificate. Schedule-label solves do not integrate the plant or establish sampled-data consistency; A2 has that separate test.

Analytic-oracle/KKT failures: `[]`. All expected infeasibility checks agree: `True`. Strict raw-sign rejection/boundary-sign failures: `['box_torque_active', 'coupled_two_active', 'coupled_rescaled_2pow40_span', 'redundant_active_faces', 'Panda_actual_43_single_active_face']`. These cases retain raw negative values. Numerical KKT acceptance is separate from nonnegative-raw-row acceptance. No candidate is actuated. No threshold or expected value is retuned.

Unresolved solver calls: `[]`. Each read-only diagnostic has a predeclared 15 s subprocess wall budget (including worker startup); a TIMEOUT is UNKNOWN, never mathematical infeasibility. An earlier uncapped attempt exceeded three minutes and was interrupted; its start record and source snapshot remain in run_v1/INTERRUPTION.json. This is an instrumentation correction, not a physics/control/solver-tolerance change.

Source is inspected and fixtures EXECUTED LOCALLY; there is no independently signed T27 completion. The full frozen task/domain/conditioning stress protocol, robust treatment of near-boundary signs, real-time qualification and independent reviewer disposition remain outstanding. Official T27 is not cleared by a fixture count.

Evidence: `reports/a2_extended_v1/qp_bounds_evidence/run_v2/t27_fixtures.json`; exact command, source hashes, environment and policy settings are in run_started.json. Human signatures: null.

## Retained negative raw rows

All five cases below meet the unchanged normalized KKT/oracle tolerances but fail exact raw sign acceptance. These are analysis candidates only. The A2 strict application wrapper would reject any negative raw row before torque application; these fixtures do not invalidate an earlier trajectory whose raw rows were all positive.

| Fixture | Negative raw minimum | Negative rows |
| --- | --- | --- |
| box_torque_active | -3.85483645005e-10 | box_upper_1 |
| coupled_two_active | -3.69593244898e-13 | synthetic_0, synthetic_1 |
| coupled_rescaled_2pow40_span | -2.58500222117e-07 | synthetic_0, synthetic_1 |
| redundant_active_faces | -1.1228129945e-10 | synthetic_0, synthetic_1 |
| Panda_actual_43_single_active_face | -1.30491173422e-11 | v_lower_3 |

Full per-fixture table: `qp_bounds_evidence/run_v2/T27_FIXTURE_SUMMARY.csv`. Final 15 API/solver contracts passed; reports/logs for earlier 13-test runs are also retained.
