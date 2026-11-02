"""Derive stage decisions and convergence tables from completed raw evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
import argparse,csv,hashlib,json,math

def load(p):return json.loads(Path(p).read_text())
def write(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    base=load(ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_active_E3/summary.json')
    new=load(ROOT/'runs/pre_a3_blockers_v1/projected_feedback_candidate/summary.json')
    ladder=load(ROOT/'runs/pre_a3_blockers_v1/original_AB2_delta_ladder/summary.json')
    cells=[base['cells'][0],base['cells'][2],*ladder['cells']]
    rows=[]
    for c in cells:
        m=c['a2']['metrics'];rows.append({'Delta_s':c['grid']['control_period_s'],'h_s':c['grid']['rk4_step_s'],
            'energy_J':m['modeled_electrical_energy_J'],'peak_intervention_Nm':m['maximum_intervention_Nm'],
            'completed':c['a2']['completed'],'audit_pass':c['audit']['passed']})
    rates={}
    for key in ['energy_J','peak_intervention_Nm']:
        differences=[rows[i][key]-rows[i+1][key] for i in range(3)]
        rates[key]={'successive_differences':differences,'observed_orders':[math.log(abs(differences[i]/differences[i+1]),2) for i in range(2)],
            'scope':'DIAGNOSTIC_RATE_ON_SUPPLEMENTARY_GRIDS_NOT_A_REPLACEMENT_ACCEPTANCE_OR_GLOBAL_ORDER_PROOF'}
    failed=lambda d:[{'cells':r['cells'],'factor':r['factor'],'metric':n,**v} for r in d['refinement']['comparisons'] for n,v in r['metrics'].items() if not v['passed']]
    reg=load(ROOT/'reports/pre_a3_blockers_v1/m1_registry/M1_REGISTRY.json')
    g25=load(ROOT/'reports/pre_a3_blockers_v1/g25_final_policy/SUMMARY.json')
    verified=load(ROOT/'reports/pre_a3_blockers_v1/CONSOLIDATION_AND_PRESERVATION.json')
    t27=load(ROOT/'reports/pre_a3_blockers_v1/t27_regression/SUMMARY.json')
    witness=load(ROOT/'reports/pre_a3_blockers_v1/g25_final_policy/initial_pair_witness_0.json')
    diagnosis=load(ROOT/'reports/pre_a3_blockers_v1/active_filter_diagnosis/SUMMARY.json')
    out={'version':'PRE_A3_ISSUE_RESOLUTION_V1','decisions':{'FROZEN_A2':'GO_RETAINED_FOR_19_UNCHANGED_CELLS',
        'ACTIVE_FILTER_REFINEMENT':'GO' if new['outcome']=='PASS' else 'NO-GO',
        'PROJECTED_FEEDBACK_CANDIDATE_ADOPTION':'GO' if new['outcome']=='PASS' else 'NO-GO_NOT_ADOPTED',
        'M1_NUMERICAL_COEFFICIENT_REGISTRY':'COMPLETE_14_CORE_ENTRIES_AND_DERIVED_PIPELINE',
        'M1_DOMAIN_BOUND_QUALIFICATION':'NO-GO','G2_5':g25['G2_5_decision'],
        'T27':'GO_FINITE_39_FIXTURE_STRICT_KKT_FARKAS_SCOPE' if t27['overall_pass'] else 'NO-GO','A3_READINESS':'NO-GO'},
        'original_failures_preserved':failed(base),'candidate_failures_preserved':failed(new),
        'new_candidate_cells_completed_and_audited':sum(c['a2']['completed'] and c['audit']['passed'] for c in new['cells']),
        'supplemental_ladder':rows,'observed_rates':rates,
        'unactuated_post_QP_AB2_negative_raw_queries':[c['unactuated_AB2_after_filter_negative_raw_queries'] for c in diagnosis['cells']],
        'analytic_ideal_model_m1':reg['inertia_lower_lemma']['m1_lower'],
        'sampled_eigenvalue_minimum_NOT_a_lower_bound':reg['observed_eigenvalue_minimum_NOT_used_as_bound'],
        'M1_training_points':reg['training_points'],'M1_heldout_points':reg['heldout_points'],
        'M1_heldout_exceeded_components':sum(d['component_count'] for d in reg['heldout_exceedances'].values()),
        'M1_upper_estimate_components':sum(d['component_total'] for d in reg['heldout_exceedances'].values()),
        'full_margin_G2_5_filter_points_passed':sum(d['filter_point_QPs_passed'] for d in g25['results']),
        'full_margin_G2_5_points_screened':g25['planned_points_screened'],
        'actual_start_exact_represented_speed_pair_rows':[r for r in witness['rows'] if r['failed_exactly']],
        'fixed_pose_necessary_preparation_bound':witness['preparation_duration_necessary_fixed_pose_only'],
        'preparation_or_any_other_experimental_parameter_changed':False,'source_preservation':verified,
        'new_19_cell_physical_rerun_claimed':False,'A2_evidence':'All prior physical outputs reaudited and protected source/trace bytes unchanged.',
        'official_A3_comparisons_executed':False,'Level1_certification_claimed':False,'external_verification_signatures':None}
    write(a.output/'DECISIONS_AND_EVIDENCE.json',out)
    with (a.output/'CONTROL_PERIOD_LADDER.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (a.output/'M1_BOUND_STATUS.csv').open('x') as f:
        w=csv.writer(f);w.writerow(['entry','shape','units','evidence_level','heldout_exceeded_components','certified_full_floating_domain'])
        for n,e in reg['entries'].items():w.writerow([n,e['shape'],e['units'],e['evidence_level'],reg['heldout_exceedances'].get(n,{}).get('component_count',0),False])
    print(json.dumps(out['decisions'],indent=2));print('Observed orders',rates)

if __name__=='__main__':main()
