"""Causal cubic hold and finite-grid constraint generation; no truth input.

This is a separately versioned numerical architecture, not an interval safety
certificate. Rejected/unknown completions never become commands or history.
"""
from pathlib import Path
import ctypes, hashlib, json, multiprocessing as mp, os
from time import perf_counter
import numpy as np
from .a2_qp_reliable_v1_1 import GuardedHardQP
from .a2_qp_reliable_v1 import NUMERICAL_POLICY
from .stepper import ExecutionState
from .p1_r3 import diagnostic_sample, modeled_power
from .preparation import component_extrema

VERSION='CAUSAL_CUBIC_GL2_COMPLETION_V2_3'
GUARD=NUMERICAL_POLICY['inward_guard_original_row_scale']
TARGET=1e-9
NODES=np.array([0.,1/3,2/3,1.])
VALIDATION_NODES=np.linspace(0,1,9)
GRAM=np.array([[1/(i+j+1) for j in range(1,4)] for i in range(1,4)])
TRANSFORM=np.kron(np.linalg.inv(np.linalg.cholesky(GRAM).T),np.eye(7))

class Stop(RuntimeError):
    def __init__(self,reason,record):super().__init__(reason);self.record=record


def _native_worker(conn,build):
    build=Path(build);record=json.loads((build/'BUILD.json').read_text())
    library=build/'libpanda_completion.so'
    if hashlib.sha256(library.read_bytes()).hexdigest()!=record['library_sha256']:raise ValueError('Completion binary differs')
    lib=ctypes.CDLL(str(library));f=lib.panda_completion;p=ctypes.POINTER(ctypes.c_double)
    f.argtypes=[ctypes.c_int,ctypes.c_int]+[p]*6;f.restype=ctypes.c_int
    conn.send('READY')
    try:
        while True:
            data=conn.recv()
            if data is None:break
            C,b=data;n=C.shape[1];m=len(b)
            arrays=[np.zeros(n),np.ascontiguousarray(C),np.ascontiguousarray(b),np.zeros(n),np.zeros(m),np.zeros(3)]
            code=f(n,m,*[a.ctypes.data_as(p) for a in arrays]);conn.send((code,*arrays[3:]))
    finally:conn.close()

class CompletionService:
    def __enter__(self):
        build=os.environ.get('PANDA_COMPLETION_BUILD','/workspace/panda-completion-build-v2')
        ctx=mp.get_context('spawn');self.conn,child=ctx.Pipe();self.process=ctx.Process(target=_native_worker,args=(child,build),daemon=True)
        self.process.start();child.close()
        if not self.conn.poll(15.) or self.conn.recv()!='READY':self.__exit__();raise RuntimeError('Completion unavailable')
        return self
    def solve(self,C,b,remaining):
        self.conn.send((C,b))
        if remaining<=0 or not self.conn.poll(remaining):raise Stop('COMPLETION_TIMEOUT_UNKNOWN',{'no_actuation':True})
        code,x,dual,info=self.conn.recv()
        if code or info[0]!=0 or not all(np.all(np.isfinite(a)) for a in [x,dual,info]):
            raise Stop('COMPLETION_NOT_SOLVED',{'native_code':code,'info':info,'no_actuation':True})
        return x,dual,info
    def __exit__(self,*args):
        if getattr(self,'process',None):self.process.terminate();self.process.join(timeout=2.)
        if getattr(self,'conn',None):self.conn.close()


def predict(history,t):
    """Extrapolate only measured accepted states; no waveform or future truth."""
    if len(history)<4:raise Stop('INSUFFICIENT_MEASURED_HISTORY',{'no_actuation':True})
    selected=history[-4:];base=selected[-1][0];scale=selected[-1][0]-selected[-2][0]
    xs=np.array([(a-base)/scale for a,_ in selected]);ys=np.array([x for _,x in selected])
    coefficients=np.linalg.solve(np.vander(xs,4,increasing=True),ys)
    return np.polynomial.polynomial.polyval((t-base)/scale,coefficients)


