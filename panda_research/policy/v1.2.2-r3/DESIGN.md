# P1-r3 numerical freeze

This amendment starts at `9eb1cba` on `p1-v1.2.2`. The user explicitly
authorizes simulation development, versioned policy changes and P1/A2 numerical
testing. The exact instruction is retained in the JSON plan. This supplies
execution authority for the numerical work, not independent signatures, a
manuscript build confirmation or permission to operate hardware.

The earlier P1-r2 failure after 1.25 ms in every C4 cell remains a failure.
Its code, policy and evidence are preserved byte for byte. r2 contains no
numerical computed-torque design. The r3 startup gains are a new engineering
choice, declared here before any r3 test or plant run. There is one candidate,
no search and no pass-conditioned tuning.

At each preparation control instant use

```
u = M(q) [Kp (qmid-q) - Kd qd] + C(q,qd) qd + g(q) + F(qd) - dhat
tau = projection of u onto the physical torque box
```

Hold that torque for every RK4 plant/observer stage in the period. With
`Delta0=0.001 s` and nominal double-integrator discrete poles `r=0.25`, the
ZOH feedback equations give `Kp=(1-r)^2/Delta0^2=562500 s^-2` and
`Kd=(3-2r-r^2)/(2 Delta0)=1218.75 s^-1` for every joint. Keep these gains
fixed at both control periods. Nominal linear pole placement is a design
rationale; it is not proof of stability of the nonlinear, frictional,
torque-limited, disturbed system.

Preserve the 0.156 s signed prehold, 0.01 rad and 0.02 rad/s hold windows,
all approved model parameters, disturbance, tracking/barrier/observer gains,
limits, reserves, solver settings and thresholds. Cubic RK4 extrema plus stage
and endpoint tests check the numerical position/speed windows. These are not
verified true-ODE enclosures. No clamp, reaction torque or disturbance truth
enters the controller or DOB. The observer uses actual held torque and coupled
continuous RK4 stage measurements, including during preparation. A real
sampled/delayed observer and the separate Euler sensitivity remain unvalidated.

At physical zero transfer measured `q,qd,z` exactly, keep the observer epoch at
`-0.156 s` and keep disturbance phase. Instantiate the previously proposed
0.25 s measured-state quintic reference with offset
`[0.01,0,-0.01,0,0.01,0,0] rad`. Each cell's target is explicitly relative
to its own measured endpoint; retain coefficients, targets and target differences.
The execution controller is the original Slotine--Li law, with unchanged gains.

Evaluate the original complete 43-row hard QP at the actual endpoint with this
reference and controller. Use that solve as the first execution command.
Require every raw row nonnegative and the unchanged normalized primal and scaled
stationarity thresholds. A numerically negative raw row is a rejection, even if
ProxQP returns SOLVED. Never clip a QP torque, retry with different settings,
insert a fallback, reset the observer or soften a failed test.

Attempt the four predeclared C4 cells independently. Stop a cell on its first
failure, preserving the attempted substep and all diagnostics; a failed hold or
endpoint forbids motion in that cell. A missing/completed-but-failed cell cannot
pass the aggregate. No automatic additional refinement is authorized by this
one-candidate plan. Compare all four fixed-factor edges with the preserved
absolute/relative thresholds; disclose both cross diagonals. The energy metric
is execution-only modeled non-regenerative electrical energy, integrated with
RK4 stage quadrature, excluding prehold and the separate `w_t*T` objective term.
The minimum normalized raw slack is over accepted QP applications; retain failed
QP candidates separately and label incomplete-horizon metrics.

`FROZEN_INPUTS.json` binds the complete original tracked inventory plus this
implementation, tests and policy. Commit it before running tests. The runner
refuses uncommitted or changed frozen inputs, records the freeze commit and
retains compressed full traces, per-cell results and package/source hashes in
a new exclusive `runs/p1_r3/<timestamp>/` directory. Earlier runs are not
overwritten. Numerical failure is a result (exit 3), not a reason to change
the freeze. Exit 1 indicates an engineering or integrity error.

After the freeze:

```bash
cd /workspace/project/panda_research
/workspace/panda-venv/bin/python tests/test_p1_r3.py --report /tmp/r3-contracts.json
/workspace/panda-venv/bin/python scripts/p1_r3.py
```

Use a new report path for each test call. Run the established Action 3, signed
clock and static-screen regressions on a disposable source copy so the old
tracked report pointers remain unchanged. Reproduction by this development
agent is engineering evidence, not independent review. M1, complete T27, G2.5,
build confirmation, A3, Level 1 and publication gates remain separate and open.
