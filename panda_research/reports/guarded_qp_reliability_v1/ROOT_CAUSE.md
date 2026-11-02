# Guarded-QP false-infeasibility diagnosis

The unmodified 43-row `Panda_actual_43_single_active_face` fixture is feasible.
The retained rational certificate verifies all 43 inequalities, nonnegative
dual multipliers, zero stationarity and zero complementarity for the actual
represented, guarded binary64 QP. Its identity Hessian makes that optimum
unique. Separately, SciPy SLSQP starts at zero and reaches the same point
within 3.47e-18 in scaled coordinates. Neither witness is a runtime fallback.

The installed ProxQP 0.7.2 reports PRIMAL_INFEASIBLE after 50 iterations.
An otherwise identical native unpatched build reproduces that status and
iteration count. Its instrumented inner test reports support
-3.3119545991909325e17, transpose norm 1.0288919206208337e-8 and threshold
1.6559844671413078e-7. Four entries of its trial direction are negative,
including the nearly cancelling velocity rows 17 and 24.

In upstream `helpers/common.hpp`, `negative_part(z)` is **min(z,0)**.
The support function of the interval [l,u] is

    u dot max(z,0) + l dot min(z,0).

Dense `global_primal_residual_infeasibility` instead subtracts the second
term. ProxQP represents unbounded lower sides internally by -1e20. Negative
entries in the trial direction therefore create a huge negative support,
allowing this near-null direction to pass an invalid Farkas test. For a truly
unbounded lower side and negative multiplier, the correct support is +infinity.
Tightening eps_primal_inf from 1e-4 through 1e-14 merely delays the false
classification to iterations 50 through 56; it does not repair the formula.

The versioned correction changes the two subtraction signs to addition in
the ordinary and optional box branches of that dense test. No sparse solver
is used or qualified here. Installed sources and the wheel are untouched;
the corrected backend builds in a separate directory from pinned headers.
The original cold initialization, preconditioning defaults, stopping targets,
iteration limit, QP data, guard, physical gains and experimental settings
remain unchanged. Native compilation is a separately recorded implementation
change; binary identity with the original wheel is not assumed.

The corrected counterexample solves in 84 iterations. Recomputed guarded
stationarity is 4.42e-13 and every original raw slack is positive (minimum
6.54e-8 in its row's units). This is one solved diagnostic case, before the
frozen T27 and motion tests. It is not a general reliability conclusion.

The copied v2 wrapper also gates return of torque on its already required
dual-sign and guarded-complementarity audit checks, so these checks happen
before actuation. Non-solved, nonfinite, rejected or timed-out results never
actuate, and the exact witness/SLSQP code is absent from the runtime adapter.

All validation is automated local work on this host. No external signatures,
global QP-domain theorem, robot-model enclosure or Level 1 evidence is claimed.
The newly mentioned detailed prompt and REVIEW (1).zip are not mounted in
this session. The visible user request and preserved repository evidence
govern this work; the existing review ZIP is not asserted to be that attachment.
