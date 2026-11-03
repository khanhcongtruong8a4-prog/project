"""Full development M1/G2.5 screen, without a planner or A3 comparison solve."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,csv,json,hashlib
import numpy as np
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.a2_qp_reliable_v1_1 import GuardedHardQP
from panda_closed_loop.a2_extended import ExtendedReference
from panda_closed_loop.m1_common_domain_v1 import NumericalM1Registry
from panda_closed_loop.m1_margins_v1 import DevelopmentMarginProvider,exact_initial_pair_obstruction
from panda_closed_loop.stage1_scaffold import Stage1Scaffold
from panda_closed_loop.feasibility import planner_pair_screen,pair_conditions
from panda_closed_loop.logging import json_values

def write(p,d):
    with Path(p).open('x') as f:json.dump(json_values(d),f,indent=2,allow_nan=False);f.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);registry=NumericalM1Registry(json.loads(a.registry.read_text()))
    system=build_amended_system();system.geometry.function=system.geometry.function.expand();kernel=GuardedHardQP(system.barriers.taumax)
    stage=Stage1Scaffold(system);plan=json.loads((ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json').read_text())
    reserve=system.barriers.planner_reserves(system.policy);rows=[];results=[];witnesses=[]
    gap=system.policy.raw['solver']['NLP_grid']['initial_max_gap_s'];times=np.linspace(0.,1.,round(1/gap)+1)
    for cell in range(4):
        endpoint=json.loads((ROOT/f'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_{cell}.json').read_text())['endpoint']['QP']
        witness=exact_initial_pair_obstruction(system,endpoint);witnesses.append(witness);write(a.output/f'initial_pair_witness_{cell}.json',witness)
        margins=DevelopmentMarginProvider(registry,system,endpoint['varpi'],endpoint['dhat'],1.)
        La=margins.residual_lipschitz_estimates();write(a.output/f'residual_Lipschitz_ESTIMATES_{cell}.json',{
            'values':La,'source':'eq_envelopes, eq_res_bound, eq_beta_bounds, eq_margins; chain rule with Markov a/jerk bounds',
            'certified':False,'grid_reserves_prove_continuous_feasibility':False,'initial_max_gap_s_unchanged':gap})
        table=registry.for_development();necessary=planner_pair_screen(endpoint['varpi'],system.barriers.qmax-system.barriers.qmin,
            system.barriers.vmax,system.policy.alpha1,system.policy.alpha2,system.policy.alpha_v,
            reserve['joint_HOCBF_rad_s2'],reserve['velocity_CBF_rad_s2'],Nbar=table['Nbar_il'],
            Abar_plus=table['Abar_jl'][:7],Abar_minus=table['Abar_jl'][7:14])
        write(a.output/f'common_factor_two_necessary_ESTIMATE_{cell}.json',necessary)
        for ref in ['E1','E2','E3']:
            reference=ExtendedReference(endpoint['q'],endpoint['qd'],plan['references'][ref]);nodes=[]
            for t in times:
                sample=reference.sample(float(t));bound=margins.at(float(t));detail=margins.details(float(t))
                tau,residuals=stage.residual_sample(sample,endpoint['dhat'],bound)
                current=system.barriers.rows(sample.q,sample.qd,endpoint['dhat'],detail['varpi']);solved=kernel.solve(tau,current)
                pair=pair_conditions(abs(np.linalg.inv(system.model.evaluate(sample.q,sample.qd)['M'])),detail['varpi'],
                    system.barriers.qmax-system.barriers.qmin,system.barriers.vmax,system.policy.alpha1,system.policy.alpha2,system.policy.alpha_v)
                minima={k:float(np.min(v)) for k,v in residuals.items()}
                gridmin={k:float(np.min(np.asarray(v)-np.asarray(La[k])*gap/2)) for k,v in residuals.items()}
                node={'t':float(t),'q':sample.q,'qd':sample.qd,'qdd':sample.qdd,'planned_torque':tau,
                    'full_margin_components':detail,'planner_residuals':residuals,'minimum_by_family':minima,
                    'estimated_grid_reserve_minimum_by_family':gridmin,'filter_43_row_query':solved.__dict__,
                    'filter_pair_conditions':pair,'scope':'READ_ONLY_PLANNED_POINT_WITH_FROZEN_INITIAL_DHAT_NOT_AN_EXECUTED_TRAJECTORY',
                    'torque_actuated':False}
                nodes.append(node);rows.append([cell,ref,float(t),not solved.stop_requested,*[minima[k] for k in ['torque_upper','torque_lower','speed_upper','speed_lower','hocbf','velocity_cbf_upper','velocity_cbf_lower','physical_position_and_manip_h']]])
            report={'cell':cell,'reference':ref,'alpha_v':system.policy.alpha_v,'nodes':nodes,
                'all_full_margin_nodes_nonnegative':all(all(v>=0 for v in n['minimum_by_family'].values()) for n in nodes),
                'filter_point_QPs_passed':sum(not n['filter_43_row_query']['stop_requested'] for n in nodes),
                'official_A3_executed':False,'certified_bounds':False,'continuous_time_feasibility_claimed':False}
            write(a.output/f'cell_{cell}_{ref}.json',report)
            results.append({k:report[k] for k in ['cell','reference','all_full_margin_nodes_nonnegative','filter_point_QPs_passed']})
            print('C4 start',cell,ref,'filter pass',report['filter_point_QPs_passed'],'/',len(times),'planner nodes pass',report['all_full_margin_nodes_nonnegative'],flush=True)
    with (a.output/'G2_5_NODE_SUMMARY.csv').open('x') as f:
        w=csv.writer(f);w.writerow(['C4_start','reference','t','filter_QP_pass','torque_upper_min','torque_lower_min','speed_upper_min','speed_lower_min','HOCBF_min','vCBF_upper_min','vCBF_lower_min','physical_position_and_manip_h_min']);w.writerows(rows)
    negative=any(w['status']=='NO_GO_NECESSARY_START_PAIRS' for w in witnesses)
    write(a.output/'SUMMARY.json',{'intended_policy':'UNCHANGED_ALPHA_V10_AB2_GUARDED_QP_FINAL_A2_POLICY',
        'G2_5_decision':'NO-GO' if negative or not all(r['all_full_margin_nodes_nonnegative'] for r in results) else 'NUMERICAL_NODES_ONLY_NOT_GO',
        'initial_exact_represented_pair_obstruction':negative,'results':results,'planned_points_screened':len(rows),
        'M1_core_table_complete':True,'M1_domain_upper_bound_certification':False,'residual_Lipschitz_tables_present':True,
        'factor_two_retained_and_nonzero_rho_initial_included':True,'full_torque_speed_position_manipulability_and_HOCBF_constraints_screened':True,
        'new_torque_actuated':False,'official_A3_comparisons':False,'Level1':False,'external_signatures':None,
        'registry_sha256':hashlib.sha256(a.registry.read_bytes()).hexdigest()})

if __name__=='__main__':main()
