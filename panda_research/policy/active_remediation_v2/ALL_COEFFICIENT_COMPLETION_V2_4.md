# All-coefficient completion v2.4

This addendum supersedes the fixed-constant completion formula in v2–v2.3;
those files and their failed runs are retained without modification.

Let B(s)=[I,sI,s²I,s³I], Q_ij=1/(i+j+1), i,j=0,...,3, and
T=chol(Q)^(-T) tensor I_7. The actual hold is

    tau(s) = b(s) + 87 B(s) T x,    x in R^28.

All four coefficient vectors, including the current constant, participate.
The objective 1/2 ||x||² is the integrated squared physical correction divided
by 2*87². Q is positive definite because the square of any nonzero scalar
polynomial has strictly positive integral over [0,1]. Positive original-row
normalization retains exactly the same finite augmented feasible set.

Why this matters: the unchanged point solver's numerical acceptance can leave
a current guarded residual slightly larger than 1e-9 **in original row units**,
even when its native Euclidean-row residual passes. A completion that fixes the
constant cannot repair that row: its coefficient normal is exactly zero.
Full verification exposed this obstruction, and correctly stopped v2.2/v2.3.
The new augmented QP includes the current row as an optimization constraint;
it never relaxes its guard or acceptance threshold. The original point solver
is unchanged and now supplies a seed, not a separately actuated command.

All 387 current/predictor-grid rows are evaluated before acceptance. The native
restricted solve and computed full-support KKT stage described in the v2.3
addendum form the declared optimization algorithm. Any failure is a protective
stop. Stored exact T27 oracles remain offline test inputs, never command data.

The nominal polynomial interpolates the unchanged Slotine–Li request at the
same four causal predictor nodes. Reported intervention is the maximum norm
between the accepted torque polynomial and that digital nominal polynomial,
including interior critical roots. This is the same physical torque-minus-
digital-request metric under the new, explicitly versioned realization; it is
not the old AB2 interval-average request. The old AB2 results remain failed.

The nine-node guarded argument and KKT evidence are numerical and finite.
Collocation extrema, refined trajectories and sampled margins are not
outward-rounded true-ODE enclosures, globally certified model bounds, external
reviewer signatures, official A3 comparisons or Level 1.
