"""Franka Panda FER / Gaz 2019 *selected seven-body* dynamics prototype.

Source conventions: Gaz author conversion (c1z = 0), Table IX COM inertias,
Gaz smooth friction, MDH frames algebraically matching pinned franka_arm.xacro.
DO NOT claim this is an independently validated hardware or certified model.

One CasADi automatic-differentiation evaluator produces M, dM/dq, g,
potential and flange FK. Christoffel-consistent C is assembled from AD dM.
"""
from __future__ import annotations
import numpy as np
import casadi as ca

N = 7
MASS = np.array([4.970684,0.646926,3.228604,3.587895,1.225946,1.666555,0.735522])
COM = np.array([
 [0.003875,0.002081,0.0],
 [-0.003141,-0.028720,0.003495],
 [0.027518,0.039252,-0.066502],
 [-0.053170,0.104419,0.027454],
 [-0.011953,0.041065,-0.038437],
 [0.060149,-0.014117,-0.010517],
 [0.010517,-0.004252,0.061597]
])
# [Ixx,Ixy,Ixz,Iyy,Iyz,Izz] about COM, signed off-diagonal entries.
INERTIA6 = np.array([
 [0.703370,-0.000139,0.006772,0.706610,0.019169,0.009117],
 [0.007962,-0.003925,0.010254,0.028110,0.000704,0.025995],
 [0.037242,-0.004761,-0.011396,0.036155,-0.012805,0.010830],
 [0.025853,0.007796,-0.001332,0.019552,0.008641,0.028323],
 [0.035549,-0.002117,-0.004037,0.029474,0.000229,0.008627],
 [0.001964,0.000109,-0.001158,0.004354,0.000341,0.005433],
 [0.012516,-0.000428,-0.001196,0.010027,-0.000741,0.004815]
])
A_DH = np.array([0,0,0,0.0825,-0.0825,0,0.088])
ALPHA_DH = np.array([0,-np.pi/2,np.pi/2,np.pi/2,-np.pi/2,np.pi/2,np.pi/2])
D_DH = np.array([0.333,0,0.316,0,0.384,0,0])
FLANGE_Z = 0.107
GRAVITY = 9.80665
PHI1 = np.array([0.54615,0.87224,0.64068,1.2794,0.83904,0.30301,0.56489])
PHI2 = np.array([5.1181,9.0657,10.136,5.5903,8.3469,17.133,10.336])
PHI3 = np.array([0.039533,0.025882,-0.04607,0.036194,0.026226,-0.021047,0.0035526])
QMIN = np.array([-2.8973,-1.7628,-2.8973,-3.0718,-2.8973,-0.0175,-2.8973])
QMAX = np.array([ 2.8973, 1.7628, 2.8973,-0.0698, 2.8973, 3.7525, 2.8973])
VMAX = np.array([2.175,2.175,2.175,2.175,2.610,2.610,2.610])
TAUMAX = np.array([87,87,87,87,12,12,12])


def inertia_tensor(six):
    xx,xy,xz,yy,yz,zz = six
    return np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]], dtype=float)


def rot_x(theta):
    c,s=np.cos(theta),np.sin(theta)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]],dtype=float)


def rot_z_np(theta):
    c,s=np.cos(theta),np.sin(theta)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]],dtype=float)


def mdh_fk_numpy(q):
    """Internal NumPy MDH product (shared constants/helpers); returns 7 link poses and flange."""
    R=np.eye(3); p=np.zeros(3); poses=[]
    for i in range(N):
        Rx=rot_x(ALPHA_DH[i]);
        # T_(i-1,i) = Tx(a) Rx(alpha) Tz(d) Rz(q_i)
        p = p+R@np.array([A_DH[i],-D_DH[i]*np.sin(ALPHA_DH[i]),D_DH[i]*np.cos(ALPHA_DH[i])])
        R = R @ Rx @ rot_z_np(float(q[i]))
        poses.append((R.copy(),p.copy()))
    return poses, (R.copy(),p+R@np.array([0.,0.,FLANGE_Z]))


def urdf_fk_numpy(q):
    """In-code URDF-origin transcription; shares rotation helpers, not source bytes."""
    xyz=np.array([[0,0,0.333],[0,0,0],[0,-0.316,0],[0.0825,0,0],
                  [-0.0825,0.384,0],[0,0,0],[0.088,0,0]],dtype=float)
    rpy=np.array([0,-np.pi/2,np.pi/2,np.pi/2,-np.pi/2,np.pi/2,np.pi/2])
    R=np.eye(3);p=np.zeros(3); poses=[]
    for i in range(N):
        p=p+R@xyz[i]; R=R@rot_x(rpy[i])@rot_z_np(float(q[i]));
        poses.append((R.copy(),p.copy()))
    return poses,(R.copy(),p+R@np.array([0.,0.,FLANGE_Z]))


