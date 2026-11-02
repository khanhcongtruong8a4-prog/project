"""Read-only diagnosis of preserved active-filter traces; no new actuation."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,hashlib,json,time
import numpy as np
from panda_closed_loop.a2_acceptance import read_recorded_trace
from panda_closed_loop.a2_qp_reliable_v1_1 import GuardedHardQP
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.logging import json_values

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    folder=ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_active_E3'
    summary=json.loads((folder/'summary.json').read_text());results=[];arrays=[]
    qp=GuardedHardQP([87]*4+[12]*3)
    for cell in summary['cells']:
        index=cell['cell'];trace=read_recorded_trace(folder,cell['a2']['trace']);updates=trace['updates']
        t=np.array([u['physical_t_s'] for u in updates]);request=np.array([u['u_nom'] for u in updates])
        raw=np.array([u['tracking_errors']['continuous_request_Nm'] for u in updates]);tau=np.array([u['candidate_tau'] for u in updates])
        intervention=np.linalg.norm(tau-request,axis=1);sample_correction=request-raw
        sets=[tuple(i for i,x in enumerate(u['diagnostics']['dual_scaled']) if x>1e-10) for u in updates]
        transitions=[{'time':float(t[k]),'previous_time':float(t[k-1]),'from':[updates[k]['row_names'][i] for i in sets[k-1]],
                      'to':[updates[k]['row_names'][i] for i in sets[k]]} for k in range(1,len(t)) if sets[k]!=sets[k-1]]
        raw_filtered=[];hypothesis_bad=[];commutation=[];solve_failures=[]
        for k,u in enumerate(updates):
            rows=AffineRows(u['G'],u['c'],u['row_scales'],tuple(u['row_names']),tuple(u['row_units']))
            solve=qp.solve(raw[k],rows)
            if solve.stop_requested:
                solve_failures.append({'index':k,'status':solve.status});raw_filtered.append(None);continue
            raw_filtered.append(solve.applied)
            if k and raw_filtered[k-1] is not None:
                hypothetical=solve.applied+.5*(solve.applied-raw_filtered[k-1])
                slacks=rows.slacks(hypothetical);bad=np.where(slacks<0)[0]
                commutation.append(float(np.linalg.norm(tau[k]-hypothetical)))
                if len(bad):hypothesis_bad.append({'index':k,'time':float(t[k]),
                    'minimum_normalized_raw_slack':float(np.min(slacks/rows.scales)),
                    'rows':[rows.names[i] for i in bad]})
        peak=int(np.argmax(intervention));peak_fit=None
        if 0<peak<len(t)-1:
            coef=np.polyfit(t[peak-1:peak+2]-t[peak],intervention[peak-1:peak+2],2)
            vertex=-coef[1]/(2*coef[0])
            if coef[0]<0 and abs(vertex)<cell['grid']['control_period_s']:
                peak_fit={'time':float(t[peak]+vertex),'intervention':float(np.polyval(coef,vertex)),
                          'scope':'DIAGNOSTIC_ONLY_NOT_AN_ACCEPTANCE_METRIC_REPLACEMENT'}
        energy=np.array([s['modeled_electrical_energy_increment_J'] for s in trace['substeps']])
        end=np.array([s['physical_t1_s'] for s in trace['substeps']])
        arrays.append({'time':t,'raw':raw,'request':request,'tau':tau,'state':np.array([u['q']+u['qd']+u['z'] for u in updates]),
                       'energy_t':end,'energy':np.cumsum(energy)})
        result={'cell':index,'grid':cell['grid'],'historical_metrics':cell['a2']['metrics'],
            'positive_dual_active_rows':sorted({updates[0]['row_names'][i] for s in sets for i in s}),
            'active_update_count':sum(bool(s) for s in sets),'transitions':transitions,
            'intervention_peak_time':float(t[peak]),'quadratic_peak_diagnostic':peak_fit,
            'max_AB2_sampling_correction_Nm':float(np.max(np.linalg.norm(sample_correction,axis=1))),
            'max_tau_minus_raw_Nm':float(np.max(np.linalg.norm(tau-raw,axis=1))),
            'raw_request_projection_diagnostic_failures':solve_failures,
            'unactuated_AB2_after_filter_negative_raw_queries':len(hypothesis_bad),
            'unactuated_AB2_after_filter_negative_raw_examples':hypothesis_bad[:10],
            'max_projection_AB2_commutator_Nm':max(commutation,default=None),'hypothetical_torque_actuated':False}
        results.append(result)
        with (a.output/f'cell_{index}.json').open('x') as f:json.dump(json_values(result),f,indent=2);f.write('\n')
        print('cell',index,'active',result['active_update_count'],'bad projected-then-AB2',len(hypothesis_bad),flush=True)
    pairs=[]
    for i,j in [(0,1),(2,3),(0,2),(1,3)]:
        x,y=arrays[i],arrays[j];ratio=round(len(y['time'])/len(x['time']))
        if ratio<1 or len(y['time'][::ratio])!=len(x['time']):raise ValueError('Unaligned preserved grids')
        aligned={k:float(np.max(abs(x[k]-y[k][::ratio]))) for k in ['raw','request','tau','state']}
        energy_differences={}
        for boundary in [.1,.2,.3,.4,.5,.6,.7,.8,.9,1.]:
            values=[float(z['energy'][np.searchsorted(z['energy_t'],boundary,side='right')-1]) for z in [x,y]]
            energy_differences[str(boundary)]={'values':values,'difference':values[0]-values[1]}
        pairs.append({'cells':[i,j],'aligned_max_absolute_differences':aligned,'cumulative_energy_differences_J':energy_differences})
    output={'scope':'LOCAL_READ_ONLY_ACTIVE_FILTER_DIAGNOSIS_NO_ACTUATION_NO_A3',
        'source_summary_sha256':hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest(),
        'cells':results,'pairs':pairs,'historical_failure_outcome_unchanged':summary['outcome'],
        'thresholds_changed':False,'gains_or_constraints_changed':False,'external_signatures':None}
    with (a.output/'SUMMARY.json').open('x') as f:json.dump(output,f,indent=2,allow_nan=False);f.write('\n')

if __name__=='__main__':main()
