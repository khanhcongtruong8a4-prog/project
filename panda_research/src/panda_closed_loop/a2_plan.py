"""A2 draft completeness checks; no approval inference or execution capability."""
import numpy as np
from .contracts import scalar, vector


def quintic_reference_coefficients(q_start, qd_start, offset, duration):
    q=vector(q_start,'measured start q');v=vector(qd_start,'measured start qd')
    dq=vector(offset,'predeclared offset');T=scalar(duration,'duration s',positive=True)
    return np.vstack([q,T*v,np.zeros(7),10*dq-6*T*v,-15*dq+8*T*v,6*dq-3*T*v])


def check_plan(draft, policy, screen=None, preparation=None):
    items=[]
    def add(key,status,reason,required=True):
        items.append({'item':key,'status':status,'reason':reason,'required':required})
    pending='AWAITING HUMAN REVIEW'
    prep=(preparation or {}).get('summary',{})
    cells=prep.get('cells',[])
    prep_tested=bool(cells)
    expected_grid=policy.raw['integration']['validation_grid']
    prep_pass=(prep.get('P1_numerical_hold')=='PASS' and
        [c.get('grid') for c in cells]==expected_grid and
        all(c.get('completed') and c.get('valid_zero_endpoint') for c in cells))
    clock_tests=(preparation or {}).get('clock_tests',{})
    add('policy_v122_approval',pending,'DRAFT / OWNER APPROVAL PENDING; not a signed revision')
    reference=draft.get('A2_execution_reference',{})
    kind=reference.get('kind')
    if kind not in ['nonoptimized_measured_state','stage1_tightened']:
        add('reference_definition','FAIL','Reference kind is not specified')
    elif kind=='nonoptimized_measured_state':
        complete=all(reference.get(k) is not None for k in ['duration_s','joint_offset_rad','formula','initial_rule','endpoint_rule','actual_terminal_position_error_m'])
        add('reference_fields','PASS' if complete else 'FAIL','Formula/initial/endpoint/duration/accuracy are proposed, not approved')
        add('planner_only_M1_inputs','PASS','Not used by a non-optimized smoke reference; remain OPEN for A3/G2.5',required=False)
    else:
        complete=all(policy.raw['margin_mode'][k] is not None for k in ['constant_values','equation_map','speed_domain','acceleration_domain','tube_extension'])
        add('stage1_M1_inputs','PASS' if complete else 'FAIL','Tightened Stage-1 references need their actual M1 bounds/plan')
    add('reference_initial_state_measured','PASS' if prep_pass else 'NOT TESTED',
        'Completed measured zero-time endpoints available' if prep_pass else 'No valid completed prehold endpoint; abort states cannot replace q(0),qd(0)')
    add('reference_owner_controls_decision',pending,'Reference choice and new measured-endpoint start rule require approval')
    candidate=(screen or {}).get('P1_candidate',{})
    sampled=candidate.get('sampled_pair_screen_passed')
    add('P1_sampled_pair_screen','PASS' if sampled else 'NOT TESTED' if sampled is None else 'FAIL',
        'Numerical predeclared nodes only; no continuous-box enclosure')
    qp=candidate.get('complete_QP_fixture',{}).get('numerical_pass')
    add('P1_complete_point_QP','PASS' if qp else 'NOT TESTED' if qp is None else 'FAIL',
        'Fixed midpoint/zero-velocity estimate fixtures; not physical prehold endpoints')
    hold_status=('PASS' if prep_pass else 'FAIL') if prep_tested else 'NOT TESTED'
    add('physical_prehold_dynamics',hold_status,'Applied-torque model prehold checked; frozen acceptance failed' if prep_tested and not prep_pass else
        'Numerical development hold only; no physical hardware or continuous ODE certification' if prep_pass else 'No prehold evidence supplied')
    add('hold_tracking_torque_end_conditions',hold_status,'No tolerance relaxation or post-failure duration change; require a valid zero-time endpoint')
    add('signed_physical_prehold_clock','PASS' if clock_tests.get('overall_pass') else 'NOT TESTED',
        'Signed adapter continuity and applied-torque contracts have engineering unit evidence; policy approval remains separate')
    if prep_tested:
        add('continuous_true_ODE_neighborhood','NOT TESTED','Cubic numerical interpolation is not an ODE error enclosure; observed violations already reject this candidate')
        add('actual_zero_endpoint_full_QP','PASS' if prep_pass else 'NOT TESTED','Only a completed valid t=0 endpoint can satisfy this gate; stopped states do not qualify')
        add('prehold_failure_disposition',pending,'Theory/controls and owner must explicitly redesign/redeclare a candidate or choose an alternative; no automatic retuning')
    add('prehold_owner_theory_controls_decision',pending,'P1 is the explored proposal, not an approved startup change')
    grid=draft.get('integration',{}).get('validation_grid')
    expected=policy.raw['integration']['validation_grid']
    add('C4_grid','PASS' if grid==expected else 'FAIL','Later approved C4 includes (Delta=.5ms,h=.25ms), m=2; supersedes old h=Delta/4 default')
    add('observer_method_fields','PASS' if draft.get('observer_proposal',{}).get('method') else 'FAIL','Coupled-continuous RK4 and separate sampled sensitivity are explicitly proposed')
    sensitivity=draft.get('observer_proposal',{}).get('sampled_sensitivity_definition',{})
    add('sampled_observer_sensitivity_definition','PASS' if all(sensitivity.get(k) is not None for k in ['update','cadence','plant_state_rule','acceptance']) else 'FAIL',
        'Sampled sensitivity must declare update, cadence, held-state rule and acceptance before execution')
    add('observer_execution_approval',pending,'No physical sampled-observer bound inferred')
    add('infeasibility_semantics','PASS' if draft.get('failure_semantics',{}).get('recovery_enabled') is False else 'FAIL',
        'Proposed A2 FAIL / development NO-ADVANCE request; not safe hardware zero torque; no unapproved Kb/gamma')
    add('infeasibility_policy_approval',pending,'Owner/controls must approve the proposed stop semantics')
    metrics=draft.get('A2_acceptance_proposal',{})
    required_metrics=['physical_state','raw_CBF_rows','applied_torque','observer_envelope','QP','refinement','terminal_task','evidence_level']
    add('acceptance_metric_definitions','PASS' if all(metrics.get(k) is not None for k in required_metrics) else 'FAIL',
        'Physical, observer, QP, refinement and terminal criteria must all be explicit; approvals are separate')
    preserved=draft.get('fixed_acceptance_thresholds')==policy.raw['fixed_acceptance_thresholds']
    add('approved_acceptance_thresholds_preserved','PASS' if preserved else 'FAIL','Draft retains the approved v1.2.1 numerical thresholds')
    missing=[k for k in ['gains','disturbance','physical_parameters','energy','solver','margin_mode'] if draft.get(k)!=policy.raw[k]]
    add('v121_parameters_preserved','FAIL' if missing else 'PASS','Unchanged baseline fields: '+(', '.join(missing)+' differ' if missing else 'gains/disturbance/reserves/energy/solver/M1'))
    if reference.get('kind')=='nonoptimized_measured_state':
        try:
            scalar(reference.get('duration_s'),'reference duration',positive=True)
            vector(reference.get('joint_offset_rad'),'reference offset')
            scalar(reference.get('actual_terminal_position_error_m'),'terminal tolerance',positive=True)
            valid=True
        except (ValueError,TypeError):
            valid=False
        add('reference_numeric_fields','PASS' if valid else 'FAIL','Duration, seven offsets and terminal tolerance must be finite and correctly shaped')
    add('full_A2_refinement','NOT TESTED','No official A2 or actual 2x2 closed-loop run executed')
    add('independent_clean_environment_rerun',pending,'Controls reviewer must rerun scripts/action3.py validate; engineering reruns are not that signature')
    add('manuscript_build_revision',pending,'02/03 equation hashes match; main.tex and Project.rar discrepancies need responsible confirmation')
    for role in ['controls_reviewer_signature','theory_reviewer_signature','written_A2_authorization']:
        add(role,pending,'No signature or written execution authority generated/inferred')
    return {'policy_status':'DRAFT_OWNER_APPROVAL_PENDING','reference_kind':kind,'items':items,
            'official_A2':'NO-GO','A1_component_development':'GO',
            'P1':('PASS_NUMERICAL_ONLY_POLICY_PENDING' if prep_pass else 'FAIL_PREDECLARED_TORQUE_HOLD') if prep_tested else 'BLOCKED_UNVERIFIED_PHYSICAL_PREHOLD',
            'A3':'NO-GO','Level_1':'NO-GO','publication':'NO-GO','execution_performed':False,
            'development_prehold_evidence_supplied':prep_tested,
            'checker_scope':'Completeness and recorded evidence only; never authorizes a run'}
