"""Equation/dependency registry and explicit A2 gates, without guessed bounds."""
from pathlib import Path
import hashlib
import json
from .config import ROOT


def source_location(label, filename):
    path = ROOT/'sources/manuscript_v1.2.1'/filename
    lines = path.read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if '\\label{'+label+'}' in line)
    begin = next((i for i in range(index, -1, -1) if '\\begin{equation}' in lines[i]), index)
    end = next((i for i in range(index, len(lines)) if '\\end{equation}' in lines[i]), index)
    return {'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'label': label, 'line_start': begin+1, 'line_end': end+1}


def equation_crosswalk():
    records = []
    for label, file, code, status in [
        ('eq_dynamics','02_mm&nc.tex','src/panda_dynamics.py; panda_closed_loop.stepper.HeldTorqueHarness','IMPLEMENTED_NUMERICAL'),
        ('eq_skew_property','02_mm&nc.tex','tests/test_t28_raw_c.py','TESTED_NUMERICAL_NOT_GLOBAL'),
        ('eq_momentum','02_mm&nc.tex','tests/test_action3.py observer identity','IMPLEMENTED_IDENTITY_TEST'),
        ('eq_observer','02_mm&nc.tex','panda_closed_loop.observer.MomentumObserver','IMPLEMENTED_COMPONENT'),
        ('eq_obs_envelope','02_mm&nc.tex','panda_closed_loop.observer.ObserverEnvelope','CONTINUOUS_IDEAL_FORMULA; DISCRETE_EXTENSION_UNAPPROVED'),
        ('eq_controller','02_mm&nc.tex','panda_closed_loop.controller.SlotineLiController','IMPLEMENTED_COMPONENT'),
        ('eq_tracking','02_mm&nc.tex','tests/test_action3.py tracking identity','TESTED_NUMERICAL_IDENTITY'),
        ('eq_hocbf','02_mm&nc.tex','panda_closed_loop.barriers.BarrierEvaluator','IMPLEMENTED_COMPONENT'),
        ('eq_robust_cbf','02_mm&nc.tex','panda_closed_loop.barriers.BarrierEvaluator.rows','IMPLEMENTED_43_AFFINE_ROWS'),
        ('eq_hard_qp','02_mm&nc.tex','panda_closed_loop.qp.HardSafetyQP','IMPLEMENTED_COMPONENT; FULL_T27_NOT_RUN'),
        ('eq_envelopes','03_contribution.tex','M1 requirements registry','BLOCKED_MISSING_DOMAIN_CONSTANTS'),
        ('eq_res_bound','03_contribution.tex','M1 requirements registry','BLOCKED_MISSING_C_BOUNDS'),
        ('eq_beta_bounds','03_contribution.tex','M1 requirements registry','BLOCKED_MISSING_DERIVATIVE_BOUNDS'),
        ('eq_margins','03_contribution.tex','panda_closed_loop.margins.velocity_margin and disturbance_allowances','ALGEBRAIC_INTERFACES_ONLY; NO_JUSTIFIED_M1_NUMBERS'),
        ('eq_planner','03_contribution.tex','M1 registry and A2 preflight','NOT_IMPLEMENTED_ACTION3_SCOPE'),
        ('eq_brake','03_contribution.tex','panda_closed_loop.qp.project_torque_box','PROJECTION_ONLY; BRAKING_DISABLED_MISSING_KB'),
        ('eq_fallback','03_contribution.tex','QPResult + ProtectiveStop','SOFT_QP_DISABLED_MISSING_KB_GAMMA; STOP_REQUEST_INSTEAD')]:
        records.append({**source_location(label,file), 'code': code, 'status': status})
    return records


def m1_registry(policy, reference_kind=None):
    if reference_kind not in [None, 'stage1_tightened', 'nonoptimized_measured_state']:
        raise ValueError('Unrecognized A2 reference kind')
    data = []
    def add(name, shape, units, formula, dependencies, label, required=True):
        data.append({'name': name, 'shape': shape, 'units': units, 'formula': formula,
            'dependencies': dependencies, 'source': source_location(label, '03_contribution.tex'),
            'value': None, 'status': 'OPEN_MISSING_INPUT',
            'required_for_A2_entry': None if reference_kind is None else reference_kind == 'stage1_tightened',
            'required_for_A3_stage1': required,
            'evidence_level': 'Level 2 numerical estimate selected; no global interval certificate',
            'estimation_method_grid_seed_budget': None})
    add('m1', 'positive scalar', 'kg m^2', 'lower eigenvalue bound of M over declared Q; NOT sampled min', ['Q','estimator policy'], 'eq_envelopes')
    add('mbar_i', [7], '(kg m^2)^-1', 'sup_Q (M^-1)_ii', ['Q','estimator policy'], 'eq_envelopes')
    add('Nbar_Q_il', [7,7], '(kg m^2)^-1', 'sup_Q abs((M^-1)_il)', ['Q','estimator policy'], 'eq_envelopes')
    add('nu_and_yb', 'scalar function of physical t', 'sqrt(J)/s and sqrt(J)', 'nu=min(norm(varpi)/sqrt(m1),sqrt(varpi^T Nbar_Q varpi)); yb=convolution(exp(-kappa*t),nu)', ['varpi','m1','Nbar_Q_il'], 'eq_envelopes')
    add('chi_s_e_v', [3,7], 'rad/s; rad; rad/s', 'chi_s=sqrt(mbar)*yb; chi_e=convolution(exp(-Lambda*t),chi_s); chi_v=chi_s+Lambda*chi_e', ['mbar_i','nu_and_yb'], 'eq_envelopes')
    add('Tube_T_and_K', 'q/qd/a domain boxes', 'rad; rad/s; rad/s^2', 'T: widths chi_e,chi_v around candidate; K: acceleration width Lambda*chi_v', ['chi_s_e_v','speed_domain','acceleration_domain','tube_extension'], 'eq_beta_bounds')
    add('Cbar_li', [7,7], 'N m s/rad', 'sup_T abs(C_li)', ['Tube_T_and_K','M1 common fixed domain'], 'eq_res_bound')
    add('rho_r_i', [7], 'N m', 'exp(-kappa*t)*varpi0 + convolution(exp(-kappa*t), kappa*Cbar^T*chi_s+Ko*varpi+dbar1)', ['Cbar_li','chi_s_e_v','varpi'], 'eq_res_bound')
    for name, shape, units, formula in [
        ('Abar_jl',[15,7],'h_j/(N m s^2)','sup_T abs(grad(h_j)^T M^-1)'),
        ('Nbar_il',[7,7],'rad/(N m s^2)','sup_T abs(M^-1)'),
        ('Bbar_il',[7,7],'s^-1','sup_T abs(M^-1 C)'),
        ('Dbar_jl',[15,7],'h_j/(rad s)','sup_T abs(grad(h_j)^T M^-1 C)')]:
        add(name,shape,units,formula,['Tube_T_and_K','M1 common fixed domain'],'eq_margins')
    for family, rows, output in [('u',7,'N m'),('h',15,'h_j/s^2')]:
        for variable, unit in [('q','rad'),('qd','rad/s'),('qdd','rad/s^2')]:
            add(f'L_{family}_{variable}',[rows,7],f'({output})/({unit})',f'componentwise sup_K abs(partial {"ID" if family=="u" else "H_j"}/partial {variable})',
                ['Tube_T_and_K','derivative equation map','M1 common fixed domain'],'eq_beta_bounds')
    add('beta_u_and_beta_h', [7,15], 'N m; h_j/s^2', 'eq_beta_bounds with Lambda*chi_v acceleration segment', ['L_u_q','L_u_qd','L_u_qdd','L_h_q','L_h_qd','L_h_qdd','Cbar_li','chi_s_e_v'],'eq_beta_bounds')
    add('b_u_plus_minus_h_vB', '7+7+15+7', 'N m; h_j/s^2; rad/s^2', 'eq_margins; velocity term is abs(alpha_v-Lambda)*chi_v', ['beta_u_and_beta_h','rho_r_i','Abar_jl','Nbar_il','Bbar_il','Dbar_jl','varpi','zeta_plus_minus'],'eq_margins')
    add('residual_Lipschitz_La', 'one per tightened residual', 'residual unit/s', 'g_a(tk) >= L_a*Delta_c/2 requires justified interval/sample handling', ['Tube_T_and_K','derivative bounds','candidate residuals','grid policy'],'eq_planner')
    return {'schema':'M1-conditional-A2-scope-v1.2.2-draft','mode':'M1_COMMON_FROZEN_DOMAIN_CONSTANTS',
            'A2_reference_kind':reference_kind,'scope_note':'Unapproved/unselected A2 reference is a decision gate; planner-only constants are not unconditional online-filter prerequisites.',
            'domain_inputs':policy.raw['margin_mode'], 'known_inputs':{'Ko_s_inverse':policy.ko,'Lambda_s_inverse':policy.lambdas,
            'kappa_s_inverse':policy.kappa,'dbar':'0.02*taumax','dbar1':'1.4*dbar','q_extension_rad':.01},
            'entries':data,'observer_discretization_error_allowance':{'value':None,'status':'OPEN_ENGINEERING_GATE',
              'note':'No new theorem term invented. Continuous ideal envelope is not automatically a discrete/delayed observer certificate.'},
            'online_filter_note':'Local exact-model rows + analytic varpi can be component-tested without filling M1 planner constants; this does not clear the A2 entry gate.'}


def gates(policy, component_diagnostics=None):
    blockers = policy.a2_blockers()
    if component_diagnostics and component_diagnostics.get('PANDA_APPROVED_INITIAL_COMPONENT',{}).get('feasibility','').startswith('FAIL'):
        blockers.append('APPROVED_MIDPOINT_HARD_QP_COMPONENT_INFEASIBLE')
    return {'A1':{'decision':'GO','reason':'Continue additive implementation and component verification'},
        'A2':{'decision':'NO-GO (HOLD)','blockers':blockers,'executed':False},
        'A3':{'decision':'NO-GO','reason':'A2, complete T27, positive G2.5 and frozen planner/task settings missing','executed':False},
        'Level_1':{'decision':'NO-GO','reason':'No verified global m1, full bound suite or theorem hypotheses'},
        'publication':{'decision':'NO-GO','reason':'No authorized comparative experiments'},
        'T27':{'status':'COMPONENT_SOLVER_FIXTURES_ONLY; COMPLETE_PROTOCOL_NOT_RUN'},
        'G2.5':{'status':'NOT_RUN; static point-specific speed-row contradiction is not a G2.5 screen'},
        'approvals':policy.raw['approvals']}
