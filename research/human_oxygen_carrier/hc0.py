"""HC0: hypothetical equilibrium binding/unloading sensitivity, not a clinical model.

No doses, formulations, manufacture, patient inputs, or oxygen-delivery claims.
Uses the installed project environment only for plotting; all calculations use
the Python standard library. All writes stay beside this script.
"""
from pathlib import Path
import argparse, csv, hashlib, io, json, math, statistics, sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
CONFIG={
    'protocol':'HC0-v1',
    'question':'How do hypothetical affinity and relative binding-site capacity change the equilibrium content difference between fixed loading and unloading pressures?',
    'p50_grid_mmHg':list(range(5,101)),
    'hill_coefficients':[1.0,2.0,2.7,4.0],
    'loading_pressures_mmHg':[60.0,80.0,100.0],
    'unloading_pressures_mmHg':[10.0,20.0,40.0],
    'relative_capacity_units':[0.5,1.0,2.0],
    'plot_pair_mmHg':[100.0,20.0],
    'plot_hill_coefficient':2.7,
    'scope':'Hypothetical equilibrium model; no empirical product calibration, human efficacy, tissue viability, clinical dose or manufacturing guidance.',
    'parameter_provenance':{
        'equation':'Chosen Hill-form model S(P)=P^n/(P^n+P50^n); model assumption, not fit to a named carrier.',
        'P50_and_n':'Sensitivity grid selected by Coda; not measured NMU-HbV or patient parameters.',
        'pressures':'Illustrative fixed boundary conditions selected by Coda; not treatment targets or measured tissue pressures.',
        'capacity':'Dimensionless relative binding-site inventory; no conversion to concentration, mass, infusion volume or dose.',
        'human_trial_sources':'Motivate the research track only; supply none of the numerical HC0 parameters.'},
    'declared_checks':['S(P50)=0.5','S(0)=0','saturation bounds and monotonicity',
        'n=1 independent closed form','nonnegative and bounded content differences',
        'linear capacity scaling','finite-difference derivative at analytic optimum',
        'grid does not exceed analytic optimum','dimensionless pressure-scale invariance',
        'invalid parameter rejection'],
    'equilibrium_limits':['No transport times, kinetics, flow, viscosity or capillary geometry.',
        'No pH/CO2/temperature-dependent affinity, oxidation, methemoglobin, nitric oxide, or immune effects.',
        'No dissolved oxygen, carbon dioxide transport, coagulation or immune-cell function.',
        'Boundary pressures are imposed; no tissue-consumption or coupled circulation calculation.'],
}

def encoded(x): return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj): Path(path).write_bytes(encoded(obj))
def finite(x): return type(x) in (float,int) and math.isfinite(x)

def saturation(pressure,p50,n):
    if not all(finite(x) for x in (pressure,p50,n)) or pressure<0 or p50<=0 or n<=0:
        raise ValueError('Require finite pressure>=0, P50>0, n>0')
    if pressure==0: return 0.0
    z=n*(math.log(p50)-math.log(pressure))
    if z>=0:
        exp=math.exp(-z)
        return exp/(1+exp)
    return 1/(1+math.exp(z))

def unloading(p_load,p_unload,p50,n,capacity=1.):
    if not finite(capacity) or capacity<0 or p_unload>p_load:
        raise ValueError('Require nonnegative finite capacity and P_unload<=P_load')
    return capacity*(saturation(p_load,p50,n)-saturation(p_unload,p50,n))

def prepare():
    p=ROOT/'freeze.json'
    if p.exists(): raise SystemExit('Freeze exists; preserve it and use a new version for a changed model.')
    write(p,{'local_utc':datetime.now(timezone.utc).isoformat(),'independent_timestamp':False,
             'source_sha256':sha(__file__),'config':CONFIG,
             'status':'Local pre-execution specification; not externally witnessed preregistration.'})
    print('HC0 source/configuration frozen locally before execution.')

