# Combined release 1.2.0 — 1 November 2026

- Adopted the newer validated numerical API; fixed vector broadcasting and
  invalid disturbance-bound inputs relative to the original Phase 1 module.
- Preserved the selected Gaz seven-body physical model and source identity.
- Combined both independent engines on the original and expanded case sets.
- Preserved original/historical files and complete primary-source evidence.
- Retained the 19-check reproduction, current 19 checks, MuJoCo API/plant tests,
  Pinocchio per-case diagnostics, source-review sheets and error-sensitivity tests.
- Added per-comparison MuJoCo CSV diagnostics with state indices.
- Removed production-source regeneration and adapted the friction-grid caller.
- Added isolated, retained run directories and protected-file integrity checks.
- Added editable installation, a combined dependency lock, documentation,
  versioned runtime ancestry and a reproducible release archive command.
- Carried protocol/fairness/refinement proposals forward without approvals or
  changes to scientific tolerances, disturbance, gains or comparison results.

Active code is under src/, tests/ and scripts/. Old tools under historical/ and
baseline/ are retained as evidence and are not the active validation workflow.
No manuscript or research workbook was edited. No GitHub push was performed.
