"""Prepare a method-independent target PROPOSAL, without planner/filter runs."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pinocchio as pin
from scipy.stats import qmc
from reference_model import build_reference_urdf

ROOT=Path(__file__).resolve().parents[1]


def main():
    registry=json.loads((ROOT/'baseline/model_manifest_v1.json').read_text())
    lower=np.array(registry['joint_limits_qmin_rad'])
    upper=np.array(registry['joint_limits_qmax_rad'])
    model=pin.buildModelFromUrdf(str(build_reference_urdf()))
    data=model.createData()
    flange=model.getFrameId('panda_link8')
    def position(q):
        pin.framesForwardKinematics(model,data,q)
        return data.oMf[flange].translation.copy()
    q0=(lower+upper)/2
    x0=position(q0)
    fractions=qmc.Sobol(d=7,scramble=True,seed=20261102).random_base2(m=6)
    candidates=lower+(.05+.9*fractions)*(upper-lower)
    rows=[]; accepted=[]
    for i,q in enumerate(candidates):
        x=position(q)
        distance=float(np.linalg.norm(x-x0))
        duplicate=any(np.linalg.norm(x-prev)<1e-6 for prev in accepted)
        reason='distance_below_0.10_m' if distance<.10 else 'duplicate_within_1e-6_m' if duplicate else 'INCLUDED'
        if reason=='INCLUDED':accepted.append(x)
        rows.append({'candidate_index':i,'seed_configuration_rad':q.tolist(),'flange_target_m':x.tolist(),
                     'distance_from_initial_m':distance,'disposition':reason})
    report={'status':'PROPOSED_FIXED_TARGET_LIST_PENDING_TEAM_APPROVAL', 'seed':20261102,
        'generator':'scipy.stats.qmc.Sobol(d=7,scramble=True,seed=20261102).random_base2(m=6)',
        'domain':'joint fraction .05.. .95 of physical box', 'initial_q_rad':q0.tolist(),
        'initial_qd_rad_s':[0.]*7,'initial_flange_m':x0.tolist(), 'orientation':'free',
        'selection':'All 64 ordered candidates except geometric distance/duplicate exclusions; no planner, margin, solver or baseline outcomes consulted',
        'included_count':len(accepted),'candidate_count':64,'candidates':rows,
        'approval':None,'comparison_runs_executed':False,
        'freeze_status':'Target bytes fixed as a proposal before either method is run; NOT a signed experimental freeze'}
    output=ROOT/'protocol/scenario_b_target_suite_PROPOSED.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print('Proposed targets:',len(accepted),'of 64; SHA256:',hashlib.sha256(output.read_bytes()).hexdigest())


if __name__=='__main__':main()
