"""Versioned numerical hard-QP realization; original model/rows are untouched.

Solve the same physical least-squares objective with a declared inward
roundoff guard on every original row. A single cold ProxQP solve is used.
There is no projection, retry, fallback, truth input or post-solve repair.
The original zero-negative rule and T29 targets still gate every application.
"""
import multiprocessing as mp
import numpy as np
import proxsuite
from .contracts import vector
from .barriers import AffineRows
from .qp import QPResult


NUMERICAL_POLICY = {
    'version': 'A2_QP_NUMERICS_V2',
    'variable': 'y=tau/87 N m; isotropic Hessian I',
    'constraint_scaling': 'Euclidean unit normal in y, positive row scaling only',
    'inward_guard_original_row_scale': 1e-8,
    'guard_rule': 'G tau+c >= 1e-8 * original row scale',
    'eps_abs': 1e-12,
    'eps_rel': 0.,
    'max_iter': 10000,
    'check_duality_gap': True,
    'eps_duality_gap_abs': 1e-12,
    'eps_duality_gap_rel': 0.,
    'original_normalized_primal_target': 1e-9,
    'original_scaled_stationarity_target': 1e-9,
    'wall_budget_s': 15.,
    'retry': False,
    'post_QP_projection': False,
}


class GuardedHardQP:
    def __init__(self, taumax, settings=None):
        self.taumax = vector(taumax, 'taumax')
        self.settings = dict(NUMERICAL_POLICY)
        if settings is not None and dict(settings) != NUMERICAL_POLICY:
            raise ValueError('Use the exact versioned numerical policy')

    def solve(self, u_nom, rows):
        nominal = vector(u_nom, 'u_nom')
        if not isinstance(rows, AffineRows):
            raise ValueError('Expected original AffineRows')
        guard = NUMERICAL_POLICY['inward_guard_original_row_scale']*rows.scales
        den = 87.*np.linalg.norm(rows.G, axis=1)
        # Zero normals cannot be scaled; retain their affine constant test.
        den = np.where(den > 0., den, 1.)
        C, b = -87.*rows.G/den[:, None], (rows.c-guard)/den
        H, g = np.eye(7), -nominal/87.
        solver = proxsuite.proxqp.dense.QP(7, 0, len(b))
        for k in ['eps_abs', 'eps_rel', 'max_iter', 'check_duality_gap',
                  'eps_duality_gap_abs', 'eps_duality_gap_rel']:
            setattr(solver.settings, k, NUMERICAL_POLICY[k])
        diagnostics = {
            'solver': 'ProxQP '+proxsuite.__version__, 'settings': self.settings,
            'row_names': rows.names, 'row_units': rows.units,
            'row_scales': rows.scales.tolist(), 'row_scaling_denominator': den.tolist(),
            'inward_guard_raw': guard.tolist(),
            'recovery': 'DISABLED', 'replan_requested': False,
            'cold_solves': 1, 'post_solve_repair': False,
        }
        try:
            solver.init(H, g, None, None, C, np.full(len(b), -np.inf), b)
            solver.solve()
        except Exception as error:
            diagnostics.update(error=str(error), replan_requested=True)
            return QPResult(None, 'SOLVER_ERROR', True, diagnostics)
        result, info = solver.results, solver.results.info
        status = str(info.status)
        diagnostics.update(iterations=int(info.iter), duality_gap=float(info.duality_gap))
        if info.status != proxsuite.proxqp.QPSolverOutput.PROXQP_SOLVED:
            diagnostics.update(replan_requested=True)
            return QPResult(None, status, True, diagnostics)
        y, dual = np.asarray(result.x).copy(), np.asarray(result.z).copy()
        tau = y*87.
        if not np.all(np.isfinite(tau)) or not np.all(np.isfinite(dual)):
            return QPResult(None, 'NONFINITE_SOLUTION', True, diagnostics)
        raw = rows.slacks(tau)
        # Recompute in the ORIGINAL T29 variables and row normalization.
        theta = tau/self.taumax
        original_C = -rows.G*self.taumax[None, :]/rows.scales[:, None]
        original_b = rows.c/rows.scales
        original_dual = dual*rows.scales/den
        original_H = np.diag(self.taumax**2)/87.**2
        original_g = -self.taumax*nominal/87.**2
        primal = float(max(0., np.max(original_C@theta-original_b)))
        stationarity = float(np.max(abs(original_H@theta+original_g+original_C.T@original_dual)))
        guarded_primal = float(max(0., np.max(C@y-b)))
        guarded_stationarity = float(np.max(abs(y+g+C.T@dual)))
        diagnostics.update(
            tau_candidate=tau.tolist(), dual_original=original_dual.tolist(),
            dual_scaled=dual.tolist(), raw_slacks=raw.tolist(),
            normalized_slacks=(raw/rows.scales).tolist(),
            exact_all_rows_nonnegative=bool(np.all(raw >= 0)),
            negative_raw_row_count=int(np.sum(raw < 0)),
            normalized_primal=primal, scaled_stationarity=stationarity,
            guarded_normalized_primal=guarded_primal,
            guarded_scaled_stationarity=guarded_stationarity,
            complementarity=float(np.max(abs(original_dual*(original_C@theta-original_b)))),
            guarded_complementarity=float(np.max(abs(dual*(C@y-b)))),
            negative_upper_dual=float(max(0., np.max(-original_dual))),
            intervention_Nm=float(np.linalg.norm(tau-nominal)),
            torque_upper_slack=(self.taumax-tau).tolist(),
            torque_lower_slack=(self.taumax+tau).tolist(),
            numerical_solver_acceptance_not_invariance_proof=True)
        accepted = bool(primal <= 1e-9 and stationarity <= 1e-9
                        and guarded_primal <= 1e-9 and guarded_stationarity <= 1e-9
                        and np.all(raw >= 0) and np.all(self.taumax-abs(tau) >= 0))
        diagnostics['replan_requested'] = not accepted
        return QPResult(tau if accepted else None,
                        status if accepted else 'NUMERICAL_OR_RAW_ROW_REJECTION', not accepted, diagnostics)


