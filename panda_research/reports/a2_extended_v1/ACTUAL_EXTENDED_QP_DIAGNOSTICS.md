# Actual A2-Extended failed-QP diagnostics

**New read-only analysis; every original frozen case remains FAIL.** No ProxQP production call, new motion, gain/setting/threshold change, alternative actuation or trajectory substitution occurred.

The final attempted updates were read from hash-verified CTZ archives. The original 43 rows were reconstructed bit-for-bit from each actual q/qd/dhat/varpi state. Necessary paired speed/position conditions and physical h/psi1/speed/manipulability conditions use that actual abort state, not a nominal midpoint or zero velocity. This is not a duplicate full-prefix trajectory audit.

| Case | t s | Original ProxQP status | HiGHS LP status | LP minimum raw slack | Interior witness eta | Exact recorded-row strict feasibility |
| --- | --- | --- | --- | --- | --- | --- |
| E1 cell 1 | 0.998 | QPSolverOutput.PROXQP_PRIMAL_INFEASIBLE | 0 | -6.572520305780927e-13 | 0.9650315709761329 | True |
| E3 cell 0 | 0.095 | QPSolverOutput.PROXQP_SOLVED | 0 | -3.375077994860476e-14 | 0.9678549906279252 | True |
| E3 cell 1 | 0.076 | QPSolverOutput.PROXQP_SOLVED | 0 | -2.842170943040401e-14 | 0.9678925970164949 | True |
| E3 cell 2 | 0.0925 | QPSolverOutput.PROXQP_SOLVED | 0 | -1.2185807918285718e-12 | 0.9678647810158317 | True |
| E3 cell 3 | 0.02 | QPSolverOutput.PROXQP_MAX_ITER_REACHED | 0 | -1.3677947663381929e-13 | 0.7253550867512081 | True |

HiGHS status is a separate numerical feasibility classification, not by itself a proof. Its raw candidate signs are retained, including any small negatives. The auxiliary maximum-normalized-margin LP uses the same original affine rows and finds an interior candidate solely for analysis. When all exact dyadic row values are positive, the stored finite binary64 matrix has a mathematical strict-feasibility witness. Exact rational numerators/denominators for all 43 rows are retained. This statement is limited to the recorded rounded coefficients: it is not a validated enclosure of the exact robot model, a continuous-time theorem, or permission to actuate that candidate. No objective-optimality claim is made for the production QP.

The E1 PRIMAL_INFEASIBLE report and E3 MAX_ITER report must therefore be distinguished from a demonstrated empty feasible set whenever a strict recorded-matrix witness is present. E3 SOLVED candidates with negative floating raw rows remain rejected under the frozen zero-negative rule, even when their normalized solver residuals are small or exact-dyadic sign evaluation differs from the rounded dot-product result. No diagnostic reinterpretation restores the missing physical steps or changes a case result.

T27 implication: actual-trajectory matrices corroborate the earlier active-boundary and solver-classification limitations. They should become regression fixtures in a separately versioned solver-qualification study. Any future precision/scaling/solver or raw-sign policy change needs new reviewed/frozen experiments; no such change was selected here. Official T27, A3 and publication interpretation remain open. Human signatures remain null.

Evidence: `reports/a2_extended_v1/actual_extended_qp_diagnostics`; this report and per-case JSON contain source/CTZ hashes, all original rows and signs, LP candidates, pair conditions and exact-recorded-coefficient witnesses.
