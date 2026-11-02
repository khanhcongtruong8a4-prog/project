"""Base-frame translational flange derivatives of the unchanged model."""
import casadi as ca
import numpy as np
from .contracts import vector, scalar


class FlangeGeometry:
    def __init__(self, model):
        q = ca.MX.sym('geometry_q', 7)
        f = model._fun(q)[4]  # frozen runtime function, flange output only
        J = ca.jacobian(f, q)
        gram = J@J.T
        # Explicit 3x3 determinant avoids unsupported generic MX Det evaluation.
        W = (gram[0,0]*(gram[1,1]*gram[2,2]-gram[1,2]*gram[2,1])
             -gram[0,1]*(gram[1,0]*gram[2,2]-gram[1,2]*gram[2,0])
             +gram[0,2]*(gram[1,0]*gram[2,1]-gram[1,1]*gram[2,0]))
        gradient = ca.gradient(W, q)
        self.function = ca.Function('flange_geometry_action3', [q], [f, J, W, gradient, ca.jacobian(gradient, q)], {'cse': True})

    def evaluate(self, q):
        f, j, w, grad, hess = self.function(vector(q, 'q'))
        result = {'f': np.asarray(f).reshape(3), 'Jv': np.asarray(j), 'W': float(w),
                  'gradient_W': np.asarray(grad).reshape(7), 'hessian_W': np.asarray(hess)}
        if not all(np.all(np.isfinite(v)) for v in result.values()):
            raise ValueError('Nonfinite kinematic derivatives')
        return result

    def floor_at(self, q0, fraction=.1):
        fraction = scalar(fraction, 'floor fraction', positive=True)
        w2 = self.evaluate(q0)['W']
        if w2 <= 0:
            raise ValueError('Degenerate initial manipulability; no automatic repair')
        return fraction*np.sqrt(w2)
