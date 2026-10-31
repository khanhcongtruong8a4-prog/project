"""Negative controls: external checks must detect physical-model mutations."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import numpy as np
import pinocchio as pin
from compare_external_dynamics import sample_cases
from reference_model import build_reference_urdf
from panda_dynamics import PandaDynamics

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=build_reference_urdf().read_text()
    q,qd,qdd=sample_cases()
    q,qd,qdd=q[1],qd[1],qdd[1]
    target=PandaDynamics().evaluate(q,qd,qdd)
    results=[]
    for mutation in ['mass_link2','COM_link2','inertia_sign_link2','joint3_origin','gravity_sign']:
        tree=ET.fromstring(source)
        if mutation=='mass_link2':
            e=tree.find("link[@name='panda_link2']/inertial/mass");e.set('value',str(float(e.get('value'))*1.1))
        elif mutation=='COM_link2':
            e=tree.find("link[@name='panda_link2']/inertial/origin")
            v=list(map(float,e.get('xyz').split()));v[2]+=.01;e.set('xyz',' '.join(map(str,v)))
        elif mutation=='inertia_sign_link2':
            e=tree.find("link[@name='panda_link2']/inertial/inertia");e.set('ixy',str(-float(e.get('ixy'))))
        elif mutation=='joint3_origin':
            e=tree.find("joint[@name='panda_joint3']/origin")
            v=list(map(float,e.get('xyz').split()));v[1]+=.001;e.set('xyz',' '.join(map(str,v)))
        model=pin.buildModelFromXML(ET.tostring(tree,encoding='unicode'))
        model.gravity.linear=np.array([0.,0.,9.80665 if mutation=='gravity_sign' else -9.80665])
        value=pin.rnea(model,model.createData(),q,qd,qdd).copy()
        expected=target['ID']-target['F']
        error=float(np.max(np.abs(expected-value)))
        detected=bool(np.any(np.abs(expected-value)>1e-8+1e-9*np.abs(value)))
        results.append({'mutation':mutation,'max_ID_difference_Nm':error,
                        'detected':detected,'result':'PASS_DETECTED' if detected else 'FAIL_NOT_DETECTED'})
    report={'purpose':'Deliberate isolated corruptions; NOT alternative physical models or experiment results',
            'controls':results,'overall_pass':all(r['detected'] for r in results)}
    (ROOT/'reports/reference_sensitivity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['overall_pass']:raise SystemExit(1)


if __name__=='__main__':main()
