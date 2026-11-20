"""Exact threshold certificate per fixed endpoint pair for arbitrary interior assignment."""
import hashlib,itertools,json
from pathlib import Path
import numpy as np
from rank_score import table,LOCK
ROOT=Path(__file__).resolve().parent
assert hashlib.sha256((ROOT/'conditional-forecast-coefficients.json').read_bytes()).hexdigest()==LOCK
B=np.array([float(v['concentration_umol_per_l']) for v in table(ROOT/'rank-readings.csv')]).reshape(19,4).T
A=np.array([float(v['oxygen_umol_per_l']) for v in table(ROOT/'input/train.csv')])
t=np.arange(1,18)/18;d=A[1:-1]-((1-t)*A[0]+t*A[-1])
lo,hi=np.min(B[:,1:-1],axis=0),np.max(B[:,1:-1],axis=0)
# For each g >= 0 the condition ||r||-||r+d|| >= g is equivalent to
# -2 <r,d> - ||d||^2 - g^2 >= 2 g ||r+d|| (RMS-scaled norms).
# LHS minus RHS is concave in r, so checking all vertices proves the
# inequality on the entire box, including interior ranks and co-location.
gaps=np.full((4,4),np.inf)
for start in range(0,2**17,8192):
    bits=(np.arange(start,start+8192)[:,None]>>np.arange(17)[None,:])&1
    y=lo[None,:]+bits*(hi-lo)[None,:]
    for i,j in itertools.product(range(4),repeat=2):
        r=(1-t)*B[i,0]+t*B[j,-1]-y
        g=np.sqrt(np.mean(r*r,axis=1))-np.sqrt(np.mean((r+d)**2,axis=1))
        gaps[i,j]=min(gaps[i,j],np.min(g))
# With a negative vertex minimum the positive-g proof cannot certify that negative
# value. Use the reverse triangle inequality as a valid universal fallback.
proof=np.where(gaps>=0,gaps,-np.sqrt(np.mean(d*d)))
from scipy.optimize import minimize
for i,j in np.argwhere(gaps<0):
    c=(1-t)*B[i,0]+t*B[j,-1]
    L,U=c-hi,c-lo
    h0,h1=-gaps[i,j],np.sqrt(np.mean(d*d))
    # For negative gain, ||r||+h >= ||r+d|| iff
    # -2*r.d-||d||^2+2h||r||+h^2 >= 0. Every supporting hyperplane to
    # the norm gives a global affine minorant with an exact box minimum.
    for _ in range(32):
        h=.5*(h0+h1)
        def objective(r):
            nr=np.sqrt(np.mean(r*r));return np.mean(-2*r*d-d*d)+2*h*nr+h*h
        def grad(r):return 2*(h*r/max(np.sqrt(np.mean(r*r)),1e-14)-d)/len(r)
        sol=minimize(objective,(L+U)/2,jac=grad,bounds=list(zip(L,U)),method='L-BFGS-B',
                     options={'ftol':1e-14,'gtol':1e-11,'maxiter':200})
        w=sol.x/max(np.sqrt(np.mean(sol.x**2)),1e-14)
        a=2*h*w-2*d
        bound=np.mean(np.minimum(a*L,a*U)-d*d)+h*h
        if bound>=1e-8:h1=h
        else:h0=h
    proof[i,j]=-h1
lower=min(np.mean(proof[np.arange(4),v]) for v in itertools.permutations(range(4)))
out={'endpoint_pair_vertex_minima':gaps.tolist(),'certified_per_pair_lower_gains':proof.tolist(),
     'assignment_free_equal_trace_lower_fixed_central_readings':float(lower)}
for label,terr,aerr in [('central',0.,0.),('chart',4*1.24462962,2.9424701)]:
    # Sum of the four MSE improvements depends only on average concentrations.
    # A common reciprocal-denominator bound is valid on positive gains. Charge
    # an explicit signed penalty for any trace for which the gain could be negative.
    from score_b import lower_benefit
    delta=lower_benefit(A,B.mean(axis=0),np.arange(19)*100,np.full(19,aerr),np.full(19,terr))
    e_min=np.zeros_like(gaps);lows=np.zeros_like(gaps);ups=np.zeros_like(gaps)
    for i,j in itertools.product(range(4),repeat=2):
        c=(1-t)*B[i,0]+t*B[j,-1]
        # Simultaneously cover target and boundary reading errors.
        u=c-lo+2*terr;l=c-hi-2*terr
        dlow,dhigh=d-2*aerr,d+2*aerr
        e_min[i,j]=np.min([-2*r*dd-dd**2 for r,dd in itertools.product([l,u],[dlow,dhigh])],axis=0).mean()
        def rm(x):return np.mean(x*x)**.5
        min_r=np.maximum(0,np.maximum(l,-u));min_p=np.maximum(0,np.maximum(l+dlow,-u-dhigh))
        lows[i,j]=max(rm(min_r)+rm(min_p),rm(np.maximum(0,abs(d)-2*aerr)))
        ups[i,j]=rm(np.maximum(abs(l),abs(u)))+rm(np.maximum(abs(l+dlow),abs(u+dhigh)))
    proofs=[]
    for v in itertools.permutations(range(4)):
        index=(np.arange(4),v);k=1/np.max(ups[index])
        proofs.append(float(delta*k+np.mean(np.minimum(0,e_min[index])*(1/lows[index]-k))))
    out['shared_numerator_lower_'+label]=min(proofs)
    if label=='central':
        q=np.maximum(proof,np.where(e_min>=0,e_min/ups,e_min/lows))
        out['mixed_pair_lower_central']=min(float(np.mean(q[np.arange(4),v])) for v in itertools.permutations(range(4)))
        out['central_multimethod_pair_bounds']=q.tolist()
(ROOT/'equal-trace-range.json').write_text(json.dumps(out,indent=2));print(float(lower),gaps)
