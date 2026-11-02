"""Predeclared nonoptimized 1 s references and additive r4 validation adapters."""
from types import FunctionType
import multiprocessing as mp
import numpy as np
from .contracts import scalar, vector
from .a2_plan import quintic_reference_coefficients
from .reference import ReferenceSample
from .feasibility import pair_conditions
from . import p1_r4
from .qp import HardSafetyQP, QPResult


def _qp_service(connection, limits, settings):
    solver = HardSafetyQP(limits, settings)
    try:
        while True:
            request = connection.recv()
            if request is None:
                break
            try:
                connection.send(solver.solve(*request))
            except Exception as error:
                connection.send(QPResult(None, 'SOLVER_SERVICE_ERROR', True, {'error': repr(error)}))
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


class BoundedQP:
    """Same cold production QP mathematics in a bounded, isolated service.

    A wall-time expiry means UNKNOWN/no actuation, not primal infeasibility.
    There is no retry or changed solver setting. This bounds engineering hangs
    while preserving the complete attempted update and preceding plant trace.
    """
    def __init__(self, limits, settings, timeout_s):
        self.limits, self.settings = vector(limits, 'torque limits'), dict(settings)
        self.timeout_s = scalar(timeout_s, 'QP engineering timeout', positive=True)
        self.process, self.connection = None, None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _start(self):
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_qp_service, args=(child, self.limits, self.settings), daemon=True)
        self.process.start()
        child.close()

    def solve(self, nominal, rows):
        if self.process is None:
            self._start()
        self.connection.send((nominal, rows))
        if self.connection.poll(self.timeout_s):
            try:
                return self.connection.recv()
            except EOFError:
                self.close()
                return QPResult(None, 'SOLVER_SERVICE_EXIT_UNKNOWN', True, {'torque_applied': False})
        self.close()
        return QPResult(None, 'SOLVER_WALL_TIMEOUT_UNKNOWN', True,
                        {'wall_time_budget_s': self.timeout_s, 'classification': 'UNKNOWN_NOT_INFEASIBLE',
                         'torque_applied': False, 'retry': False, 'replan_requested': True})

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2.)
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None


class ExtendedReference:
    """C2 piecewise quintics, matched to the actual post-P1 q and qd.

    Only prescribed net-transfer coordinates are selected; the remaining
    coordinates retain the small Hermite transients needed to match measured
    nonzero initial velocities. No midpoint/zero-velocity replacement occurs.
    """
    def __init__(self, q_start, v_start, definition):
        q, v = vector(q_start, 'measured q_start'), vector(v_start, 'measured qd_start')
        self.duration = scalar(definition['duration_s'], 'T s', positive=True)
        self.boundaries = np.asarray(definition['normalized_boundaries'], dtype=float)*self.duration
        offsets = np.asarray(definition['waypoint_offsets_rad'], dtype=float)
        if self.boundaries[0] != 0. or self.boundaries[-1] != self.duration or np.any(np.diff(self.boundaries) <= 0):
            raise ValueError('Invalid fixed segment boundaries')
        if offsets.shape != (len(self.boundaries), 7) or not np.all(np.isfinite(offsets)) or np.any(offsets[0] != 0):
            raise ValueError('Invalid fixed waypoint offsets')
        self.coefficients = []
        for index, (a, b) in enumerate(zip(self.boundaries[:-1], self.boundaries[1:])):
            self.coefficients.append(quintic_reference_coefficients(q+offsets[index],
                v if index == 0 else np.zeros(7), offsets[index+1]-offsets[index], b-a))
        self.coefficients = np.array(self.coefficients)
        self.target_q = q+offsets[-1]

    def sample(self, t):
        t = scalar(t, 'physical execution time', nonnegative=True)
        if t > self.duration+1e-12:
            raise ValueError('Reference beyond frozen duration')
        t = min(t, self.duration)
        segment = min(np.searchsorted(self.boundaries, t, side='right')-1, len(self.coefficients)-1)
        a, b = self.boundaries[segment:segment+2]
        s = (t-a)/(b-a)
        c = self.coefficients[segment]
        return ReferenceSample(np.polynomial.polynomial.polyval(s, c),
            np.polynomial.polynomial.polyval(s, np.arange(1, 6)[:, None]*c[1:])/(b-a),
            np.polynomial.polynomial.polyval(s, (np.arange(2, 6)*np.arange(1, 5))[:, None]*c[2:])/(b-a)**2)


def reference_screen(system, reference, nodes):
    """Fixed sampled reference-state checks; no claim of full planner feasibility."""
    values = []
    for t in nodes:
        r = reference.sample(float(t))
        physical = system.barriers.entry_conditions(r.q, r.qd)
        values.append({'t_s': float(t), 'q': r.q, 'qd': r.qd, 'qdd': r.qdd,
                       'physical_slacks': physical})
    return {'passed': all(v['physical_slacks']['passed'] for v in values),
            'samples': values, 'scope': 'FIXED_SAMPLED_REFERENCE_STATE_SCREEN_NOT_TORQUE_OR_M1_PLANNER_CERTIFICATE'}


