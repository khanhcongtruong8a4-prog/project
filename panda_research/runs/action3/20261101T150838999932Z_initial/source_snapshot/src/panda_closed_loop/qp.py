"""Dense hard ProxQP, measured T29 residuals and explicit protective stop."""
from dataclasses import dataclass
import numpy as np
import proxsuite
from .contracts import vector
from .barriers import AffineRows


@dataclass
class QPResult:
    applied: np.ndarray | None
    status: str
    stop_requested: bool
    diagnostics: dict


def project_torque_box(command, limits):
    """Projection in eq_brake, exposed/tested separately; not used as recovery."""
    command, limits = vector(command, 'command'), vector(limits, 'limits')
    if np.any(limits <= 0):
        raise ValueError('Nonpositive torque limits')
    return np.clip(command, -limits, limits)


class HardSafetyQP:
    def __init__(self, taumax, settings, primal_target=1e-9, stationarity_target=1e-9):
        self.taumax = vector(taumax, 'taumax')
        if np.any(self.taumax <= 0) or primal_target != 1e-9 or stationarity_target != 1e-9:
            raise ValueError('Invalid limits or changed T29 thresholds')
        self.settings = dict(settings)
        self.primal_target, self.stationarity_target = primal_target, stationarity_target

    def solve(self, u_nom, rows):
        nominal = vector(u_nom, 'u_nom')
        if not isinstance(rows, AffineRows):
            raise ValueError('Expected AffineRows')
        # theta=diag(taumax)^-1 tau. Objective scaled by (87 N m)^2.
        H = np.diag(self.taumax**2)/87.**2
        g = -self.taumax*nominal/87.**2
        C = -rows.G*self.taumax[None, :]/rows.scales[:, None]
        upper = rows.c/rows.scales
        solver = proxsuite.proxqp.dense.QP(7, 0, len(upper))
        mapping = {'eps_abs_proposed': 'eps_abs', 'eps_rel': 'eps_rel', 'max_iter': 'max_iter',
                   'check_duality_gap': 'check_duality_gap', 'eps_duality_gap_abs': 'eps_duality_gap_abs',
                   'eps_duality_gap_rel': 'eps_duality_gap_rel'}
        for source, target in mapping.items():
            if source not in self.settings or not hasattr(solver.settings, target):
                raise ValueError('Missing/unavailable ProxQP setting: '+source)
            setattr(solver.settings, target, self.settings[source])
        diagnostics = {'solver': 'ProxQP '+proxsuite.__version__, 'settings': self.settings,
                       'row_names': rows.names, 'row_units': rows.units, 'row_scales': rows.scales.tolist(),
                       'recovery': 'DISABLED: K_b/gamma and recovery semantics not supplied', 'replan_requested': False}
        try:
            solver.init(H, g, None, None, C, np.full(len(upper), -np.inf), upper)
            solver.solve()
        except Exception as error:
            diagnostics.update(error=str(error), replan_requested=True)
            return QPResult(None, 'SOLVER_ERROR', True, diagnostics)
        result = solver.results
        status = str(result.info.status)
        if result.info.status != proxsuite.proxqp.QPSolverOutput.PROXQP_SOLVED:
            diagnostics.update(replan_requested=True, iterations=int(result.info.iter))
            return QPResult(None, status, True, diagnostics)
        theta, dual = np.asarray(result.x).copy(), np.asarray(result.z).copy()
        tau = theta*self.taumax
        if not np.all(np.isfinite(tau)) or not np.all(np.isfinite(dual)):
            return QPResult(None, 'NONFINITE_SOLUTION', True, diagnostics)
        primal = float(max(0., np.max(C@theta-upper)))
        stationarity = float(np.max(np.abs(H@theta+g+C.T@dual)))
        raw = rows.slacks(tau)
        diagnostics.update(tau_candidate=tau.tolist(), raw_slacks=raw.tolist(), normalized_slacks=(raw/rows.scales).tolist(),
            normalized_primal=primal, scaled_stationarity=stationarity,
            complementarity=float(np.max(np.abs(dual*(C@theta-upper)))),
            negative_upper_dual=float(max(0., np.max(-dual))), iterations=int(result.info.iter),
            duality_gap=float(result.info.duality_gap), intervention_Nm=float(np.linalg.norm(tau-nominal)),
            torque_upper_slack=(self.taumax-tau).tolist(), torque_lower_slack=(self.taumax+tau).tolist())
        # No clipping to conceal solver error. A negative physical torque slack
        # requests stop even if a normalized residual is below its threshold.
        accepted = (primal <= self.primal_target and stationarity <= self.stationarity_target
                    and np.all(self.taumax-np.abs(tau) >= 0))
        diagnostics['replan_requested'] = not accepted
        return QPResult(tau if accepted else None, status if accepted else 'NUMERICAL_OR_TORQUE_LIMIT_REJECTION', not accepted, diagnostics)
