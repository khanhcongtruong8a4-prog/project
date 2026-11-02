"""Generate 70+21 primary-source rows and an eight-joint frame review sheet."""
from pathlib import Path
import ast
import csv
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation
from reference_model import source_parameters, source_joint_data, supplement_tables
import panda_dynamics as target

ROOT=Path(__file__).resolve().parents[1]


def write_csv(name, rows):
    with (ROOT/'review_sheets'/name).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def code_urdf_origins():
    tree=ast.parse((ROOT/'src/panda_dynamics.py').read_text())
    fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='urdf_fk_numpy')
    xyz_assignment=next(n for n in fun.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='xyz' for t in n.targets))
    rpy_assignment=next(n for n in fun.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='rpy' for t in n.targets))
    def scalar(node):
        if isinstance(node,ast.Constant):return float(node.value)
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='np' and node.attr=='pi':return np.pi
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -scalar(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return scalar(node.left)/scalar(node.right)
        raise ValueError('Unsupported source literal expression')
    return (np.array(ast.literal_eval(xyz_assignment.value.args[0])),
            np.array([scalar(n) for n in rpy_assignment.value.args[0].elts]))


def main():
    source=source_parameters()
    table,friction_table=supplement_tables()
    manifest=json.loads((ROOT/'baseline/model_manifest_v1.json').read_text())
    downloads=json.loads((ROOT/'reports/source_downloads.json').read_text())
    identities={r['file']:r for r in downloads}
    inertial=[]
    friction=[]
    for i in range(7):
        fields=[(f'm{i+1}','mass',None,'MASS', 'link_masses_kg','kg')]
        fields += [(f'c{i+1}{axis}','com',j,'COM','link_centres_m','m') for j,axis in enumerate('xyz')]
        fields += [(f'I{i+1}{name}','inertia6',j,'INERTIA6','link_com_inertia_kg_m2_signed_xx_xy_xz_yy_yz_zz','kg m^2')
                   for j,name in enumerate(['xx','xy','xz','yy','yz','zz'])]
        for key,source_key,j,code_key,manifest_key,unit in fields:
            selection=(i,) if j is None else (i,j)
            author=float(source[source_key][selection])
            code=float(getattr(target,code_key)[selection])
            registered=float(np.array(manifest[manifest_key])[selection])
            special=key=='c1z'
            table_matches=table[key]=='*' if special else float(table[key])==author
            ok=table_matches and author==code==registered
            inertial.append({'parameter':key,'link':i+1,'unit':unit,'table': 'VIII' if source_key!='inertia6' else 'IX',
                'pdf_page':9,'table_p_hat_literal':table[key], 'author_code_value':author,
                'target_code_value':code,'manifest_value':registered,'difference_target_minus_author':code-author,
                'target_field':code_key+'['+','.join(map(str,selection))+']',
                'manifest_field':manifest_key+''.join('['+str(k)+']' for k in selection),
                'source_commit':identities['DynPars2VREP.m']['commit'],
                'source_matlab_sha256':identities['DynPars2VREP.m']['sha256'],
                'supplement_sha256':identities['supplement.pdf']['sha256'],
                'equality_result':'PASS_AUTHOR_CONVENTION' if ok and special else 'PASS' if ok else 'FAIL',
                'disposition':'Table prints asterisk; author code explicitly selects zero. Not a measured table value.' if special else 'No discrepancy',
                'reviewer_name':'','reviewer_date':'','reviewer_signature':'','human_acceptance':'PENDING SIGNATURE'})
        for k,unit in [(1,'N m'),(2,'s/rad'),(3,'rad/s')]:
            key=f'phi{k}_{i+1}'
            author=float(source[f'phi{k}'][i]);code=float(getattr(target,f'PHI{k}')[i])
            registered=float(manifest[{1:'friction_phi1_Nm',2:'friction_phi2_s_per_rad',3:'friction_phi3_rad_per_s'}[k]][i])
            ok=float(friction_table[key])==author==code==registered
            friction.append({'parameter':key,'joint':i+1,'unit':unit,'table':'I','pdf_page':1,
                'table_literal':friction_table[key],'author_code_value':author,'target_code_value':code,'manifest_value':registered,
                'difference_target_minus_author':code-author,'target_field':f'PHI{k}[{i}]',
                'source_commit':identities['get_FrictionTorque.m']['commit'],
                'source_matlab_sha256':identities['get_FrictionTorque.m']['sha256'],
                'supplement_sha256':identities['supplement.pdf']['sha256'],
                'equality_result':'PASS' if ok else 'FAIL',
                'erratum_disposition':'Corrected 0.87224 in BOTH revised Table I and pinned author code; older 8722.4 rejected. Author webpage not independently retrieved.' if k==1 and i==1 else 'No discrepancy',
                'reviewer_name':'','reviewer_date':'','reviewer_signature':'','human_acceptance':'PENDING SIGNATURE'})
    origins,rolls=code_urdf_origins()
    frames=[]
    for row in source_joint_data():
        i=row['index']-1
        expected_xyz=np.array([target.A_DH[i],-target.D_DH[i]*np.sin(target.ALPHA_DH[i]),target.D_DH[i]*np.cos(target.ALPHA_DH[i])]) if i<7 else np.array([0,0,target.FLANGE_Z])
        expected_rotation=target.rot_x(target.ALPHA_DH[i]) if i<7 else np.eye(3)
        source_rotation=Rotation.from_euler('xyz',row['rpy']).as_matrix()
        origin_difference=float(np.max(np.abs(expected_xyz-row['xyz'])))
        rotation_difference=float(np.max(np.abs(source_rotation-expected_rotation)))
        axis_difference=float(np.max(np.abs(np.array(row['axis'])-[0,0,1]))) if i<7 else 0.
        literal_difference=float(np.max(np.abs(origins[i]-row['xyz']))) if i<7 else float(np.max(np.abs(expected_xyz-row['xyz'])))
        roll_difference=abs(float(rolls[i])-row['rpy'][0]) if i<7 else 0.
        ok=origin_difference<=1e-10 and rotation_difference<=1e-10 and axis_difference<=1e-10 and literal_difference<=1e-10 and roll_difference<=1e-10
        frames.append({'joint':i+1,'joint_type':row['type'],'source_parent':row['parent'],'source_child':row['child'],
            'source_xyz_m':json.dumps(row['xyz']),'source_rpy_rad':json.dumps(row['rpy']),
            'source_axis':json.dumps(row['axis']),'target_mdh_xyz_m':json.dumps(expected_xyz.tolist()),
            'target_literal_origin_error_m':literal_difference,'mdh_origin_error_m':origin_difference,
            'target_literal_roll_error_rad':roll_difference,
            'mdh_rotation_error':rotation_difference,'axis_error':axis_difference,
            'frame_map_R_Gaz_to_target':json.dumps(np.eye(3).tolist()),'frame_map_t_m':json.dumps([0,0,0]),
            'base_alignment':'identity','joint_zero_offset_rad':0,
            'source_commit':identities['franka_arm.xacro']['commit'],'source_sha256':identities['franka_arm.xacro']['sha256'],
            'result':'PASS' if ok else 'FAIL','reviewer_name':'','reviewer_date':'','reviewer_signature':'','human_acceptance':'PENDING SIGNATURE'})
    write_csv('T04b_inertial_70.csv',inertial)
    write_csv('T04b_friction_21.csv',friction)
    write_csv('T06a_joint_frames_8.csv',frames)
    maps=[]
    for i in range(7):
        maps.append({'link':i+1,'source_frame':f'Gaz{i+1}','target_frame':f'panda_link{i+1}',
            'R':np.eye(3).tolist(),'t_m':[0.,0.,0.],'mass_kg':source['mass'][i].item(),
            'com_m':source['com'][i].tolist(),'inertia6_com_kg_m2_signed_xx_xy_xz_yy_yz_zz':source['inertia6'][i].tolist(),
            'inertia_frame_rpy':[0.,0.,0.],'parallel_axis_shift_applied':False,'human_acceptance':'PENDING SIGNATURE'})
    (ROOT/'review_sheets/T06a_link_parameter_mapping.json').write_text(json.dumps(maps,indent=2)+'\n')
    overall=all(x['equality_result'].startswith('PASS') for x in inertial+friction) and all(x['result']=='PASS' for x in frames)
    report={'status':'PASS_AUTOMATED_SOURCE_CROSSCHECK' if overall else 'FAIL','inertial_rows':len(inertial),
        'friction_rows':len(friction),'joint_frame_rows':len(frames),
        'inertial_mismatches':[x['parameter'] for x in inertial if not x['equality_result'].startswith('PASS')],
        'friction_mismatches':[x['parameter'] for x in friction if x['equality_result']!='PASS'],
        'human_T04b':'PENDING SIGNATURE','human_T06a':'PENDING SIGNATURE',
        'erratum_webpage':'NOT_RETRIEVED; revised Table I and pinned friction code checked directly',
        'overall_pass':overall}
    (ROOT/'reports/primary_source_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not overall: raise SystemExit(1)


if __name__=='__main__':
    main()
