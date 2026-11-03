"""eq_controller, with e=qp-q and positive kappa M s feedback."""
import numpy as np
from .contracts import vector, scalar
from .reference import ReferenceSample


class SlotineLiController:
    def __init__(self, model, lambdas, kappa):
        self.model = model
        self.lambdas = vector(lambdas, 'Lambda s^-1')
        if np.any(self.lambdas <= 0):
            raise ValueError('Lambda must be positive')
        self.kappa = scalar(kappa, 'kappa s^-1', positive=True)

    def command(self, q, qd, reference, dhat):
        q, qd, dhat = vector(q, 'q'), vector(qd, 'qd'), vector(dhat, 'dhat N m')
        if not isinstance(reference, ReferenceSample):
            raise ValueError('Expected validated ReferenceSample')
        e, edot = reference.q-q, reference.qd-qd
        s = edot+self.lambdas*e
        qr_dot = reference.qd+self.lambdas*e
        qr_ddot = reference.qdd+self.lambdas*edot
        dynamics = self.model.evaluate(q, qd)
        tau = dynamics['M']@qr_ddot+dynamics['C']@qr_dot+dynamics['g']+dynamics['F']+self.kappa*dynamics['M']@s-dhat
        return vector(tau, 'u_nom N m'), {'e': e, 'edot': edot, 's': s, 'qr_dot': qr_dot, 'qr_ddot': qr_ddot}
