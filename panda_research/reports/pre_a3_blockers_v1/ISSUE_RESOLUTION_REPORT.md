# IC2AI 2027 issue-resolution report

| Stage | Decision | Technical evidence |
|---|---|---|
| Frozen A2 scope | **GO retained** | Original seven and v4 twelve recorded physical cells and all 120 refinement metric checks reaudited; protected source and trace bytes unchanged |
| Active-filter refinement | **NO-GO** | Historical eight failures retained; new projected-feedback candidate completes/audits four cells but fails the same eight metric checks |
| M1 numeric registry/pipeline | **Complete implementation, bound qualification NO-GO** | All 14 core entries and source mappings; full envelopes/margins and 72 residual Lipschitz estimates. Finite-sample extrema are not certified upper bounds |
| G2.5 final-policy feasibility | **NO-GO** | 1,212 filter point QPs pass; full planner entry violates two necessary speed pairs |
| T27 | **GO for the finite tested scope** | All 39 fixtures pass strict classification; exact feasible/infeasible witnesses retained |
| A3 readiness | **NO-GO** | Active-filter qualification, M1 bound validity and full planner entry gates remain open |

## Active-filter diagnosis and tested correction

The original eight failures are control-period and diagonal comparisons for
energy and peak intervention. Halving the RK4 step changes energy by about
2e-11 J and peak intervention by about 3e-11 Nm; changing Delta produces
approximately 4.20e-4 J and 1.51e-3 Nm differences. The source model, continuous
Slotine–Li gains/law, observer, HOCBF constraints, guard, disturbance, reference
and all numerical/acceptance targets are unchanged.

The active rows are v_upper_3 followed by v_lower_1. On Delta=1 ms the recorded
transitions occur near .020, .330 and .406 s; on Delta=.5 ms there is a brief
two-face interval near .3295 s and the last active interval ends at .4025 s.
Quadratic peak interpolation changes the coarse peak by only about 1.31e-6 Nm;
it does not remove the 1.51e-3 Nm refinement discrepancy. It was never used to
replace the approved maximum-intervention metric.

AB2 of the nominal r is not generally AB2 of sigma=P_C(r). The read-only
post-filter extrapolation sigma_k+(sigma_k-sigma_previous)/2 violates original
raw constraints at 386/386 active coarse updates and 765/765 active fine
updates. No such torque was actuated. A simple moving-face example explains
the obstruction: if tau<=b(t)=t and r>t, the continuous projected feedback is t,
but its next-interval average t+Delta/2 violates the current constraint. Thus
current-state hard constraints and a ZOH average interpretation do not support
a general second-order claim merely by moving AB2 after the QP.

One candidate was derived and frozen at 2ca4de7 before testing:

    sigma_k = P_Ck(r_k)
    u_0 = r_0
    u_k = r_k + (sigma_k - sigma_previous)/2
    tau_k = P_Ck(u_k)

It recovers the original AB2 rule in an inactive region and is causal and
consistent with the projected continuous map as Delta tends to zero. It does
not claim second-order accuracy or a new stability theorem at moving active
faces. Both required solves are independently checked against the same rows;
the combined query retains the 15 s wall budget. The raw-feedback solve is not
a fallback. Failure of either solve stops the cell. The endpoint query is
reused once, and the plant and DOB receive the same actually held final torque.
The metric remains norm(tau-u), with u explicitly recorded as the final QP's
declared digital request. All stages and both QP diagnostics are retained.

All four candidate cells complete and pass raw signs, physical limits,
observer checks, original/guarded KKT checks, held-input and energy audits.
The original C4 refinement still fails eight comparisons. The candidate is
therefore **not adopted**; it remains a preserved failed development version.

The separate original-AB2 ladder is diagnostic only:

| Delta (s) | h (s) | Energy (J) | Peak intervention (Nm) |
|---|---|---|---|
| .001 | .00025 | 1.172860159355944 | .130720578804632 |
| .0005 | .00025 | 1.172440490690066 | .129210306666044 |
| .00025 | .000125 | 1.172232173519377 | .128452721746830 |
| .000125 | .0000625 | 1.172128773519081 | .128073293212051 |

Observed energy orders are 1.01047 and 1.01055; peak-intervention orders are
.99533 and .99758. The supplemental ladder also refines h, while the original
C4 h-only comparisons already show negligible RK4 error. These are observed
rates, not a global convergence proof or replacement of failed C4 acceptance.
A future version must reconcile sampled input accuracy and moving active
constraints and demonstrate every original C4 check; no validated correction
that removes this limitation is claimed in this delivery.

## M1 registry and evidence levels

The common coefficient domain and estimator were frozen at 9f30dac before
sampling. The computational phase box [-4,4]^7 covers the periodic model
coefficients; it does not wrap any physical trajectory or alter joint limits.
Velocity/augmented-acceleration coverage is explicitly conditional on the
original tightened speed constraints. Degree-five Markov inequalities, the
unchanged Tmin=.5 s and the original knot spans provide conservative a/jerk
boxes. All physical limits and the original .01 rad extension are retained.

The registry contains m1, mbar_i, Nbar_Q_il, Cbar_li, Abar_jl, Nbar_il, Bbar_il,
Dbar_jl and all six inverse-dynamics/HOCBF derivative tables, with shapes,
units, equation/source hashes, common-domain hash, grid hash, seed and budget.
The derivative evaluator uses the original model and CasADi AD; six contract
checks, including independent finite differences, pass.

