"""Per-update and time-weighted RMS of the three distinct baseline differences."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/'PREDECLARED_BASELINE_REPRODUCTION.json').read_text())
root=Path(plan['fresh_checkout'])/'panda_research'/plan['new_run']
summary=json.loads((root/'summary.json').read_text())
rows=[]
for cell in summary['cells']:
    descriptor=cell['a2']['trace'];path=root/descriptor['file'];packed=path.read_bytes()
    assert hashlib.sha256(packed).hexdigest()==descriptor['sha256']
    raw=gzip.decompress(packed)
    assert hashlib.sha256(raw).hexdigest()==descriptor['uncompressed_json_sha256']
    updates=json.loads(raw)['updates'];delta=cell['grid']['control_period_s'];duration=len(updates)*delta
    data={name:[] for name in ['u_minus_r','tau_minus_u','tau_minus_r']}
    for item in updates:
        r=np.array(item['tracking_errors']['continuous_request_Nm']);u=np.array(item['u_nom']);tau=np.array(item['candidate_tau'])
        for name,value in [('u_minus_r',u-r),('tau_minus_u',tau-u),('tau_minus_r',tau-r)]:data[name].append(value)
    stats={}
    for name,value in data.items():
        a=np.array(value);norm=np.linalg.norm(a,axis=1)
        stats[name]={'max_L2_Nm':float(np.max(norm)),
                     'time_weighted_RMS_L2_Nm':float(np.sqrt(np.sum(delta*norm**2)/duration)),
                     'uniform_update_RMS_L2_Nm':float(np.sqrt(np.mean(norm**2))),
                     'time_weighted_component_RMS_Nm':np.sqrt(np.sum(delta*a*a,axis=0)/duration).tolist()}
    rows.append({'cell':cell['cell'],'grid':cell['grid'],'updates':len(updates),'weighted_duration_s':duration,**stats})
result={'scope':'EXECUTED LOCALLY FROM FRESH BASELINE RAW TRACES','definition':'Euclidean norm over 7 joints at applied updates. Time-weighted RMS=sqrt(sum_k Delta*||x_k||_2^2/(N*Delta)); constant Delta percell, mathematically equal to uniform update RMS. Not a continuous-time r(t) claim.','cells':rows,'independent_signature':None}
with (HERE/'BASELINE_SAMPLER_TIME_WEIGHTED.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('Computed all3 norms, max and explicit time-weighted RMS, for7 cells.')
