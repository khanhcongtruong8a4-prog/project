"""Phase-3a MODEL-ONLY floating-point checks. No verified intervals, no QP/planner."""
from __future__ import annotations
import json,sys,platform,traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import scipy, casadi
from panda_dynamics import (PandaDynamics,MASS,COM,INERTIA6,QMIN,QMAX,N,
                            rot_x,mdh_fk_numpy,urdf_fk_numpy,inertia_tensor,
                            friction,PHI1,PHI2,PHI3,dual_harmonic_disturbance,
                            disturbance_bounds,TAUMAX)

SEED=20261101
RNG=np.random.default_rng(SEED)
Q_CASES=[np.zeros(N),(QMIN+QMAX)/2]
Q_CASES.extend(QMIN+.05*(QMAX-QMIN)+RNG.random((20,N))*.9*(QMAX-QMIN))
QD_CASES=RNG.normal(0,.35,(len(Q_CASES),N))
QDD_CASES=RNG.normal(0,.4,(len(Q_CASES),N))
RECORD=[]

def add(name,measured,threshold,note=''):
    measured=float(measured)
    ok=bool(np.isfinite(measured) and measured<=threshold)
    RECORD.append({'test':name,'result':'PASS' if ok else 'FAIL',
                   'measured_max':measured,'pass_threshold':float(threshold),'notes':note})
    return ok


