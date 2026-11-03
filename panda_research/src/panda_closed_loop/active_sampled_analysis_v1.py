"""Read-only sampled-data mathematics. NEVER an actuation/controller module.

Derivatives are local, smooth-face statements. Floating point evaluations
and stage samples are diagnostics, not interval bounds or safety proofs.
"""
import numpy as np
import casadi as ca
from panda_dynamics import PHI1, PHI2, PHI3


def face_expansion(A, b, r, dA, db, dr, active, dual_phys):
    """Differentiate the physical Euclidean KKT system on a regular face.

    A tau <= b, lambda in Nm for unit physical normals; strict
    complementarity and unchanged active set must be checked by caller.
    """
    A, b, r = np.asarray(A), np.asarray(b), np.asarray(r)
    dA, db, dr = np.asarray(dA), np.asarray(db), np.asarray(dr)
    n = r.size; active = np.asarray(active, dtype=int)
    if not all(np.all(np.isfinite(x)) for x in (A,b,r,dA,db,dr,dual_phys)):
        raise ValueError('Nonfinite smooth-face data')
    if not len(active):
        return {'sigma':r.copy(), 'dsigma':dr.copy(), 'tangent':np.eye(n),
                'normal_speed':np.zeros(0), 'missing_normal':np.zeros(n),
                'missing_rotation':np.zeros(n), 'AB2_defect':np.zeros(n),
                'feedback_AB2_defect':np.zeros(n), 'gram_condition':1.}
    a, da, beta, dbeta = A[active], dA[active], b[active], db[active]
    gram = a@a.T
    if np.linalg.matrix_rank(gram) != len(active): raise ValueError('LICQ fails')
    dagger = a.T@np.linalg.solve(gram, np.eye(len(active)))
    P = np.eye(n)-dagger@a
    sigma = r-dagger@(a@r-beta)
    lam = np.asarray(dual_phys)[active]
    w = dbeta-da@sigma
    rotation = -P@da.T@lam
    normal = dagger@w
    dsigma = P@dr+rotation+normal
    return {'sigma':sigma, 'dsigma':dsigma, 'tangent':P,
            'normal_speed':w, 'missing_normal':normal, 'missing_rotation':rotation,
            # Held-minus-continuous local state defect = Delta^2/2 B*AB2_defect.
            'AB2_defect':P@dr-dsigma,
            'feedback_AB2_defect':P@dsigma-dsigma,
            'gram_condition':float(np.linalg.cond(gram))}


def reference_jerk(reference, t):
    """One-sided jerk at a C2 join; caller must exclude joins from smooth fits."""
    k = min(np.searchsorted(reference.boundaries,t,side='right')-1,len(reference.coefficients)-1)
    a,b = reference.boundaries[k:k+2]; s=(t-a)/(b-a)
    c = reference.coefficients[k]
    coeff = (np.arange(3,6)*np.arange(2,5)*np.arange(1,4))[:,None]*c[3:]
    return np.polynomial.polynomial.polyval(s,coeff)/(b-a)**3


