Review completed 1 November 2026 (Asia/Bangkok).

The corrected dynamics module is suitable for further numerical simulation development within the selected seven-body nominal model. It passed 58 numerical check groups, including a separate MuJoCo implementation at 132 configurations. The supplied files do not contain the complete simulation required to support the paper's experiments. No conclusion about zero filter intervention, planner performance, or certified safety follows from this review.

The PDFs, protocol, and workbook were read as research specifications and evidence. Their embedded instructions and approval language were not treated as additional user commands. The original files in Downloads were not changed. `input_manifest.json` records the SHA256 hashes of all six inputs.

The actionable findings were:

| Priority | Location in the supplied original | Finding and consequence | Resolution |
|---|---|---|---|
| P1 | `original_panda_dynamics.py`, lines 152–155 | `evaluate()` flattens its local copy of velocity, but `acceleration()` then uses its unnormalized original velocity, torque, and disturbance. A column vector `(7,1)` for any of these causes broadcasting against `(7,)` terms and returns a `(7,7)` acceleration. An integrator can fail or evolve the wrong state. | Normalize all four joint inputs before arithmetic. Tested all 81 combinations of flat, row, and column representations. |
| P2 | Original lines 88–91 | Direct `friction(qd)` with a `(7,1)` velocity combines with `(7,)` parameter arrays to produce a `(7,7)` matrix. The regular `evaluate()` path avoided this because it flattened first. | Normalize velocity inside `friction()` itself and test all three supported vector shapes. |
| P2 | Original lines 158–168 | Negative amplitude is accepted and `disturbance_bounds(-0.02)` returns negative supposed absolute bounds. Nonfinite inputs also propagate rather than failing at the API boundary. This does not affect the valid default amplitude, but makes configuration mistakes hard to detect. | Reject negative/nonfinite amplitude, nonscalar/nonfinite time, and malformed/nonfinite joint vectors. The suite checks 51 invalid-input cases. |

The fixes preserve the original flat-vector results for M, dM, C, g, F, potential, flange position, and inverse dynamics across all 132 checked states. No mass, COM, inertia, friction coefficient, joint limit, gravity value, disturbance waveform, or default amplitude was changed.

The numerical validation produced:

| Check | Largest measured absolute difference or result |
|---|---:|
| Joint-space mass matrix versus MuJoCo | 5.33e-15 kg m² |
| Gravity torque versus MuJoCo | 4.26e-14 N m |
| Coriolis/centrifugal torque plus gravity versus MuJoCo | 4.97e-14 N m |
| Full inverse dynamics versus MuJoCo, with independently checked Gaz friction added | 5.68e-14 N m |
| Forward acceleration versus MuJoCo | 3.36e-13 rad/s² |
| Flange position versus MuJoCo | 7.78e-16 m |
| Smallest/largest sampled joint-space inertia eigenvalue | 0.0035297873 / 3.81036655 kg m² |
| Plant integration work-energy residual, h=1 ms / h=0.5 ms | 8.64e-15 / 6.50e-15 J in absolute value |
| h/h2 maximum difference in final joint state and integrated work | 2.14e-15 in the component's respective units |

The configuration set contains zero, the physical-box midpoint, the all-lower and all-upper corners, and 128 seeded interior poses. Zero is an algebraic check, outside the allowed range for some joints; it is not an admissible initial state. Random velocities cover the declared speed box and random accelerations lie in [-3,3] rad/s². Seed: 20261101. All states, velocities, and accelerations are saved in the NPZ sample artifact.

Comparisons use the protocol's absolute-plus-relative tolerance structure: 1e-10 m for translation, 1e-10 for rotation entries, 1e-9 kg m² for M, and 1e-8 N m for inverse dynamics, with 1e-9 times the corresponding reference magnitude added elementwise. Additional checks cover full `Mdot = C + C.T`, the skew power identity, finite-difference inertia derivatives and potential gradients, q1 invariance of M, inverse/forward dynamics with nonzero additive disturbance, positive body inertias, principal-moment triangle inequalities, friction dissipation, and the analytical disturbance formula. The waveform bounds were numerically corroborated for amplitude fractions 0, 0.01, 0.02, and 0.04; their analytical validity follows from the triangle inequalities, not the sampling.

