"""T28: raw target C versus Christoffel C from finite-differenced Pinocchio M."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import argparse
import json
import numpy as np
import pinocchio as pin
from case_sets import protocol_cases
from reference_model import build_reference_urdf
from panda_dynamics import PandaDynamics


def main(report):
    model=pin.buildModelFromUrdf(str(build_reference_urdf()));model.gravity.linear=np.array([0.,0.,-9.80665])
    data=model.createData();target=PandaDynamics();rows=[]
    def mass(q):
        m=pin.crba(model,data,q).copy()
        return np.triu(m)+np.triu(m,1).T
    for i,(q,v) in enumerate(zip(*protocol_cases()[:2])):
        out=target.evaluate(q,v)
        libC=pin.computeCoriolisMatrix(model,data,q,v).copy()
        lib_bias=pin.rnea(model,data,q,v,np.zeros(7)).copy()-pin.computeGeneralizedGravity(model,data,q).copy()
        for h in [1e-4,5e-5,2.5e-5]:
            D=np.stack([(-mass(q+2*h*e)+8*mass(q+h*e)-8*mass(q-h*e)+mass(q-2*h*e))/(12*h) for e in np.eye(7)],axis=2)
            C=.5*(np.einsum('ijk,k->ij',D,v)+np.einsum('ikj,k->ij',D,v)-np.einsum('jki,k->ij',D,v))
            mdot=np.einsum('ijk,k->ij',D,v)
            errors={'raw_C':float(np.max(abs(out['C']-C))),
                    'Mdot_minus_target_C_CT':float(np.max(abs(mdot-out['C']-out['C'].T))),
                    'Cqd_vs_Pinocchio_RNEA':float(np.max(abs(out['C']@v-lib_bias))),
                    'Pinocchio_library_raw_C_difference_diagnostic_only':float(np.max(abs(out['C']-libC)))}
            passed=bool(np.all(abs(out['C']-C)<=5e-8+1e-9*abs(C)) and errors['Mdot_minus_target_C_CT']<=5e-8 and errors['Cqd_vs_Pinocchio_RNEA']<=1e-8)
            rows.append({'case':i,'fd_step_rad':h,'errors':errors,'passed':passed,
                         'target_C':out['C'].tolist(),'independent_Christoffel_C':C.tolist()})
    result={'overall_pass':all(r['passed'] for r in rows),'scope':'T28 ORDINARY NUMERICAL CONVENTION CHECK, not global/certified',
            'reference':'5-point central differences of source-built Pinocchio CRBA mass matrix; Christoffel tensor contracted with qd',
            'independence':'Reference uses no target transforms, M, U, dM or CasADi derivatives',
            'case_count':22,'steps_rad':[1e-4,5e-5,2.5e-5],'raw_C_abs_tolerance':5e-8,'raw_C_relative_tolerance':1e-9,
            'limitations':'FD truncation/rounding, 22 states only. Pinocchio raw C is diagnostic, not assumed Christoffel. Cqd agreement alone never proves raw-C convention.',
            'per_case':rows}
    report.write_text(json.dumps(result,indent=2)+'\n')
    print('T28', 'PASS' if result['overall_pass'] else 'FAIL',len(rows),'pose/step comparisons')
    if not result['overall_pass']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);main(parser.parse_args().report)
