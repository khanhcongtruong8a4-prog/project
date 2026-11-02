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
| v1 E1/0 | 1 | 0.00609357228268 | 0.00339815728541 | 4.20448276195e-09 | 3.65228539177e-09 | 0.00609357245693 | 0.00339815739301 |
| v1 E1/1 | 0.998 prefix | 0.00601896125637 | 0.0033906719724 | 4.20448253991e-09 | 3.6530480227e-09 | 0.00601896142345 | 0.0033906720798 |
| v1 E1/2 | 1 | 0.00306078173743 | 0.00170047899711 | 4.23607438016e-09 | 3.65549645522e-09 | 0.00306078191206 | 0.00170047910483 |
| v1 E1/3 | 1 | 0.00306078173741 | 0.00170047899776 | 4.23607504629e-09 | 3.6560145548e-09 | 0.00306078191205 | 0.00170047910557 |
| v1 E2/0 | 1 | 0.00801472280126 | 0.00433064232775 | 4.24256496601e-09 | 3.50253120284e-09 | 0.00801472301178 | 0.00433064241211 |
| v1 E2/1 | 1 | 0.00801472280126 | 0.00433064232875 | 4.2425654101e-09 | 3.50325899502e-09 | 0.00801472301177 | 0.00433064241315 |
| v1 E2/2 | 1 | 0.00402622143619 | 0.00216721262995 | 4.24384882792e-09 | 3.50251635203e-09 | 0.0040262216141 | 0.00216721271442 |
| v1 E2/3 | 1 | 0.00402622143618 | 0.00216721263046 | 4.243849272e-09 | 3.50431608565e-09 | 0.00402622161409 | 0.00216721271488 |
| v1 E3/0 | 0.095 prefix | 0.0437449330941 | 0.0256159707032 | 0.0659372690311 | 0.0324145344966 | 0.0647545307055 | 0.0405525185338 |
| v1 E3/1 | 0.076 prefix | 0.0437449330982 | 0.0283205046367 | 0.0470641843409 | 0.0222024422451 | 0.04721191054 | 0.0354398438173 |
| v1 E3/2 | 0.0925 prefix | 0.0218519405059 | 0.0129739673241 | 0.0630143568714 | 0.0306245909778 | 0.0623848242014 | 0.0328160695322 |
| v1 E3/3 | 0.02 prefix | 0.0218519405085 | 0.0193547737727 | 3.80547815482e-09 | 3.56775968739e-09 | 0.0218519404752 | 0.0193547737366 |

Detailed component max/RMS and exact machine values remain in each cell JSON and the baseline sampler JSON; the derived CSV includes every extension max/RMS pair. The fresh baseline maximum digital correction is about 0.00281078060735 N m; maximum filter correction is about 3.80438081038e-9 N m. Thus a nearly inactive QP relative to u does not establish negligible difference from continuous r. The three vector norms do not add as scalar equalities.

The baseline phrase zero intervention is an approved numerical diagnostic for ||tau-u|| <= 1e-6 N m. It is relative to the QP input u. It cannot establish tau=r, a solver error bound, continuous-law equivalence, or a whole-suite zero-intervention claim where E3 activates the filter.

Transferring continuous-time claims would require a reviewed sampled-data analysis with consistent sampler/hold/controller histories, observer discretization and error envelopes, sampling/delay/jitter assumptions, integration error enclosures, model regularity/domain bounds, and intersample constraint/tracking margins. None is proved by these measured differences. No manuscript or theorem was silently rewritten.

The user has supplied acceptance in the conversation; the exact statement is retained in the v2 predeclaration. No attributable external theory/controls signature artifact was supplied. The written review request remains unsigned until a real reviewer supplies their decision. This limits publication interpretation without erasing valid numerical runs.
