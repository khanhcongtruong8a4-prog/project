# Verified IC2AI 2027 A2 package

Read panda_research/reports/a2_acceptance_v1/A2_READINESS_DECISION.md first.
The versioned policy is panda_research/policy/a2_verified_v1/FINAL_A2_POLICY.json.
Original r4 seven cells and v4 twelve cells were freshly replayed in a clean
checkout / pinned environment, with exact full scientific data agreement.
This is local technical evidence on the same host, not independent signatures.

One additional legacy-alpha5/guarded-solver probe FAILS despite an exact
represented-QP optimum. It is preserved and blocks broader solver/T27 claims.
The selected original alpha5 protocol uses its original solver; v4 uses
alpha10 and the guarded solver. Scope and known failure were declared before
the fresh replays. No gain, model, reference, guard or pass tolerance was changed.

This complete ZIP includes ALL prior protected source/input/failed-experiment
files and the new replay evidence. Large/raw files are LOSSLESSLY encoded in
evidence/, not omitted. Code and ordinary reports can be read immediately.
Restoration verifies every original file byte SHA-256 and refuses overwrites.

Use the recorded Python3.12.14 / Linux environment, zlib1.3.2 for identical
compressed containers, and the unchanged numerical version lock:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_REPRODUCTION.py --verify-only

To execute another complete 19-cell replay with fresh exclusive outputs:

    .venv/bin/python RUN_REPRODUCTION.py --run --prefix my_fresh_replay

Use the matching virtual-environment Python path on your platform; the exact
reproduction claim is for the recorded Linux/pinned environment. Allow several
GB of temporary disk space for restored originals and shared decompression.
The supplied dependency lock pins versions without distribution hashes.

The original frozen CLI runners and all their SHA/Git checks remain enabled.
Because source ZIPs contain no .git history, the bootstrap creates a clearly
labeled LOCAL input-staging commit. It is not a historical commit reconstruction
or external reviewer signature. In a full checkout this step is unnecessary.

REVIEW.zip is an optional SMALL code/policy/report subset with no raw payloads.
It cannot substitute for complete replay or recovery. The outer complete ZIP
contains all payloads and manifests. Earlier historical pending-approval text
is preserved; direct user consultation/authorization governs this technical
release. No further administrative approval is requested.

Official A3 comparisons were not started. Level1 is not established. Numerical
GO applies only to the precisely frozen A2 experiments; it is not a general
solver-domain, all-time, hardware, optimized-planner or publication theorem.
