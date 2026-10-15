"""OK0: clamped-bath, finite-contact carrier toy model; no empirical physiology."""
from pathlib import Path
import csv,hashlib,json,math
ROOT=Path(__file__).resolve().parent

def saturation(p,p50,n):
    if not all(math.isfinite(x) for x in (p,p50,n)) or p<0 or p50<=0 or n<=0:raise ValueError('Invalid pressure/Hill input')
    if p==0:return 0.0
    z=n*(math.log(p50)-math.log(p))
    if z>=0:
        e=math.exp(-z);return e/(1+e)
    return 1/(1+math.exp(z))

def cycle(pl,pu,p50,n,kl,ku,tl,tu,b):
    if not all(math.isfinite(x) and x>=0 for x in (kl,ku,tl,tu,b)) or pl<pu:raise ValueError('Invalid rate, time, capacity or boundary order')
    sl,su=saturation(pl,p50,n),saturation(pu,p50,n);delta=sl-su
    a,z=kl*tl,ku*tu;period=tl+tu
    if a+z==0:
        return dict(sl_eq=sl,su_eq=su,unique_css=False,exit_l=None,exit_u=None,delta_eq=delta,kinetic_factor=0.,delta_cycle=0.,q_per_volume=0.,rate_per_volume=0. if period>0 else None,efficiency=0. if delta>0 else None)
    # expm1 avoids cancellation at arbitrarily slow positive relaxation.
    al,au=-math.expm1(-a),-math.expm1(-z);den=-math.expm1(-(a+z))
    el,eu=math.exp(-a),math.exp(-z)
    exit_u=(au*su+eu*al*sl)/den;exit_l=(al*sl+el*au*su)/den
    factor=al*au/den;change=factor*delta;q=b*change
    return dict(sl_eq=sl,su_eq=su,unique_css=True,exit_l=exit_l,exit_u=exit_u,delta_eq=delta,kinetic_factor=factor,delta_cycle=change,q_per_volume=q,rate_per_volume=q/period,efficiency=factor if delta>0 else None)

def rk4_phase(s,target,k,t,steps):
    h=t/steps
    for _ in range(steps):
        f=lambda y:k*(target-y)
        a=f(s);b=f(s+h*a/2);c=f(s+h*b/2);d=f(s+h*c)
        s+=h*(a+2*b+2*c+d)/6
    return s

def numeric_css(case,initial):
    pl,pu,p50,n,kl,ku,tl,tu,b=case
    sl,su=saturation(pl,p50,n),saturation(pu,p50,n)
    count=math.ceil(-math.log(1e-13)/(kl*tl+ku*tu))+5
    nl=max(20,math.ceil(kl*tl/.02));nu=max(20,math.ceil(ku*tu/.02));s=initial
    for _ in range(count):
        start=s;l=rk4_phase(s,sl,kl,tl,nl);s=rk4_phase(l,su,ku,tu,nu)
    return {'exit_l':l,'exit_u':s,'net_loading':l-start,'net_unloading':l-s,'cycles':count,'steps_per_loading':nl,'steps_per_unloading':nu}

def bounded_max(fun,lo,hi):
    # Numerical maximizer on this declared interval, not a global theorem.
    for _ in range(100):
        a=lo+(hi-lo)/3;b=hi-(hi-lo)/3
        if fun(a)<fun(b):lo=a
        else:hi=b
    p=(lo+hi)/2;return {'p50':p,'q_per_volume':fun(p)}

