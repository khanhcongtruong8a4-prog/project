# Which Panda package should development continue from?

Prepared 1 November 2026. Comparison of the existing `ic2ai_remediation` package
with the uploaded `panda_review.zip` (SHA256
`563d663ac69ddb427d10fa3710c5caac7a97ea128685ffdaaa0b413eae01c3c0`).

## Recommendation

**Use the new `panda_review/panda_dynamics.py` as the runtime code base, while
retaining the existing remediation package's provenance, Pinocchio validation,
source-review sheets and protocol/gate documents.** If one dynamics module must
be selected today, select the new one. Replacing the whole existing research
package would discard useful verification and decision work.

The decisive reason is a real API defect: the existing module returns a `(7,7)`
acceleration when velocity, torque or disturbance is a column vector. It also
returns a `(7,7)` friction matrix for a column velocity and accepts negative
disturbance amplitudes, producing negative supposed absolute bounds. I reproduced
these failures in the existing working code. The new code fixes them.

The earlier remediation preserved the evaluator's executable model while fixing
reviewer-requested evidence/provenance issues. That left these runtime defects
undetected and unchanged. It should not be used as the runtime base unpatched.

## What was actually checked

- Both packages share the exact same original evaluator and historical result
  file. The new package's manifest matches all 16 declared file hashes.
- Re-ran the existing model-evidence workflow in a separate copy: **PASS**,
  including the original/corrected 19 checks, source tables, Pinocchio reference
  and five model-error sensitivity checks.
- Re-ran the new suite on Linux/Python 3.12.14 with its exact pinned NumPy 2.3.5,
  SciPy 1.17.0, CasADi 3.7.2 and MuJoCo 3.3.7: **58/58 groups PASS at 132 states**.
  Its saved q/qd/qdd sample arrays reproduce exactly. This reproduces the suite
  on a different OS/Python release from its recorded Windows/Python 3.13 run.
- Compared both numerical evaluators on the new 132-state set PLUS the original
  protocol's exact 22 q/qd/qdd cases: **all returned flat-vector values are
  exactly equal across 154 state cases** (including M, dM, C, g, F, U, flange
  and ID). The broader sampled eigenvalue range is a sampling difference,
  not evidence that the physical model was changed.
- Compared the NEW module against the existing source-built Pinocchio reference
  on those same 154 states: all five quantity comparisons per state pass the
  unchanged protocol tolerances. Maximum errors: M 2.22045e-15 kg m^2,
  g 2.13163e-14 N m, Cqd 2.13163e-14 N m,
  ID 3.55271e-14 N m, flange 3.33067e-16 m.
- Independently compared the new handwritten MJCF masses, COMs, signed COM
  tensors, origins/rotations, gravity and flange with the existing downloaded,
  Git-pinned Gaz/Xacro source data: all match numerically.
- Tested integration compatibility in disposable copies. A naive file swap
  fails the legacy friction-grid test; changing that test to call the new
  single-vector API once per grid row restores **19/19 PASS**.
- Both original packages' recorded file bytes remain unchanged. No development
  merge, Git commit, GitHub push or closed-loop experiment was performed.

The numbers 58 groups, 594 quantity/pose checks and 19 internal checks describe
different test structures. They cannot be ranked as equivalent test counts.

## Comparison by development concern

| Concern | Existing remediation | New panda_review | Preferred use |
| --- | --- | --- | --- |
| Numerical plant API | Column-vector broadcasting bug remains; negative bounds accepted | Correct normalization, 81 shape combinations and 51 invalid-input cases tested | New module |
| Valid nominal dynamics | Source-built Pinocchio agrees on exact 22 protocol cases | MuJoCo agrees on 132 cases; now also agrees with Pinocchio on the common 154 cases | Keep both engine checks |
| State coverage | Prescribed zero/midpoint/20 seeded inset poses; controlled normal qd/qdd | Adds all-lower/all-upper poses, 128 full-box interiors, full-speed-box qd and qdd in [-3,3] | New expanded coverage plus required original 22 |
| Source provenance | Retained primary bytes, actual Git commit/tree/blob verification, 70+21 parameter rows and frame maps | Handwritten reference XML and source URLs; primary source bytes/review sheets not bundled | Existing evidence package |
| Plant integration | No plant integration run | 0.25 s DOP853 work-energy check and maximum-step refinement | New plant-only check; not A2 |
| Reviewer issue coverage | Corrected evidence labels, source checks, unsigned review sheets, M1/Scenario B/refinement proposals, decisions and gates | Better runtime engineering; retains old helper docstring claiming independent NumPy FK; no equivalent full remediation register/protocol addendum | Retain existing reviewer/protocol layer |
| Missing paper components | Numerical plant; no symbolic public planner API, controller, DOB or HOCBF-QP | Same gaps; documents them clearly | Neither is the complete paper simulation |
| Research approval | Human signatures and full freeze pending | No qualified sign-off or approved comparative freeze supplied | Gate state unchanged |

