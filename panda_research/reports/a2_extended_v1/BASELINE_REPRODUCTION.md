# Original A2 baseline reproduction

**The original narrow A2 numerical GO was reproduced exactly in a clean Git
worktree and fresh pinned virtual environment. This is EXECUTED LOCALLY
engineering evidence, not an independently human-reviewed acceptance.**

Baseline commit: `45d1adae85f4f2484202792041e080fa54e23962`. The complete original checkout and
raw traces were available; this reproduction did not rely on compact A2.zip.
No baseline source, parameter, policy, threshold, reference, archived failure,
result pointer or signed-input file was edited.

## What was actually executed

- Fresh detached checkout: `/workspace/a2-baseline-clean` at 45d1ada.
- New venv: `/workspace/a2-baseline-venv`, Python 3.12.14, exact
  `requirements.lock.txt` plus setuptools 80.9.0 and the unchanged editable
  package. Pip dependency check PASS. Installation preserves TLS/checksums.
- All 14 original r4 contracts PASS.
- The unmodified `scripts/p1_r4.py` was run without reuse on the full original
  seven-cell grid. Every 0.156 s P1 hold, measured zero-endpoint 43-row QP,
  0.25 s A2 motion and trace audit PASS. The computed gate is GO, exit 0.
- All seven metric dictionaries, measured zero states and final states match
  the original `runs/p1_r4/fresh_2fe50b9` values exactly. There are no nonzero
  numerical differences in the declared comparisons. Both original C4 and
  finer-confirmation refinement cohorts pass their unchanged inequalities.
- All 1236 original tracked file hashes remain
  unchanged. The fresh run also records its own frozen-input integrity PASS.

The exact comparison rule was saved before the physical run in
[PREDECLARED_BASELINE_REPRODUCTION.json](baseline_reproduction/PREDECLARED_BASELINE_REPRODUCTION.json),
SHA-256 `cb7c5d5541c1778957563e5d31a825dfdc5e0ec21f61598db6345c2af0287133`. Its primary criterion is exact
agreement; approved-tolerance comparisons were only a diagnostic fallback,
not a way to relabel nonexact results. Exact agreement was obtained.

This is a separate clean source checkout and fresh venv on the **same managed
cloud machine**. A separately provisioned machine was not used. The environment
was not copied from the original venv: locked dependencies were installed anew
using the verified package cache/proxy. Full package inventories are in the
run metadata. The only inventory difference is that the fresh environment
omits optional PyBullet 3.2.7, which the A2 workflow does not import or use.
All locked numerical/solver package versions match.

## Inventory and source status

[BASELINE_INVENTORY.json](baseline_reproduction/BASELINE_INVENTORY.json)
records the exact original reference, P1 controller/windows, gains,
initialization, signed disturbance clock, observer convention, reserves,
energy model, solver settings, seven cells, cohort map and thresholds. The
working model is the unchanged Gaz seven-body evaluator. Canonical equation
source checks were executed by the baseline runner. Existing manuscript-build
acceptance discrepancies remain outside this numerical reproduction.

| Evidence | Verification status |
| --- | --- |
| Complete original checkout and recorded raw data | SOURCE VERIFIED, available locally |
| Original report's GO and its historical values | LOG-REPORTED; preserved unchanged |
| Current model/policy/source hashes and pinned versions | SOURCE VERIFIED |
| Original 14 contract tests | EXECUTED LOCALLY, PASS |
| Fresh full seven-cell P1/A2 run and audits | EXECUTED LOCALLY, PASS |
| Exact metric/endpoint/final-state comparisons | EXECUTED LOCALLY, exact PASS |
| Separately provisioned-machine reproduction | NOT VERIFIED / not performed |
| Independent controls/theory human acceptance | NOT VERIFIED; signatures remain blank |
| Hardware/sampled-delay guarantees, all-time certification | NOT VERIFIED / not claimed |

## Separate digital, filter and total differences

The table uses the Euclidean norm over seven joints at each applied control
update. RMS means `sqrt(mean_k(||x_k||_2^2))`. Since Delta is constant within
an individual cell, the time-weighted ZOH-interval RMS is mathematically the
same: `sqrt(sum_k Delta*||x_k||_2^2 / sum_k Delta)`. This describes sampled
requests r_k and u_k, not an unobserved continuous r(t) between updates.

