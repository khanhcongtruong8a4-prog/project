# A2 technical acceptance: mathematical consistency and exact claim scope

This is an automated/local engineering analysis, not a supplied independent
reviewer signature. The user authorized proceeding after consultation,
conditional on consistency with the framework. No source equation, physical
parameter, experimental reference, gain, solver setting or pass threshold is
changed by this verification. Official A3 and Level 1 remain outside scope.

## Two distinct existing protocols

Original A2 r4 uses the preserved alpha_v=5 filter, original hard ProxQP,
one fixed 0.25 s measured-endpoint reference, and seven declared cells across
original/finer cohorts. A2-Extended v4 uses alpha_v=10, the declared guarded
current-state QP, three fixed 1 s references and twelve original C4 cells.
The final policy must keep these designs separate. v4 does not retroactively
approve alpha5 constraints. Old failures and alpha5 shadow negatives remain.

## AB2 request sampler

Let r_k be the original continuous-law request evaluated at the actual current
sample. The actual digital QP input is u_0=r_0 and
u_k=1.5 r_k-0.5 r_(k-1). This is a causal request sampler, not an AB2 plant
integrator: the plant/DOB are integrated by coupled RK4 under held QP torque.

For an externally smooth request r(t), Taylor expansion gives
u_k=r(t_k)+(Delta/2)r'(t_k)-(Delta^2/4)r''(t_k)+O(Delta^3).
Its true interval average is
r(t_k)+(Delta/2)r'(t_k)+(Delta^2/6)r''(t_k)+O(Delta^3).
Thus the mean-request error is -(5/12)Delta^2 r''+O(Delta^3), and impulse
error O(Delta^3). The bootstrap has O(Delta^2) impulse error. Affine requests
are integrated exactly after bootstrap. These facts are tested algebraically.

They do not prove closed-loop order/stability for a state-dependent nonlinear
controller followed by active-set switching. Past v2/v3 failed refinements
demonstrate why that distinction matters. Actual numerical refinement must
pass; the continuous theorem is not silently transferred to this sampler.
Fresh per-cell history, single endpoint solve reuse, permitted measured/DOB
signals, and exact held tau into the observer are audited from the full logs.
u-r, tau-u and tau-r are separate measured quantities, not interchangeable.

## Positive speed-barrier gain 10

Write N=M(q)^-1 and b=dhat-C(q,v)v-g(q)-F(v). With e=d-dhat and
|e|<=varpi, nominal acceleration is N(tau+b), with error N e.
For h_plus=vmax-v and h_minus=vmax+v, the worst current-point residuals are

    -N(tau+b)+alpha_v*(vmax-v)-abs(N)*varpi,
    +N(tau+b)+alpha_v*(vmax+v)-abs(N)*varpi.

These are exactly the fourteen speed rows in the implementation. The box
minimum is attained at sign corners; all 128 corners are checked locally.
alpha_v=10>0 is a valid linear class-K choice, with the same physical speed
limits. It changes acceleration admissibility, so it is a versioned filter
design value rather than an unchanged-alpha5 claim. Other barrier/controller/
observer gains and the Gaz model stay byte-identical.

If these derivative inequalities held for ALL time and the envelope/model
assumptions held, the usual comparison argument would preserve nonnegative
speed barriers. The simulations enforce them at scheduled updates and inspect
retained RK4 samples; that is not the all-time premise. No intersample/model
error enclosure or continuous-time/Level1 certificate is supplied here.

## Guarded QP equivalence and numerical gate

The declared physical objective is 0.5*||tau-u||_2^2, with an irrelevant
constant/positive objective scale. Let y=tau/87, n=u/87,
d_i=87*||G_i||_2 (or 1 for zero normals). The solver uses H=I, g=-n,
C_i=-87 G_i/d_i and b_i=(c_i-1e-8*s_i)/d_i, so C y<=b is the same inward
tightening G tau+c>=1e-8*s. This is an unweighted physical-torque projection,
including when joint torque limits differ. Positive row scaling preserves
inequalities. s denotes the approved numerical row-unit normalization.

For original theta=tau/taumax, the dual transformation is
lambda_original=lambda_scaled*s/d. It gives the same Lagrangian gradient
for H_original=diag(taumax^2)/87^2 and g_original=-taumax*u/87^2.
Primal feasibility, stationarity, dual signs and complementarity are
recomputed from retained duals. The same 1e-9 T29 targets and strict raw
nonnegative rule apply. The inward guard shrinks the feasible set and can
remove boundary-only feasibility. It is not a certified error bound.

H=I is strictly positive definite. Exact primal/dual feasibility,
stationarity and complementarity therefore suffice to identify the unique
optimum of the represented scaled QP. A separate rational-arithmetic routine
checks all those conditions on an actual gain10 43-row active-face fixture.
It certifies recorded binary64 coefficients only, not the exact robot model.
The actual ProxQP result is compared to that optimum in y at the unchanged
1e-9 numerical target. There is no post-QP repair, clipping, retry or actuation
in these read-only fixtures. Actual trajectory current rows are also checked.

## Disclosed extra counterexample and gate separation

A read-only cross-combination probe feeds a preserved ORIGINAL alpha5 active
43-row fixture to the v4 guarded solver. The exact represented-QP optimum
exists, but ProxQP reports PRIMAL_INFEASIBLE after 50 iterations and returns
no applied torque. This is a genuine failed numerical solver probe. Its test
remains FAIL, with exact witness, source, log and diagnostics retained.
It is not silently made an expected pass or erased.

This hybrid is not either selected experimental protocol: the original
alpha5 A2 runs its original solver; v4 runs alpha10. The user's requested
acceptance is for those precisely fixed original/v4 experiments. Their GO
requires all of their unchanged cell/refinement criteria, exact replay, and
all applicable algebraic checks. The hybrid probe is explicitly a separate
broader solver-qualification finding BEFORE the new physical replays.
Its failure prevents a general guarded-QP-domain/T27 completion claim.

A remedy for broader qualification is a separately versioned, robust solver
implementation/initialization or exact-status verification that passes this
counterexample, active/scaled feasible/infeasible fixtures and the unchanged
A2 replay set. Do not retune gains, references, guards or acceptance limits
to hide it, or actuate a diagnostic witness as a fallback in frozen v4.

## Acceptance and authority

Source/integrity recovery, exact replay, model mathematics and all applicable
gain10/current-protocol checks determine the numerical A2 decision. A source
archive gets local Git input-staging metadata solely to execute the ORIGINAL
unchanged runner checks; this is labeled local and is not historic provenance.
The user-provided consultation/authorization is retained verbatim. External
reviewer identities/signatures are not supplied or invented. A numerical GO
for these finite experiments is distinct from broad solver qualification,
publication/theorem interpretation, A3 comparisons and Level1 certification.
