"""Read-only comparison of the predeclared clean baseline reproduction."""
from pathlib import Path
import csv,gzip,hashlib,json,math,subprocess
import numpy as np

HERE=Path(__file__).resolve().parent
PLAN=json.loads((HERE/'PREDECLARED_BASELINE_REPRODUCTION.json').read_text())
CHECKOUT=Path(PLAN['fresh_checkout'])
ROOT=CHECKOUT/'panda_research'
ORIGINAL=ROOT/PLAN['original_recorded_run']
FRESH=ROOT/PLAN['new_run']

def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def summary_norms(trace):
    updates=trace['updates']
    result={}
    values={'sampling_u_minus_r':[], 'QP_tau_minus_u':[], 'total_tau_minus_r':[]}
    for u in updates:
        r=np.asarray(u['tracking_errors']['continuous_request_Nm'])
        digital=np.asarray(u['u_nom']);tau=np.asarray(u['candidate_tau'])
        values['sampling_u_minus_r'].append(digital-r)
        values['QP_tau_minus_u'].append(tau-digital)
        values['total_tau_minus_r'].append(tau-r)
    for name,rows in values.items():
        a=np.asarray(rows);norms=np.linalg.norm(a,axis=1)
        result[name]={'norm':'Euclidean 2-norm over seven joints at applied control updates',
                      'unit':'N m','max':float(np.max(norms)),
                      'RMS':float(np.sqrt(np.mean(norms**2))),
                      'component_max_abs':np.max(abs(a),axis=0).tolist(),
                      'component_RMS':np.sqrt(np.mean(a*a,axis=0)).tolist()}
    return {'updates':len(updates),'RMS_cadence':'Uniform within each cell; one sample per applied control interval; not independent experiments',**result}

def numbers(value,prefix=''):
    if isinstance(value,dict):
        out={}
        for k,v in value.items():out.update(numbers(v,prefix+'.'+k))
        return out
    if isinstance(value,list):
        out={}
        for i,v in enumerate(value):out.update(numbers(v,prefix+f'[{i}]'))
        return out
    if isinstance(value,(float,int)) and not isinstance(value,bool):return {prefix:float(value)}
    return {}

def main():
    end=json.loads((FRESH/'run_completed.json').read_text())
    record=json.loads((FRESH/'summary.json').read_text())
    original=json.loads((ORIGINAL/'summary.json').read_text())
    start=json.loads((FRESH/'run_started.json').read_text())
    assert record['gate']['status']=='GO' and end['exit_code']==0 and end['frozen_inputs_unchanged']
    contracts=json.loads((HERE/'contracts_fresh.json').read_text())
    assert contracts['overall_pass'] and contracts['tests_run']==PLAN['expected_contract_tests']
    all_equal=[];differences=[];sampler=[]
    for index in range(7):
        a=original['cells'][index];b=record['cells'][index]
        eq={'cell':index,'grid_equal':a['grid']==b['grid'],
            'metrics_exact':a['a2']['metrics']==b['a2']['metrics'],
            'measured_zero_state_exact':a['endpoint']['state']==b['endpoint']['state'],
            'final_state_exact':a['a2']['final_state']==b['a2']['final_state'],
            'new_hold_completed':b['prehold']['completed'],'new_actual_endpoint_QP_pass':b['endpoint']['QP']['strict_pass'],
            'new_A2_cell_completed':b['a2']['completed'],'new_A2_cell_pass':b['a2']['passed'],'new_trace_audit_pass':b['audit']['passed']}
        all_equal.append(eq)
        for group,x,y in [('metrics',a['a2']['metrics'],b['a2']['metrics']),('zero_state',a['endpoint']['state'],b['endpoint']['state']),('final_state',a['a2']['final_state'],b['a2']['final_state'])]:
            nx,ny=numbers(x),numbers(y)
            for k in nx:
                delta=abs(nx[k]-ny[k])
                if delta: differences.append({'cell':index,'group':group,'key':k,'recorded':nx[k],'reproduced':ny[k],'absolute_difference':delta})
        path=FRESH/b['a2']['trace']['file']
        assert sha(path)==b['a2']['trace']['sha256']
        payload=gzip.decompress(path.read_bytes())
        assert hashlib.sha256(payload).hexdigest()==b['a2']['trace']['uncompressed_json_sha256']
        sampler.append({'cell':index,'grid':b['grid'],**summary_norms(json.loads(payload))})
    changed=[n for n,h in PLAN['tracked_input_hashes'].items() if sha(CHECKOUT/n)!=h]
    metadata_old=json.loads((ORIGINAL/'run_started.json').read_text())
    pa,pb=metadata_old['packages'],start['packages']
    package_differences={n:{'recorded':pa.get(n),'fresh':pb.get(n)} for n in sorted(set(pa)|set(pb)) if pa.get(n)!=pb.get(n)}
    status={'scope':'FRESH_CHECKOUT_FRESH_VENV_EXECUTED_LOCALLY_NOT_HUMAN_INDEPENDENT_SIGNOFF',
            'source_commit':PLAN['baseline_commit'],'predeclared_rule_sha256':sha(HERE/'PREDECLARED_BASELINE_REPRODUCTION.json'),
            'baseline_full_checkout_and_original_raw_traces_accessible':True,
            'source_verified_tracked_files':PLAN['preserved_tracked_file_count'],'changed_tracked_files':changed,
            'contract_tests_run':contracts['tests_run'],'contract_tests_passed':contracts['overall_pass'],
            'fresh_full_seven_cell_command_exit':end['exit_code'],'fresh_numerical_gate':record['gate']['status'],
            'all_seven_exact_reproductions':not differences and all(all(v for k,v in r.items() if k!='cell') for r in all_equal),
            'per_cell':all_equal,'nonzero_numeric_differences':differences,
            'original_packages_vs_fresh_packages_differences':package_differences,
            'baseline_runtime_status':'EXECUTED LOCALLY','source_inputs_status':'SOURCE VERIFIED',
            'original_archived_logs_status':'LOG-REPORTED and raw evidence accessible',
            'human_independent_review_status':'NOT VERIFIED; no human sign-off supplied',
            'independent_controls_signature':None,'independent_theory_signature':None,'new_machine_reproduction':False,
            'fresh_checkout':str(CHECKOUT),'fresh_venv':PLAN['fresh_venv'],'fresh_raw_run':str(FRESH),
            'fresh_run_started_sha256':sha(FRESH/'run_started.json'),'fresh_run_completed_sha256':sha(FRESH/'run_completed.json'),
            'fresh_summary_sha256':sha(FRESH/'summary.json'),'fresh_gate_sha256':sha(FRESH/'gate.json')}
    write(HERE/'BASELINE_REPRODUCTION_RESULTS.json',status)
    write(HERE/'BASELINE_SAMPLER_DIFFERENCES.json',{'scope':'FRESH BASELINE MEASUREMENTS; NO CONTINUOUS-THEOREM CLAIM','cells':sampler})
    with (HERE/'BASELINE_COMPARISON.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,list(all_equal[0]),lineterminator='\n');w.writeheader();w.writerows(all_equal)
    print(json.dumps({'fresh_gate':record['gate']['status'],'all_seven_exact':status['all_seven_exact_reproductions'],'preserved_tracked_files':len(PLAN['tracked_input_hashes']),'changed':changed,'package_inventory_differences':package_differences},indent=2))

if __name__=='__main__':main()
