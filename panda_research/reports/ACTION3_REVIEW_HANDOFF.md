# Action 3 review handoff — v1.2.1

Run: `runs/action3/20261101T172354305225Z`. Result: **PASS_COMPONENTS_AND_REGRESSIONS_A2_HOLD**.
All source/code/policy hashes, exact commands, effective configuration and logs
are in this run. New source/test snapshots are retained. Original source
archives, LaTeX, workbook, v1.2.0 evidence and human signatures were not edited.

## Component status

| Item | Result |
| --- | --- |
| Policy bytes, equation-source hashes, workbook cells | See source_audit.json; canonical equation files match |
| Momentum observer, Slotine-Li, 43 robust rows, hard QP, RK4 and contracts | True; 19 tests executed |
| T28 independent raw-C convention check | PASS (22 poses x 3 FD steps) |
| Preserved source/Pinocchio/MuJoCo baseline regression | PASS |
| Approved Panda initial midpoint hard-QP feasibility | FAIL_INFEASIBLE_WITH_APPROVED_INITIAL_VARPI |
| Official A2 / full A2 2x2 refinement | NOT_RUN / BLOCKED |
| Complete T27 / G2.5 | NOT_RUN; solver fixtures and static point check are not these experiments |
| A3 / Level 1 / publication experiments | NOT_RUN / NO-GO |

## Critical static component result

Current run contains point diagnostics: **True**. The numerical values
below describe the retained point fixture; consult the current component JSON
before attributing them to this run if a test was not executed.

At the approved q0 midpoint, qdot=0 and varpi0=0.02*tau_max, the paired speed
rows require `abs(M^-1)@varpi0 <= alpha_v*vmax`. This necessary condition fails
for joints 1,3,4,5,6,7. For joint 1 it is approximately 93.325 versus 10.875
rad/s^2. ProxQP returns PRIMAL_INFEASIBLE. No torque is applied and no plant
state is advanced. This is configuration/point-specific evidence, not a global
impossibility theorem or a completed G2.5 screen. The position pairs also fail
for joints 1 and 3. The separate P1 static screen and draft policy are described
in reports/p1_v1.2.2/REVIEWER_ISSUE_RESPONSE.md; they authorize no execution.
No gain/disturbance/bound was
retuned or replaced to obtain a pass. The passing unit test verifies detection
and stop behavior; it does not label the infeasible configuration feasible.

## Numerical conventions and limitations

- Observer z is integrated with plant q/qd using coupled RK4, actual held torque
  and stage state measurements. This is a declared COMPONENT convention; the
  approved policy's observer-update field remains null. Its independent dhat-ODE
  comparison does not validate a real sampled/delayed observer envelope.
- Controller and safety QP update once per Delta; applied torque is held for
  all RK4 stages. True disturbance enters only the plant; truth is logged for
  diagnosis after control computation. Replanning preserves z, global time and
  the propagated envelope. The deterministic reference is a measured-state
  fixture, not an optimized Stage-1 solution.
- Dense ProxQP 0.7.2 uses the supplied settings. Each component solve is cold;
  this is not an approved future warm-start policy. Actual normalized primal,
  scaled stationarity, complementarity, duality gap and raw negative slacks are
  retained. Numerical acceptance is not a proof of invariance or solver error.
- T28 forms a Christoffel reference from five-point derivatives of independent
  source-built Pinocchio CRBA M, never target dM. Raw library C is diagnostic
  only; FD comparisons at 22 states are not a global convention proof.
- Recovery is DISABLED because K_b, gamma and discrete recovery semantics are
  not supplied. A hard-QP failure requests replan/protective stop and provides
  no fabricated safe torque. The torque-box projection alone is tested.
- M1 domains/constants, derivative/tube bounds, estimator policy and discrete
  observer justification remain OPEN in M1_requirements.json. No null was
  replaced by zero. Planner-only constants are required for Stage-1 references
  and A3, not unconditionally for a non-optimized A2 reference. The A2 reference
  choice itself remains unapproved. No planner result is used to clear A2.
- The source archive and main.tex differ from policy hashes. The two canonical
  equation files match. Manuscript build-revision acceptance remains open.
- The T29 CSV's old NOT_APPROVED status is preserved; v1.2.1 C6 explicitly
  approves the protocol row-scale rule, not a nonexistent T29 worksheet.

## Reproduce

```bash
.venv/bin/python scripts/action3.py preflight
.venv/bin/python scripts/action3.py validate
.venv/bin/python scripts/action3.py a2  # intentionally exits 2 with blockers
```

The validate command includes all established dynamics/source/Pinocchio/MuJoCo
tests. Inspect per-test JSON and logs, not only aggregate counts. Every call
creates a new run directory, retaining failures and earlier outputs.

## Gates

A1 GO. A2 NO-GO/HOLD under current inputs and initial-QP result. A3, Level 1
and publication NO-GO. Owner design acceptance is recorded in the supplied
policy; it is not a second-person signature. No official A2, planner comparison
or certification run was executed.

## Exactly three prioritized next actions

| Priority | Owner | Artifact | Objective acceptance criterion |
| --- | --- | --- | --- |
| 1 | Theory lead + controls lead + project owner | Reviewed startup disposition and versioned policy | Resolve both online pair families, full QP and physical prehold validity under the same frozen values; P1 remains a proposal |
| 2 | Project owner + controls lead | Frozen A2 reference, observer, failure semantics and metrics | Scope planner M1 to a Stage-1 reference, preserve all four C4 cells, and approve all proposed execution fields |
| 3 | Independent controls reviewer + numerical lead + build owner | Clean-environment reproduction, build confirmation and written A2 authorization | Inspect component/T28/regression code, reproduce validate, confirm main.tex/Project.rar revision and record genuine signatures before a separately authorized A2 |