The new m1=0.0002429577549824883 kg m^2 is an analytic selected-ideal-model
lower bound. Exact rational SPD checks of all seven COM inertia tensors give
I_i >= [1/trace(I_i^-1)] I. The kinetic-energy/axis-increment argument gives
sum v_i^2 <= 4 sum |omega_i|^2, hence M >= min_i[1/trace(I_i^-1)]/4 I. The
fixed-axis matrix hypotheses are checked exactly. This is a component lemma;
it does not certify floating model evaluation, all upper constants or Level 1.
The observed eigenvalue minimum .0035472620471413705 was **not** used as a
lower bound.

The upper matrices are explicitly finite-sample extrema: 512 fixed Sobol
points plus five declared anchors for training, and 256 held-out points.
Held-out samples exceed 254 of 875 training extrema components. Every training
value and every exceedance is preserved; no inflation or incorporation of the
held-out values is used to hide the result. These arrays are therefore not
qualified domain upper bounds. `require_certified()` rejects their use as a
certified planner registry. Complete numerical tables do not clear that gate.
The raw coordinates, all coefficient outputs and observed eigenvalues are in
RAW_M1_SAMPLES.npz. The exact inertia lemma and entry-wise statuses are in
M1_REGISTRY.json and final_analysis/M1_BOUND_STATUS.csv.

The derived implementation follows the manuscript order varpi -> y_b ->
chi_s/chi_e/chi_v -> rho_r -> beta/zeta -> b_u+/b_u-/b_h/b_vB. In particular,
rho_r(0)=varpi0, and the alpha_v=10 velocity term is |10-5| chi_v. All 72
inequality-residual Lipschitz estimates are supplied with their chain-rule
and Markov provenance. Their grid reserves remain estimates; no continuous
feasibility certificate is inferred from them.

Finite numerical qualification must first close the failed held-out checks
and the declared domain/tube coverage checks. Rigorous domain-bound claims
additionally need analytic/interval enclosure or verified remainder control
for every upper coefficient and the residual grid bounds. More samples or a
status-label change alone do not establish those global guarantees. Numerical
qualification and Level 1 certification remain separate gates.

## Full G2.5 and the entry contradiction

Twelve unchanged E1/E2/E3/C4-start cases were screened on 101 nodes each, using
the final alpha_v=10 policy and the complete development M1 margin equations.
The screen includes torque reserves, speed, physical joint/manipulability h,
HOCBF, paired velocity CBF and estimated between-node reserves. All 1,212
read-only full 43-row filter QPs pass. These are planned-point diagnostics
with the declared frozen initial estimate, not executed A3 trajectories.

The factor-two-only lower screen passes at the measured start: its limiting
speed slack is about .573 rad/s^2. The full planner margin also retains
Nbar*rho_r. Since chi_s=chi_e=chi_v=0 and rho_r(0)=varpi0, it requires at least

    3 abs(M(q0)^-1) varpi0 + delta_vB <= alpha_v vmax.

At C4 start 0 the necessary slacks are -9.345882714675025 and
-10.015904287971434 rad/s^2 for joints 1 and 3. For each pair, weights 1/2 and
1/2 cancel the opposite acceleration coefficients exactly and leave a negative
right-hand side. Rational inversion of the represented binary64 M and exact
input rationals supplies the explicit witnesses for all four actual starts.
The certificate is for that represented mass matrix/input set, not a Level 1
certificate of the nonlinear real robot. Any valid containing Nbar must be
at least the point absolute inverse entries; tightening an invalid sampled
estimate cannot remove this necessary contradiction. Extra torque,
manipulability or nonnegative margin terms cannot repair a failed speed pair.
The new planner-entry gate recomputes this witness and stops before a solve.

At the fixed pose, the unchanged analytic observer envelope needs more than
.2517863776757874 s preparation for this necessary condition; .253 s is the
quantized diagnostic candidate. The current .156 s protocol is unchanged.
This is not a sufficient new policy: a new actual P1 endpoint and the full
screen with qualified common-domain bounds are still required. A separately
justified tighter initial error bound is another possible mathematical route;
using simulated disturbance truth to force a smaller bound is not performed.

## Consolidation, regression and scope

`panda_closed_loop.guarded_qp_final_v1` is the consolidated API. It exports the
already qualified sign-corrected v1 kernel with the exact constant-row v1.1
classifier and the original settings. The native library hash is
3370c29e2c3e42db44bc7cfed1d385ebc6680a519a1501693c223575122fc8c1.
The rejected sampler is not exported as the final solver. No stored witness,
SLSQP output, retry or post-solve torque repair is a runtime fallback.

All 39 T27 fixtures pass again, with 34 exact feasible KKT certificates and
five exact infeasibility witnesses. This is the tested finite numerical scope,
not universal solver qualification. All 2,506 pre-task files retain their bytes.
The full prior 19-cell A2 scientific data and all 120 refinement metrics were
reaudited unchanged. This task does not claim another fresh 19-cell physical
run; it adds four candidate and two supplemental development simulation cells.
The selected final A2 controller remains the previously frozen realization.

The user confirmed that the direct message is the handoff prompt. The prior
QP_REPRODUCTION.zip was recovered with SHA256
48bd60815b7b7227545fcf573a666d50e5eecb365d30c515bfbece8b5eda41e0.
All work is automated local evidence on this host. Independent human signature
fields remain blank. No official A3 comparison or Level 1 claim is made.

The new compact package will include all code/inputs needed to reproduce the
new numerical work; the task evidence package also contains full raw traces
for the six new cells and the four legacy active-filter execution traces used
in diagnosis.
The unchanged complete earlier history is an explicitly linked immutable
annex, not silently omitted or described as part of the small numerical ZIP.
