# IC2AI 2027 Panda A2 polynomial-hold remediation v2.4b

The requested unpublished checkpoint f9278f2 was not recovered. This is a new
versioned reconstruction from published 4e6335d, with every earlier source and
failure preserved. Read panda_research/reports/active_remediation_v2/final_v2_4b/
ACCEPTANCE.json and ALL_CANDIDATE_REFINEMENTS.csv for separate decisions.

Runtime v2.4 uses causal cubic torque holds, Gauss-Legendre execution, and
28-variable augmented completion QPs with constraint generation and full
finite-grid guarded/KKT verification. Dynamics, gains, disturbance, original
numerical thresholds and historical sources are unchanged. There is no stored
exact-witness runtime fallback. All new source versions and failed attempts
are included. See policy/active_remediation_v2/ for mathematical justification.

IMPORTANT VERIFICATION HISTORY: original result.json and logs retain the failed
bitwise implicit-fixed-point assertion. They are never overwritten. The frozen
v2.4b audit independently checks matching actual polynomial torque and complete
plant/DOB/power stage equations at the ORIGINAL predeclared 1e-13 residual.
AUDIT_V2_4A.json binds this correction to each original result and raw trace by
SHA256. The acceptance ledger explicitly records both verdicts. No physical
trajectory is changed or spliced, and no guard, KKT or refinement tolerance is
relaxed. Three negative-control/analytic tests qualify that auditor. A separate v2.4b
check bounds arithmetic representation roundoff without waiving any negative
slack or changing feasibility/KKT thresholds; three further contracts qualify it.

The ZIP includes ALL tracked source, inputs, past failures, current raw traces,
original seven plus twelve extended replays, and 39 finite T27 fixtures. No
rounding/downsampling of evidence is used. MANIFEST_A2_POLYNOMIAL_REPRODUCTION.json hashes
every delivered file except itself; the outer ZIP has a separate SHA256.
Git object history is not embedded. A2_POLYNOMIAL_SOURCE_VERSION.json records source commit
and correction history. A standalone run creates explicitly LOCAL policy
staging metadata for the unchanged original Git-checking CLIs; it never forges
historic provenance, external reviewer signatures or checkpoint recovery.

Use Linux x86-64, Python 3.12.14, g++ and Poppler pdftotext. Tested native
libraries are included with build records, source and support-sign patch.
Dependencies are pinned; installation keeps TLS verification enabled.

    python VERIFY_A2_POLYNOMIAL_PACKAGE.py
    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0 wheel==0.48.0
    .venv/bin/python RUN_A2_POLYNOMIAL_REPRODUCTION.py --verify-only
    .venv/bin/python RUN_A2_POLYNOMIAL_REPRODUCTION.py --prefix fresh_local_full_replay

The full command reruns contract tests, all 39 T27 fixtures, all 19 frozen
regressions, and all eight new candidate cells with their corrected independent
audits and every refinement comparison. It is computationally substantial;
prefixes must be new. No previous summary is a substitute for a new run.
The extra historical active-AB2 campaign inside the frozen regression command
is EXPECTED to remain a refinement failure (exit3). Its preserved failure is
reported separately; the final source's acceptance is never based on that exit
alone. For candidate-only iteration use --candidate-only; it does not qualify
the omitted 19-cell/T27 gates. --workers 1 or 2 controls physical-run parallelism.

Read ALL_COEFFICIENT_COMPLETION_V2_4.md and the numerical audit policy before
interpreting results. Sampled trajectories, finite-grid guarded inequalities,
KKT tolerances and collocation extrema are NUMERICAL evidence, not certified
bounds on the true ODE between samples. A2 numerical acceptance is separate
from continuous-time certification, planner/M1/G2.5 readiness, official A3 and
Level1. No official A3 comparison or Level1 certification is performed.
