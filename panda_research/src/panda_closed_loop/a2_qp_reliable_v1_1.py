"""Conservative classification extension; the v1 sign-corrected solver remains.

A zero-normal inequality is a constant test, not an optimization problem.
No feasible torque is synthesized and no constraint is removed or relaxed.
All nonzero-normal problems execute the unmodified v1 solve function.
"""
import multiprocessing as mp
import numpy as np
from .a2_qp_reliable_v1 import GuardedHardQP as SignCorrectedQP
from .a2_qp_reliable_v1 import BoundedGuardedQP as SignCorrectedBoundedQP
from .a2_qp_reliable_v1 import NUMERICAL_POLICY
from .barriers import AffineRows
from .qp import QPResult


class GuardedHardQP(SignCorrectedQP):
    def solve(self,u_nom,rows):
        if not isinstance(rows,AffineRows):raise ValueError('Expected AffineRows')
        constant=rows.c-NUMERICAL_POLICY['inward_guard_original_row_scale']*rows.scales
        impossible=np.where(np.all(rows.G==0.,axis=1)&(constant<0.))[0]
        if len(impossible):
            i=int(impossible[0])
            return QPResult(None,'EXACT_CONSTANT_ROW_INFEASIBLE',True,{
                'classification_version':'GUARDED_QP_RELIABILITY_V1_1',
                'row_index':i,'row_name':rows.names[i],'guarded_affine_constant':float(constant[i]),
                'exact_certificate':'All seven coefficients equal binary zero; guarded constant is strictly negative.',
                'replan_requested':True,'torque_applied':False,'cold_solves':0,
                'retry':False,'post_solve_repair':False,'witness_fallback':False})
        return super().solve(u_nom,rows)


def _worker(connection,limits):
    qp=GuardedHardQP(limits)
    try:
        connection.send('READY')
        while True:
            payload=connection.recv()
            if payload is None:break
            connection.send(qp.solve(*payload))
    finally:connection.close()


class BoundedGuardedQP(SignCorrectedBoundedQP):
    def __enter__(self):
        ctx=mp.get_context('spawn');self.connection,child=ctx.Pipe()
        self.process=ctx.Process(target=_worker,args=(child,self.taumax),daemon=True)
        self.process.start();child.close()
        if not self.connection.poll(self.timeout_s) or self.connection.recv()!='READY':
            self.close();raise RuntimeError('QP worker did not initialize')
        return self
