Continue the IC2AI 2027 Panda simulation project using the attached Codex Next Actions Prompt and QP_REPRODUCTION.zip.

Your primary objective is to resolve the remaining numerical and planner-feasibility blockers before A3.

Priority 1: Investigate the eight active-filter refinement failures. Examine the AB2 digital controller, zero-order-held torque, active-set transitions and control-period sensitivity. Preserve the original failures and acceptance thresholds. Implement only mathematically justified, versioned corrections.

Priority 2: Complete the M1 common-domain bound registry and conduct G2.5 feasibility screening using the intended final policy, including the factor-two planner constraints, torque bounds and manipulability conditions. Clearly distinguish sampled estimates from certified bounds.

Priority 3: Consolidate the corrected guarded-QP implementation, independently reproducible T27 evidence, exact feasible/infeasible witnesses and unchanged A2 regression results.

Do not alter the robot model, disturbance, controller gains, numerical thresholds or safety constraints simply to obtain passing results. Preserve all historical failures and maintain fail-closed behavior.

You are authorized to implement and run development diagnostics, but do not execute official A3 comparisons or claim Level 1 certification until their separate verification gates pass.

Deliver a reproducible ZIP, a detailed issue-resolution report, and explicit GO/NO-GO decisions for each remaining stage.

User clarification: Instead of sending a .txt file, the user sent its contents directly in the message.
