# Three actions after the frozen P1 failure

| Priority | Responsible owner | Artifact | Acceptance criterion |
| --- | --- | --- | --- |
| 1 | Theory lead + controls lead, project owner decides | Signed disposition of failed P1 and a newly versioned candidate/test plan | Acknowledge the 1.25 ms counterexample. Explicitly choose a redesigned holding controller/admissible region or P2/P3/P4. Freeze all new choices before tests. Keep the old failed duration/tolerances/evidence; do not relabel this P1 as valid by owner approval alone. |
| 2 | Controls lead + numerical lead | Valid actual zero-time endpoint and complete entry/definition package | After separate authorization, establish the chosen holding dynamics and continuous-state/numerical-error handling, measured q/qd/z and propagated varpi at zero, h/psi1/speed/manipulability/torque and full 43-row QP. Then finalize reference, observer, fail handling and all four C4 A2 cells. Preparation-grid tests are not full A2. |
| 3 | Independent controls/theory reviewers + manuscript/build owner; project owner grants A2 authority | Independent reproduction/signatures, confirmed build hashes and separate written A2 authorization | Independently inspect equations and rerun `python scripts/action3.py validate` plus the relevant frozen startup tests in a clean pinned environment. Confirm main.tex/Project.rar revision. Record genuine signatures and explicit A2 authorization only after startup/entry gates hold. Planner M1/G2.5 and A3 remain separate later gates. |

No alternative gain, holding tolerance, disturbance or theory change is selected
or executed by this remediation. Pre-settling alone also leaves the nominal
planner floor contradiction for joints 1 and 3.
