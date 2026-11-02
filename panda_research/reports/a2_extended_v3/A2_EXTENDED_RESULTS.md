# A2-Extended v3: PARTIAL; numerical gate NO-GO

Computed from twelve separately prepared fixed cells: E1 **PASS**, E2 **PASS**, E3 **FAIL**. This is local numerical simulation evidence. The original r4 result and every earlier failure remain unchanged.

Predeclaration SHA-256: `fdf300e88b14e4e02802c7e2406928a801c2bf77f3af877359a2a5e9cf54f650`. Motion source freeze: `aec8e86`. All original grids, reference amplitudes/durations, model, gains, observer/disturbance semantics, energy model and acceptance inequalities were retained.

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
| E3 | 0 | 1/0.25 | PASS | 1 | 1.1770856895 | 0.525445162501 | — |
| E3 | 1 | 1/0.125 | PASS | 1 | 1.17708568954 | 0.525445159317 | — |
| E3 | 2 | 0.5/0.25 | PASS | 1 | 1.17707158785 | 0.525271419722 | — |
| E3 | 3 | 0.5/0.125 | PASS | 1 | 1.17707158789 | 0.525271416532 | — |

Incomplete-cell energy is only the executed-prefix integral. Its distance to the declared final target is an abort-state diagnostic; it is never terminal accuracy at T. The legacy raw metric key `actual_terminal_error_m` exists for both completed and aborted runs; the CSV above separates their meanings.

## Every refinement pair

| Case | 0–1 (h) | 2–3 (h) | 0–2 (Delta) | 1–3 (Delta) | 0–3 diagonal | 1–2 diagonal |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | PASS | PASS | PASS | PASS | PASS | PASS |
| E2 | PASS | PASS | PASS | PASS | PASS | PASS |
| E3 | PASS | PASS | FAIL | FAIL | FAIL | FAIL |

All four fixed-factor edges and both diagonals must pass for a reference GO. Each checks energy, elapsed duration, max ||tau-u|| and minimum normalized raw row using `abs(a-b) <= max(approved_absolute, 1e-4*max(abs(a),abs(b)))`. Absolute floors remain energy 1e-6 J, duration 1e-6 s, intervention 1e-7 N m and normalized slack 1e-6. Actual terminal position tolerance remains 1 mm and planned 1e-6 m. A raw negative remains a failure at any magnitude.

`A2_EXTENDED_REFINEMENT.csv` retains every numerical pair, threshold and metric result. `ALL_NEGATIVE_SLACKS.json` lists every retained negative. Each completed cell has the unchanged r4 mathematical trace audit with only the lossless input loader adapted. Full P1/update/RK4 stage/endpoint logs, original matrices/slacks, state/observer signals, references, r/u/tau, signed analysis-only truth, energy and source/environment/command metadata are retained in the run directories.

## Explicit causal digital QP amendment

v2 completed all twelve individual cells, but E3 failed energy and intervention refinement on both Delta edges and both diagonals. The complete failed-refinement evidence remains in `../a2_extended_v2/`. It was not relabeled, removed or used to reduce a reference or relax an acceptance threshold.

v3 retains the same nominal AB2 request u and applies the same causal interval rule to G and c: bootstrap uses current rows, then B_interval=B_current+0.5(B_current-B_previous). The single actual 43-row QP targets G_interval*tau+c_interval >= (0.1+1e-8)*original_row_scale. The fixed 0.1 is an explicit engineering inward reserve, not a certified M1 drift constant. This changes the digital safety-QP realization and is scoped/versioned as such.

Before any returned torque can be applied, all 43 ORIGINAL current-state inequalities G_current*tau+c_current >=0 are separately recomputed with no tolerance exception. Only the exact QP candidate is held; no post-QP extrapolation, clipping, retry or backup actuation occurs. The full bootstrap QP is solved at the actual P1 endpoint and reused for the first application.

The unchanged 1e-9 T29 numerical targets apply to the ACTUAL declared interval QP. Its retained duals and causal row history are recomputed by the extra audit, alongside the original current-state hard-row audit. Original-instantaneous-QP stationarity is not falsely claimed for a different optimization problem. The actual solved G/c and the original current G/c are both retained for every update.

All ten v3 pre-motion contracts and 6000 read-only v2 E3-matrix queries passed before the v3 freeze. Those read-only old-state queries are development qualification, not v3 motion or refinement results. This report uses only the separately executed complete v3 campaign for its outcome.

This is a local numerical result for the explicit new sampled controller and fixed references, not a retroactive GO for v1/v2 or proof of the original continuous-time theorem. The user acceptance statement is retained verbatim; no external reviewer identity or signature artifact has been invented.

## Repeatability and limits

The original seven-cell 0.25 s baseline was reproduced exactly in a separate clean checkout/fresh pinned venv on the same machine; see `../a2_extended_v1/BASELINE_REPRODUCTION.md`. Each new extension cell was executed once. Refinement is a resolution comparison, not repeated independent reproduction. No unexecuted repeat run is claimed.

The C2 reversal, fixed references and pointwise audits do not establish all-time true-ODE safety, a sampled-data theorem, hardware behavior, optimized planner/filter consistency, A3 readiness or Level 1 certification. Sampler interpretation requires the separately attributable theory/controls decision in `SAMPLER_THEORY_SCOPE.md` and `REVIEW_REQUEST.md`.
