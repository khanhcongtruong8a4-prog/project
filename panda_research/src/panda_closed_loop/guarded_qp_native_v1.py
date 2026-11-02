"""Narrow adapter for the locally built support-function sign correction.

No stored witness, optimization fallback, warm start, projection or retry.
The original ProxQP wheel remains installed and unmodified for old replays.
"""
from pathlib import Path
from types import SimpleNamespace
import ctypes, hashlib, json, os
import numpy as np
import proxsuite as upstream

ROOT=Path(__file__).resolve().parents[2]
VERSION='0.7.2+guarded-support-sign-v1'
_CACHE={}

def build_directory():
    return Path(os.environ.get('PANDA_GUARDED_QP_BUILD',str(ROOT/'native/build_guarded_qp_v1'))).resolve()

def backend_record():
    path=build_directory();record=json.loads((path/'BUILD.json').read_text())
    library=path/'libpanda_guarded_qp.so'
    if not record['patched'] or record['instrumented']:raise ValueError('Requires corrected noninstrumented backend')
    if hashlib.sha256(library.read_bytes()).hexdigest()!=record['library_sha256']:raise ValueError('Backend binary checksum differs')
    wrapper=ROOT/'native/guarded_qp_reliability_v1.cpp'
    if hashlib.sha256(wrapper.read_bytes()).hexdigest()!=record['wrapper_sha256']:raise ValueError('Backend wrapper source differs')
    if hashlib.sha256((path/'applied.patch').read_bytes()).hexdigest()!=record['applied_patch_sha256']:raise ValueError('Backend patch differs')
    return record

def kernel():
    path=build_directory()
    if str(path) not in _CACHE:
        record=backend_record();lib=ctypes.CDLL(str(path/'libpanda_guarded_qp.so'))
        fun=lib.panda_qp_solve;pointer=ctypes.POINTER(ctypes.c_double)
        fun.argtypes=[ctypes.c_int]+[pointer]*6;fun.restype=ctypes.c_int
        _CACHE[str(path)]=(lib,fun,record)
    return _CACHE[str(path)]

def raw_solve(target,C,b):
    """Single cold native solve; returned values are NOT acceptance/actuation."""
    _,fun,record=kernel();m=len(b)
    arrays=[np.ascontiguousarray(a,dtype=np.float64) for a in [target,C,b]]
    x=np.zeros(7);z=np.zeros(m);info=np.zeros(5)
    pointer=ctypes.POINTER(ctypes.c_double)
    code=fun(m,*[a.ctypes.data_as(pointer) for a in arrays+[x,z,info]])
    if code!=0:raise RuntimeError('Corrected ProxQP kernel exception')
    result=SimpleNamespace(x=x,z=z,info=SimpleNamespace(
        status=upstream.proxqp.QPSolverOutput(int(info[0])),iter=int(info[1]),
        duality_gap=float(info[2]),pri_res=float(info[3]),dua_res=float(info[4])))
    return result

class CorrectedDenseQP:
    """Only the fixed seven-variable upper-inequality problem is supported."""
    def __init__(self,n,n_eq,m):
        if n!=7 or n_eq!=0:raise ValueError('Unsupported QP dimensions')
        self.m=m;self.settings=SimpleNamespace();self.initialized=False
    def init(self,H,g,A,a,C,l,b):
        if not np.array_equal(H,np.eye(7)) or A is not None or a is not None:
            raise ValueError('Changed Hessian/equality data')
        if np.shape(C)!=(self.m,7) or not np.all(np.isneginf(l)):
            raise ValueError('Changed inequality representation')
        self.target=-np.array(g,copy=True);self.C=np.array(C,copy=True);self.b=np.array(b,copy=True)
        self.initialized=True
    def solve(self):
        expected=dict(eps_abs=1e-12,eps_rel=0.,max_iter=10000,check_duality_gap=True,
                      eps_duality_gap_abs=1e-12,eps_duality_gap_rel=0.)
        if vars(self.settings)!=expected or not self.initialized:raise ValueError('Changed fixed solver settings')
        self.results=raw_solve(self.target,self.C,self.b)

# An explicit adapter, not a modification of the upstream module or wheel.
corrected_proxsuite=SimpleNamespace(__version__=VERSION,proxqp=SimpleNamespace(
    dense=SimpleNamespace(QP=CorrectedDenseQP),QPSolverOutput=upstream.proxqp.QPSolverOutput))
