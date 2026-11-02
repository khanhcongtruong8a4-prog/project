"""eq_hocbf / eq_robust_cbf: 15 position-level, 14 speed, 14 torque rows."""
from dataclasses import dataclass
import numpy as np
from .contracts import vector, scalar, matrix


@dataclass(frozen=True)
class AffineRows:
    G: np.ndarray
    c: np.ndarray
    scales: np.ndarray
    names: tuple
    units: tuple

    def __post_init__(self):
        n = len(self.names)
        G, c = matrix(self.G, 'row G', (n, 7)), vector(self.c, 'row c', n)
        G.setflags(write=False); c.setflags(write=False)
        object.__setattr__(self, 'G', G)
        object.__setattr__(self, 'c', c)
        scales = vector(self.scales, 'positive row scales', n)
        if np.any(scales <= 0) or len(self.units) != n:
            raise ValueError('Invalid row normalization/units')
        scales.setflags(write=False)
        object.__setattr__(self, 'scales', scales)

    def slacks(self, tau):
        return self.G@vector(tau, 'tau N m')+self.c


class BarrierEvaluator:
    def __init__(self, model, geometry, qmin, qmax, vmax, taumax, w_min, alpha1, alpha2, alpha_v):
        self.model, self.geometry = model, geometry
        self.qmin, self.qmax = vector(qmin, 'qmin rad'), vector(qmax, 'qmax rad')
        self.vmax, self.taumax = vector(vmax, 'vmax rad/s'), vector(taumax, 'taumax N m')
        if np.any(self.qmin >= self.qmax) or np.any(self.vmax <= 0) or np.any(self.taumax <= 0):
            raise ValueError('Invalid physical limits')
        self.w_min = scalar(w_min, 'w_min m^3', positive=True)
        self.alpha1 = scalar(alpha1, 'alpha1 s^-1', positive=True)
        self.alpha2 = scalar(alpha2, 'alpha2 s^-1', positive=True)
        self.alpha_v = scalar(alpha_v, 'alpha_v s^-1', positive=True)

    def position_data(self, q):
        q = vector(q, 'q')
        k = self.geometry.evaluate(q)
        h = np.r_[self.qmax-q, q-self.qmin, k['W']-self.w_min**2]
        gradients = np.vstack([-np.eye(7), np.eye(7), k['gradient_W']])
        hessians = np.zeros((15, 7, 7))
        hessians[-1] = k['hessian_W']
        return h, gradients, hessians

    def rows(self, q, qd, dhat, varpi):
        q, v = vector(q, 'q'), vector(qd, 'qd')
        dhat, varpi = vector(dhat, 'dhat N m'), vector(varpi, 'varpi N m', nonnegative=True)
        e = self.model.evaluate(q, v)
        M = matrix(e['M'], 'M', (7, 7))
        np.linalg.cholesky(M)
        if not np.allclose(M, M.T, atol=1e-12, rtol=0):
            raise ValueError('Asymmetric mass matrix')
        N = np.linalg.solve(M, np.eye(7))
        h, gradient, hessian = self.position_data(q)
        A = np.linalg.solve(M.T, gradient.T).T
        bias = dhat-e['C']@v-e['g']-e['F']
        cpos = A@bias+np.einsum('i,kij,j->k', v, hessian, v)
        cpos += (self.alpha1+self.alpha2)*(gradient@v)+self.alpha1*self.alpha2*h
        cpos -= np.abs(A)@varpi
        margin_v = np.abs(N)@varpi
        G = np.vstack([A, -N, N, -np.eye(7), np.eye(7)])
        c = np.r_[cpos, -N@bias+self.alpha_v*(self.vmax-v)-margin_v,
                  N@bias+self.alpha_v*(self.vmax+v)-margin_v, self.taumax, self.taumax]
        scales = np.r_[self.qmax-self.qmin, self.qmax-self.qmin, self.w_min**2,
                       self.vmax, self.vmax, self.taumax, self.taumax]
        names = tuple([f'q_upper_{i+1}' for i in range(7)]+[f'q_lower_{i+1}' for i in range(7)]+['manipulability']+
                      [f'v_upper_{i+1}' for i in range(7)]+[f'v_lower_{i+1}' for i in range(7)]+
                      [f'torque_upper_{i+1}' for i in range(7)]+[f'torque_lower_{i+1}' for i in range(7)])
        units = tuple(['rad/s^2']*14+['m^6/s^2']+['rad/s^2']*14+['N m']*14)
        return AffineRows(G, c, scales, names, units)

    def entry_conditions(self, q, qd, tau=None):
        q, v = vector(q, 'q'), vector(qd, 'qd')
        h, gradient, _ = self.position_data(q)
        result = {'position_and_manip_h': h, 'psi1': gradient@v+self.alpha1*h,
                  'speed_upper': self.vmax-v, 'speed_lower': self.vmax+v}
        if tau is not None:
            tau = vector(tau, 'tau')
            result.update(torque_upper=self.taumax-tau, torque_lower=self.taumax+tau)
        result['passed'] = all(np.all(x >= 0) for x in result.values())
        return result

    def planner_reserves(self, policy):
        """T16 interfaces only. NOT added silently to the execution hard QP."""
        raw = policy.raw['physical_parameters']
        eta, t = raw['eta_delta'], raw['normalization_time_s']
        return {'joint_HOCBF_rad_s2': eta*(self.qmax-self.qmin)/t**2,
                'manip_HOCBF_m6_s2': eta*self.w_min**2/t**2,
                'velocity_CBF_rad_s2': raw['barrier_reserves']['velocity_CBF_delta_vB_rad_s2'],
                'velocity_rad_s': raw['velocity_reserve_rad_s'], 'torque_Nm': raw['torque_reserve_Nm']}
