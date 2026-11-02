# IC2AI 2027 — reviewer-remediation evidence package

Start with [the reviewer response](reports/REVIEWER_RESPONSE.md). This package
compares the uploaded nine-file ZIP with the **full-package** reviewer report
and makes targeted corrections. It preserves the research model and all
original evidence. The earlier generic PyBullet demo is unrelated and excluded.

**Current result:** 19 original internal checks reproduced; 19 corrected
internal checks pass; source-built Pinocchio agrees at all 22 prescribed poses.
Automated source checks pass for 70 inertial values, 21 friction values and
eight joint/frame rows. Human signatures and experiment approvals are pending.
No closed-loop, comparative or interval-certification experiment was run.

## Evidence map

| Path | Meaning |
| --- | --- |
| inputs/ | Exact uploaded originals plus clearly named extracted reference text |
| baseline/ | Exact nine ZIP members, historical records preserved unchanged |
| src/panda_dynamics.py | Original evaluator with two misleading docstrings corrected only |
| src/run_phase3a_tests.py | Working tests with corrected labels, maximum eigenvalue and full-speed friction grid |
| reports/original_reproduction.json | Fresh 19-check results, historical comparison and evidence classification |
| reports/corrected_internal_tests.json | Corrected internal checks and measured diagnostics |
| reports/external_cases.json | Exact original 22 q/qd/qdd cases and draw order |
| reports/external_dynamics.json and .csv | Per-pose/quantity diagnostics, component values, tolerances and summary |
| reports/reference_sensitivity.json | Five deliberate model errors detected by the external comparison |
| reports/source_downloads.json | Pinned URLs, downloaded sizes, SHA256 and Git-blob hashes |
| reports/source_git_verification.json | Actual Git commits and tree/blob equality for downloaded sources |
| review_sheets/ | 70+21 parameter rows, eight joint rows, seven link maps and UNSIGNED acceptance sheets |
| protocol/ | Proposed R1 addendum, fixed target-suite proposal, incomplete freeze and unresolved decisions |
| reports/verification_run.json | Exact commands, exit codes, cwd, times, runtime and dependency versions |
| reports/preservation_check.json | Baseline, uploaded original and downloaded-source integrity checks |
| reports/evaluator_semantics.json | Executable AST unchanged after removing docstrings for comparison |
| reports/code_changes.patch | Minimal code diff against original ZIP |
| CHANGELOG.md | Exact nature and scope of source/document changes |

## Reproduce the model-only workflow

Tested on Linux x86-64, Python 3.12.14, NumPy 2.3.5, SciPy 1.16.3,
CasADi 3.7.2 and Pinocchio 3.8.0. The original reported Python 3.13.5 /
SciPy 1.17.0 are recorded historically, not necessary minimum versions.

From this package directory (currently /workspace/ic2ai_remediation):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python src/run_all.py
.venv/bin/python src/build_deliverables.py
```

`pdftotext` from Poppler must be available (tested version in verification_run).
The offline workflow regenerates source-table text from the retained PDF.
On Debian/Ubuntu the system package is `poppler-utils`. All model/data files
needed by the offline checks are included. No secrets, ROS, graphics or GPU
are required. Scripts exit nonzero on failed checks and preserve diagnostic
outputs. Re-running updates NEW evidence under reports/, logs/ and runs/;
baseline/ and uploaded original bytes are never changed. Preserve/archive a
previous remediation run before rerunning if its new evidence must be retained.

The lock includes URDFDOM 4.0.1 and TinyXML2 10.0.0 deliberately: an initial
resolver install selected ABI-incompatible newer libraries for Pinocchio 3.8.0.
The import failure and correction are documented in logs/pinocchio_abi_fix.log.
Do not fix missing libraries by bypassing TLS or changing verification checks.

Optional remote re-verification with the inherited HTTPS proxy and TLS trust:

```bash
python3 src/fetch_sources.py
python3 src/verify_git_sources.py
```

The public destinations used are raw.githubusercontent.com and github.com.
Git object caches are excluded from the delivery archive; these two commands
recreate them when online. The source-identity report and exact downloaded
bytes are retained for offline replay. Public source attribution/licenses are
under sources/; original uploaded work is not relicensed by this package.

Optional DOCX exports use Python with python-docx 1.2.0:

```bash
python3 src/build_documents.py
```

Markdown/text/JSON/CSV remain the canonical, directly inspectable evidence;
DOCX exports are convenience review copies. No PDF-rendered layout review is
claimed.

## Independent reference and tolerance policy

reference_model.py parses **downloaded** Gaz MATLAB mass/COM/COM-inertia arrays
and official Xacro joint XML. It imports no target constants, transformations,
CasADi, M, dM or U. A second parser reads supplement Tables VIII/IX/I from the
PDF and checks every selected value. The selected reference URDF contains seven
Gaz inertial bodies and a massless 0.107 m flange. Pinocchio URDFDOM supplies
FK, CRBA supplies M, RNEA supplies g/Cqd/ID. Smooth friction is evaluated using
the downloaded author's logistic equation, separate from the target tanh code.

Common base, zero offsets, joint ordering, COM-centered tensors, gravity
(0,0,-9.80665) m/s^2 and no hand/payload/rotor/damping match the selected model.
The broad limits in the generated reference URDF are parser-only placeholders
for algebraic evaluation; they are NOT physical limits or experiment settings.
The sample box is taken from the unchanged manifest for shared test inputs.
Physical limits and the zero-pose exception remain as in v1.0. Link7's pi/4
macro rotates its collision sub-link only, as confirmed in pinned utils.xacro.

Apply v1.0 section 2.3 **elementwise**, using absolute tolerance plus 1e-9 times
the absolute reference component: translation 1e-10 m, rotation 1e-10,
M 1e-9 kg m^2 and ID 1e-8 N m. For g, Cqd and friction, use the same torque
tolerance as ID, stated explicitly. Optional kinetic/potential energy checks
use separately disclosed diagnostic thresholds. Do not compare arbitrary raw
library C entries to the target Christoffel C. The old shared-derivative checks
remain internal indexing tests, even after external numerical agreement.

## Remaining boundaries

A1 implementation can continue. A2 is conditional and currently BLOCKED by
required human source/model acceptance and unselected smoke-test settings.
A3, Level 1 and publication-result evidence remain NO-GO. Missing framework,
decision brief and research workbook prevent a complete equation-level NLP
map and registry freeze. Read input_inventory.json and unresolved_decisions.csv.
M1, Scenario B and refinement documents are proposals; null fields and blank
signatures are intentional. No coefficients, calibrated motor data, approvals
or research results are invented. No manuscript/workbook edits or GitHub push
were performed. The original model_manifest_v1.json approval fields stay null.
