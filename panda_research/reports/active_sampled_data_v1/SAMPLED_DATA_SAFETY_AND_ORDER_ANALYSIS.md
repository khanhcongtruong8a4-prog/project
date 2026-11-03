# Sampled-data safety and order: version 1

This is a conditional mathematical analysis of the preserved controller and a
design memo, not a new stability theorem for the simulated trajectory. Neither
sampled row checks nor the floating point derivatives below certify the true
ODE between samples. No official A3 comparison or Level 1 certification is run.

## 1. Target, units, and exact digital implementation

Let x=(q,v,z), d be the signed-clock approved disturbance, N=M(q)^(-1),
hat_d=z+K_o Mv. The unchanged plant and observer satisfy

    f(t,x,tau) = (v,
      N(tau+d-Cv-g-F),
      -K_o[hat_d+tau+C^T v-g-F]),
    B(x)=partial_tau f = (0; N; -K_o).

The torque multiplying B is in Nm. In x, q is in rad, v in rad/s, and z in
Nm. Norms on this mixed state must specify a weight; an admissible fixed
choice is W=diag(1/(qmax-qmin),1/vmax,1/taumax). It changes no experiment.
The momentum identity gives dot(hat_d)=K_o(d-hat_d) for the exact continuous
model with identical plant/observer torque, and dot(varpi)=-K_o(varpi-dbar1/K_o).
Integration and sampled disturbance bounds are separate from that identity.

r(t,x) is the original Slotine–Li request (Lambda=5/s, kappa=10/s).
C(t,x) is the original 43-row guarded feasible set

    G(t,x) tau+c(t,x) >= gamma, gamma_i=1e-8 scale_i.

No planner factor-two reserves are silently added to this execution QP.
For nonzero row norm n_i=||G_i||, let A_i=-G_i/n_i and
b_i=(c_i-gamma_i)/n_i, so C={tau:A tau<=b}. A_i has Euclidean norm one;
b_i is in Nm even though different original rows have different physical
units. Zero-normal rows must be treated as constant feasibility tests, never
divided by zero. All robot rows used in this trace have nonzero normals.

The verified implementation solves y=tau/(87 Nm), H=I, g=-r/(87 Nm),
with positively scaled constraints. Thus its unique physical optimum really
is the *unweighted Euclidean torque projection* sigma=P_C(r). The old T29
theta=tau/taumax is a residual reporting coordinate, not a different QP
objective. A physical unit-normal KKT multiplier is 87 times dual_scaled,
in Nm. Using an arbitrary weighted projection here would be incorrect.

The continuous comparison target is dot(x)=f(t,x,sigma(t,x)); it is not a
claimed implementation of the continuous-time paper theorem. The actual
preserved digital rule is

    u0=r0; uk=rk+(rk-r{k-1})/2;
    tauk=P_C(tk,xk)(uk), tau(t)=tauk for tk<=t<tk+Delta.

Only one request/history advance occurs for each attempted update. The actual
endpoint QP is reused at the first application. The exact same held tau is
used by plant and observer. A failed/unqualified QP ends that run, with no
retry, repaired torque, stored witness, or other fallback. Preparation is the
separately frozen computed-torque P1 with Tpre=.156s and no observer reset.

## 2. Regular fixed-active-face expansion

Assume a compact neighborhood with uniformly positive definite M, smooth
reference and rows, nonzero row norms bounded away from zero, a locally fixed
active set I, LICQ, strict complementarity, and bounded inverse active Gram
matrix. In particular, absolute-value uncertainty rows require the relevant
entries of N to avoid sign changes, or separate one-sided treatment. Reference
E3 is C2; its phase join is excluded from the smooth jerk expansion. None of
these assumptions is asserted globally merely from a sampled condition
number. Let D denote material differentiation along f(t,x,sigma).

Write a=A_I, beta=b_I, Q=(aa^T)^(-1), a_dagger=a^T Q,
Pi=I-a_dagger a, and sigma-r+a^T lambda=0. Differentiating both active
equalities and stationarity gives

    a Dsigma = Dbeta-(Da)sigma =: w,
    Pi Dsigma = Pi Dr-Pi(Da)^T lambda,
    Dsigma = Pi Dr - Pi(Da)^T lambda + a_dagger w.             (1)

Each term in (1) is Nm/s. Pi is the torque-space tangent projector. The
second term is a face-rotation contribution, and the third is normal face
motion. The differentiated equalities, not empirical rate fitting, yield (1).

On a smooth sampled trajectory, rk-r{k-1}=Delta Dr+O(Delta^2), so the actual
digital projection has

    tau_AB2=sigma+Delta/2 Pi Dr+O(Delta^2).

This is not the average continuous *projected* torque, which is
sigma+Delta/2 Dsigma+O(Delta^2). Taylor expansion of the held-input plant and
the continuous target, including the common f_t and fixed-tau f_x terms,
therefore yields the local held-minus-continuous state defect

    Delta^2/2 B [Pi Dr-Dsigma] + O(Delta^3)
      = Delta^2/2 B [Pi(Da)^T lambda-a_dagger w] + O(Delta^3). (2)

