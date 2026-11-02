"""Numerical contracts. Units are explicit in APIs/configuration, all values SI."""
import numpy as np


def scalar(value, name, *, positive=False, nonnegative=False):
    a = np.asarray(value, dtype=float)
    if a.ndim != 0 or not np.isfinite(a):
        raise ValueError(f'{name}: expected finite scalar')
    x = float(a)
    if (positive and x <= 0) or (nonnegative and x < 0):
        raise ValueError(f'{name}: invalid sign')
    return x


def vector(value, name, size=7, *, nonnegative=False):
    a = np.asarray(value, dtype=float)
    if a.shape not in ((size,), (size, 1), (1, size)) or not np.all(np.isfinite(a)):
        raise ValueError(f'{name}: expected finite ({size},) vector')
    a = a.reshape(size).copy()
    if nonnegative and np.any(a < 0):
        raise ValueError(f'{name}: negative component')
    return a


def matrix(value, name, shape, *, nonnegative=False):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.all(np.isfinite(a)) or (nonnegative and np.any(a < 0)):
        raise ValueError(f'{name}: expected finite matrix {shape}')
    return a.copy()
