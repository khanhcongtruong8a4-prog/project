# A2-Extended v2 — numerical QP amendment, before new motion

The user requested all E1/E2/E3 cells and all refinement checks to pass and
explicitly authorized continuing numerical development. This is a NEW
version, not a retrospective amendment of v1. The original narrow r4 numerical
GO and v1 E1/E3 failures remain intact. The user's acceptance statement is
recorded verbatim in the predeclaration; no external reviewer identity or
signature artifact is invented from it.

Read-only analysis found strict interior witnesses for each of the five
recorded failed affine matrices. This includes the E1 solver-reported primal
infeasibility and E3 iteration exhaustion. Several solved boundary candidates
also had tiny negative raw rows. These are genuine implementation problems to
qualify, not evidence that the frozen feasible sets were empty. The exact
dyadic witnesses apply only to the recorded binary64 coefficients.

The new numerical realization still minimizes physical squared distance from
the same digital request u. It uses y=tau/87 with Hessian I, eliminating the
old per-joint variable-scaling Hessian condition ratio. Each inequality is
scaled by its positive Euclidean normal length. For the same 43 original rows,
the solve targets G tau+c >= 1e-8 times the ORIGINAL row scale. This explicit
inward roundoff guard is one tenth of the existing 1e-7 normalized reserve
diagnostic, and is an added numerical constraint tightening, not a relaxation
of any safety limit or acceptance rule. It is not a certified error bound.

One cold ProxQP 0.7.2 solve is used, eps_abs=1e-12, eps_rel=0,
max_iter=10000, with duality-gap checking at 1e-12 absolute and zero relative.
Other defaults are pinned by the package version. The 15 s query wall budget
remains fail-closed UNKNOWN. There is no retry, warm-start history, clipping,
backup controller, candidate interpolation or post-solve torque repair.

All original G,c,scales, physical limits, row counts, raw >=0 comparisons and
1e-9 normalized primal/scaled stationarity targets remain unchanged. The new
solver retains both dual representations. A read-only audit recomputes original
T29 and the tightened-problem KKT residuals from them. Applied torque must be
the exact returned candidate and all original raw rows must be nonnegative.
The guard is a solve target; its floating residual is separately measured.

Every trajectory, amplitude, sign, waypoint, duration, reference construction,
actual P1 entrance state, gain, model, observer, disturbance, physical clock,
AB2 sampler, integration grid and refinement tolerance is byte-equivalent to
v1. No reference is made easier. No finer cohort is substituted. All twelve
motion cells and all eighteen edge/diagonal comparisons will be executed after
the new source, contracts, policy and input hashes are committed. PASS is
computed only from complete evidence; further failures remain failures.

The new code is additive. `FROZEN_INPUTS.json` binds all original protected
inputs, v1 motion evidence and the new v2 implementation. The initial failed
scaling contract is retained: noninteger powers of two changed the input
coefficients by an ulp, so exact invariance was an invalid fixture assumption.
The corrected contract uses integer powers, without loosening the solver or
the scientific acceptance thresholds. All pre-motion evidence is retained.

This amendment authorizes local numerical A2 development only. It supplies no
sampled-data stability proof, hardware validation, official T27 completion,
A3 comparisons, Level 1 certificate or new publication statement. Human
review decisions remain separately attributable to real supplied artifacts.
