"""Score every baseline-compatible assignment between the study's two displayed concentrations."""
from collections import defaultdict
from itertools import permutations
from pathlib import Path
import csv,json
import numpy as np
from scipy.optimize import linear_sum_assignment
from extract import ROOT,NAMES,read

def assignments(x,y,tol):
    columns=[np.flatnonzero(abs(y-v)<=tol).tolist() for v in x]
    out=[]
    def visit(chosen,used):
        if len(chosen)==len(x):
            out.append(chosen)
            return
        for j in columns[len(chosen)]:
            if j not in used:visit(chosen+[j],used|{j})
    visit([],set())
    return np.asarray(out,int)

def data():
    points,_=read();series=defaultdict(dict)
    for name in NAMES:
        for obs in ('total','cellular'):
            for dose in (5,10):
                rows=sorted((q for q in points if (q['instrument'],q['observable'],q['condition'])==(name,obs,dose)),key=lambda q:(q['control_g_dl'],q['delta_g_dl']))
                if rows:series[(name,obs)][dose]=np.array([[q['control_g_dl'],q['delta_g_dl']] for q in rows],float)
    return series

def scores(series,tol):
    metrics={}; aggregate=defaultdict(lambda:defaultdict(list)); global_diffs=defaultdict(list)
    for (name,obs),v in series.items():
        x,y=v[5].T;xh,yh=v[10].T;ix=assignments(x,xh,tol)
        assert len(ix)>0,(name,obs,tol)
        peer_means=[vv[5][:,1].mean() for (nm,o),vv in series.items() if o==obs and nm!=name]
        methods={'double':2*y,'double group mean':2*np.mean(y),'double other-instrument mean':2*np.mean(peer_means),'nominal':1.3 if obs=='total' else 0.,'double leave-one-out mean':2*(np.sum(y)-y)/(len(y)-1)}
        mae={k:np.mean(abs(a-yh[ix]),axis=1) for k,a in methods.items()}
        rmse={k:np.mean((a-yh[ix])**2,axis=1)**.5 for k,a in methods.items()}
        def extent(a):return [float(a.min()),float(a.max())]
        pairdiff={k:mae['double']-m for k,m in mae.items() if k!='double'}
        metrics[name+';'+obs]={'n':len(y),'matchings':len(ix),'mae':{k:extent(m) for k,m in mae.items()},'rmse':{k:extent(m) for k,m in rmse.items()},'double_minus_comparator_mae':{k:extent(d) for k,d in pairdiff.items()}}
        for k,m in mae.items():aggregate[obs][k].append(extent(m))
        for k,m in pairdiff.items():global_diffs[(obs,k)].append(extent(m))
    return {'series':metrics,'equal_instrument_mae':{o:{k:np.mean(mm,axis=0).tolist() for k,mm in vv.items()} for o,vv in aggregate.items()},'equal_instrument_double_minus_comparator':{o:{k:np.mean(mm,axis=0).tolist() for (ob,k),mm in global_diffs.items() if ob==o} for o in aggregate}}

def dissociation(series):
    results={}
    for instrument in NAMES[:3]:
        for dose in (5,10):
            total=series[instrument,'total'][dose][:,1];cell=series[instrument,'cellular'][dose][:,1]
            contrast=total[:,None]-cell[None,:]
            lower_assignment=linear_sum_assignment(contrast);upper_assignment=linear_sum_assignment(-contrast)
            results[instrument+':'+str(dose)]={'possible_single_contrast_g_dl':[float(contrast.min()),float(contrast.max())],'mean_of_matched_total_minus_cellular_range':[float(contrast[idx].mean()) for idx in [lower_assignment,upper_assignment]],'n_total':len(total),'n_cellular':len(cell)}
    return results
if __name__=='__main__':
    s=data()
    out={'released_figure':True,'tolerances':{str(t):scores(s,t) for t in [.002,.005,.01,.05]},'cell_free_contrast':dissociation(s)}
    (ROOT/'independent-scores.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out['tolerances']['0.005']['equal_instrument_mae'],indent=2))
    print([(k,m['matchings']) for k,m in out['tolerances']['0.005']['series'].items()])
    print(out['cell_free_contrast'])
