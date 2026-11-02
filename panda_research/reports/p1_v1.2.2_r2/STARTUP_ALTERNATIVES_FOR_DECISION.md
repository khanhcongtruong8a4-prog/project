# Startup alternatives for human decision — no values selected

The frozen P1 fails its preparation speed tolerance after 1.25 ms. Original
physical h/psi1/speed and applied-torque sample checks remain nonnegative until
abort; the failed criterion is the specifically declared preparation speed
window. This evidence does not justify enlarging that window after the fact.

| Alternative | Evidence needed before a newly authorized test | Main consequence |
| --- | --- | --- |
| Redesign P1 | Freeze a revised applied-torque holding controller or scientifically justified admissible region; establish continuous/numerical-error validity and actual zero endpoint under legitimate observer bounds | Current controller/tolerance candidate is rejected. Original static online screen remains only a conditional point screen; planner floor issue remains separate. |
| P2 gain amendment | Review both alpha_v and alpha1*alpha2, the changed abs(alpha_v-Lambda)*chi_v term, actual M1 bounds/tightening and full QP | At the unchanged initial midpoint, online necessary limits are alpha_v>=43.8324932 /s and alpha1*alpha2>=32.9050056 /s². These are lower limits, not selected gains or sufficient conditions. |
| P3 disturbance amendment | Scientific justification, signed revised disturbance policy and identical choices across methods before any new screen | At the initial midpoint, online pairs alone would require amplitude fraction<=0.00228141255; planner/tube/QP constraints could be stricter. This changes the study and is not selected. |
| P4 theory/initialization amendment | New manuscript hashes, exact initialization/relaxation semantics and independent theory review | No theory or recovery rule is changed by this task. |

Even at the observer floor the midpoint planner factor-two lower speed condition
requires alpha_v>=6.13664905 /s, exceeding the existing 5 /s.
Initial planner factor-two point lower limits are alpha_v>=87.6650864 /s and
alpha1*alpha2>=65.8102112 /s².
No pointwise abs(N) is promoted to an M1 upper bound. Nonnegative rho/beta/tube
terms and a changing gain-cancellation term can raise the actual requirements.
No lower limit in this table authorizes a new numerical value, a gain sweep,
a longer hold, official A2 or Stage-1 planning.

The theory/controls leads and owner must make a documented choice and freeze a
new candidate before testing. See [the three actions](NEXT_THREE_ACTIONS.md).
