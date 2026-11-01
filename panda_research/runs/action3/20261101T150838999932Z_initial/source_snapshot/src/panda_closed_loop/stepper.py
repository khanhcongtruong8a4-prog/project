"""ZOH torque with coupled RK4 [q,qd,z]. Component-test convention, not A2."""
from dataclasses import dataclass
import numpy as np
from .contracts import vector, scalar
from .reference import MeasuredStateReference


class ProtectiveStop(RuntimeError):
    def __init__(self, reason, diagnostics):
        super().__init__(reason)
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class HoldSchedule:
    delta: float
    h: float

    def __post_init__(self):
        delta, h = scalar(self.delta, 'Delta s', positive=True), scalar(self.h, 'h s', positive=True)
        if delta/h < 1 or abs(delta/h-round(delta/h)) > 1e-12:
            raise ValueError('Delta/h must be a positive integer')
        object.__setattr__(self, 'delta', delta)
        object.__setattr__(self, 'h', h)

    @property
    def substeps(self):
        return round(self.delta/self.h)


@dataclass(frozen=True)
class ExecutionState:
    q: np.ndarray
    qd: np.ndarray
    z: np.ndarray
    t: float

    def __post_init__(self):
        for name in ['q', 'qd', 'z']:
            a = vector(getattr(self, name), name)
            a.setflags(write=False)
            object.__setattr__(self, name, a)
        object.__setattr__(self, 't', scalar(self.t, 'global time s', nonnegative=True))


class HeldTorqueHarness:
    observer_semantics = 'COUPLED_RK4_MEASURED_STAGE_STATES_AND_HELD_APPLIED_TORQUE; COMPONENT_TEST_CONVENTION_NOT_POLICY_APPROVED'

    def __init__(self, model, observer, controller, barrier, qp, envelope, reference, schedule, plant_disturbance):
        self.model, self.observer, self.controller = model, observer, controller
        self.barrier, self.qp, self.envelope, self.reference = barrier, qp, envelope, reference
        self.schedule, self._plant_disturbance = schedule, plant_disturbance
        self.controller_updates = 0

    def replan_from_measured(self, state):
        self.reference = MeasuredStateReference(state.q, state.qd, state.t)
        # z, t and the original propagated envelope are NOT reset.
        return state

    def advance(self, state):
        if not isinstance(state, ExecutionState):
            raise ValueError('Expected validated ExecutionState')
        initial = self.barrier.entry_conditions(state.q, state.qd)
        if not initial['passed']:
            raise ProtectiveStop('Initial h/psi1/speed conditions fail', {'initial': initial})
        estimate = self.observer.estimate(state.q, state.qd, state.z)
        nominal, errors = self.controller.command(state.q, state.qd, self.reference.sample(state.t), estimate)
        self.controller_updates += 1
        varpi = self.envelope.value(state.t)
        rows = self.barrier.rows(state.q, state.qd, estimate, varpi)
        filtered = self.qp.solve(nominal, rows)
        if filtered.stop_requested or filtered.applied is None:
            raise ProtectiveStop('Hard QP unavailable; no torque applied or state advanced', {'qp': filtered.diagnostics, 'status': filtered.status})
        held = vector(filtered.applied, 'actually applied torque')
        stages = []
        stage_slacks = []
        def derivative(t, x):
            q, v, z = x[:7], x[7:14], x[14:]
            d = vector(self._plant_disturbance(t), 'plant-only disturbance')
            dynamics = self.model.evaluate(q, v)
            acceleration = np.linalg.solve(dynamics['M'], held+d-dynamics['C']@v-dynamics['g']-dynamics['F'])
            zdot = self.observer.derivative(q, v, z, held)
            stages.append({'t': t, 'applied_tau': held.copy()})
            stage_slacks.append(self.barrier.entry_conditions(q, v, held))
            return np.r_[v, acceleration, zdot]
        x = np.r_[state.q, state.qd, state.z]
        h = self.schedule.h
        for j in range(self.schedule.substeps):
            t = state.t+j*h
            k1 = derivative(t, x)
            k2 = derivative(t+h/2, x+h*k1/2)
            k3 = derivative(t+h/2, x+h*k2/2)
            k4 = derivative(t+h, x+h*k3)
            x += h*(k1+2*k2+2*k3+k4)/6
        after = ExecutionState(x[:7], x[7:14], x[14:], state.t+self.schedule.delta)
        final_dhat = self.observer.estimate(after.q, after.qd, after.z)
        # Truth is collected AFTER all control/observer updates, only for diagnostics.
        truth = vector(self._plant_disturbance(after.t), 'diagnostic truth')
        final_slacks = self.barrier.entry_conditions(after.q, after.qd, held)
        reference_end = self.reference.sample(after.t)
        terminal_error = float(np.linalg.norm(self.barrier.geometry.evaluate(after.q)['f']-
                                              self.barrier.geometry.evaluate(reference_end.q)['f']))
        log = {'scope': 'COMPONENT_FIXTURE_NOT_A2', 't0': state.t, 't1': after.t,
               'q0': state.q, 'qd0': state.qd, 'q1': after.q, 'qd1': after.qd, 'z1': after.z,
               'u_nom': nominal, 'tau_applied': held, 'dhat0': estimate, 'dhat1': final_dhat,
               'truth_post_run_only': truth, 'observer_error': truth-final_dhat,
               'analytic_varpi': self.envelope.value(after.t),
               'observer_envelope_slack': self.envelope.value(after.t)-np.abs(truth-final_dhat),
               'tracking_errors_at_update': errors, 'initial_conditions': initial,
               'stage_physical_slacks': stage_slacks, 'final_conditions': final_slacks,
               'terminal_reference_error_m': terminal_error, 'QP': filtered.diagnostics,
               'intervention_Nm': float(np.linalg.norm(held-nominal)), 'rk4_stages': stages,
               'observer_semantics': self.observer_semantics,
               'all_checked_physical_slacks_nonnegative': all(s['passed'] for s in stage_slacks+[final_slacks]),
               'uncomputed_tracking_tube_slacks': 'BLOCKED: M1 constants not supplied; no zero substitution'}
        return after, log
