"""Coda recovery of Wren's eight-case linear benchmark; NOT EXECUTED at preparation.
Requires separate coordinator admission. No network, parameter search or retries.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
REL, ABS = 1e-10, 1e-14

def close(x, y):
    return abs(x-y) <= ABS + REL*abs(y)

def atomic_json(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x', encoding='utf-8', newline='\n') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)

def direct_rk4(a, k, g, T, c0):
    # Deliberately independent of Wren's matrix and exact/eigenvalue functions.
    bound = a + k*(g+1)
    hmax = min(.001, .01/bound) if bound > 0 else .001
    steps = math.ceil(T/hmax)
    h = T/steps
    state = [c0, g*c0, 0.0]
    def rhs(x):
        exchange = k*(g*x[0]-x[1])
        removal = a*x[0]
        return [-removal-exchange, exchange, removal]
    for _ in range(steps):
        p = rhs(state)
        q = rhs([x+h*v/2 for x,v in zip(state,p)])
        r = rhs([x+h*v/2 for x,v in zip(state,q)])
        s = rhs([x+h*v for x,v in zip(state,r)])
        state = [x+h*(v+2*w+2*y+z)/6 for x,v,w,y,z in zip(state,p,q,r,s)]
    return dict(c=state[0], b=state[1], U_integrated=state[2], steps=steps, rhs_evaluations=4*steps)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-reviewed', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute_reviewed:
        parser.error('Separate coordinator admission and --execute-reviewed required')
    # Byte check before importing the preserved unexecuted analytic implementation.
    source = ROOT/'wren_fixed_unexecuted.py'
    if hashlib.sha256(source.read_bytes()).hexdigest() != '584c43a2dbce37ffeb1178cf7286813b04216cbcd06b8be6f0484c551f964237':
        raise RuntimeError('Wren source bytes changed')
    import wren_fixed_unexecuted as upstream
    plan = json.loads((ROOT/'proposed_cases.json').read_text(encoding='utf-8'))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    c0 = plan['c0']
    data = {}
    checks = {}
    count = 0
    started = time.monotonic()
    ledger = (output/'ledger.jsonl').open('x', encoding='utf-8', newline='\n')
    def event(item):
        item['utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ledger.write(json.dumps(item, allow_nan=False)+'\n')
        ledger.flush()
        os.fsync(ledger.fileno())
    def evaluate(name, method, fn):
        nonlocal count
        if count >= 16 or time.monotonic()-started > 120:
            raise RuntimeError('Evaluation or elapsed budget exhausted before reservation')
        count += 1
        event(dict(evaluation=count, case=name, method=method, status='started'))
        try:
            result = fn()
            atomic_json(output/f'{count:02d}_{name}_{method}.json', result)
            event(dict(evaluation=count, case=name, method=method, status='completed'))
            return result
        except BaseException as exc:
            event(dict(evaluation=count, case=name, method=method, status='failed', error=type(exc).__name__, detail=str(exc)))
            raise
    def exact_bundle(a,k,g,T):
        c,b,info = upstream.exact(a,k,g,T,c0)
        U = c0*(1+g)-c-b
        integral = a*upstream.int_c(a,k,g,T)
        return dict(c=c,b=b,U=U,a_int_c=integral, info=info,
                    endpoint_evaluations=1,quadrature_samples=2048)
    finite = {n: [1/30 if v == '1/30' else v for v in values]
              for n,values in plan['finite_cases'].items()}
    try:
        for n,values in finite.items():
            data[n] = evaluate(n,'exact_balance',lambda v=values: exact_bundle(*v))
        for n,values in finite.items():
            result = evaluate(n,'rk4',lambda v=values: direct_rk4(*v,c0))
            reference = data[n]
            reference['independent_rk4'] = result
            checks[n+'_rk4'] = all(close(result[k],reference[k]) for k in ('c','b')) and close(result['U_integrated'],reference['U'])
            checks[n+'_balance'] = abs(reference['U']-reference['a_int_c']) <= ABS + REL*max(abs(reference['U']),abs(reference['a_int_c']))
            checks[n+'_finite_nonnegative'] = all(math.isfinite(reference[k]) for k in ('c','b','U')) and reference['c'] >= 0 and reference['b'] >= 0
        def algebraic(case):
            a,g,T = (case[k] for k in ('a','gamma','T'))
            c = c0*math.exp(-a*T/(1+g))
            return dict(c=c,b=g*c,U=-(1+g)*c0*math.expm1(-a*T/(1+g)))
        for n in ('D','E'):
            data[n] = evaluate(n,'algebraic',lambda n=n: algebraic(plan[n]))
        h = plan['hydraulics']
        def hydraulic(factor):
            resistance = 12*h['mu']*factor*h['L']/(h['W']*h['h']**3)
            qp = h['pressure_cap']/resistance
            qw = math.sqrt(h['fluid_power_cap']/resistance)
            q = min(qp,qw)
            return dict(R=resistance,Q=q,T=h['V']/q,pressure=q*resistance,
                        fluid_power=q*q*resistance,binding='pressure' if qp <= qw else 'power')
        for n,factor,T in (('dissolved',1,3),('carrier',4,8)):
            row = evaluate(n,'hydraulics',lambda f=factor: hydraulic(f))
            data[n] = row
            checks[n+'_hydraulics'] = close(row['T'],T) and row['pressure'] <= h['pressure_cap']*(1+1e-12) and row['fluid_power'] <= h['fluid_power_cap']*(1+1e-12)
        limit_c = c0*math.exp(-.2*8)
        checks['F1_limit'] = abs(data['F1']['c']/limit_c-1) <= 1e-12 and abs(data['F1']['b']-4*c0) <= 1e-12*4*c0
        checks['F4_limit'] = abs(data['F4']['c']/limit_c-1) <= 1e-12 and abs(data['F4']['b']) <= ABS
        checks['F5_limit'] = abs(data['F5']['U']) <= ABS
        diagnostic = dict(F3_minus_E_c=data['F3']['c']-data['E']['c'],
                          F2_minus_D_c=data['F2']['c']-data['D']['c'],
                          F6_flow_note='T=80 diagnostic only; no QU at the T=8 hydraulic flow')
        atomic_json(output/'results.json',dict(byline='Coda local recovery of Wren linear benchmark',
                    evaluations=count,cases=data,checks=checks,all_checks_pass=all(checks.values()),
                    diagnostic=diagnostic,seconds=time.monotonic()-started))
        if not all(checks.values()):
            raise RuntimeError('Completed evaluations include failed checks; preserved without retry')
    finally:
        ledger.close()

if __name__ == '__main__':
    main()
