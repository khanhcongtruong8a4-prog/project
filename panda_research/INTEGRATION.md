# Integration record

This document records the v1.2.0 merge. The additive v1.2.1 Action 3 work is
documented separately in ACTION3.md and the current Action 3 handoff. Statements
below about absent components describe that historical merge, not the new code.

Combined development version 1.2.0, prepared 1 November 2026. This is a code
integration and numerical model-validation release, not an approved experiment
freeze or an approved revision of the research model.

## Retained from panda_review

- `_vector7` and `_finite_scalar` guards, normalized acceleration/friction/FK
  inputs, rejection of malformed/nonfinite inputs and negative amplitudes.
- Unchanged selected constants and CasADi physical model; exact flat-vector
  behavior is checked against the original at all 154 cases.
- MuJoCo reference XML, documented fullinertia precision problem, explicit
  principal-inertia import and reconstruction check without relaxed tolerances.
- Expanded 132-state sample set, API regressions, independently transcribed
  logistic-friction check, disturbance sweeps and plant-only work-energy test.

## Retained from the remediation

- All primary-source bytes and actual pinned Git commit/tree/blob comparisons.
- Original 22 protocol case-generation sequence, original 19-check reproduction
  and accurate classification of internal consistency checks.
- Pinocchio model built from parsed source bytes, source-table/Xacro checks,
  70+21 review rows, link maps and five controlled model-error detections.
- Corrected evidence labels, computed eigenvalue extrema, full-limit friction
  grid, unsigned review sheets, M1/fairness/refinement proposals and gate policy.

## Integration fixes

1. Corrected the new runtime's two inherited helper docstrings. No physical
   constants or dynamics-construction equations changed.
2. Changed the legacy friction-grid test to call the documented single-vector
   API once per row. No test threshold was loosened.
3. Removed active use of `prepare_corrected_tests.py` and the source-regenerating
   runner. Historical copies are retained only under historical/. A validation
   run now checks the production source hash before and after execution.
4. Replaced the obsolete whole-module unchanged-AST assertion with explicit
   selected-constant equality, unchanged CasADi-constructor AST, valid-input
   parity and API regression tests. The new guards intentionally change code.
5. Both engines use the same expanded132 + exact protocol22 state set; the exact
   original q/qd/qdd arrays are preserved and checked separately. Test/group
   counts remain distinct, with no inflated count of independent experiments.
6. Moved all generated XML/URDF, source-table extraction, reports, unsigned CSV
   sheets and logs into a unique run directory. Neither tests nor replay edit
   code, historical evidence, protocol proposals or human acceptance records.
7. Merged scientific dependencies into one tested environment while preserving
   Pinocchio's URDFDOM 4.0.1 / TinyXML2 10.0.0 ABI pins and MuJoCo 3.3.7.
8. Added an editable runtime package and a single Linux/Windows Python runner.
   Final release packaging excludes virtual environments and Git caches.

The new runtime's ancestry and exact diffs are in provenance/. Original ZIP
members, incoming review artifacts, inputs and earlier remediation records
remain byte-identical and are checked on every run.

## Scope still open

No symbolic public planner API, observer, controller, HOCBF-QP or optimizer was
added. No unknown gain, electrical coefficient, simulation period or solver
policy was invented. The earlier generic PyBullet demo remains separate.
Human T04b/T06a/dynamics acceptance is not supplied by either engine passing.
Protocol proposals remain unsigned; missing source documents and the decision
register still govern the next scientific implementation step.
