"""Stage 1 numerical/symbolic scaffold; official A3 solving stays disabled.

No model/policy input is changed here. Missing M1 margins are errors rather than
zeros. Synthetic margin fixtures are explicitly scoped and cannot authorize a
planner solve or supply planner--filter consistency evidence.
"""
from dataclasses import dataclass
from typing import Protocol
import json
import numpy as np
import casadi as ca
from scipy.interpolate import BSpline
from numpy.polynomial.legendre import leggauss
from panda_dynamics import PHI1, PHI2, PHI3
from .contracts import scalar, vector, matrix
from .reference import ReferenceSample
from .config import digest
from .readiness import source_location, m1_registry


class MissingPlanningMargin(ValueError):
    pass


class Stage1NotReady(RuntimeError):
    def __init__(self, blockers):
        self.blockers = tuple(blockers)
        super().__init__('Stage 1 official solve HOLD: '+', '.join(self.blockers))


def _array(value, shape, name, nonnegative=False):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.all(np.isfinite(a)) or (nonnegative and np.any(a < 0)):
        raise ValueError(name+': invalid finite shape/sign')
    a = a.copy()
    a.setflags(write=False)
    return a


def _sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(name+': expected lowercase SHA-256 metadata')
    return value


@dataclass(frozen=True)
class QuinticHermite:
    """Seven-joint quintic with explicit initial/final q, qd and qdd."""
    coefficients: np.ndarray
    duration: float

    def __post_init__(self):
        object.__setattr__(self, 'coefficients', _array(self.coefficients, (6, 7), 'Hermite coefficients'))
        object.__setattr__(self, 'duration', scalar(self.duration, 'T s', positive=True))

    @classmethod
    def from_boundary(cls, q0, v0, a0, q1, v1, a1, duration):
        T = scalar(duration, 'T s', positive=True)
        q0, v0, a0, q1, v1, a1 = [vector(x, n) for x, n in
            [(q0, 'q0'), (v0, 'v0'), (a0, 'a0'), (q1, 'q1'), (v1, 'v1'), (a1, 'a1')]]
        start = np.vstack([q0, T*v0, .5*T*T*a0])
        rhs = np.vstack([q1-start.sum(axis=0), T*v1-start[1]-2*start[2], T*T*a1-2*start[2]])
        end = np.linalg.solve(np.array([[1., 1., 1.], [3., 4., 5.], [6., 12., 20.]]), rhs)
        return cls(np.vstack([start, end]), T)

    @property
    def spans(self):
        return np.array([0., 1.])

    def sample(self, t):
        t = scalar(t, 'trajectory t s', nonnegative=True)
        if t > self.duration:
            raise ValueError('Trajectory requested after T')
        s, c = t/self.duration, self.coefficients
        return ReferenceSample(np.polynomial.polynomial.polyval(s, c),
            np.polynomial.polynomial.polyval(s, np.arange(1, 6)[:, None]*c[1:])/self.duration,
            np.polynomial.polynomial.polyval(s, (np.arange(2, 6)*np.arange(1, 5))[:, None]*c[2:])/self.duration**2)


@dataclass(frozen=True)
class QuinticBSpline:
    control_points: np.ndarray
    knots: np.ndarray
    duration: float

    def __post_init__(self):
        c = np.asarray(self.control_points, dtype=float)
        k = np.asarray(self.knots, dtype=float)
        if c.ndim != 2 or c.shape[1] != 7 or len(c) < 6:
            raise ValueError('Expected at least six seven-joint control points')
        if k.shape != (len(c)+6,) or not np.all(np.isfinite(k)) or np.any(np.diff(k) < 0):
            raise ValueError('Invalid degree-five knot vector')
        if not np.array_equal(k[:6], np.zeros(6)) or not np.array_equal(k[-6:], np.ones(6)):
            raise ValueError('Require clamped [0,1] quintic knots')
        if np.any(k[6:-6] <= 0) or np.any(k[6:-6] >= 1) or len(set(k[6:-6])) != len(k[6:-6]):
            raise ValueError('Require simple interior knots; no undeclared continuity change')
        object.__setattr__(self, 'control_points', _array(c, c.shape, 'control points'))
        object.__setattr__(self, 'knots', _array(k, k.shape, 'knots'))
        object.__setattr__(self, 'duration', scalar(self.duration, 'T s', positive=True))

    @classmethod
    def from_policy(cls, control_points, duration, policy):
        return cls(control_points, policy.raw['solver']['NLP_quintic_knots_normalized'], duration)

    @property
    def spans(self):
        return np.unique(self.knots)

    def basis(self, normalized_t, derivative=0):
        s = scalar(normalized_t, 'normalized trajectory time', nonnegative=True)
        if s > 1 or derivative not in [0, 1, 2]:
            raise ValueError('Invalid normalized time or derivative order')
        return BSpline(self.knots, np.eye(len(self.control_points)), 5)(s, nu=derivative)

    def sample(self, t):
        t = scalar(t, 'trajectory t s', nonnegative=True)
        if t > self.duration:
            raise ValueError('Trajectory requested after T')
        s = t/self.duration
        return ReferenceSample(self.basis(s)@self.control_points,
            self.basis(s, 1)@self.control_points/self.duration,
            self.basis(s, 2)@self.control_points/self.duration**2)

    def decision_vector(self):
        return np.r_[self.control_points.reshape(-1), self.duration]

    @classmethod
    def from_decision(cls, values, knots, control_count=12):
        x = vector(values, 'spline coefficients and free duration', 7*control_count+1)
        return cls(x[:-1].reshape(control_count, 7), knots, x[-1])


