"""Build unsigned r2 disposition from the immutable failed development hold."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import copy,csv,difflib,json,shutil
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.a2_plan import check_plan

REPORT=ROOT/'reports/p1_v1.2.2_r2'
POLICY=ROOT/'policy/v1.2.2-r2-draft'


def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def at(path,needle):
    return f'`{path}:{next(i for i,s in enumerate((ROOT/path).read_text().splitlines(),1) if needle in s)}`'


def main():
    REPORT.mkdir(parents=True,exist_ok=True)
    pointer=json.loads((ROOT/'reports/p1_prehold_latest.json').read_text());run=ROOT/pointer['run_directory']
    if digest(run/'summary.json')!=pointer['summary_sha256']:raise ValueError('Retained hold evidence changed')
    summary=json.loads((run/'summary.json').read_text())
    plan=json.loads((POLICY/'PREDECLARED_DEVELOPMENT_PREHOLD.json').read_text())
    if digest(POLICY/'PREDECLARED_DEVELOPMENT_PREHOLD.json')!=summary['frozen_plan_sha256']:raise ValueError('Frozen plan changed')
    evidence=REPORT/'evidence/prehold';evidence.mkdir(parents=True,exist_ok=True)
    for p in run.iterdir():
        if p.is_file():shutil.copy2(p,evidence/p.name)
    tests=ROOT/'runs/p1_r2_development_checks/signed_clock_and_hold_tests_r2.json'
    if not tests.exists():raise ValueError('Completed r2 signed-clock contract tests required')
    test_data=json.loads(tests.read_text())
    if not test_data['overall_pass']:raise ValueError('Contract tests failed')
    shutil.copy2(tests,REPORT/'evidence/signed_clock_and_hold_tests.json')
    shutil.copy2(tests.with_suffix('.log'),REPORT/'evidence/signed_clock_and_hold_tests.log')
    review=ROOT/'inputs/p1_review_2026_11_02/IC2AI_2027_P1_Independent_Review_Decision_2026-11-02.txt'
    (REPORT/'reviewer_sources').mkdir(exist_ok=True);shutil.copy2(review,REPORT/'reviewer_sources'/review.name)
    r1=ROOT/'policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json'
    draft=copy.deepcopy(json.loads(r1.read_text()));approved=Policy.load()
    draft['development_revision']='v1.2.2-r2'
    draft['status']='DRAFT / OWNER APPROVAL PENDING'
    draft['P1_preparation_proposal'].update(status='FAIL_PREDECLARED_DEVELOPMENT_HOLD',
        development_model_prehold_executed=True,physical_hardware_prehold_executed=False,
        signed_clock_execution_support='IMPLEMENTED_IN_DEVELOPMENT_ADAPTER; NOT_POLICY_APPROVAL',
        result='All four frozen C4 preparation cells violate qd tolerance for joints 3,7 by elapsed 0.00125 s; stopped. No completed zero endpoint.',
        evidence='reports/p1_v1.2.2_r2/evidence/prehold/summary.json')
    draft['observer_proposal']['signed_preparation_clock_execution_support']='IMPLEMENTED_AND_CONTRACT_TESTED_IN_DEVELOPMENT; APPROVAL_PENDING'
    draft['A2_execution_reference']['actual_zero_endpoint_available']=False
    draft['A2_execution_reference']['motion_reference_coefficients']=None
    draft['P1_failure_disposition']={'status':'FROZEN_CANDIDATE_REJECTED_BY_DEVELOPMENT_COUNTEREXAMPLE',
        'human_replacement_decision':None,'new_controller_or_thresholds_selected':False,
        'actual_abort_QP':'FULL_43_ROWS_EVALUATED; PRIMAL_INFEASIBLE IN ALL FOUR CELLS',
        'completed_zero_endpoint':False,'no_retuning':True,'no_motion_after_hold':True,
        'continuous_true_ODE_neighborhood_certified':False,
        'interpretation':'A finite violating sampled state rejects the declared tolerance. Dense numerical interpolation and refinement are not a certified continuous-time invariant-region proof.'}
    draft['gates']['P1']='FAIL, frozen development torque hold rejected; verified startup NOT APPROVED'
    draft['gates']['A2']='NO-GO, startup fails and independent human/build/policy gates remain'
    draft['approvals']={k:None for k in draft['approvals']}
    draft['unresolved_conflicts']='P1 frozen holding tolerance failed. Replacement startup decision, independent human review and manuscript build confirmation remain pending; planner M1/floor issue remains separate.'
    out=POLICY/'PROPOSED_POLICY_CONFIGURATION_v1.2.2_r2.json';write(out,draft)
    for name,baseline in [('DRAFT_R1_TO_R2.diff',r1),('APPROVED_v121_TO_DRAFT_R2.diff',approved.path)]:
        (POLICY/name).write_text(''.join(difflib.unified_diff(baseline.read_text().splitlines(True),out.read_text().splitlines(True),fromfile=str(baseline.relative_to(ROOT)),tofile=str(out.relative_to(ROOT)))))
    static_pointer=json.loads((ROOT/'reports/p1_latest.json').read_text())
    static=json.loads((ROOT/static_pointer['run_directory']/'screen.json').read_text())
    checklist=check_plan(draft,approved,static,{'summary':summary,'clock_tests':test_data})
    write(REPORT/'A2_ENTRY_CHECKLIST.json',checklist)
    md='# A2 entry checklist — r2, DRAFT / OWNER APPROVAL PENDING\n\nA1 GO; frozen P1 FAIL; verified startup NOT APPROVED; official A2/A3/Level 1/publication NO-GO.\n\n'
    md+='| Item | Status | Meaning |\n| --- | --- | --- |\n'
    for row in checklist['items']:md+=f"| {row['item']} | {row['status']} | {row['reason']} |\n"
    md+='\nEvidence: [actual torque hold](evidence/prehold/summary.json), [contract tests](evidence/signed_clock_and_hold_tests.json), [policy](../../policy/v1.2.2-r2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2_r2.json). A passing technical check never supplies a human signature.\n'
    (REPORT/'A2_ENTRY_CHECKLIST.md').write_text(md)
    records=[];table=[]
    for row in summary['cells']:
        c=json.loads((run/row['record_file']).read_text());e=c['endpoint_diagnostics'];p=e['physical_slacks']
        v=e['state']['qd'];dt=row['grid']['control_period_s']*1000;h=row['grid']['rk4_step_s']*1000
        table.append(f"| {row['cell']} | {dt:g} | {h:g} | {abs(v[2]):.12f} | {abs(v[6]):.12f} | {e['state']['physical_t_s']:.8f} | FAIL / PRIMAL_INFEASIBLE |")
        for kind,values in p.items():
            if kind=='passed':continue
            for j,value in enumerate(values):
                unit=('m^6' if j==14 else 'rad') if kind=='position_and_manip_h' else ('m^6/s' if j==14 else 'rad/s') if kind=='psi1' else 'N m' if kind.startswith('torque') else 'rad/s'
                records.append([row['cell'],e['state']['physical_t_s'],kind,j+1,value,unit,'actual simulated abort state; not physical time zero'])
    with (REPORT/'ACTUAL_ABORT_STATE_PHYSICAL_SLACKS.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['cell','physical_time_s','family','component_1_based','slack','unit','scope']);w.writerows(records)
    text='''# Independent P1 review remediation — r2

**The frozen P1 candidate FAILS its declared development hold tolerance.**
A1 component development remains GO. P1 as verified startup is NOT APPROVED;
official A2, A3, Level 1 and publication remain NO-GO.

The review's accepted analytical screen is preserved. Its 0.156 s settling
duration and 129 midpoint QP results do not imply a viable torque hold.
The current user request authorizes engineering remediation; no owner/theory/
controls startup selection, policy signature or official A2 authority is inferred.

## Applied-torque development result

Before the first Panda prehold integration, the new test plan froze the old
duration, gains, waveform, tolerances and all four C4 cells. The controller is
the existing Slotine–Li static-midpoint law, torque-box projected only during
preparation. The plant and DOB receive the same actual held torque. The plant
uses the original negative physical disturbance time. There is no ideal clamp,
reaction torque, injected-truth controller input, observer reset or retry.

All four cells stop at physical time -0.15475 s: elapsed 0.00125 s after starting
at -0.156 s. Actual endpoint speeds already exceed the 0.02 rad/s limit:

| Cell | Delta ms | h ms | abs(qd3) rad/s | abs(qd7) rad/s | Abort physical time s | Hold / actual-state QP |
| --- | --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(table)+'''

These are measured simulated abort states, not q(0) or an ideal midpoint fixture.
Their correctly propagated envelope has only 1.25 ms elapsed, not 0.156 s.
The full 43-row QP is PRIMAL_INFEASIBLE in each case. No candidate QP torque is
applied and no post-hold motion/reference execution occurs. There is no valid
zero-time endpoint and no successful P1 procedure to approve under these settings.
Do not extend the duration, enlarge tolerance or increase gains retrospectively.

Every attempted RK4 substep also checks all extrema of its cubic continuous
extension, retained RK4 stages and endpoints. This covers the numerical cubic's
components; it is not a verified error enclosure for the true ODE. The actual
violating endpoints are sufficient to reject the development candidate without
claiming a continuous-state invariance proof or a verified neighborhood.

## Findings and disposition

| Review item | Disposition | Evidence / remaining work |
| --- | --- | --- |
| Blocker 1: missing applied-torque hold | TESTED — FROZEN CANDIDATE REJECTED | All four model cells fail the unchanged speed tolerance after 1.25 ms; [summary](evidence/prehold/summary.json). A different startup needs a new human decision. |
| Blocker 2: signed execution clock | RESOLVED FOR DEVELOPMENT | Signed adapter, unchanged applied torque, no phase/observer reset, transfer guards and continuity tests implemented; [tests](evidence/signed_clock_and_hold_tests.json). Policy approval is separate. |
| Blocker 3: continuous neighborhood / measured endpoint | PARTIAL, NOT CERTIFIED | Continuous cubic extrema and actual sampled abort states checked. The candidate has a counterexample; no completed zero endpoint or true-ODE neighborhood proof is claimed. |
| Blocker 4: QP only at midpoint | PARTIAL | Complete 43-row QPs evaluated at actual nonzero-speed abort states with actual elapsed bounds; all infeasible. Successful post-hold/A2 execution cannot follow this failed hold. |
| Blocker 5: draft/human/build/reproduction gates | BLOCKED ON HUMAN DECISIONS | New r2 draft and checklist supplied; all human fields remain null. Fresh-environment engineering reproduction is recorded separately and is not independent reviewer signoff. |
| Blocker 6: planner M1 / observer floor | BLOCKED, KEPT SEPARATE | M1 remains absent and factor-two lower speed witness still fails joints 1,3 at the floor. No bound or planner success is fabricated. |
| F1 | PARTIAL | Frozen physical-model test is now performed and fails; leads/owner must select and predeclare a revised startup or alternative. |
| F2 | PARTIAL | Actual-state QP diagnostics added, definitions/C4 retained; failed hold provides no valid endpoint for finalizing execution. |
| F3 | BLOCKED ON INDEPENDENT REVIEW | Supply clean engineering checks and build hashes; genuine controls/theory signatures, build confirmation and written A2 authority must come from responsible humans. |

Implementation: SIGNED_IMPLEMENTATION, HOLD_IMPLEMENTATION, ENDPOINT_IMPLEMENTATION.
The previous analytical proposal and accepted source/evidence bytes remain unchanged.
'''
    text=text.replace('SIGNED_IMPLEMENTATION',at('src/panda_closed_loop/preparation.py','class SignedClock'))
    text=text.replace('HOLD_IMPLEMENTATION',at('src/panda_closed_loop/preparation.py','class AppliedTorquePrehold'))
    text=text.replace('ENDPOINT_IMPLEMENTATION',at('src/panda_closed_loop/preparation.py','def endpoint_diagnostics'))
    (REPORT/'REVIEW_REMEDIATION.md').write_text(text)
    audit=approved.source_audit()
    build='# Manuscript build revision — responsible confirmation pending\n\nEquation files are unchanged and match approved hashes. The build/archive discrepancy is retained:\n\n| File | Approved SHA-256 | Actual SHA-256 | Match |\n| --- | --- | --- | --- |\n'
    for r in audit['manuscript']:build+=f"| {r['file']} | `{r['expected_sha256']}` | `{r['actual_sha256']}` | {r['matches']} |\n"
    build+='\nOnly one main.tex and byte-identical copies of the supplied Project.rar were found in the available project/input source paths. No matching alternate approved build was supplied. The build owner must confirm the intended source revision and archive; no manuscript replacement or acceptance is inferred.\n'
    (REPORT/'BUILD_REVISION_REVIEW_PACKET.md').write_text(build)
    write(REPORT/'SOURCE_AUDIT.json',audit)
    hashes={str(p.relative_to(ROOT)):digest(p) for folder in [REPORT,POLICY] for p in folder.rglob('*') if p.is_file() and p.name!='SHA256_MANIFEST.json'}
    write(POLICY/'SHA256_MANIFEST.json',dict(sorted(hashes.items())))
    print(json.dumps({'P1':'FAIL_PREDECLARED_HOLD','A2':'NO-GO','policy_sha256':digest(out),'report':str(REPORT.relative_to(ROOT))},indent=2))


if __name__=='__main__':main()
