#!/usr/bin/env python3
"""Analytic and numerical oxygen-transport diagnostics, standard library only.

S model: tissue-wall local balance gives c_t = f*c_b, 0 <= f <= 1.
Along a unit serial channel, dc_b/dx = -Da*f*c_b, c_b(0)=1.
Hence distal c_t = f*exp(-Da*f), while extracted fraction = 1-exp(-Da*f).
H model: Hill equilibrium plus a first-order relaxation diagnostic.
These are mathematical test fixtures, not experimentally calibrated fluids.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

def require_finite(*values: float) -> None:
    if not all(math.isfinite(v) for v in values):
        raise ValueError('All numeric arguments must be finite')

def exact_transport(da: float, f: float) -> dict[str, float]:
    require_finite(da, f)
    if da < 0 or not 0 <= f <= 1:
        raise ValueError('Da must be nonnegative and wall fraction in [0,1]')
    cb = math.exp(-da*f)
    return {'channel_out': cb, 'distal_tissue': f*cb,
            'extraction_fraction': -math.expm1(-da*f),
            'clamped_supply_tissue': f,
            'distal_derivative_wrt_f': cb*(1-da*f)}

def integrate(da: float, f: float, n: int) -> dict[str, float]:
    require_finite(da, f)
    if type(n) is not int or n < 2 or n % 2:
        raise ValueError('Even mesh size >=2 required for Simpson integration')
    exact = exact_transport(da, f)
    a, h = da*f, 1/n
    c = 1.0
    concentrations = [c]
    for _ in range(n):
        k1 = -a*c
        k2 = -a*(c + h*k1/2)
        k3 = -a*(c + h*k2/2)
        k4 = -a*(c + h*k3)
        c += h*(k1+2*k2+2*k3+k4)/6
        concentrations.append(c)
    # Independent quadrature of local sink, rather than defining uptake as 1-c.
    weights = [1 if i in (0,n) else (4 if i%2 else 2) for i in range(n+1)]
    uptake_integral = a*h/3 * math.fsum(w*v for w,v in zip(weights, concentrations))
    return {'channel_out_numeric': c, 'distal_tissue_numeric': f*c,
            'channel_out_abs_error': abs(c-exact['channel_out']),
            'quadrature_extraction': uptake_integral,
            'mass_balance_abs_error': abs(1-c-uptake_integral)}

def saturation(p: float, p50: float, n: float) -> float:
    require_finite(p, p50, n)
    if p < 0 or p50 <= 0 or n <= 0:
        raise ValueError('Pressure >=0; P50 and Hill n >0 required')
    if p == 0:
        return 0.0
    z = n*(math.log(p)-math.log(p50))
    if z >= 0:
        return 1/(1+math.exp(-z))
    ez = math.exp(z)
    return ez/(1+ez)

def equilibrium_unloading(load: float, unload: float, p50: float, n: float) -> float:
    if unload >= load:
        raise ValueError('Unloading pressure must be below loading pressure')
    return saturation(load,p50,n)-saturation(unload,p50,n)

def kinetic_release_fraction(t_over_tau: float) -> float:
    require_finite(t_over_tau)
    if t_over_tau < 0:
        raise ValueError('Contact time / tau must be nonnegative')
    return -math.expm1(-t_over_tau)

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def run(output: Path) -> dict[str, Any]:
    start=time.perf_counter()
    cfg=json.loads((ROOT/'inputs/protocol.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for da in cfg['damkohler']:
        for f in cfg['wall_fraction']:
            base={'Da':da,'wall_fraction':f,**exact_transport(da,f)}
            for n in cfg['axial_mesh_sizes']:
                rows.append({**base,'axial_cells':n,**integrate(da,f,n)})
    write_csv(output/'S_transport.csv',rows)
    points=cfg['p50_grid']['points']
    lo,hi=cfg['p50_grid']['minimum'],cfg['p50_grid']['maximum']
    grid=[math.exp(math.log(lo)+(math.log(hi)-math.log(lo))*i/(points-1)) for i in range(points)]
    hrows=[]
    for load in cfg['equilibrium_load_pressure_mmHg']:
        for unload in cfg['equilibrium_unload_pressure_mmHg']:
            for n in cfg['hill_n']:
                best=max(grid,key=lambda p: equilibrium_unloading(load,unload,p,n))
                optimum=math.sqrt(load*unload)
                hrows.append({'loading_mmHg':load,'unloading_mmHg':unload,'Hill_n':n,
                    'grid_best_p50_mmHg':best,'exact_optimum_p50_mmHg':optimum,
                    'relative_optimum_error':abs(best/optimum-1),
                    'maximum_bound_fraction_unloaded':equilibrium_unloading(load,unload,optimum,n)})
    write_csv(output/'H_equilibrium.csv',hrows)
    krows=[]
    for t in cfg['contact_time_over_tau']:
        for m in cfg['inactive_carrier_fraction']:
            krows.append({'contact_time_over_tau':t,'inactive_fraction':m,
                'available_fraction_of_equilibrium_capacity':(1-m)*kinetic_release_fraction(t)})
    write_csv(output/'H_kinetic_controls.csv',krows)
    finest=[r for r in rows if r['axial_cells']==max(cfg['axial_mesh_sizes'])]
    mono=all(all(exact_transport(da,fs[i])['extraction_fraction']<=
                 exact_transport(da,fs[i+1])['extraction_fraction'] for i in range(len(fs)-1))
             for da in cfg['damkohler'] for fs in [cfg['wall_fraction']])
    pairs=[]
    for da in cfg['damkohler']:
        fs=cfg['wall_fraction']
        for i in range(len(fs)-1):
            x,y=exact_transport(da,fs[i]),exact_transport(da,fs[i+1])
            if y['distal_tissue']<x['distal_tissue']-1e-15:
                pairs.append({'Da':da,'lower_wall_fraction':fs[i],'upper_wall_fraction':fs[i+1],
                              'lower_distal':x['distal_tissue'],'upper_distal':y['distal_tissue']})
    bounds=cfg['checks']
    checks={
        'rk4_exact_solution':max(r['channel_out_abs_error'] for r in finest)<=bounds['RK4_max_absolute_error_N256'],
        'independent_quadrature_conservation':max(r['mass_balance_abs_error'] for r in finest)<=bounds['independent_Simpson_balance_error_N256'],
        'hill_optimum':max(r['relative_optimum_error'] for r in hrows)<=bounds['p50_grid_relative_error_to_exact_optimum'],
        'clamped_supply_monotone':all(exact_transport(4,f)['clamped_supply_tissue']==f for f in cfg['wall_fraction']),
        'total_extraction_monotone':mono,
        'no_transfer_no_uptake':all(exact_transport(da,0)['extraction_fraction']==0 for da in cfg['damkohler']),
        'kinetics_below_equilibrium':all(0<=r['available_fraction_of_equilibrium_capacity']<=1-r['inactive_fraction'] for r in krows),
        'finite_nonnegative_outputs':all(math.isfinite(r[key]) and r[key]>=0 for r in rows for key in ['channel_out','distal_tissue','extraction_fraction','channel_out_numeric'])
    }
    summary={'protocol_id':cfg['protocol_id'],'status':'executed',
        'S_parameter_cases':len(finest),'S_mesh_runs':len(rows),'H_equilibrium_cases':len(hrows),
        'H_kinetic_cases':len(krows),'checks':checks,'all_checks_pass':all(checks.values()),
        'RK4_max_error_N256':max(r['channel_out_abs_error'] for r in finest),
        'quadrature_max_balance_error_N256':max(r['mass_balance_abs_error'] for r in finest),
        'max_relative_Hill_optimum_error':max(r['relative_optimum_error'] for r in hrows),
        'distal_decreasing_adjacent_pairs':pairs,
        'counterexample':{'Da':4,'lower_transfer':{'wall_fraction':.25,**exact_transport(4,.25)},
                              'higher_transfer':{'wall_fraction':.9,**exact_transport(4,.9)}},
        'runtime':{'python':platform.python_version(),'platform':platform.platform(),'wall_seconds':time.perf_counter()-start},
        'inference':'Exact model diagnostics, no empirical uncertainty interval or claim of biological validation.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not summary['all_checks_pass']:
        raise RuntimeError('A predeclared check failed; outputs preserved for inspection')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'rerun')
    args=p.parse_args()
    print(json.dumps(run(args.output),indent=2))
