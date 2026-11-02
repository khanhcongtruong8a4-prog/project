"""Measured-state trajectory fixture, not an optimized Stage-1 trajectory."""
from dataclasses import dataclass
import numpy as np
from .contracts import vector, scalar


@dataclass(frozen=True)
class ReferenceSample:
    q: np.ndarray
    qd: np.ndarray
    qdd: np.ndarray

    def __post_init__(self):
        for name in ['q', 'qd', 'qdd']:
            a = vector(getattr(self, name), name)
            a.setflags(write=False)
            object.__setattr__(self, name, a)


class MeasuredStateReference:
    """Constant-velocity reference fixture matching measured q and qd at epoch."""
    def __init__(self, q, qd, t0):
        self.q0, self.qd0 = vector(q, 'q0'), vector(qd, 'qd0')
        self.t0 = scalar(t0, 't0 s', nonnegative=True)

    def sample(self, t):
        t = scalar(t, 'global t s', nonnegative=True)
        if t < self.t0:
            raise ValueError('Reference requested before its epoch')
        return ReferenceSample(self.q0+(t-self.t0)*self.qd0, self.qd0, np.zeros(7))