def calculate():
    checks=[]
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok: raise AssertionError(name)
    for n in CONFIG['hill_coefficients']:
        for p50 in CONFIG['p50_grid_mmHg']:
            check('half_saturation',saturation(p50,p50,n)==.5)
            check('zero_pressure',saturation(0,p50,n)==0)
            values=[saturation(p,p50,n) for p in [0,1,10,20,40,60,80,100,200]]
            check('bounded_monotone_saturation',all(0<=v<=1 for v in values) and values==sorted(values))
            check('pressure_scale_invariance',math.isclose(saturation(70,p50,n),saturation(700,p50*10,n),abs_tol=1e-14))
    for p in [0,1,7,30,100]:
        for p50 in [1,9,26,80]: check('n1_independent_closed_form',math.isclose(saturation(p,p50,1),p/(p+p50),abs_tol=1e-14))
    invalid=[(-1,20,2),(1,0,2),(1,20,0),(float('nan'),20,2),(1,float('inf'),2),(True,20,2)]
    for args in invalid:
        try: saturation(*args); rejected=False
        except ValueError: rejected=True
        check('reject_invalid_saturation_parameters',rejected)
    for args in [(10,20,20,2,1),(100,20,20,2,-1),(100,20,20,2,float('nan'))]:
        try: unloading(*args); rejected=False
        except ValueError: rejected=True
        check('reject_invalid_unloading_parameters',rejected)
    rows=[]; optima=[]
    for n in CONFIG['hill_coefficients']:
        for p_load in CONFIG['loading_pressures_mmHg']:
            for p_unload in CONFIG['unloading_pressures_mmHg']:
                optimum=math.sqrt(p_load*p_unload)
                delta_opt=unloading(p_load,p_unload,optimum,n)
                eps=optimum*1e-4
                deriv=(unloading(p_load,p_unload,optimum+eps,n)-unloading(p_load,p_unload,optimum-eps,n))/(2*eps)
                check('analytic_optimum_derivative',abs(deriv)<1e-8,{'n':n,'load':p_load,'unload':p_unload,'derivative':deriv})
                grid=[]
                for p50 in CONFIG['p50_grid_mmHg']:
                    loaded=saturation(p_load,p50,n); residual=saturation(p_unload,p50,n)
                    delta=loaded-residual
                    check('equilibrium_difference_bounds',0<=delta<=loaded<=1)
                    check('analytic_optimum_bounds_grid',delta<=delta_opt+1e-13)
                    check('capacity_linearity',math.isclose(unloading(p_load,p_unload,p50,n,2),2*delta,abs_tol=1e-14))
                    grid.append((delta,p50))
                    for cap in CONFIG['relative_capacity_units']:
                        rows.append({'load_pressure_mmHg':p_load,'unload_pressure_mmHg':p_unload,
                            'P50_mmHg':p50,'hill_n':n,'relative_capacity':cap,
                            'load_saturation':loaded,'unload_saturation':residual,
                            'delta_saturation':delta,'normalized_loaded_content':cap*loaded,
                            'normalized_equilibrium_content_difference':cap*delta,
                            'fraction_of_loaded_content_released':delta/loaded})
                best=max(grid)
                optima.append({'load_pressure_mmHg':p_load,'unload_pressure_mmHg':p_unload,'hill_n':n,
                    'analytic_P50_mmHg':optimum,'analytic_max_delta_saturation':delta_opt,
                    'grid_max_P50_mmHg':best[1],'grid_max_delta_saturation':best[0]})
    # Two independent asymptotic limits: neither near-zero nor enormous P50 wins.
    for n in CONFIG['hill_coefficients']:
        check('affinity_extremes_unload_little',unloading(100,20,1e-9,n)<1e-8 and unloading(100,20,1e12,n)<1e-8)
    return rows,optima,checks

def csv_data(rows):
    buf=io.StringIO(newline=''); w=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    return buf.getvalue().encode()

def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(13.6,6.2));fig.subplots_adjust(left=.075,right=.97,bottom=.22,top=.76,wspace=.28)
    colors=['#6f8792','#c27834','#197a8c','#715f9b']
    p_load,p_unload=CONFIG['plot_pair_mmHg']; optimum=math.sqrt(p_load*p_unload)
    for n,col in zip(CONFIG['hill_coefficients'],colors):
        selected=[r for r in rows if r['load_pressure_mmHg']==p_load and r['unload_pressure_mmHg']==p_unload and r['hill_n']==n and r['relative_capacity']==1]
        axes[0].plot([r['P50_mmHg'] for r in selected],[r['delta_saturation'] for r in selected],label=f'Hill n = {n:g}',color=col,lw=2.2)
    axes[0].axvline(optimum,color='#64747e',ls='--',lw=1.3)
    axes[0].text(optimum+2,.94,f'Analytic maximum\nP50 = {optimum:.2f} mmHg',transform=axes[0].get_xaxis_transform(),va='top',fontsize=10)
    axes[0].set(xlabel='Hypothetical P50 (mmHg)',ylabel='Equilibrium saturation difference',ylim=(0,.98),xlim=(5,100),title='A   Affinity alone does not maximize release')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(frameon=False,loc='lower right',fontsize=10)
    for cap,col in zip(CONFIG['relative_capacity_units'],['#6f8792','#197a8c','#c27834']):
        selected=[r for r in rows if r['load_pressure_mmHg']==p_load and r['unload_pressure_mmHg']==p_unload and r['hill_n']==CONFIG['plot_hill_coefficient'] and r['relative_capacity']==cap]
        axes[1].plot([r['P50_mmHg'] for r in selected],[r['normalized_equilibrium_content_difference'] for r in selected],label=f'Relative capacity {cap:g}',color=col,lw=2.2)
    axes[1].set(xlabel='Hypothetical P50 (mmHg)',ylabel='Normalized equilibrium content difference',xlim=(5,100),title='B   More binding sites scale capacity in this model')
    axes[1].legend(frameon=False,loc='lower right',fontsize=10)
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('HC0  |  Hypothetical oxygen binding and unloading',x=.075,ha='left',y=.96,fontsize=19,weight='bold')
    fig.text(.075,.86,f'Illustrative fixed pressures: loading {p_load:g} mmHg, unloading {p_unload:g} mmHg.  Panel B uses hypothetical n = {CONFIG["plot_hill_coefficient"]:g}.',fontsize=11,color='#4f616d')
    fig.text(.075,.075,'Equilibrium sensitivity only: not measured carrier performance, tissue delivery, a product ranking, or clinical guidance.\nAll parameter values are hypothetical; relative capacity has no conversion to a concentration or dose.',fontsize=10.5,color='#4f616d',linespacing=1.5)
    fig.savefig(ROOT/'HC0_binding_unloading.png',dpi=200)
    fig.savefig(ROOT/'HC0_binding_unloading.pdf')
    plt.close(fig)