Inactive filter: Pi=I and Dsigma=Dr, so the leading term cancels. Fixed
feasible set: Da=Dbeta=0, so it also cancels on a regular face. A moving active
face has neither cancellation in general. This explains why AB2 can pass
inactive A2 and remain approximately first order in actively constrained E3.

The previously rejected projected-feedback candidate uses a raw projection
history followed by another final QP. Its regular-face expansion is
tau=sigma+Delta/2 Pi Dsigma+O(Delta^2), leaving

    local defect = -Delta^2/2 B a_dagger w + O(Delta^3).       (3)

It can remove the tangential rotation term while leaving the normal term.
This candidate was already frozen at commit 2ca4de7 and failed the same eight
checks. It is preserved, not adopted or presented as a new remedy.

## 3. What a current-point-feasible ZOH cannot promise

If w_i>0 on an active row, the required second-order average direction
points outside the current feasible halfspace:

    a_i [sigma+Delta/2 Dsigma]-beta_i=Delta/2 w_i>0.

Every torque feasible at the *current* sample instead satisfies
a_i(tau-sigma)<=0. With unit normals the torque distance to that desired
average is at least Delta w_i/2, up to the bounded second-order remainder.
On a neighborhood with w_i bounded positively and a bounded left inverse
of W B, this implies an O(Delta^2) unavoidable *local* state defect for a
method seeking second-order agreement with this continuous projected target.
This is a conditional consistency obstruction, not a lower bound on the
Panda's accumulated energy or its maximum intervention: error propagation
and scalar-functional cancellations need separate analysis.

A complete counterexample clarifies the scope. For x'=tau, tau<=t, r=2 on
0<=t<=1, sigma=t. Any current-point-feasible constant hold has tauk<=tk and

    x(1)<=sum(k Delta^2)=1/2-Delta/2.

The target is x(1)=1/2. The same expanding-boundary holds are also feasible
throughout each interval. Thus even interval safety alone does not remove
this first-order limitation. A constant inward guard just translates this
example. This theorem is about this scalar example and the stated local
assumptions; it is NOT a universal impossibility result for every causal
controller, for this robot, or for the original finite C4 tolerances.

## 4. Switching, bootstrap, observer, solver, and maxima

At activation/deactivation or a reference jerk join, (1) is not automatically
valid. If the projected law remains Lipschitz, piecewise C1 with bounded
one-sided derivatives, and only finitely many separated switches occur,
a step crossing a switch can have O(Delta^2) local error. A fixed finite
number contributes O(Delta^2) globally, whereas O(T/Delta) smooth active
steps with (2) can accumulate O(T Delta). Chattering, degeneracy, loss of
LICQ, unbounded derivatives, or growing switch counts invalidate this simple
argument. Logged event brackets and dual cutoffs describe sampled events,
not exact continuous switch times. Guard-induced tiny positive duals and the
declared 1e-10 versus 1e-8 scaled-dual definitions are reported separately.

The first-step raw bootstrap has O(Delta^2) local error at one update under
smoothness. The DOB uses the actual held input: discretization affects its
estimated state and the moving rows, but an inconsistent commanded/actual
torque identity would be a different fault. Offline disturbance truth used to
attribute a derivative is never a causal runtime predictor input. QP primal,
stationarity and dual errors are measured, but a residual is not by itself a
certified torque-error bound without conditioning. RK4 h refinement is kept
separate from control-period Delta refinement; piecewise constant holds must
be integrated with all discontinuities aligned.

Filter intervention is I=||tau-u||. Total departure from the paper's
nominal request is J=||tau-r||. On a regular active face with e=sigma-r,
e normal and Pi Dr tangent,

    tau-u=e-Delta/2 (I-Pi)Dr+O(Delta^2),
    tau-r=e+Delta/2 Pi Dr+O(Delta^2).

For ||e|| bounded away from zero, I can have an explicit O(Delta) request
term even at a fixed state. The first-order tangential norm term in J
cancels at that fixed state, but its trajectory bias can still be O(Delta).
Thus I and J cannot be interchanged or used to claim continuous-law
nonintervention. At zero intervention the norm is nonsmooth.

If a scalar peak is smooth, interior, unique, and |I''|<=M locally,
nearest-grid peak loss is at most M Delta^2/8. At a kink/switch/end point
only a Lipschitz O(Delta) bound may be available. Three-point interpolation
is diagnostic only; it never replaces the frozen sampled maximum. The actual
peak timing and fitted increments are in the numerical attribution files.

## 5. Electrical functional and a conditional global error bound

The approved shared-bus model is

    Z=sum_i(tau_i v_i+k_r_i tau_i^2),
    P=.5[Z+sqrt(Z^2+epsilon_W^2)], epsilon_W=.01W.