@dataclass(frozen=True)
class PlanningMargins:
    """One explicit margin sample; metadata is not a bound certificate."""
    b_u_plus: np.ndarray
    b_u_minus: np.ndarray
    chi_v: np.ndarray
    b_h: np.ndarray
    b_vB: np.ndarray
    scope: str
    domain_sha256: str
    provenance_sha256: str
    mode: str = 'M1_COMMON_FROZEN_DOMAIN_CONSTANTS'

    def __post_init__(self):
        for key, n in [('b_u_plus', 7), ('b_u_minus', 7), ('chi_v', 7), ('b_h', 15), ('b_vB', 7)]:
            object.__setattr__(self, key, _array(getattr(self, key), (n,), key, nonnegative=True))
        if self.scope not in ['SYNTHETIC_TEST_ONLY', 'M1_LEVEL_2_SUPPLIED_NOT_VALIDATED_HERE']:
            raise ValueError('Margin evidence scope must be explicit; no self-issued certification')
        if self.mode != 'M1_COMMON_FROZEN_DOMAIN_CONSTANTS':
            raise ValueError('No candidate-dependent M2 or local-Taylor baseline switch')
        _sha(self.domain_sha256, 'domain digest')
        _sha(self.provenance_sha256, 'margin provenance digest')


class MarginProvider(Protocol):
    def at(self, elapsed_s: float) -> PlanningMargins: ...


@dataclass(frozen=True)
class ConstantMarginProvider:
    """Explicit constant table, chiefly for synthetic scaffold tests.

    Actual dynamic M1 envelope construction is not implemented by this class.
    A table with real values is still supplied/unvalidated input, not A3 GO.
    """
    sample: PlanningMargins

    def at(self, elapsed_s):
        scalar(elapsed_s, 'margin elapsed time s', nonnegative=True)
        return self.sample


def shared_bus_power(tau, velocity, energy):
    tau, velocity = vector(tau, 'planned torque'), vector(velocity, 'planned velocity')
    kr = vector(energy['k_r'], 'k_r', nonnegative=True)
    epsilon = scalar(energy['nonregenerative_smoothing']['epsilon_W'], 'epsilon W', positive=True)
    bus = float(np.sum(tau*velocity+kr*tau*tau))
    return .5*(bus+np.hypot(bus, epsilon))


def normalized_quadrature(spans, points_per_span):
    spans = np.asarray(spans, dtype=float)
    if spans.ndim != 1 or len(spans) < 2 or spans[0] != 0 or spans[-1] != 1 or np.any(np.diff(spans) <= 0):
        raise ValueError('Expected increasing normalized spans including both endpoints')
    if not isinstance(points_per_span, int) or points_per_span < 1:
        raise ValueError('Positive integer quadrature order required')
    nodes, weights = leggauss(points_per_span)
    return [(float((a+b)/2+(b-a)*node/2), float(weight*(b-a)/2))
            for a, b in zip(spans[:-1], spans[1:]) for node, weight in zip(nodes, weights)]