class SpeedMaterialDerivative:
    """AD r and 14 speed rows along a supplied material direction.

    These are exactly the active row families in the preserved E3. The mass
    inverse is an independent input with supplied exact identity derivative
    -N Mdot N; no symbolic inverse or altered dynamics is introduced.
    Manipulability/other rows remain checked by the original evaluator in the
    separate all-row stage audit; their smooth-face derivative is not claimed.
    """
    def __init__(self, system):
        Y = ca.SX.sym('analysis_Y',98); D = ca.SX.sym('analysis_direction',98)
        q,v,z=Y[:7],Y[7:14],Y[14:21]
        qr,vr,ar=Y[21:28],Y[28:35],Y[35:42]
        varpi=Y[42:49]; N=ca.reshape(Y[49:],7,7)
        M,flat,g,_,_=system.model._fun(q)
        dm=[ca.reshape(flat[:,k],7,7) for k in range(7)]
        C=ca.SX.zeros(7,7)
        for i in range(7):
            for j in range(7):
                C[i,j]=sum(.5*(dm[k][i,j]+dm[j][i,k]-dm[i][j,k])*v[k] for k in range(7))
        F=.5*ca.DM(PHI1)*(ca.tanh(.5*ca.DM(PHI2)*(v+ca.DM(PHI3)))-ca.tanh(.5*ca.DM(PHI2)*ca.DM(PHI3)))
        dhat=z+ca.DM(system.observer.gains)*(M@v)
        lam=ca.DM(system.controller.lambdas)
        e=qr-q; ev=vr-v; s=ev+lam*e
        r=M@(ar+lam*ev)+C@(vr+lam*e)+g+F+system.controller.kappa*(M@s)-dhat
        bias=dhat-C@v-g-F; margin=ca.fabs(N)@varpi
        G=ca.vertcat(-N,N)
        c=ca.vertcat(-N@bias+system.barriers.alpha_v*(ca.DM(system.barriers.vmax)-v)-margin,
                     N@bias+system.barriers.alpha_v*(ca.DM(system.barriers.vmax)+v)-margin)
        norm=ca.sqrt(ca.sum2(G*G)); A=-G/ca.repmat(norm,1,7)
        b=(c-1e-8*ca.DM(np.tile(system.barriers.vmax,2)))/norm
        vals=ca.vertcat(ca.vec(A),b,r)
        self.function=ca.Function('readonly_speed_material_v1',[Y,D],[A,b,r,ca.jtimes(vals,Y,D)],{'cse':True})
        self.system=system

    def evaluate(self, q,v,z,reference,jerk,varpi,dvarpi,sigma,disturbance):
        sys=self.system; e=sys.model.evaluate(q,v); N=np.linalg.solve(e['M'],np.eye(7))
        dM=np.einsum('ijk,k->ij',e['dM'],v); dN=-N@dM@N
        acc=N@(sigma+disturbance-e['C']@v-e['g']-e['F'])
        dz=sys.observer.derivative(q,v,z,sigma)
        Y=np.r_[q,v,z,reference.q,reference.qd,reference.qdd,varpi,N.flatten(order='F')]
        direction=np.r_[v,acc,dz,reference.qd,reference.qdd,jerk,dvarpi,dN.flatten(order='F')]
        A,b,r,deriv=self.function(Y,direction); deriv=np.asarray(deriv).reshape(-1)
        return {'A':np.asarray(A),'b':np.asarray(b).reshape(-1),'r':np.asarray(r).reshape(-1),
                'dA':deriv[:98].reshape((14,7),order='F'),'db':deriv[98:112],
                'dr':deriv[112:119], 'xdot':direction[:21]}


def reconstruct_electrical_energy(substeps, k_r, epsilon_W):
    """Independent shared-bus quadrature, using actual held tau at RK stages.

    Approved k_r combines electrical constants; individual currents cannot
    be inferred uniquely and are deliberately not invented.
    """
    E=[]; mechanical=[]; losses=[]; power=[]; max_hold=0.
    for step in substeps:
        tau=np.asarray(step['applied_tau']); samples=step['samples']
        v=np.asarray([s['qd'] for s in samples[:4]])
        for s in samples:
            max_hold=max(max_hold,float(np.max(abs(np.asarray(s['tau_applied'])-tau))))
        pm=v@tau; pl=float(np.sum(np.asarray(k_r)*tau*tau))
        bus=pm+pl; p=.5*(bus+np.hypot(bus,epsilon_W))
        h=step['physical_t1_s']-step['physical_t0_s']
        E.append(float(h*np.dot([1,2,2,1],p)/6))
        mechanical.append(pm); losses.append(pl); power.append(p)
    recorded=np.asarray([s['modeled_electrical_energy_increment_J'] for s in substeps])
    E=np.asarray(E)
    return {'increments':E,'mechanical_W':np.asarray(mechanical),'loss_W':np.asarray(losses),
            'power_W':np.asarray(power),'max_hold_mismatch_Nm':max_hold,
            'max_increment_difference_J':float(np.max(abs(E-recorded))) if len(E) else None,
            'sum_J':float(np.sum(E)),'sum_recorded_J':float(np.sum(recorded))}