def load_frozen():
    frozen=json.loads((ROOT/'freeze.json').read_text())
    if frozen['source_sha256']!=sha(__file__) or frozen['config']!=CONFIG: raise RuntimeError('Frozen code/configuration mismatch')
    return frozen

def manifest():
    files=[p for p in ROOT.iterdir() if p.is_file() and p.name!='manifest-sha256.txt']
    (ROOT/'manifest-sha256.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(files)),encoding='utf-8')

def run():
    frozen=load_frozen()
    if (ROOT/'results.json').exists():raise SystemExit('Results exist; use verify, not an in-place replacement.')
    rows,optima,checks=calculate()
    (ROOT/'sensitivity.csv').write_bytes(csv_data(rows));write(ROOT/'optima.json',optima)
    write(ROOT/'checks.json',checks)
    p_load,p_unload=CONFIG['plot_pair_mmHg'];n=CONFIG['plot_hill_coefficient'];p50=math.sqrt(p_load*p_unload)
    results={'protocol':CONFIG['protocol'],'status':'executed theoretical sensitivity calculation',
        'rows':len(rows),'unique_pressure_affinity_cooperativity_cases':len(rows)//len(CONFIG['relative_capacity_units']),
        'analytic_optimum_cases':len(optima),'checks_passed':sum(c['passed'] for c in checks),'checks_total':len(checks),
        'illustrative_case':{'load_pressure_mmHg':p_load,'unload_pressure_mmHg':p_unload,'hill_n':n,
            'analytic_optimum_P50_mmHg':p50,'max_delta_saturation':unloading(p_load,p_unload,p50,n),
            'capacity_0_5_difference':unloading(p_load,p_unload,p50,n,.5),
            'capacity_1_difference':unloading(p_load,p_unload,p50,n,1),
            'capacity_2_difference':unloading(p_load,p_unload,p50,n,2)},
        'interpretation':'For fixed pressures and one unchanged Hill curve, equilibrium unloading has an interior affinity optimum; relative capacity scales the content difference linearly by assumption.',
        'not_established':['Clinical safety or benefit','NMU-HbV binding parameters','Tissue oxygen-delivery rate','Perfused tissue viability','Superiority of any product'],
        'source_sha256':frozen['source_sha256'],'csv_sha256':hashlib.sha256(csv_data(rows)).hexdigest()}
    write(ROOT/'results.json',results);plot(rows);manifest();print(json.dumps(results,indent=2))

def verify():
    load_frozen();rows,optima,checks=calculate();saved=json.loads((ROOT/'results.json').read_text())
    assert hashlib.sha256(csv_data(rows)).hexdigest()==saved['csv_sha256']==sha(ROOT/'sensitivity.csv')
    assert optima==json.loads((ROOT/'optima.json').read_text())
    assert checks==json.loads((ROOT/'checks.json').read_text())
    receipt={'status':'passed','rows_recomputed':len(rows),'checks_recomputed':len(checks),
        'exact_csv_and_json_recomputation':True,'independent_replication':False}
    write(ROOT/'verification.json',receipt);manifest();print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','verify','manifest']);args=p.parse_args()
    {'prepare':prepare,'run':run,'verify':verify,'manifest':manifest}[args.command]()
