"""Execute frozen AB-LFR1 fixtures. Verification dependency: mpmath 1.3.0.

The independent reference uses a 4x4 high-precision matrix exponential, not
benchmark.py's scalar spectral implementation. Added rows integrate sink and
net release directly. Every attempted run and failed assertion is retained.
"""
from __future__ import annotations
import argparse, csv, datetime, hashlib, json, math, platform, sys, time, traceback
from pathlib import Path
import mpmath as mp
from benchmark import exact_state, propagator, equilibrium_state, backward_euler, geometry_to_rates

ROOT=Path(__file__).resolve().parent

def write_json(p, obj):
    p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def run() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=None)
    args=parser.parse_args()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=args.output or ROOT/'runs'/stamp
    out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((ROOT/'FROZEN_CASES.json').read_text())
    freeze=json.loads((ROOT/'FREEZE.json').read_text())
    sha=hashlib.sha256((ROOT/'FROZEN_CASES.json').read_bytes()).hexdigest()
    if sha!=freeze['cases_sha256']:
        raise RuntimeError('Frozen input hash mismatch')
    start=time.perf_counter()
    source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['benchmark.py','run_benchmark.py','FROZEN_CASES.json']}
    write_json(out/'STARTED.json',dict(utc=stamp,case_hash=sha,source_hashes=source_hashes,python=sys.version,os=platform.system(),mpmath=mp.__version__,scope='AB-LFR1 only'))
    checks=[]; failures=[]; states=[]; be_rows=[]; terminals=[]; endpoints={}
    journal=(out/'checks.jsonl').open('w')
    def check(name,ok,**details):
        row=dict(name=name,passed=bool(ok),**details)
        checks.append(row)
        if not ok: failures.append(row)
        journal.write(json.dumps(row,allow_nan=False)+'\n'); journal.flush()
    tol=cfg['tolerances']
    dps=tol['reference_dps']
    def reference(case,t,precision=dps):
        with mp.workdps(precision):
            a,k,g,c0=map(mp.mpf,[case['alpha_s_inv'],case['k_s_inv'],case['gamma'],case['c0_mol_m3']])
            tt=mp.mpf(t)
            # U'=alpha*c; R'=k*(b-gamma*c), net release into free phase.
            M=mp.matrix([[-a-k*g,k,0,0],[k*g,-k,0,0],[a,0,0,0],[-k*g,k,0,0]])
            e=mp.expm(M*tt)
            z=e*mp.matrix([c0,g*c0,0,0])
            return e,z
    def ratio(x,y,scale):
        return abs(x-y)/(tol['analytic_component_atol_scaled']*scale+tol['analytic_component_rtol']*abs(y))
    try:
        for case in cfg['cases']:
            cid=case['id']; a,k,g,T,c0=map(float,[case['alpha_s_inv'],case['k_s_inv'],case['gamma'],case['T_s'],case['c0_mol_m3']])
            b0=g*c0; scale_c=c0 or 1.; scale_b=max(c0,b0) or 1.; total=c0+b0 or 1.
            print('CASE',cid,case['purpose'],flush=True)
            for fraction in cfg['time_fractions']:
                with mp.workdps(dps): tt=mp.mpf(case['T_s'])*mp.mpf(fraction)
                E,z=reference(case,tt)
                t=float(tt); c,b=exact_state(a,k,g,t,c0); P=propagator(a,k,g,t)
                cr,br,U,R=map(float,z)
                mr=max(ratio(P[i][j],float(E[i,j]),1.) for i in range(2) for j in range(2))
                sr=max(ratio(c,cr,scale_c),ratio(b,br,scale_b))
                residual=abs(math.fsum([c,b,U,-c0,-b0]))/total
                fr=abs(math.fsum([c,U,-R,-c0]))/total
                brs=abs(math.fsum([b,R,-b0]))/total
                with mp.workdps(dps):
                    cc=mp.mpf(case['c0_mol_m3']); bb=mp.mpf(case['gamma'])*cc
                    rerr=max(abs(z[0]+z[1]+z[2]-cc-bb),abs(z[0]+z[2]-z[3]-cc),abs(z[1]+z[3]-bb))/(cc+bb or 1)
                tag=f'{cid}@{fraction}'
                check(tag+':propagator_reference',mr<=1,max_tolerance_ratio=mr)
                check(tag+':state_reference',sr<=1,max_tolerance_ratio=sr)
                check(tag+':positivity',min(c,b,*[q for row in P for q in row],cr,br,U)>=0)
                check(tag+':inventory',max(residual,fr,brs)<=tol['conservation_total_scaled'],total_scaled=residual,free_scaled=fr,bound_scaled=brs)
                check(tag+':reference_inventory',rerr<mp.mpf('1e-65'),scaled=float(rerr))
                check(tag+':inlet_bounds',c<=c0+2e-13*scale_c and b<=b0+2e-13*scale_b)
                states.append(dict(case_id=cid,time_fraction=fraction,t_s=t,c=c,b=b,c_ref=cr,b_ref=br,uptake_ref=U,release_ref=R,matrix_tolerance_ratio=mr,state_tolerance_ratio=sr,conservation_scaled=residual))
                if fraction=='1':
                    endpoints[cid]=(case,(c,b,U,R),z)
                    terminals.append(dict(case_id=cid,purpose=case['purpose'],alpha=a,k=k,gamma=g,T=T,c0=c0,b0=b0,c=c,b=b,uptake=U,net_release=R,c_equilibrium=equilibrium_state(a,g,T,c0)[0],total_residual_scaled=residual))
            # Full matrix semigroup, including the Jordan off-diagonal case.
            P=propagator(a,k,g,T); H=propagator(a,k,g,T/2)
            err=max(abs(P[i][j]-math.fsum(H[i][l]*H[l][j] for l in range(2))) for i in range(2) for j in range(2))
            check(cid+':semigroup',err<=tol['semigroup_atol'],max_abs_error=err)
            E1,z1=reference(case,case['T_s'],dps)
            E2,z2=reference(case,case['T_s'],tol['reference_recheck_dps'])
            with mp.workdps(tol['reference_recheck_dps']):
                ref_delta=max(abs(z1[i]-z2[i])/(1+abs(z2[i])) for i in range(4))
            check(cid+':precision_recheck',ref_delta<tol['reference_recheck_relative'],scaled=float(ref_delta))
            cr,br,U,R=map(float,z2)
            if g==0 or k==0:
                check(cid+':dissolved_or_frozen_limit',ratio(exact_state(a,k,g,T,c0)[0],c0*math.exp(-a*T),scale_c)<=1 and ratio(exact_state(a,k,g,T,c0)[1],b0,scale_b)<=1)
                check(cid+':accessible_inventory',U<=c0+tol['conservation_total_scaled']*scale_c)
            if a==0:
                c,b=exact_state(a,k,g,T,c0)
                check(cid+':zero_sink_limit',ratio(c,c0,scale_c)<=1 and ratio(b,b0,scale_b)<=1 and abs(U)<=tol['conservation_total_scaled']*total)
            if cid=='C21':
                c,b=exact_state(a,k,g,T,c0)
                re=max(abs(c/cr-1),abs(b/br-1))
                check(cid+':small_positive_relative_accuracy',re<=tol['analytic_component_rtol'],relative_error=re)
            local_be=[]
            for n in cfg['backward_euler_segments']:
                vals=backward_euler(a,k,g,T,n,c0)
                er=max(abs(vals['c']-cr)/scale_c,abs(vals['b']-br)/scale_b)
                cons=max(abs(vals[key]) for key in ['global_residual','free_residual','bound_residual','max_segment_residual','max_free_segment','max_bound_segment'])/total
                check(f'{cid}:BE:{n}:conservation',cons<=tol['be_conservation_total_scaled'],scaled=cons)
                check(f'{cid}:BE:{n}:positivity',vals['min_state']>=0)
                row=dict(case_id=cid,segments=n,state_error_scaled=er,uptake_error_scaled=abs(vals['uptake']-U)/total,conservation_scaled=cons,**vals)
                be_rows.append(row);local_be.append(row)
            if cid in cfg['convergence_required_cases']:
                errs=[r['state_error_scaled'] for r in local_be]
                floor=tol['analytic_component_atol_scaled']
                monotone=all(y<=x or x<floor for x,y in zip(errs,errs[1:]))
                order=math.log(errs[-2]/errs[-1],2) if errs[-1]>floor else None
                check(cid+':BE:convergence',monotone and (order is None or tol['be_last_order_min']<=order<=tol['be_last_order_max']) and errs[-1]<=tol['be_selected_finest_state_error_scaled'],last_order=order,finest_error=errs[-1])
            # Durable results per case, even if later cases raise.
            write_json(out/f'{cid}.json',dict(input=case,terminal=terminals[-1],backward_euler=local_be))
        # Separately evaluated algebraic limit. Finite rates remain finite.
        base=(1.,4.,1.,1.)
        eq=equilibrium_state(*base)
        limit_errors={}
        for cid in ['C11','C12','C13']:
            val=endpoints[cid][1]
            limit_errors[cid]=max(abs(val[0]-eq[0]),abs(val[1]-eq[1])/4.)
        es=list(limit_errors.values())
        check('finite_to_algebraic_limit',es[0]>es[1]>es[2] and es[2]<=tol['equilibrium_limit_state_error_C13_scaled'],errors=limit_errors)
        frozen=endpoints['C04'][1];weak=endpoints['C08'][1]
        weakerr=max(abs(weak[0]-frozen[0]),abs(weak[1]-frozen[1])/4.)
        check('weak_finite_limit',weakerr<=tol['weak_limit_state_error_C08_scaled'],scaled_error=weakerr)
        # Dimension conversion; NOT a nonlinear tissue solve.
        aa,TT=geometry_to_rates(1e-7,1e-3,1e-3,2e-9/60,5e-5)
        check('dimensional_conversion',abs(aa-0.5)<=1e-14 and abs(TT-3)<=1e-14,alpha=aa,T=TT,Da=aa*TT,R=2*TT)
        # Deliberate wrong-model controls: expected to fail the correct physics.
        wrong=(1+4)*math.exp(-1)-4
        gap=abs(wrong-endpoints['C04'][1][0])
        check('negative_control_total_content_sink_detected',wrong<0 and gap>tol['negative_control_difference_min_scaled'],wrong_c=wrong,correct_c=endpoints['C04'][1][0],gap=gap)
        eqgap=abs(eq[0]-endpoints['C04'][1][0])
        check('negative_control_equilibrium_at_k0_detected',eqgap>tol['negative_control_difference_min_scaled'],gap=eqgap)
        # First Euler step leaves inlet b unchanged; second sees the stiff mismatch.
        h=1/16; c,b=1.,4.; a,k,g=1.,1e12,4.
        euler=[]
        for _ in range(2):
            c,b=c+h*(-a*c-k*(g*c-b)),b+h*k*(g*c-b)
            euler.append([c,b])
        check('negative_control_explicit_euler_detected',min(x for row in euler for x in row)<0,first_two_steps=euler)
    except Exception as exc:
        check('UNHANDLED_EXCEPTION',False,error_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        journal.close()
        for name,rows in [('states.csv',states),('backward_euler.csv',be_rows),('terminal.csv',terminals)]:
            if rows:
                with (out/name).open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        summary=dict(benchmark='AB-LFR1',case_count_completed=len(terminals),state_evaluations=len(states),be_runs=len(be_rows),checks=len(checks),passed=len(checks)-len(failures),failed=len(failures),failures=failures,seconds=time.perf_counter()-start,source_hashes=source_hashes,frozen_cases_sha256=sha,
                     max_state_tolerance_ratio=max((r['state_tolerance_ratio'] for r in states),default=None),max_matrix_tolerance_ratio=max((r['matrix_tolerance_ratio'] for r in states),default=None),max_analytic_conservation_scaled=max((r['conservation_scaled'] for r in states),default=None),max_be_conservation_scaled=max((r['conservation_scaled'] for r in be_rows),default=None))
        write_json(out/'SUMMARY.json',summary)
        print(json.dumps(summary,indent=2),flush=True)
    return 1 if failures else 0

if __name__=='__main__':
    raise SystemExit(run())