def support_kkt(C,b,deadline):
    """Compute finite-QP support from current rows, never stored witnesses.

    This is an explicit numerical stage of the completion algorithm, after a
    SOLVED native restricted QP. No torque has been accepted or actuated.
    SVD solves the support equations without squaring the condition number.
    """
    active=[];x=np.zeros(C.shape[1]);dual=np.zeros(len(b));norm=np.linalg.norm(C,axis=1)
    nonzero=norm>0.;history=[]
    for iteration in range(10000):
        if perf_counter()>deadline:raise Stop('SUPPORT_KKT_TIMEOUT_UNKNOWN',{'no_actuation':True})
        if active:
            A=C[active]/norm[active,None];v=b[active]/norm[active]
            x,_,rank,_=np.linalg.lstsq(A,v,rcond=None)
            lam=np.linalg.lstsq(A.T,-x,rcond=None)[0]
            if np.min(lam)<-1e-12:
                active.pop(int(np.argmin(lam)));continue
            dual=np.zeros(len(b));dual[active]=lam/norm[active]
        residual=C@x-b
        eligible=np.where(nonzero,residual,-np.inf);j=int(np.argmax(eligible))
        history.append({'active':list(active),'full_primal':max(0.,float(np.max(residual)))})
        if eligible[j]<=1e-12:return x,dual,history
        if j in active:raise Stop('SUPPORT_RANK_OR_RESOLUTION_FAILURE',{'active':active,'residual':residual,'no_actuation':True})
        active.append(j)
    raise Stop('SUPPORT_KKT_ITERATION_LIMIT',{'no_actuation':True,'history':history})


def complete(base,rows,service,deadline):
    """Fixed finite polytope; working-set generation, full-grid KKT verification.

    tau(s)=base(s)+87*[sI,s²I,s³I]T*x. The constant is unchanged.
    min 1/2 ||x||² = (1/(2*87²)) integral ||tau-base||² ds.
    Each omitted multiplier is zero; no witness enters this function.
    """
    matrices=[];bounds=[];scales=[];rawG=[];rawc=[]
    for s,row in zip(VALIDATION_NODES,rows):
        B=np.hstack([s**j*np.eye(7) for j in range(1,4)])@TRANSFORM
        G=87.*row.G@B
        c=row.slacks(np.polynomial.polynomial.polyval(s,base))-GUARD*row.scales
        matrices.append(-G);bounds.append(c);scales.extend(row.scales);rawG.extend(G);rawc.extend(c)
    C=np.vstack(matrices);b=np.concatenate(bounds);scales=np.array(scales)
    den=scales.copy()  # Full original-row guarded residual controls solver accuracy.
    C=C/den[:,None];b=b/den
    # Current rows have zero variable coefficient and must already be feasible
    # to original strict tolerance. They remain present in full verification.
    working=list(np.flatnonzero(b<0));working=[i for i in working if np.any(C[i]!=0)]
    x=np.zeros(21);dual=np.zeros(len(b));rounds=[]
    for iteration in range(len(b)+1):
        if perf_counter()>deadline:raise Stop('COMBINED_QUERY_WALL_BUDGET_UNKNOWN',{'no_actuation':True,'rounds':rounds})
        if working:
            x,wd,info=service.solve(C[working],b[working],deadline-perf_counter());dual=np.zeros(len(b));dual[working]=wd
        native_residuals={'primal':max(0.,float(np.max(C@x-b))),
                          'stationarity':float(np.max(abs(x+C.T@dual))),
                          'complementarity':float(np.max(abs(dual*(C@x-b))))}
        support_history=[]
        if working and any(v>1e-12 for v in native_residuals.values()):
            x,dual,support_history=support_kkt(C,b,deadline)
        residual=C@x-b
        missing=[int(i) for i in np.flatnonzero(residual>TARGET) if i not in working and np.any(C[i]!=0)]
        rounds.append({'working_rows':list(working),'maximum_full_violation':max(0.,float(np.max(residual))),'added_rows':missing})
        if missing:working.extend(missing);continue
        values={'full_primal':max(0.,float(np.max(residual))),
                'stationarity':float(np.max(abs(x+C.T@dual))),
                'negative_dual':max(0.,float(np.max(-dual))),
                'complementarity':float(np.max(abs(dual*residual))),
                'original_scale_guarded_violation':max(0.,float(np.max((np.array(rawG)@x*-1-np.array(rawc))/scales)))}
        guarded=np.array(rawG)@x+np.array(rawc)
        raw=guarded+GUARD*scales
        accepted=all(v<=TARGET for v in values.values()) and np.all(raw>=0)
        audit={'accepted':bool(accepted),'C':C,'b':b,'x':x,'dual_full':dual,'row_scales':scales,
               'full_guarded_normalized_slacks':guarded/scales,'full_raw_normalized_slacks':raw/scales,
               'residuals':values,'native_pre_support_residuals':native_residuals,'computed_support_history':support_history,'generation':rounds,'all_rows_verified':len(b),'witness_fallback':False}
        if not accepted:raise Stop('FULL_GUARDED_KKT_REJECTION',audit)
        coefficients=base.copy();coefficients[1:]+=87.*(TRANSFORM@x).reshape(3,7)
        return coefficients,audit
    raise Stop('CONSTRAINT_GENERATION_EXHAUSTED',{'no_actuation':True,'rounds':rounds})

