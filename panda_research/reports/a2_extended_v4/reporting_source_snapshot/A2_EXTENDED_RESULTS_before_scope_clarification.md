# A2-Extended v4: PASS; numerical gate GO

Computed from twelve separately prepared fixed cells: E1 **PASS**, E2 **PASS**, E3 **PASS**. This is local numerical simulation evidence. The original r4 result and every earlier failure remain unchanged.

Predeclaration SHA-256: `f4f6466db39758f6256303bd609afd6480e8e4534216e8811b420a72b03ac591`. Motion source freeze: `c02f908`. All original grids, reference amplitudes/durations, model, P1/Slotine-Li/observer gains, observer/disturbance semantics, energy model and pass tolerances were retained. Velocity-CBF alpha_v changes 5→10 in the explicit amendment below.

| Case | Cell | Delta/h ms | Cell+audit | Executed s | Energy J | Terminal error at 1 s mm | Abort distance mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 0 | 1/0.25 | PASS | 1 | 0.263004551044 | 0.525345144458 | — |
| E1 | 1 | 1/0.125 | PASS | 1 | 0.263004551117 | 0.525345141453 | — |
| E1 | 2 | 0.5/0.25 | PASS | 1 | 0.263003696454 | 0.525207102597 | — |
| E1 | 3 | 0.5/0.125 | PASS | 1 | 0.263003696527 | 0.525207099586 | — |
| E2 | 0 | 1/0.25 | PASS | 1 | 0.209611297069 | 0.475954311562 | — |
| E2 | 1 | 1/0.125 | PASS | 1 | 0.209611297156 | 0.4759543089 | — |
| E2 | 2 | 0.5/0.25 | PASS | 1 | 0.20961059806 | 0.475734178176 | — |
| E2 | 3 | 0.5/0.125 | PASS | 1 | 0.209610598146 | 0.475734175511 | — |
| E3 | 0 | 1/0.25 | PASS | 1 | 1.15590661209 | 0.518762307035 | — |
| E3 | 1 | 1/0.125 | PASS | 1 | 1.15590661204 | 0.518762304074 | — |
| E3 | 2 | 0.5/0.25 | PASS | 1 | 1.15589673931 | 0.518561100543 | — |
| E3 | 3 | 0.5/0.125 | PASS | 1 | 1.15589673926 | 0.51856109758 | — |

Incomplete-cell energy is only the executed-prefix integral. Its distance to the declared final target is an abort-state diagnostic; it is never terminal accuracy at T. The legacy raw metric key `actual_terminal_error_m` exists for both completed and aborted runs; the CSV above separates their meanings.

## Every refinement pair

| Case | 0–1 (h) | 2–3 (h) | 0–2 (Delta) | 1–3 (Delta) | 0–3 diagonal | 1–2 diagonal |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | PASS | PASS | PASS | PASS | PASS | PASS |
| E2 | PASS | PASS | PASS | PASS | PASS | PASS |
| E3 | PASS | PASS | PASS | PASS | PASS | PASS |

All four fixed-factor edges and both diagonals must pass for a reference GO. Each checks energy, elapsed duration, max ||tau-u|| and minimum normalized raw row using `abs(a-b) <= max(approved_absolute, 1e-4*max(abs(a),abs(b)))`. Absolute floors remain energy 1e-6 J, duration 1e-6 s, intervention 1e-7 N m and normalized slack 1e-6. Actual terminal position tolerance remains 1 mm and planned 1e-6 m. A raw negative remains a failure at any magnitude.

`A2_EXTENDED_REFINEMENT.csv` retains every numerical pair, threshold and metric result. `ALL_NEGATIVE_SLACKS.json` lists every retained negative. Each completed cell has the unchanged r4 mathematical trace audit with only the lossless input loader adapted. Full P1/update/RK4 stage/endpoint logs, original matrices/slacks, state/observer signals, references, r/u/tau, signed analysis-only truth, energy and source/environment/command metadata are retained in the run directories.

## Declared numerical correction and stronger audit

The v2 amendment solves with isotropic physical-torque scaling, positive Euclidean row scaling, a 1e-8 original-normalized inward constraint guard, eps_abs 1e-12 and a checked duality gap. All 43 ORIGINAL raw inequalities still gate application. This is an explicit new numerical constraint tightening and solver realization, not an unchanged original solver claim. There is one cold query per update, no post-QP projection, retry, warm-start history or fallback.

Both original-T29 and guarded-problem primal/stationarity residuals, guarded complementarity and dual signs are recomputed from retained dual vectors for every completed update. The original mathematical controller/plant/audit rules and raw zero-negative criterion also pass only when the records show that. The guard is a numerical target, with measured floating residual, not a certified solver-error bound.

All 14 pre-motion v2 contracts passed after correcting an invalid exact-invariance fixture: its initial noninteger powers changed the input coefficients by one ulp. That failed log remains alongside the corrected integer-power fixture. The five original failed matrices passed read-only v2 qualification before any new motion.

The user acceptance statement is recorded in the new predeclaration. External reviewer identity/signature artifacts were not supplied; those fields remain null. Numerical acceptance, user acceptance and independently evidenced controls/theory review are distinct records.

## Explicit velocity-barrier gain change

This numerical GO, if computed above, is for the v4 filter design: velocity-CBF alpha_v doubles from 5 to 10 s^-1. It expands the robust acceleration admissibility inside the SAME physical speed limits. It is a controller/barrier policy change, not a preserved-alpha_v5 claim, a physical-model edit or a change of pass tolerances. The new configuration is separately frozen; original approved policy bytes remain intact.

All other gains, observer envelope, P1 procedure, fixed references, C4 grid, terminal tolerances and refinement thresholds remain unchanged. The actual QP is the qualified v2 CURRENT-STATE guarded QP. There is no v3 interval-row correction or added 0.1 reserve. The ten pre-motion v4 contracts and 6000 old-state nominal-feasibility screens passed before the new freeze; they are not counted as v4 motion evidence.

For transparency, each full cell audit also evaluates all OLD alpha_v5 rows on the v4 states and applied torques. Any negative shadow values remain in `audit.barrier_gain_amendment.old_alpha5_shadow_negatives`. They are explicitly unused OLD-POLICY diagnostics; we do not claim the old filter design passed this new motion. Actual v4 negative raw rows still fail without any tolerance exception.

v1, v2 and v3 outcomes stay PARTIAL/NO-GO for their full suites. Their complete failed/aborted traces and all failed comparisons remain in the package. This separates a new successful design, when actually shown, from retrospectively approving an earlier failed experiment.

## Repeatability and limits

The original seven-cell 0.25 s baseline was reproduced exactly in a separate clean checkout/fresh pinned venv on the same machine; see `../a2_extended_v1/BASELINE_REPRODUCTION.md`. Each new extension cell was executed once. Refinement is a resolution comparison, not repeated independent reproduction. No unexecuted repeat run is claimed.

The C2 reversal, fixed references and pointwise audits do not establish all-time true-ODE safety, a sampled-data theorem, hardware behavior, optimized planner/filter consistency, A3 readiness or Level 1 certification. Sampler interpretation requires the separately attributable theory/controls decision in `SAMPLER_THEORY_SCOPE.md` and `REVIEW_REQUEST.md`.
