"""Read-only T27/G2.5/M1 DEVELOPMENT preparation, not A3 comparisons."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import platform
import subprocess
import numpy as np
from panda_dynamics import QMIN,QMAX,TAUMAX
from panda_closed_loop.assembly import build_components
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.observer import ObserverEnvelope
from panda_closed_loop.readiness import m1_registry
from panda_closed_loop.a3_qp_bounds import diagnostic_qp,synthetic_box_rows,active_face_fixture,screen_state


def write(path,data):
    with path.open('x') as f:json.dump(json_values(data),f,indent=2,allow_nan=False);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report=ROOT/'reports/a2_extended_v1';report.mkdir(parents=True,exist_ok=True)
    out=(args.output or report/'qp_bounds_evidence'/('run_'+stamp)).resolve()
    out.mkdir(parents=True,exist_ok=False)
    def report_write(name,text):
        path=report/name
        if path.exists():path=report/(path.stem+'_'+stamp+path.suffix)
        with path.open('x') as f:f.write(text)
        return str(path.relative_to(ROOT))
    policy=Policy.load();system=build_components(policy)
    system.geometry.function=system.geometry.function.expand()
    sources={n:digest(ROOT/n) for n in ['src/panda_closed_loop/a3_qp_bounds.py','scripts/a3_qp_bounds.py',
             'src/panda_closed_loop/qp.py','src/panda_closed_loop/barriers.py','src/panda_closed_loop/feasibility.py',
             'src/panda_dynamics.py','policy/v1.2.1/APPROVED_POLICY_CONFIGURATION_v1.2.1.json']}
    meta={'started_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
          'cwd':str(ROOT),'python':sys.version,'platform':platform.platform(),
          'commit_at_execution':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'source_hashes':sources,'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','casadi','proxsuite']},
          'scope':'READ_ONLY_DEVELOPMENT_PREPARATION_NO_A3_COMPARISON_NO_PLANT_ADVANCE',
          'human_signatures':None,'full_official_T27_authorized':False,'full_official_G2_5_authorized':False,
          'grid_rule':'Fixed synthetic matrices, retained original endpoints, qmid plus one-joint 10% range offsets; no RNG or result-guided replacement.'}
    write(out/'run_started.json',meta)
    fixtures=[]
    def fixture(name,nominal,rows,expected=None,**extra):
        result=diagnostic_qp(system.qp,nominal,rows,expected,name)
        result.update(extra);fixtures.append(result)
        return result
    inside=np.array([1.,-2.,3.,-4.,.1,.2,.3])
    fixture('box_interior',inside,synthetic_box_rows(TAUMAX),inside,oracle='Unconstrained identity optimum')
    u=np.zeros(7);u[0]=TAUMAX[0]+10;target=np.zeros(7);target[0]=TAUMAX[0]
    fixture('box_torque_active',u,synthetic_box_rows(TAUMAX),target,oracle='Exact Euclidean box projection')
    G=np.zeros((2,7));G[0,:2]=1;G[1,2:4]=[1,-1]
    target=np.array([1.,-1.,.5,.5,0,0,0]);u=target-G.T@np.array([3.,2.])
    for factors,label in [(np.ones(2),'coupled_two_active'),(np.array([2.**-20,2.**20]),'coupled_rescaled_2pow40_span')]:
        rows=synthetic_box_rows(TAUMAX,G*factors[:,None],(-G@target)*factors,factors)
        fixture(label,u,rows,target,oracle='KKT positive multipliers with known primal optimum')
    redundant=np.zeros((2,7));redundant[0,:2]=1;redundant[1,:2]=2
    fixture('redundant_active_faces',-redundant.T@np.ones(2),synthetic_box_rows(TAUMAX,redundant,np.zeros(2),np.array([1.,2.])),np.zeros(7),
            oracle='Strictly convex primal; dual need not be unique')
    bad=np.zeros((2,7));bad[0,0]=1;bad[1,0]=-1
    fixture('contradictory_halfspaces',np.zeros(7),synthetic_box_rows(TAUMAX,bad,[-2.,1.],np.ones(2)),expected_feasible=False)
    bad=np.zeros((1,7));bad[0,-1]=1
    fixture('outside_physical_torque_box',np.zeros(7),synthetic_box_rows(TAUMAX,bad,[-TAUMAX[-1]-1],np.ones(1)),expected_feasible=False)
    qmid=(QMIN+QMAX)/2
    initial=system.barriers.rows(qmid,np.zeros(7),np.zeros(7),system.bounds.magnitude)
    fixture('Panda_original_initial_43_infeasible',system.model.evaluate(qmid)['g'],initial,expected_feasible=False)
    states=[{'label':'original_initial_midpoint','q':qmid,'qd':np.zeros(7),'dhat':np.zeros(7),'varpi':system.bounds.magnitude,
             'provenance':{'type':'SOURCE_VERIFIED_APPROVED_INITIAL_POINT','physical_t_s':-.156,'elapsed_s':0.}}]
    for index in [0,2,3,6]:
        path=ROOT/f'runs/p1_r4/fresh_2fe50b9/cell_{index}.json'
        endpoint=json.loads(path.read_text())['endpoint']['QP']
        rows=system.barriers.rows(endpoint['q'],endpoint['qd'],endpoint['dhat'],endpoint['varpi'])
        fixture(f'actual_r4_endpoint_cell_{index}',np.array(endpoint['u_nom']),rows,np.array(endpoint['u_nom']),
                oracle='Request is strictly feasible in the full 43-row problem',source=str(path.relative_to(ROOT)),source_sha256=digest(path))
        states.append({**{k:endpoint[k] for k in ['q','qd','dhat','varpi']},'label':f'actual_r4_endpoint_cell_{index}',
                       'provenance':{'type':'ORIGINAL_LOCALLY_EXECUTED_BASELINE_ENDPOINT','file':str(path.relative_to(ROOT)),
                                     'sha256':digest(path),'physical_t_s':0.,'elapsed_s':.156}})
        if index==0:
            active=active_face_fixture(rows,np.array(endpoint['candidate_tau']))
            fixture('Panda_actual_43_single_active_face',active['nominal'],rows,active['expected'],oracle=active)
            quantized=AffineRows(rows.G.astype(np.float32).astype(float),rows.c.astype(np.float32).astype(float),
                rows.scales.astype(np.float32).astype(float),rows.names,rows.units)
            uq=np.array(endpoint['u_nom'],dtype=np.float32).astype(float)
            fixture('Panda_43_float32_inputs_float64_solver',uq,quantized,uq,
                    precision_note='Input quantization only, not validation of a float32 solver or controller',
                    max_G_input_quantization=float(np.max(abs(rows.G-quantized.G))))
            for grid in policy.raw['integration']['validation_grid']:
                fixture('same_43_matrix_schedule_'+str(grid['control_period_s'])+'_'+str(grid['rk4_step_s']),
                        np.array(endpoint['u_nom']),rows,np.array(endpoint['u_nom']),schedule_label=grid,
                        time_step_scope='Same static matrix per label; full two-factor plant consistency is the separate A2 test.')
    vp=ObserverEnvelope(policy.ko,system.bounds.magnitude,system.bounds.rate).value(.156)
    for j in range(7):
        for sign in [-1,1]:
            q=qmid.copy();q[j]+=sign*.1*(QMAX[j]-QMIN[j])
            states.append({'label':f'fixed_qmid_joint_{j+1}_{sign:+d}_10pct_range','q':q,'qd':np.zeros(7),'dhat':np.zeros(7),'varpi':vp,
                'provenance':{'type':'PREDECLARED_READ_ONLY_POINT_NOT_A_PLANT_ENDPOINT','elapsed_envelope_s':.156,
                              'observer_estimate_assumption':'zero estimate fixture; not claimed as a measured observer at this offset'}})
    states.append({'label':'midpoint_asymptotic_observer_floor','q':qmid,'qd':np.zeros(7),'dhat':np.zeros(7),
        'varpi':system.bounds.rate/np.array(policy.ko),
        'provenance':{'type':'ANALYTIC_ASYMPTOTIC_FLOOR_NOT_FINITE_TIME_STATE','physical_t_s':None}})
    screens=[screen_state(system,**state) for state in states]
    required=m1_registry(policy,'stage1_tightened')
    required['new_API']={'module':'panda_closed_loop.a3_qp_bounds','domain':'M1DomainSpec','bound':'M1BoundRecord',
        'bundle':'M1BoundBundle.require(name,shape,units)','missing_exception':'MissingM1Bound',
        'official_domain_created':False,'official_numeric_records_created':False,'caller_metadata_is_not_certification':True}
    strict_fail=[r['name'] for r in fixtures if r['candidate_for_analysis_only'] is not None and not r['strict_raw_pass']]
    numeric_bad=[r['name'] for r in fixtures if r.get('oracle_pass') is False or (r.get('oracle_pass') is not None and not r['normalized_KKT_pass'])]
    infeasible_ok=all(r['production_stop_requested'] and r['independent_LP']['status_code']==2 for r in fixtures if r.get('expected_feasible') is False)
    filter_pass=sum(r['filter_point_status']=='PASS_POINT_ONLY' for r in screens)
    summary={'T27':'PARTIAL_DEVELOPMENT_COVERAGE_OFFICIAL_GATE_OPEN','G2_5':'INCOMPLETE_PLANNER_M1_MISSING',
        'M1':'INCOMPLETE_NO_OFFICIAL_COMMON_DOMAIN_OR_NUMBERS','fixture_count':len(fixtures),
        'numeric_oracle_failures':numeric_bad,'strict_raw_boundary_rejections':strict_fail,
        'expected_infeasibility_cross_checks_pass':infeasible_ok,'screen_count':len(screens),
        'filter_point_pass_count':filter_pass,'filter_point_fail_count':len(screens)-filter_pass,
        'official_G2_5_positive':False,'official_T27_complete':False,'A3_comparisons_executed':False,
        'human_signatures':None,'all_original_source_hashes_unchanged':all(digest(ROOT/n)==h for n,h in sources.items())}
    write(out/'t27_fixtures.json',fixtures);write(out/'g25_screens.json',screens)
    write(out/'m1_requirements.json',required);write(out/'summary.json',summary)
    documents=write_reports(report_write,out,meta,summary)
    meta.update(finished_utc=datetime.now(timezone.utc).isoformat(),documents=documents,summary=summary)
    write(out/'run_completed.json',meta)
    print(json.dumps(json_values({'output':str(out.relative_to(ROOT)),**summary}),indent=2))
    return 0 if infeasible_ok and not numeric_bad and summary['all_original_source_hashes_unchanged'] else 1


def write_reports(report_write,out,meta,s):
    relative=str(out.relative_to(ROOT))
    t27=f'''# T27 development status

Status: **PARTIAL — official gate OPEN**.

Executed locally: {s['fixture_count']} read-only QP fixtures using unchanged ProxQP {meta['packages']['proxsuite']} settings. Coverage includes inactive and torque-active boxes, two coupled active constraints with an analytic KKT optimum, redundant active faces, matched row rescaling over a 2^40 span, contradictory halfspaces, an impossible physical torque demand, the original infeasible 43-row midpoint, four actual r4 post-prehold matrices, a constructed active face of an actual 43-row matrix, float32-input quantization with a float64 solver, and identical-matrix consistency under the four schedule labels.

An independent SciPy HiGHS LP cross-checks linear feasibility. It is numerical evidence, not a certificate. Schedule-label solves do not integrate the plant or establish sampled-data consistency; A2 has that separate test.

Analytic-oracle/KKT failures: `{s['numeric_oracle_failures']}`. All expected infeasibility checks agree: `{s['expected_infeasibility_cross_checks_pass']}`. Strict raw-sign rejection/boundary-sign failures: `{s['strict_raw_boundary_rejections']}`. These cases retain raw negative values. Numerical KKT acceptance is separate from nonnegative-raw-row acceptance. No candidate is actuated. No threshold or expected value is retuned.

Source is inspected and fixtures EXECUTED LOCALLY; there is no independently signed T27 completion. The full frozen task/domain/conditioning stress protocol, robust treatment of near-boundary signs, real-time qualification and independent reviewer disposition remain outstanding. Official T27 is not cleared by a fixture count.

Evidence: `{relative}/t27_fixtures.json`; exact command, source hashes, environment and policy settings are in run_started.json. Human signatures: null.
'''
    g25=f'''# G2.5 screen report

Status: **INCOMPLETE — planner M1 missing; no official positive G2.5**.

Executed locally: {s['screen_count']} deterministic read-only points. Filter point passes: {s['filter_point_pass_count']}; filter point failures: {s['filter_point_fail_count']}. Inputs are the approved initial midpoint, actual measured r4 endpoints at cells 0/2/3/6, fourteen one-joint +/-10%-range offsets, and an explicitly labeled asymptotic observer-floor point. Offset/floor fixtures are not manufactured plant endpoints.

Each point logs necessary paired speed/position inequalities, physical h/psi1 and speed/manipulability conditions, full 43-row ProxQP and separate LP classifications including torque/manipulability rows, and raw negatives. Bounds are the original initial bound, correctly propagated 0.156 s envelope, or its explicitly labeled analytic floor. No phase or gain changes occur.

Planner factor-two lower witnesses use |M(q)^-1| only as a LOWER witness for a containing common domain, never as an M1 upper bound. Omitted nonnegative margins can only make planning harder; the witness cannot establish feasibility. The actual planner-pair API refuses missing Nbar/separate Abar inputs and returns BLOCKED_MISSING_M1_BOUNDS. Filter-point passes cannot clear the planner G2.5 gate.

Node selection is fixed by code before screening; no plant/trajectory is advanced. Status is EXECUTED LOCALLY for these sampled points, not independently accepted, not full-grid/global feasibility and not an official G2.5 campaign or A3 comparison. Usable common-domain M1 and a frozen complete screen protocol remain needed.

Evidence: `{relative}/g25_screens.json`. Human signatures: null.
'''
    m1=f'''# M1 requirements and implementable evidence API

Status: **INCOMPLETE — no official numerical bounds constructed**.

Approved mode remains M1_COMMON_FROZEN_DOMAIN_CONSTANTS; no candidate-dependent M2/local Taylor substitute is selected. Policy has no estimator grid/seed/budget, speed/acceleration/tube domain, complete numeric registry or bound equation map. Physical joint limits and the proposed 0.01 rad position extension are known; these do not define the full common domain.

The existing source-equation-linked registry is retained at `{relative}/m1_requirements.json`. It lists m1, diagonal/full inverse inertia bounds, Coriolis bounds, common q/v/a/tube domains, Abar/Nbar/Bbar/Dbar, ID/HOCBF derivative bounds, chi envelopes, rho_r, beta/signed margins and residual-Lipschitz/grid requirements with shapes, units and source equation hashes. Unsupplied values remain null.

New `M1DomainSpec(q_lower,q_upper,v_lower,v_upper,a_lower,a_upper,tube_q_radius,tube_v_radius,position_extension_rad,estimator_method,seed,budget)` requires explicit finite boxes and freezes a canonical SHA-256. `M1BoundRecord` requires finite nonnegative values, units, matching common domain/evaluator hashes and estimator method/grid/seed/budget; evidence level remains distinct from certification. `M1BoundBundle.require(name,shape,units)` raises MissingM1Bound for absent entries and never supplies zeros or point estimates. Bundles/returned arrays are immutable.

Unit-test bounds are explicitly SYNTHETIC; no such bundle becomes the actual robot registry. Even complete caller records are INPUTS_PRESENT_UNVERIFIED_NO_OFFICIAL_APPROVAL, certified=false. Metadata/shape validation does not validate domain coverage, a numerical upper bound, global enclosure or human acceptance.

Next computation needs a versioned common domain/estimator policy, source-traced derivative evaluators, Level 2 samples with raw evidence and honest coverage interpretation, and independent disposition for numerical planner use. Verified enclosure/Level 1 are separate absent work. Human approval fields remain null.
'''
    return [report_write('T27_STATUS.md',t27),report_write('G2_5_SCREEN_REPORT.md',g25),report_write('M1_REQUIREMENTS.md',m1)]


if __name__=='__main__':raise SystemExit(main())
