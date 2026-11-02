# IC2AI 2027 guarded-QP remediation

Read panda_research/reports/guarded_qp_reliability_v1/READINESS_DECISION.md.
The scoped decisions and known failures are separate and machine readable in
panda_research/policy/guarded_qp_reliability_v1/ACCEPTANCE_DECISIONS.json.
No independent reviewer signatures, official A3 experiments or Level 1 claims.

This COMPLETE package contains every previous protected source/input/failure
file, full new 23-cell motion evidence, both 39-fixture regressions, exact
certificates, corrected source, build recipe and the tested Linux x86_64 backend.
Large original files use exact reversible encodings in evidence/. Nothing is
rounded or replaced with a numerical witness. Restore checks original byte SHA.

Use the recorded Linux / Python 3.12.14, zlib 1.3.2 and pinned versions:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_REMEDIATION.py --verify-only
    .venv/bin/python RUN_REMEDIATION.py --qp-only --prefix my_qp_check
    .venv/bin/python RUN_REMEDIATION.py --run --prefix my_motion_replay

The last command runs all 19 selected A2 cells AND the four separately labeled
legacy active-filter cells. A failure of their original refinement criteria
remains a failure and produces a nonzero aggregate process exit code.

The ZIP has no Git history. Full restoration creates explicitly labeled LOCAL
input-staging metadata to keep the ORIGINAL runners' committed-input checks
enabled. This is not a reconstruction of historical commits or signatures.
Full restoration needs several GB of temporary disk; QP-only needs no raw-trace
restoration. The tested backend is bundled with its SHA and source hashes.

To rebuild from pinned installed headers (g++17 required):

    .venv/bin/python panda_research/scripts/build_guarded_qp_reliability.py --output my_local_build

Use PANDA_GUARDED_QP_BUILD to select that build and rerun the 39 strict fixtures.
A rebuilt binary is a separate build unless its SHA matches the frozen tested
binary; the motion verifier intentionally rejects silently substituted builds.
Do not overwrite the frozen policies or earlier failed results.

QP_REPRODUCTION.zip is a SMALL extra package containing source, policies,
reports and every fixture needed for the 39-case solver reproduction. It is
not the complete trajectory evidence archive; its --qp-only command is usable
without downloading or restoring the large raw-history payloads.
