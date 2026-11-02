"""Read-only solver qualification on retained matrices, never new motion."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,json
from datetime import datetime,timezone
import numpy as np
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from panda_closed_loop.logging import json_values
from panda_closed_loop.a2_qp_v2 import BoundedGuardedQP,NUMERICAL_POLICY


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    cases=[]
    for p in sorted((ROOT/'reports/a2_extended_v1/actual_extended_qp_diagnostics').glob('E*_cell_*.json')):
        d=json.loads(p.read_text());u=d['last_attempted_update']
        cases.append((p,u['u_nom'],AffineRows(u['G'],u['c'],u['row_scales'],u['row_names'],u['row_units'])))
    with BoundedGuardedQP([87]*4+[12]*3) as qp:
        results=[]
        for p,nom,rows in cases:
            result=qp.solve(nom,rows)
            record={'input_file':str(p.relative_to(ROOT)),'input_sha256':digest(p),'status':result.status,
                    'applied':result.applied,'stop_requested':result.stop_requested,'diagnostics':result.diagnostics}
            (out/(p.stem+'.json')).write_text(json.dumps(json_values(record),indent=2,allow_nan=False)+'\n')
            results.append({'case':p.stem,'pass':result.applied is not None and not result.stop_requested,
                            'status':result.status,'min_raw':min(result.diagnostics.get('raw_slacks',[0.]))})
            print(results[-1],flush=True)
    summary={'created_utc':datetime.now(timezone.utc).isoformat(),'policy':NUMERICAL_POLICY,'results':results,
             'all_pass':all(r['pass'] for r in results),'new_motion_executed':False,
             'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'src/panda_closed_loop/a2_qp_v2.py']}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return 0 if summary['all_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
