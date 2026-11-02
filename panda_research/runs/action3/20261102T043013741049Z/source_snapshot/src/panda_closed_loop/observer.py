"""eq_observer / eq_obs_envelope. No injected true disturbance argument."""
from dataclasses import dataclass
import numpy as np
from .contracts import vector, scalar


@dataclass(frozen=True)
class DisturbanceBounds:
    magnitude: np.ndarray
    rate: np.ndarray

    def __post_init__(self):
        for name in ['magnitude', 'rate']:
            a = vector(getattr(self, name), name, nonnegative=True)
            a.setflags(write=False)
            object.__setattr__(self, name, a)


class ObserverEnvelope:
    def __init__(self, gains, initial_bound, rate_bound, t0=0.):
        self.gains = vector(gains, 'Ko s^-1')
        if np.any(self.gains <= 0):
            raise ValueError('Observer gains must be positive')
        self.initial = vector(initial_bound, 'varpi0 N m', nonnegative=True)
        self.rate = vector(rate_bound, 'dbar1 N m/s', nonnegative=True)
        self.t0 = scalar(t0, 't0 s', nonnegative=True)

    def value(self, t):
        elapsed = scalar(t, 'global t s', nonnegative=True)-self.t0
        if elapsed < 0:
            raise ValueError('Envelope before initialization')
        return np.exp(-self.gains*elapsed)*self.initial - np.expm1(-self.gains*elapsed)*self.rate/self.gains

    def restart_at(self, t):
        return ObserverEnvelope(self.gains, self.value(t), self.rate, t)


class MomentumObserver:
    def __init__(self, model, gains):
        self.model = model
        self.gains = vector(gains, 'Ko s^-1')
        if np.any(self.gains <= 0):
            raise ValueError('Observer gains must be positive')

    def initialize(self, q, qd):
        q, qd = vector(q, 'q'), vector(qd, 'qd')
        return -self.gains*(self.model.evaluate(q, qd)['M']@qd)

    def estimate(self, q, qd, z):
        q, qd, z = vector(q, 'q'), vector(qd, 'qd'), vector(z, 'z N m')
        return z+self.gains*(self.model.evaluate(q, qd)['M']@qd)

    def derivative(self, q, qd, z, tau_applied):
        q, qd, z = vector(q, 'q'), vector(qd, 'qd'), vector(z, 'z N m')
        tau = vector(tau_applied, 'actually applied torque N m')
        e = self.model.evaluate(q, qd)
        dhat = z+self.gains*(e['M']@qd)
        return -self.gains*(dhat+tau+e['C'].T@qd-e['g']-e['F'])
