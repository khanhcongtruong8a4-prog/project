# Reviewer issue response — v1.2.2 DRAFT

Authoritative input: `inputs/p1_v1.2.2/Action 3 r2 Review A2 Gate Decision.docx`, sections A,D,E,F. The TXT handoff defines this engineering task. The reviewer did not execute tests; new results below are engineering reproductions, not new independent signatures.

| Finding | Status | File / line or artifact | Change, evidence and remaining condition |
| --- | --- | --- | --- |
| E5 | RESOLVED | `src/panda_closed_loop/feasibility.py:9` | Reproduced formal velocity-pair failure and baseline full-QP stop; source/unit checks use no plant. |
| E6 | RESOLVED | `scripts/p1_feasibility.py:62` | Position-pair derivation and per-joint output added; baseline joints 1,3 fail. |
| E7 | PARTIAL | `src/panda_closed_loop/feasibility.py:72` | Factor-two necessary arithmetic and separate lower witnesses added. Actual domain M1 bounds absent; planner remains BLOCKED. |
| E8 | RESOLVED | `src/panda_closed_loop/readiness.py:42`; `src/panda_closed_loop/config.py:141` | A2 requirement flags depend on reference kind (null/unselected, true/Stage-1, false/nonoptimized); A3 requirements remain true. Reference approval itself is pending. |
| E9 | PARTIAL | `src/panda_closed_loop/a2_plan.py:49` | Coupled-continuous RK4 plus explicit sampled sensitivity proposed; execution approval, discrete error justification and physical validation remain pending. |
| E10 | BLOCKED | policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json → source_build_review | 02/03 hashes match; main.tex and Project.rar still differ. No source rewrite or fabricated build acceptance. |
| E11 | RESOLVED | policy/v1.2.2-draft/PROTOCOL_v1.2.2_DRAFT_ADDENDUM.md → C4 | All four approved cells retained, including Delta=.5ms,h=.25ms,m=2; later C4 overrides T25 default. |
| E12 | BLOCKED | policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json → approvals | Baseline owner acceptance is historical; every new human signature/approval remains null. No independent signoff inferred. |
| F1 | PARTIAL | policy/v1.2.2-draft/PREDECLARED_P1_DESIGN.json; P1_FEASIBILITY_MEMORANDUM.md | P1 design declared before screen; T_pre analytically selected once; sampled pairs and point QP pass. Physical prehold not established and human startup choice unsigned. |
| F2 | PARTIAL | `src/panda_closed_loop/a2_plan.py:12`; scripts/check_a2_plan.py | Complete proposed reference, duration, metrics, observer, failure semantics and C4 supplied. Completeness PASS is not owner approval; signed execution definition absent. |
| F3 | BLOCKED | NEXT_THREE_ACTIONS.md; evidence/verification/verification.json | Engineering rerun is retained, but independent clean-environment reproduction, controls/theory signatures, build confirmation and written A2 authorization cannot be supplied by Codex. |
| E2 (additional) | PARTIAL | `tests/test_action3.py:205` | Renamed the shared-model row check and labeled its scope; independent reviewer rerun still outstanding. |

Evidence: [static screen](evidence/static_screen/screen.json), [per-joint online rows](online_pairs_per_joint.csv), [planner lower witnesses](planner_point_lower_witnesses.csv), [engineering rerun](evidence/verification/verification.json), [entry checklist](A2_ENTRY_CHECKLIST.md). Source line numbers refer to this overlay revision.

Decisions: **A1 GO; P1 BLOCKED; official A2 NO-GO; A3/Level 1/publication NO-GO.** No gain/disturbance/model change, plant prehold, official A2, optimizer, scenario or publication run was performed.
