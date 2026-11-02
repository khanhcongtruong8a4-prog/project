# A2 entry checklist — DRAFT / OWNER APPROVAL PENDING

A1 GO; P1 BLOCKED; official A2 NO-GO; A3, Level 1 and publication NO-GO.

PASS applies only to the named field or retained static fixture. It is not an execution authorization. Evidence: [static screen](evidence/static_screen/screen.json), [draft policy](../../policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json), [engineering verification](evidence/verification/verification.json), [P1 memo](P1_FEASIBILITY_MEMORANDUM.md).

| Item | Status | Evidence / remaining work |
| --- | --- | --- |
| policy_v122_approval | AWAITING HUMAN REVIEW | DRAFT / OWNER APPROVAL PENDING; not a signed revision |
| reference_fields | PASS | Formula/initial/endpoint/duration/accuracy are proposed, not approved |
| planner_only_M1_inputs | PASS | Not used by a non-optimized smoke reference; remain OPEN for A3/G2.5 |
| reference_initial_state_measured | NOT TESTED | Prehold endpoint has not been measured; never assume exact midpoint |
| reference_owner_controls_decision | AWAITING HUMAN REVIEW | Reference choice and new measured-endpoint start rule require approval |
| P1_sampled_pair_screen | PASS | Numerical predeclared nodes only; no continuous-box enclosure |
| P1_complete_point_QP | PASS | Fixed midpoint/zero-velocity estimate fixtures; not physical prehold endpoints |
| physical_prehold_dynamics | NOT TESTED | No prehold executed or validated; no clamp/reaction torque allowed |
| hold_tracking_torque_end_conditions | NOT TESTED | Must verify declared q/qd tolerances, applied torque and final measured state |
| signed_physical_prehold_clock | NOT TESTED | Execution adapters for negative preparation epochs are not implemented/approved |
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

The existing approved v1.2.1 startup remains infeasible (FAIL). The proposed preparation has not been physically validated (NOT TESTED). All human fields in this revision remain null (AWAITING HUMAN REVIEW). The checker has no actuator or A2 launch path.
