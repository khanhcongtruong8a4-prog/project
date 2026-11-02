"""Derive review tables from retained read-only QP/screen evidence."""
from pathlib import Path
import argparse,csv,hashlib,json


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();run=args.run.resolve()
    fixtures=json.loads((run/'t27_fixtures.json').read_text());screens=json.loads((run/'g25_screens.json').read_text())
    def write(name,rows):
        with (run/name).open('x',newline='') as f:
            w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    write('T27_FIXTURE_SUMMARY.csv',[{'fixture':r['name'],'solver_status':r['status'],
        'normalized_KKT_pass':r['normalized_KKT_pass'],'strict_raw_pass':r['strict_raw_pass'],
        'production_stop_requested':r['production_stop_requested'],'oracle_error_Nm':r['oracle_max_error_Nm'],
        'oracle_pass':r['oracle_pass'],'negative_raw_minimum':r['negative_raw_minimum'],
        'negative_raw_rows':';'.join(r['negative_raw_rows']),'independent_LP_status':r['independent_LP']['status_code'],
        'wall_runtime_s':r['wall_runtime_s']} for r in fixtures])
    write('G2_5_POINT_SUMMARY.csv',[{'point':r['label'],'filter_point_status':r['filter_point_status'],
        'velocity_pair_pass':r['filter_pair_conditions']['velocity']['passed'],
        'position_pair_pass':r['filter_pair_conditions']['position']['passed'],
        'physical_initial_conditions_pass':r['initial_physical_conditions']['passed'],
        'QP_status':r['torque_and_manipulability_full_43_row_QP']['status'],
        'QP_strict_raw_pass':r['torque_and_manipulability_full_43_row_QP']['strict_raw_pass'],
        'planner_status':r['planner_status'],
        'factor2_velocity_failing_joints':';'.join(map(str,r['planner_point_lower_witness_only']['reviewer_factor_two']['velocity_failing_joints'])),
        'factor2_position_failing_joints':';'.join(map(str,r['planner_point_lower_witness_only']['reviewer_factor_two']['position_failing_joints']))} for r in screens])
    record={'command':'python scripts/a3_qp_bounds_tables.py <retained-run>',
        'scope':'READ_ONLY_DERIVED_TABLES_NO_NEW_SOLVE','inputs':{n:hashlib.sha256((run/n).read_bytes()).hexdigest() for n in ['t27_fixtures.json','g25_screens.json']},
        'outputs':{n:hashlib.sha256((run/n).read_bytes()).hexdigest() for n in ['T27_FIXTURE_SUMMARY.csv','G2_5_POINT_SUMMARY.csv']}}
    with (run/'DERIVED_TABLES.json').open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print(run)


if __name__=='__main__':main()
