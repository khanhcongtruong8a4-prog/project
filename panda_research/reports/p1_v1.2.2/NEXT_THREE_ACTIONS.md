# Three next human decisions/actions

| Priority | Owner | Required artifact | Objective acceptance criterion |
| --- | --- | --- | --- |
| 1 | Theory lead + controls lead; project owner approves | Signed P1 disposition and versioned startup decision, or an explicitly selected alternative | Review the frozen 0.156 s proposal, both pair families and full point QP; define the valid continuous state region or actual endpoint checks; resolve the signed physical clock and numerical-observer assumptions. Separately authorize and establish the applied-torque hold with the declared tolerances, no clamp/reset. P1 becomes PASS only after valid holding/end-state evidence; do not retune after failure. |
| 2 | Project owner + controls lead | Fully reviewed and hashed Protocol/policy v1.2.2 | Approve reference formula and measured-endpoint rule, 0.25 s duration/metrics, coupled-continuous observer plus sampled sensitivity, A2 FAIL/development stop semantics and every C4 cell. Complete all fields actually used by A2. Keep planner M1 open for A3; require it if a Stage-1 reference is selected. No missing value may be substituted by zero. |
| 3 | Independent controls reviewer + numerical lead + manuscript/build owner; project owner grants execution authority | Signed independent controls/theory review, clean-environment reproduction record, build-revision confirmation and separate written A2 authorization | Independently compare components/T28 with the pinned equation files; rerun `python scripts/action3.py validate` in a clean pinned environment and match outcomes, including the original infeasibility and A2 refusal. Confirm the responsible main.tex/Project.rar build revision and hashes. Verify P1/entry gates and record genuine signatures before issuing explicit written A2 authorization. Codex's engineering rerun does not supply these signatures. |

Official A2 can move to GO only after all applicable entry conditions and these
reviews/authorizations are satisfied. A3, Level 1 and publication retain their
later independent gates even after an eventual A2 GO.
