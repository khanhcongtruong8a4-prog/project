"""Signed-clock, applied-torque preparation for DEVELOPMENT simulation only.

This module cannot authorize A2. A numerical hold failure is retained and
cannot be bypassed to obtain a zero-time endpoint or a motion reference.
"""
from dataclasses import dataclass
import numpy as np
from .contracts import vector,scalar
from .observer import ObserverEnvelope
from .reference import ReferenceSample
from .qp import project_torque_box
from .stepper import ExecutionState,HoldSchedule


@dataclass(frozen=True)
class SignedClock:
    observer_epoch: float

    def __post_init__(self):
        object.__setattr__(self,'observer_epoch',scalar(self.observer_epoch,'signed observer epoch s'))

    def elapsed(self,physical_t):
        elapsed=scalar(physical_t,'signed physical time s')-self.observer_epoch
        if elapsed<0:raise ValueError('Physical time precedes observer initialization')
        return elapsed


class SignedObserverEnvelope:
    """Translate only the envelope's elapsed argument, never the plant clock."""
    def __init__(self,clock,gains,initial,rate):
        self.clock=clock
        self.elapsed_envelope=ObserverEnvelope(gains,initial,rate,t0=0.)

    def value(self,physical_t):
        return self.elapsed_envelope.value(self.clock.elapsed(physical_t))


@dataclass(frozen=True)
class PreparationState:
    q: np.ndarray
    qd: np.ndarray
    z: np.ndarray
    t: float

    def __post_init__(self):
        for name in ['q','qd','z']:
            a=vector(getattr(self,name),name);a.setflags(write=False)
            object.__setattr__(self,name,a)
        object.__setattr__(self,'t',scalar(self.t,'signed physical time s'))

    def record(self):return {'q':self.q,'qd':self.qd,'z':self.z,'physical_t_s':self.t}


def rk4_extension_coefficients(x0,h,stages):
    """Standard cubic RK4 continuous extension, not a verified ODE enclosure."""
    x=np.asarray(x0,dtype=float);k=np.asarray(stages,dtype=float)
    if x.ndim!=1 or k.shape!=(4,len(x)) or not np.all(np.isfinite(k)) or not np.all(np.isfinite(x)):
        raise ValueError('Invalid finite RK4 state/stages')
    h=scalar(h,'RK4 step',positive=True)
    return np.stack([x,h*k[0],h*(-1.5*k[0]+k[1]+k[2]-.5*k[3]),
                     h*(2/3)*(k[0]-k[1]-k[2]+k[3])])


def component_extrema(coefficients):
    """All real stationary points plus endpoints of each cubic component."""
    c=np.asarray(coefficients,dtype=float)
    if c.ndim!=2 or c.shape[0]!=4 or not np.all(np.isfinite(c)):raise ValueError('Expected finite cubic coefficients')
    lo=[];hi=[];where=[]
    for j in range(c.shape[1]):
        derivative=np.array([3*c[3,j],2*c[2,j],c[1,j]])
        roots=np.roots(np.trim_zeros(derivative,'f')) if np.any(derivative) else []
        theta=[0.,1.]+[float(r.real) for r in roots if abs(r.imag)<1e-12 and 0<r.real<1]
        values=np.polynomial.polynomial.polyval(theta,c[:,j])
        lo.append(float(np.min(values)));hi.append(float(np.max(values)));where.append(theta)
    return {'minimum':np.array(lo),'maximum':np.array(hi),'checked_theta':where,
            'scope':'NUMERICAL_CUBIC_INTERPOLANT_ONLY_NOT_VERIFIED_TRUE_ODE_BOUND'}


@dataclass
class PreholdResult:
    state: PreparationState
    completed: bool
    decision: str
    trace: list
    failure: dict | None
    last_applied_torque: np.ndarray | None

    def measured_state_at_zero(self):
        if not self.completed or self.decision!='PASS_NUMERICAL_HOLD_ONLY' or self.state.t!=0.:
            raise ValueError('No valid zero-time preparation endpoint')
        # Preserve measured q,qd,z byte-for-byte, with no observer reinitialization.
        return ExecutionState(self.state.q,self.state.qd,self.state.z,self.state.t)


