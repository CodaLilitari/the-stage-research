# SPDX-License-Identifier: Apache-2.0
"""Read-only, hash-pinned FINITE-L0 reduced operator and deliberate mutations.

The production reference is imported in place; it is not copied or modified.
This adapter does not import the independent oracle.
"""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import hashlib
import importlib.util
import math
import sys

REFERENCE_PATH=Path(__file__).resolve().parent.parent/'finite_inventory'/'revised_v1'/'reference.py'
REFERENCE_SHA256='5b5ba1dca3f182eb5f9e181c1bf514f9029ebfb88b4f14c726d40db6a3eebcc1'
if hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()!=REFERENCE_SHA256:
    raise RuntimeError('Production reference no longer matches the frozen source')
_name='_wexact0_finite_l0_reference'
_spec=importlib.util.spec_from_file_location(_name,REFERENCE_PATH)
ref=importlib.util.module_from_spec(_spec)
sys.modules[_name]=ref
_spec.loader.exec_module(ref)


def reduced_model(case,mutation=None):
    cfg=ref.Config(channel_volume=float(case['v1']),wall_volume=float(case['v2']),
                   channel_cells=1,flow=0,exchange=float(case['k']),
                   binding=0,release=0,sink=0,source=0)
    model=ref.build(cfg)
    c=model.index('C0.free'); w=model.index('W0.free')
    if mutation is None:return model
    if mutation=='wrong_volume':
        # Both entries of the wall-outgoing column retain opposite signs.
        # Incorrectly use V1 rather than V2 as the outgoing denominator.
        scale=cfg.wall_volume/cfg.channel_volume
        entries=tuple((row,col,rate*scale if col==w else rate) for row,col,rate in model.matrix)
    elif mutation=='sign_reversal':
        entries=tuple((row,col,-rate) for row,col,rate in model.matrix)
    elif mutation=='unbooked_clamp':
        # Remove the channel derivative while retaining its contribution to wall.
        entries=tuple((row,col,rate) for row,col,rate in model.matrix if row!=c)
    else:raise ValueError(f'Unknown deliberate mutation: {mutation}')
    return replace(model,matrix=entries)


def run_case(case,mutation=None):
    model=reduced_model(case,mutation)
    c=model.index('C0.free'); w=model.index('W0.free')
    y=ref.initial_amounts(model,{'C0.free':float(case['a10']),'W0.free':float(case['a20'])})
    slope=ref.rhs(model,y)
    sums=[Fraction(0) for _ in model.labels]
    for row,col,rate in model.matrix:sums[col]+=Fraction.from_float(rate)
    record={'case':case['id'],'mutation':mutation,'initial_slopes':[slope[c],slope[w]],
            'exact_column_balance':all(value==0 for value in sums),
            'column_sums_rational':[str(value) for value in sums],
            'amounts':None,'other_amounts':None,'balance_error':None,'minimum_seen':None,
            'steps':None,'actual_dt':None,'exception':None}
    try:
        solved=ref.solve(model,y,float(case['t']),float(case['dt']))
    except (ArithmeticError,ValueError) as exc:
        record['exception']={'type':type(exc).__name__,'message':str(exc)}
        return record
    record.update(amounts=[solved.amounts[c],solved.amounts[w]],
                  other_amounts=[v for i,v in enumerate(solved.amounts) if i not in (c,w)],
                  balance_error=math.fsum(solved.amounts)-math.fsum(y),
                  minimum_seen=solved.minimum_seen,steps=solved.steps,actual_dt=solved.actual_dt)
    return record
