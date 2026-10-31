# Independent acceptance sheets — UNSIGNED

Preparation date: 1 November 2026. Automated results support review; they do
not replace a qualified second person. Do not fill these fields automatically.
Original manifest approval fields remain null.

## T04b: 70 inertial + 21 friction entries

Evidence: T04b_inertial_70.csv and T04b_friction_21.csv; supplement.pdf pages 9
(Tables VIII/IX) and 1 (Table I); pinned DynPars2VREP.m/get_FrictionTorque.m;
reports/source_git_verification.json and reports/primary_source_checks.json.

Check every value, unit, signed off-diagonal entry, target and manifest field.
c1z is printed as an asterisk, with zero chosen by author conversion code.
Joint 2 phi1 is 0.87224 N m in revised Table I and the pinned friction code;
8722.4 is an excluded older error. The author erratum webpage was not downloaded.
Confirm COM-centered tensors, no origin shift, and no mixed older ROS inertials.

Discrepancies and disposition: __________________________________________
Reviewer name: __________________  Date/time: __________________________
Qualification/role: ______________ Signature: __________________________
Acceptance: **PENDING SIGNATURE** (accept/reject only after actual review).
Evidence bundle hash accepted: ________________________________________

## T06a: official origins/axes, frame and inertia mapping

Evidence: T06a_joint_frames_8.csv, T06a_link_parameter_mapping.json, pinned
franka_arm.xacro/utils.xacro, sources/reference_panda.urdf, and external report.
Review all seven moving links and the massless fixed flange. Check common base,
q ordering/zero offsets, local +z axes, MDH product, frame-map R=I/t=0,
COM orientation and COM tensor constructor convention. The pi/4 attribute on
the source link7 macro rotates only the fixed link7_sc collision sub-link
(utils.xacro link_with_sc); it does not rotate the arm joint frame/inertia.
No hand/payload, rotor armature, elastic or ROS damping terms are included.

Discrepancies and disposition: __________________________________________
Reviewer name: __________________  Date/time: __________________________
Qualification/role: ______________ Signature: __________________________
Acceptance: **PENDING SIGNATURE**.
Evidence bundle hash accepted: ________________________________________

## Independent dynamics acceptance

Review construction boundary in src/reference_model.py and the protocol
elementwise absolute-plus-relative tolerances. Inspect external_cases.json,
external_dynamics.csv/JSON, reference_sensitivity.json, source hashes and run
commands. Confirm all 22 original q/qd/qdd vectors and friction/gravity policies.
Pinocchio's raw C matrix is not compared; CRBA M and RNEA Cqd/ID are compared.
Numerical agreement supports the selected software model, not physical Panda
identification or a global interval bound. Do not use the prior generic PyBullet
grasp demo as research evidence.

Discrepancies and disposition: __________________________________________
Independent dynamics reviewer: _____________ Date/time: _________________
Qualification/role: ________________________ Signature: ________________
Acceptance: **PENDING SIGNATURE**.
Evidence bundle hash accepted: ________________________________________
