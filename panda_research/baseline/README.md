# IC2AI 2027 — Phase 1 (three reviewer actions)

**Status:** Engineering model implementation and reproducible internal numerical tests. **Not a simulation result or a mathematical certificate.**

This package implements the selected Gaz seven-body Panda rigid model as documented in `Action_2026-10-31.docx`, not the older, incompatible Action Pack numerical alternatives.

## Files

- `model_manifest_v1.json` — frozen, hashed selected dynamics/data conventions and explicit pending signatures.
- `panda_dynamics.py` — single CasADi-AD dynamics evaluator for M(q), derivatives, Christoffel C(q,qdot), g(q), F(qdot), U(q), flange position, acceleration and ID.
- `run_phase3a_tests.py` — fixed-seed self-consistency tests (no optimizer/filter implemented).
- `phase3a_test_report.json` — actual observed numerical test outcomes and errors.
- `Protocol_v1_1_DRAFT.docx` — original protocol retained, with versioned addendum, task-ID errata, and blank approval fields.
- `Protocol_v1_1_DRAFT.txt` — concise standalone decision amendment, approvals pending.
- `model_check_summary.txt` — source review findings, limitations and next test gates.

## Run

Requirements: Python 3.13+, NumPy 2.3+, SciPy 1.17+, CasADi 3.7+ (versions recorded in report). Run:

```bash
python run_phase3a_tests.py
```

The routine checks 20 fixed-seed interior configurations plus a mathematical zero pose and physical box midpoint. The zero pose need not satisfy the physical joint box; it tests kinematics algebraically.

`PandaDynamics().evaluate(q, qd, qdd)` returns `M`, `dM` (shape 7 x 7 x 7, third axis d/dq), `C`, `g`, `F`, `U`, `flange` and `ID`.

## Non-claims

- The pinned Gaz author source and older ROS Xacro provide source-level parameter/kinematic cross-checks; source byte checks and Gaz/Pinocchio ID agreement are **not** performed. The short reviewer reply did not define exact protocols for T04b/T06a, so our primary checks are transparently interpreted implementations and still need independent sign-off.
- Positive eigenvalues at 22 poses **do not** establish a global, outward-rounded `m1` certificate.
- None of the observer, closed-loop controller, QP, planner, model variation bounds, G2.5 or T27 are yet implemented or tested here.
- Not a validation of physical Panda friction, payload identification, current limit, rotor inertia, or motor-loss coefficients.

## References (pinned)

Gaz source code: https://github.com/marcocognetti/FrankaEmikaPandaDynModel/blob/24d85ce4e648e2e894c832bfeee9b16711eb1a1a/matlab/ConvertDynPars2VREP/DynPars2VREP.m

Gaz friction: https://github.com/marcocognetti/FrankaEmikaPandaDynModel/blob/24d85ce4e648e2e894c832bfeee9b16711eb1a1a/matlab/dyn_model_panda/get_FrictionTorque.m

Older Panda Xacro: https://github.com/frankarobotics/franka_ros/blob/ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98/franka_description/robots/common/franka_arm.xacro

FER limits: https://frankarobotics.github.io/docs/robot_specifications.html
