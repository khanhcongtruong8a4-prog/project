from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,subprocess,sys
root=Path('/workspace/project/panda_research')
cells=[('alpha5',i) for i in range(1,4)]+[('alpha10',i) for i in range(4)]
def run(pair):
 case,index=pair;name=f'v2_3_{case}_cell{index}'
 cmd=[sys.executable,'scripts/run_polynomial_hold_v2_3.py','--case',case,'--cell',str(index),'--output','runs/active_remediation_v2/'+name]
 for old in ['v2_2','v2_1']:
  prior=root/'runs/active_remediation_v2'/f'{old}_{case}_cell{index}'
  if (prior/'result.json').exists():
   data=json.loads((prior/'result.json').read_text())
   if data['prehold']['passed']:
    cmd.extend(['--prehold-source',str(prior)]);break
 with (root/'reports/active_remediation_v2'/f'{name}.log').open('x') as f:r=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return {'case':case,'cell':index,'command':cmd,'exit_code':r.returncode}
with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,cells))
with (root/'reports/active_remediation_v2/remaining_candidate_exit_codes_v2_3.json').open('x') as f:json.dump(result,f,indent=2)
