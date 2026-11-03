"""Fail-closed aggregation of NEW eight-cell, T27 and 19-cell evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,copy,csv,hashlib,json,multiprocessing
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from panda_closed_loop.p1_r3 import compare_refinement
from panda_closed_loop.trace_archive import read_trace
from run_polynomial_hold_v2_4 import verify,plan_for

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def above_duration(coeff,threshold):
    square=np.zeros(7)
    for j in range(7):square+=np.convolve(coeff[:,j],coeff[:,j])
    square[0]-=threshold**2
    roots=np.polynomial.polynomial.polyroots(square)
    nodes=sorted([0.,1.]+[float(x.real) for x in roots if abs(x.imag)<1e-9 and 0<x.real<1])
    return sum(b-a for a,b in zip(nodes[:-1],nodes[1:]) if np.polynomial.polynomial.polyval((a+b)/2,square)>0)

def independent_trace_audit(path,cell,case):
    tr=cell['a2']['trace'];trace=read_trace(path/tr['file'],tr);holds=trace['holds'];steps=trace['substeps']
    checks={'nonempty':bool(holds and steps),'full_completion_KKT':True,'point_projection_KKT':True,
            'identical_accepted_polynomial_torques':True,'physical_and_observer':True,'complete_counts':True}
    maximum={'point_primal':0.,'point_stationarity':0.,'point_complementarity':0.,'completion_primal':0.,'completion_stationarity':0.,'completion_complementarity':0.,'stage_residual':0.}
    active_duration=0.;peak=0.;actual_feedback_sampled_peak=0.;energy=0.;minraw=np.inf
    from panda_closed_loop.polynomial_hold_v2_4 import polynomial_peak,torque
    for h in holds:
        q=h['completion'];C=np.array(q['C']);b=np.array(q['b']);x=np.array(q['x']);dual=np.array(q['dual_full']);res=C@x-b
        values=[max(0.,float(np.max(res))),float(np.max(abs(x+C.T@dual))),float(np.max(abs(dual*res)))]
        for name,v in zip(['completion_primal','completion_stationarity','completion_complementarity'],values):maximum[name]=max(maximum[name],v)
        raw=1e-8-res
        checks['full_completion_KKT'] &= (all(v<=1e-9 for v in values) and np.all(dual>=-1e-9) and np.all(raw>=0)
            and len(b)==387 and len(x)==28 and np.allclose(raw,q['full_raw_normalized_slacks'],rtol=0,atol=1e-13))
        minraw=min(minraw,float(np.min(raw)))
        diff=np.array(h['coefficients'])-h['nominal_coefficients'];peak=max(peak,polynomial_peak(diff))
        active_duration+=h['delta']*above_duration(diff,.001)
        for point in h['projection_queries']:
            G=np.array(point['G']);c=np.array(point['c']);scales=np.array(point['scales']);r=point['query'];tau=np.array(r['applied']);d=r['diagnostics'];dual=np.array(d['dual_scaled'])
            den=87*np.linalg.norm(G,axis=1);den=np.where(den>0,den,1.);C=-87*G/den[:,None];b=(c-1e-8*scales)/den;res=C@(tau/87)-b
            pv=[max(0.,float(np.max(res))),float(np.max(abs(tau/87-np.array(point['nominal'])/87+C.T@dual))),float(np.max(abs(dual*res)))]
            for name,v in zip(['point_primal','point_stationarity','point_complementarity'],pv):maximum[name]=max(maximum[name],v)
            checks['point_projection_KKT'] &= all(v<=1e-9 for v in pv) and np.all(dual>=-1e-9) and np.all(G@tau+c>=0)
    for s in steps:
        energy+=s['modeled_electrical_energy_increment_J'];maximum['stage_residual']=max(maximum['stage_residual'],s['stage_equation_residual'])
        checks['physical_and_observer'] &= all(s['checks'].values())
        period=s['control_period_index']
        for t,tau in zip(s['stage_times'],s['stage_torques']):checks['identical_accepted_polynomial_torques'] &= np.array_equal(torque(holds[period],t),tau)
    expected=plan_for(case)['references']['E3']['duration_s'];grid=cell['grid']
    checks['complete_counts'] &= len(holds)==round(expected/grid['control_period_s']) and len(steps)==round(expected/grid['rk4_step_s'])
    checks['metrics_recomputed']=(abs(peak-cell['a2']['metrics']['maximum_intervention_Nm'])<=1e-12 and energy==cell['a2']['metrics']['modeled_electrical_energy_J'])
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':all(checks.values()),'checks':checks,'maxima':maximum,'hold_count':len(holds),'substep_count':len(steps),
            'peak_digital_intervention_Nm':peak,'duration_above_0p001_Nm_s':active_duration,
            'genuine_activity_passed':peak>.01 and active_duration>=.005,'minimum_recomputed_raw_normalized_slack':minraw,
            'query_wall_time_s':{k:float(v) for k,v in zip(['median','p95','p99','maximum'],[np.median([h['wall_s'] for h in holds]),*np.quantile([h['wall_s'] for h in holds],[.95,.99]),max(h['wall_s'] for h in holds)])},'trace_sha256':tr['sha256'],'scope':'NUMERICAL_FULL_FINITE_GRID_KKT_AND_RECORDED_TRAJECTORY_AUDIT_NOT_INTERVAL_CERTIFICATE'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate-prefix',default='v2_4');p.add_argument('--regression-prefix',default='correction_v2_fresh');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    frozen,commit=verify();out=a.output;out.mkdir(parents=True,exist_ok=False);pending=[];result={};rows=[]
    for case in ['alpha5','alpha10']:
        cells=[];audits=[];jobs=[]
        for i in range(4):
            path=ROOT/'runs/active_remediation_v2'/f'{a.candidate_prefix}_{case}_cell{i}';file=path/'result.json'
            if not file.exists():pending.append(str(file.relative_to(ROOT)));continue
            c=load(file)
            cert=path/'AUDIT_V2_4A.json'
            if cert.exists():
                correction=load(cert)
                if correction.get('passed') and correction.get('original_result_sha256')==sha(file) and correction.get('trace_sha256')==c['a2']['trace']['sha256'] and correction.get('audit_policy_sha256')==sha(ROOT/'policy/active_remediation_v2/AUDIT_CORRECTION_V2_4A.json'):
                    c=copy.deepcopy(c);c['original_runtime_result_passed']=c['a2']['passed'];c['verification_correction']=correction
                    c['a2']['passed']=True;c['audit']['passed']=True
            cells.append(c)
            if c['a2']['completed'] and c['a2']['passed']:
                jobs.append((len(audits),path,c,case));audits.append(None)
            else:audits.append({'passed':False,'failure':c['a2']['failure']})
        if jobs:
            with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
                submitted=[(index,pool.submit(independent_trace_audit,path,c,kind)) for index,path,c,kind in jobs]
                for index,future in submitted:audits[index]=future.result()
        refinement=compare_refinement(cells,plan_for(case)['fixed_acceptance_thresholds'])
        passed=len(cells)==4 and all(c['a2']['passed'] and c['audit']['passed'] for c in cells) and all(r['passed'] and r.get('genuine_activity_passed',False) for r in audits) and all(v['status']=='PASS' for v in refinement['comparisons'])
        result[case]={'passed':bool(passed),'cells':cells,'independent_audits':audits,'refinement':refinement}
        for r in refinement['comparisons']:
            for name,v in r['metrics'].items():rows.append({'case':case,'cells':str(r['cells']),'factor':r['factor'],'metric':name,**{k:v[k] for k in ['absolute_difference','tolerance','passed']}})
    regression={};refinement_fields=[]
    rpath=ROOT/'runs/p1_r4'/f'{a.regression_prefix}_original_r4'/'summary.json'
    if rpath.exists():
        original=load(rpath);regression['original_7']={'cell_count':len(original['cells']),'passed':len(original['cells'])==7 and original['gate']['status']=='GO' and all(c['audit']['passed'] and c['a2']['passed'] for c in original['cells']),'summary_sha256':sha(rpath),'gate':original['gate']}
        for r in original['gate']['cohorts'].values():
            for c in r['comparisons']:refinement_fields.extend(m['passed'] for m in c['metrics'].values())
    else:pending.append(str(rpath.relative_to(ROOT)))
    for ref in ['E1','E2','E3']:
        pth=ROOT/'runs/guarded_qp_reliability_v1'/f'{a.regression_prefix}_v4_{ref}'/'summary.json'
        if pth.exists():
            v=load(pth);regression[ref]={'cell_count':len(v['cells']),'passed':len(v['cells'])==4 and v['outcome']=='PASS' and all(c['a2']['passed'] and c['audit']['passed'] for c in v['cells']),'summary_sha256':sha(pth),'refinement':v['refinement']}
            for c in v['refinement']['comparisons']:refinement_fields.extend(m['passed'] for m in c['metrics'].values())
        else:pending.append(str(pth.relative_to(ROOT)))
    t27path=ROOT/'reports/active_remediation_v2/t27_fresh/SUMMARY.json';t27=load(t27path) if t27path.exists() else {}
    t27pass=t27.get('overall_pass') is True and t27.get('fixture_count')==39 and all(v['passed'] for v in t27['results'])
    regressionpass=len(regression)==4 and sum(v['cell_count'] for v in regression.values())==19 and all(v['passed'] for v in regression.values()) and len(refinement_fields)==120 and all(refinement_fields)
    candidatepass=all(v['passed'] for v in result.values()) and len(rows)==48 and all(r['passed'] for r in rows)
    scope={'requested_checkpoint_recovered':False,'source_freeze_commit':commit,'pending':pending,'candidate':result,'regressions':regression,
           'candidate_refinement_fields':{'passed':sum(r['passed'] for r in rows),'total':len(rows)},
           'frozen_regression_refinement_fields':{'passed':sum(refinement_fields),'total':len(refinement_fields)},
           'T27':{'passed':bool(t27pass),'fixture_count':t27.get('fixture_count'),'summary_sha256':sha(t27path) if t27 else None},
           'separate_acceptance_decisions':{'eight_candidate_cells_and_refinements':'GO_NUMERICAL' if candidatepass else 'NOT_GO',
              'original_7_plus_extended_12':'GO_NUMERICAL' if regressionpass else 'NOT_GO','T27_39_finite_fixtures':'GO_FINITE_TESTED_SCOPE' if t27pass else 'NOT_GO',
              'A2_full_requested_numerical_campaign':'GO_NUMERICAL' if candidatepass and regressionpass and t27pass and not pending else 'NOT_GO',
              'hardware_real_time_deadline':'NOT_QUALIFIED_OFFLINE_SIMULATION','true_ODE_interval_safety':'NOT_CERTIFIED','certified_global_bounds':'NOT_ESTABLISHED','official_A3':'NOT_RUN_NO_GO','Level1':'NOT_CLAIMED_NO_GO'},
           'historical_failures_reclassified':False,'stored_witness_runtime_fallback':False,'official_A3_executed':False}
    with (out/'ACCEPTANCE.json').open('x') as f:json.dump(scope,f,indent=2,allow_nan=False);f.write('\n')
    with (out/'ALL_CANDIDATE_REFINEMENTS.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['case','cells','factor','metric','absolute_difference','tolerance','passed']);writer.writeheader();writer.writerows(rows)
    print(json.dumps(scope['separate_acceptance_decisions'],indent=2));return 0 if candidatepass and regressionpass and t27pass and not pending else 3
if __name__=='__main__':raise SystemExit(main())
