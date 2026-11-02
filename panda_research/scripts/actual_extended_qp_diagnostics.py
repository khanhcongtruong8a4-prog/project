"""Read-only diagnoses of retained failed A2-Extended QPs; no ProxQP rerun.

Only HiGHS LPs, pointwise row reconstruction and exact rational evaluation of
stored binary64 coefficients are used. No control/state/plan/threshold changes.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import importlib.metadata
import json
import numpy as np
from scipy.optimize import linprog
from panda_closed_loop.assembly import build_components
from panda_closed_loop.barriers import AffineRows
from panda_closed_loop.config import digest
from panda_closed_loop.feasibility import pair_conditions
from panda_closed_loop.logging import json_values
from panda_closed_loop.observer import ObserverEnvelope
from panda_closed_loop.a3_qp_bounds import independent_linear_feasibility
from panda_closed_loop.trace_archive import read_trace


def exact_recorded_row_signs(rows,tau):
    """Exact real arithmetic on the finite floats' dyadic rational values.

    This proves only a property of the stored rounded affine matrix. It is
    not an interval enclosure of the model, dynamics or continuous trajectory.
    """
    if tau is None:return None
    x=[Fraction.from_float(float(a)) for a in tau]
    values=[]
    for name,g,c in zip(rows.names,rows.G,rows.c):
        value=Fraction.from_float(float(c))+sum((Fraction.from_float(float(a))*b for a,b in zip(g,x)),Fraction(0))
        values.append({'row':name,'sign':1 if value>0 else -1 if value<0 else 0,
                       'numerator':str(value.numerator),'denominator':str(value.denominator),
                       'float_display_only':float(value)})
    return {'all_nonnegative_for_exact_recorded_coefficients':all(v['sign']>=0 for v in values),
            'all_strictly_positive_for_exact_recorded_coefficients':all(v['sign']>0 for v in values),
            'negative_rows':[v['row'] for v in values if v['sign']<0],
            'rows':values,'scope':'EXACT_DYADIC_RECORDED_AFFINE_COEFFICIENTS_ONLY_NOT_EXACT_ROBOT_MODEL',
            'does_not_override_frozen_floating_raw_sign_rule':True}


def positive_margin_witness(rows,taumax):
    """Find an interior witness for the same original feasible set.

    Auxiliary LP maximizes one shared normalized slack eta. Its objective is
    solely diagnostic; its candidate is never applied or substituted into QP.
    """
    C=np.c_[-rows.G*taumax[None,:]/rows.scales[:,None],np.ones(len(rows.names))]
    result=linprog(np.r_[np.zeros(7),-1.],A_ub=C,b_ub=rows.c/rows.scales,
                   bounds=[(None,None)]*8,method='highs')
    record={'solver':'SciPy HiGHS auxiliary maximum-normalized-margin LP',
            'status_code':int(result.status),'message':result.message,
            'success':bool(result.success),'candidate_applied':False,
            'objective_is_not_the_production_QP_objective':True}
    if result.success:
        tau=result.x[:7]*taumax
        raw=rows.slacks(tau)
        record.update(eta=float(result.x[-1]),tau=tau,raw_slacks=raw,
                      raw_minimum=float(np.min(raw)),normalized_raw_minimum=float(np.min(raw/rows.scales)),
                      negative_raw_rows=[rows.names[i] for i in np.where(raw<0)[0]],
                      exact_recorded_coefficients=exact_recorded_row_signs(rows,tau))
    return record


def diagnose(system,reference,index):
    folder=ROOT/f'runs/a2_extended_v1/{reference}_e4267be'
    cell_file=folder/f'cell_{index}.json'
    cell=json.loads(cell_file.read_text())
    trace_record=cell['a2']['trace']
    trace=read_trace(folder/trace_record['file'],trace_record)
    update=trace['updates'][-1]
    assert not update['torque_applied'],'Select the failed, unapplied update only'
    rows=AffineRows(np.array(update['G']),np.array(update['c']),np.array(update['row_scales']),
                    tuple(update['row_names']),tuple(update['row_units']))
    assert len(rows.names)==43
    q,v,dhat,vp=[np.array(update[k]) for k in ['q','qd','dhat','varpi']]
    rebuilt=system.barriers.rows(q,v,dhat,vp)
    assert np.array_equal(rebuilt.G,rows.G) and np.array_equal(rebuilt.c,rows.c)
    N=np.linalg.solve(system.model.evaluate(q,v)['M'],np.eye(7))
    pairs=pair_conditions(abs(N),vp,system.barriers.qmax-system.barriers.qmin,system.barriers.vmax,
                           system.policy.alpha1,system.policy.alpha2,system.policy.alpha_v)
    lp=independent_linear_feasibility(rows)
    if lp['feasible']:
        tau=np.array(lp['tau_candidate']);raw=rows.slacks(tau)
        lp.update(raw_slacks=raw,normalized_raw_slacks=raw/rows.scales,
                  negative_raw_rows=[rows.names[i] for i in np.where(raw<0)[0]],
                  exact_recorded_coefficients=exact_recorded_row_signs(rows,tau),candidate_applied=False)
    margin=positive_margin_witness(rows,system.barriers.taumax)
    candidate=update['candidate_tau']
    candidate_raw=rows.slacks(candidate) if candidate is not None else None
    previous_tau=trace['substeps'][-1]['applied_tau'] if trace['substeps'] else None
    physical=system.barriers.entry_conditions(q,v,previous_tau)
    elapsed=update['physical_t_s']+.156
    expected_vp=ObserverEnvelope(system.policy.ko,system.bounds.magnitude,system.bounds.rate).value(elapsed)
    finite_set_witness=(margin.get('exact_recorded_coefficients') or {}).get('all_strictly_positive_for_exact_recorded_coefficients',False)
    result={'reference_id':reference,'cell':index,'source_cell':str(cell_file.relative_to(ROOT)),
        'source_cell_sha256':digest(cell_file),'source_trace':trace_record,
        'original_completed':cell['a2']['completed'],'original_passed':cell['a2']['passed'],
        'original_failure':cell['a2']['failure'],'last_attempted_update':update,
        'last_failed_update_actuated':update['torque_applied'],
        'previous_applied_update_count':sum(bool(u['torque_applied']) for u in trace['updates']),
        'last_attempt_matches_actual_abort_state':all(update[k]==cell['a2']['final_state'][k] for k in ['q','qd','z']),
        'original_43_rows_reconstructed_exactly':True,
        'actual_filter_pair_conditions':pairs,
        'actual_physical_conditions_with_previous_held_torque':physical,
        'original_observer_elapsed_s':elapsed,
        'propagated_varpi_matches_original_no_reset':bool(np.array_equal(vp,expected_vp)),
        'recorded_candidate_raw_slacks_recomputed':candidate_raw,
        'recorded_candidate_negative_raw_rows':[] if candidate_raw is None else [rows.names[i] for i in np.where(candidate_raw<0)[0]],
        'recorded_candidate_exact_dyadic_signs':exact_recorded_row_signs(rows,candidate),
        'independent_HiGHS_feasibility_LP':lp,'interior_witness_diagnostic':margin,
        'recorded_binary64_affine_problem_has_strict_feasible_witness':bool(finite_set_witness),
        'feasibility_claim_scope':'Recorded rounded 43-row affine coefficients only. No model/ODE enclosure or robot safety proof.',
        'production_rerun':False,'new_motion_executed':False,'original_case_outcome_changed':False,
        'scientific_disposition':'ORIGINAL_FROZEN_CASE_REMAINS_FAIL_NO_DIAGNOSTIC_TORQUE_SUBSTITUTED',
        'verification_status':'EXECUTED_LOCALLY_READ_ONLY_ANALYSIS_NOT_INDEPENDENT_HUMAN_REVIEW',
        'human_signatures':None}
    del trace
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'reports/a2_extended_v1/actual_extended_qp_diagnostics')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    policy_file=ROOT/'policy/a2_extended_v1/FROZEN_INPUTS.json'
    frozen=json.loads(policy_file.read_text())['files']
    assert all(digest(ROOT/n)==h for n,h in frozen.items())
    metadata={'scope':'READ_ONLY_NEW_DIAGNOSIS_NO_PRODUCTION_QP_OR_PLANT_RERUN',
        'started_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
        'source_sha256':digest(Path(__file__)),'frozen_input_count':len(frozen),'frozen_manifest_sha256':digest(policy_file),
        'versions':{n:importlib.metadata.version(n) for n in ['numpy','scipy','casadi','proxsuite']},
        'production_settings_changed':False,'human_signatures':None}
    def write(path,data):
        with path.open('x') as f:json.dump(json_values(data),f,indent=2,allow_nan=False);f.write('\n')
    write(out/'run_started.json',metadata)
    system=build_components();system.geometry.function=system.geometry.function.expand()
    cases=[]
    for reference,index in [('E1',1),('E3',0),('E3',1),('E3',2),('E3',3)]:
        result=diagnose(system,reference,index);cases.append(result)
        write(out/f'{reference}_cell_{index}.json',result)
        print(reference,index,result['original_failure'],
              'LP=',result['independent_HiGHS_feasibility_LP']['status_code'],
              'strict recorded-coefficient witness=',result['recorded_binary64_affine_problem_has_strict_feasible_witness'],flush=True)
    summary=[{'reference':c['reference_id'],'cell':c['cell'],'physical_t_s':c['last_attempted_update']['physical_t_s'],
              'original_QP_status':c['last_attempted_update']['status'],
              'LP_status':c['independent_HiGHS_feasibility_LP']['status_code'],
              'LP_raw_minimum':c['independent_HiGHS_feasibility_LP'].get('minimum_raw_slack'),
              'strict_witness_eta':c['interior_witness_diagnostic'].get('eta'),
              'strict_witness_minimum_raw':c['interior_witness_diagnostic'].get('raw_minimum'),
              'strict_witness_exact_recorded_coefficients':c['recorded_binary64_affine_problem_has_strict_feasible_witness'],
              'negative_rejected_candidate_rows':c['recorded_candidate_negative_raw_rows'],
              'original_result_unchanged':'FAIL'} for c in cases]
    write(out/'summary.json',summary)
    lines=['# Actual A2-Extended failed-QP diagnostics\n',
      '**New read-only analysis; every original frozen case remains FAIL.** No ProxQP production call, new motion, gain/setting/threshold change, alternative actuation or trajectory substitution occurred.\n',
      'The final attempted updates were read from hash-verified CTZ archives. The original 43 rows were reconstructed bit-for-bit from each actual q/qd/dhat/varpi state. Necessary paired speed/position conditions and physical h/psi1/speed/manipulability conditions use that actual abort state, not a nominal midpoint or zero velocity. This is not a duplicate full-prefix trajectory audit.\n',
      '| Case | t s | Original ProxQP status | HiGHS LP status | LP minimum raw slack | Interior witness eta | Exact recorded-row strict feasibility |\n| --- | --- | --- | --- | --- | --- | --- |']
    for c in summary:
        lines.append(f"| {c['reference']} cell {c['cell']} | {c['physical_t_s']:.6g} | {c['original_QP_status']} | {c['LP_status']} | {c['LP_raw_minimum']} | {c['strict_witness_eta']} | {c['strict_witness_exact_recorded_coefficients']} |")
    lines += ['',
      'HiGHS status is a separate numerical feasibility classification, not by itself a proof. Its raw candidate signs are retained, including any small negatives. The auxiliary maximum-normalized-margin LP uses the same original affine rows and finds an interior candidate solely for analysis. When all exact dyadic row values are positive, the stored finite binary64 matrix has a mathematical strict-feasibility witness. Exact rational numerators/denominators for all 43 rows are retained. This statement is limited to the recorded rounded coefficients: it is not a validated enclosure of the exact robot model, a continuous-time theorem, or permission to actuate that candidate. No objective-optimality claim is made for the production QP.',
      '',
      'The E1 PRIMAL_INFEASIBLE report and E3 MAX_ITER report must therefore be distinguished from a demonstrated empty feasible set whenever a strict recorded-matrix witness is present. E3 SOLVED candidates with negative floating raw rows remain rejected under the frozen zero-negative rule, even when their normalized solver residuals are small or exact-dyadic sign evaluation differs from the rounded dot-product result. No diagnostic reinterpretation restores the missing physical steps or changes a case result.',
      '',
      'T27 implication: actual-trajectory matrices corroborate the earlier active-boundary and solver-classification limitations. They should become regression fixtures in a separately versioned solver-qualification study. Any future precision/scaling/solver or raw-sign policy change needs new reviewed/frozen experiments; no such change was selected here. Official T27, A3 and publication interpretation remain open. Human signatures remain null.',
      '',f'Evidence: `{out.relative_to(ROOT)}`; this report and per-case JSON contain source/CTZ hashes, all original rows and signs, LP candidates, pair conditions and exact-recorded-coefficient witnesses.']
    report=ROOT/'reports/a2_extended_v1/ACTUAL_EXTENDED_QP_DIAGNOSTICS.md'
    with report.open('x') as f:f.write('\n'.join(lines)+'\n')
    assert all(digest(ROOT/n)==h for n,h in frozen.items())
    metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(),frozen_inputs_unchanged=True,cases=len(cases),
                    source_sha256_matches=digest(Path(__file__))==metadata['source_sha256'])
    write(out/'run_completed.json',metadata)
    print(report)


if __name__=='__main__':main()
