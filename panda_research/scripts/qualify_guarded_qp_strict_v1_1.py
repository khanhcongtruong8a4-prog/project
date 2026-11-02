"""Repeat the SAME frozen 39 fixtures with strict solver classification."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,hashlib,json,time
import numpy as np
from panda_closed_loop.a2_qp_reliable_v1_1 import BoundedGuardedQP
from panda_closed_loop.guarded_qp_qualification_v1 import fixtures,validate
from panda_closed_loop.guarded_qp_native_v1 import backend_record
from panda_closed_loop.logging import json_values

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    policy=ROOT/'policy/guarded_qp_reliability_v1/CLASSIFICATION_EXTENSION_V1_1.json'
    frozen=json.loads(policy.read_text())
    if any(sha(ROOT/n)!=h for n,h in frozen['source_sha256'].items()):raise ValueError('Extension source changed')
    a.output.mkdir(parents=True,exist_ok=False);results=[]
    with BoundedGuardedQP([87]*4+[12]*3) as solver:
        for i,(name,nominal,rows) in enumerate(fixtures(ROOT)):
            start=time.perf_counter();oracle=validate(nominal,rows);query=solver.solve(nominal,rows);error=None
            if oracle['feasible']:
                optimum=(oracle.get('exact_certificate') or {}).get('unique_optimum_y_float_display_only')
                if query.applied is not None and optimum is not None:error=float(np.max(abs(query.applied-87*np.array(optimum))))
                passed=(oracle['passed'] and not query.stop_requested and error is not None and error<=1e-7
                        and query.status=='QPSolverOutput.PROXQP_SOLVED')
            else:
                passed=(oracle['passed'] and query.stop_requested and query.applied is None and
                        query.status in ['QPSolverOutput.PROXQP_PRIMAL_INFEASIBLE','EXACT_CONSTANT_ROW_INFEASIBLE'])
            record=json_values({'name':name,'G':rows.G,'c':rows.c,'scales':rows.scales,'row_names':rows.names,
                'nominal':nominal,'oracle':oracle,'query':query.__dict__,'physical_error_vs_exact_Nm':error,
                'passed':bool(passed),'wall_s':time.perf_counter()-start,'torque_actuated':False})
            with (a.output/f'fixture_{i:02d}.json').open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
            results.append({k:record[k] for k in ['name','passed','physical_error_vs_exact_Nm','wall_s']})
            print(i,name,'PASS' if passed else 'FAIL',query.status,flush=True)
    overall=all(r['passed'] for r in results)
    with (a.output/'SUMMARY.json').open('x') as f:json.dump({'overall_pass':overall,'fixture_count':len(results),
        'strict_SOLVED_or_exactly_crosschecked_INFEASIBLE_required':True,'results':results,'backend':backend_record(),
        'classification_extension':'V1_1_ZERO_NORMAL_INFEASIBILITY_ONLY','source_sha256':frozen['source_sha256'],
        'physical_parameters_changed':False,'witness_fallback':False,
        'scope':'FINITE_NUMERICAL_T27_REGRESSION_NOT_GLOBAL_DOMAIN_PROOF_OR_LEVEL1'},f,indent=2);f.write('\n')
    return 0 if overall else 3

if __name__=='__main__':raise SystemExit(main())
