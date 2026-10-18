"""AB-LA1 verification closures around the actual pinned AB-CT0 solve/content.

Import defines functions only. Production functions are not rewritten. Call
trace counts original code objects, not similarly named adapter functions.
"""
import hashlib, importlib.util, json, math, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def context(spec):
    cfg=json.loads((HERE/'pinned_sources/ab_ct0_config.json').read_text())
    cfg.update({k:spec[k] for k in ('w','gap','L','cin')})
    cfg['B']=spec['gamma']*cfg['cin']
    case=dict(case_id=spec['attempt_id'],profile=spec['profile'],mu=spec['mu'],
      flow_mode=spec['flow_mode'],k=spec['k'],ny=spec['ny'],nz=spec['nz'],
      clamped=spec['block']=='radial',P=spec.get('P',5e-6),Rmax=.001,
      reaction='linear',kt=spec.get('kt',spec['alpha']),beta=1+spec['gamma'])
    if case['flow_mode']=='fixed_flow':case['Q']=spec['Q_uL_min']*1e-9/60
    return case,cfg
def execute(spec,heartbeat):
    m=load_file('_abct0_'+spec['attempt_id'],HERE/'pinned_sources/ab_ct0_model.py')
    case,cfg=context(spec)
    original={n:getattr(m,n) for n in ('solve','validate','hydraulics','content','slab')}
    code_names={f.__code__:n for n,f in original.items()};counts={n:0 for n in original}
    overrides=[];last_content={'total':None}
    if case['profile'].startswith('H'):
        def linear_seq(c,config):
            if not math.isfinite(c) or not 0<=c<=config['cin']*(1+config['domain_relative_tol']):
                raise ValueError('Linear verification seq outside declared c/cin domain')
            return c/config['cin']
        m.seq=linear_seq;overrides.append('seq: linear c/cin with B=gamma*cin')
    fault=spec.get('fault')
    if fault in ('reverse_release','spatial_k','total_sink'):
        def fault_content(c,ca,co,old_s=None,a=None):
            aa=a
            if a is not None and old_s is not None:
                if fault=='reverse_release':aa=-a
                elif fault=='spatial_k':aa=a*(spec['expected_Q_uL_min']*1e-9/60)/(co['w']*co['gap'])
            ans=original['content'](c,ca,co,old_s,aa)
            last_content['total']=ans[0]
            return ans
        m.content=fault_content;overrides.append('DELIBERATE WRONG content argument/recording: '+fault)
    if spec['block'] in ('imposed','fault'):
        G=spec['alpha']*cfg['gap']
        def imposed(c,ca,co,hb,counters):
            counters['slab_calls']+=1
            drive=last_content['total'] if fault=='total_sink' else c
            if drive is None:raise RuntimeError('Missing total-content mutation state')
            J=G*drive*(2 if fault=='double_perimeter' else 1)
            return dict(c=[c]*ca['ny'],J=J,reaction_integral=J,normalized_residual=0.,wall_surface=None)
        law='2*G*c (deliberate perimeter error)' if fault=='double_perimeter' else ('G*total_content (deliberate free/total error)' if fault=='total_sink' else 'G*c')
        m.slab=imposed;overrides.append('slab: IMPOSED J='+law+'; c-array is API placeholder, NOT tissue')
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in code_names:counts[code_names[frame.f_code]]+=1
    previous=sys.getprofile();sys.setprofile(profile)
    try:
        result=original['solve'](case,cfg,heartbeat)
    except BaseException as exc:
        exc.adapter_trace=dict(calls=counts,overrides=overrides)
        raise
    finally:sys.setprofile(previous)
    result['verification_adapter']=dict(scope='Linear verification only; nonlinear original unmodified',
      production_source_sha256=hashlib.sha256((HERE/'pinned_sources/ab_ct0_model.py').read_bytes()).hexdigest(),
      calls=counts,overrides=overrides,case_input=spec,
      tissue_field_interpretation='actual linear radial solve' if spec['block'] in ('radial','coupled') else 'imposed-closure placeholder; not a tissue field')
    return result

