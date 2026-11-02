# A2-Extended v1: PARTIAL; numerical gate NO-GO

Computed from twelve separately prepared fixed cells: E1 **FAIL**, E2 **PASS**, E3 **FAIL**. This is local numerical simulation evidence. The original r4 result and every earlier failure remain unchanged.

Predeclaration SHA-256: `14c0e0e3e2c42461c36dc2aa0aea5b2f25d174c42cf6f350cad9aa53d659e9e9`. Motion source freeze: `e4267be`. All original grids, reference amplitudes/durations, model, gains, observer/disturbance semantics, energy model and acceptance inequalities were retained.

| Case | Cell | Delta/h ms | Cell+audit | Executed s | Energy J | Terminal error at 1 s mm | Abort distance mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 0 | 1/0.25 | PASS | 1 | 0.263004551391 | 0.525344802743 | — |
| E1 | 1 | 1/0.125 | FAIL | 0.998 | 0.260350937775 prefix | — | 0.52661914884 |
| E1 | 2 | 0.5/0.25 | PASS | 1 | 0.2630036968 | 0.525206760966 | — |
| E1 | 3 | 0.5/0.125 | PASS | 1 | 0.263003696872 | 0.525206757935 | — |
| E2 | 0 | 1/0.25 | PASS | 1 | 0.209611297352 | 0.475953993622 | — |
| E2 | 1 | 1/0.125 | PASS | 1 | 0.209611297438 | 0.475953990941 | — |
| E2 | 2 | 0.5/0.25 | PASS | 1 | 0.209610598343 | 0.475733860128 | — |
| E2 | 3 | 0.5/0.125 | PASS | 1 | 0.20961059843 | 0.475733857439 | — |
| E3 | 0 | 1/0.25 | FAIL | 0.095 | 0.106915073317 prefix | — | 2.89801930019 |
| E3 | 1 | 1/0.125 | FAIL | 0.076 | 0.0829264592521 prefix | — | 1.57602538886 |
| E3 | 2 | 0.5/0.25 | FAIL | 0.0925 | 0.103628988178 prefix | — | 2.69744368517 |
| E3 | 3 | 0.5/0.125 | FAIL | 0.02 | 0.0212749433681 prefix | — | 0.0320900508672 |

Incomplete-cell energy is only the executed-prefix integral. Its distance to the declared final target is an abort-state diagnostic; it is never terminal accuracy at T. The legacy raw metric key `actual_terminal_error_m` exists for both completed and aborted runs; the CSV above separates their meanings.

## Every refinement pair

| Case | 0–1 (h) | 2–3 (h) | 0–2 (Delta) | 1–3 (Delta) | 0–3 diagonal | 1–2 diagonal |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | INCOMPLETE | PASS | PASS | INCOMPLETE | PASS | INCOMPLETE |
| E2 | PASS | PASS | PASS | PASS | PASS | PASS |
| E3 | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |

All four fixed-factor edges and both diagonals must pass for a reference GO. Each checks energy, elapsed duration, max ||tau-u|| and minimum normalized raw row using `abs(a-b) <= max(approved_absolute, 1e-4*max(abs(a),abs(b)))`. Absolute floors remain energy 1e-6 J, duration 1e-6 s, intervention 1e-7 N m and normalized slack 1e-6. Actual terminal position tolerance remains 1 mm and planned 1e-6 m. A raw negative remains a failure at any magnitude.

`A2_EXTENDED_REFINEMENT.csv` retains every numerical pair, threshold and metric result. `ALL_NEGATIVE_SLACKS.json` lists every retained negative. Each completed cell has the unchanged r4 mathematical trace audit with only the lossless input loader adapted. Full P1/update/RK4 stage/endpoint logs, original matrices/slacks, state/observer signals, references, r/u/tau, signed analysis-only truth, energy and source/environment/command metadata are retained in the run directories.

## Failed outcomes retained

E1 cell 1 stopped at 0.998 s on PROXQP_PRIMAL_INFEASIBLE. Separate HiGHS and exact-dyadic interior-witness analysis demonstrates strict feasibility of its stored affine coefficients. The solver status is therefore not evidence that the recorded feasible set is empty. There was no fallback, retry or subsequent state advance.

E3 cells 0/1/2 stopped at 0.095/0.076/0.0925 s on solved candidates with negative v_upper_3 rows. Cell 3 stopped at 0.020 s on MAX_ITER_REACHED, with no returned candidate. All four stopped before the 0.5 s reversal. The reversal profile is defined but its physical second phase was not exercised in v1.

Every executed failed prefix was subsequently audited read-only, including controller/observer/43-row reconstruction, original signs, actual held inputs, RK4 stage and endpoint arithmetic, cubic interpolant extrema, all physical/envelope samples, energy and fail-closed continuity. All five prefix-data audits PASS. This does not provide a completed horizon or change a scientific FAIL. See `prefix_audits/` and `ACTUAL_EXTENDED_QP_DIAGNOSTICS.md`. The diagnostic witnesses are not new actuation or exact-model certificates.

The later user authorized a separate numerical-solver correction. v2 has a new pre-motion commit, policy and full separate run directories. No v1 case was overwritten or relabeled.

## Repeatability and limits

The original seven-cell 0.25 s baseline was reproduced exactly in a separate clean checkout/fresh pinned venv on the same machine; see `../a2_extended_v1/BASELINE_REPRODUCTION.md`. Each new extension cell was executed once. Refinement is a resolution comparison, not repeated independent reproduction. No unexecuted repeat run is claimed.

The C2 reversal, fixed references and pointwise audits do not establish all-time true-ODE safety, a sampled-data theorem, hardware behavior, optimized planner/filter consistency, A3 readiness or Level 1 certification. Sampler interpretation requires the separately attributable theory/controls decision in `SAMPLER_THEORY_SCOPE.md` and `REVIEW_REQUEST.md`.
