# ZIP versus reviewer: remediation result

Prepared 1 November 2026. Original ZIP, model manifest, Protocol v1.0 and historical results are preserved byte-for-byte. No GitHub push was made.

The reviewer correctly identified the difference between internal consistency and external model validation. The technical defects below were corrected without changing the evaluator's executable AST, physical model, original test tolerances or experiment thresholds. Human acceptance and protocol decisions remain pending.

## Executed evidence

- Original suite: **19/19 PASS**, reproduced from unmodified copied code; historical outcomes agree. Internal tests only.
- Corrected suite: **19/19 PASS** with accurate descriptions, a calculated maximum eigenvalue and a full-limit friction grid.
- Primary source bytes: pinned Gaz and franka_ros Git commit/tree/blob identities checked; SHA256 recorded. The supplement hash matches v1.0.
- Source comparisons: **70 inertial + 21 friction values and 8 joint/frame rows PASS**. c1z remains author-code zero versus table asterisk; no mixed ROS inertials.
- External reference: **22 original q/qd/qdd cases, 594 quantity/pose comparisons PASS**, using Pinocchio 3.8.0 and independently parsed Gaz/Xacro data. These are 27 quantity groups per pose, not 594 independent robots or experiments.
- All five isolated mass/COM/inertia-sign/frame/gravity error injections were detected by the external comparison.
- Sampled joint-space eigenvalues span 0.00353490904589553 to 3.67369536401921 kg m^2 across the test poses. These are not global certified bounds.

| External quantity | Maximum absolute difference | Units |
| --- | ---: | --- |
| AD_flange_translation | 2.22045e-16 | m |
| M | 8.88178e-16 | kg m^2 |
| g | 1.42109e-14 | N m |
| Cqd | 1.05471e-14 | N m |
| ID_friction_on | 2.13163e-14 | N m |

Full per-component reference/target values, failures (none) and elementwise abs+relative tolerance ratios are in external_dynamics.json/CSV. Rotation maximum error is 6.245e-16.

## Reviewer disposition

| ID | Issue | Status |
| --- | --- | --- |
| R01 | No external dynamics reference | CLOSED TECHNICAL; HUMAN ACCEPTANCE PENDING |
| R02 | T04b primary source/signature missing | PARTIALLY RESOLVED |
| R03 | T06a primary Xacro/signature missing | PARTIALLY RESOLVED |
| R04 | Margin mode and NLP coupling unspecified | PARTIALLY RESOLVED |
| R05 | Misleading test notes/internal identities | CLOSED IN WORKING COPIES |
| R06 | Scenario B selection bias safeguard | PARTIALLY RESOLVED |
| R07 | Control-period refinement missing | PARTIALLY RESOLVED |
| R08 | 19/19 only historical/log-reported | CLOSED: REPRODUCED INTERNAL CHECKS |
| R09 | Maximum sampled eigenvalue hard-coded null | CLOSED |
| R10 | Friction grid below declared joint speeds | CLOSED |
| R11 | Manuscript alpha_v/comma corrections | OPEN / OUT OF SCOPE |
| R12 | Unsigned protocol and experiment freeze | OPEN |

See reviewer_issue_disposition.csv for evidence paths and the exact remaining work. Historical misleading notes remain only in clearly identified immutable baseline/run-copy records. Corrected executable tests are in src/.

## Protocol work

A separate R1 addendum proposes M1 with frozen common constants, candidate-aware margin evaluation inside the NLP, matching constant-envelope treatment, a method-independent Scenario B suite, and integrator plus control-period refinement. The 64 proposed targets were generated without running a planner or baseline. No proposal is marked approved.

The workbook, full mathematical framework, decision brief and optional manuscript are missing. The addendum defines the dependency/entry policy; exact equation-level NLP/envelope mapping and constants cannot be completed from the supplied package alone. Nulls and owners are listed in the proposed configuration and unresolved-decision register.

## Gates and smallest next step

| Gate | Current decision |
| --- | --- |
| A1 implementation | GO |
| A2 closed-loop smoke | CONDITIONAL GO; CURRENTLY BLOCKED |
| A3 numerical Scenarios A/B/C | NO-GO |
| Level 1 | NO-GO |
| Publication-result evidence | NO-GO |

**Smallest next step:** a qualified human reviews the source/frame and external dynamics evidence and signs or rejects the acceptance sheets. In parallel, supply the missing framework/registry and resolve the listed smoke-test settings. A2 can be proposed after those prerequisites; no closed-loop or comparative run is approved by this package.

No A2/shakedown, A3 comparison, T27, G2.5 or interval-certification run was performed. The unrelated earlier PyBullet grasp demo is excluded from research evidence. Do not call this completed Phase-3a acceptance, approved Protocol v1.1, a Level-1 certificate or paper-ready simulation evidence.
