"""Separate exact and SLSQP validation of represented guarded QPs; no actuation."""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog, minimize
from .a2_acceptance import exact_qp_certificate, dot
from .barriers import AffineRows


def scaled_data(nominal,rows):
    den=87*np.linalg.norm(rows.G,axis=1);den=np.where(den>0,den,1.)
    return np.asarray(nominal)/87.,-87*rows.G/den[:,None],(rows.c-1e-8*rows.scales)/den


def exact_unique_linear(A,b):
    """Overdetermined rational system, requiring a unique consistent solution."""
    n=len(A[0]);m=[list(r)+[v] for r,v in zip(A,b)];row=0;pivots=[]
    for col in range(n):
        pivot=next((i for i in range(row,len(m)) if m[i][col]),None)
        if pivot is None:continue
        m[row],m[pivot]=m[pivot],m[row];d=m[row][col];m[row]=[x/d for x in m[row]]
        for i in range(len(m)):
            if i!=row:
                d=m[i][col];m[i]=[x-d*y for x,y in zip(m[i],m[row])]
        pivots.append(col);row+=1
    if len(pivots)!=n or any(not any(r[:n]) and r[n] for r in m):raise ValueError('No unique exact solution')
    return [m[i][-1] for i in range(n)]


def infeasibility_certificate(C,b):
    # HiGHS selects a support; its floating output alone is not a certificate.
    lp=linprog(b,A_eq=np.vstack([C.T,np.ones(len(b))]),b_eq=np.r_[np.zeros(7),1.],
               bounds=[(0,None)]*len(b),method='highs',options={'primal_feasibility_tolerance':1e-10,'dual_feasibility_tolerance':1e-10})
    if not lp.success:return {'passed':False,'LP_status':int(lp.status)}
    active=np.where(lp.x>1e-10)[0].tolist()
    try:
        A=[[F.from_float(float(C[i,j])) for i in active] for j in range(7)]+[[F(1)]*len(active)]
        lam=exact_unique_linear(A,[F(0)]*7+[F(1)])
        support=sum((F.from_float(float(b[i]))*w for i,w in zip(active,lam)),F(0))
        ok=all(w>=0 for w in lam) and support<0
        return {'passed':ok,'support_indices':active,'exact_dual':[str(w) for w in lam],
                'exact_support':str(support),'scope':'EXACT_BINARY64_GUARDED_QP_FARKAS_CERTIFICATE'}
    except ValueError as e:return {'passed':False,'reason':str(e),'support_indices':active}


def validate(nominal,rows):
    n,C,b=scaled_data(nominal,rows)
    lp=linprog(np.zeros(7),A_ub=C,b_ub=b,bounds=[(None,None)]*7,method='highs',
               options={'primal_feasibility_tolerance':1e-10,'dual_feasibility_tolerance':1e-10})
    if not lp.success:
        cert=infeasibility_certificate(C,b)
        return {'feasible':False,'passed':lp.status==2 and cert['passed'],'LP_status':int(lp.status),'exact_certificate':cert}
    independent=minimize(lambda x:.5*np.dot(x-n,x-n),np.zeros(7),jac=lambda x:x-n,method='SLSQP',
        constraints=[{'type':'ineq','fun':lambda x:b-C@x,'jac':lambda x:-C}],options={'ftol':1e-14,'maxiter':1000})
    active=np.where(abs(b-C@independent.x)<1e-8)[0].tolist();cert=None
    # Active sets are hypotheses. Every inequality and KKT identity is then
    # checked exactly, including rows not selected by the independent solver.
    for count in range(min(7,len(active))+1):
        for hypothesis in combinations(active,count):
            try:trial=exact_qp_certificate(nominal,rows,hypothesis)
            except ValueError:continue
            if trial['passed']:cert=trial;break
        if cert is not None:break
    error=None if cert is None else float(np.max(abs(independent.x-cert['unique_optimum_y_float_display_only'])))
    return {'feasible':True,'passed':cert is not None and error<=1e-9,
        'separate_algorithm':'SLSQP, zero initialization, never given an exact witness',
        'SLSQP_status':int(independent.status),'SLSQP_success':bool(independent.success),
        'SLSQP_scaled_primal':float(max(0.,np.max(C@independent.x-b))),
        'SLSQP_error_vs_exact':error,'exact_certificate':cert}


def fixtures(root):
    base=json.loads((Path(root)/'reports/a2_extended_v1/qp_bounds_evidence/run_v2/t27_fixtures.json').read_text())
    out=[]
    for f in base:out.append((f['name'],f['nominal'],AffineRows(f['G'],f['c'],f['scales'],tuple(f['row_names']),tuple(f['row_units']))))
    actual=base[9];G=np.array(actual['G']);c=np.array(actual['c']);s=np.array(actual['scales'])
    for exponent in [-20,-10,10,20]:
        factors=2.**np.linspace(-exponent,exponent,43)
        out.append((f'actual_43_positive_scaling_span_{2*abs(exponent)}bits',actual['nominal'],
            AffineRows(G*factors[:,None],c*factors,s*factors,tuple(actual['row_names']),tuple(actual['row_units']))))
    for sign in [-1,1]:
        for coordinate in range(7):
            n=np.array(actual['nominal']);n[coordinate]+=sign*.001
            out.append((f'actual_43_nominal_j{coordinate+1}_{sign:+d}_millinewtonmetre',n,
                AffineRows(G,c,s,tuple(actual['row_names']),tuple(actual['row_units']))))
    for constant in [1.,0.,-1.]:
        out.append((f'zero_normal_constant_{constant}',np.zeros(7),AffineRows(np.zeros((1,7)),[constant],[1.],('zero',),('test',))))
    return out
