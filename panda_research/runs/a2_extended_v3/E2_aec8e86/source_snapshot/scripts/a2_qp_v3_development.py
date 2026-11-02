"""Read-only causal QP qualification over all retained v2 E3 matrices.

States and requests are retained v2 data, not new v3 physical trajectories.
No torque is actuated and this cannot establish v3 motion/refinement PASS.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json
from datetime import datetime,timezone
import numpy as np
from panda_closed_loop.a2_qp_v3 import BoundedIntervalQP,SAMPLING_QP_POLICY
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from panda_closed_loop.trace_archive import read_trace,write_trace
from panda_closed_loop.logging import json_values


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    results=[]
    for i in range(4):
        folder=ROOT/'runs/a2_extended_v2/E3_0391c5b';cp=folder/f'cell_{i}.json';cell=json.loads(cp.read_text())
        tr=cell['a2']['trace'];updates=read_trace(folder/tr['file'],tr)['updates'];log=[]
        with BoundedIntervalQP([87]*4+[12]*3) as qp:
            for index,u in enumerate(updates):
                rr=AffineRows(u['G'],u['c'],u['row_scales'],tuple(u['row_names']),tuple(u['row_units']))
                r=qp.solve(u['u_nom'],rr);d=r.diagnostics
                log.append({'index':index,'physical_t_s':u['physical_t_s'],'status':r.status,
                    'pass':r.applied is not None and not r.stop_requested,'candidate_not_actuated':r.applied,
                    'torque_applied':False,'raw_current':d.get('raw_slacks'),'raw_actual_QP':d.get('actual_QP_diagnostics',{}).get('raw_slacks'),
                    'normalized_primal':d.get('normalized_primal'),'scaled_stationarity':d.get('scaled_stationarity')})
                if r.applied is None or r.stop_requested:
                    log[-1]['full_failure_diagnostics']=d
                    break
        archive=write_trace(out/f'cell_{i}_read_only_queries.ctz',log)
        result={'cell':i,'source_cell':str(cp.relative_to(ROOT)),'source_cell_sha256':digest(cp),'source_trace':tr,
                'queries':len(log),'expected_queries':len(updates),'passed':len(log)==len(updates) and all(v['pass'] for v in log),
                'trace':archive,'all_current_raw_rows_checked':True,'new_motion_executed':False,'torque_actuated':False}
        (out/f'cell_{i}.json').write_text(json.dumps(json_values(result),indent=2)+'\n');results.append(result)
        print(f"cell {i}: queries={len(log)}/{len(updates)} pass={result['passed']}",flush=True)
    summary={'created_utc':datetime.now(timezone.utc).isoformat(),'policy':SAMPLING_QP_POLICY,'results':results,
             'all_pass':all(c['passed'] for c in results),'scope':'READ_ONLY_RETAINED_V2_MATRICES_NOT_V3_PLANT_OR_REFINEMENT_EVIDENCE',
             'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'src/panda_closed_loop/a2_qp_v3.py']}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return 0 if summary['all_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
