# IC2AI 2027 active-filter sampled-data remediation v1

Read panda_research/reports/active_sampled_data_v1/ACTIVE_FILTER_GATE_DECISION.md
and ACTIVE_FILTER_REFINEMENT_ROOT_CAUSE.md in that folder. All 19 frozen A2
cells freshly pass, with 120/120 refinement fields. T27 freshly passes 39
finite fixtures. All eight original active-filter failures reproduce exactly.
The separate genuinely active alpha10 challenge fails four peak comparisons.
Active-filter qualification and A3 are NO-GO; no Level1 or external signatures.

The moving-face local defect predicts the measured energy difference within
0.2% and peak difference within 1.2%, without fitting final outcomes. This is
conditional analysis and numerical attribution, not universal impossibility
or an interval safety certificate. Production control, original thresholds,
all 2644 prior tracked files and all failed experiments are unchanged.
The explicitly versioned first-order/hold-policy alternatives are proposals.

There are two downloads. ACTIVE_FILTER_REPRODUCTION.zip is the small runnable
source/analysis/T27 package, with no raw trace payloads. The full evidence ZIP
adds ALL new raw histories (27 simulation cells), all analysis arrays, retained
offline-analysis failures, and eight older raw traces used for exact historical
comparison. It restores exact original CTZ, gzip and NPZ bytes, not rounded or
downsampled data. Older complete history remains in HISTORICAL_ANNEX.json;
it is linked, not redundantly included. The small ZIP alone is not the complete
raw-evidence package. Raw evidence parts are <=20MiB for reliable downloads.

Use Linux and the exact recorded Python3.12.14 / pinned dependencies:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_ACTIVE_FILTER.py --verify-only
    .venv/bin/python RUN_ACTIVE_FILTER.py --run-numerics --prefix independent_local_replay

The numerical command runs six mathematical plus three clock tests and the
39 exact KKT/Farkas solver fixtures. It needs no large evidence download.
“Local replay” is not an invented independent reviewer or signature.

From the FULL package, restore and recompute the trace analysis:

    .venv/bin/python RUN_ACTIVE_FILTER.py --restore --verify-only
    .venv/bin/python RUN_ACTIVE_FILTER.py --analyze-traces --prefix trace_replay

Restoration is standard-library-only, checks every original SHA, and refuses
to overwrite changed files. Exact container restoration uses the recorded
zlib1.3.2. Analyze-traces reruns the corrected read-only operator analysis and
modified-equation propagation. Failed gates remain failed during reproduction.

For all FRESH physical simulations using the original historical CLI provenance
checks, use the actual versioned source checkout; no fake Git history is made:

    git clone --branch active-sampled-data-v1 https://github.com/khanhcongtruong8a4-prog/project.git
    cd project/panda_research
    python scripts/replay_guarded_qp_reliability.py --prefix your_fresh_23
    python scripts/run_active_sampled_challenge_v1.py --output runs/active_sampled_data_v1/your_alpha10

Use the installed pinned Python for those commands. Prefixes/directories must
be new. The first command really runs seven original, twelve v4 and four legacy
active cells, and is EXPECTED to exit3 because the eight failures persist. The
second runs the separately frozen harder active alpha10 case and is EXPECTED
to exit3 because four peak comparisons fail. These are successful reproductions
of failed experiments, never a promotion to acceptance. The small ZIP does not
include the huge earlier source/input history needed by those frozen CLI hash
checks. Full checkout and older annex are explicitly separate provenance inputs.

No command in this package runs official A3 comparisons or claims Level1.
Neither a stored witness nor an unsafe extrapolated torque is a runtime fallback.
Wall-clock statistics under shared cloud load do not qualify a 1ms deadline.
M1 bounds and G2.5 planner start feasibility remain independent NO-GO gates.
