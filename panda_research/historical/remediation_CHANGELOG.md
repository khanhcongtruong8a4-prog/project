# Reviewer-remediation change log

All work is in a new directory, /workspace/ic2ai_remediation. The pre-existing
project/PyBullet files and uploaded attachments remain unchanged. No branch,
commit or GitHub push was created. Baseline/source identities are recorded in
reports/baseline_hashes.json and reports/source_git_verification.json.

## Modified working copies, compared with ZIP

- src/panda_dynamics.py: only the docstrings of mdh_fk_numpy and urdf_fk_numpy
  changed, removing false independence/source-verification labels. No executable
  AST change, parameter change or mathematical model change.
- src/run_phase3a_tests.py: test names/notes now distinguish in-code literals,
  shared kinematics, shared derivatives and same-model finite differences.
  Calculate the largest joint-space mass-matrix eigenvalue across all 22 poses.
  Test friction at 261 inclusive speeds per joint across its full declared
  [-VMAX,+VMAX] range. Add evidence classes/grid metadata and direct output to
  a new report. The original 19 test thresholds remain unchanged.
- New README/model_check_summary: replace misleading primary-check and
  independence language in active documentation; clearly identify historical
  copies and the pending human reviews. Original README/summary retained.
- Protocol: separate R1 MD/TXT/DOCX addendum addresses TXT B2/D/F and DOCX
  10.2/10.4/10.5 and adds v1.0 8.2 refinement/fairness proposals. Original v1.0
  and both draft v1.1 files are unchanged. No approved protocol is fabricated.

The exact two-file diff is reports/code_changes.patch. The unchanged executable
model is checked in reports/evaluator_semantics.json.

## Added implementation and evidence

- fetch_sources.py and verify_git_sources.py: verified-TLS downloads, SHA256,
  Git blob hashes and actual pinned Git commit/tree identity checks.
- run_reproduction.py: execute exact original scripts in runs/original, record
  runtime/commands/outcomes and honestly classify the internal evidence.
- prepare_corrected_tests.py: reproducible minimal edits to working copies.
- reference_model.py: independent source parsers and source-built URDF.
- compare_external_dynamics.py: exact seeded 22-case FK/CRBA/RNEA comparison,
  explicit per-component tolerances and per-case CSV/JSON.
- verify_primary_sources.py: independent PDF/MATLAB/Xacro comparisons against
  target and manifest; 70+21 rows, all joint origins/axes and full link map.
- test_reference_sensitivity.py: controlled mass, COM, inertia-sign, origin and
  gravity corruptions; confirm the external tests detect them without altering
  accepted model files.
- prepare_scenario_b_suite.py: method-independent target proposal, no planner
  feasibility or comparative result screening.
- run_all.py: offline replay with source extraction, actual command exit codes,
  runtime, exact original case-array match, baseline preservation and AST check.
- build_deliverables.py/build_documents.py: issue disposition, gates, incomplete
  proposal manifest, decisions and review-document exports from real evidence.
- audit_package.py: final artifact integrity, result-count/schema and archive
  checks, plus the package artifact index.
- review_sheets/: source comparisons and unsigned human acceptance sheets.
- protocol/: addendum, target proposal, incomplete configuration, decisions.
- reports/: fresh results, source identities, reviewer response, gate matrix,
  editorial out-of-scope memo and input inventory; logs/: actual command output.
- requirements.lock.txt: exact successfully imported scientific dependencies;
  requirements-docs.txt: optional DOCX dependency.

## Intentionally unchanged or unperformed

Original ZIP and all nine members; model_manifest_v1.json; Protocol v1.0;
historical JSON/logs; original draft v1.1 TXT/DOCX. Missing workbook/manuscript
are not reconstructed or edited. All human approval fields remain blank/null.
No A2/shakedown, A3 Scenario A/B/C, T27, G2.5 or interval-certification run.
No new electrical coefficients, physical-robot validation or Level-1 claim.
