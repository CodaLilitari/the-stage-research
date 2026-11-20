"""Fit a robust centered response to other instruments, then score each omitted instrument."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog
from score import data,assignments

def fit(groups,scale_bounds):
    # Minimize the largest possible assignment loss separately in each
    # training analyzer. Two global fitted parameters: intercept and scale.
    nvar=2+len(groups)
    fits=[]
    for (x,v) in groups:
        ixs=assignments(x[0][:,0],x[1][:,0],.005)
        xn=x[0][:,1];xn=2*(xn-xn.mean())
        edges=sorted({(i,j) for perm in ixs for i,j in enumerate(perm)})
        endpoint={(i,j):nvar+k for k,(i,j) in enumerate(edges)}
        fits.append((xn,x[1][:,1],ixs,endpoint))
        nvar+=len(edges)
    c=np.zeros(nvar);c[2:2+len(groups)]=1/len(groups)
    mat=[];rhs=[]
    for g,(x,y,ixs,endpoint) in enumerate(fits):
        for (i,j),k in endpoint.items():
            for sign in [-1,1]:
                q=np.zeros(nvar);q[0]=sign;q[1]=sign*x[i];q[k]=-1
                mat.append(q);rhs.append(sign*y[j])
        for perm in ixs:
            q=np.zeros(nvar);q[2+g]=-1
            for i,j in enumerate(perm):q[endpoint[i,j]]=1/len(x)
            mat.append(q);rhs.append(0)
    bounds=[(None,None),scale_bounds]+[(0,None)]*(nvar-2)
    sol=linprog(c,A_ub=mat,b_ub=rhs,bounds=bounds,method='highs');assert sol.success
    # Prefer the smallest nonnegative scale within numerical tolerance of the trained optimum.
    qfit=np.zeros(nvar);qfit[1]=1
    sol2=linprog(qfit,A_ub=[*mat,c],b_ub=[*rhs,sol.fun+1e-10],bounds=bounds,method='highs');assert sol2.success
    beta=max(0.,sol2.x[1])
    # Given that chosen scale, the set of intercept minimizers may be an interval.
    # Use its midpoint as a fully determined training-only rule.
    bounds[1]=(beta,beta);icent=np.zeros(nvar);icent[0]=1
    mus=[]
    for sign in [1,-1]:
        s=linprog(sign*icent,A_ub=[*mat,c],b_ub=[*rhs,sol.fun+1.1e-10],bounds=bounds,method='highs')
        assert s.success;mus.append(s.x[0])
    return float(np.mean(mus)),float(beta),float(sol.fun),mus

def run():
    series=data();out={}
    for (name,obs),g in series.items():
        other=[((gg[5],gg[10]),nm) for (nm,o),gg in series.items() if nm!=name and obs==o]
        t5,t10=g[5],g[10]
        ix=assignments(t5[:,0],t10[:,0],.005);out[name+';'+obs]={}
        for label,bound in [('free',(0,1)),('no individual effect',(0,0)),('full individual effect',(1,1))]:
            mu,b,training,mus=fit(other,bound);pred=mu+2*b*(t5[:,1]-t5[:,1].mean())
            error=abs(pred-t10[:,1][ix]).mean(axis=1)
            out[name+';'+obs][label]=dict(center_g_dl=mu,weight=b,training_mae=training,center_range=mus,held_mae=[float(error.min()),float(error.max())])
    pooled={o:{label:np.mean([rec[label]['held_mae'] for k,rec in out.items() if k.endswith(';'+o)],axis=0).tolist() for label in next(iter(out.values()))} for o in ('cellular','total')}
    result={'by_instrument':out,'equal_instrument_held_mae':pooled,'mode':'Retrospective leave-one-analyzer-out with potentially shared specimens across analyzers.'}
    (Path(__file__).parent/'instrument-heldout.json').write_text(json.dumps(result,indent=2))
    print(pooled)
if __name__=='__main__':run()