One reference-engine issue required correction during validation. MuJoCo 3.3.7's direct `fullinertia` import reconstructed some body tensors imprecisely, by as much as 4.57e-7 kg m². The initial comparison consequently missed the prescribed tolerances, with maximum M difference 2.83e-8 and inverse-dynamics difference 9.03e-8. The harness now diagonalizes the independently transcribed XML tensors with `numpy.linalg.eigh` and supplies explicit principal inertias and quaternions. It then reconstructs and checks every compiled tensor against the XML source, achieving maximum error 3.34e-16 kg m² before comparing dynamics. The production model and test tolerances were unchanged. `reference_import_diagnostic.json` retains the initial discrepancy; `reference_model_precise.xml` is the model actually used by the passing comparison.

This external check uses an independently transcribed model and a separate dynamics engine. It is stronger evidence than internal energy identities alone. It is not an independent measurement of the physical robot, a formal second-person model review, or an outward-rounded certificate. Gaz friction is checked separately against the pinned author expression and is not implemented through MuJoCo's Coulomb-friction setting. Pinocchio was not used or claimed.

The integration smoke test runs a 0.25 s plant trajectory with constant initial gravity-compensation torque, a small nonzero initial velocity, and the specified evolving disturbance. It integrates actuator/disturbance work minus frictional dissipation and checks the mechanical energy balance. It uses DOP853 with maximum steps of 1 ms and 0.5 ms. It does not implement the workbook's RK4 plant integrator, zero-order-held controller, or paper safety QP. Its h/h2 agreement therefore supports this plant smoke test only.

The remaining requirements map to the supplied material as follows:

| Requirement | Research reference | Status in the supplied Python file |
|---|---|---|
| Seven selected rigid bodies, Panda/FER geometry, flange TCP, smooth friction, additive disturbance sign | Manuscript p.2 Eqs.(1)–(3); protocol Sections 1–4; workbook T01/T03/T05 | Present and numerically checked. Source identification tooling remains unestablished; no extra hand, payload, or rotor is silently included. |
| Christoffel-consistent full C for the momentum observer | Manuscript p.2 Eqs.(3)–(5); workbook T28 | Present and checked through the full matrix identity. |
| Observer state, initialization, estimate, and envelope | Manuscript p.2 Eq.(5), p.3 Eq.(11); protocol Section 5 | Not implemented. Use the actual applied torque, initialize z=-Ko M(q0) qd0 for zero initial estimate, and preserve the observer state and global disturbance clock at replanning. |
| Slotine–Li controller | Manuscript p.2 Eq.(6); workbook T10/T11 | Not implemented. The manuscript uses e=qp-q and a positive kappa M s feedback term; importing an opposite error convention without changing signs is incorrect. |
| Translational Jacobian, squared manipulability, barrier gradients/Hessians, robust HOCBF-QP | Manuscript p.3 Eqs.(13)–(14); workbook T14/T15/T27 | Not implemented. Flange position alone is insufficient for these derivatives and 43 scalar QP inequalities. |
| Observer/tracking/residual envelopes, tube bounds and margins | Manuscript p.3 Eqs.(11)–(17); protocol Sections 3/10; workbook T18–T21 | Not implemented or certified. A sampled minimum eigenvalue must not be used as a proven global m1. |
| Free-duration quintic planner and symbolic inverse dynamics | Manuscript p.3 Eqs.(10)/(18); workbook T25/T30 | Not implemented. `evaluate()` is a numerical NumPy API and cannot be called with CasADi MX/SX decision variables. A public symbolic inverse-dynamics/kinematics interface is needed for the stated CasADi/IPOPT planner. |
| Modeled energy, objective and matched baselines | Manuscript p.3 after Eq.(18); protocol Section 8; workbook T08/T09/T23/T24 | Not implemented. Use the same representative loss coefficients, smoothing and shared-bus convention for planned and actual energy; actual energy uses applied torque and actual velocity. |
| Held-control execution, measured QP residuals, signed safety/envelope slacks and convergence | Protocol Section 8; workbook T25/T27 | Not implemented or validated. Requested 1 ms control updates and RK4 plant substeps still need their own checks. |
| Comparative task selection, common multistarts, candidate/failure logs and manifest | Protocol Sections 7–8; workbook T30 | Not supplied. This review does not select a favorable target or produce comparison results. |