class PolynomialHold:
    def __init__(self,system,service):self.system=system;self.service=service;self.kernel=GuardedHardQP(system.barriers.taumax)
    def query(self,state,delta,history,envelope,reference):
        start=perf_counter();deadline=start+15.;system=self.system;torques=[];nominals=[];queries=[]
        for s in NODES:
            sx=np.r_[state.q,state.qd,state.z] if s==0 else predict(history,state.t+s*delta)
            q,v,z=sx[:7],sx[7:14],sx[14:21];t=min(state.t+s*delta,reference.duration)
            dhat=system.observer.estimate(q,v,z)
            nominal,errors=system.controller.command(q,v,reference.sample(t),dhat)
            row=system.barriers.rows(q,v,dhat,envelope.value(t));solved=self.kernel.solve(nominal,row)
            queries.append({'s':s,'predicted_state':sx,'nominal':nominal,'G':row.G,'c':row.c,'scales':row.scales,'query':solved.__dict__})
            if solved.stop_requested or solved.applied is None:raise Stop('PREDICTED_PROJECTION_FAILURE',{'queries':queries,'no_actuation':True})
            torques.append(solved.applied);nominals.append(nominal)
        base=np.linalg.solve(np.vander(NODES,4,increasing=True),torques)
        nominal_poly=np.linalg.solve(np.vander(NODES,4,increasing=True),nominals)
        rows=[]
        for s in VALIDATION_NODES:
            sx=np.r_[state.q,state.qd,state.z] if s==0 else predict(history,state.t+s*delta)
            q,v,z=sx[:7],sx[7:14],sx[14:21]
            rows.append(system.barriers.rows(q,v,system.observer.estimate(q,v,z),envelope.value(state.t+s*delta)))
        coefficients,audit=complete(base,rows,self.service,deadline)
        if perf_counter()>deadline:raise Stop('COMBINED_QUERY_WALL_BUDGET_UNKNOWN',{'no_actuation':True})
        return {'version':VERSION,'t0':state.t,'delta':delta,'coefficients':coefficients,'nominal_coefficients':nominal_poly,
                'projection_queries':queries,'completion':audit,'wall_s':perf_counter()-start,'accepted':True,'actuated':False,
                'future_measured_state_used':False,'plant_truth_used':False}


def torque(hold,t):
    s=(t-hold['t0'])/hold['delta']
    if s < -1e-10 or s>1+1e-10:raise ValueError('Outside accepted polynomial hold')
    return np.polynomial.polynomial.polyval(min(1.,max(0.,s)),hold['coefficients'])


