"""Independent saved-result audit. Never imports/calls the transport adapter.
Uses Decimal arithmetic for balances and the independently eliminated BE step.
No optimization, ODE/PDE/transport execution or new parameter search.
"""
from pathlib import Path
from decimal import Decimal, getcontext
import hashlib, json, math

getcontext().prec=60
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/'linear_adapter'
D=lambda x: Decimal(str(x))
read=lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name,ok,details=None):
    checks.append({'name':name,'passed':bool(ok),'details':details})
def close(a,b,scale,tol='2e-9'):
    return abs(D(a)-D(b)) <= D(tol)*D(scale)

def main():
    destination=HERE/'linear_saved_result_audit.json'
    if destination.exists():raise RuntimeError('Preserve previous audit; no implicit overwrite')
    freeze=read(ROOT/'freeze.json'); plan=read(ROOT/'cases.json')
    cfg0=read(ROOT/'pinned_sources/ab_ct0_config.json')
    ledger=read(ROOT/'run/ledger.json'); summary=read(ROOT/'run/summary.json')
    check('frozen_inputs',all(sha(ROOT/r['path'])==r['sha256'] for r in freeze['files']))
    check('all_frozen_attempts_once',len(ledger['attempts'])==51 and
          [r['attempt_id'] for r in ledger['attempts']]==[s['attempt_id'] for s in plan['cases']])
    check('precall_records_and_result_hashes',all(r['started_utc']<=r['finished_utc'] and
          sha(ROOT/'run'/r['result_path'])==r['result_sha256'] for r in ledger['attempts']))
    worst={'step_total':D(0),'step_bound':D(0),'BE_path':D(0),'radial_balance':D(0),'global_content':D(0)}
    count_stations=0; count_radial_cells=0; mutations=[]
    for spec in plan['cases']:
        ident=spec['attempt_id']; result=read(ROOT/'run/attempts'/f'{ident}.json')
        assessment=read(ROOT/'run/attempts'/f'{ident}_assessment.json')
        if spec['block']=='fault':
            if 'failure' in result:
                detected=result['failure']['type']=='ArithmeticError' and result['failure']['message'] in (
                    'Saturation bound failed; no clipping applied','Physical axial bracket failed',
                    'Segment conservation failed','Global conservation failed')
                check(ident+':specific_guard',detected,result['failure']['message'])
                mutations.append({'id':ident,'outcome':result['failure']['message']})
            else:
                # Independently reject on a concentration path compared with eliminated BE.
                c=D(spec['cin']); b=D(spec['gamma'])*c
                dt=D(spec['expected_T'])/D(spec['nz']); k=D(spec['k']); g=D(spec['gamma']); alpha=D(spec['alpha'])
                errors=[]
                for row in result['stations']:
                    theta=k*dt/(1+k*dt)
                    c=(c+theta*b)/(1+alpha*dt+theta*g)
                    b=(b+k*dt*g*c)/(1+k*dt)
                    errors.append(max(abs(D(row['c_lumen'])-c)/D(spec['cin']),abs(D(row['bound_content'])-b)/max(D(spec['cin']),g*D(spec['cin']))))
                check(ident+':wrong_model_discriminated',max(errors)>D('2e-9'),float(max(errors)))
                mutations.append({'id':ident,'outcome':'independent BE mismatch','max_scaled':float(max(errors))})
            continue
        cfg={**cfg0,**{k:spec[k] for k in ('w','gap','L','cin')}}
        w,h,L,ci,mu0,Qref=[D(cfg[k]) for k in ('w','gap','L','cin','mu0','Qref')]
        mu=D(spec['mu']); r0=12*mu0*L/(w*h**3); resistance=r0*mu
        dpmax=r0*D('3e-9')/60; powermax=r0*Qref**2
        q=(min(dpmax/resistance,(powermax/resistance).sqrt()) if spec['flow_mode']=='envelope'
           else D(spec['Q_uL_min'])*D('1e-9')/60)
        transit=w*h*L/q; ss=result['summary']; rows=result['stations']; count_stations+=len(rows)
        check(ident+':hydraulics',all(close(ss[k],v,max(abs(v),D('1e-40')),'1e-12') for k,v in
              [('Q',q),('residence_s',transit),('power_W',resistance*q*q),('deltaP_Pa',resistance*q),('power_max_W',powermax),('deltaP_max_Pa',dpmax)]))
        calls=result['verification_adapter']['calls']
        check(ident+':actual_code_calls',all(calls[k]>0 for k in ('solve','validate','content','hydraulics')))
        real=spec['block'] in ('radial','coupled')
        check(ident+':field_scope',(calls['slab']>0 if real else calls['slab']==0) and
              ('actual linear radial solve' if real else 'not a tissue field') in result['verification_adapter']['tissue_field_interpretation'])
        if real:
            dy=D(cfg['d'])/D(spec['ny']); diffusivity=D(cfg['D']); p=D(spec['P']); kt=D(spec['kt'])
            wall=1/(1/p+dy/(2*diffusivity)); interior=diffusivity/dy
            maxres=D(0)
            for row in rows:
                tissue=list(map(D,row['tissue'])); bulk=D(row['c_lumen'])
                for i,ct in enumerate(tissue):
                    count_radial_cells+=1
                    left=(wall*(bulk-ct) if i==0 else interior*(tissue[i-1]-ct))
                    right=(D(0) if i==len(tissue)-1 else interior*(tissue[i+1]-ct))
                    res=abs(left+right-kt*ct*dy)/max(p*ci,diffusivity*ci/D(cfg['d']),D('1e-30'))
                    maxres=max(maxres,res)
                check(ident+':wall_and_reaction_'+str(row['z']),close(row['J'],wall*(bulk-tissue[0]),p*ci,'2e-9') and
                      close(row['reaction_integral'],sum(tissue)*kt*dy,p*ci,'2e-9'))
            worst['radial_balance']=max(worst['radial_balance'],maxres)
            check(ident+':independent_radial_FV_residual',maxres<=D('2e-9'),float(maxres))
        if spec['block']=='radial':continue
        alpha=(D(spec['alpha']) if spec['block']=='imposed' else
               D(read(ROOT/'run/attempts'/f"{spec['radial_dependency']}.json")['stations'][0]['J'])/ci/h)
        gamma=D(spec['gamma']); k=D(spec['k'] or 0); dt=transit/D(spec['nz'])
        c=oldc=ci; b=oldb=gamma*ci; sum_flux=D(0); bound_scale=max(ci,gamma*ci)
        maxstep=maxbound=maxpath=D(0)
        for row in rows:
            observed_c=D(row['c_lumen']); observed_b=D(row['bound_content'])
            maxstep=max(maxstep,abs(observed_c+observed_b+dt*D(row['J'])/h-oldc-oldb)/ci)
            if spec['profile']=='H_eq':
                c=c/(1+alpha*dt/(1+gamma)); b=gamma*c
                maxbound=max(maxbound,abs(observed_b-gamma*observed_c)/bound_scale)
            else:
                theta=k*dt/(1+k*dt)
                c=(c+theta*b)/(1+alpha*dt+theta*gamma)
                b=(b+k*dt*gamma*c)/(1+k*dt)
                maxbound=max(maxbound,abs(observed_b-(oldb+k*dt*gamma*observed_c)/(1+k*dt))/bound_scale)
            maxpath=max(maxpath,abs(observed_c-c)/ci,abs(observed_b-b)/bound_scale)
            oldc,oldb=observed_c,observed_b
            sum_flux+=dt*D(row['J'])/h
        maxglobal=max(abs(D(ss['uptake_mol_s'])/q-sum_flux),abs((1+gamma)*ci-oldc-oldb-sum_flux))/((1+gamma)*ci)
        for key,value in [('step_total',maxstep),('step_bound',maxbound),('BE_path',maxpath),('global_content',maxglobal)]:worst[key]=max(worst[key],value)
        check(ident+':independent_decimal_balances_and_path',max(maxstep,maxbound,maxpath,maxglobal)<=D('2e-9'),
              {'step':float(maxstep),'bound':float(maxbound),'path':float(maxpath),'global':float(maxglobal)})
    report={'scope':'Independent saved-result arithmetic audit; zero transport/fit calls',
      'auditor':'Coda coordinator, separate implementation from adapter author',
      'freeze_sha256':sha(ROOT/'freeze.json'),'source_sha256':sha(Path(__file__)),
      'checks':checks,'passed':sum(x['passed'] for x in checks),'total':len(checks),
      'stations_audited':count_stations,'real_radial_cells_audited':count_radial_cells,
      'worst_scaled_residuals':{k:float(v) for k,v in worst.items()},'mutations':mutations}
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))
    if report['passed']!=report['total']:raise SystemExit(1)
if __name__=='__main__':main()
