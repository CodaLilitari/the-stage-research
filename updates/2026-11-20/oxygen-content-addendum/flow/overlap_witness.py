"""Find a counterexample inside a deliberately relaxed rank-and-reading sensitivity set."""
import itertools,json
from pathlib import Path
import numpy as np
from rank_score import table
ROOT=Path(__file__).resolve().parent
r=table(ROOT/'rank-readings.csv');a=table(ROOT/'input/train.csv');x=table(ROOT/'target-readings.csv')
B=np.array([float(v['concentration_umol_per_l']) for v in r]).reshape(19,4)
A=np.array([float(v['oxygen_umol_per_l']) for v in a]);ta=float(a[0]['chart_tolerance_umol_per_l']);tb=float(r[0]['tolerance_umol_per_l'])
cross={int(v['depth_um'])//100:float(v['oxygen_umol_per_l']) for v in x}
P=list(itertools.permutations(range(4)))
def orders(i):
    if i not in cross:return P
    near=int(np.argmin(abs(B[i]-cross[i])));return [p for p in P if p[0]==near]
choices=[orders(i) for i in range(19)]
t=np.arange(1,18)[:,None]/18
def score(b,s):
    m=(1-t)*b[0]+t*b[-1]-b[1:-1]
    d=s[1:-1,None]-(1-t)*s[0]-t*s[-1]
    return float(np.mean(np.mean(m*m,axis=0)**.5-np.mean((m+d)**2,axis=0)**.5))
rng=np.random.default_rng(128)
best=np.inf
for start in range(6):
    ords=[list(q[rng.integers(len(q))]) for q in choices];S=A.copy();S[1:-1]+=ta;S[[0,-1]]-=ta
    b=np.array([B[i,order] for i,order in enumerate(ords)])
    shift=np.full_like(b,tb);shift[[0,-1]]=-tb
    for step in range(6):
        for i in rng.permutation(19):
            def cost(p):
                trial=b+shift;trial[i]=B[i,p]+shift[i];return score(trial,S)
            p=min(choices[i],key=cost);ords[i]=list(p);b[i]=B[i,list(p)]
            vals=[]
            for sign in [-1,1]:
                z=S.copy();z[i]=A[i]+sign*ta;vals.append(score(b+shift,z))
            S[i]=A[i]+([-1,1][np.argmin(vals)])*ta
            for j in range(4):
                vals=[]
                for sign in [-1,1]:
                    u=b+shift;u[i,j]=b[i,j]+sign*tb;vals.append(score(u,S))
                shift[i,j]=([-1,1][np.argmin(vals)])*tb
    val=score(b+shift,S)
    if val<best:
        best=val;w={'gain':val,'orders':ords,'source_reading_changes':(S-A).tolist(),'target_reading_changes':shift.tolist()}
assert abs(np.array(w['source_reading_changes'])).max()<=ta+1e-10
assert abs(np.array(w['target_reading_changes'])).max()<=tb+1e-10
assert all(tuple(row) in choices[i] for i,row in enumerate(w['orders']))
assert abs(score(np.array([B[i,o] for i,o in enumerate(w['orders'])])+w['target_reading_changes'],A+w['source_reading_changes'])-best)<1e-10
(ROOT/'overlap-witness.json').write_text(json.dumps(w,indent=2));print(best)
