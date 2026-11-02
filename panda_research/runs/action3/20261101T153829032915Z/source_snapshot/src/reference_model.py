"""Independent reference construction from downloaded source bytes.

This module never imports panda_dynamics, its constants or transforms, CasADi,
or the baseline manifest. It parses the Gaz MATLAB arrays and official Xacro
joint elements, then emits a mesh-free URDF for Pinocchio/URDFDOM.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import numpy as np
from evidence_paths import evidence_dir

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'sources'


def matlab_array(text, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*=\s*\[(.*?)\]', text, re.S)
    if match is None:
        raise ValueError(f'Missing MATLAB array: {name}')
    body = re.sub(r'%[^\n]*', '', match[1]).replace('...', '')
    rows = [r.strip() for r in re.split(r';|\n', body) if r.strip()]
    values = [[float(x) for x in re.split(r'[,\s]+', row) if x] for row in rows]
    return np.array(values)


def source_parameters():
    text = (SOURCES / 'DynPars2VREP.m').read_text()
    mass = matlab_array(text, 'm').reshape(7)
    com = matlab_array(text, 'CoM_l')
    inertia = matlab_array(text, 'Il')
    fp = matlab_array((SOURCES / 'get_FrictionTorque.m').read_text(), 'fp')
    assert com.shape == (7, 3) and inertia.shape == (7, 6) and fp.shape == (4, 7)
    return {'mass': mass, 'com': com, 'inertia6': inertia,
            'phi1': fp[0], 'phi2': fp[3], 'phi3': fp[2]}


def source_joint_elements():
    tree = ET.parse(SOURCES / 'franka_arm.xacro')
    joints = []
    # Deliberately select exactly the eight numbered arm joints; conditional
    # connected_to mount and unrelated visual/collision macros are excluded.
    for index in range(1, 9):
        name = '${arm_id}_joint' + str(index)
        found = [j for j in tree.iter('joint') if j.get('name') == name]
        if len(found) != 1:
            raise ValueError(f'Expected one source joint {name}')
        joints.append(found[0])
    return joints


def numeric_tokens(text):
    # A whitelist for the only expressions in the selected joint origins.
    # No eval/xacro execution, imports, or external macro expansion.
    expressions = {'${pi/2}': repr(np.pi / 2), '${-pi/2}': repr(-np.pi / 2)}
    for key, value in expressions.items():
        text = text.replace(key, value)
    return [float(x) for x in text.split()]


def source_joint_data():
    rows = []
    for index, element in enumerate(source_joint_elements(), 1):
        origin = element.find('origin')
        axis = element.find('axis')
        rows.append({'index': index, 'type': element.get('type'),
                     'xyz': numeric_tokens(origin.get('xyz', '0 0 0')),
                     'rpy': numeric_tokens(origin.get('rpy', '0 0 0')),
                     'axis': numeric_tokens(axis.get('xyz')) if axis is not None else None,
                     'parent': element.find('parent').get('link').replace('${arm_id}', 'panda'),
                     'child': element.find('child').get('link').replace('${arm_id}', 'panda')})
    return rows


def build_reference_urdf():
    pars = source_parameters()
    robot = ET.Element('robot', name='gaz_seven_body_from_pinned_sources')
    ET.SubElement(robot, 'link', name='panda_link0')
    for i in range(7):
        link = ET.SubElement(robot, 'link', name=f'panda_link{i+1}')
        inertial = ET.SubElement(link, 'inertial')
        ET.SubElement(inertial, 'origin', xyz=' '.join(map(str, pars['com'][i])), rpy='0 0 0')
        ET.SubElement(inertial, 'mass', value=str(pars['mass'][i]))
        ET.SubElement(inertial, 'inertia', **dict(zip(
            ['ixx', 'ixy', 'ixz', 'iyy', 'iyz', 'izz'], map(str, pars['inertia6'][i]))))
    ET.SubElement(robot, 'link', name='panda_link8')  # massless fixed flange
    for row in source_joint_data():
        joint = ET.SubElement(robot, 'joint', name=f"panda_joint{row['index']}", type=row['type'])
        ET.SubElement(joint, 'origin', xyz=' '.join(map(str, row['xyz'])), rpy=' '.join(map(str, row['rpy'])))
        ET.SubElement(joint, 'parent', link=row['parent'])
        ET.SubElement(joint, 'child', link=row['child'])
        if row['axis'] is not None:
            ET.SubElement(joint, 'axis', xyz=' '.join(map(str, row['axis'])))
            # Broad parser-required limits, NOT physical experiment limits.
            # This reference performs algebraic evaluations only, no simulation.
            ET.SubElement(joint, 'limit', lower='-10', upper='10', effort='1000', velocity='10')
    ET.indent(robot)
    path = evidence_dir() / 'reference_panda.urdf'
    ET.ElementTree(robot).write(path, encoding='utf-8', xml_declaration=True)
    return path


def reference_friction(velocity):
    p = source_parameters()
    v = np.asarray(velocity)
    # Literal logistic equation in downloaded get_FrictionTorque.m; target
    # implementation instead uses an algebraically equivalent tanh expression.
    return p['phi1'] * (1 / (1 + np.exp(-p['phi2'] * (v + p['phi3'])))
                        - 1 / (1 + np.exp(-p['phi2'] * p['phi3'])))


def supplement_tables():
    pages = (evidence_dir() / 'supplement_layout.txt').read_text().split('\f')
    inertial = {}
    for line in pages[8].splitlines():
        match = re.match(r'^\s*(m[1-7]|c[1-7][xyz])\s+\S+\s+\S+\s+(\S+)', line)
        if match:
            inertial[match[1]] = match[2]
        match = re.search(r'\b(I[1-7](?:xx|xy|xz|yy|yz|zz))\s+\S+\s+\S+\s+(\S+)', line)
        if match:
            inertial[match[1]] = match[2]
    friction = {}
    for line in pages[0].splitlines():
        match = re.match(r'^\s*ϕ([123])\s+(.*)', line)
        if match:
            values = match[2].split()[:7]
            for index, value in enumerate(values, 1):
                friction[f'phi{match[1]}_{index}'] = value
    if len(inertial) != 70 or len(friction) != 21:
        raise ValueError(f'PDF parse incomplete: {len(inertial)} inertial, {len(friction)} friction')
    return inertial, friction
