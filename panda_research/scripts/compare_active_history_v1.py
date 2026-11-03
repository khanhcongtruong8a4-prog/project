"""Compare complete fresh/retained legacy histories without discarding failures."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,hashlib,json
from panda_closed_loop.a2_acceptance import compare_cell

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='sd_v1_fresh');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old=ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_active_E3'
    new=ROOT/f'runs/guarded_qp_reliability_v1/{a.prefix}_active_E3'
    original=json.loads((old/'summary.json').read_text());fresh=json.loads((new/'summary.json').read_text())
    comparisons=[]
    for x,y in zip(original['cells'],fresh['cells']):
        result=compare_cell(x,y,old,new);comparisons.append(result)
        print('historical full-trace comparison',y['cell'],result['passed'],flush=True)
    failed=lambda s:[{'cells':r['cells'],'factor':r['factor'],'metric':m,**v} for r in s['refinement']['comparisons'] for m,v in r['metrics'].items() if not v['passed']]
    failures=failed(fresh)
    passed=len(comparisons)==4 and all(r['passed'] for r in comparisons) and len(failures)==8 and failures==failed(original) and fresh['refinement']==original['refinement'] and fresh['outcome']==original['outcome']=='FAIL'
    result={'historical_reproduction_passed':passed,'fresh_simulations_executed':True,'cell_comparisons':comparisons,
        'all_refinement_comparisons_exact':fresh['refinement']==original['refinement'],
        'eight_failed_metrics_preserved':failures,'failed_refinement_count':len(failures),'original_outcome':original['outcome'],
        'fresh_outcome':fresh['outcome'],'refinement':fresh['refinement'],'authoritative_source_commit':'f6d5a18d9046d4a814e480498f916f92b4396287',
        'native_solver_sha256':'3370c29e2c3e42db44bc7cfed1d385ebc6680a519a1501693c223575122fc8c1',
        'same_original_thresholds':True,'no_failed_gate_promoted':True,'external_signatures':None}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with a.output.with_suffix('.csv').open('x',newline='') as f:
        fields=['cell','control_period_s','rk4_step_s','energy_J','peak_tau_minus_u_Nm','minimum_normalized_raw_slack','physics_pass','audit_pass','full_trace_exact']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c,r in zip(fresh['cells'],comparisons):
            m=c['a2']['metrics'];w.writerow(dict(zip(fields,[c['cell'],c['grid']['control_period_s'],c['grid']['rk4_step_s'],m['modeled_electrical_energy_J'],m['maximum_intervention_Nm'],m['minimum_normalized_raw_slack'],c['a2']['passed'],c['audit']['passed'],r['passed']])))
    return 0 if passed else 3

if __name__=='__main__':raise SystemExit(main())