class AppliedTorquePrehold:
    """Unchanged tracking law + preparation-only torque projection; no clamp/QP."""
    def __init__(self,system,schedule,T_pre,q_mid,q_radius,qd_radius,plant_disturbance):
        if not isinstance(schedule,HoldSchedule):raise ValueError('Expected HoldSchedule')
        self.system,self.schedule=system,schedule
        self.T_pre=scalar(T_pre,'T_pre',positive=True)
        if abs(self.T_pre/schedule.delta-round(self.T_pre/schedule.delta))>1e-10:
            raise ValueError('Preparation duration must align with the frozen control period')
        self.qmid=vector(q_mid,'midpoint');self.q_radius=vector(q_radius,'hold q radius',nonnegative=True)
        self.v_radius=vector(qd_radius,'hold speed radius',nonnegative=True)
        self.clock=SignedClock(-self.T_pre)
        self.envelope=SignedObserverEnvelope(self.clock,system.policy.ko,system.bounds.magnitude,system.bounds.rate)
        self._plant_disturbance=plant_disturbance

    def initial_state(self):
        v=np.zeros(7)
        return PreparationState(self.qmid,v,self.system.observer.initialize(self.qmid,v),-self.T_pre)

    def run(self):
        state=self.initial_state();trace=[];last_tau=None
        sys=self.system;reference=ReferenceSample(self.qmid,np.zeros(7),np.zeros(7))
        failure=None;periods=round(self.T_pre/self.schedule.delta)
        for period in range(periods):
            estimate=sys.observer.estimate(state.q,state.qd,state.z)
            nominal,_=sys.controller.command(state.q,state.qd,reference,estimate)
            tau=project_torque_box(nominal,sys.barriers.taumax);last_tau=tau.copy()
            for substep in range(self.schedule.substeps):
                index=period*self.schedule.substeps+substep
                t=-self.T_pre+index*self.schedule.h
                x=np.r_[state.q,state.qd,state.z]
                samples=[]
                def derivative(stage_t,stage_x):
                    q,v,z=stage_x[:7],stage_x[7:14],stage_x[14:]
                    # Truth reaches the plant only, after the held command exists.
                    d=vector(self._plant_disturbance(stage_t),'plant-only disturbance')
                    e=sys.model.evaluate(q,v)
                    acc=np.linalg.solve(e['M'],tau+d-e['C']@v-e['g']-e['F'])
                    zdot=sys.observer.derivative(q,v,z,tau)
                    samples.append((stage_t,stage_x.copy(),d))
                    return np.r_[v,acc,zdot]
                h=self.schedule.h
                k1=derivative(t,x);k2=derivative(t+h/2,x+h*k1/2)
                k3=derivative(t+h/2,x+h*k2/2);k4=derivative(t+h,x+h*k3)
                after_x=x+h*(k1+2*k2+2*k3+k4)/6
                end_index=index+1
                end_t=0. if end_index==periods*self.schedule.substeps else -self.T_pre+end_index*h
                after=PreparationState(after_x[:7],after_x[7:14],after_x[14:],end_t)
                dense=component_extrema(rk4_extension_coefficients(x,h,[k1,k2,k3,k4])[:,:14])
                q_peak=np.maximum(abs(dense['minimum'][:7]-self.qmid),abs(dense['maximum'][:7]-self.qmid))
                v_peak=np.maximum(abs(dense['minimum'][7:14]),abs(dense['maximum'][7:14]))
                # Only diagnostic checks below can access truth. Neither controller
                # nor observer was supplied d, an envelope-adjusted estimate or a clamp.
                end_truth=vector(self._plant_disturbance(end_t),'post-control diagnostic truth')
                samples.append((end_t,after_x.copy(),end_truth))
                diagnostics=[]
                for st,sx,d in samples:
                    q,v,z=sx[:7],sx[7:14],sx[14:]
                    dh=sys.observer.estimate(q,v,z);vp=self.envelope.value(st)
                    physical=sys.barriers.entry_conditions(q,v,tau)
                    diagnostics.append({'physical_t_s':st,'q':q,'qd':v,'z':z,
                        'applied_tau':tau,'dhat':dh,'truth_post_control_only':d,'varpi':vp,
                        'observer_envelope_slack':vp-abs(d-dh),'physical_slacks':physical})
                stage_q=np.max([abs(a['q']-self.qmid) for a in diagnostics],axis=0)
                stage_v=np.max([abs(a['qd']) for a in diagnostics],axis=0)
                q_peak=np.maximum(q_peak,stage_q);v_peak=np.maximum(v_peak,stage_v)
                q_slack=self.q_radius-q_peak;v_slack=self.v_radius-v_peak
                observer_ok=all(np.all(a['observer_envelope_slack']>=0) for a in diagnostics)
                physical_ok=all(a['physical_slacks']['passed'] for a in diagnostics)
                checks={'q_tolerance':bool(np.all(q_slack>=0)), 'qd_tolerance':bool(np.all(v_slack>=0)),
                    'applied_torque':bool(np.all(abs(tau)<=sys.barriers.taumax)),
                    'physical_sample_checks':physical_ok,'observer_diagnostic_checks':observer_ok}
                record={'physical_t0_s':t,'physical_t1_s':end_t,'control_period_index':period,'substep_index':substep,
                    'u_nom_at_update':nominal,'dhat_at_update':estimate,'tau_applied':tau,
                    'state_before':state.record(),'state_after':after.record(),
                    'q_deviation_peak_rad':q_peak,'qd_peak_rad_s':v_peak,
                    'q_tolerance_slack_rad':q_slack,'qd_tolerance_slack_rad_s':v_slack,
                    'dense_extension':dense,'stage_and_endpoint_diagnostics':diagnostics,'checks':checks}
                trace.append(record);state=after
                if not all(checks.values()):
                    failure={'reason':'PREDECLARED_HOLD_ACCEPTANCE_FAILURE','failed_checks':[k for k,v in checks.items() if not v],
                        'physical_t_s':end_t,'q_violating_joints_1_based':(np.where(q_slack<0)[0]+1).tolist(),
                        'qd_violating_joints_1_based':(np.where(v_slack<0)[0]+1).tolist(),
                        'no_further_torque_or_state_advance':True}
                    break
            if failure:break
        completed=failure is None and state.t==0.
        return PreholdResult(state,completed,'PASS_NUMERICAL_HOLD_ONLY' if completed else 'FAIL_PREDECLARED_HOLD',trace,failure,last_tau)


