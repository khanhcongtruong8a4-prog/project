"""Deterministic read-only pair/point-QP screens. Never runs a plant or A2."""
import itertools
import math
import numpy as np
from .contracts import scalar, vector, matrix
from .observer import ObserverEnvelope


def pair_conditions(N_abs, varpi, q_range, vmax, alpha1, alpha2, alpha_v):
    N = matrix(N_abs, 'abs(M^-1)', (7,7), nonnegative=True)
    vp = vector(varpi, 'varpi N m', nonnegative=True)
    width, speed = vector(q_range, 'joint range'), vector(vmax, 'vmax')
    if np.any(width <= 0) or np.any(speed <= 0):
        raise ValueError('Positive joint ranges and speed limits required')
    a1, a2, av = [scalar(x, name, positive=True) for x,name in [(alpha1,'alpha1'),(alpha2,'alpha2'),(alpha_v,'alpha_v')]]
    lhs = N@vp
    vrhs, prhs = av*speed, a1*a2*width/2
    def family(rhs, label):
        slack = rhs-lhs
        return {'family':label,'unit':'rad/s^2','lhs':lhs.tolist(),'rhs':rhs.tolist(),'slack':slack.tolist(),
                'passed':bool(np.all(slack >= 0)), 'worst_violation':float(max(0.,-np.min(slack))),
                'violating_joints_1_based':(np.where(slack < 0)[0]+1).tolist()}
    return {'velocity':family(vrhs,'ONLINE_VELOCITY_PAIRS'), 'position':family(prhs,'ONLINE_POSITION_PAIRS'),
            'necessary_only':True,'not_full_QP_or_safety_proof':True}


def duration_for_pairs(B0, rhs, dbar, rate, gains, quantum_s):
    """Closed-form common-Ko decay threshold; no search/plant iteration.

    B(t) <= B0*[f+(1-f)*exp(-k*t)] with f=max_i d1_i/(k*dbar_i).
    Max f conservatively covers floating-point ratio differences.
    """
    B0 = np.asarray(B0,dtype=float)
    if B0.ndim != 2 or B0.shape[1] != 7 or not np.all(np.isfinite(B0)) or np.any(B0<0):
        raise ValueError('B0 must be a finite nonnegative (samples,7) matrix')
    rhs = vector(rhs,'both-family threshold',nonnegative=True)
    dbar, rate = vector(dbar,'dbar',nonnegative=True),vector(rate,'dbar1',nonnegative=True)
    gains = vector(gains,'Ko'); quantum=scalar(quantum_s,'duration quantum s',positive=True)
    if np.any(gains<=0) or not np.all(gains==gains[0]) or np.any(dbar<=0):
        raise ValueError('This analytical implementation requires positive common Ko and dbar')
    k=float(gains[0]);f=float(np.max(rate/(k*dbar)))
    if not 0<=f<1:raise ValueError('Nondecaying/unsupported envelope')
    ratio=np.divide(rhs[None,:],B0,out=np.full_like(B0,np.inf),where=B0>0)
    limiting=np.unravel_index(np.argmin(ratio),ratio.shape);threshold=float(np.min(ratio))
    base={'floor_fraction_upper':f,'k_s_inverse':k,'limiting_sample':int(limiting[0]),'limiting_joint_1_based':int(limiting[1])+1,
          'threshold_fraction':threshold if np.isfinite(threshold) else None,'duration_selection':'single analytical rule, no retuning on QP results'}
    if threshold>=1:
        return dict(base,status='ALREADY_PASSES',critical_s=0.,proposed_T_pre_s=0.)
    if threshold<=f:
        return dict(base,status='NO_FINITE_DURATION_ABOVE_FLOOR',critical_s=None,proposed_T_pre_s=None)
    critical=-math.log((threshold-f)/(1-f))/k
    selected=(math.ceil(critical/quantum)+1)*quantum
    return dict(base,status='FINITE_ANALYTIC_THRESHOLD',critical_s=critical,proposed_T_pre_s=selected)


def q_grid(center, radii):
    center,radii=vector(center,'center'),vector(radii,'radii',nonnegative=True)
    return np.vstack([center]+[center+radii*np.array(signs) for signs in itertools.product([-1.,1.],repeat=7)])


def elapsed_envelope(physical_t, T_pre, gains, dbar, rate):
    t=scalar(physical_t,'physical clock s')
    pre=scalar(T_pre,'T_pre s',nonnegative=True)
    elapsed=t+pre
    if elapsed < -1e-12:
        raise ValueError('Time before observer initialization')
    # Only a mathematical elapsed-time map. Does not retrofit negative-time
    # support into the physical execution harness or restart the disturbance.
    return ObserverEnvelope(gains,dbar,rate,t0=0.).value(max(0.,elapsed))