class SymbolicPandaPlant:
    """Differentiable adapter from unchanged model AD outputs and friction bytes."""
    def __init__(self, model, geometry):
        q, v, a = ca.MX.sym('s1_q', 7), ca.MX.sym('s1_v', 7), ca.MX.sym('s1_a', 7)
        M, flat, g, _, flange = model._fun(q)
        C = ca.MX.zeros(7, 7)
        for i in range(7):
            for j in range(7):
                C[i, j] = sum(.5*(flat[i+7*j, k]+flat[i+7*k, j]-flat[j+7*k, i])*v[k] for k in range(7))
        F = .5*ca.DM(PHI1)*(ca.tanh(.5*ca.DM(PHI2)*(v+ca.DM(PHI3)))-ca.tanh(.5*ca.DM(PHI2)*ca.DM(PHI3)))
        _, _, W, gradient, hessian = geometry.function(q)
        self.function = ca.Function('stage1_source_adapter', [q, v, a],
            [M@a+C@v+g+F, flange, W, gradient, hessian], {'cse': True}).expand()


class Stage1Scaffold:
    def __init__(self, system):
        self.system = system
        self.policy = system.policy
        self.symbolic_plant = None

    def source_map(self):
        return {label: source_location(label, '03_contribution.tex') for label in
                ['eq_tau_p', 'eq_envelopes', 'eq_beta_bounds', 'eq_margins', 'eq_planner']}

    def _margins(self, provider, t):
        if provider is None:
            raise MissingPlanningMargin('M1-derived b_u+/b_u-/chi_v/b_h/b_vB missing; no zero substitution')
        value = provider.at(t)
        if not isinstance(value, PlanningMargins):
            raise MissingPlanningMargin('Margin provider did not return an explicit PlanningMargins value')
        return value

    def _reserves(self):
        p = self.system.barriers.planner_reserves(self.policy)
        return {**p, 'hocbf': np.r_[p['joint_HOCBF_rad_s2'], p['joint_HOCBF_rad_s2'], p['manip_HOCBF_m6_s2']]}

    def residual_sample(self, sample, dhat0, margins):
        q, v, a = sample.q, sample.qd, sample.qdd
        e = self.system.model.evaluate(q, v, a)
        tau = e['ID']-vector(dhat0, 'initial dhat only')
        barrier = self.system.barriers
        h, gradient, hessian = barrier.position_data(q)
        H = gradient@a+np.einsum('i,kij,j->k', v, hessian, v)
        H += (barrier.alpha1+barrier.alpha2)*(gradient@v)+barrier.alpha1*barrier.alpha2*h
        reserves = self._reserves()
        return tau, {
            'physical_position_and_manip_h': h,
            'torque_upper': barrier.taumax-tau-margins.b_u_plus-reserves['torque_Nm'],
            'torque_lower': barrier.taumax+tau-margins.b_u_minus-reserves['torque_Nm'],
            'speed_upper': barrier.vmax-v-margins.chi_v-reserves['velocity_rad_s'],
            'speed_lower': barrier.vmax+v-margins.chi_v-reserves['velocity_rad_s'],
            'hocbf': H-margins.b_h-reserves['hocbf'],
            'velocity_cbf_upper': -a+barrier.alpha_v*(barrier.vmax-v)-margins.b_vB-reserves['velocity_CBF_rad_s2'],
            'velocity_cbf_lower': a+barrier.alpha_v*(barrier.vmax+v)-margins.b_vB-reserves['velocity_CBF_rad_s2']}

    def evaluate(self, trajectory, q_start, v_start, target_xyz, dhat0, margins, normalized_nodes,
                 quadrature_points=None):
        nodes = np.asarray(normalized_nodes, dtype=float)
        if nodes.ndim != 1 or len(nodes) < 2 or nodes[0] != 0 or nodes[-1] != 1 or np.any(np.diff(nodes) <= 0):
            raise ValueError('Residual nodes must increase and include 0 and 1')
        T = trajectory.duration
        start, end = trajectory.sample(0.), trajectory.sample(T)
        target = vector(target_xyz, 'Cartesian target', 3)
        equalities = {'initial_q': start.q-vector(q_start, 'measured q_start'),
                      'initial_qd': start.qd-vector(v_start, 'measured qd_start'),
                      'terminal_qd': end.qd, 'terminal_qdd': end.qdd,
                      'terminal_cartesian': self.system.geometry.evaluate(end.q)['f']-target}
        records = []
        for s in nodes:
            sample = trajectory.sample(float(s*T))
            supplied = self._margins(margins, float(s*T))
            tau, residuals = self.residual_sample(sample, dhat0, supplied)
            records.append({'normalized_t': float(s), 'physical_elapsed_s': float(s*T), 'q': sample.q,
                            'qd': sample.qd, 'qdd': sample.qdd, 'tau_planned': tau, 'residuals': residuals,
                            'margin_scope': supplied.scope, 'margin_domain_sha256': supplied.domain_sha256})
        order = quadrature_points or self.policy.raw['solver']['NLP_energy_quadrature']['Gauss_Legendre_points_per_span_primary']
        electrical = 0.
        for s, w in normalized_quadrature(trajectory.spans, order):
            sample = trajectory.sample(s*T)
            tau = self.system.model.evaluate(sample.q, sample.qd, sample.qdd)['ID']-vector(dhat0, 'initial dhat')
            electrical += T*w*shared_bus_power(tau, sample.qd, self.policy.raw['energy'])
        energy = self.policy.raw['energy']
        duration_slacks = np.array([T-energy['T_min_s'], energy['T_max_s']-T])
        return {'scope': 'SAMPLED_SCAFFOLD_EVALUATION_NOT_PLANNER_ACCEPTANCE', 'duration_s': T,
                'electrical_energy_J': electrical, 'time_penalty_J': energy['w_t_W']*T,
                'objective_J': electrical+energy['w_t_W']*T, 'equalities': equalities,
                'duration_slacks': duration_slacks, 'samples': records,
                'all_sampled_inequalities_nonnegative': bool(np.all(duration_slacks >= 0)
                    and all(np.all(v >= 0) for record in records for v in record['residuals'].values())),
                'A3_GO': False, 'continuous_time_validity': False, 'human_signature': None}

    def build_symbolic_fixture(self, prototype, q_start, v_start, target_xyz, dhat0, margins, normalized_nodes):
        """Assemble f(x),g(x) for a synthetic constant-margin fixture; no solve.

        The real dynamic M1 symbolic-envelope provider is still missing. Do not
        present this synthetic graph as a production Stage 1 planner.
        """
        if not isinstance(prototype, QuinticBSpline) or not isinstance(margins, ConstantMarginProvider):
            raise ValueError('Symbolic development fixture requires quintic B-spline and explicit constant margins')
        m = self._margins(margins, 0.)
        if m.scope != 'SYNTHETIC_TEST_ONLY':
            raise Stage1NotReady(['DYNAMIC_M1_SYMBOLIC_MARGIN_PROVIDER_NOT_VALIDATED'])
        nodes = np.asarray(normalized_nodes, dtype=float)
        if nodes.ndim != 1 or len(nodes) < 2 or nodes[0] != 0 or nodes[-1] != 1 or np.any(np.diff(nodes) <= 0):
            raise ValueError('Normalized fixture grid must contain increasing endpoints')
        if self.symbolic_plant is None:
            self.symbolic_plant = SymbolicPandaPlant(self.system.model, self.system.geometry)
        n = len(prototype.control_points)
        x = ca.MX.sym('stage1_free_coefficients_and_T', 7*n+1)
        c, T = ca.reshape(x[:-1], 7, n).T, x[-1]
        def sample(s):
            return tuple(ca.DM(prototype.basis(s, derivative)).T@c/T**derivative for derivative in [0, 1, 2])
        q0, v0, _ = sample(0.)
        qf, vf, af = sample(1.)
        flange = self.symbolic_plant.function(qf.T, vf.T, af.T)[1]
        equalities = ca.vertcat(q0.T-vector(q_start, 'measured q_start'), v0.T-vector(v_start, 'measured v_start'),
                                 vf.T, af.T, flange-vector(target_xyz, 'target', 3))
        barrier, reserve = self.system.barriers, self._reserves()
        inequalities = [T-self.policy.raw['energy']['T_min_s'], self.policy.raw['energy']['T_max_s']-T]
        for s in nodes:
            q, v, a = [value.T for value in sample(float(s))]
            ID, _, W, gradW, hessW = self.symbolic_plant.function(q, v, a)
            tau = ID-vector(dhat0, 'initial dhat')
            h = ca.vertcat(barrier.qmax-q, q-barrier.qmin, W-barrier.w_min**2)
            gradient = ca.vertcat(-ca.DM.eye(7), ca.DM.eye(7), gradW.T)
            curvature = ca.vertcat(ca.MX.zeros(14, 1), ca.mtimes([v.T, hessW, v]))
            H = gradient@a+curvature+(barrier.alpha1+barrier.alpha2)*(gradient@v)+barrier.alpha1*barrier.alpha2*h
            inequalities.extend([h, barrier.taumax-tau-m.b_u_plus-reserve['torque_Nm'],
                barrier.taumax+tau-m.b_u_minus-reserve['torque_Nm'],
                barrier.vmax-v-m.chi_v-reserve['velocity_rad_s'], barrier.vmax+v-m.chi_v-reserve['velocity_rad_s'],
                H-m.b_h-reserve['hocbf'], -a+barrier.alpha_v*(barrier.vmax-v)-m.b_vB-reserve['velocity_CBF_rad_s2'],
                a+barrier.alpha_v*(barrier.vmax+v)-m.b_vB-reserve['velocity_CBF_rad_s2']])
        objective = self.policy.raw['energy']['w_t_W']*T
        energy = self.policy.raw['energy']
        for s, weight in normalized_quadrature(prototype.spans, self.policy.raw['solver']['NLP_energy_quadrature']['Gauss_Legendre_points_per_span_primary']):
            q, v, a = [value.T for value in sample(s)]
            tau = self.symbolic_plant.function(q, v, a)[0]-vector(dhat0, 'initial dhat')
            bus = ca.sum1(tau*v+ca.DM(energy['k_r'])*tau*tau)
            epsilon = energy['nonregenerative_smoothing']['epsilon_W']
            objective += T*weight*.5*(bus+ca.sqrt(bus*bus+epsilon*epsilon))
        ineq = ca.vertcat(*inequalities)
        g = ca.vertcat(equalities, ineq)
        fun = ca.Function('stage1_synthetic_structure', [x], [objective, g, ca.gradient(objective, x)])
        return {'x': x, 'f': objective, 'g': g, 'function': fun,
                'lbg': np.r_[np.zeros(int(equalities.numel())), np.zeros(int(ineq.numel()))],
                'ubg': np.r_[np.zeros(int(equalities.numel())), np.full(int(ineq.numel()), np.inf)],
                'equality_count': int(equalities.numel()), 'inequality_count': int(ineq.numel()),
                'scope': 'SYNTHETIC_NLP_GRAPH_ONLY_NO_OPTIMIZER_CALLED', 'official_solver_ready': False}

    def readiness(self, m1_bundle=None):
        registry = m1_registry(self.policy, 'stage1_tightened')
        required = [r['name'] for r in registry['entries'] if r['required_for_A3_stage1']]
        if m1_bundle is None:
            m1_status = {'status': 'INCOMPLETE', 'missing': required}
        else:
            m1_status = m1_bundle.status()
        blockers = ['OFFICIAL_A3_COMPARISONS_NOT_AUTHORIZED', 'INDEPENDENT_A2_ACCEPTANCE_NOT_RECORDED',
                    'DIGITAL_SAMPLER_THEORY_REVIEW_NOT_RECORDED', 'OFFICIAL_T27_ACCEPTANCE_NOT_RECORDED',
                    'POSITIVE_G2_5_NOT_ESTABLISHED', 'DYNAMIC_M1_SYMBOLIC_MARGIN_PROVIDER_NOT_VALIDATED',
                    'STAGE1_SOLVER_AND_GRID_VALIDATION_INCOMPLETE', 'T22_TASK_FREEZE_NOT_AVAILABLE',
                    '10_COMMON_COLD_START_INPUTS_NOT_FROZEN', 'SIGNED_HASHED_COMPARISON_MANIFEST_MISSING']
        if m1_status.get('missing'):
            blockers.append('M1_NUMERICAL_BOUND_REGISTRY_INCOMPLETE')
        else:
            blockers.append('M1_SUPPLIED_VALUES_NOT_OFFICIALLY_ACCEPTED')
        return {'status': 'HOLD', 'stage1_scaffold': 'IMPLEMENTED_DEVELOPMENT_ONLY',
                'M1': m1_status, 'blockers': blockers, 'approved_solver_settings_proposal': self.policy.raw['solver']['NLP_settings'],
                'NLP_version': self.policy.raw['solver']['NLP_version'], 'source_map': self.source_map(),
                'human_signatures': None, 'official_solve_executed': False}

    def solve_official(self, *args, **kwargs):
        # No nlpsol construction or solve is hidden behind a permissive flag.
        raise Stage1NotReady(self.readiness()['blockers'])
