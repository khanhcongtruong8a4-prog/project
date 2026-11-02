"""Causal interval QP rows with explicitly checked current-state hard rows.

Versioned DIGITAL controller amendment. The unmodified physical 43-row
constraints are recomputed and strictly checked on the final QP torque.
No continuous-time theorem or certified drift bound is supplied here.
"""
import multiprocessing as mp
import numpy as np
from .barriers import AffineRows
from .qp import QPResult
from .a2_qp_v2 import GuardedHardQP,BoundedGuardedQP,audit_qp_numerics,NUMERICAL_POLICY


SAMPLING_QP_POLICY={
    'version':'A2_CAUSAL_INTERVAL_QP_V3',
    'row_sampler':'B0=B_current; Bk=B_current+0.5*(B_current-B_previous), B in {G,c}',
    'nominal_sampler':'UNCHANGED_AB2_r; u0=r0; uk=rk+0.5*(rk-r_previous)',
    'fixed_inward_reserve_original_row_scale':0.1,
    'roundoff_guard_original_row_scale':NUMERICAL_POLICY['inward_guard_original_row_scale'],
    'actual_solved_rows':'G_interval tau+c_interval-0.1*original_scale >= roundoff_guard*original_scale',
    'mandatory_current_state_check':'All ORIGINAL G_current tau+c_current >=0 exactly in float arithmetic before application',
    'history':'Fresh per cell; actual entrance QP is first query and reused for first application; one query per attempt; no future data',
    'T29_scope':'Actual declared digital QP, recomputed with retained duals; current physical rows have a separate exact raw sign gate',
    'reserve_status':'ENGINEERING_DESIGN_CONSTANT_NOT_CERTIFIED_M1_DRIFT_BOUND',
    'retry':False,'post_QP_projection':False,
}


def interval_rows(current,previous):
    if previous is None:G,c=current.G.copy(),current.c.copy()
    else:
        if current.names!=previous.names or not np.array_equal(current.scales,previous.scales):
            raise ValueError('Physical row identities/scales changed')
        G=current.G+.5*(current.G-previous.G)
        c=current.c+.5*(current.c-previous.c)
    return AffineRows(G,c-SAMPLING_QP_POLICY['fixed_inward_reserve_original_row_scale']*current.scales,
                      current.scales,current.names,current.units)


class IntervalHardQP:
    def __init__(self,taumax):
        self.base=GuardedHardQP(taumax);self.previous=None;self.index=0

    def solve(self,u_nom,current):
        actual=interval_rows(current,self.previous)
        result=self.base.solve(u_nom,actual)
        d=dict(result.diagnostics)
        d.update(actual_QP_diagnostics=result.diagnostics,
                 sampling_QP_policy=SAMPLING_QP_POLICY,sampling_QP_index=self.index,
                 actual_QP_rows={'G':actual.G.tolist(),'c':actual.c.tolist(),'scales':actual.scales.tolist(),
                                 'names':actual.names,'units':actual.units},
                 previous_current_rows=None if self.previous is None else {'G':self.previous.G.tolist(),'c':self.previous.c.tolist()})
        self.previous=current;self.index+=1
        if result.applied is None:
            return QPResult(None,result.status,True,d)
        raw=current.slacks(result.applied)
        d.update(raw_slacks=raw.tolist(),normalized_slacks=(raw/current.scales).tolist(),
                 exact_all_rows_nonnegative=bool(np.all(raw>=0)),negative_raw_row_count=int(np.sum(raw<0)),
                 current_physical_row_minimum=float(np.min(raw/current.scales)),
                 actual_QP_target_scope='EXPLICIT_V3_INTERVAL_ROWS_NOT_ORIGINAL_CONTINUOUS_INSTANTANEOUS_QP')
        if np.any(raw<0):
            d['replan_requested']=True
            return QPResult(None,'CURRENT_RAW_ROW_REJECTION',True,d)
        return QPResult(result.applied,result.status,result.stop_requested,d)


def _worker(connection,limits):
    qp=IntervalHardQP(limits)
    try:
        connection.send('READY')
        while True:
            payload=connection.recv()
            if payload is None:break
            connection.send(qp.solve(*payload))
    finally:connection.close()


class BoundedIntervalQP(BoundedGuardedQP):
    def __init__(self,taumax,settings=None,timeout_s=15.):
        if settings is not None and dict(settings)!=SAMPLING_QP_POLICY:raise ValueError('Changed digital QP policy')
        super().__init__(taumax,timeout_s=timeout_s)
        self.settings=dict(SAMPLING_QP_POLICY)

    def __enter__(self):
        ctx=mp.get_context('spawn');self.connection,child=ctx.Pipe()
        self.process=ctx.Process(target=_worker,args=(child,self.taumax),daemon=True)
        self.process.start();child.close()
        if not self.connection.poll(self.timeout_s) or self.connection.recv()!='READY':
            self.close();raise RuntimeError('QP worker did not initialize')
        return self


def audit_interval_numerics(updates,taumax):
    previous=None;checks={'causal_interval_rows_exact':True,'current_physical_raw_nonnegative':True,
                          'one_QP_per_controller_sample':True,'no_projection_or_retry':True}
    actual_updates=[];minimum=np.inf
    for i,u in enumerate(updates):
        current=AffineRows(u['G'],u['c'],u['row_scales'],tuple(u['row_names']),tuple(u['row_units']))
        actual=interval_rows(current,previous);d=u['diagnostics'];r=d['actual_QP_rows'];tau=np.array(u['candidate_tau'])
        expected_previous=None if previous is None else {'G':previous.G.tolist(),'c':previous.c.tolist()}
        checks['causal_interval_rows_exact'] &= (np.array_equal(actual.G,r['G']) and np.array_equal(actual.c,r['c'])
                 and d['previous_current_rows']==expected_previous and d['sampling_QP_policy']==SAMPLING_QP_POLICY)
        raw=current.slacks(tau);checks['current_physical_raw_nonnegative'] &= np.all(raw>=0) and np.array_equal(raw,u['raw_slacks'])
        minimum=min(minimum,float(np.min(raw/current.scales)))
        checks['one_QP_per_controller_sample'] &= d['sampling_QP_index']==i==u['tracking_errors']['sampling_update_index']
        checks['no_projection_or_retry'] &= np.array_equal(tau,d['actual_QP_diagnostics']['tau_candidate'])
        actual_updates.append({**u,'G':actual.G,'c':actual.c,'raw_slacks':actual.slacks(tau),
                               'diagnostics':d['actual_QP_diagnostics']})
        previous=current
    kkt=audit_qp_numerics(actual_updates,taumax)
    checks={k:bool(v) for k,v in checks.items()}
    return {'passed':bool(updates) and all(checks.values()) and kkt['passed'],'checks':checks,
            'actual_digital_QP_KKT_audit':kkt,'minimum_original_current_normalized_raw_slack':minimum,
            'scope':'DECLARED_CAUSAL_INTERVAL_QP_AND_ALL_ORIGINAL_CURRENT_HARD_ROWS_CHECKED_SEPARATELY',
            'QP_resolves_performed':False}
