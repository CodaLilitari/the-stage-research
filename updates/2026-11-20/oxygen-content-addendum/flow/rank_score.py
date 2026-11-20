"""Assignment-invariant difference of pooled squared losses and conditional RMSE enclosures."""
from pathlib import Path
import hashlib,json,csv,itertools
import numpy as np
from score_b import lower_benefit
ROOT=Path(__file__).resolve().parent
LOCK='0423744ec22898c5e8ef0c16c2718202a624bd61a70770042971c72cec970949'
def table(path):
    with path.open() as f:return list(csv.DictReader(f))
def run():
    f=ROOT/'conditional-forecast-coefficients.json';assert hashlib.sha256(f.read_bytes()).hexdigest()==LOCK
    ref=table(ROOT/'input/train.csv');A=np.array([float(r['oxygen_umol_per_l']) for r in ref]);ta=np.array([float(r['chart_tolerance_umol_per_l']) for r in ref])
    ranks=table(ROOT/'rank-readings.csv');B=np.array([float(r['concentration_umol_per_l']) for r in ranks]).reshape(19,4).T
    t=np.arange(1,18)/18;D=A[1:-1]-(1-t)*A[0]-t*A[-1];b=B.mean(axis=0)
    perms=list(itertools.permutations(range(4)));Y=B[:,1:-1];C=(1-t)*b[0]+t*b[-1]
    bunit=float(ranks[0]['tolerance_umol_per_l']);out={}
    for name,tb,eta in [('central',0.,np.zeros(19)),('chart',bunit,ta)]:
        def maxima(residual):
            # For fixed anchors, squared matching losses are maximized by reversed
            # rank matching, with a separate worst permutation allowed at each depth.
            # Reading allowances affect both the measured target and its two anchors.
            mx=-np.inf
            for order in perms:
                pred=np.sort((1-t)*B[:,0,None]+t*B[order,-1,None],axis=0)
                rad=2*tb
                if residual:pred+=D;rad+=eta[1:-1]+(1-t)*eta[0]+t*eta[-1]
                mx=max(mx,np.mean((abs(pred-np.sort(Y,axis=0)[::-1])+rad)**2))
            return np.sqrt(mx)
        lin_max=maxima(False);transfer_max=maxima(True)
        delta_min=lower_benefit(A,b,np.arange(19)*100,eta,np.full(19,tb))
        # Lower bounds on average trace RMSE follow by the triangle inequality,
        # using the norm of the mean residual (invariant to every assignment).
        chord_lower=np.mean(np.maximum(abs(C-b[1:-1])-2*tb,0)**2)**.5
        unchanged_lower=np.mean(np.maximum(abs(A[1:-1]-b[1:-1])-tb-eta[1:-1],0)**2)**.5
        # For central readings, trace-specific RMSE can additionally be bounded
        # with first/last anchors fixed and the worst ranked mark at each depth.
        # The average of those lower and upper bounds admits separate arbitrary
        # assignments per trace, hence is conservative.
        per_order=[]
        for order in perms:
            c=(1-t)*B[:,0,None]+t*B[order,-1,None];pp=c+D
            rc=abs(c[:,None,:]-Y[None,:,:]);rp=abs(pp[:,None,:]-Y[None,:,:])
            lower_per=np.mean(np.maximum(rc.min(axis=1)-2*tb,0)**2,axis=1)**.5
            ru=2*tb+eta[1:-1]+(1-t)*eta[0]+t*eta[-1]
            upper_per=np.mean((rp.max(axis=1)+ru)**2,axis=1)**.5
            per_order.append(float(np.mean(lower_per-upper_per)))
        delta_point=float(np.mean(2*D*(b[1:-1]-C)-D**2))
        out[name]={'pooled_chord_minus_transfer_MSE_point':delta_point,'pooled_MSE_advantage_lower':delta_min,
                   'pooled_RMSE_advantage_lower':float(delta_min/(lin_max+transfer_max)) if delta_min>0 else None,
                   'equal_trace_chord_minus_transfer_RMSE_lower':max(float(chord_lower-transfer_max),min(per_order)),
                   'equal_trace_unchanged_minus_transfer_RMSE_lower':float(unchanged_lower-transfer_max),
                   'pooled_chord_RMSE_upper':float(lin_max),'pooled_transfer_RMSE_upper':float(transfer_max),
                   'positions_mean_profile_chord_RMSE':float(np.mean((C-b[1:-1])**2)**.5),
                   'positions_mean_profile_transfer_RMSE':float(np.mean((C+D-b[1:-1])**2)**.5)}
    (ROOT/'rank-scores.json').write_text(json.dumps(out,indent=2));print(out)
if __name__=='__main__':run()