There are important version differences to resolve before implementing experiments. The 24 October framework, pp.23–25, proposes constant payload mismatch, payload pickup/replanning, and several additional ablations. Protocol v1.1 and the workbook instead define a smooth time-only primary disturbance and dynamic/constant/unreserved comparisons for the initial study. The four-page manuscript supplies residual-based margins and bounded disturbance-rate assumptions; it contains no completed simulation results. These documents should not be combined by silently importing older payload or constant-disturbance assumptions into the newer protocol.

Two further implementation choices are explicitly unresolved between the available sources. The manuscript's velocity margin, p.3 Eq.(16), uses `(lambda_i + alpha_v)*chi_v`; workbook T14 derives the tighter `abs(alpha_v-lambda_i)*chi_v`. Both must not be mixed across methods. The manuscript's scalar-looking delta_h notation also needs the workbook T16 barrier-specific units/scaling for joint and manipulability rows. Neither choice affects the supplied plant module, but both affect comparative feasibility and must be recorded consistently in the eventual configuration.

For the primary numerical paper runs, the outstanding acceptance checks include maximum intervention <=1e-6 N m; independently measured normalized QP primal and stationarity residuals <=1e-9; all raw signed physical and envelope slacks nonnegative; planned terminal error <=1e-6 m; actual terminal error <=1e-3 m; and the specified integration/control-period refinements. The report supplied by you explicitly marked the independent-library validation, interval certification and closed-loop simulation as not run. This review adds external model-level numerical evidence; it does not fill the remaining controller/planner/certification fields.

A short timing diagnostic measured about 0.61 ms per validated `evaluate()` call on this computer. That excludes the QP, observer, planner, and integrator stages and is not a hard real-time benchmark. Offline simulation can run more slowly than simulated time; this measurement does not demonstrate that the complete loop can execute within a 1 ms wall-clock deadline.

The validation environment was Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, CasADi 3.7.2, and MuJoCo 3.3.7 on Windows. Full per-check results, tolerances, hashes and exclusions are in `review_test_report.json`; the original report remains separately preserved as `supplied_phase3a_test_report.json`.

Primary references used for the source cross-check are the pinned [Gaz parameter-conversion script](https://github.com/marcocognetti/FrankaEmikaPandaDynModel/blob/24d85ce4e648e2e894c832bfeee9b16711eb1a1a/matlab/ConvertDynPars2VREP/DynPars2VREP.m), [Gaz friction implementation](https://github.com/marcocognetti/FrankaEmikaPandaDynModel/blob/24d85ce4e648e2e894c832bfeee9b16711eb1a1a/matlab/dyn_model_panda/get_FrictionTorque.m), [pinned Panda arm origins](https://github.com/frankarobotics/franka_ros/blob/ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98/franka_description/robots/common/franka_arm.xacro), and [official FER joint limits](https://frankarobotics.github.io/docs/robot_specifications.html#limits-for-franka-emika-robot-fer). The reference-engine import convention follows the [MuJoCo 3.3.7 inertial documentation](https://mujoco.readthedocs.io/en/3.3.7/XMLreference.html#body-inertial).
