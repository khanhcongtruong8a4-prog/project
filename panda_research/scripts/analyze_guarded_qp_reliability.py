"""Audit replay equivalence and derive decisions from completed evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,hashlib,json,math
import numpy as np
from panda_closed_loop.a2_acceptance import compare_cell,read_recorded_trace,scientific_digest

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

IGNORED={'solver','backend_correction','iterations','duality_gap','dual_original','dual_scaled',
         'complementarity','guarded_complementarity','normalized_primal','scaled_stationarity',
         'guarded_normalized_primal','guarded_scaled_stationarity','solve_runtime_s'}

def physical_comparison(a,b):
    result={'passed':True,'numeric_values_compared':0,'max_absolute_difference':0.,
            'max_torque_absolute_difference_Nm':0.,'failures':[]}
    def reject(path,reason,old=None,new=None):
        result['passed']=False
        if len(result['failures'])<20:result['failures'].append({'path':path,'reason':reason,'old':old,'new':new})
    def walk(x,y,path='',torque=False):
        if isinstance(x,dict) and isinstance(y,dict):
            left=set(x)-IGNORED;right=set(y)-IGNORED
            if left!=right:reject(path,'physical keys differ',sorted(left-right),sorted(right-left))
            for k in sorted(left&right):walk(x[k],y[k],path+'/'+k,torque or k in ['candidate_tau','tau_candidate','applied_tau','u_nom','tau','tau_applied'])
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):reject(path,'length',len(x),len(y))
            for i,(xx,yy) in enumerate(zip(x,y)):walk(xx,yy,path+'/'+str(i),torque)
        elif isinstance(x,(int,float)) and isinstance(y,(int,float)) and not isinstance(x,bool) and not isinstance(y,bool):
            error=abs(x-y);result['numeric_values_compared']+=1
            result['max_absolute_difference']=max(result['max_absolute_difference'],error)
            if torque:result['max_torque_absolute_difference_Nm']=max(result['max_torque_absolute_difference_Nm'],error)
            if error>1e-8+1e-10*max(abs(x),abs(y)):reject(path,'frozen numeric comparison threshold',x,y)
            if torque and error>1e-7:reject(path,'absolute torque ceiling',x,y)
        elif x!=y:reject(path,'exact nonnumeric value',x,y)
    walk(a,b)
    result['ignored_fields']=sorted(IGNORED)
    result['ignored_scope']='Declared backend diagnostics only; fresh raw signs and KKT independently audited without resolving QPs.'
    return result

def failed_refinements(summary):
    return [{'cells':r['cells'],'factor':r['factor'],'metric':m,**v}
        for r in summary['refinement']['comparisons'] for m,v in r['metrics'].items() if not v['passed']]

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='reliability_v1_fresh');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result={'prefix':a.prefix,'external_signatures':None,'Level1_claimed':False,'A3_comparisons_executed':False}
    old=ROOT/'runs/p1_r4/fresh_2fe50b9';new=ROOT/f'runs/p1_r4/{a.prefix}_original_r4'
    s,t=load(old/'summary.json'),load(new/'summary.json')
    cells=[compare_cell(x,y,old,new) for x,y in zip(s['cells'],t['cells'])]
    result['original_A2']={'cells':cells,'gate':t['gate'],'passed':len(cells)==7 and all(r['passed'] for r in cells) and t['gate']['status']=='GO'}
    result['v4']={};new_runs=[];minimum_row_norm=float('inf')
    for ref in ['E1','E2','E3']:
        old=ROOT/f'runs/a2_extended_v4/{ref}_c02f908';new=ROOT/f'runs/guarded_qp_reliability_v1/{a.prefix}_v4_{ref}'
        s,t=load(old/'summary.json'),load(new/'summary.json');cells=[]
        for x,y in zip(s['cells'],t['cells']):
            comparisons={};all_trace=True
            for phase in ['prehold','a2']:
                ot=read_recorded_trace(old,x[phase]['trace']);nt=read_recorded_trace(new,y[phase]['trace'])
                if phase=='a2':
                    for u in nt['updates']:minimum_row_norm=min(minimum_row_norm,float(np.min(np.linalg.norm(u['G'],axis=1))))
                comparison=physical_comparison(ot,nt)
                comparison.update(original_full_scientific_sha256=scientific_digest(ot),new_full_scientific_sha256=scientific_digest(nt))
                comparison['full_scientific_trace_exact']=comparison['original_full_scientific_sha256']==comparison['new_full_scientific_sha256']
                comparisons[phase]=comparison;all_trace &= comparison['passed']
            metrics=physical_comparison(x['a2']['metrics'],y['a2']['metrics'])
            cells.append({'cell':y['cell'],'passed':bool(all_trace and metrics['passed'] and y['audit']['passed'] and y['a2']['passed'] and y['endpoint']['QP']['strict_pass']),
                'physical_trace_comparisons':comparisons,'metrics_comparison':metrics})
        result['v4'][ref]={'cells':cells,'refinement':t['refinement'],'outcome':t['outcome'],
            'passed':len(cells)==4 and all(c['passed'] for c in cells) and t['outcome']=='PASS' and not failed_refinements(t)}
        new_runs+=t['cells']
    active=load(ROOT/f'runs/guarded_qp_reliability_v1/{a.prefix}_active_E3/summary.json')
    result['active_filter']={'outcome':active['outcome'],'cells':[{'cell':c['cell'],'completed':c['a2']['completed'],
        'passed':c['a2']['passed'],'audited':c['audit']['passed'],'metrics':c['a2']['metrics']} for c in active['cells']],
        'refinement':active['refinement'],'failed_refinement_metrics':failed_refinements(active),
        'passed':active['outcome']=='PASS' and not failed_refinements(active)}
    t27=load(ROOT/'reports/guarded_qp_reliability_v1/t27_fresh/SUMMARY.json')
    unresolved=[]
    for i in range(t27['fixture_count']):
        f=load(ROOT/f'reports/guarded_qp_reliability_v1/t27_fresh/fixture_{i:02d}.json')
        if f['query']['status'] not in ['QPSolverOutput.PROXQP_SOLVED','QPSolverOutput.PROXQP_PRIMAL_INFEASIBLE']:
            unresolved.append({'fixture':i,'name':f['name'],'status':f['query']['status'],'torque_actuated':False})
    result['T27']={'declared_regression_passed':t27['overall_pass'],'fixtures':t27['fixture_count'],'unresolved_solver_classifications':unresolved,
        'scope':'Finite guarded-QP accuracy and safe-stop regression, not a global solver-domain proof.'}
    strict=load(ROOT/'reports/guarded_qp_reliability_v1/t27_strict_v1_1_fresh/SUMMARY.json')
    result['T27']['classification_extension_strict_rerun']={'passed':strict['overall_pass'],'fixtures':strict['fixture_count'],
        'same_fixtures_data_oracles_tolerances':True,'strict_SOLVED_or_exactly_crosschecked_INFEASIBLE_required':True,
        'source_sha256':strict['source_sha256'],'history_of_v1_unknown_retained':True}
    checks=load(ROOT/f'reports/guarded_qp_reliability_v1/{a.prefix}/CONTRACTS.json')
    protected=load(ROOT/'policy/guarded_qp_reliability_v1/PROTECTED_INPUTS.json')
    changed=[n for n,h in protected['protected_source_sha256'].items() if sha(ROOT.parent/n)!=h]
    result['protected_files']={'count':len(protected['protected_source_sha256']),'unchanged':not changed,'changed':changed}
    selected=not changed and all(c['passed'] for c in checks.values()) and result['original_A2']['passed'] and all(v['passed'] for v in result['v4'].values())
    result['decisions']={'A2_SELECTED_FROZEN_SCOPE':'GO' if selected else 'NO-GO',
        'GENERAL_GUARDED_QP_QUALIFICATION':'GO' if selected and result['active_filter']['passed'] and not unresolved and t27['overall_pass'] else 'NO-GO',
        'T27_FINITE_REGRESSION':'GO' if t27['overall_pass'] else 'NO-GO',
        'T27_CLASSIFICATION_EXTENSION_FINITE_SCOPE':'GO' if strict['overall_pass'] else 'NO-GO',
        'A3_READINESS':'NO-GO'}
    result['corrected_v4_extrema']={'maximum_actual_terminal_error_m':max(c['a2']['metrics']['actual_terminal_error_m'] for c in new_runs),
        'minimum_normalized_raw_slack':min(c['a2']['metrics']['minimum_normalized_raw_slack'] for c in new_runs),
        'maximum_scaled_stationarity':max(c['a2']['metrics']['max_scaled_stationarity'] for c in new_runs),
        'minimum_constraint_normal_norm':minimum_row_norm,
        'v1_1_constant_classifier_changes_any_selected_v4_query':minimum_row_norm==0.}
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result['decisions'],indent=2))

if __name__=='__main__':main()
