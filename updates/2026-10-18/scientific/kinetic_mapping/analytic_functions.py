"""Public extraction: pure frozen AB-KMAP0 definitions; local launcher omitted."""
"""AB-KMAP0: guarded synthetic analytic checks; never fits or integrates data."""
from pathlib import Path
from fractions import Fraction as F
import ctypes, datetime as dt, hashlib, json, math, os, socket, sys, time

BASE = Path(__file__).resolve().parent

def coefficients(p):
    q, a, d = (F(p[k]) for k in ('q', 'a', 'd'))
    if min(q, a, d) <= 0:
        raise ValueError('strictly positive parameters required')
    return {'T': q+a+d, 'D': q*d, 'N': a*q, 'beta': a/d}

def poles(p):
    z = coefficients(p)
    T, D = float(z['T']), float(z['D'])
    root = math.sqrt(T*T-4*D)
    fast = (T+root)/2
    slow = D/fast
    return slow, fast

def evaluate(case, times):
    kind = case['kind']
    if 'parameters' in case:
        p = {k:F(v) for k,v in case['parameters'].items()}
        q, a, d = (p[k] for k in ('q','a','d'))
        z = coefficients(p)
    if kind == 'decay':
        b0, bp = F(case['b0']), F(case['bprime0'])
        ls, lf = poles(p)
        cs, cf = (float(bp)+lf*float(b0))/(lf-ls), -(float(bp)+ls*float(b0))/(lf-ls)
        return dict(z, c0=(bp+d*b0)/a, lambda_s=ls, lambda_f=lf,
                    slow_coefficient=cs, fast_coefficient=cf,
                    trace=[cs*math.exp(-ls*t)+cf*math.exp(-lf*t) for t in times])
    if kind == 'transfer_partner':
        pp = {'q':a+d, 'a':a*q/(a+d), 'd':d*q/(a+d)}
        return dict(z, partner_q=pp['q'], partner_a=pp['a'], partner_d=pp['d'],
                    same_calibrated_kernel=coefficients(pp)==z)
    if kind == 'internal_state':
        p2 = {k:F(v) for k,v in case['partner'].items()}
        b0, bp = F(case['b0']), F(case['bprime0'])
        c1, c2 = (bp+d*b0)/a, (bp+p2['d']*b0)/p2['a']
        dc1, dc2 = -(q+a)*c1+d*b0, -(p2['q']+p2['a'])*c2+p2['d']*b0
        return dict(first_c0=c1, second_c0=c2, first_cprime0=dc1, second_cprime0=dc2,
                    same_b_initial_conditions=(a*c1-d*b0==p2['a']*c2-p2['d']*b0==bp),
                    internal_derivatives_differ=(dc1!=dc2))
    if kind in ('shared_chemistry','shared_chemistry_reject'):
        z2 = coefficients(case['second'])
        deltaT, deltaD = z2['T']-z['T'], z2['D']-z['D']
        if kind == 'shared_chemistry_reject':
            return dict(delta_T=deltaT, delta_D=deltaD,
                        shared_chemistry_consistent=not(deltaT==0 and deltaD!=0))
        dd = deltaD/deltaT
        q1, q2 = z['D']/dd, z2['D']/dd
        aa = z['T']-q1-dd
        return dict(first_T=z['T'], first_D=z['D'], second_T=z2['T'], second_D=z2['D'],
                    recovered_d=dd, recovered_a=aa, first_q=q1, second_q=q2,
                    shared_chemistry_consistent=(min(dd,aa,q1,q2)>0 and z2['T']-q2-dd==aa))
    if kind == 'series_resistance':
        def conductance(v):
            P, film=F(v['P']),F(v['film'])
            return 1/(1/P+1/film)
        k1,k2=conductance(case['first']),conductance(case['second'])
        av=F(case['area_volume'])
        return dict(first_K=k1,second_K=k2,first_q=av*k1,second_q=av*k2,
                    distinct_resistances=case['first']!=case['second'])
    if kind in ('qssa_valid','qssa_invalid'):
        ls,lf=poles(p)
        kr,kf=d*q/(q+a),a*q/(q+a)
        return dict(qssa_forward=kf,qssa_reverse=kr,beta=a/d,epsilon_c=d/(q+a),
                    lambda_s=ls,relative_rate_error=abs(float(kr)/ls-1),pole_ratio=ls/lf)
    if kind == 'chemical_fast':
        ls,lf=poles(p)
        kr=q/(1+a/d)
        return dict(chemical_fast_forward=(a/d)*kr,chemical_fast_reverse=kr,
                    low_frequency_forward=z['N']/z['T'],low_frequency_reverse=z['D']/z['T'],
                    beta=a/d,chemical_rate_error=abs(float(kr)/ls-1),
                    internal_free_qssa_error=abs(float(d*q/(q+a))/ls-1),lambda_s=ls)
    if kind == 'nonlinear_scale':
        s={k:F(v) for k,v in case['state'].items()}; eta=F(case['eta'])
        def rhs(v):
            R=v['kon']*v['c']*(v['B']-v['b'])-v['koff']*v['b']
            total=v['q']*(v['u']-v['c'])
            return R,total-R,R,total,v['gain']*v['b']
        ss=dict(s)
        for k in ('c','b','B'): ss[k]*=eta
        ss['kon']/=eta;ss['gain']/=eta
        r,dc,db,total,y=rhs(s);rr,dcc,dbb,tt,yy=rhs(ss)
        residual=s['q']*(1-eta)
        return dict(R=r,cprime=dc,bprime=db,totalprime=total,scaled_R=rr,
                    scaled_cprime=dcc,scaled_bprime=dbb,scaled_totalprime=tt,
                    first_output=y,scaled_output=yy,
                    fixed_input_symmetry_residual_per_unit_u=residual,
                    fixed_nonzero_input_breaks_scale=residual!=0)
    raise ValueError('unknown case kind')

def compare(actual, expected):
    checks=[]
    for key,value in expected.items():
        if key.endswith('_lt') or key.endswith('_gt'):
            field,relation=key.rsplit('_',1); got=actual[field]
            ok=(got<value) if relation=='lt' else (got>value)
        else:
            got=actual[key]
            if isinstance(value,bool): ok=(got is value)
            elif isinstance(got,F): ok=(got==F(value))
            else: ok=math.isclose(float(got),float(F(value)),rel_tol=1e-12,abs_tol=1e-12)
        checks.append({'field':key,'passed':bool(ok),'actual':got,'expected':value})
    return checks

def write_json(path, obj):
    path.write_text(json.dumps(obj,indent=2,default=lambda x:str(x) if isinstance(x,F) else x),encoding='utf-8')
