"""T27 numerical regression with separate exact-QP oracles; no actuation."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,time
import numpy as np
from panda_closed_loop.a2_qp_reliable_v1 import BoundedGuardedQP
from panda_closed_loop.guarded_qp_qualification_v1 import fixtures,validate
from panda_closed_loop.guarded_qp_native_v1 import backend_record
from panda_closed_loop.logging import json_values


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);results=[]
    with BoundedGuardedQP([87]*4+[12]*3) as solver:
        for i,(name,nominal,rows) in enumerate(fixtures(ROOT)):
            start=time.perf_counter();oracle=validate(nominal,rows);query=solver.solve(nominal,rows)
            error=None
            if oracle['feasible']:
                optimum=(oracle.get('exact_certificate') or {}).get('unique_optimum_y_float_display_only')
                if query.applied is not None and optimum is not None:error=float(np.max(abs(query.applied-87*np.array(optimum))))
                passed=oracle['passed'] and not query.stop_requested and error is not None and error<=1e-7
            else:passed=oracle['passed'] and query.stop_requested and query.applied is None
            record=json_values({'name':name,'G':rows.G,'c':rows.c,'scales':rows.scales,'row_names':rows.names,
                'nominal':nominal,'oracle':oracle,'query':query.__dict__,'physical_error_vs_exact_Nm':error,
                'passed':bool(passed),'wall_s':time.perf_counter()-start,'torque_actuated':False})
            with (a.output/f'fixture_{i:02d}.json').open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
            results.append({k:record[k] for k in ['name','passed','physical_error_vs_exact_Nm','wall_s']})
            print(i,name,'PASS' if passed else 'FAIL',query.status,flush=True)
    overall=all(r['passed'] for r in results)
    with (a.output/'SUMMARY.json').open('x') as f:json.dump({'overall_pass':overall,'fixture_count':len(results),
        'results':results,'backend':backend_record(),'physical_parameters_changed':False,'witness_fallback':False,
        'scope':'T27_EXECUTED_FINITE_NUMERICAL_REGRESSION_NOT_GLOBAL_DOMAIN_PROOF_OR_LEVEL1'},f,indent=2);f.write('\n')
    return 0 if overall else 3

if __name__=='__main__':raise SystemExit(main())