## Strengths and limits of the new validation

The MuJoCo reference is genuinely a separate implementation for rigid-body
dynamics. Its documented fullinertia import issue is handled appropriately:
the reference's independently entered tensors are diagonalized, the compiled
tensors are reconstructed and checked, and production parameters/tolerances
are preserved. I reproduced the passing corrected import. Keep both the initial
failure diagnostic and the corrected reference; this is useful evidence.

However, the new XML is still a handwritten transcription and its friction
reference uses literal coefficient arrays. The new ZIP alone does not retain
the source-byte checks or 70+21 signed-review records. The present comparison
checks its XML against the existing pinned sources, which is why combining the
two evidence layers is stronger than throwing either away.

The new suite does not use the exact original 22-state sampling sequence:
its 132-pose generation and speed/acceleration distributions differ, despite
sharing seed 20261101. Keep the exact original 22 as a named regression set.
The common-case comparison performed here confirms the new module passes them.

The DOP853 plant-only test verifies a numerical plant trajectory/energy balance.
Its h values are adaptive integrator maximum-step limits, not fixed-step RK4
execution or a control-period refinement. It does not implement the observer,
controller, held-control safety QP or A2. It must not advance those gates.

## Integration changes needed before adopting the new code

1. Version the new runtime module as the development successor while preserving
   the original model manifest and original evidence. Carry over the existing
   accurate helper docstrings; the new module still contains the old
   `Independent NumPy MDH product reference` wording.
2. Keep the new API regression tests and MuJoCo suite alongside the existing
   exact-22 Pinocchio/source tests. Maintain a clear distinction between internal
   identities, external numerical checks and human acceptance.
3. Update the old friction-grid test from the batch call `friction(vv)` to an
   explicit row loop/stack, since the new public API deliberately supports only
   one joint vector. I tested this adaptation successfully in a disposable copy.
   This API contract change is manageable, but a blind file swap is not enough.
4. Fix the existing regeneration pipeline before use: `run_all.py` invokes
   `prepare_corrected_tests.py`, which rewrites the dynamics module from the old
   baseline and would undo the new runtime fixes. Its assertion of unchanged
   executable AST must also become a version-aware regression check: new input
   guards intentionally change executable code while preserving model equations.
5. Update versioned code/evidence hashes and the environment instructions after
   integration; preserve baseline hashes as history. Keep the existing Linux
   lock/Pinocchio ABI pins and a separate tested MuJoCo dependency definition.

These are migration findings and validated probes, not a claim that a production
merge has already been made. Both source packages are unchanged.

## Specifications still requiring source inspection

The new REVIEW.md reports having read a 28-page framework PDF, a four-page paper
and Tasks_2026.xlsx. Their hashes are listed, but their bytes are not in the new
ZIP and have not been supplied in this chat. This comparison therefore cannot
independently confirm its manuscript-specific choices: tracking error sign,
quintic planner, 1 ms control period, exact barrier counts, or the reported
velocity-margin conflict `(lambda+alpha_v)` versus `abs(alpha_v-lambda)`.
These notes are useful leads, not authority to silently change the selected
protocol or implement one conflicting formula. Obtain and version the actual
documents before resolving those choices. The common protocol DOCX hash does
match the existing supplied v1.1 draft.

Neither module's public `evaluate()` accepts symbolic CasADi MX decision
variables; I tested that both reject symbolic input. A public symbolic
dynamics/kinematics interface, Jacobian/manipulability derivatives, controller,
observer, QP and planner remain genuine implementation work. Do not select
gains or electrical coefficients from a passing plant-validation report.

## Gate decision and next development step

**A1 implementation: GO. A2: still conditional/blocked by required qualified
model/source acceptance and approved smoke-test settings. A3, Level 1 and
publication-result claims: NO-GO.** Numerical agreement does not sign T04b/T06a
or prove a global positive m1 or sampled-controller safety.

The next development step should be a versioned integration of the new module
and regression suite into the existing research evidence structure, with the
pipeline/API adaptations above. Then build and validate the symbolic model
interface needed by the planner. In parallel, obtain the missing source
documents and human reviews before selecting the final closed-loop settings.

## Evidence files

- reports/new_reproduced.json and new_reproduction_console.log: actual new run.
- runs/existing/reports/verification_run.json: actual existing workflow replay.
- reports/head_to_head.json: common-state parity, API probes, independent
  Pinocchio results and MJCF/source comparisons.
- reports/integration_compatibility.json and adapted_integration_console.log:
  expected naive-swap failure and passing single-vector test adaptation.
- reports/package_manifest_check.json and original_package_preservation.json:
  package identities and unchanged originals.
- compare_models.py: reproducible comparison implementation.

Review is based on executed checks and inspectable artifacts, not on authorship
of either package or on the number of tests claimed in its README.
