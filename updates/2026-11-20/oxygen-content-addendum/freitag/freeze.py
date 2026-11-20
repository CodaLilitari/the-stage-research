"""No target venous table or outcomes are opened by this program."""
from pathlib import Path
import hashlib,json
import numpy as np
P=Path(__file__).resolve().parent
train_src=P/'standl-means.json'
raw=json.loads(train_src.read_bytes())['groups'];cov=json.loads((P/'covariates-only.json').read_bytes())
rows=[]
for arm,rr in raw.items():
 for i,r in enumerate(rr):
  (Q,sQ),(A,sA),(V,sV)=r[:3]
  phase=('baseline' if i==0 else 'dilution' if i==1 else 'carrier' if arm=='H' else 'rbc')
  rows.append(dict(id=f'{arm}{i}',arm=arm,phase=phase,A=A,Q=Q,V=V,errA=sA,errQ=sQ,errV=sV,uncertainty='SEM',n=6))
query=[]
for a,q in zip(cov['II'],cov['IV']):
 group,name,A,sA=a;assert q[:2]==[group,name];Q,sQ=q[2:];phase=('baseline' if name=='Baseline' else 'control' if group=='1' else 'dilution' if name=='20 min' else 'carrier')
 query.append(dict(id='G'+group+'-'+name.replace(' ','-'),arm='control' if group=='1' else 'H',phase=phase,A=A,Q=Q,errA=sA,errQ=sQ,uncertainty='SD',n=6))
def predict(rs,A,Q):
 f=np.array([r['A'] for r in rs]);v=np.array([r['V'] for r in rs]);q=np.array([r['Q'] for r in rs]);av=f-v
 return {k:float(np.clip(x,0,A)) for k,x in [('fraction',A*(1-np.median(av/f))),('difference',A-np.median(av)),('demand',A-np.median(q*av)/Q),('plug-flow',A*np.exp(-np.median(-q*np.log(v/f))/Q))]}
forecast={}
for row in query:
 phase=row['phase'] if row['phase']!='control' else 'baseline';match=[r for r in rows if r['phase']==phase]
 forecast[row['id']]={scope:predict(rr,row['A'],row['Q']) for scope,rr in [('pooled',rows),('phase',match)]}
def once(name,obj):
 b=json.dumps(obj,indent=2).encode()
 f=P/name
 if f.exists() and f.read_bytes()!=b:raise ValueError('Stored pre-score record conflicts: '+name)
 f.write_bytes(b)
 return hashlib.sha256(b).hexdigest()
training_sha=once('prediction-input.json',{'train':rows,'query':query});fc=once('local-forecast-lock.json',forecast)
print('training/query-only',training_sha,'fixed forecasts',fc);print([(q['id'],q['A'],q['Q']) for q in query])
