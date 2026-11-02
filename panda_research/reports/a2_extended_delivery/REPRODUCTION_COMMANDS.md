# Reproduction commands and scope

Actual commands, timestamps, source/package/machine hashes and failed logs are retained in each run/report directory. Use NEW exclusive output paths; original records must not be overwritten.

On a full checkout of the source branch with the pinned Python 3.12.14 environment:

```bash
cd panda_research
python -m pip install -r requirements.lock.txt
python -m pip install setuptools==80.9.0
python -m pip install --no-deps --no-build-isolation -e .
python tests/test_a2_policy_v4.py --report /tmp/new-v4-contracts.json
python scripts/a2_extended_v4.py --reference E1 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E1
python scripts/a2_extended_v4.py --reference E2 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E2
python scripts/a2_extended_v4.py --reference E3 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E3
```

Python/NumPy/CasADi/SciPy/ProxQP/pin/MuJoCo versions are pinned by the recorded runtime, lock and package inventories. The supplied dependency lock pins versions without distribution hashes; it is not a hashed supply-chain lock. Source configuration/model hashes are separately verified by every runner. Runtime setup/reproduction details are in BASELINE_REPRODUCTION.md and its install logs.

The ZIP is a complete NEW-evidence/code overlay plus unchanged runtime context, not a duplicate of every old baseline archive. Strict full-run freeze verification also requires the immutable original checkout at 45d1ada with its older archival files. The source branch retains that ancestry/data. Baseline old failures were not deleted to shrink the ZIP.

Restore the shared compressed evidence using the top-level standard-library helper:

```bash
python archive_evidence.py restore --evidence evidence --destination . --report restored-proof.json
```

It reconstructs all original CTZ files at their recorded paths and verifies byte SHA-256, schemas, arrays and original container metadata. A differing existing file is never overwritten. Exact container rebuilding was tested on Python3.12.14 / zlib1.3.2. The scientific bytes are losslessly archived; recreating identical compressed containers requires compatible zlib. The pinned numerical environment is also needed for exact numerical replay.

Use `src/panda_closed_loop/trace_archive.py:read_trace` for retained native records, and `runs/a2_extended_baseline_clean_ctz/restore_json.py` when original baseline JSON/gzip bytes are needed. No raw-trace subset is represented as a complete reproduction.
