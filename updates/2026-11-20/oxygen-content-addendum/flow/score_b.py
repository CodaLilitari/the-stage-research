"""Score only after a verified lock of all responses. No source-image access here."""
from pathlib import Path
from itertools import product
import csv,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).parent
def intervals_rms(e,r):
    return [float(np.mean(np.maximum(0,abs(e)-r)**2)**.5),float(np.mean((abs(e)+r)**2)**.5)]
def lower_benefit(A,B,z,ta,tb):
    # Exact minimum (under a rectangular reading-error sensitivity box) of the
    # difference of mean squared errors, MSE(chord) - MSE(residual transfer).
    # Holding B fixed gives a concave objective in every A coordinate; holding
    # A fixed gives a linear objective in the B coordinates. A minimum exists
    # at corners of all intervals. Handle the four shared endpoints explicitly.
    t=z[1:-1]/z[-1];ans=float('inf')
    for pins in product([-1,1],repeat=4):
        al,ar=A[0]+pins[0]*ta[0],A[-1]+pins[1]*ta[-1]
        bl,br=B[0]+pins[2]*tb[0],B[-1]+pins[3]*tb[-1]
        candidates=[]
        for s,v in product([-1,1],repeat=2):
            d=A[1:-1]+s*ta[1:-1]-(1-t)*al-t*ar
            r=B[1:-1]+v*tb[1:-1]-(1-t)*bl-t*br
            candidates.append(2*r*d-d*d)
        ans=min(ans,np.min(candidates,axis=0).mean())
    return float(ans)
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def run(digest):
    f=ROOT/'conditional-forecast-coefficients.json';assert hashlib.sha256(f.read_bytes()).hexdigest()==digest
    lock=json.loads(f.read_bytes());data=rows(ROOT/'target-readings.csv');a0=rows(ROOT/'input/train.csv')
    a={int(row['depth_um']):row for row in a0}
    out={}
    for tag in sorted({r['trace'] for r in data}):
        target={int(row['depth_um']):row for row in data if row['trace']==tag}
        ds=[d for d in (1800,1700,1600,1500) if d in target]
        if not ds or 0 not in target:raise ValueError('No preregistered pair of B endpoints')
        D=ds[0];z=np.asarray(sorted(set(range(0,D+1,100))&target.keys()))
        assert len(z)-2>=5
        B=np.array([float(target[k]['oxygen_umol_per_l']) for k in z]);A=np.array([float(a[k]['oxygen_umol_per_l']) for k in z])
        ta=np.array([float(a[k]['chart_tolerance_umol_per_l']) for k in z]);tb=np.array([float(target[k]['chart_tolerance_umol_per_l']) for k in z]);se=np.array([float(a[k]['se_umol_per_l']) for k in z])
        sub=[i for i,v in enumerate(lock['design']) if int(v['D_um'])==D and int(v['depth_um']) in set(z[1:-1])]
        assert [int(lock['design'][i]['depth_um']) for i in sub]==list(z[1:-1])
        t=z[1:-1]/D;res={}
        for n,coef in lock['models'].items():
            p=np.asarray(coef)[sub]@[B[0],B[-1],1.]
            e=p-B[1:-1]
            r=tb[1:-1]+abs(np.asarray(coef)[sub,0])*tb[0]+abs(np.asarray(coef)[sub,1])*tb[-1]
            if n=='registered-affine-residual':r+=ta[1:-1]+(1-t)*ta[0]+t*ta[-1]
            if n=='unchanged-stagnant':r+=ta[1:-1]
            res[n]={'rmse':float(np.mean(e**2)**.5),'mean_error':float(e.mean()),'mae':float(np.mean(abs(e))),'rmse_reading_outer':intervals_rms(e,r),'A_training_reading_included':n in ('registered-affine-residual','unchanged-stagnant','linear-boundaries')}
        entry={'scores':res,'measured_left_right':[B[0],B[-1]],'D_um':int(D),'n_scored':len(z)-2,'sharp_min_MSE_chord_minus_primary_under_chart_reading':lower_benefit(A,B,z,ta,tb)}
        if all(target[k].get('se_umol_per_l') for k in z):
            se_b=np.array([float(target[k]['se_umol_per_l']) for k in z])
            entry['minimum_MSE_difference_pointwise_SE_plus_reading_sensitivity']=lower_benefit(A,B,z,ta+se,tb+se_b)
        out[tag]=entry
    summary={m:float(np.mean([v['scores'][m]['rmse'] for v in out.values()])) for m in next(iter(out.values()))['scores']}
    gains={m:summary[m]-summary['registered-affine-residual'] for m in ['linear-boundaries','unchanged-stagnant']}
    data={'locked_sha256':digest,'measured_sha256':hashlib.sha256((ROOT/'target-readings.csv').read_bytes()).hexdigest(),'traces':out,'equal_trace_rmse_umol_L':summary,'registered_gains_umol_L':gains,'primary_pass':min(gains.values())>=5}
    (ROOT/'transfer-scores.json').write_text(json.dumps(data,indent=2));print(summary,gains,data['primary_pass'])
if __name__=='__main__':run(sys.argv[1])
