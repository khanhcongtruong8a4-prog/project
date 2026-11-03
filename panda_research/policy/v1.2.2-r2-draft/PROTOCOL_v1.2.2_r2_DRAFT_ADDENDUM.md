# Protocol v1.2.2 r2 — DRAFT / OWNER APPROVAL PENDING

The analytical P1 screen remains accepted for development review only, as stated
in the supplied independent review. This revision adds a signed physical-clock
adapter and development applied-torque integration of the unchanged candidate.
It does not approve a startup procedure or authorize official A2.

The frozen development plan uses T_pre=0.156 s, the original gains/waveform,
0.01 rad position and 0.02 rad/s speed hold tolerances, and all four approved C4
pairings. These were recorded before the first Panda prehold. The controller
uses actual torque-box-projected Slotine–Li commands, shared with the observer.
The disturbance uses original negative physical time; z/dhat/varpi are not reset.

**Disposition: FAIL.** Every cell violates the preparation speed tolerance at
joints 3 and 7 by elapsed 1.25 ms and stops. The actual abort states have failed
full 43-row QPs and do not constitute completed zero-time endpoints. Therefore
no motion reference is instantiated/executed and official A2 remains NO-GO.

Cubic RK4 extension extrema and retained stage/endpoint checks are numerical
diagnostics, not a true-ODE error enclosure or continuous-state safety proof.
No tolerances, duration, gains, disturbance or approved solver/model parameters
are changed to obtain a pass. The failed candidate needs an explicit human
replacement decision and a new predeclared test, not a retrospective approval.

The existing nonoptimized quintic reference, coupled-continuous observer plus
sampled sensitivity proposal, development stop/A2 FAIL semantics, acceptance
thresholds and full C4 grid remain proposals as before. Preparation comparisons
are not official A2 refinement. Planner-only M1 remains outside nonoptimized A2
but required for Stage-1/A3; the planner's observer-floor witness remains failed.

Owner/theory/controls signatures, independent clean-environment review, manuscript
build confirmation and written A2 authorization remain null. Fresh engineering
reproduction does not supply those approvals. Original v1.2.1 and the earlier
v1.2.2 draft/source/evidence are preserved.
