from pathlib import Path
import sys,time,json
root=Path('/workspace/project/panda_research');sys.path.insert(0,str(root/'src'));sys.path.insert(0,str(root/'scripts'))
from audit_gauss_execution_v2_4a import audit_cell,sha
from panda_closed_loop.assembly import build_components
from panda_closed_loop.a2_policy_v4 import build_amended_system
from run_polynomial_hold_v2_4 import verify
verify();policy=root/'policy/active_remediation_v2/AUDIT_CORRECTION_V2_4A.json'
for case in ['alpha5','alpha10']:
 system=build_components() if case=='alpha5' else build_amended_system()
 for i in range(4):
  folder=root/'runs/active_remediation_v2'/f'v2_4_{case}_cell{i}';target=folder/'AUDIT_V2_4A.json'
  if target.exists():continue
  while not (folder/'result.json').exists():time.sleep(10)
  result=audit_cell(folder,system,case);result['audit_policy_sha256']=sha(policy)
  with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
  print(case,i,result['passed'],result.get('maxima'),flush=True)