def endpoint_diagnostics(system,runner,result):
    """Read-only full-QP check at the actual simulated state, including aborts."""
    state=result.state;dhat=system.observer.estimate(state.q,state.qd,state.z)
    vp=runner.envelope.value(state.t)
    physical=system.barriers.entry_conditions(state.q,state.qd,result.last_applied_torque)
    reference=ReferenceSample(state.q,state.qd,np.zeros(7))
    nominal,_=system.controller.command(state.q,state.qd,reference,dhat)
    rows=system.barriers.rows(state.q,state.qd,dhat,vp)
    solved=system.qp.solve(nominal,rows)
    strict=not solved.stop_requested and solved.diagnostics.get('exact_all_rows_nonnegative') is True
    return {'state':state.record(),'dhat':dhat,'propagated_varpi':vp,
        'observer_elapsed_s':runner.clock.elapsed(state.t),'physical_slacks':physical,
        'q_hold_slack':runner.q_radius-abs(state.q-runner.qmid),'qd_hold_slack':runner.v_radius-abs(state.qd),
        'QP_status':solved.status,'QP_full_43_rows':len(rows.names)==43,
        'QP_strict_pass':strict,'QP_diagnostics':solved.diagnostics,
        'QP_candidate_not_applied':solved.applied,
        'valid_zero_time_endpoint':bool(result.completed and physical['passed'] and strict),
        'scope':'ACTUAL_SIMULATED_ZERO_ENDPOINT' if result.completed else 'ACTUAL_SIMULATED_ABORT_STATE_NOT_A_VALID_ZERO_ENDPOINT',
        'motion_started':False,'official_A2_authorized':False}