| Cell | Delta ms | h ms | max ||u-r|| Nm | RMS ||u-r|| Nm | max ||tau-u|| Nm | max ||tau-r|| Nm |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 0.25 | 0.00281078051987 | 0.00169109078553 | 3.79165521203e-09 | 0.00281078004003 |
| 1 | 1 | 0.125 | 0.00281078060735 | 0.0016910907969 | 3.80389564292e-09 | 0.00281078012751 |
| 2 | 0.5 | 0.25 | 0.00142112719739 | 0.000846613952262 | 3.79314557542e-09 | 0.00142112672435 |
| 3 | 0.5 | 0.125 | 0.0014211272442 | 0.000846613958031 | 3.79314579746e-09 | 0.00142112677117 |
| 4 | 0.5 | 0.0625 | 0.00142112724705 | 0.000846613958398 | 3.80362452646e-09 | 0.00142112677401 |
| 5 | 0.25 | 0.125 | 0.000714184227836 | 0.000423555277938 | 3.80438058834e-09 | 0.000714183758245 |
| 6 | 0.25 | 0.0625 | 0.000714184229301 | 0.000423555278121 | 3.80438081038e-09 | 0.000714183759716 |

[BASELINE_SAMPLER_DIFFERENCES.json](baseline_reproduction/BASELINE_SAMPLER_DIFFERENCES.json)
contains max/RMS for **all three** vector differences and componentwise
statistics, with each cell's grid and update count. Small `tau-u` supports
negligible filter intervention **relative to digital request u**, not equality
of applied torque with the continuous controller request r. No sampled-data
stability theorem or independent reviewer approval is inferred.

## Reproduction and preserved evidence

The new full raw run is at:
`/workspace/a2-baseline-clean/panda_research/runs/p1_r4/baseline_clean_reproduction_v1`.
Its complete compressed P1/execution traces, actual endpoints, QP matrices,
slacks, state/observer histories, source snapshots, package inventory and audit
records remain intact. Packaging may losslessly transcode them; the package
manifest/decoder must preserve original raw JSON bytes and source hashes.

Actual commands, with the clean checkout's `panda_research` as working directory:

```bash
/workspace/a2-baseline-venv/bin/python tests/test_p1_r4.py --report /workspace/a2-extended/panda_research/reports/a2_extended_v1/baseline_reproduction/contracts_fresh.json
/workspace/a2-baseline-venv/bin/python scripts/p1_r4.py --contracts /workspace/a2-extended/panda_research/reports/a2_extended_v1/baseline_reproduction/contracts_fresh.json --output runs/p1_r4/baseline_clean_reproduction_v1
python /workspace/a2-extended/panda_research/reports/a2_extended_v1/baseline_reproduction/compare_clean_baseline.py
```

The paths above identify the actual run; use fresh exclusive paths to rerun.
Installation, contracts, physical-run and comparison logs are retained in
`baseline_reproduction/`. [BASELINE_REPRODUCTION_RESULTS.json](baseline_reproduction/BASELINE_REPRODUCTION_RESULTS.json)
contains the source/run SHA-256 values and all seven comparisons; the
[comparison CSV](baseline_reproduction/BASELINE_COMPARISON.csv) is suitable
for review. Prior r2/r3 failures and original A2 inputs/results remain intact.

Independent controls reviewer signature: **null**. Independent theory reviewer
signature: **null**. Reproduction by this development agent does not fill
another person's sign-off fields. The existing narrow numerical A2 remains
GO; independent A2 acceptance remains HOLD pending genuine human review.

## Explicit time weighting and lossless archive

[BASELINE_SAMPLER_TIME_WEIGHTED.json](baseline_reproduction/BASELINE_SAMPLER_TIME_WEIGHTED.json)
separately evaluates the explicit Delta-weighted RMS formula for all three
vector differences in all seven cells, alongside uniform-update RMS. The
analysis helper and command log are retained. Every weighted cell duration is
0.25 s. Small representation-level differences between the mathematically
equivalent summation forms are floating-point summation effects, not a new
acceptance test.

A lossless archival copy of all 14 new baseline trace streams and unchanged
nontrace metadata/source snapshots is at
`runs/a2_extended_baseline_clean_ctz/`. Its `TRANSCODE_INDEX.json` links every
original gzip and raw JSON SHA-256 to the new CTZ checksum. All 14 raw JSON
streams and original gzip files were reconstructed exactly on the recorded
Python3.12.14/zlib1.3.2 runtime; the original gzip inputs remain intact. The
standalone restore helper was separately executed on cell 0 and its exact
gzip byte equality recorded in `baseline_reproduction/RESTORE_CHECK.json`.
CTZ totals 67,126,256 bytes versus 84,196,147 bytes for source gzip streams.
This is a reversible archival encoding change, not a rerun or policy change.
