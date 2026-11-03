from pathlib import Path
import os,signal,json,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
root=Path('/workspace/project/panda_research')
for p in Path('/proc').glob('[0-9]*/cmdline'):
 try:a=[v.decode() for v in p.read_bytes().split(b'\0') if v]
 except (OSError,UnicodeDecodeError):continue
 if len(a)>1 and a[1]=='/workspace/panda-tools/remaining_candidates_v2_4.py':os.kill(int(p.parent.name),signal.SIGTERM)
active=[]
for p in Path('/proc').glob('[0-9]*/cmdline'):
 try:a=[v.decode() for v in p.read_bytes().split(b'\0') if v]
 except (OSError,UnicodeDecodeError):continue
 if len(a)>1 and a[1]=='scripts/run_polynomial_hold_v2_4.py':active.append((a[a.index('--case')+1],int(a[a.index('--cell')+1])))
pending=[]
for case in ['alpha5','alpha10']:
 for i in range(4):
  if (case,i) not in active and not (root/'runs/active_remediation_v2'/f'v2_4_{case}_cell{i}'/'result.json').exists():pending.append((case,i))
with (root/'reports/active_remediation_v2/PARALLELISM_RESCHEDULE.json').open('x') as f:json.dump({'reason':'Original 19-cell replay finished; use freed CPU slots. No running physical cell is interrupted or repeated.','active_unchanged':active,'pending_unchanged_commands':pending,'available_cores':5,'workers_for_pending':3},f,indent=2)
def run(pair):
 case,i=pair;name=f'v2_4_{case}_cell{i}';cmd=[sys.executable,'scripts/run_polynomial_hold_v2_4.py','--case',case,'--cell',str(i),'--output','runs/active_remediation_v2/'+name]
 for old in ['v2_3','v2_2','v2_1']:
  prior=root/'runs/active_remediation_v2'/f'{old}_{case}_cell{i}'
  if (prior/'result.json').exists() and json.loads((prior/'result.json').read_text())['prehold']['passed']:cmd.extend(['--prehold-source',str(prior)]);break
 with (root/'reports/active_remediation_v2'/f'{name}.log').open('x') as f:r=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 return {'case':case,'cell':i,'exit_code':r.returncode,'command':cmd}
with ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(run,pending))
with (root/'reports/active_remediation_v2/rescheduled_exit_codes.json').open('x') as f:json.dump(records,f,indent=2)
