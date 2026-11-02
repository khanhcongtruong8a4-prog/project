# Panda research development — v1.2.2 P1 review remediation r2

The combined v1.2.0 numerical model is preserved unchanged. The new
`panda_closed_loop` package implements Action 3 components under the supplied
v1.2.1 owner policy. Start with [ACTION3.md](ACTION3.md) and
[the latest Action 3 handoff](reports/ACTION3_REVIEW_HANDOFF.md).
Current status is the [independent-review remediation](reports/p1_v1.2.2_r2/REVIEW_REMEDIATION.md)
and [r2 draft policy](policy/v1.2.2-r2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2_r2.json).
The frozen applied-torque development hold fails its speed tolerance at joints
3 and 7 after 1.25 ms in all four C4 cells. Signed execution and actual abort-state
full-QP diagnostics are implemented; no valid zero-time endpoint is obtained.
Official A2 remains NO-GO. A new startup decision, independent human review and
build confirmation are outstanding. The previous [analytical review](reports/p1_v1.2.2/REVIEWER_ISSUE_RESPONSE.md)
and its draft remain unchanged as history.
Planner-only M1 inputs remain open for Stage-1 references and A3.

This is the combined development base for the selected **Gaz seven-body
Franka Emika Panda model**. It brings together the validated single-vector API
and MuJoCo review from `panda_review.zip` with the pinned source provenance,
Pinocchio comparison, review sheets and protocol work from the remediation.
The original packages remain preserved under baseline/, inputs/ and historical/.

Start with [development status](reports/DEVELOPMENT_STATUS.md) for actual results
and [integration notes](INTEGRATION.md) for what was combined.

## Install and validate

Tested on Linux x86-64 with Python 3.12.14. The full development environment
contains NumPy 2.3.5, SciPy 1.17.0, CasADi 3.7.2, Pinocchio 3.8.0 and MuJoCo
3.3.7. Poppler `pdftotext` must be available (`poppler-utils` on Debian/Ubuntu).
No ROS, GPU, GUI or credentials are needed for these checks. Action 3 adds
ProxQP via Proxsuite 0.7.2; it is pinned in the same lockfile.

From this directory (`/workspace/project/panda_research` in the prepared cloud):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python scripts/run_validation.py
# Action 3 focused tests + all baseline regression checks:
.venv/bin/python scripts/action3.py validate
```

On Windows, use `.venv\Scripts\python.exe` and install Poppler so `pdftotext`
is on PATH. The scripts themselves use pathlib and subprocess without shell
commands. This combined release was validated on Linux; the incoming MuJoCo
package's earlier Windows run remains historical evidence.

Each run gets a new UTC-named directory under `runs/`. Its JSON, CSV, exact
sample arrays, commands, package versions and logs are retained. `reports/latest.json`
points to the newest run; its status records failure as well as success.
Failed or older runs are not overwritten. Validation never regenerates the
production module or edits baseline files, protocol proposals or human reviews.

## Use the numerical plant

After editable installation:

```python
import numpy as np
from panda_dynamics import PandaDynamics, QMIN, QMAX, dual_harmonic_disturbance

model = PandaDynamics()
q = (QMIN + QMAX) / 2
qd = np.zeros(7)
tau = model.evaluate(q)["g"]
qdd = model.acceleration(q, qd[:, None], tau, d=dual_harmonic_disturbance(0.0))
assert qdd.shape == (7,)
```

Joint-vector inputs accept `(7,)`, `(7,1)` or `(1,7)` and return normalized
vectors. Nonfinite/malformed inputs and negative/nonfinite disturbance amplitude
are rejected. The public friction API deliberately accepts one vector, not
batches: use `np.stack([friction(v) for v in velocity_grid])` for a grid.
The plant does not enforce physical limits; later controller/execution code
must check those separately. Public `evaluate()` is numerical; a symbolic
planner interface is still future work.

## Validation coverage

- Reproduce the untouched original 19 checks in a disposable run-local copy,
  classifying them honestly as internal tests.
- Run 19 corrected internal checks, including the maximum sampled inertia
  eigenvalue and 261 inclusive velocities per joint over its declared limits.
- Compare all 70 inertial and 21 friction entries to the revised Gaz supplement
  and author MATLAB bytes; compare seven moving joint origins/axes and the fixed
  flange to the pinned official Xacro. Retain unsigned CSV sheets and link maps.
- Compare Pinocchio CRBA/RNEA/FK and independently evaluated author friction
  against the development model on **154 state cases**: the newer 132-state
  full-box/edge suite plus the exact original 22 protocol cases. Record
  per-component values and per-pose diagnostics with unchanged tolerances.
- Run the MuJoCo suite on those **same 154 cases**, retain its compiled-inertia
  precision check, 81 API shape combinations, 51 invalid-input checks and
  plant-only work-energy test. Per-comparison CSV includes state indices.
- Detect five controlled physical-model corruptions. Verify unchanged selected
  constants, unchanged CasADi construction, exact valid-flat-vector results,
  exact sample sequences and independent MJCF agreement with pinned sources.

The two references use different dynamics engines and separate model
construction. The Pinocchio builder parses pinned MATLAB/Xacro bytes and never
imports target transforms, M, dM, U or CasADi. MuJoCo uses a separate handwritten
XML checked against those source bytes. Sharing test INPUTS is intentional.
Internal shared-derivative identities remain internal evidence.

## Project layout

| Path | Purpose |
| --- | --- |
| src/panda_dynamics.py | Development runtime, with API fixes and accurate helper descriptions |
| src/reference_model.py | Independent source-built reference; not part of the installed runtime module |
| tests/ | Original/internal/source/Pinocchio/MuJoCo and integration checks |
| scripts/run_validation.py | One offline validation command; no code regeneration |
| provenance/ | Pinned source identities, preserved-input hashes and runtime ancestry/diffs |
| sources/ | Retained primary source bytes and their attribution/licenses |
| references/mujoco/ | Original independent XML and initial import-failure diagnostic |
| baseline/ | Original nine-file ZIP members plus the exact incoming review package |
| historical/ | Earlier remediation code/reports and comparison notes; not active tooling |
| protocol/ | Proposed amendment, target suite, incomplete configuration and decision register |
| review_sheets/ | Unsigned acceptance instructions/templates |
| reviews/ | Actual human acceptance records; never generated or overwritten by tests |
| runs/ | Immutable-by-convention run history, including failures |

`scripts/fetch_sources.py` and `scripts/verify_git_sources.py` are optional
online re-verification tools using existing HTTPS proxy/TLS trust and pinned
Git commits. Do not run historical scripts as the current workflow. Runtime
and model-identity versions are distinct; the original manifest is unchanged.

## Research gates

**A1 implementation: GO.** The supplied v1.2.1 policy supersedes the earlier
C1-C6 proposals and specifies gains, reserves, disturbance and refinement.
It records owner acceptance of model evidence, not independent signatures.
Closed-loop components and focused fixtures are implemented, but official A2,
A3 comparisons, complete T27, G2.5, Level 1 and publication claims remain blocked.
See the [r2 A2 entry checklist](reports/p1_v1.2.2_r2/A2_ENTRY_CHECKLIST.md) for current blockers.
Sampled inertia eigenvalues do not establish global m1. The original model,
past proposals/evidence, manuscript and workbook have not been rewritten.

Optional DOCX regeneration needs `requirements-docs.txt` and
`python scripts/build_documents.py`; this exports unsigned protocol/review
copies only. Final packaging uses `python scripts/package_release.py` after a
passing validation run. Neither command publishes or pushes to GitHub.
