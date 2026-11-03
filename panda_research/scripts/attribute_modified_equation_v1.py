"""Read-only first-order defect propagation on the finest historical C4 trace.

Ordinary floating point linearization, not certified bounds or runtime control.
Predicts Delta sensitivity from differentiated dynamics/KKT, not a fit to final
energy/peak outcomes. Only measured initial-state difference initializes bias.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,time,hashlib
import numpy as np
import casadi as ca
from panda_dynamics import PHI1,PHI2,PHI3,dual_harmonic_disturbance
from panda_closed_loop.assembly import build_components
from panda_closed_loop.active_sampled_analysis_v1 import SpeedMaterialDerivative
from panda_closed_loop.a2_acceptance import read_recorded_trace
from panda_closed_loop.logging import json_values

def write(p,d):
    with Path(p).open('x') as f:json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')

def build_jacobians(system,operator):
    Y=ca.SX.sym('sensitivity_Y',98);tau=ca.SX.sym('actual_tau',7);d=ca.SX.sym('offline_disturbance',7)
    A,b,r,_=operator.function(Y,ca.SX.zeros(98))
    target_data=ca.vertcat(ca.vec(A),b,r)
    q,v,z=Y[:7],Y[7:14],Y[14:21];N=ca.reshape(Y[49:],7,7)
    M,flat,g,_,_=system.model._fun(q);dm=[ca.reshape(flat[:,k],7,7) for k in range(7)]
    C=ca.SX.zeros(7,7)
    for i in range(7):
        for j in range(7):C[i,j]=sum(.5*(dm[k][i,j]+dm[j][i,k]-dm[i][j,k])*v[k] for k in range(7))
    F=.5*ca.DM(PHI1)*(ca.tanh(.5*ca.DM(PHI2)*(v+ca.DM(PHI3)))-ca.tanh(.5*ca.DM(PHI2)*ca.DM(PHI3)))
    dhat=z+ca.DM(system.observer.gains)*(M@v)
    flow=ca.vertcat(v,N@(tau+d-C@v-g-F),-ca.DM(system.observer.gains)*(dhat+tau+C.T@v-g-F))
    function=ca.Function('readonly_flow_and_KKT_jacobians_v1',[Y,tau,d],
        [ca.jacobian(target_data,Y),ca.jacobian(flow,Y),flow],{'cse':True})
    return function

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--operators',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);begin=time.perf_counter()
    while not (a.operators/'SUMMARY.json').exists():
        if time.perf_counter()-begin>3600:raise TimeoutError('Operator analysis not finished')
        time.sleep(2)
    index=2 # fine Delta=.5ms with h=.25ms, matched to coarse cell0.
    data=np.load(a.operators/f'cell_{index}_operators.npz',allow_pickle=False)
    cell=json.loads((a.input/f'cell_{index}.json').read_text());coarse=json.loads((a.input/'cell_0.json').read_text())
    trace=read_recorded_trace(a.input,cell['a2']['trace']);U=trace['updates'];n=len(U)
    sys=build_components();operator=SpeedMaterialDerivative(sys);jac=build_jacobians(sys,operator)
    times=data['t'];dt=cell['grid']['control_period_s']; gap=coarse['grid']['control_period_s']-dt
    J=[];sources=[];I_x=[];I_direct=[];sigma_jacs=[];raw_jacs=[];row_value_errors=[]
    eps=1e-7;derivative_crosschecks=[]
    for k,u in enumerate(U):
        q,v,z=data['state'][k,:7],data['state'][k,7:14],data['state'][k,14:]
        e=sys.model.evaluate(q,v);N=np.linalg.solve(e['M'],np.eye(7))
        Y=np.r_[q,v,z,u['reference']['q'],u['reference']['qd'],u['reference']['qdd'],u['varpi'],N.flatten(order='F')]
        truth=dual_harmonic_disturbance(float(times[k]),sys.policy.raw['disturbance']['amplitude_fraction'])
        R0,F0,flow=jac(Y,data['sigma'][k],truth);R0=np.asarray(R0);F0=np.asarray(F0)
        chain=np.zeros((98,21));chain[:21]=np.eye(21)
        for j in range(7):chain[49:,j]=(-N@e['dM'][:,:,j]@N).flatten(order='F')
        R=R0@chain;F=F0@chain;rx=R[112:119]
        A=data['current_row_A'][k,15:29];sig=data['sigma'][k];r=data['r'][k]
        active=np.flatnonzero(data['raw_projection_dual_scaled'][k,15:29]>1e-10)
        lam=87*data['raw_projection_dual_scaled'][k,15:29]
        if len(active):
            aa=A[active];dagger=aa.T@np.linalg.solve(aa@aa.T,np.eye(len(active)));P=np.eye(7)-dagger@aa
            dA=R[:98].reshape((14,7,21),order='F')[active];db=R[98:112][active]
            normal=db-np.einsum('ijk,j->ik',dA,sig)
            sx=P@rx-P@np.einsum('ijk,i->jk',dA,lam[active])+dagger@normal
            rotation=data['missing_rotation'][k];normal_term=data['missing_normal'][k]
            if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(normal_term)):
                raise ValueError('Missing active-face diagnostic')
        else:
            P=np.eye(7);sx=rx;rotation=np.zeros(7);normal_term=np.zeros(7)
        B=np.vstack([np.zeros((7,7)),N,-np.diag(sys.observer.gains)])
        kr=np.array(sys.policy.raw['energy']['k_r']);vel=v
        bus=float(np.sum(sig*vel+kr*sig*sig));phi=.5*(1+bus/np.hypot(bus,.01))
        ptau=phi*(vel+2*kr*sig);px=np.r_[np.zeros(7),phi*sig,np.zeros(7)]
        JJ=np.zeros((22,22));JJ[:21,:21]=F+B@sx;JJ[21,:21]=px+ptau@sx
        gg=np.zeros((22,5))
        # Columns: initial bias, rotation via state, normal via state,
        # rotation direct power, normal direct power. Their sum is the defect.
        gg[:21,1]=-.5*B@rotation;gg[:21,2]=-.5*B@normal_term
        gg[21,3]=-.5*ptau@rotation;gg[21,4]=-.5*ptau@normal_term
        correction=sig-r;length=np.linalg.norm(correction)
        ix=correction@(sx-rx)/length if length>1e-8 else np.zeros(21)
        eta=-.5*correction@((np.eye(7)-P)@data['dr'][k])/length if len(active) and length>1e-8 else 0.
        J.append(JJ);sources.append(gg);I_x.append(ix);I_direct.append(eta);sigma_jacs.append(sx);raw_jacs.append(rx)
        # Independent directional FD of the fixed-torque plant/DOB Jacobian.
        if k in [100,400,700,1200,1800]:
            dx=np.array([.3,-.2,.1,-.1,.2,.1,-.3]+[.2]*7+[-.1]*7)
            values=[]
            for sign in [-1,1]:
                xx=data['state'][k]+sign*eps*dx
                ee=sys.model.evaluate(xx[:7],xx[7:14])
                acc=np.linalg.solve(ee['M'],sig+truth-ee['C']@xx[7:14]-ee['g']-ee['F'])
                zd=sys.observer.derivative(xx[:7],xx[7:14],xx[14:],sig)
                values.append(np.r_[xx[7:14],acc,zd])
            fd=(values[1]-values[0])/(2*eps)
            derivative_crosschecks.append({'t_s':float(times[k]),'relative_error':float(np.linalg.norm(fd-F@dx)/max(np.linalg.norm(fd),1e-30))})
    J=np.asarray(J);sources=np.asarray(sources);I_x=np.asarray(I_x);I_direct=np.asarray(I_direct)
    bias=np.zeros((22,5));bias[:21,0]=(np.r_[coarse['endpoint']['state']['q'],coarse['endpoint']['state']['qd'],coarse['endpoint']['state']['z']]-data['state'][0])/gap
    history=[bias.copy()]
    for k in range(n):
        j0=J[k];g0=sources[k];j1=J[min(k+1,n-1)];g1=sources[min(k+1,n-1)]
        jm=.5*(j0+j1);gm=.5*(g0+g1)
        k1=j0@bias+g0;k2=jm@(bias+dt*k1/2)+gm;k3=jm@(bias+dt*k2/2)+gm;k4=j1@(bias+dt*k3)+g1
        bias=bias+dt*(k1+2*k2+2*k3+k4)/6;history.append(bias.copy())
    history=np.asarray(history);peak=int(np.argmax(np.linalg.norm(data['tau']-data['u'],axis=1)))
    peak_state=I_x[peak]@np.sum(history[peak,:21,:],axis=1);peak_direct=I_direct[peak]
    observed_E=coarse['a2']['metrics']['modeled_electrical_energy_J']-cell['a2']['metrics']['modeled_electrical_energy_J']
    observed_I=coarse['a2']['metrics']['maximum_intervention_Nm']-cell['a2']['metrics']['maximum_intervention_Nm']
    pred_E=gap*float(np.sum(history[-1,21]));pred_I=gap*float(peak_state+peak_direct)
    outcome={'scope':'READ_ONLY_FIRST_ORDER_MODIFIED_EQUATION_ATTRIBUTION_NOT_CERTIFIED_ERROR_BOUND',
        'source_trace_sha256':cell['a2']['trace']['sha256'],'evaluation_grid':cell['grid'],'Delta_difference_s':gap,
        'not_fitted_to_energy_or_peak_results':True,'initial_bias_source':'Actual coarse-minus-fine post-P1 state divided by Delta difference; no outcome fit',
        'energy':{'observed_difference_J':observed_E,'first_order_prediction_J':pred_E,
            'prediction_to_observed_ratio':pred_E/observed_E,
            'contribution_J':dict(zip(['initial_state','face_rotation_state','face_normal_state','face_rotation_direct_power','face_normal_direct_power'],(gap*history[-1,21]).tolist()))},
        'peak_intervention':{'fine_peak_t_s':float(times[peak]),'observed_difference_Nm':observed_I,
            'first_order_prediction_Nm':pred_I,'prediction_to_observed_ratio':pred_I/observed_I,
            'state_contribution_Nm':gap*float(peak_state),'digital_request_direct_contribution_Nm':gap*float(peak_direct)},
        'fixed_torque_flow_Jacobian_independent_FD':derivative_crosschecks,
        'limitations':['Finite-grid trace used in place of exact continuous solution',
            'Piecewise smooth floating point KKT sensitivities at sampled active sets; no global interval regularity proof',
            'Linear coefficient integrated with sampled/interpolated Jacobians; no certified remainder',
            'Peak evaluation at fine-grid maximum; not substituted for frozen sampled metric',
            'Local defect contributions may cancel; no universal impossibility conclusion'],
        'wall_s':time.perf_counter()-begin,'independent_signatures':None,'torque_actuated':False}
    write(a.output/'SUMMARY.json',outcome)
    np.savez_compressed(a.output/'first_order_bias.npz',t=np.r_[times,cell['a2']['final_state']['physical_t_s']],
        component_bias=history,J=J,defect_sources=sources,I_x=I_x,I_digital_direct=I_direct,
        sigma_x=np.array(sigma_jacs),r_x=np.array(raw_jacs))
    print(json.dumps({'energy':outcome['energy'],'peak':outcome['peak_intervention']},indent=2))

if __name__=='__main__':main()