def entrance_pairs(system, state, varpi):
    N = np.linalg.solve(system.model.evaluate(state.q, state.qd)['M'], np.eye(7))
    p = system.policy
    return pair_conditions(abs(N), varpi, system.barriers.qmax-system.barriers.qmin,
                           system.barriers.vmax, p.alpha1, p.alpha2, p.alpha_v)


def audit_extended(cell, out, system, plan):
    """Reuse the unchanged r4 mathematical auditor with codec-only input I/O.

    No mutation of the r4 module or its acceptance rules is made: the function
    is rebound to a globals copy whose only replacement is the trace loader.
    """
    from .trace_archive import read_trace
    loader = lambda folder, record: read_trace(folder/record['file'], record)
    original = p1_r4.audit_cell
    globals_copy = dict(original.__globals__)
    globals_copy['_load_trace'] = loader
    compatible = FunctionType(original.__code__, globals_copy, name='r4_audit_columnar_IO')
    result = compatible(cell, out, system, plan)
    motion = loader(out, cell['a2']['trace'])
    definition = plan['references'][cell['reference_id']]
    reference = ExtendedReference(cell['endpoint']['state']['q'], cell['endpoint']['state']['qd'], definition)
    reference_exact = all(all(np.array_equal(getattr(reference.sample(u['physical_t_s']), key), u['reference'][key])
                              for key in ['q', 'qd', 'qdd']) for u in motion['updates'])
    result['checks']['logged_reference_matches_predeclaration'] = reference_exact
    result['passed'] = bool(result['passed'] and reference_exact)
    result['codec_adapter_scope'] = 'UNCHANGED_R4_AUDIT_BYTECODE_WITH_LOSSLESS_TRACE_LOADER_ONLY'
    return result


def difference_statistics(updates):
    applied = [u for u in updates if u.get('torque_applied') and u.get('candidate_tau') is not None]
    if not applied:
        return {'updates': 0, 'statistics': {}, 'scope': 'NO_APPLIED_UPDATES'}
    r = np.array([u['tracking_errors']['continuous_request_Nm'] for u in applied])
    digital = np.array([u['u_nom'] for u in applied])
    tau = np.array([u['candidate_tau'] for u in applied])
    stats = {}
    for name, a in [('u_minus_r', digital-r), ('tau_minus_u', tau-digital), ('tau_minus_r', tau-r)]:
        norms = np.linalg.norm(a, axis=1)
        stats[name] = {'max_2norm_Nm': float(max(norms)), 'RMS_2norm_Nm': float(np.sqrt(np.mean(norms**2))),
                       'component_max_abs_Nm': np.max(abs(a), axis=0),
                       'component_RMS_Nm': np.sqrt(np.mean(a*a, axis=0))}
    return {'updates': len(applied), 'statistics': stats,
            'norm': '7-joint Euclidean norm; RMS over uniform control updates equals time-weighted RMS per cell',
            'scope': 'NUMERICAL_CORRECTIONS_NOT_A_CONTINUOUS_THEOREM_OR_SOLVER_ERROR_BOUND'}


def negative_slack_report(motion):
    """Retain every negative raw value, including rejected QP candidates."""
    negatives = []
    for update in motion['updates']:
        raw = update.get('raw_slacks')
        if raw is None:
            raw = update.get('diagnostics', {}).get('raw_slacks')
        if raw is not None:
            names = update['row_names']
            for j in np.where(np.array(raw) < 0)[0]:
                negatives.append({'t_s': update['physical_t_s'], 'kind': 'QP_RAW', 'row': names[j],
                                  'value': float(raw[j]), 'torque_applied': update['torque_applied']})
    for step in motion['substeps']:
        for sample in step['samples']:
            for name, array in sample['physical_slacks'].items():
                if name == 'passed':
                    continue
                for j in np.where(np.array(array) < 0)[0]:
                    negatives.append({'t_s': sample['physical_t_s'], 'kind': 'PHYSICAL', 'row': name+f'[{j}]',
                                      'value': float(array[j]), 'torque_applied': True})
            for j in np.where(np.array(sample['observer_envelope_slack']) < 0)[0]:
                negatives.append({'t_s': sample['physical_t_s'], 'kind': 'OBSERVER', 'row': f'joint_{j+1}',
                                  'value': float(sample['observer_envelope_slack'][j]), 'torque_applied': True})
    return {'negative_count': len(negatives), 'negative_values': negatives,
            'raw_negative_rule': 'Any negative is a failure; no numerical-resolution exception'}