def continuum_radial(spec,cfg):
    lam=math.sqrt(spec['kt']/cfg['D']);K=math.sqrt(cfg['D']*spec['kt'])*math.tanh(lam*cfg['d'])
    G=1/(1/spec['P']+1/K)
    surface=cfg['cin']/(1+K/spec['P'])
    return G,lambda y:surface*math.cosh(lam*(cfg['d']-y))/math.cosh(lam*cfg['d'])

def discrete_reference(alpha,k,gamma,T,n,c0,equilibrium=False):
    dt=T/n;c=c0;b=gamma*c0;rows=[];sink=[]
    for _ in range(n):
        if equilibrium:
            c=c/(1+dt*alpha/(1+gamma));b=gamma*c
        else:
            theta=k*dt/(1+k*dt)
            c=(c+theta*b)/(1+dt*alpha+theta*gamma)
            b=b/(1+k*dt)+theta*gamma*c
        sink.append(dt*alpha*c);rows.append((c,b))
    return rows,math.fsum(sink)

def assess(spec,result,tol,dependencies):
    case,cfg=context(spec);summary=result['summary'];checks=[]
    def check(name,ok,**details):checks.append(dict(name=name,passed=bool(ok),**details))
    trace=result['verification_adapter']['calls']
    check('actual_production_calls',all(trace[x]>=1 for x in ('solve','validate','content','hydraulics')))
    check('actual_radial_calls' if spec['block'] in ('radial','coupled') else 'radial_closure_explicit',
          trace['slab']>=1 if spec['block'] in ('radial','coupled') else trace['slab']==0)
    check('flow_and_residence',abs(summary['Q_uL_min']/spec['expected_Q_uL_min']-1)<=tol['hydraulic_relative'] and abs(summary['residence_s']/spec['expected_T']-1)<=tol['hydraulic_relative'])
    check('envelope_flags',bool(summary['pressure_violation'] or summary['power_violation'])==spec['expected_envelope_violation'])
    cin=cfg['cin'];gamma=spec['gamma'];scale_b=max(cin,gamma*cin);total=(1+gamma)*cin
    if spec['block']=='radial':
        G,field=continuum_radial(spec,cfg)
        Gn=result['stations'][0]['J']/cin
        field_error=max(abs(c-field(y)) for c,y in zip(result['stations'][0]['tissue'],result['y_cell_centers']))/cin
        return dict(checks=checks,passed=all(x['passed'] for x in checks),metrics=dict(G_continuum=G,G_discrete=Gn,G_relative_error=abs(Gn/G-1),field_scaled_error=field_error))
    alpha=spec['alpha']
    if spec['block']=='coupled':alpha=dependencies[spec['radial_dependency']]['metrics']['G_discrete']/cfg['gap']
    T=spec['expected_T'];n=spec['nz'];equilibrium=spec['profile']=='H_eq';k=0. if spec['profile']=='D' else spec['k']
    lily=load_file('_lily_reference',HERE/'pinned_sources/lily_benchmark.py')
    refrows,U=discrete_reference(alpha,k,gamma,T,n,cin,equilibrium)
    worst=max(max(abs(row['c_lumen']-c)/cin,abs(row['bound_content']-b)/scale_b) for row,(c,b) in zip(result['stations'],refrows))
    uptake_scaled=abs(summary['uptake_mol_s']/summary['Q']-U)/total
    check('discrete_BE_path',worst<=tol['discrete_scaled'],max_scaled=worst)
    check('discrete_BE_uptake',uptake_scaled<=tol['discrete_scaled'],scaled=uptake_scaled)
    if not equilibrium:
        be=lily.backward_euler(alpha,k,gamma,T,n,cin)
        beerr=max(abs(be['c']-refrows[-1][0])/cin,abs(be['b']-refrows[-1][1])/scale_b,abs(be['uptake']-U)/total)
        check('independent_Lily_BE_endpoint',beerr<=tol['lily_be_scaled'],max_scaled=beerr)
    endpoint=lily.equilibrium_state(alpha,gamma,T,cin) if equilibrium else lily.exact_state(alpha,k,gamma,T,cin)
    exact_error=max(abs(summary['outlet_free']-endpoint[0])/cin,abs(summary['outlet_bound']-endpoint[1])/scale_b)
    if n==128:check('finest_continuum_endpoint',exact_error<=tol['continuum_finest_scaled'],max_scaled=exact_error)
    old_c,old_b=cin,gamma*cin;dt=T/n;residual=0.;bound_residual=0.;negative=False;coordinates=0.
    for j,row in enumerate(result['stations'],1):
        c,b=row['c_lumen'],row['bound_content']
        residual=max(residual,abs(c+b+dt*alpha*c-old_c-old_b)/cin)
        if not equilibrium:
            expected_b=(old_b+dt*k*gamma*c)/(1+dt*k)
            bound_residual=max(bound_residual,abs(b-expected_b)/scale_b)
        coordinates=max(coordinates,abs(row['z']-cfg['L']*j/n)/cfg['L'])
        negative |= min(c,b)<0
        old_c,old_b=c,b
    check('separate_total_and_bound_updates',max(residual,bound_residual)<=tol['discrete_scaled'],total_scaled=residual,bound_scaled=bound_residual)
    check('nonnegative_unclipped_states',not negative)
    check('endpoint_coordinates',coordinates<=1e-14,max_relative=coordinates)
    if spec['block']=='coupled':
        clamp=dependencies[spec['radial_dependency']]['result']['stations'][0]['tissue']
        homogeneity=max(abs(c-base*row['c_lumen']/cin)/cin for row in result['stations'] for c,base in zip(row['tissue'],clamp))
        check('real_radial_linear_scaling',homogeneity<=tol['real_field_scaling'],max_scaled=homogeneity)
    return dict(checks=checks,passed=all(x['passed'] for x in checks),metrics=dict(alpha_reference=alpha,endpoint_exact=endpoint,continuum_endpoint_scaled_error=exact_error,discrete_path_scaled_error=worst,discrete_uptake_scaled_error=uptake_scaled))

