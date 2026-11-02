"""Read-only A3 development tools: QP diagnostics and honest M1 provenance.

No plant integration, controller update, official comparison or certified bound
is performed here. Existing policy and production QP settings remain unchanged.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from time import perf_counter
from types import MappingProxyType
import numpy as np
from scipy.optimize import linprog
from .barriers import AffineRows
from .contracts import vector, scalar
from .feasibility import pair_conditions, planner_pair_screen, pointwise_planner_lower_witness


class MissingM1Bound(ValueError):
    """A numerical value or its common-domain evidence is unavailable."""


def _hash(value):
    def serial(x):
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, dict): return {k: serial(v) for k, v in x.items()}
        return x
    return sha256(json.dumps(serial(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _hex(value, name):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(name+' must be an explicit SHA-256')


@dataclass(frozen=True)
class M1DomainSpec:
    q_lower: np.ndarray
    q_upper: np.ndarray
    v_lower: np.ndarray
    v_upper: np.ndarray
    a_lower: np.ndarray
    a_upper: np.ndarray
    tube_q_radius: np.ndarray
    tube_v_radius: np.ndarray
    position_extension_rad: float
    estimator_method: str
    seed: int
    budget: int

    def __post_init__(self):
        for name in ['q_lower', 'q_upper', 'v_lower', 'v_upper', 'a_lower', 'a_upper', 'tube_q_radius', 'tube_v_radius']:
            value = vector(getattr(self, name), name, nonnegative=name.startswith('tube_'))
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        for lo, hi in [('q_lower', 'q_upper'), ('v_lower', 'v_upper'), ('a_lower', 'a_upper')]:
            if np.any(getattr(self, lo) >= getattr(self, hi)):
                raise ValueError('Every common-domain interval must have positive width')
        object.__setattr__(self, 'position_extension_rad', scalar(self.position_extension_rad, 'q extension', nonnegative=True))
        if not isinstance(self.estimator_method, str) or not self.estimator_method.strip():
            raise ValueError('Explicit estimator method required')
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError('Explicit nonnegative integer seed required')
        if isinstance(self.budget, bool) or not isinstance(self.budget, int) or self.budget < 1:
            raise ValueError('Explicit positive estimator budget required')

    def record(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @property
    def sha256(self):
        return _hash(self.record())


@dataclass(frozen=True)
class M1BoundRecord:
    name: str
    values: np.ndarray
    units: str
    domain_sha256: str
    evaluator_sha256: str
    evidence_level: str
    method: str
    grid_sha256: str
    seed: int
    budget: int

    def __post_init__(self):
        if not self.name or not self.units or not self.method:
            raise ValueError('Bound name, units and method required')
        # None must not become an invented zero, or a silent nan.
        if self.values is None:
            raise MissingM1Bound(self.name+' has no value')
        values = np.asarray(self.values, dtype=float).copy()
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError('Bounds require finite nonnegative component values')
        if self.name == 'm1' and (values.shape != () or float(values) <= 0):
            raise ValueError('m1 must be a strictly positive scalar')
        for name in ['domain_sha256', 'evaluator_sha256', 'grid_sha256']:
            _hex(getattr(self, name), name)
        if self.evidence_level not in ['SAMPLED_LEVEL_2_ESTIMATE', 'VERIFIED_ENCLOSURE_REQUIRES_EXTERNAL_REVIEW']:
            raise ValueError('Unrecognized evidence level; no automatic certificate')
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError('Bound seed is required')
        if isinstance(self.budget, bool) or not isinstance(self.budget, int) or self.budget < 1:
            raise ValueError('Bound budget is required')
        values.setflags(write=False)
        object.__setattr__(self, 'values', values)


class M1BoundBundle:
    """Frozen evidence selectors; values remain caller assertions, not proofs."""
    REQUIRED = ('m1', 'mbar_i', 'Nbar_Q_il', 'Cbar_li', 'Abar_jl', 'Nbar_il', 'Bbar_il', 'Dbar_jl',
                'L_u_q', 'L_u_qd', 'L_u_qdd', 'L_h_q', 'L_h_qd', 'L_h_qdd')

    def __setattr__(self, name, value):
        if getattr(self, '_sealed', False):
            raise AttributeError('A common M1 bundle is immutable after construction')
        object.__setattr__(self, name, value)

    def __init__(self, domain, records, evaluator_sha256):
        if not isinstance(domain, M1DomainSpec):
            raise MissingM1Bound('A fully specified frozen common domain is required')
        _hex(evaluator_sha256, 'evaluator_sha256')
        copied = {}
        for record in records:
            if not isinstance(record, M1BoundRecord):
                raise TypeError('Use M1BoundRecord, not untyped point estimates')
            if record.name in copied:
                raise ValueError('Duplicate common bound: '+record.name)
            if record.domain_sha256 != domain.sha256 or record.evaluator_sha256 != evaluator_sha256:
                raise ValueError('Bound domain/evaluator provenance mismatch')
            if record.seed != domain.seed or record.budget != domain.budget:
                raise ValueError('Bound estimator seed/budget differs from the common frozen policy')
            copied[record.name] = record
        self.domain, self.evaluator_sha256 = domain, evaluator_sha256
        self.records = MappingProxyType(copied)
        self._sealed = True

    def require(self, name, shape, units):
        if name not in self.records:
            raise MissingM1Bound('Missing common-domain bound: '+name)
        record = self.records[name]
        if record.values.shape != tuple(shape) or record.units != units:
            raise ValueError('M1 shape/units mismatch: '+name)
        value = record.values.copy()
        value.setflags(write=False)
        return value

    def status(self, required_names=None):
        required = self.REQUIRED if required_names is None else tuple(required_names)
        missing = [n for n in required if n not in self.records]
        return {'status': 'INCOMPLETE' if missing else 'INPUTS_PRESENT_UNVERIFIED_NO_OFFICIAL_APPROVAL',
                'missing': missing, 'domain_sha256': self.domain.sha256,
                'evaluator_sha256': self.evaluator_sha256,
                'certified': False, 'official_stage1_approved': False,
                'evidence_note': 'Metadata and arithmetic validation do not validate a global enclosure or supply human approval.'}


def independent_linear_feasibility(rows):
    """Separate HiGHS LP classification for diagnostic cross-checking only."""
    if not isinstance(rows, AffineRows):
        raise TypeError('Expected AffineRows')
    solved = linprog(np.zeros(7), A_ub=-rows.G, b_ub=rows.c, bounds=[(None, None)]*7, method='highs')
    return {'solver': 'SciPy HiGHS LP, independent of ProxQP objective', 'status_code': int(solved.status),
            'message': solved.message, 'feasible': bool(solved.success),
            'tau_candidate': solved.x if solved.success else None,
            'minimum_raw_slack': float(np.min(rows.slacks(solved.x))) if solved.success else None,
            'scope': 'NUMERICAL_LINEAR_FEASIBILITY_NOT_A_CERTIFICATE'}


def diagnostic_qp(qp, nominal, rows, expected=None, name='fixture'):
    """Do not turn solver-tolerance acceptance into strict raw acceptance."""
    start = perf_counter()
    solved = qp.solve(nominal, rows)
    runtime = perf_counter()-start
    candidate = solved.applied
    if candidate is None and solved.diagnostics.get('tau_candidate') is not None:
        candidate = np.array(solved.diagnostics['tau_candidate'])
    raw = rows.slacks(candidate) if candidate is not None else None
    numeric = (raw is not None and solved.diagnostics.get('normalized_primal', np.inf) <= 1e-9
               and solved.diagnostics.get('scaled_stationarity', np.inf) <= 1e-9)
    strict = numeric and not solved.stop_requested and np.all(raw >= 0)
    oracle_error = float(np.max(abs(candidate-vector(expected, 'expected optimum')))) if expected is not None and candidate is not None else None
    return {'name': name, 'G': rows.G, 'c': rows.c, 'scales': rows.scales, 'row_names': rows.names,
            'row_units': rows.units, 'nominal': nominal, 'status': solved.status,
            'production_stop_requested': solved.stop_requested, 'actually_applied': None,
            'wall_runtime_s': runtime,
            'candidate_for_analysis_only': candidate, 'raw_slacks': raw,
            'negative_raw_rows': [] if raw is None else [rows.names[i] for i in np.where(raw < 0)[0]],
            'negative_raw_minimum': None if raw is None else float(min(0., np.min(raw))),
            'normalized_KKT_pass': bool(numeric), 'strict_raw_pass': bool(strict),
            'oracle_max_error_Nm': oracle_error,
            'oracle_error_tolerance_Nm': 1e-7 if expected is not None else None,
            'oracle_pass': None if expected is None else bool(oracle_error is not None and oracle_error <= 1e-7),
            'diagnostics': solved.diagnostics, 'independent_LP': independent_linear_feasibility(rows),
            'scope': 'READ_ONLY_DEVELOPMENT_FIXTURE_NO_ACTUATION_NO_OFFICIAL_T27'}


def synthetic_box_rows(taumax, extra_G=None, extra_c=None, extra_scales=None):
    limits = vector(taumax, 'taumax')
    G = np.vstack([-np.eye(7), np.eye(7)])
    c, scales = np.r_[limits, limits], np.r_[limits, limits]
    names = [f'box_upper_{i+1}' for i in range(7)]+[f'box_lower_{i+1}' for i in range(7)]
    if extra_G is not None:
        extra_G = np.asarray(extra_G, dtype=float)
        G = np.vstack([G, extra_G])
        c = np.r_[c, extra_c]
        scales = np.r_[scales, extra_scales]
        names += [f'synthetic_{i}' for i in range(len(extra_G))]
    return AffineRows(G, c, scales, tuple(names), tuple(['synthetic SI']*len(names)))


def active_face_fixture(rows, interior_tau, coordinate=0):
    """Construct an analytic single-face optimum from an existing full matrix.

    Deterministic first blocking row along a +coordinate ray; no control or
    trajectory search. Numerical raw-sign errors at the face are retained.
    """
    tau = vector(interior_tau, 'strict feasible center')
    slack = rows.slacks(tau)
    if np.any(slack <= 0):
        raise ValueError('A strictly feasible center is required for this fixture')
    direction = np.eye(7)[coordinate]
    slopes = rows.G@direction
    admissible = np.where(slopes < 0)[0]
    if not len(admissible):
        raise ValueError('No blocking face in the specified direction')
    k = int(admissible[np.argmin(slack[admissible]/(-slopes[admissible]))])
    boundary = tau+(slack[k]/(-slopes[k]))*direction
    normal = rows.G[k]
    nominal = boundary-normal/np.linalg.norm(normal)
    return {'nominal': nominal, 'expected': boundary, 'active_index': k,
            'active_row': rows.names[k], 'analytic_multiplier': 1/np.linalg.norm(normal),
            'reference_feasibility_minimum_raw': float(np.min(rows.slacks(boundary)))}


def screen_state(system, q, qd, dhat, varpi, label, provenance):
    """A point/node screen only; no integration or planner upper-bound fiction."""
    q, v = vector(q, 'q'), vector(qd, 'qd')
    dhat, vp = vector(dhat, 'dhat'), vector(varpi, 'varpi', nonnegative=True)
    p = system.policy
    N = np.linalg.solve(system.model.evaluate(q, v)['M'], np.eye(7))
    pair = pair_conditions(abs(N), vp, system.barriers.qmax-system.barriers.qmin,
                           system.barriers.vmax, p.alpha1, p.alpha2, p.alpha_v)
    rows = system.barriers.rows(q, v, dhat, vp)
    e = system.model.evaluate(q, v)
    nominal = e['C']@v+e['g']+e['F']-dhat
    qp = diagnostic_qp(system.qp, nominal, rows, name=label)
    physical = system.barriers.entry_conditions(q, v)
    reserves = system.barriers.planner_reserves(p)
    planner = planner_pair_screen(vp, system.barriers.qmax-system.barriers.qmin, system.barriers.vmax,
                                 p.alpha1, p.alpha2, p.alpha_v, reserves['joint_HOCBF_rad_s2'], reserves['velocity_CBF_rad_s2'])
    lower = pointwise_planner_lower_witness(abs(N), vp, system.barriers.qmax-system.barriers.qmin,
                                           system.barriers.vmax, p.alpha1, p.alpha2, p.alpha_v,
                                           reserves['joint_HOCBF_rad_s2'], reserves['velocity_CBF_rad_s2'])
    passed = (pair['velocity']['passed'] and pair['position']['passed'] and physical['passed']
              and qp['strict_raw_pass'] and qp['independent_LP']['feasible'])
    return {'label': label, 'provenance': provenance, 'q': q, 'qd': v, 'dhat': dhat, 'varpi': vp,
            'filter_pair_conditions': pair, 'initial_physical_conditions': physical,
            'torque_and_manipulability_full_43_row_QP': qp,
            'filter_point_status': 'PASS_POINT_ONLY' if passed else 'FAIL_POINT_SCREEN',
            'planner_status': 'INCOMPLETE_MISSING_COMMON_DOMAIN_M1', 'planner_pair_screen': planner,
            'planner_point_lower_witness_only': lower,
            'point_inverse_promoted_to_upper_bound': False, 'official_G2_5_positive': False,
            'scope': 'DETERMINISTIC_READ_ONLY_POINTS_NOT_FULL_G2_5_OR_GLOBAL_FEASIBILITY'}
