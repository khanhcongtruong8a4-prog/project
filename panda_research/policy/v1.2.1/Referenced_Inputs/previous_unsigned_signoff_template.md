# T04b / T06a / T02 / independent dynamics acceptance — UNSIGNED

All linked paths below are relative to this delivered review package. No prior signature is implied.

## T04b — Gaz inertial and friction values
Inspect `Source_Manifest/supplement.pdf` (Tables VIII/IX PDF p.9; Table I p.1), `Source_Manifest/DynPars2VREP.m`, `Source_Manifest/get_FrictionTorque.m`, `01_Model_Verification/T04b_inertial_70.csv`, `01_Model_Verification/T04b_friction_21.csv`, and `01_Model_Verification/author_to_runtime_91_entries.csv`. Confirm source bytes, signs and COM tensor convention.

Reviewer and qualification: ____________________  Date: __________________
Discrepancies and disposition: __________________________________________
Decision: [ ] ACCEPT [ ] REJECT [ ] INCONCLUSIVE  Signature: _____________

## T06a — Official Xacro and Gaz MDH mapping
Inspect `Source_Manifest/franka_arm.xacro`, `Source_Manifest/utils.xacro`, `01_Model_Verification/T06a_joint_frames_8.csv`, `01_Model_Verification/T06a_link_parameter_mapping.json`. Check fixed flange, joint +z axes, zero offsets, link7 collision macro and no payload policy.

Reviewer and qualification: ____________________  Date: __________________
Discrepancies and disposition: __________________________________________
Decision: [ ] ACCEPT [ ] REJECT [ ] INCONCLUSIVE  Signature: _____________

## T02 — Manufacturer FER/Panda limits (not FR3)
Independently compare all rows in `01_Model_Verification/T02_FER_official_28_value_crosscheck.csv` with https://frankarobotics.github.io/docs/robot_specifications.html and applicable joint constraints. This new record is not a substitute for the missing original task-specific T02 workbook sheet.

Reviewer and qualification: ____________________  Date: __________________
Discrepancies and disposition: __________________________________________
Decision: [ ] ACCEPT [ ] REJECT [ ] INCONCLUSIVE  Signature: _____________

## Independent dynamics
Review original run in v1.2.0 package including Pinocchio/MuJoCo comparisons, shared model origin assumptions, test tolerances, raw C exclusion and remaining T28 work. The present package only crosschecks source data; it does not reproduce independent dynamics tests.

Reviewer and qualification: ____________________  Date: __________________
Decision: [ ] ACCEPT [ ] REJECT [ ] INCONCLUSIVE  Signature: _____________

Final note: Do not enter names or sign for another person. Acceptance remains pending until actual qualified review.