def friction(qd):
    qd=np.asarray(qd,dtype=float)
    # tanh numerically stable equivalent to two logistic terms.
    return 0.5*PHI1*(np.tanh(0.5*PHI2*(qd+PHI3))-np.tanh(0.5*PHI2*PHI3))


def _rotz(t):
    c,s=ca.cos(t),ca.sin(t)
    return ca.vertcat(ca.horzcat(c,-s,0),ca.horzcat(s,c,0),ca.horzcat(0,0,1))


class PandaDynamics:
    def __init__(self):
        q=ca.MX.sym('q',N)
        R=ca.MX.eye(3); p=ca.MX.zeros(3,1)
        axes=[]; pivots=[]; M=ca.MX.zeros(N,N);potential=0
        link_positions=[]
        z0=ca.DM([0,0,1])
        for i in range(N):
            Rx=ca.DM(rot_x(ALPHA_DH[i]))
            offset=ca.DM([A_DH[i],-D_DH[i]*np.sin(ALPHA_DH[i]),D_DH[i]*np.cos(ALPHA_DH[i])])
            pivot=p+ca.mtimes(R,offset)
            axis=ca.mtimes(R,Rx)@z0
            R=ca.mtimes([R,Rx,_rotz(q[i])]); p=pivot
            pivots.append(pivot); axes.append(axis)
            center=p+ca.mtimes(R,ca.DM(COM[i])); link_positions.append(center)
            Jv=[]; Jw=[]
            for j in range(N):
                if j<=i:
                    Jv.append(ca.cross(axes[j],center-pivots[j]))
                    Jw.append(axes[j])
                else:
                    Jv.append(ca.MX.zeros(3,1)); Jw.append(ca.MX.zeros(3,1))
            Jv=ca.horzcat(*Jv); Jw=ca.horzcat(*Jw)
            Iworld=ca.mtimes([R,ca.DM(inertia_tensor(INERTIA6[i])),R.T])
            M+=MASS[i]*ca.mtimes(Jv.T,Jv)+ca.mtimes([Jw.T,Iworld,Jw])
            potential+=MASS[i]*GRAVITY*center[2]
        flange=p+R@ca.DM([0,0,FLANGE_Z])
        g=ca.gradient(potential,q)
        dM=ca.jacobian(ca.reshape(M,N*N,1),q)
        self._fun=ca.Function('gaz_seven_body_AD',[q],[M,dM,g,potential,flange],
                ['q'],['M','dM','g','U','flange'],{'cse':True})

    def evaluate(self,q,qd=None,qdd=None):
        q=np.asarray(q,dtype=float).reshape(N)
        if qd is None:qd=np.zeros(N)
        qd=np.asarray(qd,dtype=float).reshape(N)
        mat,dflat,gravity,U,flange=self._fun(q)
        M=np.asarray(mat,dtype=float)
        dflat=np.asarray(dflat,dtype=float)
        dm=np.empty((N,N,N))
        for k in range(N):dm[:,:,k]=dflat[:,k].reshape((N,N),order='F')
        C=np.empty((N,N))
        for i in range(N):
            for j in range(N):
                C[i,j]=sum(.5*(dm[i,j,k]+dm[i,k,j]-dm[j,k,i])*qd[k] for k in range(N))
        grav=np.asarray(gravity).reshape(N)
        out={'M':M,'dM':dm,'C':C,'g':grav,'F':friction(qd),
             'U':float(U),'flange':np.asarray(flange).reshape(3)}
        if qdd is not None:
            qdd=np.asarray(qdd,dtype=float).reshape(N)
            out['ID']=M@qdd+C@qd+grav+out['F']
        return out

    def acceleration(self,q,qd,tau,d=None):
        e=self.evaluate(q,qd)
        if d is None:d=np.zeros(N)
        return np.linalg.solve(e['M'],np.asarray(tau)+np.asarray(d)-e['C']@qd-e['g']-e['F'])


def dual_harmonic_disturbance(t, amplitude=0.02):
    """Protocol v1.0 proposed waveform, still awaiting team approval."""
    phi=2*np.pi*np.arange(N)/N
    a=amplitude*TAUMAX
    phase=t  # t_ref = 0, omega = 1 s^-1
    return a*(.6*np.sin(phase+phi)+.4*np.cos(2*phase+phi))


def disturbance_bounds(amplitude=0.02):
    a=amplitude*TAUMAX
    return a,1.4*a
