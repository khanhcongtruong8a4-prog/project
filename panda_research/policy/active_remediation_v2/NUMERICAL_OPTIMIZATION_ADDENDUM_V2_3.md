# v2.3 completion optimization and acceptance scope

The immutable earlier versions and their failures remain in Git and run history.
V2 failed at a dense-output adapter. V2.1 stopped at 0.023 s because unit-normal
scaling concealed a 2.000159006e-9 original-scale guarded residual. V2.2 stopped
at 0.147 s because a native SOLVED candidate still had a 1.022295494e-9 full
original-scale guarded residual. Both exceed the unchanged 1e-9 target.

The current completion uses **original row scales**, not Euclidean normal
scales. All guard magnitudes, native settings and acceptance targets are
unchanged. A SOLVED native restricted QP can be followed by an explicitly
computed full-polytope support-KKT optimization stage when its residuals exceed
the native 1e-12 accuracy. This is part of the new completion algorithm, before
any candidate is accepted. It never alters the original seven-variable point
projection or uses a stored optimum, true disturbance, clipping, or a ZOH fallback.
An unavailable/non-SOLVED native query still ends the attempted command.

For a proposed support I, direct SVD least squares solves A_I x=b_I for its
minimum-norm x and A_I^T lambda=-x. Negative support multipliers cause removal;
violated current constraints cause insertion. All data come from the current
full augmented QP. SVD acts on A, not squared normal equations. Rank/resolution
failure, iteration limit, timeout or failed full KKT verification stops execution.
The finite-QP optimality argument is the convex KKT sufficiency argument in the
original mathematical note. This algorithm has finite test evidence, not a
universal termination guarantee. Its limit is 10000 iterations, and it shares
the same 15 s combined offline query budget. No hardware deadline is certified.

The raw and guarded residuals, stationarity, nonnegative duals and
complementarity are recomputed on **all 387 rows**, including zero multipliers
for omitted rows. A small floating-point KKT residual is a numerical acceptance
criterion; it is not an outward-rounded certificate of feasibility, exact
optimality, or a certified physical torque error. The separately reproduced
T27 error comparisons apply only to their 39 finite fixtures.

A preparation may be reused only from a losslessly checked, completed,
identical-grid P1 executed in this session with unchanged protected startup
source. Reuse retains the measured q/v/z and signed clock, records trace/result
hashes, and never reuses an execution torque or an exact QP witness. The default
standalone reproduction reruns each preparation.

Candidate accuracy uses the exact extrema of the **numerical torque/request
polynomials**, including interior critical roots. Physical/observer sampling,
collocation extrema and finite predictor-grid constraints remain numerical
evidence. They do not bound the true ODE solution between samples. Full numerical
A2, continuous-time certification, A3 readiness and Level 1 must remain separate
decisions. Historical failed candidates remain failed, even if a later version
passes every current numerical check.
