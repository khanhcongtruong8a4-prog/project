"""Build the reviewer disposition, proposed freeze and decision register."""
from pathlib import Path
import csv
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def load(name):return json.loads((ROOT/name).read_text())
def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
def save(name,data):(ROOT/name).write_text(json.dumps(data,indent=2)+'\n')


def main():
    original=load('reports/original_reproduction.json')
    external=load('reports/external_dynamics.json')
    sources=load('reports/primary_source_checks.json')
    corrected=load('reports/corrected_internal_tests.json')
    decisions=[
        ('D01','M1 versus M2','M1 common constants proposed; not team-approved','Team lead/controls','Approve M1 and obtain exact envelope/dependency equations'),
        ('D02','Missing mathematical framework','OPEN','Controls/theory owner','Supply earlier senior-engineer framework and decision brief; manuscript if available'),
        ('D03','Frozen domain/constants','OPEN','Dynamics/controls','Select speed/acceleration/tube domains, estimator grid/seed/budget and every constant/formula/unit'),
        ('D04','DOB K_o (T10)','UNSELECTED','Controls','Choose positive 7-vector gains, units s^-1'),
        ('D05','Tracking Lambda/kappa (T11)','UNSELECTED','Controls','Choose gains and units consistent with manuscript'),
        ('D06','HOCBF gains (T14)','UNSELECTED','Controls','Choose alpha_1/alpha_2/alpha_v and initial conditions'),
        ('D07','w_min and physical reserves','UNSELECTED','Controls','Choose w_min>0, all signed margins/reserves and row scales'),
        ('D08','Electrical coefficients/objective (T08/T09)','UNSELECTED','Energy/model owner','Supply representative k_r, smoothing, w_t, durations, sensitivity multipliers; do not claim calibration'),
        ('D09','T22 Scenario A','PENDING APPROVAL/SELECTION','Team lead','Approve retained selection rule; freeze selected index/task/plan before baselines'),
        ('D10','Scenario B target suite','PROPOSED FIXED LIST','Team lead','Approve the 64-target file and its hash before either method runs'),
        ('D11','Solver/transcription/T23/T30','UNSELECTED','Optimization lead','Freeze NLP/QP solver versions, settings, grid, T23 maximum construction, derivatives, warm starts, seeds, multistarts and budgets'),
        ('D12','Integrator/control period T29','PROPOSED METHOD / VALUES UNSELECTED','Controls','Approve RK4/refinement proposal; select Delta, m, validation grid and exact update/hold semantics'),
        ('D13','Source/frame/dynamics acceptance','PENDING SIGNATURE','Qualified independent dynamics reviewer','Review and sign T04b/T06a and external dynamics evidence'),
        ('D14','Research master workbook','MISSING','Research owner','Supply read-only registry to reconcile all frozen values and tracker IDs'),
        ('D15','A2/T27/G2.5','NOT_RUN','Engineering after prerequisites','Authorize A2 only after review/settings; run refinement, solver accuracy and frozen tightening screen'),
        ('D16','Signed protocol/manifest','PENDING SIGNATURE','Team lead/controls','Complete all values then sign/date/hash actual approved artifacts'),
        ('D17','Level 1 m1 and theorem conditions','NOT_RUN','Verification/theory reviewer','Outward-rounded global m1>0 and all other required verified bounds'),
    ]
    with (ROOT/'protocol/unresolved_decisions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','topic','state','owner_role','required_action']);w.writerows(decisions)
    suite='protocol/scenario_b_target_suite_PROPOSED.json'
    config={
        'schema_version':'proposal-1.1-R1','prepared_date':'2026-11-01',
        'status':'INCOMPLETE_PROPOSAL_NOT_APPROVED_NOT_EXPERIMENT_FROZEN',
        'baseline_model_manifest_sha256':sha('baseline/model_manifest_v1.json'),
        'baseline_evaluator_sha256':sha('baseline/panda_dynamics.py'),
        'working_evaluator_sha256':sha('src/panda_dynamics.py'),
        'model_identity':'Unchanged seven Gaz moving bodies; c1z author zero; signed COM tensors; smooth author friction; no hand/payload/rotor/elastic states',
        'gravity_world_m_s2':[0,0,-9.80665],'base_transform':'identity','joint_zero_offsets_rad':[0]*7,
        'fixed_flange_z_m':.107,'tcp':'panda_link8 flange','task_orientation':'free',
        'technical_external_validation':external['status'],'human_dynamics_acceptance':None,
        'proposed_comparison_evidence_level':'Level 2 NUMERICAL/SAMPLED, not approved',
        'margin_mode':{'proposed':'M1','approved':None,'constant_values':None,'equation_map':None,
                       'position_domain_extension_rad':.01,'speed_domain':None,'acceleration_domain':None,
                       'tube_extension':None,'estimator_grid':None,'estimator_seed':None,'estimator_budget':None,
                       'update_frequency':'Once per frozen configuration; identical across candidates/methods'},
        'disturbance':{'status':'Retained study proposal; team approval pending','type':'dual harmonic',
                      'amplitude_fraction':.02,'omega_rad_s':1,'t_ref_s':0,'phase_i':'2*pi*(i-1)/7',
                      'dbar_i':'0.02*tau_max_i','dbar1_i':'1.4*dbar_i*omega','global_clock':True},
        'observer_initialization':{'dhat0':0,'z0':'-K_o*M(q0)*qd0','varpi0':'dbar','replan':'retain observer and propagated bound'},
        'gains':{'K_o_s_inverse':None,'Lambda':None,'kappa':None,'alpha_1':None,'alpha_2':None,'alpha_v':None},
        'physical_parameters':{'w_min':None,'position_reserve_rad':None,'velocity_reserve_rad_s':None,
                               'torque_reserve_Nm':None,'barrier_reserves':None},
        'energy':{'wording':'MODELED non-regenerative electrical energy','k_r':None,'w_t_W':None,
                  'nonregenerative_smoothing':None,'sensitivity_protocol':None,'T_min_s':None,'T_max_s':None},
        'scenario_A_T22':{'rule':'Original protocol section 7 retained; proposal-conditioned','approval':None,'selected_index':None,
                         'target':None,'plan_hash':None,'configuration_hash':None},
        'scenario_B':{'file':suite,'sha256':sha(suite),'seed':20261102,'target_count':load(suite)['included_count'],
                      'approval':None,'multistart_seed':None,'multistart_count':None,'all_initial_guesses':None,
                      'aggregation_plan':None,'include_all_failures':True},
        'solver':{'NLP':None,'NLP_version':None,'NLP_settings':None,'QP':None,'QP_version':None,'QP_settings':None,
                  'transcription':None,'grid':None,'budgets':None,'warm_start_policy':None,
                  'T23_constant_maximum_formula':None,'nonsmooth_derivative_policy':None},
        'integration':{'proposed_method':'fixed-step RK4','approved_method':None,'control_period_s':None,
                       'substeps_m':None,'h_s':None,'validation_grid':None,'observer_update_semantics':None,
                       'max_refinement_rounds_proposed':3,'refinement_approval':None,'A2_executed':False},
        'fixed_acceptance_thresholds':{'relative_refinement':1e-4,'energy_abs_J':1e-6,'duration_abs_s':1e-6,
            'intervention_difference_abs_Nm':1e-7,'normalized_slack_difference_abs':1e-6,
            'zero_intervention_Nm':1e-6,'QP_normalized_primal':1e-9,'QP_scaled_stationarity':1e-9,
            'minimum_reserve_to_row_scale_strictly_greater_than':1e-7,'planned_terminal_error_m':1e-6,
            'actual_terminal_error_m':1e-3,'raw_negative_slack':'FAIL even near numerical resolution'},
        'approvals':{'T04b_second_reviewer':None,'T06a_second_reviewer':None,'team_lead':None,
                     'controls_reviewer':None,'T22':None,'T29':None,'protocol_v1_1':None},
        'gates':{'A2':'BLOCKED','A3':'NO-GO','Level_1':'NO-GO','publication':'NO-GO'}
    }
    save('protocol/proposed_frozen_configuration.json',config)
    missing={
        'supplied':['Handoff prompt TXT','Phase1 ZIP (9 members)','Full-package reviewer DOCX','Action_2026-10-31.docx'],
        'missing_required_for_full_protocol_freeze':[
            'IC2AI_2027_Simulation_Research_Master.xlsx (read-only)',
            'IC2AI_2027_Senior_Engineer_Model_and_Verification_Prompt_2026-10-31.txt',
            'IC2AI_2027_Simulation_Decision_Brief.docx'],
        'missing_optional':['Project.rar manuscript sources/PDFs'],
        'historical_not_supplied_not_merged':['IC2AI_2027_Section_IV_Action_Pack_2026-10-31.xlsx'],
        'not_independently_retrieved':['Gaz main-paper institutional PDF','Author erratum webpage'],
        'impact':'P0/source-table/external numerical checks complete without these; exact equation-level planner mapping, registry reconciliation, hardware identification claims and signed protocol freeze remain unavailable'}
    save('reports/input_inventory.json',missing)
    issues=[
        ('R01','No external dynamics reference','CLOSED TECHNICAL; HUMAN ACCEPTANCE PENDING','reports/external_dynamics.json','594 quantity/pose comparisons pass; source-built Pinocchio CRBA/RNEA; no raw C equality claim'),
        ('R02','T04b primary source/signature missing','PARTIALLY RESOLVED','review_sheets/T04b_inertial_70.csv; review_sheets/T04b_friction_21.csv','70+21 rows source-crosschecked, no mismatch; c1z exception explicit; qualified signature absent; erratum webpage not retrieved'),
        ('R03','T06a primary Xacro/signature missing','PARTIALLY RESOLVED','review_sheets/T06a_joint_frames_8.csv','All origins/axes, actual target literal origins/rolls, MDH maps and flange checked; human signature pending'),
        ('R04','Margin mode and NLP coupling unspecified','PARTIALLY RESOLVED','protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.md section 2','M1 proposed; update/dependency/feasible-set policy explicit; exact missing-framework equations, constants and approval remain open'),
        ('R05','Misleading test notes/internal identities','CLOSED IN WORKING COPIES','reports/code_changes.patch; reports/original_reproduction.json','Names/notes corrected, internal evidence classes explicit; original historical files unchanged; separate external evidence added'),
        ('R06','Scenario B selection bias safeguard','PARTIALLY RESOLVED','protocol/scenario_b_target_suite_PROPOSED.json','64 method-independent targets fixed as a proposal before methods run; T22 selection bias disclosed; team approval/shared settings remain open'),
        ('R07','Control-period refinement missing','PARTIALLY RESOLVED','protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.md section 4','Integrator AND control-period refinement specified with unchanged thresholds; values, approval and A2 execution pending'),
        ('R08','19/19 only historical/log-reported','CLOSED: REPRODUCED INTERNAL CHECKS','reports/original_reproduction.json','Original copied source reproduced 19/19 on recorded current runtime, historical pass/fail agrees; still not independently validating robot dynamics'),
        ('R09','Maximum sampled eigenvalue hard-coded null','CLOSED','reports/corrected_internal_tests.json',f"Actual largest sampled eigenvalue {corrected['max_sampled_joint_inertia_eigenvalue']:.15g} kg m^2 reported; no global certificate"),
        ('R10','Friction grid below declared joint speeds','CLOSED','reports/corrected_internal_tests.json','261 inclusive velocities per joint from -VMAX to +VMAX, including +/-2.61 rad/s for joints 5-7'),
        ('R11','Manuscript alpha_v/comma corrections','OPEN / OUT OF SCOPE','reports/OUT_OF_SCOPE_EDITORIAL_MEMO.md','Manuscript not supplied; no manuscript edits'),
        ('R12','Unsigned protocol and experiment freeze','OPEN','protocol/proposed_frozen_configuration.json; protocol/unresolved_decisions.csv','All unknown values and human approvals explicitly null; no A2/A3, T27 or G2.5 run'),
    ]
    with (ROOT/'reports/reviewer_issue_disposition.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','reviewer_issue','disposition','evidence','remaining_or_resolution']);w.writerows(issues)
    gates=[
        {'gate':'A1 implementation','verdict':'GO','evidence':['reports/original_reproduction.json','reports/external_dynamics.json'],'remaining':'Continue model/verification implementation without claiming approval of experiments'},
        {'gate':'A2 closed-loop smoke','verdict':'CONDITIONAL GO; CURRENTLY BLOCKED','evidence':['reports/primary_source_checks.json','review_sheets/HUMAN_REVIEW_SIGNATURES.md'],
         'remaining':'Qualified signed T04b/T06a and dynamics review; approved complete smoke settings/controls plan. No A2 executed'},
        {'gate':'A3 numerical Scenarios A/B/C','verdict':'NO-GO','evidence':['protocol/unresolved_decisions.csv'],'remaining':'Signed source/model review, passing A2 with both refinements, T27, positive G2.5, approved M1, signed+hashed full v1.1, frozen T22 and Scenario B/shared solver settings'},
        {'gate':'Level 1','verdict':'NO-GO','evidence':['protocol/Protocol_v1_1_REMEDIATION_ADDENDUM.md'],'remaining':'Verified outward-rounded global m1>0, all tube/trajectory/HOCBF bounds and all theorem conditions'},
        {'gate':'Publication-result evidence','verdict':'NO-GO','evidence':['reports/external_dynamics.json'],'remaining':'No closed-loop/comparative results; present artifacts are model-validation evidence only'},
    ]
    save('reports/stage_gates.json',gates)
    summary=['# ZIP versus reviewer: remediation result','',
        'Prepared 1 November 2026. Original ZIP, model manifest, Protocol v1.0 and historical results are preserved byte-for-byte. No GitHub push was made.', '',
        'The reviewer correctly identified the difference between internal consistency and external model validation. The technical defects below were corrected without changing the evaluator\'s executable AST, physical model, original test tolerances or experiment thresholds. Human acceptance and protocol decisions remain pending.', '',
        '## Executed evidence','',
        f"- Original suite: **{original['passed']}/{original['check_count']} PASS**, reproduced from unmodified copied code; historical outcomes agree. Internal tests only.",
        '- Corrected suite: **19/19 PASS** with accurate descriptions, a calculated maximum eigenvalue and a full-limit friction grid.',
        '- Primary source bytes: pinned Gaz and franka_ros Git commit/tree/blob identities checked; SHA256 recorded. The supplement hash matches v1.0.',
        '- Source comparisons: **70 inertial + 21 friction values and 8 joint/frame rows PASS**. c1z remains author-code zero versus table asterisk; no mixed ROS inertials.',
        '- External reference: **22 original q/qd/qdd cases, 594 quantity/pose comparisons PASS**, using Pinocchio 3.8.0 and independently parsed Gaz/Xacro data. These are 27 quantity groups per pose, not 594 independent robots or experiments.',
        '- All five isolated mass/COM/inertia-sign/frame/gravity error injections were detected by the external comparison.',
        f"- Sampled joint-space eigenvalues span {corrected['min_sampled_joint_inertia_eigenvalue']:.15g} to {corrected['max_sampled_joint_inertia_eigenvalue']:.15g} kg m^2 across the test poses. These are not global certified bounds.",'',
        '| External quantity | Maximum absolute difference | Units |', '| --- | ---: | --- |']
    for key,unit in [('AD_flange_translation','m'),('M','kg m^2'),('g','N m'),('Cqd','N m'),('ID_friction_on','N m')]:
        summary.append(f"| {key} | {external['summary'][key]['max_absolute_error']:.6g} | {unit} |")
    summary += ['', 'Full per-component reference/target values, failures (none) and elementwise abs+relative tolerance ratios are in external_dynamics.json/CSV. Rotation maximum error is '+f"{max(v['max_absolute_error'] for k,v in external['summary'].items() if k.endswith('_rotation')):.6g}.", '',
        '## Reviewer disposition','', '| ID | Issue | Status |', '| --- | --- | --- |']
    summary += [f'| {r[0]} | {r[1]} | {r[2]} |' for r in issues]
    summary += ['', 'See reviewer_issue_disposition.csv for evidence paths and the exact remaining work. Historical misleading notes remain only in clearly identified immutable baseline/run-copy records. Corrected executable tests are in src/.', '',
        '## Protocol work','',
        'A separate R1 addendum proposes M1 with frozen common constants, candidate-aware margin evaluation inside the NLP, matching constant-envelope treatment, a method-independent Scenario B suite, and integrator plus control-period refinement. The 64 proposed targets were generated without running a planner or baseline. No proposal is marked approved.', '',
        'The workbook, full mathematical framework, decision brief and optional manuscript are missing. The addendum defines the dependency/entry policy; exact equation-level NLP/envelope mapping and constants cannot be completed from the supplied package alone. Nulls and owners are listed in the proposed configuration and unresolved-decision register.', '',
        '## Gates and smallest next step','', '| Gate | Current decision |', '| --- | --- |']
    summary += [f"| {g['gate']} | {g['verdict']} |" for g in gates]
    summary += ['',
        '**Smallest next step:** a qualified human reviews the source/frame and external dynamics evidence and signs or rejects the acceptance sheets. In parallel, supply the missing framework/registry and resolve the listed smoke-test settings. A2 can be proposed after those prerequisites; no closed-loop or comparative run is approved by this package.', '',
        'No A2/shakedown, A3 comparison, T27, G2.5 or interval-certification run was performed. The unrelated earlier PyBullet grasp demo is excluded from research evidence. Do not call this completed Phase-3a acceptance, approved Protocol v1.1, a Level-1 certificate or paper-ready simulation evidence.', '']
    (ROOT/'reports/REVIEWER_RESPONSE.md').write_text('\n'.join(summary))
    (ROOT/'model_check_summary.txt').write_text('\n'.join(summary))
    (ROOT/'requirements.lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in sorted(load('reports/verification_run.json')['packages'].items()) if k.lower() not in ['pip','setuptools'])+'\n')
    print('Reviewer response, proposal manifest, decision register and gates generated.')


if __name__=='__main__':main()
