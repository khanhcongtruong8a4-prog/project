"""Available algebraic margin interfaces; no fabricated domain/tube bounds."""
import numpy as np
from .contracts import scalar, vector, matrix


def disturbance_allowances(elapsed, initial_varpi, dbar, dbar1, initial_dhat):
    t = scalar(elapsed, 'elapsed s', nonnegative=True)
    initial = vector(initial_varpi, 'varpi0', nonnegative=True)
    dbar, dbar1 = vector(dbar, 'dbar', nonnegative=True), vector(dbar1, 'dbar1', nonnegative=True)
    dhat = vector(initial_dhat, 'initial dhat')
    eta = initial+dbar1*t
    return np.minimum(eta, np.maximum(0, dbar+dhat)), np.minimum(eta, np.maximum(0, dbar-dhat))


def velocity_margin(alpha_v, lambdas, chi_v, chi_s, rho_r, varpi, Bbar, Nbar):
    """eq_margins C5. Caller must supply traceably justified bounds, not samples."""
    av = scalar(alpha_v, 'alpha_v', positive=True)
    lam = vector(lambdas, 'Lambda', nonnegative=True)
    vectors = [vector(x, name, nonnegative=True) for x, name in
               [(chi_v, 'chi_v'), (chi_s, 'chi_s'), (rho_r, 'rho_r'), (varpi, 'varpi')]]
    cv, cs, rho, vp = vectors
    B = matrix(Bbar, 'Bbar', (7, 7), nonnegative=True)
    N = matrix(Nbar, 'Nbar', (7, 7), nonnegative=True)
    return np.abs(av-lam)*cv+B@cs+N@rho+2*N@vp
