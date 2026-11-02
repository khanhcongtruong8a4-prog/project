"""Equation-traced development M1 registry, estimates and analytic lemmas.

No sampled extremum is a certified domain upper bound. No planner solve or
actuation is authorized by this module. The ideal-model inertia lemma does
not certify floating-point model evaluation, the full bound suite or Level 1.
"""
from fractions import Fraction as F
from types import MappingProxyType
import hashlib,json
import numpy as np
import casadi as ca
from .a2_acceptance import fraction_solve
from .contracts import vector
from panda_dynamics import INERTIA6,inertia_tensor,ALPHA_DH,rot_x,QMIN,QMAX,VMAX,PHI1,PHI2,PHI3

SHAPES={'m1':(),'mbar_i':(7,),'Nbar_Q_il':(7,7),'Cbar_li':(7,7),'Abar_jl':(15,7),
        'Nbar_il':(7,7),'Bbar_il':(7,7),'Dbar_jl':(15,7),
        'L_u_q':(7,7),'L_u_qd':(7,7),'L_u_qdd':(7,7),
        'L_h_q':(15,7),'L_h_qd':(15,7),'L_h_qdd':(15,7)}
UNITS={'m1':'kg m^2','mbar_i':'(kg m^2)^-1','Nbar_Q_il':'(kg m^2)^-1',
       'Cbar_li':'N m s/rad','Abar_jl':'h_j/(N m s^2)','Nbar_il':'rad/(N m s^2)',
       'Bbar_il':'s^-1','Dbar_jl':'h_j/(rad s)',
       'L_u_q':'(N m)/(rad)','L_u_qd':'(N m)/(rad/s)','L_u_qdd':'(N m)/(rad/s^2)',
       'L_h_q':'(h_j/s^2)/(rad)','L_h_qd':'(h_j/s^2)/(rad/s)','L_h_qdd':'(h_j/s^2)/(rad/s^2)'}

def rational(x):return F.from_float(float(x))
def canonical_sha(d):return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def inertia_lower_lemma():
    """M >= min_i[1/trace(I_i^-1)]/4 * I for the selected ideal model.

    omega_i=sum_{j<=i}axis_j*v_j. Since every fixed Rx is noncontracting,
    |v_i| <= |omega_i-omega_{i-1}| and sum v_i^2 <= 4 sum |omega_i|^2.
    I_i >= 1/trace(I_i^-1) I; positive translational energy can be discarded.
    All inertia and fixed-Rx checks below use exact represented rationals.
    """
    bodies=[];bounds=[]
    for i,six in enumerate(INERTIA6):
        A=[[rational(x) for x in row] for row in inertia_tensor(six)]
        d1=A[0][0];d2=A[0][0]*A[1][1]-A[0][1]*A[1][0]
        d3=(A[0][0]*(A[1][1]*A[2][2]-A[1][2]*A[2][1])
            -A[0][1]*(A[1][0]*A[2][2]-A[1][2]*A[2][0])+A[0][2]*(A[1][0]*A[2][1]-A[1][1]*A[2][0]))
        if not all(x>0 for x in [d1,d2,d3]):raise ValueError('Inertia is not exactly SPD')
        columns=[fraction_solve(A,[F(int(j==k)) for j in range(3)]) for k in range(3)]
        gamma=1/sum(columns[i][i] for i in range(3));bounds.append(gamma)
        R=[[rational(x) for x in row] for row in rot_x(ALPHA_DH[i])]
        gram=[[sum(R[k][a]*R[k][b] for k in range(3)) for b in range(3)] for a in range(3)]
        if not all(gram[a][b]==0 for a in range(3) for b in range(3) if a!=b):raise ValueError('Unexpected fixed Rx Gram')
        if min(gram[k][k] for k in range(3))<1:raise ValueError('Noncontracting fixed-axis hypothesis not proved')
        bodies.append({'body':i+1,'exact_leading_principal_minors':[str(x) for x in [d1,d2,d3]],
                       'exact_inverse_trace_lower_bound':str(gamma),'fixed_Rx_Gram_diagonal':[str(gram[k][k]) for k in range(3)]})
    bound=min(bounds)/4;value=float(np.nextafter(float(bound),-np.inf))
    return {'m1_lower':value,'exact_lower_bound':str(bound),'bodies':bodies,
            'scope':'ANALYTIC_SELECTED_IDEAL_MODEL_LEMMA_NOT_FLOAT_EVALUATOR_OR_FULL_LEVEL1_CERTIFICATION',
            'sampled_eigenvalue_minimum_used_as_lower_bound':False}

