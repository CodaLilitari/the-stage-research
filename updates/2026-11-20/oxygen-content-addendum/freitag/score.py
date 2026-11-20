"""Only run after the train-only local and external predictor rules have been fixed."""
from pathlib import Path
import json,re,hashlib
import numpy as np
P=Path(__file__).resolve().parent
locked=P/'local-forecast-lock.json'
assert hashlib.sha256(locked.read_bytes()).hexdigest()=='a5fc64ef7012eaf3fdb71ba9d89141b63796ab306a41914bfdbd4909dc585b30'
x=json.loads((P/'prediction-input.json').read_bytes())['query']; forecasts=json.loads(locked.read_bytes())
text=(P/'source-layout.txt').read_text(encoding='utf8').split('\f')[4].split('TABLE IV Parameter')[1]
rr=[]
for line in text.splitlines():
 t=line.strip()
 if not re.match(r'^(Baseline|20 min|60 min|100 min)\b',t):continue
 a=re.findall(r'(-?\d+(?:\.\d+)?)\s*±\s*(-?\d+(?:\.\d+)?)',t);assert len(a)==5
 r={n:[float(i),float(j)] for n,(i,j) in zip(['V','av','Q','delivery','uptake'],a)};rr.append(r)
assert len(rr)==len(x)==8
def mass_bound(Q,sq,z,sz):
 # Group means rounded to nearest unit on Q and 0.1 on C; sample SDs likewise.
 return [((Q-.5)*(z-.05)-(5/6)*(sq+.5)*(sz+.05))/100,((Q+.5)*(z+.05)+(5/6)*(sq+.5)*(sz+.05))/100]
ints=[];actual={}
for row,obs in zip(x,rr):
 assert row['Q']==obs['Q'][0]
 A=row['A'];Q=row['Q'];V,sv=obs['V'];av,sav=obs['av']
 z=A-V-av
 d=mass_bound(Q,row['errQ'],A,row['errA']);u=mass_bound(Q,row['errQ'],av,sav)
 actual[row['id']]={'V':V,'errV':sv,'av':av,'errav':sav,'delivery':obs['delivery'][0],'uptake':obs['uptake'][0]}
 ints.append(dict(id=row['id'],difference_minus_printed=z,rounding_identity_pass=abs(z)<=.15000001,
    delivery_bound=d,printed_delivery=obs['delivery'][0],delivery_compatible=d[0]<=obs['delivery'][0]+.05 and d[1]>=obs['delivery'][0]-.05,
    uptake_bound=u,printed_uptake=obs['uptake'][0],uptake_compatible=u[0]<=obs['uptake'][0]+.05 and u[1]>=obs['uptake'][0]-.05))
(P/'score-only.json').write_text(json.dumps(actual,indent=2))
groups={'all':[r['id'] for r in x],'baseline':[r['id'] for r in x if r['phase']=='baseline'],'post-baseline':[r['id'] for r in x if r['phase']!='baseline'],'control post':[r['id'] for r in x if r['phase']=='control'],'treated post':[r['id'] for r in x if r['arm']=='H' and r['phase']!='baseline'],'hemodilution only':[r['id'] for r in x if r['phase']=='dilution'],'carrier':[r['id'] for r in x if r['phase']=='carrier']}
def score(v):
 out={}
 for k,ids in groups.items():
  ds=np.array([v[i]-actual[i]['V'] for i in ids]);out[k]=dict(n=len(ids),rmse=float(np.mean(ds**2)**.5),bias=float(ds.mean()),mae=float(abs(ds).mean()),max_abs=float(abs(ds).max()))
 return out
scores={}
for mode in ['phase','pooled']:
 for m in ['fraction','difference','demand','plug-flow']:
  v={i:dd[mode][m] for i,dd in forecasts.items()};scores[mode+' '+m]=score(v)
research={'registered_models':scores,'target_interface':ints,'groups':groups}
(P/'local-scores.json').write_text(json.dumps(research,indent=2))
print([(k,round(d['post-baseline']['rmse'],4),round(d['post-baseline']['mae'],4),round(d['control post']['rmse'],4),round(d['treated post']['rmse'],4)) for k,d in scores.items()])
print(json.dumps([r for r in ints if not all(r[k] for k in ['rounding_identity_pass','delivery_compatible','uptake_compatible'])],indent=2))
