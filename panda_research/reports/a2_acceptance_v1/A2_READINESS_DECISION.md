# A2 numerical readiness: GO for the precisely verified scope

Original A2 r4: seven cells freshly reproduced with all original/finer-cohort
checks. A2-Extended v4: E1/E2/E3 all reproduced across four C4 cells each,
with all 18 pairs / 72 metrics. All 19 metrics/state/complete scientific
trace comparisons are exact when only solver wall time is excluded.
These are local replays in a fresh checkout and pinned environment on the
same machine, not externally independent verification. All 2018
prior tracked source/evidence files remain unchanged.

Worst v4 terminal error: 0.525345144458 mm.
Minimum v4 normalized actual raw slack: 0.660765017403.
Maximum v4 scaled stationarity: 4.99600361081e-16.
Full endpoint QPs, all scheduled updates and retained RK4 samples were audited.

The existing AB2 nominal sampler, alpha_v=10 v4 speed-barrier design and
guarded current-state QP are frozen, without new gains, guard/tolerance,
reference, duration, model or energy changes. The positive-gain barrier and
QP transformations are checked mathematically. AB2 is a causal request
sampler; no continuous-theorem transfer is inferred. Three separate torque
differences, with per-cell max/RMS, are in SAMPLER_MAX_RMS.csv.

**One extra numerical solver probe FAILS and remains FAIL.** A preserved
alpha5 active fixture has an exact represented-QP optimum, but the guarded
solver reports infeasibility and stops with no torque. The selected original
alpha5 protocol uses its original solver, and v4 uses alpha10, so this hybrid
probe is outside both frozen experiment definitions. That scope separation
and known failure were explicitly predeclared before these fresh replays.
It blocks general guarded-QP/T27 qualification; it is not hidden, marked
passed, or used as a reason to erase successful unchanged numerical runs.
See GUARDED_QP_BLOCKER.json for the exact witness and remedy requirements.

User consultation/authorization is recorded. Additional administrative
approval is not requested. Attributable external reviewer names/signatures
were not supplied and remain null. Earlier pending-approval wording in
preserved historical reports is not a new administrative block here.

The final versioned policy is policy/a2_verified_v1/FINAL_A2_POLICY.json.
Its numerical GO is limited to the listed fixed experiments. General QP
qualification remains HOLD. Official A3 comparisons were not started and
remain NO-GO; Level1 certification is not established.
