"""Assemble the selected Panda components from policy, without clearing A2."""
from dataclasses import dataclass
import numpy as np
from panda_dynamics import PandaDynamics, QMIN, QMAX, VMAX, TAUMAX, dual_harmonic_disturbance, disturbance_bounds
from .config import Policy
from .geometry import FlangeGeometry
from .barriers import BarrierEvaluator
from .controller import SlotineLiController
from .observer import MomentumObserver, DisturbanceBounds, ObserverEnvelope
from .reference import MeasuredStateReference
from .qp import HardSafetyQP
from .stepper import HoldSchedule, HeldTorqueHarness, ExecutionState
from .contracts import vector


@dataclass
class ComponentSystem:
    policy: Policy
    model: PandaDynamics
    geometry: FlangeGeometry
    barriers: BarrierEvaluator
    observer: MomentumObserver
    controller: SlotineLiController
    qp: HardSafetyQP
    bounds: DisturbanceBounds

    def initialized_fixture(self, q=None, qd=None, t0=0.):
        q = (QMIN+QMAX)/2 if q is None else vector(q, 'q0')
        qd = np.zeros(7) if qd is None else vector(qd, 'qd0')
        state = ExecutionState(q, qd, self.observer.initialize(q, qd), t0)
        envelope = ObserverEnvelope(self.policy.ko, self.bounds.magnitude, self.bounds.rate, t0)
        # Global t is deliberately passed through; replanning never rebases it.
        waveform = lambda t: dual_harmonic_disturbance(t, self.policy.raw['disturbance']['amplitude_fraction'])
        harness = HeldTorqueHarness(self.model, self.observer, self.controller, self.barriers, self.qp,
            envelope, MeasuredStateReference(q, qd, t0), HoldSchedule(self.policy.delta, self.policy.h), waveform)
        return harness, state


def build_components(policy=None):
    policy = policy or Policy.load()
    policy.source_audit()
    model = PandaDynamics()
    geometry = FlangeGeometry(model)
    # The floor always uses the frozen physical-box midpoint, not a chosen
    # current state or a favorable new reference.
    w_min = geometry.floor_at((QMIN+QMAX)/2)
    barriers = BarrierEvaluator(model, geometry, QMIN, QMAX, VMAX, TAUMAX, w_min,
                                 policy.alpha1, policy.alpha2, policy.alpha_v)
    bounds = DisturbanceBounds(*disturbance_bounds(policy.raw['disturbance']['amplitude_fraction']))
    return ComponentSystem(policy, model, geometry, barriers, MomentumObserver(model, policy.ko),
        SlotineLiController(model, policy.lambdas, policy.kappa),
        HardSafetyQP(TAUMAX, policy.raw['solver']['QP_settings']), bounds)