def _worker(connection, limits):
    qp = GuardedHardQP(limits)
    try:
        connection.send('READY')
        while True:
            payload = connection.recv()
            if payload is None:
                break
            connection.send(qp.solve(*payload))
    finally:
        connection.close()


class BoundedGuardedQP:
    """One solve per query; timeout is UNKNOWN and ends the cell."""
    def __init__(self, taumax, settings=None, timeout_s=15.):
        if settings is not None and dict(settings) != NUMERICAL_POLICY:
            raise ValueError('Changed frozen numerical policy')
        self.taumax = vector(taumax, 'taumax')
        self.settings = dict(NUMERICAL_POLICY)
        if timeout_s != NUMERICAL_POLICY['wall_budget_s']:
            raise ValueError('Changed wall budget')
        self.timeout_s, self.process, self.connection = timeout_s, None, None

    def __enter__(self):
        ctx = mp.get_context('spawn')
        self.connection, child = ctx.Pipe()
        self.process = ctx.Process(target=_worker, args=(child, self.taumax), daemon=True)
        self.process.start(); child.close()
        if not self.connection.poll(self.timeout_s) or self.connection.recv() != 'READY':
            self.close()
            raise RuntimeError('QP worker did not initialize')
        return self

    def __exit__(self, *args):
        self.close()

    def solve(self, u_nom, rows):
        if self.process is None or not self.process.is_alive():
            return QPResult(None, 'QP_WORKER_UNAVAILABLE', True, {'replan_requested': True})
        self.connection.send((u_nom, rows))
        if self.connection.poll(self.timeout_s):
            return self.connection.recv()
        self.close()
        return QPResult(None, 'QP_QUERY_WALL_BUDGET_UNKNOWN', True,
                        {'timeout_s': self.timeout_s, 'classification': 'UNKNOWN_NOT_INFEASIBLE',
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


def audit_qp_numerics(updates, taumax):
    """Recompute both KKT scalings using the retained duals, without solving."""
    limits=vector(taumax,'taumax')
    checks={'exact_versioned_policy':True,'original_raw_signs':True,
            'both_primal_and_stationarity_targets':True,'nonnegative_dual_and_guarded_complementarity':True,
            'candidate_and_applied_identical':True}
    maxima={'original_normalized_primal':0.,'original_scaled_stationarity':0.,
            'guarded_primal':0.,'guarded_stationarity':0.,'guarded_complementarity':0.}
    for u in updates:
        d=u['diagnostics'];G=np.array(u['G']);c=np.array(u['c']);s=np.array(u['row_scales'])
        tau=np.array(u['candidate_tau']);nom=np.array(u['u_nom']);theta=tau/limits;y=tau/87.
        den=87.*np.linalg.norm(G,axis=1);den=np.where(den>0.,den,1.)
        C=-G*limits[None,:]/s[:,None];b=c/s;dual=np.array(d['dual_original'])
        Cs=-87.*G/den[:,None];bs=(c-NUMERICAL_POLICY['inward_guard_original_row_scale']*s)/den
        ds=np.array(d['dual_scaled'])
        values={'original_normalized_primal':float(max(0.,np.max(C@theta-b))),
                'original_scaled_stationarity':float(np.max(abs(limits*(tau-nom)/87.**2+C.T@dual))),
                'guarded_primal':float(max(0.,np.max(Cs@y-bs))),
                'guarded_stationarity':float(np.max(abs(y-nom/87.+Cs.T@ds))),
                'guarded_complementarity':float(np.max(abs(ds*(Cs@y-bs))))}
        for k,v in values.items():maxima[k]=max(maxima[k],v)
        checks['exact_versioned_policy'] &= d['settings']==NUMERICAL_POLICY and d['cold_solves']==1 and not d['post_solve_repair']
        raw=G@tau+c
        checks['original_raw_signs'] &= np.all(raw>=0) and np.array_equal(raw,u['raw_slacks'])
        checks['both_primal_and_stationarity_targets'] &= all(v<=1e-9 for k,v in values.items() if k!='guarded_complementarity')
        checks['nonnegative_dual_and_guarded_complementarity'] &= np.all(ds>=-1e-9) and values['guarded_complementarity']<=1e-9
        checks['candidate_and_applied_identical'] &= u['torque_applied'] and np.array_equal(tau,d['tau_candidate'])
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':bool(updates) and all(checks.values()),'checks':checks,'maxima':maxima,
            'updates':len(updates),'QP_resolves_performed':False,
            'scope':'ORIGINAL_T29_AND_NEW_GUARDED_KKT_RECOMPUTED_FROM_RETAINED_DUALS'}