def polynomial_peak(coefficients):
    square=np.zeros(7)
    for j in range(7):square+=np.convolve(coefficients[:,j],coefficients[:,j])
    roots=np.polynomial.polynomial.polyroots(np.arange(1,7)*square[1:])
    nodes=[0.,1.]+[float(r.real) for r in roots if abs(r.imag)<1e-9 and 0<r.real<1]
    return float(np.sqrt(max(0.,max(np.polynomial.polynomial.polyval(s,square) for s in nodes))))


def integrate(system,state,hold,h,end_t,envelope,waveform):
    """Two-stage implicit Gauss-Legendre collocation, order four.

    Identical stage torque is supplied to plant and DOB. Truth is confined to
    plant RHS and diagnostics. Iteration failure rejects the attempted step.
    Dense polynomial extrema are numerical, not true-ODE interval bounds.
    """
    root=np.sqrt(3)/6;c=np.array([.5-root,.5+root]);A=np.array([[.25,.25-root],[.25+root,.25]])
    x=np.r_[state.q,state.qd,state.z,0.];times=state.t+h*c
    def rhs(t,sx):
        q,v,z=sx[:7],sx[7:14],sx[14:21];tau=torque(hold,t);e=system.model.evaluate(q,v)
        a=np.linalg.solve(e['M'],tau+waveform(t)-e['C']@v-e['g']-e['F'])
        return np.r_[v,a,system.observer.derivative(q,v,z,tau),modeled_power(tau,v,system.policy.raw['energy'])]
    K=np.array([rhs(t,x) for t in times]);converged=False
    for iteration in range(40):
        stages=x+h*A@K;new=np.array([rhs(t,s) for t,s in zip(times,stages)])
        error=float(np.max(abs(h*(new-K))))
        K=new
        if error<=1e-13:converged=True;break
    if not converged:raise Stop('GAUSS_LEGENDRE_STAGE_NONCONVERGENCE',{'iteration':iteration,'error':error,'no_further_advance':True})
    stages=x+h*A@K;residual=float(np.max(abs(np.array([rhs(t,s) for t,s in zip(times,stages)])-K))*h)
    if residual>1e-13:raise Stop('GAUSS_LEGENDRE_RESIDUAL_REJECTION',{'residual':residual})
    after=x+h*.5*(K[0]+K[1]);final=ExecutionState(after[:7],after[7:14],after[14:21],end_t)
    l0=np.array([c[1],-1.])/(c[1]-c[0]);l1=np.array([-c[0],1.])/(c[1]-c[0])
    densecoef=np.vstack([x[:14],h*(l0[0]*K[0,:14]+l1[0]*K[1,:14]),h*.5*(l0[1]*K[0,:14]+l1[1]*K[1,:14])])
    dense=component_extrema(np.vstack([densecoef,np.zeros((1,14))]))
    samples=[diagnostic_sample(system,envelope,waveform,t,sx,torque(hold,t)) for t,sx in [(state.t,x),*zip(times,stages),(end_t,after)]]
    checks={'physical_samples':all(s['physical_slacks']['passed'] for s in samples),
            'observer_samples':all(np.all(s['observer_envelope_slack']>=0) for s in samples),
            'dense_joint_position':bool(np.all(dense['minimum'][:7]>=system.barriers.qmin) and np.all(dense['maximum'][:7]<=system.barriers.qmax)),
            'dense_joint_speed':bool(np.all(dense['minimum'][7:14]>=-system.barriers.vmax) and np.all(dense['maximum'][7:14]<=system.barriers.vmax))}
    return final,{'physical_t0_s':state.t,'physical_t1_s':end_t,'samples':samples,'dense_extension':dense,
                  'modeled_electrical_energy_increment_J':float(after[-1]),'checks':checks,
                  'stage_rhs':K,'stage_state':stages,'stage_times':times,'stage_torques':np.array([torque(hold,t) for t in times]),
                  'stage_equation_residual':residual,'nonlinear_iterations':iteration+1,'integrator':'GL2_ORDER4'}
