"""Build unsigned review artifacts from retained static evidence. No simulation."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import copy
import csv
import difflib
import hashlib
import io
import json
import subprocess
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.a2_plan import check_plan
from panda_closed_loop.readiness import m1_registry

BASE_COMMIT='cea93d667350d56df7f7de2426f3679ee6eacce0'
DRAFT=ROOT/'policy/v1.2.2-draft'
REPORT=ROOT/'reports/p1_v1.2.2'


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def line(path,needle):
    for i,s in enumerate((ROOT/path).read_text().splitlines(),1):
        if needle in s:return f'`{path}:{i}`'
    raise ValueError((path,needle))


def proposed_policy(base,intent,screen):
    p=copy.deepcopy(base)
    p.update(schema_version='IC2AI-2027-policy-v1.2.2-DRAFT',prepared_date='2026-11-01',
        status='DRAFT / OWNER APPROVAL PENDING',development_version='1.2.2-draft',
        team_approval=None,configuration_freeze_approval=None,approval_scope=None,
        unresolved_conflicts='P1 physical hold unverified; signed clock adapter absent; new execution choices and manuscript build await human review',
        approval_scope_note='v1.2.1 decisions are inherited only for unchanged fields. This file has no approval or execution authority.')
    p['baseline_approval_record']={'path':'policy/v1.2.1/APPROVED_POLICY_CONFIGURATION_v1.2.1.json',
        'sha256':screen['source_policy_sha256'],'commit':BASE_COMMIT,
        'release_sha256':intent['baseline_release_sha256'],'status':'IMMUTABLE OWNER-APPROVED DESIGN BASELINE, NOT AN A2 RUN AUTHORIZATION'}
    p['approvals']=copy.deepcopy(intent['approvals'])
    p['approvals'].update(project_owner=None,independent_dynamics_reviewer_signature=None,T29_standalone_signature=None)
    p['A2_execution_reference']=copy.deepcopy(intent['reference_proposal'])
    p['observer_proposal']=copy.deepcopy(intent['observer_proposal'])
    p['observer_proposal']['sampled_sensitivity_definition']={
        'update':'Forward Euler z[k+1]=z[k]+Delta*zdot(q[k],qd[k],z[k],tau_applied[k]); dhat at control instants is z[k]+Ko*M(q[k])*qd[k]',
        'cadence':'One z update per control period for each of the same four C4 cells; no retuning',
        'plant_state_rule':'During each held-torque plant RK4 step use the sampled observer convention; do not silently couple a continuous z into this sensitivity',
        'acceptance':'Report full metrics and any violation of the unchanged analytic envelope. A violation FAILS the sampled convention and requires separate theory/discrete-error review. Never enlarge varpi from these results.',
        'implementation_status':'NOT_IMPLEMENTED_OR_EXECUTED; proposal only','approval':None}
    p['integration']['observer_update_semantics']='PROPOSED_COUPLED_CONTINUOUS_Q_QD_Z_RK4; OWNER/CONTROLS APPROVAL PENDING'
    p['integration']['C4_precedence_note']='The approved full 2x2 grid supersedes workbook T25 h=Delta/4 for the Delta=.5 ms,h=.25 ms (m=2) cell.'
    p['failure_semantics']=copy.deepcopy(intent['failure_semantics'])
    p['P1_preparation_proposal']=copy.deepcopy(intent['preparation'])
    p['P1_preparation_proposal'].update(T_pre_s=screen['duration_analysis']['proposed_T_pre_s'],
        analytical_duration_evidence='reports/p1_v1.2.2/evidence/static_screen/screen.json#duration_analysis',
        screen=intent['screen'],status='BLOCKED_PHYSICAL_PREHOLD_NOT_VERIFIED',
        signed_clock_execution_support='NOT_IMPLEMENTED',
        holding_dynamics='M(q)*qdd+C(q,qd)*qd+g(q)+F(qd)=tau_hold+d(t); zdot=-Ko*z-Ko*(Ko*M(q)*qd+tau_hold+C(q,qd).T*qd-g(q)-F(qd))',
        hold_integrator_proposed='Same held applied torque and coupled continuous q,qd,z RK4 as A2 primary; C4 grid; never reset at physical time zero',
        torque_rule='Componentwise torque-box projection is part of the proposed prehold controller only; online hard-QP torque must never be clipped after solving',
        validity_requirements=['Physical hold meets the declared position and velocity tolerance throughout [-T_pre,0]',
            'DOB uses exactly the torque actually applied after prehold saturation',
            'One physical disturbance clock including negative t, fixed t_ref=0; no phase restart',
            'Do not reset z, dhat or varpi at physical time zero',
            'Measure q(0),qd(0),z(0); verify h>=0,psi1>=0,speed limits and complete 43-row QP at that endpoint',
            'Verify sampled-data/numerical observer error; analytic continuous envelope alone does not certify an RK4 or sampled observer',
            'No coverage of the continuous q neighborhood is established by the 129 static nodes'])
    p['A2_acceptance_proposal']={
        'physical_state':{'criterion':'q_min<=q<=q_max; abs(qd)<=vmax; W>=w_min^2; h>=0; initial psi1>=0; report raw physical slacks',
            'evaluation':'control instants and retained plant RK4 stages; sampled evidence only, no between-sample certification'},
        'raw_CBF_rows':{'criterion':'All original 43 raw slacks >=0 at every QP application; any negative raw slack is FAIL even near numerical resolution',
            'scope':'QP satisfaction at updates is not a continuous-time invariance proof'},
        'applied_torque':{'criterion':'abs(tau_applied)<=tau_max at all retained stages; no post-QP clipping or fabricated fallback',
            'on_failure':'Record A2 FAIL and stop development state advance before actuation'},
        'observer_envelope':{'criterion':'abs(dhat_i-d_i)<=varpi_i(physical_t+T_pre); maximum signed excess <=0 N m for every joint',
            'truth_access':'post-control diagnostic only; never used for command, observer, time selection or precondition',
            'numerical_error_allowance_Nm':0.,'scope':'Strict proposed numerical diagnostic; no sampled-observer certificate; continuous ideal envelope may fail under discretization'},
        'QP':{'normalized_primal_max':base['fixed_acceptance_thresholds']['QP_normalized_primal'],
            'scaled_stationarity_max':base['fixed_acceptance_thresholds']['QP_scaled_stationarity'],
            'additional':'Log status, iterations, complementarity, duality gap, correction and runtime; all complete rows and torque box must pass; full T27 remains open'},
        'refinement':{'grid':'integration.validation_grid, exactly the four approved C4 cells',
            'metrics':['modeled non-regenerative electrical energy J','run duration s','max torque correction N m','minimum normalized raw slack'],
            'comparison_rule':'For each factor compare adjacent cells at fixed other factor. Each metric difference must be <= max(approved absolute tolerance, approved relative_refinement*max(abs(values))). Also disclose cross-diagonal differences.',
            'thresholds':copy.deepcopy(base['fixed_acceptance_thresholds']),
            'additional':'Report terminal errors and envelope excess for every cell. Reuse physical clock, T_pre and declared reference rule; no gain or threshold retuning. Fixed task duration is not a free-time planning result.',
            'failure':'Any missing/failed cell or criterion keeps A2 FAIL/NO-GO. No automatic refinement or modified policy authorized by this draft.'},
        'terminal_task':{'target':'FK_flange(q_start+predeclared_offset), free orientation',
            'planned_position_error_m_max':base['fixed_acceptance_thresholds']['planned_terminal_error_m'],
            'actual_position_error_m_max':base['fixed_acceptance_thresholds']['actual_terminal_error_m'],
            'duration_s':intent['reference_proposal']['duration_s'],
            'prehold_endpoint_rule':'Do not substitute midpoint for measured endpoint; record each C4 endpoint and reference coefficients, disclose any target differences before comparison'},
        'evidence_level':'DEVELOPMENT, then separately authorized LEVEL_2_SAMPLED only; no LEVEL_1, no paper experiment',
        'approval':None}
    p['A2_M1_scope']={'reference_kind':'nonoptimized_measured_state','planner_M1_required_for_this_proposal':False,
        'online_requirements':'Validated runtime model and geometry, legitimate propagated observer bound, valid measured state, full hard QP, frozen approved execution definition',
        'stage1_reference':'All actually used planner M1 domain/tube constants and equations required if reference changes to Stage-1',
        'A3':'Full M1 registry remains OPEN; no invented zeros or point upper bounds'}
    p['source_build_review']={'canonical_equations_match':True,'manuscript_rows':screen['source_audit']['manuscript'],
        'main_tex_and_archive_confirmation':None,'source_files_edited':False}
    p['gates'].update(A1='GO, component development only',P1='BLOCKED, static point evidence only',A2='NO-GO, no execution authorization',
        A3='NO-GO, A2/T27/G2.5/M1/frozen tasks outstanding',Level_1='NO-GO',publication='NO-GO')
    p['A2_execution_authorized']=False
    return p


def csv_reports(screen):
    fields=['scope','physical_t_s','q_index','joint_1_based','family','lhs','rhs','slack','unit','source','interpretation']
    records=[]
    def add_pair(pairs,scope,t,qindex):
        for family in ['velocity','position']:
            f=pairs[family]
            for j in range(7):records.append([scope,t,qindex,j+1,family,f['lhs'][j],f['rhs'][j],f['slack'][j],f['unit'],
                'approved_v1.2.1 + runtime abs(M^-1) + analytic varpi','necessary online condition only'])
    add_pair(screen['baseline_online_pairs'],'baseline_initial',0,0)
    for sample in screen.get('P1_candidate',{}).get('time_samples',[]):
        for row in sample['q_samples']:add_pair(row,'P1_static_node',sample['physical_t_s'],row['q_index'])
    with (REPORT/'online_pairs_per_joint.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(records)
    rows=[]
    for when,key in [('initial','planner_initial_pointwise_lower_witness'),('observer_floor','planner_floor_pointwise_lower_witness')]:
        for variant in ['reviewer_factor_two','matched_reference_start_factor_three']:
            p=screen[key][variant]
            for family in ['velocity','position']:
                for j in range(7):rows.append([when,variant,p['factor'],j+1,family,p[family+'_lhs'][j],p[family+'_rhs'][j],p[family+'_slack'][j],'rad/s^2',
                    'point abs(N) is a conditional LOWER witness, never M1 upper bound','planner computation BLOCKED: missing M1'])
    with (REPORT/'planner_point_lower_witnesses.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['envelope','variant','factor','joint_1_based','family','lhs','rhs','slack','unit','interpretation','planner_status']);w.writerows(rows)


def checklist_md(result):
    text='# A2 entry checklist — DRAFT / OWNER APPROVAL PENDING\n\n'
    text+='A1 GO; P1 BLOCKED; official A2 NO-GO; A3, Level 1 and publication NO-GO.\n\n'
    text+='PASS applies only to the named field or retained static fixture. It is not an execution authorization. '
    text+='Evidence: [static screen](evidence/static_screen/screen.json), [draft policy](../../policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json), '
    text+='[engineering verification](evidence/verification/verification.json), [P1 memo](P1_FEASIBILITY_MEMORANDUM.md).\n\n'
    text+='| Item | Status | Evidence / remaining work |\n| --- | --- | --- |\n'
    for item in result['items']:text+=f"| {item['item']} | {item['status']} | {item['reason']} |\n"
    text+='\nThe existing approved v1.2.1 startup remains infeasible (FAIL). The proposed preparation has not been physically validated (NOT TESTED). '
    text+='All human fields in this revision remain null (AWAITING HUMAN REVIEW). The checker has no actuator or A2 launch path.\n'
    return text


def memorandum(screen,run):
    d=screen['duration_analysis'];candidate=screen['P1_candidate'];qp=candidate['complete_QP_fixture'];times=candidate['time_samples']
    f=d['floor_fraction_upper'];threshold=d['threshold_fraction']
    worst={k:min(r[k]['slack'][j] for t in times for r in t['q_samples'] for j in range(7)) for k in ['velocity','position']}
    entries=screen['initial_entry_samples']
    diag=[c['diagnostics'] for c in qp['cases']]
    text=f'''# P1 feasibility memorandum — DRAFT / OWNER APPROVAL PENDING

**P1 overall: BLOCKED. Official A2: NO-GO.** Static sampled online checks pass;
the actual applied-torque prehold, end state, signed execution clock and numerical
observer envelope are not verified. No physical or plant prehold was executed.

## Frozen inputs and ordering

The candidate design was written at `{screen['predeclaration']['declared_utc_before_new_screens']}`
before the screen run `{run}`. Its SHA-256 is
`{screen['predeclaration_sha256']}`. The prescribed state set is the physical
joint midpoint plus all 128 sign corners at ±0.01 rad per joint; velocity radius
0.02 rad/s per joint. Report times are 0, 0.125 and 0.25 s. No favorable state
selection, gain sweep, plant trial, disturbance query or duration retry was used.
The accepted r2 ZIP and v1.2.1 policy are immutable references in the draft manifest.

## Exact necessary online conditions

Let `N=M(q)^-1`, `B=abs(N)*varpi`. For a linear joint barrier, its Hessian is zero.
Adding each upper and lower row cancels torque, bias, q and the linear velocity
terms. Thus the exact paired sums are:

`velocity: 2*alpha_v*vmax - 2*B >= 0`;
`position: alpha1*alpha2*(qmax-qmin) - 2*B >= 0`.

Both reduce to `B <= RHS`, in rad/s². They are necessary only. At the original
startup they fail for velocity joints 1,3,4,5,6,7 and position joints 1,3. Worst
violations are {screen['baseline_online_pairs']['velocity']['worst_violation']:.9f} and
{screen['baseline_online_pairs']['position']['worst_violation']:.9f} rad/s².
The complete baseline QP correctly reports `{screen['baseline_complete_QP_status']}`.
No solver tuning can repair that algebraic contradiction.

## Analytic duration, selected once

At physical time `-T_pre`, initialize `dhat=0`, `z=-Ko*M(q)*qd`, `varpi=dbar`.
For common `Ko=20/s` and `dbar1=1.4*dbar/s`, observer elapsed time is
`s=physical_t+T_pre` and

`varpi(s)=dbar*[f+(1-f)*exp(-20*s)]`, `f={f}`.

At each predeclared node/joint let `R=min(alpha_v*vmax,alpha1*alpha2*range/2)`.
The smallest ratio `R/B_initial` is `{threshold:.12g}` at node
{d['limiting_sample']}, joint {d['limiting_joint_1_based']}. It exceeds the floor
fraction. The analytic critical time is `{d['critical_s']:.12g}` s. The previously
declared rounding rule `ceil(Tcritical/Delta)*Delta+Delta`, with Delta=0.001 s,
gives **T_pre={d['proposed_T_pre_s']} s**. This duration was not increased after
the complete-QP check. If the ratio were <=f, no finite duration would be returned.

At physical time zero the ideal continuous envelope is
`{candidate['continuous_ideal_varpi_at_zero_Nm']}` N m. It is not reset at zero.
It decreases componentwise, so at each *fixed* q node the t=0 pair check covers
the future declared [0,0.25] s window. This is not an enclosure of all q in the
continuous neighborhood or of the future moving robot.

## Numerical evidence and limits

All 129 nodes pass both pairs at all three report times. Minimum online pair
slacks are {worst['velocity']:.9g} (velocity) and {worst['position']:.9g} (position)
rad/s². All declared-node entry h and worst-case psi1 over the velocity box
are nonnegative; minimum h={min(e['h_min'] for e in entries):.9g} (mixed physical
barrier units, not a normalized distance) and minimum psi1={min(e['psi1_min_over_velocity_box'] for e in entries):.9g}
(mixed derivative units). See each row's scale/units in the original barrier
implementation rather than comparing mixed raw magnitudes.

The complete **43-row** QP is numerically feasible for {qp['count']} fixed fixtures
at q=midpoint, qd=0: estimate zero and all 128 corners of
`abs(dhat)<=dbar+varpi(0)`. This estimate box follows from the triangle inequality;
it uses no disturbance truth. The full checks include position, velocity,
manipulability and torque rows. At a fixed state these constraints are affine
in (tau,dhat); feasible vertex witnesses support numerical feasibility of the
estimate box. They do not establish feasibility over a continuous q/qd tube,
the unmeasured physical hold endpoint or the subsequent trajectory. Full T27
is not completed by these fixtures.

Per-joint LHS/RHS/slack/units and source are in [online_pairs_per_joint.csv](online_pairs_per_joint.csv).
Full solver diagnostics and per-node states are in [screen.json](evidence/static_screen/screen.json).
No plant acceleration function or disturbance waveform is called by this tool;
the unit test patches both to fail on access.

## Proposed physical prehold: not executed and not yet justified

Use the existing Slotine–Li controller with fixed q_ref=midpoint, qd_ref=qdd_ref=0
and existing gains. Project that *preparation controller's* command componentwise
onto ±tau_max. Apply exactly that saturated torque to
`M*qdd+C*qd+g+F=tau_hold+d(physical_t)`. The DOB must use that same applied
torque. Integrate q,qd,z continuously with held torque; do not reset z/dhat or
the disturbance clock at zero. The prephase is outside the A2 safety claim and
does not use the initially infeasible hard QP. No kinematic clamp, reaction
torque, artificial q reset or fabricated disturbance estimate is allowed.

Required tolerance throughout the hold: abs(q-midpoint)<=0.01 rad and
abs(qd)<=0.02 rad/s per joint; applied torque remains in the physical box.
These tolerances have **not** been verified. Finite torque saturation alone
does not establish hold stability, trajectory safety or observer-envelope
validity with discrete measurements/numerics. No holding dynamics were simulated.

At zero measure actual q,qd,z and keep propagated varpi. Reject an out-of-window
endpoint. Recompute h,psi1,manipulability,speed and complete 43-row QP there;
do not claim q(0)=midpoint or qd(0)=0. Initialize the proposed reference at that
measured state. The current execution-state/epoch contracts reject negative
times: a reviewed signed-clock adapter is **not implemented**. The mathematical
elapsed-time map in the screen is not such an adapter or an authorization.

## Planner remains separate and blocked

The actual planner pair tool needs M1 Nbar and Abar domain bounds, which remain
null. It reports **BLOCKED_MISSING_M1_BOUNDS**. No point abs(N) is substituted
as a certified or sampled upper bound. An explicitly separate conditional
*lower witness* uses the requirement that any valid domain bound including the
midpoint must dominate its absolute entries. The reviewer factor-two lower
condition fails in all velocity joints at startup, and in joints 1 and 3 even
at the observer floor: LHS 13.065683 and 13.347212 versus RHS 10.875 rad/s².
Therefore waiting longer alone cannot restore that tightened planner at this
point under these unchanged gains/disturbance. This is conditional on a domain
including the point, not a computed M1 registry or a global impossibility theorem.

The source also retains the nonnegative Nbar*rho_r / Abar*rho_r term. At matched
reference initialization chi=0 but rho_r(0)=varpi(0), giving a factor-three
lower witness; it is reported separately, not silently dropped. The implemented
M1-input arithmetic is a necessary lower-margin screen and explicitly omits
nonnegative beta/tube terms. A pass would never establish full planner feasibility.

## Failure modes and disposition

P1 is blocked by physical hold validity, continuous state coverage or actual
endpoint checks, signed-clock execution support, numerical observer validity,
and human policy/review decisions. If any predeclared condition fails, retain
the failure; do not extend T_pre, select another q0 or relax a threshold.
P2 would require reviewing both alpha_v and alpha1*alpha2 plus the newly nonzero
abs(alpha_v-lambda)*chi_v and planner margins. P3 needs scientific justification
for a different disturbance; P4 needs new manuscript/theory review. All are
UNAPPROVED alternatives; none is implemented or automatically selected.

A1 component development GO. P1 BLOCKED. Official A2, A3, Level 1 and publication
NO-GO. The next authorized work is the human disposition described in
[NEXT_THREE_ACTIONS.md](NEXT_THREE_ACTIONS.md), not an A2 launch.
'''
    return text


def issue_response(screen):
    rows=[
        ('E5','RESOLVED',line('src/panda_closed_loop/feasibility.py','def pair_conditions'), 'Reproduced formal velocity-pair failure and baseline full-QP stop; source/unit checks use no plant.'),
        ('E6','RESOLVED',line('scripts/p1_feasibility.py',"'position':'upper+lower"),'Position-pair derivation and per-joint output added; baseline joints 1,3 fail.'),
        ('E7','PARTIAL',line('src/panda_closed_loop/feasibility.py','def planner_pair_screen'),'Factor-two necessary arithmetic and separate lower witnesses added. Actual domain M1 bounds absent; planner remains BLOCKED.'),
        ('E8','RESOLVED',line('src/panda_closed_loop/readiness.py','def m1_registry')+'; '+line('src/panda_closed_loop/config.py','def a2_blockers'),'A2 requirement flags depend on reference kind (null/unselected, true/Stage-1, false/nonoptimized); A3 requirements remain true. Reference approval itself is pending.'),
        ('E9','PARTIAL',line('src/panda_closed_loop/a2_plan.py',"add('observer_execution_approval'"),'Coupled-continuous RK4 plus explicit sampled sensitivity proposed; execution approval, discrete error justification and physical validation remain pending.'),
        ('E10','BLOCKED','policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json → source_build_review','02/03 hashes match; main.tex and Project.rar still differ. No source rewrite or fabricated build acceptance.'),
        ('E11','RESOLVED','policy/v1.2.2-draft/PROTOCOL_v1.2.2_DRAFT_ADDENDUM.md → C4','All four approved cells retained, including Delta=.5ms,h=.25ms,m=2; later C4 overrides T25 default.'),
        ('E12','BLOCKED','policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json → approvals','Baseline owner acceptance is historical; every new human signature/approval remains null. No independent signoff inferred.'),
        ('F1','PARTIAL','policy/v1.2.2-draft/PREDECLARED_P1_DESIGN.json; P1_FEASIBILITY_MEMORANDUM.md','P1 design declared before screen; T_pre analytically selected once; sampled pairs and point QP pass. Physical prehold not established and human startup choice unsigned.'),
        ('F2','PARTIAL',line('src/panda_closed_loop/a2_plan.py','def check_plan')+'; scripts/check_a2_plan.py','Complete proposed reference, duration, metrics, observer, failure semantics and C4 supplied. Completeness PASS is not owner approval; signed execution definition absent.'),
        ('F3','BLOCKED','NEXT_THREE_ACTIONS.md; evidence/verification/verification.json','Engineering rerun is retained, but independent clean-environment reproduction, controls/theory signatures, build confirmation and written A2 authorization cannot be supplied by Codex.'),
        ('E2 (additional)','PARTIAL',line('tests/test_action3.py','def test_43_affine_row_assembly_signs_and_torque_perturbations'),'Renamed the shared-model row check and labeled its scope; independent reviewer rerun still outstanding.')]
    text='# Reviewer issue response — v1.2.2 DRAFT\n\n'
    text+='Authoritative input: `inputs/p1_v1.2.2/Action 3 r2 Review A2 Gate Decision.docx`, sections A,D,E,F. '
    text+='The TXT handoff defines this engineering task. The reviewer did not execute tests; new results below are engineering reproductions, not new independent signatures.\n\n'
    text+='| Finding | Status | File / line or artifact | Change, evidence and remaining condition |\n| --- | --- | --- | --- |\n'
    for r in rows:text+='| '+' | '.join(r)+' |\n'
    text+='\nEvidence: [static screen](evidence/static_screen/screen.json), [per-joint online rows](online_pairs_per_joint.csv), '
    text+='[planner lower witnesses](planner_point_lower_witnesses.csv), [engineering rerun](evidence/verification/verification.json), '
    text+='[entry checklist](A2_ENTRY_CHECKLIST.md). Source line numbers refer to this overlay revision.\n\n'
    text+='Decisions: **A1 GO; P1 BLOCKED; official A2 NO-GO; A3/Level 1/publication NO-GO.** '
    text+='No gain/disturbance/model change, plant prehold, official A2, optimizer, scenario or publication run was performed.\n'
    return text


def main():
    DRAFT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    pointer=json.loads((ROOT/'reports/p1_latest.json').read_text());run=pointer['run_directory']
    path=ROOT/run/'screen.json';screen=json.loads(path.read_text())
    if digest(path)!=pointer['screen_sha256']:raise ValueError('Static evidence changed')
    intent=json.loads((DRAFT/'PREDECLARED_P1_DESIGN.json').read_text())
    if digest(DRAFT/'PREDECLARED_P1_DESIGN.json')!=screen['predeclaration_sha256']:raise ValueError('Predeclaration changed')
    policy=Policy.load();draft=proposed_policy(policy.raw,intent,screen)
    write_json(DRAFT/'PROPOSED_POLICY_CONFIGURATION_v1.2.2.json',draft)
    diff=''.join(difflib.unified_diff(policy.path.read_text().splitlines(True),
        (DRAFT/'PROPOSED_POLICY_CONFIGURATION_v1.2.2.json').read_text().splitlines(True),
        fromfile='approved-v1.2.1.json',tofile='proposed-v1.2.2-DRAFT.json'))
    (DRAFT/'APPROVED_v121_TO_DRAFT_v122.diff').write_text(diff)
    result=check_plan(draft,policy,screen)
    write_json(REPORT/'A2_ENTRY_CHECKLIST.json',result)
    (REPORT/'A2_ENTRY_CHECKLIST.md').write_text(checklist_md(result))
    write_json(REPORT/'M1_REQUIREMENTS_NONOPTIMIZED_A2.json',m1_registry(policy,'nonoptimized_measured_state'))
    csv_reports(screen)
    (REPORT/'P1_FEASIBILITY_MEMORANDUM.md').write_text(memorandum(screen,run))
    (REPORT/'REVIEWER_ISSUE_RESPONSE.md').write_text(issue_response(screen))
    write_json(REPORT/'EVIDENCE_POINTERS.json',{'static_screen_run':run,'static_screen_sha256':digest(path),
        'predeclaration_sha256':digest(DRAFT/'PREDECLARED_P1_DESIGN.json'),'policy_draft_sha256':digest(DRAFT/'PROPOSED_POLICY_CONFIGURATION_v1.2.2.json'),
        'accepted_base_commit':BASE_COMMIT,'baseline_release_sha256':intent['baseline_release_sha256'],
        'verification_pointer':'reports/p1_verification_latest.json','official_A2_executed':False})
    files=[p for folder in [DRAFT,REPORT] for p in folder.rglob('*') if p.is_file() and p.name!='SHA256_MANIFEST.json']
    write_json(DRAFT/'SHA256_MANIFEST.json',{str(p.relative_to(ROOT)):digest(p) for p in sorted(files)})
    print(json.dumps({'draft_policy_sha256':digest(DRAFT/'PROPOSED_POLICY_CONFIGURATION_v1.2.2.json'),
        'report':str(REPORT.relative_to(ROOT)),'A2':'NO-GO'},indent=2))


if __name__=='__main__':main()
