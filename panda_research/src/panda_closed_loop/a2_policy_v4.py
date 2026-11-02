"""Additive user-authorized barrier CONTROL-gain amendment, not model editing.

Only the velocity-CBF design gain doubles. Original source/config bytes and
their approval records stay intact. A new explicit configuration is required.
"""
from dataclasses import replace
import json
import numpy as np
from .config import Policy,ROOT,digest
from .assembly import build_components
from .barriers import BarrierEvaluator

AMENDMENT={'version':'A2_EXTENDED_V4_VELOCITY_CBF_GAIN',
    'base_alpha_v_s_inverse':5.,'multiplier':2.,'alpha_v_s_inverse':10.,
    'gain_scope':'VELOCITY_CBF_DESIGN_GAIN_NOT_PHYSICAL_MODEL_OR_PASS_TOLERANCE',
    'equation':'±M^-1(tau+bias)+alpha_v*(vmax∓qd)-abs(M^-1)*varpi >=0',
    'effect':'Expands instantaneous robust acceleration admissibility inside unchanged speed limits; different versioned filter design',
    'other_gains':'UNCHANGED: SlotineLi Lambda/kappa, observer Ko, position/manip alpha1/alpha2 and P1 gains',
    'digital_QP':'V2_CURRENT_STATE_GUARDED_QP; no V3 row extrapolation or 0.1 reserve',
    'approval_scope':'USER_AUTHORIZED_NUMERICAL_POLICY_DEVELOPMENT; external signature artifacts not supplied',
    'baseline_policy_files_modified':False}


def expected_configuration():
    base=Policy.load();raw=base.raw
    if raw['gains']['alpha_v']!=5.:raise ValueError('Unexpected source gain')
    raw['gains']['alpha_v']=10.
    raw['schema_version']='IC2AI-2027-A2-Extended-v4-numerical-amendment'
    raw['status']='USER_AUTHORIZED_NUMERICAL_POLICY_AMENDMENT; NOT_AN_INDEPENDENT_SIGNATURE'
    return base,raw


def load_amended_policy():
    base,expected=expected_configuration()
    path=ROOT/'policy/a2_extended_v4/AMENDED_POLICY_CONFIGURATION.json'
    supplied=json.loads(path.read_text())
    if supplied!=expected:raise ValueError('Undeclared change outside the explicit gain/schema/status amendment')
    # path deliberately remains the immutable original source package so that
    # source_audit verifies its Gaz/manuscript/workbook provenance. The NEW
    # configuration/hash/authority are separately retained by the campaign.
    return replace(base,raw_json=json.dumps(supplied),alpha_v=supplied['gains']['alpha_v'])


def build_amended_system():return build_components(load_amended_policy())


def audit_gain_amendment(updates,system):
    """All ACTUAL v4 rows audited; v1 alpha5 rows explicitly shadowed only."""
    b=system.barriers
    old=BarrierEvaluator(system.model,system.geometry,b.qmin,b.qmax,b.vmax,b.taumax,b.w_min,b.alpha1,b.alpha2,5.)
    checks={'new_configuration_is_exact_declared_change':load_amended_policy().raw==system.policy.raw,
            'all_43_actual_rows_recomputed':True,'actual_raw_nonnegative':True,
            'old_and_new_G_identical':True,'nonvelocity_c_unchanged':True,
            'velocity_c_change_matches_declared_gain':True}
    negatives=[];minimum_old=np.inf;minimum_new=np.inf
    for u in updates:
        new=b.rows(u['q'],u['qd'],u['dhat'],u['varpi']);prev=old.rows(u['q'],u['qd'],u['dhat'],u['varpi'])
        tau=np.array(u['candidate_tau']);raw=new.slacks(tau);shadow=prev.slacks(tau)
        checks['all_43_actual_rows_recomputed'] &= np.array_equal(new.G,u['G']) and np.array_equal(new.c,u['c']) and np.array_equal(raw,u['raw_slacks'])
        checks['actual_raw_nonnegative'] &= np.all(raw>=0)
        checks['old_and_new_G_identical'] &= np.array_equal(new.G,prev.G)
        checks['nonvelocity_c_unchanged'] &= np.array_equal(new.c[:15],prev.c[:15]) and np.array_equal(new.c[29:],prev.c[29:])
        expected=5.*np.r_[b.vmax-np.array(u['qd']),b.vmax+np.array(u['qd'])]
        checks['velocity_c_change_matches_declared_gain'] &= np.allclose(new.c[15:29]-prev.c[15:29],expected,atol=5e-13,rtol=0)
        minimum_old=min(minimum_old,float(min(shadow/prev.scales)));minimum_new=min(minimum_new,float(min(raw/new.scales)))
        for j in np.where(shadow<0)[0]:
            negatives.append({'t_s':u['physical_t_s'],'row':prev.names[j],'value':float(shadow[j]),
                              'scope':'OLD_ALPHA5_POLICY_SHADOW_ONLY_NOT_ACTUAL_V4_CONSTRAINT'})
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':bool(updates) and all(checks.values()),'checks':checks,'amendment':AMENDMENT,
            'minimum_actual_v4_normalized_raw_slack':minimum_new,
            'old_alpha5_shadow_minimum_normalized_raw_slack':minimum_old,
            'old_alpha5_shadow_negative_count':len(negatives),'old_alpha5_shadow_negatives':negatives,
            'old_policy_satisfaction_not_asserted':True,'QP_resolves_performed':False}
