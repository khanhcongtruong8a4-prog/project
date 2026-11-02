# QP/bounds preparation execution record

Verification status: source inspected and DEVELOPMENT fixtures EXECUTED LOCALLY. No human or official A3 acceptance is inferred.

Commands from `/workspace/a2-extended/panda_research`:

```bash
/workspace/panda-venv/bin/python tests/test_a3_qp_bounds.py --report reports/a2_extended_v1/qp_bounds_evidence/contracts_v3.json
/workspace/panda-venv/bin/python scripts/a3_qp_bounds.py --output reports/a2_extended_v1/qp_bounds_evidence/run_v2
/workspace/panda-venv/bin/python scripts/a3_qp_bounds_tables.py reports/a2_extended_v1/qp_bounds_evidence/run_v2
```

Use fresh output paths on repetition; no file is silently overwritten. The final contract command executed 15 tests and passed. Earlier 13-test reports/logs remain preserved.

The first uncapped campaign at run_v1 consumed over three minutes without returning and was stopped before any case-level output had been emitted. It is not counted as a complete campaign. Its run_started metadata, original source snapshot and INTERRUPTION.json remain intact. The correction adds subprocess time limits and per-case streaming, not changed physics, QP thresholds or target oracles. The completed run_v2 has 18 T27 development fixtures and 20 G2.5 points. All three expected infeasible cases are identified by ProxQP and a separate HiGHS LP. Five active-boundary raw-sign failures and two screen timeouts remain explicit.

Full raw matrices, candidates, slacks, KKT metrics, source hashes and environment versions are retained in the JSON evidence. No plant state or official A3 comparison is advanced by these tools. Actual M1 numerical bound values/domain choices remain absent; synthetic unit values never become official data.
