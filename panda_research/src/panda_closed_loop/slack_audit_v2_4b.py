"""Roundoff-aware identity check, never a feasibility tolerance or runtime path."""
import numpy as np

def consistent_slacks(C,b,x,stored):
    C,b,x,stored=[np.asarray(v,dtype=float) for v in [C,b,x,stored]]
    residual=C@x-b;raw=1e-8-residual
    # Two evaluation paths, each with at most 40 elementary operations per
    # row: original-unit dot/add/add/divide, and normalized dot/subtract/add.
    # gamma_40 bounds forward dot-product roundoff in normal IEEE binary64.
    u=np.finfo(float).eps/2;gamma=40*u/(1-40*u)
    bound=2*gamma*(np.abs(C)@np.abs(x)+np.abs(b)+1e-8)
    finite=all(np.all(np.isfinite(v)) for v in [C,b,x,stored,raw,bound])
    signs=np.all(raw>=0) and np.all(stored>=0)
    return bool(finite and signs and np.all(abs(raw-stored)<=bound)),bound
