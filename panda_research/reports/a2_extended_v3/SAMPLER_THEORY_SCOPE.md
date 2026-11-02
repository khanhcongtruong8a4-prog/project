# Digital sampler: measured quantities and claim scope

`src/panda_closed_loop/controller.py:SlotineLiController.command` computes the continuous-law request r_k. `src/panda_closed_loop/p1_r4.py:AB2TorqueController.command` computes u_0=r_0 and u_k=r_k+0.5*(r_k-r_(k-1)). `p1_r3.py:strict_qp_check` passes u_k to the full QP; `run_a2_cell` holds only the returned accepted tau_k and the same torque feeds the observer.

The half-difference is a causal two-step sampling correction that approximates the interval-average request to second order for smooth requests. It has fresh history per cell, one update per attempted solve and no future state, future estimate or disturbance-truth input. It is a changed digital realization of the continuous request, not an established sampled-data stability proof.

All entries below are seven-joint Euclidean norms in N m at APPLIED updates. RMS is sqrt(mean(||difference||_2^2)); constant Delta makes this the ZOH-time-weighted RMS over that cell's ACTUALLY executed duration. Aborted rows cover only the prefix. They do not include a rejected candidate and do not measure unobserved continuous r(t) between updates.

| Cohort/cell | Executed s | max u−r | RMS u−r | max tau−u | RMS tau−u | max tau−r | RMS tau−r |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Original fresh/0 | 0.25 | 0.00281078051987 | 0.00169109078553 | 3.79165521203e-09 | 3.41973891754e-09 | 0.00281078004003 | 0.00169109067637 |
| Original fresh/1 | 0.25 | 0.00281078060735 | 0.0016910907969 | 3.80389564292e-09 | 3.42611194931e-09 | 0.00281078012751 | 0.00169109068719 |
| Original fresh/2 | 0.25 | 0.00142112719739 | 0.000846613952262 | 3.79314557542e-09 | 3.41582624449e-09 | 0.00142112672435 | 0.00084661384435 |
| Original fresh/3 | 0.25 | 0.0014211272442 | 0.000846613958031 | 3.79314579746e-09 | 3.42308688765e-09 | 0.00142112677117 | 0.000846613849235 |
| Original fresh/4 | 0.25 | 0.00142112724705 | 0.000846613958398 | 3.80362452646e-09 | 3.42274831763e-09 | 0.00142112677401 | 0.000846613849858 |
| Original fresh/5 | 0.25 | 0.000714184227836 | 0.000423555277938 | 3.80438058834e-09 | 3.43074121718e-09 | 0.000714183758245 | 0.000423555169944 |
| Original fresh/6 | 0.25 | 0.000714184229301 | 0.000423555278121 | 3.80438081038e-09 | 3.42755924505e-09 | 0.000714183759716 | 0.000423555170301 |
| v3 E1/0 | 1 | 0.00609357228225 | 0.00339815728657 | 5.13231139869e-14 | 3.3539308249e-14 | 0.00609357228228 | 0.00339815728657 |
| v3 E1/1 | 1 | 0.00609357228223 | 0.00339815728786 | 5.13082216736e-14 | 3.36908124567e-14 | 0.00609357228227 | 0.00339815728785 |
| v3 E1/2 | 1 | 0.00306078173734 | 0.00170047899769 | 5.33943571059e-14 | 3.35294211631e-14 | 0.00306078173738 | 0.00170047899768 |
| v3 E1/3 | 1 | 0.00306078173732 | 0.00170047899834 | 5.62790341968e-14 | 3.35044290583e-14 | 0.00306078173736 | 0.00170047899833 |
| v3 E2/0 | 1 | 0.00801472280074 | 0.00433064232839 | 4.84219622996e-14 | 3.31566196194e-14 | 0.00801472280077 | 0.00433064232838 |
| v3 E2/1 | 1 | 0.00801472280073 | 0.00433064232939 | 5.83722191512e-14 | 3.36745264947e-14 | 0.00801472280077 | 0.00433064232938 |
| v3 E2/2 | 1 | 0.00402622143592 | 0.00216721263027 | 5.33866429973e-14 | 3.34712798973e-14 | 0.00402622143595 | 0.00216721263027 |
| v3 E2/3 | 1 | 0.00402622143591 | 0.00216721263078 | 5.06245535799e-14 | 3.36319954481e-14 | 0.00402622143596 | 0.00216721263077 |
| v3 E3/0 | 1 | 0.0455549560649 | 0.0200671385327 | 0.144275567976 | 0.0608088161327 | 0.144463403874 | 0.0634290970323 |
| v3 E3/1 | 1 | 0.0455549560648 | 0.0200671385331 | 0.144275567955 | 0.0608088161193 | 0.144463403856 | 0.0634290970204 |
| v3 E3/2 | 1 | 0.0228472122402 | 0.0100456243297 | 0.14425304488 | 0.0607968381707 | 0.144000423671 | 0.061307784531 |
| v3 E3/3 | 1 | 0.0228472122401 | 0.0100456243298 | 0.144253044858 | 0.0607968381573 | 0.144000423651 | 0.0613077845181 |

Detailed component max/RMS and exact machine values remain in each cell JSON and the baseline sampler JSON; the derived CSV includes every extension max/RMS pair. The fresh baseline maximum digital correction is about 0.00281078060735 N m; maximum filter correction is about 3.80438081038e-9 N m. Thus a nearly inactive QP relative to u does not establish negligible difference from continuous r. The three vector norms do not add as scalar equalities.

The baseline phrase zero intervention is an approved numerical diagnostic for ||tau-u|| <= 1e-6 N m. It is relative to the QP input u. It cannot establish tau=r, a solver error bound, continuous-law equivalence, or a whole-suite zero-intervention claim where E3 activates the filter.

Transferring continuous-time claims would require a reviewed sampled-data analysis with consistent sampler/hold/controller histories, observer discretization and error envelopes, sampling/delay/jitter assumptions, integration error enclosures, model regularity/domain bounds, and intersample constraint/tracking margins. None is proved by these measured differences. No manuscript or theorem was silently rewritten.

The user has supplied acceptance in the conversation; the exact statement is retained in the v2 predeclaration. No attributable external theory/controls signature artifact was supplied. The written review request remains unsigned until a real reviewer supplies their decision. This limits publication interpretation without erasing valid numerical runs.

## v3 safety-QP sampling scope

`src/panda_closed_loop/a2_qp_v3.py:interval_rows` samples the original affine G/c with the SAME causal half-difference, with a fresh history per cell. `IntervalHardQP.solve` executes the tightened interval QP and then independently requires all original current-state raw rows nonnegative. `audit_interval_numerics` reconstructs both row sets, actual-QP dual KKT residuals and history without a resolve. No future reference, predicted state or true disturbance is an input.

Consequently tau-u describes the intervention of THIS versioned sampled QP, including its explicitly declared engineering reserve. It is not the intervention of the original instantaneous continuous-time projection. The extra constraint margin is not a verified drift enclosure; original current-row passes remain sampled numerical checks. The sampler reviewer must address the row correction and reserve as well as u-r before drawing Section IV conclusions.
