# Repair the audit input boundary; retain the actual motion evidence

All seven physical cells of the frozen `9c94b06` run completed, including their
preholds, actual endpoint QPs and individual A2 checks. The runner then passed
an in-memory dictionary containing NumPy arrays to a read-only auditor that
expects serialized JSON data. Ordinary dictionary equality on those arrays
raised a ValueError. The initial run correctly ended with engineering exit 1
and gate HOLD. Its errors, gate and complete physical traces are preserved.

Fix only the runner's audit interface: read its just-written cell JSON before
calling the unchanged auditor. Do not modify the controller, audit inequalities,
physical code, task, grid, thresholds or plan. Add a contract for this boundary
and for refusal to reuse missing/unverified executions. Freeze the changed
runner and tests before qualification. The initial freeze and failed contracts
remain in history and evidence; no failed result is retrospectively relabeled.

An explicitly requested `--reuse-executed-cells` path supports requalification
of this already executed motion without claiming another simulation or another
reviewer. Require a completed source run with unchanged frozen inputs, identical
plan and pinned versions, the exact seven cell grids, and equality of every
original input hash except this runner's evidence-interface code and its tests.
The complete controller/auditor module must be byte-identical. Copy and verify
the original trace hashes, recompute every numerical check and both refinement
cohorts, and record the source execution's freeze commit and metadata hashes.
No missing or failing motion may be replaced. Qualification outputs use a new
exclusive run directory; initial errors and gate HOLD remain unchanged.

The default command performs a fresh physical run with the repaired interface.
The reuse command performs trace audit and qualification of the earlier run:

```bash
python scripts/p1_r4.py --contracts <passing-contract-report>
python scripts/p1_r4.py --contracts <passing-contract-report> --reuse-executed-cells runs/p1_r4/frozen_9c94b06
```

This repairs an engineering data-representation bug. It changes no scientific
acceptance criterion and invents no independent signature. The same frozen
numerical gate determines GO or HOLD from the verified evidence.