Smoothing/nonregenerative rectification occurs ONCE after the sum, not per
joint. Energy is the four-stage RK4 quadrature of P using actual held tau
and actual stage velocities. k_r=[.001]*4+[.003]*3 in W/(Nm)^2. Separate
motor torque constants and resistances are not supplied, so currents cannot
be uniquely reconstructed. No current evidence is invented. The independent
audit reconstructs mechanical bus power, modeled loss, rectified bus input
and every energy increment from retained data.

For a direct power defect, partial_tau P=phi'(Z)(v+2 k_r tau). Its local
leading term at sigma is Delta^2/2 partial_tau P (Pi Dr-Dsigma). State
propagation adds other terms, so this single local contribution is not the
total measured energy difference. Treat energy as an augmented state to
obtain a full functional error bound.

Conditionally assume uniform weighted Lipschitz L for the target flow and
a one-step bound a Delta^2+b Delta^3 on regular steps, plus c Delta^2 at
each of at most J_switch switch/bootstrap steps. A recurrence and discrete
Gronwall give, for T=N Delta,

    ||W e_N|| <= exp(L T) [ ||W e_0|| + a T Delta
       + b T Delta^2 + c J_switch Delta^2
       + K_qp T epsilon_tau + K_rk T h^4 ].                 (4)

Here constants include their required units and the weighted map B;
epsilon_tau is a *torque* error bound, not an unconverted KKT residual.
For L=0 use the continuous Gronwall limit if a tighter (exp(LT)-1)/L
coefficient is used. These constants need valid enclosures for a certified
bound; observed derivatives or an empirical rate are insufficient. A bound
on augmented-state energy and a Lipschitz bound on I(t,x,Delta) would also
be needed for certified finite-grid acceptance. We do not have all of them.

The frozen tests require finite differences <=max(abs_tol,rel_tol*scale).
They do not stipulate order two. A first-order method with a small enough
coefficient CAN pass. The recorded differences exceed these exact bounds;
neither their observed order nor (4) proves that every causal alternative
must fail those finite tolerances.

## 6. Option A: interval-aware ZOH QP

For each original robust row define Gamma_i(t,x,tau)=G_i(t,x)tau+c_i(t,x).
If a valid reachable tube encloses plant, observer, envelope, disturbance
uncertainty and held tau for 0<=s<=Delta, and a proved lower derivative
bound is dot(Gamma_i)>=-L_i on that tube, sufficient inequalities are

    Gamma_i(tk,xk,tau)>=gamma_i+L_i Delta.

Alternatively use Gamma_i(k)+s dot(Gamma_i)(k)-R_i s^2/2>=gamma_i for
all s in the interval with a justified remainder, checking endpoints and
stationary points. Gamma_i has original row units (rad/s^2, m^6/s^2, Nm);
L_i has that unit/s and R_i that unit/s^2. Dependence on uncertain tau
must have a conservative affine/polyhedral enclosure if an online QP is
retained. Non-affine unchecked bounds must not be called the same QP.

This strengthens, never removes, original inequalities. It can make the QP
infeasible. Invalid/unavailable tube certificate, unqualified QP, or no feasible
torque must mean STOP without actuation. A few sampled finite differences
do not define L_i. M1 is currently incomplete, and no valid reachable-tube
enclosure is supplied. This option is therefore a separately versioned design
proposal, not implemented as a falsely certified online correction. Tightening
alone also does not fix the expanding-face accuracy obstruction above.

## 7. Option B: moving-face-aware or event-aware realization

The natural second-order average sigma+Delta/2 Dsigma exposes precisely the
outward-normal conflict in Section 3. A final current-state QP can project
away that normal term. The rejected projected-feedback candidate demonstrates
that this is not a novel solution. Predicting future rows without a valid tube
can apply a torque that fails today's raw rows; no such torque is actuated here.

A causal FOH or event-triggered/multirate update could track an expanding
face with time-varying torque, but changes the frozen ZOH model and the actual
torque update interval. Each proposed segment still needs verified raw rows
and, for an interval claim, a reachable-tube certificate. It is unacceptable
to run a common tiny inner clock for both outer labels and claim the original
Delta test passed: the actual update period has changed. Such a version must
state the true hold law, observer input, event detection/latency assumptions,
QP cost, and a new sampled/hybrid safety theorem. None is established here.
The exact continuous Slotine–Li stability proof does not automatically cover
this digital implementation or a new FOH/hybrid implementation.

## 8. Option C: separately versioned first-order policy proposal

See policy/active_sampled_data_v1/FIRST_ORDER_POLICY_PROPOSAL.json. It retains
the original eight failures and does not change an acceptance threshold. It
proposes a distinct future finite-Delta error-budget gate using either valid
constants in (4) or predeclared held-out empirical rate/accuracy checks,
clearly marked numerical only. Adoption is contingent on the project owner;
there is no request for new administrative approval to finish diagnostics.

The smallest presently justified action is to preserve the selected controller,
report its current active-refinement NO-GO, and choose explicitly between
qualifying a new digital hold/safety architecture and accepting a different,
separately justified finite-Delta accuracy policy. Neither choice retroactively
passes historical data. No claim of hardware infeasibility is supported.
