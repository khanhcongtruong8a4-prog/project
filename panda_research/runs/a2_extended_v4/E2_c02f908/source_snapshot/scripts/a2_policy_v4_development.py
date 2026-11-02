"""Read-only v4 nominal-feasibility screen on all retained v2 E3 states."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json
import numpy as np
from panda_closed_loop.a2_policy_v4 import build_amended_system,AMENDMENT
from panda_closed_loop.a2_qp_v2 import BoundedGuardedQP
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.trace_archive import read_trace,write_trace


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);system=build_amended_system();system.geometry.function=system.geometry.function.expand();results=[]
    for i in range(4):
        folder=ROOT/'runs/a2_extended_v2/E3_0391c5b';cp=folder/f'cell_{i}.json';cell=json.loads(cp.read_text());tr=cell['a2']['trace']
        updates=read_trace(folder/tr['file'],tr)['updates'];log=[];worst=(np.inf,None,None)
        for index,u in enumerate(updates):
            rows=system.barriers.rows(u['q'],u['qd'],u['dhat'],u['varpi']);raw=rows.slacks(u['u_nom']);score=float(min(raw/rows.scales))
            log.append({'index':index,'t_s':u['physical_t_s'],'nominal_actual_v4_raw_rows':raw,'minimum_normalized_raw':score,'nominal_feasible':bool(np.all(raw>=0)),'torque_actuated':False})
            if score<worst[0]:worst=(score,index,rows)
        with BoundedGuardedQP(system.barriers.taumax) as qp:solved=qp.solve(updates[worst[1]]['u_nom'],worst[2])
        record={'cell':i,'source_cell':str(cp.relative_to(ROOT)),'source_cell_sha256':digest(cp),'source_trace':tr,
            'states_screened':len(log),'all_nominal_requests_feasible':all(v['nominal_feasible'] for v in log),
            'worst_normalized_raw':worst[0],'worst_index':worst[1],'full_actual_43_QP_at_worst_nominal_point':json_values(solved.__dict__),
            'trace':write_trace(out/f'cell_{i}_read_only_screen.ctz',log),'new_motion_executed':False}
        (out/f'cell_{i}.json').write_text(json.dumps(record,indent=2)+'\n');results.append(record)
        print('cell',i,'count',len(log),'nominal_feasible',record['all_nominal_requests_feasible'],'min',worst[0],flush=True)
    summary={'scope':'READ_ONLY_RETAINED_V2_STATES_NOT_V4_PLANT_OR_REFINEMENT_EVIDENCE','amendment':AMENDMENT,'results':results,
        'all_pass':all(r['all_nominal_requests_feasible'] and not r['full_actual_43_QP_at_worst_nominal_point']['stop_requested'] for r in results),
        'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'src/panda_closed_loop/a2_policy_v4.py']}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return 0 if summary['all_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
