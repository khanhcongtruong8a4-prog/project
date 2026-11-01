"""Inspect draft completeness and evidence. This command cannot authorize A2."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import json
from datetime import datetime,timezone
from panda_closed_loop.config import Policy,digest
from panda_closed_loop.a2_plan import check_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,default=ROOT/'policy/v1.2.2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2.json')
    parser.add_argument('--screen',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    screen_path=args.screen
    if screen_path is None:
        pointer=json.loads((ROOT/'reports/p1_latest.json').read_text())
        screen_path=ROOT/pointer['run_directory']/'screen.json'
    screen=json.loads(screen_path.read_text())
    draft=json.loads(args.policy.read_text())
    result=check_plan(draft,Policy.load(),screen)
    result.update(policy_sha256=digest(args.policy),screen_sha256=digest(screen_path))
    if args.output:
        out=args.output.resolve()
        if not out.is_relative_to((ROOT/'runs').resolve()):
            raise ValueError('Checklist outputs must be below runs/')
    else:
        out=ROOT/'runs/p1_checklist'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    (out/'checklist.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(out.relative_to(ROOT)),'official_A2':result['official_A2'],
                      'incomplete_fields':[i['item'] for i in result['items'] if i['status']=='FAIL'],
                      'execution_performed':False},indent=2))
    return 1 if any(i['status']=='FAIL' for i in result['items']) else 0


if __name__=='__main__':raise SystemExit(main())
