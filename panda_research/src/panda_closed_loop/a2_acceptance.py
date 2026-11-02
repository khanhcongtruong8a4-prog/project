"""Read-only technical acceptance tools; no controller/model parameter changes.

Exact arithmetic below certifies only a represented finite affine QP. It is
not an interval certificate for the robot model, ODE, or sampled trajectory.
"""
from fractions import Fraction as F
from pathlib import Path
import gzip,hashlib,json
import numpy as np
from .trace_archive import read_trace

IGNORED_REPLAY_KEYS=frozenset({'solve_runtime_s'})


def scientific_value(value):
    if isinstance(value,dict):
        return {k:scientific_value(v) for k,v in value.items() if k not in IGNORED_REPLAY_KEYS}
    if isinstance(value,list):return [scientific_value(v) for v in value]
    return value


def scientific_digest(value):
    payload=json.dumps(scientific_value(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def read_recorded_trace(folder,record):
    path=Path(folder)/record['file']
    if record.get('codec'):return read_trace(path,record)
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Gzip trace hash mismatch')
    raw=gzip.decompress(data)
    if hashlib.sha256(raw).hexdigest()!=record['uncompressed_json_sha256']:raise ValueError('Raw JSON hash mismatch')
    return json.loads(raw)


def first_differences(a,b,path='',limit=20):
    out=[]
    if type(a)!=type(b):return [{'path':path,'reason':'type','old':str(type(a)),'new':str(type(b))}]
    if isinstance(a,dict):
        if set(a)!=set(b):out.append({'path':path,'reason':'keys'})
        for k in sorted(set(a)&set(b)):
            out.extend(first_differences(a[k],b[k],path+'/'+k,limit-len(out)))
            if len(out)>=limit:break
    elif isinstance(a,list):
        if len(a)!=len(b):out.append({'path':path,'reason':'length','old':len(a),'new':len(b)})
        for i,(x,y) in enumerate(zip(a,b)):
            out.extend(first_differences(x,y,path+'/'+str(i),limit-len(out)))
            if len(out)>=limit:break
    elif a!=b:out.append({'path':path,'old':a,'new':b})
    return out[:max(limit,0)]


def compare_cell(old,new,old_folder,new_folder):
    checks={'grid_exact':old['grid']==new['grid'],
        'metrics_exact':old['a2']['metrics']==new['a2']['metrics'],
        'post_P1_state_exact':old['endpoint']['state']==new['endpoint']['state'],
        'final_state_exact':old['a2']['final_state']==new['a2']['final_state'],
        'new_P1_completed':new['prehold']['completed'],'new_endpoint_QP_pass':new['endpoint']['QP']['strict_pass'],
        'new_motion_completed':new['a2']['completed'],'new_cell_pass':new['a2']['passed'],
        'new_full_audit_pass':new['audit']['passed']}
    traces={}
    for phase in ['prehold','a2']:
        a=read_recorded_trace(old_folder,old[phase]['trace']);b=read_recorded_trace(new_folder,new[phase]['trace'])
        ah,bh=scientific_digest(a),scientific_digest(b)
        checks[phase+'_full_scientific_trace_exact']=ah==bh
        traces[phase]={'recorded_scientific_sha256':ah,'replay_scientific_sha256':bh,
                       'exact':ah==bh,'first_differences':[] if ah==bh else first_differences(scientific_value(a),scientific_value(b))}
    return {'cell':new['cell'],'passed':all(checks.values()),'checks':checks,'trace_comparison':traces,
            'ignored_trace_fields':sorted(IGNORED_REPLAY_KEYS),
            'ignored_field_scope':'Measured solver wall time only; no model/state/control/constraint/solver-result field excluded.'}


def fraction_solve(A,b):
    """Exact Gauss-Jordan elimination; singular hypotheses are rejected."""
    n=len(b);m=[list(row)+[rhs] for row,rhs in zip(A,b)]
    for j in range(n):
        pivot=next((i for i in range(j,n) if m[i][j]),None)
        if pivot is None:raise ValueError('Singular exact active-set hypothesis')
        m[j],m[pivot]=m[pivot],m[j]
        d=m[j][j];m[j]=[x/d for x in m[j]]
        for i in range(n):
            if i!=j:
                d=m[i][j];m[i]=[a-d*c for a,c in zip(m[i],m[j])]
    return [row[-1] for row in m]


def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))


def exact_qp_certificate(nominal,rows,active):
    """Independent active-set KKT witness for the actual scaled binary64 QP.

    Active indices are a hypothesis, not assumed correct. Exact primal signs,
    dual signs, complementarity and stationarity verify its global optimality
    for H=I. No production solve, repair or actuation occurs here.
    """
    den=87.*np.linalg.norm(rows.G,axis=1);den=np.where(den>0,den,1.)
    C=-87.*rows.G/den[:,None];b=(rows.c-1e-8*rows.scales)/den
    n=np.asarray(nominal)/87.
    A=[[F.from_float(float(x)) for x in row] for row in C]
    rhs=[F.from_float(float(x)) for x in b];target=[F.from_float(float(x)) for x in n]
    face=[A[i] for i in active]
    gram=[[dot(a,c) for c in face] for a in face]
    lam=fraction_solve(gram,[dot(row,target)-rhs[i] for row,i in zip(face,active)]) if active else []
    point=[x-sum((w*row[j] for row,w in zip(face,lam)),F(0)) for j,x in enumerate(target)]
    slacks=[bound-dot(row,point) for row,bound in zip(A,rhs)]
    dual=[F(0)]*len(A)
    for i,w in zip(active,lam):dual[i]=w
    gradient=[point[j]-target[j]+sum((row[j]*w for row,w in zip(A,dual)),F(0)) for j in range(7)]
    checks={'all_inequalities_exact_nonnegative':all(s>=0 for s in slacks),
            'all_duals_exact_nonnegative':all(w>=0 for w in dual),
            'stationarity_exact_zero':all(x==0 for x in gradient),
            'complementarity_exact_zero':all(w*s==0 for w,s in zip(dual,slacks))}
    encode=lambda x:{'numerator':str(x.numerator),'denominator':str(x.denominator)}
    return {'passed':all(checks.values()),'checks':checks,'active_indices':list(active),
            'unique_optimum_y_float_display_only':[float(x) for x in point],
            'exact_optimum_y':[encode(x) for x in point],
            'exact_dual':[encode(x) for x in dual],'exact_scaled_slacks':[encode(x) for x in slacks],
            'scope':'EXACT_RECORDED_BINARY64_SCALED_STRICTLY_CONVEX_QP_ONLY; NOT_EXACT_ROBOT_MODEL_OR_LEVEL1',
            'hypothesis_selection':'Supplied indices; all KKT sufficiency conditions independently verified in rational arithmetic'}
