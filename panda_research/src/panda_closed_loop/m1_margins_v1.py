"""Full source-equation development margins, including nonzero rho_r(0).

Integrating an envelope with sampled coefficient estimates does NOT certify
it. All outputs keep that evidence scope; no official planner is called.
"""
from fractions import Fraction as F
import numpy as np
from scipy.integrate import solve_ivp
from .a2_acceptance import fraction_solve
from .m1_common_domain_v1 import rational
from .observer import ObserverEnvelope
from .stage1_scaffold import PlanningMargins
from .feasibility import duration_for_pairs


class DevelopmentMarginProvider:
    def __init__(self,registry,system,varpi0,dhat0,horizon):
        self.registry=registry;self.b=registry.for_development();self.system=system
        self.varpi0=np.array(varpi0);self.dhat0=np.array(dhat0);self.horizon=float(horizon)
        self.lam=np.array(system.policy.lambdas);self.ko=np.array(system.policy.ko);self.kappa=system.policy.kappa
        self.envelope=ObserverEnvelope(self.ko,self.varpi0,system.bounds.rate)
        self.sqrtm=np.sqrt(self.b['mbar_i'])
        initial=np.r_[0.,np.zeros(7),self.varpi0] # rho_r(0)=varpi0, never zero
        self.integration=solve_ivp(self._derivative,[0.,horizon],initial,method='DOP853',rtol=1e-10,atol=1e-12,dense_output=True)
        if not self.integration.success:raise RuntimeError('Development envelope integration failed')
    def _derivative(self,t,x):
        vp=self.envelope.value(t)
        nu=min(float(np.linalg.norm(vp)/np.sqrt(self.b['m1'])),float(np.sqrt(vp@self.b['Nbar_Q_il']@vp)))
        chis=self.sqrtm*x[0]
        return np.r_[nu-self.kappa*x[0],chis-self.lam*x[1:8],
            -self.kappa*x[8:]+self.kappa*self.b['Cbar_li'].T@chis+self.ko*vp+self.system.bounds.rate]
    def details(self,t):
        if not 0<=t<=self.horizon:raise ValueError('Outside envelope horizon')
        y=self.integration.sol(t);vp=self.envelope.value(t);chis=self.sqrtm*y[0];chie=y[1:8];chiv=chis+self.lam*chie;rho=y[8:]
        # Eliminate only solver roundoff on components whose defining integral
        # is nonnegative. A negative beyond numerical resolution is an error.
        if min(float(y[0]),float(np.min(chie)),float(np.min(rho))) < -1e-12:raise ValueError('Negative integrated envelope')
        chis=np.maximum(chis,0.);chie=np.maximum(chie,0.);chiv=np.maximum(chiv,0.);rho=np.maximum(rho,0.)
        b=self.b
        betau=b['L_u_q']@chie+(b['L_u_qd']+b['L_u_qdd']*self.lam[None,:])@chiv+b['Cbar_li']@chis
        betah=b['L_h_q']@chie+(b['L_h_qd']+b['L_h_qdd']*self.lam[None,:])@chiv
        eta=self.varpi0+self.system.bounds.rate*t;zplus=np.minimum(eta,np.maximum(0.,self.system.bounds.magnitude+self.dhat0))
        zminus=np.minimum(eta,np.maximum(0.,self.system.bounds.magnitude-self.dhat0))
        buplus=betau+rho+zplus;buminus=betau+rho+zminus
        bh=betah+b['Dbar_jl']@chis+b['Abar_jl']@rho+2*b['Abar_jl']@vp
        bv=abs(self.system.policy.alpha_v-self.lam)*chiv+b['Bbar_il']@chis+b['Nbar_il']@rho+2*b['Nbar_il']@vp
        return {'varpi':vp,'yb':float(y[0]),'chi_s':chis,'chi_e':chie,'chi_v':chiv,'rho_r':rho,
                'beta_u':betau,'beta_h':betah,'zeta_plus':zplus,'zeta_minus':zminus,
                'b_u_plus':buplus,'b_u_minus':buminus,'b_h':bh,'b_vB':bv,
                'bound_evidence':'DEVELOPMENT_SAMPLED_COEFFICIENTS_NOT_CERTIFIED_ENVELOPE'}
    def at(self,t):
        d=self.details(t)
        return PlanningMargins(d['b_u_plus'],d['b_u_minus'],d['chi_v'],d['b_h'],d['b_vB'],
            'M1_LEVEL_2_SUPPLIED_NOT_VALIDATED_HERE',self.registry.document['domain_sha256'],self.registry.document['registry_provenance_sha256'])
    def residual_lipschitz_estimates(self):
        """Finite family-wise estimates with source equations and fixed domain.

        These use sampled derivative tables, so L*gap/2 cannot certify the
        continuous inequalities. Values are never labeled verified bounds.
        """
        b=self.b;vp=self.varpi0;nu=min(float(np.linalg.norm(vp)/np.sqrt(b['m1'])),float(np.sqrt(vp@b['Nbar_Q_il']@vp)))
        ymax=nu/self.kappa;cs=self.sqrtm*ymax;ce=cs/self.lam;cv=cs+self.lam*ce
        Lcs=2*self.sqrtm*nu;Lce=cs+self.lam*ce;Lcv=Lcs+self.lam*Lce
        forcing=self.kappa*b['Cbar_li'].T@cs+self.ko*vp+self.system.bounds.rate
        rmax=np.maximum(vp,forcing/self.kappa);Lrho=self.kappa*rmax+forcing
        Lvp=self.ko*abs(vp-self.system.bounds.rate/self.ko)
        Lbu=b['L_u_q']@Lce+(b['L_u_qd']+b['L_u_qdd']*self.lam[None,:])@Lcv+b['Cbar_li']@Lcs+Lrho+self.system.bounds.rate
        Lbh=b['L_h_q']@Lce+(b['L_h_qd']+b['L_h_qdd']*self.lam[None,:])@Lcv+b['Dbar_jl']@Lcs+b['Abar_jl']@Lrho+2*b['Abar_jl']@Lvp
        Lbv=abs(self.system.policy.alpha_v-self.lam)*Lcv+b['Bbar_il']@Lcs+b['Nbar_il']@Lrho+2*b['Nbar_il']@Lvp
        domain=self.registry.document['domain'];acc=np.array(domain['Markov_ap_upper']);jerk=np.array(domain['Markov_jerk_upper']);speed=self.system.barriers.vmax
        LID=b['L_u_q']@speed+b['L_u_qd']@acc+b['L_u_qdd']@jerk
        LH=b['L_h_q']@speed+b['L_h_qd']@acc+b['L_h_qdd']@jerk
        # H_a equals grad h; thus its sampled bound is also the h derivative table.
        return {'torque_upper':LID+Lbu,'torque_lower':LID+Lbu,'speed_upper':acc+Lcv,'speed_lower':acc+Lcv,
                'hocbf':LH+Lbh,'velocity_cbf_upper':jerk+self.system.policy.alpha_v*acc+Lbv,
                'velocity_cbf_lower':jerk+self.system.policy.alpha_v*acc+Lbv,'physical_position_and_manip_h':b['L_h_qdd']@speed}