def run():
    model=PandaDynamics()
    add('T04b author-code c1z convention',abs(COM[0,2]),0,
        'Compared with Gaz pinned MATLAB DynPars2VREP.m (the source table prints asterisk, not measured zero).')
    add('T04b author-code joint2 phi1',abs(PHI1[1]-.87224),0,
        'Compared with pinned get_FrictionTorque.m, not rounded from incorrect alternate sources.')
    add('T04b body inertia SPD',max(0,-min(np.linalg.eigvalsh(inertia_tensor(a))[0] for a in INERTIA6)),0,
        'Floating point per-body physical plausibility only; NOT a global m1 certificate.')
    triangles=[]
    for a in INERTIA6:
        w=np.linalg.eigvalsh(inertia_tensor(a))
        triangles.append((w[0]+w[1]-w[2]))
    add('T04b positive principal triangle slack',max(0,-min(triangles)),0,
        f'Minimum floating point slack: {min(triangles):.10g} kg m^2.')
    fk_pos=[];fk_ori=[];ad_fk=[];sym=[];small_eig=[];skew=[];grav=[];hfd=[];q1=[];energy=[];kinetic=[]
    eps=2e-5
    for j,(q,qd,qdd) in enumerate(zip(Q_CASES,QD_CASES,QDD_CASES)):
        gp,gf=mdh_fk_numpy(q);up,uf=urdf_fk_numpy(q)
        for (Rg,pg),(Ru,pu) in zip(gp,up):
            fk_pos.append(np.max(np.abs(pg-pu)));fk_ori.append(np.max(np.abs(Rg-Ru)))
        fk_pos.append(np.max(np.abs(gf[1]-uf[1])));fk_ori.append(np.max(np.abs(gf[0]-uf[0])))
        x=model.evaluate(q,qd,qdd)
        ad_fk.append(np.max(np.abs(x['flange']-gf[1])))
        M=x['M'];dm=x['dM'];C=x['C']
        sym.append(np.max(np.abs(M-M.T)))
        small_eig.append(np.linalg.eigvalsh(M)[0])
        Mdot=np.einsum('ijk,k->ij',dm,qd)
        skew.append(np.max(np.abs(Mdot-C-C.T)))
        energy.append(abs(qd@(Mdot-2*C)@qd))
        g_fd=np.array([(model.evaluate(q+np.eye(N)[k]*eps)['U']-model.evaluate(q-np.eye(N)[k]*eps)['U'])/(2*eps) for k in range(N)])
        grav.append(np.max(np.abs(x['g']-g_fd)))
        deriv_fd=np.empty((N,N,N))
        for k in range(N):
            step=np.eye(N)[k]*eps
            deriv_fd[:,:,k]=(model.evaluate(q+step)['M']-model.evaluate(q-step)['M'])/(2*eps)
        h_i=np.einsum('ijk,j,k->i',deriv_fd,qd,qd)-.5*np.einsum('jki,j,k->i',deriv_fd,qd,qd)
        hfd.append(np.max(np.abs(C@qd-h_i)))
        # For fixed-base serial chain, kinetic M is independent of first coordinate.
        qp=q.copy();qp[0]+=0.371
        q1.append(np.max(np.abs(M-model.evaluate(qp)['M'])))
        power=qd@(M@qdd+C@qd+x['g'])
        deriv_e=qd@M@qdd+.5*qd@Mdot@qd+qd@x['g']
        kinetic.append(abs(power-deriv_e))
    add('T06a MDH vs pinned-URDF link and flange positions',max(fk_pos),1e-12,
        '22 poses, independently implemented NumPy kinematic products; conventions and model-level identity only.')
    add('T06a MDH vs pinned-URDF rotations',max(fk_ori),1e-12,
        '22 poses; no hand/tool fixed transform added.')
    add('T06a CasADi AD flange FK vs NumPy MDH',max(ad_fk),1e-11)
    add('Phase3a M symmetric',max(sym),5e-12)
    add('Phase3a M positive definite on 22 checked poses',max(0,-min(small_eig)),0,
        f'Sampled min eigenvalue {min(small_eig):.10g} kg m^2; NOT a rigorous global bound.')
    add('Phase3a Mdot - C - CT zero',max(skew),3e-10,
        'Christoffel C constructed from CasADi auto-differentiated M.')
    add('Phase3a mechanical skew power identity',max(energy),1e-10)
    add('Phase3a gravity equals numeric potential gradient',max(grav),5e-8)
    add('Phase3a Cqdot vs independently finite-differenced Lagrange form',max(hfd),5e-8)
    add('Phase3a q1 independence of M (sampled)',max(q1),1e-10)
    add('Phase3a inverse-dynamics power consistency',max(kinetic),1e-10)
    add('Phase3a F(0)=0',np.max(np.abs(friction(np.zeros(N)))),1e-15)
    vv=np.linspace(-2,2,101)[:,None]*np.ones((1,N))
    fp=friction(vv)
    add('Phase3a friction dissipation on velocity grid',max(0,float(-np.min(vv*fp))),0)
    # Bounds are triangle inequalities, do NOT claim they are attained exact maxima.
    times=np.linspace(0,30,2001)
    dbar,ratebar=disturbance_bounds()
    err_mag=max(float(np.max(np.abs(dual_harmonic_disturbance(t))-dbar)) for t in times)
    phi=2*np.pi*np.arange(N)/N
    err_rate=max(float(np.max(np.abs(.02*TAUMAX*(.6*np.cos(t+phi)-.8*np.sin(2*t+phi)))-ratebar)) for t in times)
    add('T12 dual-harmonic magnitude bound (sampled check)',max(0,err_mag),1e-12,
        'Analytical dbar = a; numerical sampling is only corroboration.')
    add('T12 dual-harmonic derivative bound (sampled check)',max(0,err_rate),1e-12,
        'Analytical dbar1 = 1.4a; sampled test not proof by itself.')
    passed=all(z['result']=='PASS' for z in RECORD)
    return {
      'run_utc':datetime.now(timezone.utc).isoformat(),
      'model':'Gaz author-code COM, MDH seven-body Panda without rotor/payload',
      'scope':'ordinary numerical Phase-3a internal tests only',
      'seed':SEED,'pose_count':len(Q_CASES),
      'status':'PASS_INTERNAL_NUMERICAL_TESTS' if passed else 'FAILED_INTERNAL_NUMERICAL_TESTS',
      'overall_pass':passed,
      'min_sampled_joint_inertia_eigenvalue':min(small_eig),
      'max_sampled_joint_inertia_eigenvalue':None,
      'independent_pinocchio_validation':'NOT_RUN: pinocchio unavailable; independent library ID remains pending',
      'interval_certification':'NOT_RUN',
      'closed_loop_simulation':'NOT_RUN',
      'environment':{'python':platform.python_version(),'numpy':np.__version__,
                     'scipy':scipy.__version__,'casadi':casadi.__version__},
      'checks':RECORD}


if __name__=='__main__':
    out=run()
    outpath=Path(__file__).parent/'phase3a_test_report.json'
    outpath.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for r in out['checks']:
        print(f"{r['result']:4} | {r['test']:<65} | {r['measured_max']:.5g} <= {r['pass_threshold']:.5g}")
    print('OVERALL:',out['status'],'RESULT FILE:',outpath)
    if not out['overall_pass']: sys.exit(1)