def planner_pair_screen(varpi,q_range,vmax,alpha1,alpha2,alpha_v,delta_h,delta_vB,*,Nbar=None,Abar_plus=None,Abar_minus=None):
    """Necessary lower-margin screen, not full planner feasibility.

    Explicit separate Abar bounds are required for position rows; they are
    never silently identified with an independently supplied Nbar.
    """
    if Nbar is None or Abar_plus is None or Abar_minus is None:
        return {'status':'BLOCKED_MISSING_M1_BOUNDS','required':['Nbar','joint Abar_plus','joint Abar_minus'],
                'point_abs_N_substituted_as_upper_bound':False,'full_planner_computed':False}
    vp=vector(varpi,'varpi',nonnegative=True)
    N=matrix(Nbar,'Nbar',(7,7),nonnegative=True)
    Aplus=matrix(Abar_plus,'Abar_plus',(7,7),nonnegative=True)
    Aminus=matrix(Abar_minus,'Abar_minus',(7,7),nonnegative=True)
    dh=vector(delta_h,'per-joint HOCBF reserve',nonnegative=True)
    dv=scalar(delta_vB,'velocity CBF reserve rad/s^2',nonnegative=True)
    velocity_lhs=2*N@vp+dv
    position_lhs=(Aplus+Aminus)@vp+dh
    vrhs=scalar(alpha_v,'alpha_v',positive=True)*vector(vmax,'vmax')
    prhs=scalar(alpha1,'alpha1',positive=True)*scalar(alpha2,'alpha2',positive=True)*vector(q_range,'range')/2
    def family(lhs,rhs):
        slack=rhs-lhs
        return {'lhs':lhs.tolist(),'rhs':rhs.tolist(),'slack':slack.tolist(),
            'unit':'rad/s^2','source':'Caller-supplied M1 domain bound plus declared varpi/reserve',
            'worst_violation':float(max(0.,-np.min(slack))),
            'violating_joints_1_based':(np.where(slack<0)[0]+1).tolist()}
    return {'status':'PASS_NECESSARY_LOWER_SCREEN' if np.all(velocity_lhs<=vrhs) and np.all(position_lhs<=prhs) else 'FAIL_NECESSARY_LOWER_SCREEN',
            'velocity':family(velocity_lhs,vrhs),
            'position':family(position_lhs,prhs),
            'unit':'rad/s^2','factor_two_included':True,
            'omitted_terms':'Nonnegative beta, Bbar*chi_s, Nbar*rho_r and other margin terms; passing is NOT sufficient',
            'bound_validity':'Caller-supplied evidence not certified by this arithmetic function','full_planner_computed':False}


def pointwise_planner_lower_witness(N_abs,varpi,q_range,vmax,a1,a2,av,delta_h,delta_vB):
    """Use |N(q)| as a LOWER witness, never as a planner upper bound.

    Any valid Nbar/Abar domain including this point must dominate the matching
    absolute entries. A failed lower screen rules out its necessary inequality
    at this point; a pass establishes no planner bound or feasible plan.
    """
    N=matrix(N_abs,'point abs(N)',(7,7),nonnegative=True)
    vp=vector(varpi,'varpi',nonnegative=True)
    B=N@vp
    dh=vector(delta_h,'joint HOCBF reserve',nonnegative=True)
    dv=scalar(delta_vB,'velocity CBF reserve',nonnegative=True)
    vrhs=scalar(av,'alpha_v',positive=True)*vector(vmax,'vmax')
    prhs=scalar(a1,'alpha1',positive=True)*scalar(a2,'alpha2',positive=True)*vector(q_range,'range')/2
    def witness(factor):
        velocity,position=factor*B+dv,factor*B+dh
        return {'factor':factor,'velocity_lhs':velocity.tolist(),'velocity_rhs':vrhs.tolist(),
                'velocity_slack':(vrhs-velocity).tolist(),
                'position_lhs':position.tolist(),'position_rhs':prhs.tolist(),'position_slack':(prhs-position).tolist(),
                'velocity_worst_violation':float(max(0.,np.max(velocity-vrhs))),
                'position_worst_violation':float(max(0.,np.max(position-prhs))),
                'velocity_failing_joints':(np.where(velocity>vrhs)[0]+1).tolist(),
                'position_failing_joints':(np.where(position>prhs)[0]+1).tolist()}
    return {'status':'POINTWISE_LOWER_WITNESS_ONLY_NOT_A_PLANNER_BOUND','unit':'rad/s^2',
            'reviewer_factor_two':witness(2.),
            'matched_reference_start_factor_three':witness(3.),
            'factor_three_assumptions':'At reference initialization chi_s=chi_e=chi_v=0, rho_r(0)=varpi(0); the additional Nbar*rho_r / Abar*rho_r terms do not vanish.',
            'point_abs_N_substituted_as_upper_bound':False,'full_planner_computed':False,
            'interpretation':'Only conditional lower witnesses for any valid bounds whose domain contains this point. No computed/verified M1 enclosure.'}
