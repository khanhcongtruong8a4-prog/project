# A2 entry checklist — r2, DRAFT / OWNER APPROVAL PENDING

A1 GO; frozen P1 FAIL; verified startup NOT APPROVED; official A2/A3/Level 1/publication NO-GO.

| Item | Status | Meaning |
| --- | --- | --- |
| policy_v122_approval | AWAITING HUMAN REVIEW | DRAFT / OWNER APPROVAL PENDING; not a signed revision |
| reference_fields | PASS | Formula/initial/endpoint/duration/accuracy are proposed, not approved |
| planner_only_M1_inputs | PASS | Not used by a non-optimized smoke reference; remain OPEN for A3/G2.5 |
| reference_initial_state_measured | NOT TESTED | No valid completed prehold endpoint; abort states cannot replace q(0),qd(0) |
| reference_owner_controls_decision | AWAITING HUMAN REVIEW | Reference choice and new measured-endpoint start rule require approval |
| P1_sampled_pair_screen | PASS | Numerical predeclared nodes only; no continuous-box enclosure |
| P1_complete_point_QP | PASS | Fixed midpoint/zero-velocity estimate fixtures; not physical prehold endpoints |
| physical_prehold_dynamics | FAIL | Applied-torque model prehold checked; frozen acceptance failed |
| hold_tracking_torque_end_conditions | FAIL | No tolerance relaxation or post-failure duration change; require a valid zero-time endpoint |
| signed_physical_prehold_clock | PASS | Signed adapter continuity and applied-torque contracts have engineering unit evidence; policy approval remains separate |
| continuous_true_ODE_neighborhood | NOT TESTED | Cubic numerical interpolation is not an ODE error enclosure; observed violations already reject this candidate |
| actual_zero_endpoint_full_QP | NOT TESTED | Only a completed valid t=0 endpoint can satisfy this gate; stopped states do not qualify |
| prehold_failure_disposition | AWAITING HUMAN REVIEW | Theory/controls and owner must explicitly redesign/redeclare a candidate or choose an alternative; no automatic retuning |
| prehold_owner_theory_controls_decision | AWAITING HUMAN REVIEW | P1 is the explored proposal, not an approved startup change |
| C4_grid | PASS | Later approved C4 includes (Delta=.5ms,h=.25ms), m=2; supersedes old h=Delta/4 default |
| observer_method_fields | PASS | Coupled-continuous RK4 and separate sampled sensitivity are explicitly proposed |
| sampled_observer_sensitivity_definition | PASS | Sampled sensitivity must declare update, cadence, held-state rule and acceptance before execution |
| observer_execution_approval | AWAITING HUMAN REVIEW | No physical sampled-observer bound inferred |
| infeasibility_semantics | PASS | Proposed A2 FAIL / development NO-ADVANCE request; not safe hardware zero torque; no unapproved Kb/gamma |
| infeasibility_policy_approval | AWAITING HUMAN REVIEW | Owner/controls must approve the proposed stop semantics |
| acceptance_metric_definitions | PASS | Physical, observer, QP, refinement and terminal criteria must all be explicit; approvals are separate |
| approved_acceptance_thresholds_preserved | PASS | Draft retains the approved v1.2.1 numerical thresholds |
| v121_parameters_preserved | PASS | Unchanged baseline fields: gains/disturbance/reserves/energy/solver/M1 |
| reference_numeric_fields | PASS | Duration, seven offsets and terminal tolerance must be finite and correctly shaped |
| full_A2_refinement | NOT TESTED | No official A2 or actual 2x2 closed-loop run executed |
| independent_clean_environment_rerun | AWAITING HUMAN REVIEW | Controls reviewer must rerun scripts/action3.py validate; engineering reruns are not that signature |
| manuscript_build_revision | AWAITING HUMAN REVIEW | 02/03 equation hashes match; main.tex and Project.rar discrepancies need responsible confirmation |
| controls_reviewer_signature | AWAITING HUMAN REVIEW | No signature or written execution authority generated/inferred |
| theory_reviewer_signature | AWAITING HUMAN REVIEW | No signature or written execution authority generated/inferred |
| written_A2_authorization | AWAITING HUMAN REVIEW | No signature or written execution authority generated/inferred |

Evidence: [actual torque hold](evidence/prehold/summary.json), [contract tests](evidence/signed_clock_and_hold_tests.json), [policy](../../policy/v1.2.2-r2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2_r2.json). A passing technical check never supplies a human signature.