def convergence(specs,results,tol):
    checks=[]
    for group in specs['convergence_groups']:
        members=sorted((s for s in specs['cases'] if s['id']==group),key=lambda s:s['nz'])
        errors=[results[s['attempt_id']]['metrics']['continuum_endpoint_scaled_error'] for s in members]
        floor=tol['error_floor'];order=math.log(errors[-2]/errors[-1],2) if min(errors[-2:])>floor else None
        passed=all(y<=x or x<=floor for x,y in zip(errors,errors[1:])) and (order is None or tol['axial_order_min']<=order<=tol['axial_order_max'])
        checks.append(dict(name=group+':axial_convergence',passed=passed,errors=errors,last_order=order))
    for group in ('RAD_low','RAD_high'):
        members=sorted((s for s in specs['cases'] if s['id']==group),key=lambda s:s['ny'])
        for key in ('G_relative_error','field_scaled_error'):
            errors=[results[s['attempt_id']]['metrics'][key] for s in members]
            floor=tol['error_floor'];order=math.log(errors[-2]/errors[-1],2) if min(errors[-2:])>floor else None
            passed=errors[-1]<=tol['radial_finest_scaled'] and all(y<=x or x<=floor for x,y in zip(errors,errors[1:])) and (order is None or tol['radial_order_min']<=order<=tol['radial_order_max'])
            checks.append(dict(name=group+':'+key,passed=passed,errors=errors,last_order=order))
    return dict(checks=checks,passed=all(x['passed'] for x in checks))