def common_domain(policy):
    """A fixed periodic coefficient cover, with feasible-planner K bounds.

    The coefficient targets are periodic in q; joint H derivatives are constant.
    Safety constraints ALWAYS use unwrapped QMIN/QMAX. No trajectory is wrapped.
    Markov's polynomial inequalities bound a and jerk on every quintic span of
    a trajectory satisfying the original position limits and Tmin. The K box
    adds Lambda*vmax, because tightened speed feasibility implies chi_v<=vmax.
    """
    knots=[rational(x) for x in policy.raw['solver']['NLP_quintic_knots_normalized']]
    span=min(b-a for a,b in zip(knots[:-1],knots[1:]) if b>a)
    T=rational(policy.raw['energy']['T_min_s']);width=[rational(b)-rational(a) for a,b in zip(QMIN,QMAX)]
    up=lambda x:float(np.nextafter(float(x),np.inf))
    acceleration=np.array([up(400*w/(T*span)**2) for w in width])
    jerk=np.array([up(3360*w/(T*span)**3) for w in width])
    augmented=acceleration+np.asarray(policy.lambdas)*VMAX
    augmented=np.nextafter(augmented,np.inf)
    return {'version':'M1_FIXED_PERIODIC_COEFFICIENT_DOMAIN_V1','q_phase_lower':[-4.]*7,'q_phase_upper':[4.]*7,
        'v_lower':(-VMAX).tolist(),'v_upper':VMAX.tolist(),'a_lower':(-augmented).tolist(),'a_upper':augmented.tolist(),
        'physical_q_lower_unchanged':QMIN.tolist(),'physical_q_upper_unchanged':QMAX.tolist(),
        'physical_safety_constraints_never_wrap_q':True,'position_extension_rad_retained':.01,
        'periodic_cover':'The phase box [-4,4]^7 contains [-pi,pi]^7. All 14 coefficient targets are 2pi-periodic in q or constant (joint H derivatives). This bounds coefficient functions; it changes no physical joint limit.',
        'conditional_T_and_K_coverage':'Any feasible tightened plan has |vp|+chi_v+delta_v<=vmax, hence its T velocities are physical and chi_v<=vmax. Markov bounds on every degree-five span plus Lambda*vmax cover qr_ddot in K. A failing tightened-speed screen never establishes coverage or planner feasibility.',
        'Markov_ap_upper':acceleration.tolist(),'Markov_jerk_upper':jerk.tolist(),'Tmin_unchanged':float(T),'exact_min_knot_span':str(span),
        'Markov_derivation':'On [-1,1], ||p2||<=200||p|| and ||p3||<=840||p|| for degree5. Rescale a span and center q: ap<=400*width/L^2; jerk<=3360*width/L^3.',
        'sampler':'Sobol 21D scrambled, source-fixed before sampling','seed':20271102,'Sobol_training_power':9,'Sobol_holdout_power':8,
        'training_anchors':'Four previously measured v4 C4 starts and original physical midpoint, each a=0; included before tests, not chosen for success.'}

class CommonCoefficientEvaluator:
    def __init__(self,system):
        q=ca.SX.sym('m1q',7);v=ca.SX.sym('m1v',7);a=ca.SX.sym('m1a',7)
        M,flat,g,_,_=system.model._fun(q);C=ca.SX.zeros(7,7)
        for i in range(7):
            for j in range(7):C[i,j]=sum(.5*(flat[i+7*j,k]+flat[i+7*k,j]-flat[j+7*k,i])*v[k] for k in range(7))
        _,_,W,gradient,hessian=system.geometry.function(q)
        h=ca.vertcat(ca.DM(QMAX)-q,q-ca.DM(QMIN),W-system.barriers.w_min**2)
        grad=ca.vertcat(-ca.SX.eye(7),ca.SX.eye(7),gradient.T)
        curvature=ca.vertcat(ca.SX.zeros(14,1),ca.mtimes([v.T,hessian,v]))
        H=grad@a+curvature+(system.policy.alpha1+system.policy.alpha2)*(grad@v)+system.policy.alpha1*system.policy.alpha2*h
        friction=.5*ca.DM(PHI1)*(ca.tanh(.5*ca.DM(PHI2)*(v+ca.DM(PHI3)))-ca.tanh(.5*ca.DM(PHI2)*ca.DM(PHI3)))
        ID=M@a+C@v+g+friction
        self.function=ca.Function('m1_source_coefficients_v1',[q,v,a],[M,C,grad,
            ca.jacobian(ID,q),ca.jacobian(ID,v),ca.jacobian(ID,a),
            ca.jacobian(H,q),ca.jacobian(H,v),ca.jacobian(H,a)],{'cse':True})
    def at(self,q,v,a):
        M,C,G,*derivatives=[np.array(x,dtype=float) for x in self.function(q,v,a)]
        N=np.linalg.solve(M,np.eye(7));A=G@N
        out={'mbar_i':np.diag(N),'Nbar_Q_il':abs(N),'Cbar_li':abs(C),'Abar_jl':abs(A),
             'Nbar_il':abs(N),'Bbar_il':abs(N@C),'Dbar_jl':abs(A@C)}
        for name,value in zip(['L_u_q','L_u_qd','L_u_qdd','L_h_q','L_h_qd','L_h_qdd'],derivatives):out[name]=abs(value)
        return out,float(np.linalg.eigvalsh(M)[0])

class NumericalM1Registry:
    def __init__(self,document):
        if canonical_sha(document['domain'])!=document['domain_sha256']:raise ValueError('M1 common-domain checksum differs')
        self._document=json.dumps(document);values={}
        for name,shape in SHAPES.items():
            e=document['entries'][name];value=np.asarray(e['value'],dtype=float)
            if value.shape!=shape or e['units']!=UNITS[name] or np.any(~np.isfinite(value)) or np.any(value<0):raise ValueError('Invalid M1 entry '+name)
            if name=='m1' and value<=0:raise ValueError('Positive m1 required')
            value=value.copy();value.setflags(write=False);values[name]=value
        self.values=MappingProxyType(values)
    @property
    def document(self):return json.loads(self._document)
    def for_development(self):return {k:v.copy() for k,v in self.values.items()}
    def require_certified(self):
        raise ValueError('NO-GO: sampled upper extrema and the full floating/model/continuous-time enclosure suite are not certified')