def exact_initial_pair_obstruction(system,record):
    """Exact Farkas pairs for the represented current mass matrix only."""
    M=system.model.evaluate(record['q'],record['qd'])['M'];A=[[rational(x) for x in row] for row in M]
    columns=[fraction_solve(A,[F(int(i==j)) for i in range(7)]) for j in range(7)]
    N=[[columns[j][i] for j in range(7)] for i in range(7)]
    vp=[rational(x) for x in record['varpi']];av=rational(system.policy.alpha_v)
    reserve=system.barriers.planner_reserves(system.policy)['velocity_CBF_rad_s2'];delta=rational(reserve)
    rows=[]
    for i in range(7):
        lower=3*sum(abs(N[i][j])*vp[j] for j in range(7))+delta
        rhs=av*rational(system.barriers.vmax[i]);slack=rhs-lower
        rows.append({'joint':i+1,'three_varpi_plus_reserve_lower':float(lower),'speed_pair_rhs':float(rhs),
            'necessary_slack':float(slack),'exact_necessary_slack':str(slack),'failed_exactly':slack<0,
            'Farkas_upper_lower_weights':['1/2','1/2'],'acceleration_coefficients_cancel_exactly':True})
    absN=np.array([[float(abs(x)) for x in row] for row in N])
    threshold=duration_for_pairs((3*absN@system.bounds.magnitude)[None,:],
        system.policy.alpha_v*system.barriers.vmax-reserve,system.bounds.magnitude,system.bounds.rate,system.policy.ko,.001)
    return {'status':'NO_GO_NECESSARY_START_PAIRS' if any(r['failed_exactly'] for r in rows) else 'PASS_NECESSARY_ONLY',
        'rows':rows,'represented_M':M.tolist(),'exact_inverse_M':[[str(x) for x in row] for row in N],
        'factor_two_term_retained':True,'additional_term':'Nbar*rho_r(0), rho_r(0)=varpi0; total at least 3*abs(N)*varpi0',
        'scope':'EXACT_RATIONAL_CERTIFICATE_FOR_REPRESENTED_BINARY64_M_AND_INPUTS_NOT_NONLINEAR_MODEL_LEVEL1',
        'logical_consequence':'Any containing valid Nbar and the unchanged matched-start margins fail these paired speed inequalities. Torque/manipulability/additional margins cannot repair a failed necessary pair.',
        'preparation_duration_necessary_fixed_pose_only':threshold,
        'duration_is_not_applied_or_sufficient_for_G2_5':True,'torque_actuated':False}
