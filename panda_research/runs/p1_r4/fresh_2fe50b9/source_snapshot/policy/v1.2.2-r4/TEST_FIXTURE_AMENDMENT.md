# Synthetic history test correction before the first r4 Panda run

The first frozen contract run executed 12 tests; 11 passed and the endpoint/
history test failed because its synthetic motion required up to 5.33 N m
inside the fixture's 1 N m torque box. The hard QP correctly refused a
near-boundary solution at 3 ms. The original contract report/log and full
diagnostic updates are retained in `reports/p1_v1.2.2_r4/engineering/`.

That test is intended to verify one controller call per control update and
reuse of the actual endpoint solve over a completed short horizon. Change
only its synthetic offset from 1e-5 rad to 1e-7 rad so the exercise stays inside
the fixture's actuator limits. No assertion, physical tolerance or solver
check is removed. The separate unavailable-QP contract still checks stopping
before further actuation. This is an engineering fixture correction, not a
Panda result or a policy relaxation.

The Panda sampling code, plan, actual reference (0.01 rad components over
0.25 s), physical model, gains, disturbance, thresholds and cohort grids remain
byte-identical to freeze `52068ee`. Update the test hash and commit this amendment
before rerunning contracts and before the first r4 Panda simulation.
