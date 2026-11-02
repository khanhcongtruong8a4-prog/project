"""Read-only typed policy and byte-level source audit. Never invent M1 inputs."""
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
import csv
import hashlib
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import numpy as np
from .contracts import scalar, vector

ROOT = Path(__file__).resolve().parents[2]
POLICY_SHA256 = 'fd4ebc5ace393a5278877434e394295c74bc54e4c305ecdd103b768123dea530'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def workbook_cells(path):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(t.text or '' for t in s.findall('.//s:t', ns))
                       for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        rels = {e.get('Id'): e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns):
            target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not target.startswith('xl/'):
                raise ValueError('Workbook relationship escapes xl/')
            cells = {}
            for c in ET.fromstring(z.read(target)).findall('.//s:c', ns):
                value = c.find('s:v', ns)
                text = value.text if value is not None else ''.join(t.text or '' for t in c.findall('.//s:t', ns))
                cells[c.get('r')] = strings[int(text)] if c.get('t') == 's' else (text or '')
            result[sheet.get('name')] = cells
        return result


@dataclass(frozen=True)
class Policy:
    path: Path
    raw_json: str
    ko: tuple
    lambdas: tuple
    kappa: float
    alpha1: float
    alpha2: float
    alpha_v: float
    delta: float
    h: float

    @property
    def raw(self):
        return json.loads(self.raw_json)  # isolated copy, source file never rewritten

    @classmethod
    def load(cls, path=None):
        path = Path(path or ROOT/'policy/v1.2.1/APPROVED_POLICY_CONFIGURATION_v1.2.1.json')
        if digest(path) != POLICY_SHA256:
            raise ValueError('Policy bytes differ from supplied approved v1.2.1')
        raw = json.loads(path.read_text())
        if raw['schema_version'] != 'IC2AI-2027-policy-v1.2.1' or raw['margin_mode']['approved'] != 'M1_COMMON_FROZEN_DOMAIN_CONSTANTS':
            raise ValueError('Unrecognized policy/schema/margin mode')
        if raw['status'] != 'PROJECT_OWNER_DESIGN_APPROVED; NOT_EXECUTABLE_OR_EXPERIMENT_FROZEN':
            raise ValueError('Unexpected policy status')
        gains = raw['gains']
        ko, lam = vector(gains['K_o_s_inverse'], 'K_o s^-1'), vector(gains['Lambda'], 'Lambda s^-1')
        if np.any(ko <= 0) or np.any(lam <= 0):
            raise ValueError('Nonpositive diagonal gain')
        for key in ['kappa', 'alpha_1', 'alpha_2', 'alpha_v']:
            scalar(gains[key], key+' s^-1', positive=True)
        integ = raw['integration']
        dt, h = scalar(integ['control_period_s'], 'Delta s', positive=True), scalar(integ['h_s'], 'h s', positive=True)
        if abs(dt/h-round(dt/h)) > 1e-12 or round(dt/h) != integ['substeps_m']:
            raise ValueError('Non-integer control/plant alignment')
        if not np.array_equal(raw['gravity_world_m_s2'], [0, 0, -9.80665]) or raw['fixed_flange_z_m'] != .107:
            raise ValueError('Model convention mismatch')
        if raw['disturbance']['amplitude_fraction'] != .02 or not raw['disturbance']['global_clock']:
            raise ValueError('Unexpected disturbance policy')
        p = raw['physical_parameters']
        for key in ['velocity_reserve_rad_s', 'torque_reserve_Nm', 'eta_delta', 'normalization_time_s']:
            scalar(p[key], key, positive=True)
        if p['position_reserve_rad'] is not None:
            raise ValueError('No separate position reserve is authorized')
        if raw['fixed_acceptance_thresholds']['QP_normalized_primal'] != 1e-9 or raw['fixed_acceptance_thresholds']['QP_scaled_stationarity'] != 1e-9:
            raise ValueError('QP acceptance threshold changed')
        return cls(path, json.dumps(raw), tuple(ko), tuple(lam), gains['kappa'], gains['alpha_1'], gains['alpha_2'], gains['alpha_v'], dt, h)

    def source_audit(self):
        root = self.path.parent
        checks = []
        for row in json.loads((root/'FILE_SHA256_MANIFEST.json').read_text())['files']:
            path = (root/row['file']).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('Unsafe policy manifest path')
            ok = digest(path) == row['sha256'] and path.stat().st_size == row['size_bytes']
            checks.append({'file': str(path.relative_to(ROOT)), 'sha256': digest(path), 'matches': ok})
        if not all(x['matches'] for x in checks):
            raise ValueError('Policy package checksum mismatch')
        expected = json.loads((root/'manuscript_source_hashes.json').read_text())
        manuscript = []
        for name, sha in expected['files'].items():
            path = ROOT/'sources/manuscript_v1.2.1'/name
            manuscript.append({'file': name, 'expected_sha256': sha, 'actual_sha256': digest(path), 'matches': digest(path) == sha})
        archive = ROOT/'inputs/action3/Project.rar'
        manuscript.append({'file': 'Project.rar', 'expected_sha256': expected['archive_sha256'], 'actual_sha256': digest(archive), 'matches': digest(archive) == expected['archive_sha256']})
        canonical = all(x['matches'] for x in manuscript if x['file'] in ['02_mm&nc.tex', '03_contribution.tex'])
        if not canonical:
            raise ValueError('Canonical dynamics/control equation source mismatch')
        for field, name in [('baseline_model_manifest_sha256', 'baseline/model_manifest_v1.json'),
                            ('baseline_evaluator_sha256', 'baseline/panda_dynamics.py'),
                            ('working_evaluator_sha256', 'src/panda_dynamics.py')]:
            if digest(ROOT/name) != self.raw[field]:
                raise ValueError('Dynamics identity mismatch: '+name)
        book = workbook_cells(root/'Referenced_Inputs/Tasks_2026.xlsx')
        provenance = []
        with (root/'original_Tasks_2026_provenance.csv').open() as stream:
            for row in csv.DictReader(stream):
                actual = book.get(row['worksheet'], {}).get(row['cell'])
                expected_value = row['original_workbook_value']
                def equivalent(a, b):
                    try:
                        return float(a) == float(b)
                    except (TypeError, ValueError):
                        return a is not None and a.strip() == b.strip()
                provenance.append({'key': row['config_key'], 'worksheet': row['worksheet'], 'cell': row['cell'],
                                   'recorded': expected_value, 'actual': actual, 'matches': equivalent(actual, expected_value)})
        return {'policy_sha256': digest(self.path), 'policy_files': checks, 'canonical_equations_match': canonical,
                'manuscript': manuscript, 'workbook_cell_audit': provenance,
                'workbook_sha256': digest(root/'Referenced_Inputs/Tasks_2026.xlsx'),
                'owner_approval': 'RECORDED_IN_SUPPLIED_POLICY; NOT AN INDEPENDENT SIGNATURE',
                'T29_csv_legacy_status_note': 'CSV still says RECOVERED_FROM_PROTOCOL_NOT_APPROVED; supplied v1.2.1 C6 explicitly approves the protocol rule. Original CSV preserved.',
                'human_signatures': self.raw['approvals']}

    def a2_blockers(self):
        raw = self.raw
        blockers = ['OFFICIAL_A2_EXECUTION_NOT_AUTHORIZED', 'T27_COMPLETE_SOLVER_VALIDATION_NOT_RUN',
                    'FROZEN_REFERENCE_TASK_AND_TUBE_CHECKS_NOT_AVAILABLE', 'MANUSCRIPT_ARCHIVE_AND_MAIN_TEX_REVISION_UNCONFIRMED']
        for key in ['constant_values', 'equation_map', 'speed_domain', 'acceleration_domain', 'tube_extension', 'estimator_grid', 'estimator_seed', 'estimator_budget']:
            if raw['margin_mode'][key] is None:
                blockers.append('M1_MISSING_'+key.upper())
        if raw['integration']['observer_update_semantics'] is None:
            blockers.append('OBSERVER_DISCRETIZATION_POLICY_APPROVAL_MISSING')
        if raw['approvals']['controls_reviewer_signature'] is None:
            blockers.append('CONTROLS_REVIEW_NOT_RECORDED')
        return blockers
