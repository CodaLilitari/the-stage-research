"""Independent AB-KMAP0 saved-result algebra audit. No producer imports or solves."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, getcontext
from datetime import datetime
import ast, hashlib, json
getcontext().prec=80
HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'kinetic_mapping'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dec(x):
    if isinstance(x,F):return D(x.numerator)/D(x.denominator)
    return D(str(x))
checks=[]; recon={}
def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
def value(label,actual,reference):
    if isinstance(reference,bool):ok=actual is reference
    elif isinstance(reference,F):ok=F(actual)==reference
    else:ok=abs(dec(actual)-dec(reference))<=D('5e-14')*max(D(1),abs(dec(reference)))
    check(label,ok,dict(actual=actual,reference=str(reference)))
def mm(A,B):return [[sum(a*b for a,b in zip(row,col)) for col in zip(*B)] for row in A]
def add(A,B):return [[a+b for a,b in zip(ar,br)] for ar,br in zip(A,B)]
def scale(A,k):return [[k*a for a in row] for row in A]
I=[[F(1),F(0)],[F(0),F(1)]]
O=[[F(0),F(0)],[F(0),F(0)]]
def state(params):
    q,a,d=(F(params[k]) for k in ('q','a','d'))
    A=[[-q-a,d],[a,-d]];B=[[q],[F(0)]];C=[[F(0),F(1)]]
    T=-A[0][0]-A[1][1];det=A[0][0]*A[1][1]-A[0][1]*A[1][0]
    N=mm(mm(C,A),B)[0][0]
    return q,a,d,A,B,C,T,det,N
def roots(T,det):
    t=dec(T);d=dec(det);disc=(t*t-4*d).sqrt()
    # 80-digit direct root differs from the producer's double stable-root path.
    return (t-disc)/2,(t+disc)/2
plan=load(SRC/'diagnostic_cases.json'); saved=load(SRC/'diagnostic_results/results.json')
expect=load(SRC/'expected_outputs.json'); freeze=load(SRC/'FREEZE.json')
receipt=load(SRC/'diagnostic_results/receipt.json'); auth=load(SRC/'RUN_AUTHORIZATION.json')
ledger=load(SRC/'diagnostic_results/attempt_ledger.json')
check('freeze_digest',sha(SRC/'FREEZE.json')==receipt['freeze_sha256']==auth['freeze_sha256'])
check('authorization_digest',sha(SRC/'RUN_AUTHORIZATION.json')==receipt['authorization_sha256'])
for entry in freeze['files']:
    p=SRC/entry['path'];check('binding:'+entry['path'],p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'])
ids=[x['id'] for x in plan['cases']]
check('exact_12_case_reconciliation',len(set(ids))==12 and ids==[x['id'] for x in saved]==[x['id'] for x in ledger])
check('sequential_attempt_ledger',[x['attempt'] for x in ledger]==list(range(1,13)) and all(x['status']=='passed' for x in ledger))
check('receipt_case_check_counts',receipt['status']=='completed' and receipt['attempts']==receipt['passed_cases']==12 and receipt['checks']==receipt['passed_checks']==sum(len(x['checks']) for x in saved)==89)
check('declared_no_fits_integrations_retries',all(receipt[x]==0 for x in ('empirical_fits','ode_integrations','pde_solves','automatic_retries')))
budget=plan['budget']
check('reported_resources_within_caps',receipt['elapsed_seconds']<budget['wall_seconds'] and max(receipt['resources'].values())<budget['process_mib']*1024**2 and sum(p.stat().st_size for p in (SRC/'diagnostic_results').rglob('*') if p.is_file())<budget['output_mib']*1024**2 and receipt['cpu_affinity_mask'].bit_count()==1)
window=(datetime.fromisoformat(auth['deadline_utc'])-datetime.fromisoformat(auth['admitted_utc'])).total_seconds()
check('admission_window_and_attempt_cap',0<window<=60 and auth['max_attempts']==budget['attempts_including_failures']==12 and auth['execution_authorized'] and auth['exclusive_compute_slot'])

for case,row in zip(plan['cases'],saved):
    ident=case['id'];kind=case['kind'];got=row['actual'];out={}
    if 'parameters' in case:
        q,a,d,A,B,C,T,det,N=state(case['parameters']);beta=a/d
        ls,lf=roots(T,det)
        check(ident+':Cayley_Hamilton',add(add(mm(A,A),scale(A,T)),scale(I,det))==O)
        check(ident+':positive_real_poles',0<ls<=min(dec(q),dec(d)) and lf>=max(dec(q),dec(d)))
        check(ident+':output_elimination',mm(C,B)==[[F(0)]] and mm(mm(C,A),B)==[[N]])
    if kind=='decay':
        b=F(case['b0']);v=F(case['bprime0']);c=(v+d*b)/a
        slow=(dec(v)+lf*dec(b))/(lf-ls);fast=dec(b)-slow
        out=dict(T=T,D=det,N=N,beta=beta,c0=c,lambda_s=ls,lambda_f=lf,slow_coefficient=slow,fast_coefficient=fast)
        for i,t in enumerate(plan['times_s']):value(ident+':trace:'+str(i),got['trace'][i],slow*(-ls*dec(t)).exp()+fast*(-lf*dec(t)).exp())
        check(ident+':matched_initial_value_derivative',mm(C,[[c],[b]])==[[b]] and mm(mm(C,A),[[c],[b]])==[[v]])
    elif kind=='transfer_partner':
        # Obtain partner from the other root of q^2-T*q+(D+N), then a=N/q,d=D/q.
        qp=T-q;ap=N/qp;dp=det/qp
        out=dict(T=T,D=det,N=N,beta=beta,partner_q=qp,partner_a=ap,partner_d=dp,same_calibrated_kernel=True)
        _,_,_,Ap,Bp,Cp,Tp,Dp,Np=state(dict(q=qp,a=ap,d=dp))
        S=[[qp/q,d*(q-qp)/(a*q)],[F(0),F(1)]]
        check(ident+':similarity_A',mm(S,A)==mm(Ap,S))
        check(ident+':similarity_B',mm(S,B)==Bp)
        check(ident+':similarity_C',mm(Cp,S)==C)
        check(ident+':equilibrium_initial_line',mm(S,[[F(1)],[beta]])==[[F(1)],[beta]])
        check(ident+':distinct_positive_partner',qp>0 and qp!=q and (Tp,Dp,Np)==(T,det,N))
        recon['partner_S']=[[str(v) for v in r] for r in S]
        recon['coincident_exception']='q=a+d gives the same parameter vector and S=I; it is not a second distinct solution.'
    elif kind=='internal_state':
        q2,a2,d2,A2,B2,C2,*_=state(case['partner'])
        b=F(case['b0']);v=F(case['bprime0']);c1=(v+d*b)/a;c2=(v+d2*b)/a2
        V1=mm(A,[[c1],[b]]);V2=mm(A2,[[c2],[b]])
        out=dict(first_c0=c1,second_c0=c2,first_cprime0=V1[0][0],second_cprime0=V2[0][0],same_b_initial_conditions=V1[1][0]==V2[1][0]==v,internal_derivatives_differ=V1[0][0]!=V2[0][0])
    elif kind in ('shared_chemistry','shared_chemistry_reject'):
        *_,t2,d2,n2=state(case['second']);dt=t2-T;dd=d2-det
        if kind=='shared_chemistry_reject':out=dict(delta_T=dt,delta_D=dd,shared_chemistry_consistent=False);check(ident+':contradiction',dt==0 and dd!=0)
        else:
            chem=dd/dt;q1=det/chem;q2=d2/chem;aa=T-q1-chem
            out=dict(first_T=T,first_D=det,second_T=t2,second_D=d2,recovered_d=chem,recovered_a=aa,first_q=q1,second_q=q2,shared_chemistry_consistent=min(chem,aa,q1,q2)>0 and t2-q2-chem==aa)
            check(ident+':calibrated_numerators',N/det==n2/d2==aa/chem)
    elif kind=='series_resistance':
        p1,f1=(F(case['first'][k]) for k in ('P','film'));p2,f2=(F(case['second'][k]) for k in ('P','film'));av=F(case['area_volume'])
        k1=p1*f1/(p1+f1);k2=p2*f2/(p2+f2)
        out=dict(first_K=k1,second_K=k2,first_q=av*k1,second_q=av*k2,distinct_resistances=(p1,f1)!=(p2,f2))
    elif kind in ('qssa_valid','qssa_invalid'):
        # Schur complement eliminating the fast free-state row of A and B.
        kr=-(A[1][1]-A[1][0]*A[0][1]/A[0][0]);kf=-A[1][0]*B[0][0]/A[0][0]
        out=dict(qssa_forward=kf,qssa_reverse=kr,beta=beta,epsilon_c=d/(q+a),lambda_s=ls,relative_rate_error=abs(dec(kr)/ls-1),pole_ratio=ls/lf)
        check(ident+':qssa_gain',kf/kr==beta)
    elif kind=='chemical_fast':
        # Equilibrated partition b/c=a/d: total=(1+beta)c, source q(u-c).
        kr=q/(1+beta);low=det/T
        out=dict(chemical_fast_forward=beta*kr,chemical_fast_reverse=kr,low_frequency_forward=N/T,low_frequency_reverse=low,beta=beta,chemical_rate_error=abs(dec(kr)/ls-1),internal_free_qssa_error=abs(dec(d*q/(q+a))/ls-1),lambda_s=ls)
        check(ident+':low_frequency_error_identity',abs(dec(low)/ls-1 - (-ls/(lf+ls)))<D('1e-70'))
    elif kind=='nonlinear_scale':
        s={k:F(v) for k,v in case['state'].items()};eta=F(case['eta'])
        binding=s['kon']*s['c']*(s['B']-s['b']);release=s['koff']*s['b'];R=binding-release
        total=s['q']*(s['u']-s['c']);dc=total-R
        # Independent scaling law: reaction and internal inventories scale eta.
        out=dict(R=R,cprime=dc,bprime=R,totalprime=total,scaled_R=eta*R,scaled_cprime=eta*dc,scaled_bprime=eta*R,scaled_totalprime=eta*total,first_output=s['gain']*s['b'],scaled_output=s['gain']/eta*(eta*s['b']),fixed_input_symmetry_residual_per_unit_u=s['q']*(1-eta),fixed_nonzero_input_breaks_scale=eta!=1 and s['q']!=0)
        check(ident+':zero_input_required',s['u']==0 and dc+R==total)
    for field,ref in out.items():value(ident+':independent:'+field,got[field],ref)
    check(ident+':all_saved_fields_covered',set(got)==set(out)|({'trace'} if kind=='decay' else set()))
    recon[ident]={k:str(v) for k,v in out.items()}
    for comparison in row['checks']:
        key=comparison['field'];ex=expect[ident][key]
        if key.endswith(('_lt','_gt')):
            field,op=key.rsplit('_',1);ref=dec(out[field]);ok=ref<dec(ex) if op=='lt' else ref>dec(ex)
        else:
            ref=out[key]
            ok=ref is ex if isinstance(ex,bool) else (ref==F(ex) if isinstance(ref,F) else abs(dec(ref)-dec(F(ex)))<=D('1e-12')*max(D(1),abs(dec(F(ex)))))
        check(ident+':frozen_expected:'+key,ok and comparison['passed'] is True and comparison['expected']==ex)

# Static boundary review: no producer import/execution, plus source AST inspection.
tree=ast.parse((SRC/'analytic_diagnostic.py').read_text())
imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
check('producer_imports_standard_library_only',all(n in {'pathlib','fractions','ctypes','ctypes.wintypes','datetime','hashlib','json','math','os','socket','sys','time'} for n in imports))
inputs=['FREEZE.json','RUN_AUTHORIZATION.json','diagnostic_cases.json','expected_outputs.json','analytic_diagnostic.py','DERIVATION.md','SOURCE_ROUTE.md','SOURCE_RECEIPT.json','README.md','diagnostic_results/results.json','diagnostic_results/receipt.json','diagnostic_results/attempt_ledger.json']
report=dict(scope='Independent exact-rational state-space and Decimal-80 saved-result audit. No producer import, evaluator replay, fits, ODE/PDE or transport calls.',
  passed=sum(c['passed'] for c in checks),total=len(checks),checks=checks,reconstruction=recon,
  source_bindings=[dict(path=p,sha256=sha(SRC/p)) for p in inputs],
  author_run=dict(case_records=12,checks=89),
  qualifications=['Positive-parameter local linear model; partner collapses when q=a+d.',
    'Transfer equivalence is zero-state or appropriately transformed initial state; equilibrium initial line is preserved.',
    'Internal-free observation distinguishes the recorded release pair, not an unperturbed equilibrium or every arbitrary experiment.',
    'QSSA requires time-scale and forcing/initial-layer conditions, not merely a favorable one-rate example.',
    'Receipt resource enforcement is cooperative. Saved ledger has no immutable timestamp per attempt; it does not independently certify temporal execution order.',
    'Source route spot-check only; no newly recovered empirical parameter or source-dataset replication. Nua efflux extension excluded.'])
(HERE/'audit_receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(passed=report['passed'],total=report['total'],failures=[c for c in checks if not c['passed']],receipt_sha256=sha(HERE/'audit_receipt.json')),indent=2))