def write_csv(name,rows):
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    frozen=json.loads((ROOT/'freeze.json').read_text());assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==frozen['corrected_script_sha256']
    c=frozen['parameters'];pl,pu,n,b,tl,tu,kl,ku=[c[k] for k in ('pl','pu','n','b','tl','tu','kl','ku')]
    ref=math.sqrt(pl*pu);rows=[]
    for name in ('constant_relaxation','hypothetical_p50_dependent_unloading'):
        for p50 in frozen['p50_grid']:
            rate=ku if name=='constant_relaxation' else ku*p50/ref
            v=cycle(pl,pu,p50,n,kl,rate,tl,tu,b)
            rows.append(dict(case=name,p50=p50,kl=kl,ku=rate,**v))
    constant=lambda p:cycle(pl,pu,p,n,kl,ku,tl,tu,b)['q_per_volume']
    dependent=lambda p:cycle(pl,pu,p,n,kl,ku*p/ref,tl,tu,b)['q_per_volume']
    optima={'equilibrium_analytic':ref,'constant_bounded':bounded_max(constant,5,80),'dependent_bounded':bounded_max(dependent,5,80)}
    checks=[]
    def check(name,condition,details=None):
        assert condition,name;checks.append({'name':name,'passed':True,'details':details})
    base=cycle(pl,pu,ref,n,kl,ku,tl,tu,b)
    check('no capacity',cycle(pl,pu,ref,n,kl,ku,tl,tu,0)['q_per_volume']==0)
    ng=cycle(30,30,ref,n,kl,ku,tl,tu,b)
    check('no gradient and undefined normalized efficiency',ng['q_per_volume']==0 and ng['efficiency'] is None)
    check('zero loading or unloading contact',all(cycle(pl,pu,ref,n,kl,ku,x,y,b)['q_per_volume']==0 for x,y in [(0,tu),(tl,0)]))
    deg=cycle(pl,pu,ref,n,0,0,tl,tu,b)
    check('both inactive: no unique CSS',not deg['unique_css'] and deg['exit_l'] is None and deg['exit_u'] is None)
    check('zero cycle period has undefined rate',cycle(pl,pu,ref,n,kl,ku,0,0,b)['rate_per_volume'] is None)
    check('fast relaxation equilibrium limit',cycle(pl,pu,ref,n,100,100,10,10,b)['kinetic_factor']==1)
    check('symmetric tanh identity',abs(base['kinetic_factor']-math.tanh(kl*tl/2))<1e-14)
    check('constant-rate optimum preserved',abs(optima['constant_bounded']['p50']-ref)<2e-6)
    check('hypothetical dependent-rate optimum shifts',optima['dependent_bounded']['p50']>ref)
    tiny=cycle(pl,pu,ref,n,1,1,1e-18,1e-18,b)
    check('tiny contact stable nonzero and finite fast-cycling rate',tiny['delta_cycle']>0 and math.isclose(tiny['rate_per_volume'],b*tiny['delta_eq']/4,rel_tol=1e-14),tiny)
    check('pressure-unit rescaling invariance',math.isclose(cycle(pl*7,pu*7,ref*7,n,kl,ku,tl,tu,b)['q_per_volume'],base['q_per_volume'],rel_tol=1e-14))
    ms=cycle(pl,pu,ref,n,kl/1000,ku/1000,tl*1000,tu*1000,b)
    check('seconds-to-milliseconds dimensional conversion',math.isclose(ms['q_per_volume'],base['q_per_volume'],rel_tol=1e-14) and math.isclose(ms['rate_per_volume']*1000,base['rate_per_volume'],rel_tol=1e-14))
    check('capacity linear scaling',math.isclose(cycle(pl,pu,ref,n,kl,ku,tl,tu,2*b)['q_per_volume'],2*base['q_per_volume'],rel_tol=1e-14))
    for bad in [(-1,1,1,1,1),(1,float('nan'),1,1,1),(1,1,-1,1,1),(1,1,1,1,-1)]:
        rejected=False
        try:cycle(pl,pu,ref,n,*bad)
        except ValueError:rejected=True
        check('reject invalid '+str(bad),rejected)
    numerical=[]
    for case in frozen['ode_cases']:
        exact=cycle(*case)
        for initial in (0.,1.):
            calc=numeric_css(case,initial);err=max(abs(calc['exit_l']-exact['exit_l']),abs(calc['exit_u']-exact['exit_u']))
            balance=abs(calc['net_loading']-calc['net_unloading'])
            numerical.append({'parameters':case,'initial':initial,'max_endpoint_error':err,'mass_balance_error':balance,**calc})
            check('RK4 CSS and cycle balance '+str(len(numerical)),err<1e-8 and balance<1e-11,{'endpoint_error':err,'mass_balance_error':balance})
    counter=[]
    for name,kon,koff in [('reference',.1,2.),('higher_affinity_faster_association',.2,2.),('same_affinity_faster_both',1.,20.)]:
        p50=koff/kon;cl,cu=kon*pl+koff,kon*pu+koff
        v=cycle(pl,pu,p50,1,cl,cu,.1,.1,b)
        counter.append(dict(case=name,kon_per_pressure_per_second=kon,koff_per_second=koff,p50=p50,kl_per_second=cl,ku_per_second=cu,**v))
    check('association counterexample',counter[1]['p50']<counter[0]['p50'] and counter[1]['koff_per_second']==counter[0]['koff_per_second'] and counter[1]['ku_per_second']>counter[0]['ku_per_second'])
    check('same affinity does not determine kinetic throughput',counter[2]['p50']==counter[0]['p50'] and counter[2]['q_per_volume']>counter[0]['q_per_volume'])
    check('sweep endpoints bounded and cycles balanced',all(0<=r['exit_u']<=r['exit_l']<=1 and 0<=r['kinetic_factor']<=1 for r in rows))
    result={'scope':'Hypothetical clamped-bath relaxation toy, not measured hemoglobin kinetics','parameters':c,'optima':optima,'baseline_at_equilibrium_optimum':base,'sweep_rows':len(rows),'checks_passed':len(checks),'max_RK4_endpoint_error':max(v['max_endpoint_error'] for v in numerical),'max_cycle_balance_error':max(v['mass_balance_error'] for v in numerical),'association_counterexamples':counter}
    write_csv('sweep.csv',rows);write_csv('association_counterexamples.csv',counter)
    for name,data in [('results.json',result),('checks.json',checks),('ode_checks.json',numerical)]: (ROOT/name).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
