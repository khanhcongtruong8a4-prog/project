"""Consolidated public API for the qualified sign-corrected guarded QP.

The implementation is the preserved v1.1 classifier delegating all nonzero
rows to the frozen v1 sign-corrected native kernel. No numerical setting,
guard, objective, constraint or actuation behavior changes in this facade.
The rejected projected-feedback development sampler is NOT exported here.
"""
from types import MappingProxyType
from .a2_qp_reliable_v1_1 import GuardedHardQP,BoundedGuardedQP
from .a2_qp_v2 import NUMERICAL_POLICY as _NUMERICAL_POLICY,audit_qp_numerics
from .guarded_qp_native_v1 import backend_record

QP_NUMERICS=MappingProxyType(dict(_NUMERICAL_POLICY))
RELEASE=MappingProxyType({'name':'GUARDED_QP_FINAL_API_V1','underlying_algorithm':'SUPPORT_SIGN_V1_PLUS_EXACT_CONSTANT_ROW_CLASSIFIER_V1_1',
    'tested_native_library_sha256':'3370c29e2c3e42db44bc7cfed1d385ebc6680a519a1501693c223575122fc8c1',
    'runtime_witness_fallback':False,'native_kernel_solves_per_ordinary_query':1,
    'qualification_scope':'Finite 39-fixture strict KKT/Farkas regression; not universal or Level1 certification.'})

def verify_release():
    record=backend_record()
    if record['library_sha256']!=RELEASE['tested_native_library_sha256']:raise ValueError('Different build requires separate qualification')
    return {'release':dict(RELEASE),'settings':dict(QP_NUMERICS),'backend':record}
