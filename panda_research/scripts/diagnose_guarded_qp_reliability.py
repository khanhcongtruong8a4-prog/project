"""Read-only solver ablations on the preserved, unmodified counterexample."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse, hashlib, json, time
import numpy as np
import proxsuite
from scipy.optimize import minimize
from panda_closed_loop.a2_acceptance import exact_qp_certificate
from panda_closed_loop.a2_qp_v2 import NUMERICAL_POLICY
from panda_closed_loop.barriers import AffineRows


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    source = ROOT/'reports/a2_extended_v1/qp_bounds_evidence/run_v2/fixture_09.json'
    f = json.loads(source.read_text())
    rows = AffineRows(f['G'], f['c'], f['scales'], tuple(f['row_names']), tuple(f['row_units']))
    den = 87.*np.linalg.norm(rows.G, axis=1)
    C = -87.*rows.G/den[:, None]
    b = (rows.c-1e-8*rows.scales)/den
    n = np.asarray(f['nominal'])/87.
    certificate = exact_qp_certificate(f['nominal'], rows, [rows.names.index('v_lower_3')])
    exact = np.array(certificate['unique_optimum_y_float_display_only'])
    trials = []
    # One factor only. Targets, iteration limit, data, initialization unchanged.
    for eps in [1e-4, 1e-6, 1e-8, 1e-10, 1e-12, 1e-14]:
        q = proxsuite.proxqp.dense.QP(7, 0, len(b))
        for k in ['eps_abs', 'eps_rel', 'max_iter', 'check_duality_gap',
                  'eps_duality_gap_abs', 'eps_duality_gap_rel']:
            setattr(q.settings, k, NUMERICAL_POLICY[k])
        q.settings.eps_primal_inf = eps
        t = time.perf_counter()
        q.init(np.eye(7), -n, None, None, C, np.full(len(b), -np.inf), b)
        q.solve()
        x, z, info = np.array(q.results.x), np.array(q.results.z), q.results.info
        trials.append({'eps_primal_inf': eps, 'status': str(info.status), 'iterations': int(info.iter),
                       'duality_gap': float(info.duality_gap), 'runtime_s': time.perf_counter()-t,
                       'x': x.tolist(), 'z': z.tolist(),
                       'scaled_primal': float(max(0., np.max(C@x-b))),
                       'scaled_stationarity': float(np.max(abs(x-n+C.T@z))),
                       'min_raw_slack': float(np.min(rows.slacks(87*x))),
                       'error_vs_exact_optimum': float(np.max(abs(x-exact))),
                       'torque_actuated': False})
    # Independent algorithm starts at zero, without loading the exact witness.
    other = minimize(lambda x: .5*np.dot(x-n, x-n), np.zeros(7),
                     jac=lambda x: x-n, method='SLSQP',
                     constraints=[{'type': 'ineq', 'fun': lambda x: b-C@x, 'jac': lambda x: -C}],
                     options={'ftol': 1e-14, 'maxiter': 1000})
    independent = {'backend': 'SciPy SLSQP; zero initialization; no stored witness input',
                   'success': bool(other.success), 'message': other.message, 'iterations': int(other.nit),
                   'x': other.x.tolist(), 'objective': float(other.fun),
                   'scaled_primal': float(max(0., np.max(C@other.x-b))),
                   'error_vs_exact_optimum': float(np.max(abs(other.x-exact))),
                   'torque_actuated': False}
    data = {'source': str(source.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'exact_arithmetic_certificate': certificate, 'one_factor_ablations': trials,
            'separate_algorithm_validation': independent, 'physical_parameters_changed': False,
            'scope': 'LOCAL_NUMERICAL_DIAGNOSIS_NOT_EXTERNAL_REVIEW_OR_LEVEL1'}
    with args.output.open('x') as out: json.dump(data, out, indent=2, allow_nan=False); out.write('\n')
    print(json.dumps({'ablations': [{k: r[k] for k in ['eps_primal_inf', 'status', 'iterations', 'scaled_primal',
                       'scaled_stationarity', 'error_vs_exact_optimum']} for r in trials], 'independent': independent}, indent=2))


if __name__ == '__main__': main()
