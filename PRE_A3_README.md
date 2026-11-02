# IC2AI 2027 pre-A3 blocker investigation

Read panda_research/reports/pre_a3_blockers_v1/ISSUE_RESOLUTION_REPORT.md and
panda_research/policy/pre_a3_blockers_v1/TECHNICAL_DISPOSITION.json. A2's frozen 19-cell GO is
retained. Active-filter refinement, qualified M1 bounds, full G2.5 and A3 are
NO-GO. The rejected sampler is preserved as a failed development version.
T27 passes all 39 finite fixtures. No Level1 or external signatures are claimed.

This compact package includes all core source, unchanged model/policy audit
inputs, new numerical evidence, full raw evidence for six new simulation
cells, and four legacy active-filter execution traces used in diagnosis.
Other earlier raw history is preserved in the separately linked immutable
historical annex (HISTORICAL_ANNEX.json); it is not duplicated here.
The old 19-cell A2 data were reaudited in the full checkout. Their recorded
scientific digests and unchanged-source proof are included; another fresh
19-cell physical run is not claimed. Replaying every historical frozen CLI
requires the full original annex/checkout and all its original input checks.

Use Linux / Python3.12.14 and the recorded pinned versions. Exact CTZ container
restoration uses the recorded zlib1.3.2; every restored byte SHA is checked.

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_PRE_A3.py --verify-only
    .venv/bin/python RUN_PRE_A3.py --run-numerics --prefix my_numerical_replay
    .venv/bin/python RUN_PRE_A3.py --restore --diagnose-legacy --prefix my_trace_diagnosis
    .venv/bin/python RUN_PRE_A3.py --run-dynamics --prefix my_six_cell_replay

Numerical replay runs 4 sampler, 6 M1 and 4 entry-gate contracts, 39 T27 fixtures,
rebuilds all 14 M1 tables from the fixed raw sampling protocol, reruns the
1,212 G2.5 point checks, and confirms the technical planner stop. Reproducing
NO-GO results is a successful reproduction, never a promotion to acceptance.
Dynamic replay reruns four candidate C4 and two original-AB2 ladder cells.
Fresh outputs are exclusive and previous failures are never overwritten.

The historical diagnosis restores exact raw CTZ files from evidence/. Their
array bytes and complete original ZIP containers are checked. No float values
are rounded, approximated or replaced with an optimum witness during packing.
Raw-feedback QPs are declared algorithmic steps, never fallback actuations.
QP guards, constraints, gains and numerical/acceptance targets are unchanged.

The bundled native backend and source build recipe retain their frozen SHA.
GCC builds are separately qualified if their binary SHA changes. The package
contains no venv, cache, Git history or external human signatures. For dynamic
replay it creates explicitly labeled LOCAL Git input-staging metadata for the
new frozen development declarations; historical commits are not reconstructed.
No official A3 comparison solver is invoked by any reproduction mode.
