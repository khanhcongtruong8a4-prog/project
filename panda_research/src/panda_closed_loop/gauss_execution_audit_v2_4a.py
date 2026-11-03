"""Independent verification correction; never imported by the runtime hold.

Implicit stages satisfy a residual criterion, not an exact binary fixed point.
The 1e-13 criterion was frozen before the first v2 actuation.
"""
import numpy as np
from .polynomial_hold_v2_4 import torque
from .p1_r3 import modeled_power

def audit_step(system,hold,step,waveform):
    h=step['physical_t1_s']-step['physical_t0_s'];K=np.asarray(step['stage_rhs']);X=np.asarray(step['stage_state'])
    times=np.asarray(step['stage_times']);logged_tau=np.asarray(step['stage_torques'])
    root=np.sqrt(3)/6;A=np.array([[.25,.25-root],[.25+root,.25]])
    first=step['samples'][0];last=step['samples'][-1]
    x0=np.r_[first['q'],first['qd'],first['z'],0.]
    rhs=[];same=True
    for t,x,tau in zip(times,X,logged_tau):
        actual=torque(hold,t);same &= np.array_equal(actual,tau)
        q,v,z=x[:7],x[7:14],x[14:21];e=system.model.evaluate(q,v)
        acc=np.linalg.solve(e['M'],actual+waveform(t)-e['C']@v-e['g']-e['F'])
        observer=system.observer.derivative(q,v,z,actual)
        rhs.append(np.r_[v,acc,observer,modeled_power(actual,v,system.policy.raw['energy'])])
    defect=float(np.max(abs(h*(np.array(rhs)-K))))
    # Reconstruct the actual h from stored stage times to avoid cancellation in
    # t1-t0. The execution schedule itself is checked by the enclosing auditor.
    stage_h=(times[1]-times[0])/(2*root)
    # Stage equations and endpoints use the logged, exactly prescribed schedule
    # value supplied by the enclosing auditor whenever available.
    schedule_h=step.get('prescribed_h',h)
    stage_defect=float(np.max(abs(X-(x0+schedule_h*A@K))))
    final=x0+schedule_h*.5*(K[0]+K[1]);logged_final=np.r_[last['q'],last['qd'],last['z'],step['modeled_electrical_energy_increment_J']]
    endpoint_defect=float(np.max(abs(final-logged_final)))
    passed=bool(same and np.all(np.isfinite(rhs)) and defect<=1e-13 and stage_defect<=1e-13 and endpoint_defect<=1e-13)
    return {'passed':passed,'identical_polynomial_stage_torques':bool(same),
            'h_scaled_full_RHS_defect':defect,'stage_equation_defect':stage_defect,'endpoint_equation_defect':endpoint_defect,
            'criterion':1e-13,'exact_binary_RHS_fixed_point_required':False}
