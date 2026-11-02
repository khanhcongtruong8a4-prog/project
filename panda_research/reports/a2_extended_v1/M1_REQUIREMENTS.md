# M1 requirements and implementable evidence API

Status: **INCOMPLETE — no official numerical bounds constructed**.

Approved mode remains M1_COMMON_FROZEN_DOMAIN_CONSTANTS; no candidate-dependent M2/local Taylor substitute is selected. Policy has no estimator grid/seed/budget, speed/acceleration/tube domain, complete numeric registry or bound equation map. Physical joint limits and the proposed 0.01 rad position extension are known; these do not define the full common domain.

The existing source-equation-linked registry is retained at `reports/a2_extended_v1/qp_bounds_evidence/run_v2/m1_requirements.json`. It lists m1, diagonal/full inverse inertia bounds, Coriolis bounds, common q/v/a/tube domains, Abar/Nbar/Bbar/Dbar, ID/HOCBF derivative bounds, chi envelopes, rho_r, beta/signed margins and residual-Lipschitz/grid requirements with shapes, units and source equation hashes. Unsupplied values remain null.

New `M1DomainSpec(q_lower,q_upper,v_lower,v_upper,a_lower,a_upper,tube_q_radius,tube_v_radius,position_extension_rad,estimator_method,seed,budget)` requires explicit finite boxes and freezes a canonical SHA-256. `M1BoundRecord` requires finite nonnegative values, units, matching common domain/evaluator hashes and estimator method/grid/seed/budget; evidence level remains distinct from certification. `M1BoundBundle.require(name,shape,units)` raises MissingM1Bound for absent entries and never supplies zeros or point estimates. Bundles/returned arrays are immutable.

Unit-test bounds are explicitly SYNTHETIC; no such bundle becomes the actual robot registry. Even complete caller records are INPUTS_PRESENT_UNVERIFIED_NO_OFFICIAL_APPROVAL, certified=false. Metadata/shape validation does not validate domain coverage, a numerical upper bound, global enclosure or human acceptance.

Next computation needs a versioned common domain/estimator policy, source-traced derivative evaluators, Level 2 samples with raw evidence and honest coverage interpretation, and independent disposition for numerical planner use. Verified enclosure/Level 1 are separate absent work. Human approval fields remain null.
