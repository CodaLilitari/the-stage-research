"""Independent source checks and locked retrospective intermediate-speed comparator."""
from pathlib import Path
import json,csv
import numpy as np
P=Path(__file__).resolve().parent
def read(name):return list(csv.DictReader((P/name).open()))
def save(name,obj):(P/name).write_text(json.dumps(obj,indent=2,allow_nan=False))
curves=read('curves.csv');de=read('points-8DE.csv');bars=read('bars-8C.csv')
def getcurve(panel,rpm):
 out=[r for r in curves if r['panel']==panel and int(r['rpm'])==rpm and int(r['t'])<=198]
 return [float(r['mean']) if r['mean'] else None for r in out]
def fillnull(s):
 x=np.arange(len(s));z=np.array([np.nan if p is None else p for p in s]);ok=np.isfinite(z);z[0]=0;ok[0]=True
 return np.interp(x,x[ok],z[ok])
def ends(y):return np.mean(y[195:199])
def crossing(t,y,f,ref):
 ii=np.flatnonzero(y>=f*ref)
 if not len(ii):return None
 j=ii[0]
 return float(t[0] if j==0 else t[j-1]+(t[j]-t[j-1])*(f*ref-y[j-1])/(y[j]-y[j-1]))
ts=np.arange(199);score_t=ts[5:196:5]
train={'t':ts.tolist(),'rpm_train':[294,748],'rpm_query':445,'response_train':[getcurve('8B',r) for r in (294,748)],'buffer_proxy':getcurve('8A',294),'score_t':score_t.tolist()}
save('train.json',train)
target=fillnull(getcurve('8B',445));save('score-only.json',{'t':ts.tolist(),'rpm':445,'response':getcurve('8B',445)})
lo,hi=map(fillnull,train['response_train']);buf=fillnull(train['buffer_proxy'])
strategies={'nearest (294 rpm)':lo}
for name,u in [('rpm',(445-294)/(748-294)),('log-rpm',np.log(445/294)/np.log(748/294))]:
 ep=(1-u)*ends(lo)+u*ends(hi)
 strategies[name+' raw']=(1-u)*lo+u*hi
 strategies[name+' fractional shape']=ep*((1-u)*lo/ends(lo)+u*hi/ends(hi))
 strategies[name+' pooled PBS shape']=ep*buf/ends(buf)
scores={}
for name,y in dict(target=target,**strategies).items():
 scores[name]={'endpoint':float(ends(y)),'rmse':float(np.mean((y[score_t]-target[score_t])**2)**.5),'t50':crossing(ts,y,.5,ends(y)),'t90':crossing(ts,y,.9,ends(y))}
for a in scores.values():
 for k in ('endpoint','t50','t90'):a[k+'_minus_observed']=a[k]-scores['target'][k]
native=[]
for bar in bars:
 mat,rpm=bar['material'],int(bar['rpm']); C=float(bar['mean']);S=float(bar['sd']);n=int(bar['n'])
 curve=getcurve('8B' if mat=='OMB' else '8A',rpm)
 # Exact figure 8A endpoints for 445/748 hidden: use no borrowed mean. Report PBS proxy separately.
 v=ends(fillnull(curve)) if any(v is not None for v in curve) else None
 sd_all=[r for r in curves if r['panel']==('8B' if mat=='OMB' else '8A') and int(r['rpm'])==rpm and 195<=int(r['t'])<=198 and r['upper'] and r['lower']]
 bsd=float(np.mean([(float(r['upper'])-float(r['lower']))/2 for r in sd_all])) if sd_all else None
 points=[]
 for t in [5,10,30,60]:
  rr=[r for r in de if r['material']==mat and int(r['rpm'])==rpm and int(r['t'])==t];d,e=rr
  points.append(dict(t=t,D=float(d['mean']),Dsd=float(d['sd']) if d['sd'] else None,E=float(e['mean']),Esd=float(e['sd']) if e['sd'] else None))
 native.append(dict(material=mat,rpm=rpm,n=n,C=C,Csd=S,B200=v,Bsd=bsd,points=points))
scales=[1.,.032,1.28,1.312];save('summary.json',dict(cells=native,scales=scales))
table=[]
for c in native:
 T=c['C'];S=c['Csd'];n=c['n']
 for q in c['points']:
  R=q['E']/100;D=q['D'];sR=None if q['Esd'] is None else q['Esd']/100
  rec=dict(material=c['material'],rpm=c['rpm'],t=q['t'],single_point_scale=T*R/D if D else None,scale_checks={})
  for k in scales:
   delta=D-(T/k)*R
   lim=None if sR is None else (n-1)/n*S/k*sR
   # ±1 native unit on means AND SD estimates. Uncertain one-cap values diagnostic rather than calibrator.
   if lim is None:relax=None
   else:
    a=(T-1)*max(0,R-.01);b=(T+1)*(R+.01);extra=(n-1)/n*(S+1)*(sR+.01)
    relax=(D+1>=(a-extra)/k) and (D-1<=(b+extra)/k)
   rec['scale_checks'][str(k)]=dict(Dminus_product=delta,limit=lim,point=None if lim is None else abs(delta)<=lim,plus_minus_1=relax)
  table.append(rec)
endpoints=[]
for c in native:
 if c['B200'] is None:continue
 endpoints.append(dict(material=c['material'],rpm=c['rpm'],native_C=c['C'],chamber=c['B200'],Bsd=c['Bsd'],implied=c['C']/c['B200'],resid_C_minus_pred={str(k):c['C']-k*c['B200'] for k in scales}))
last=[]
for k in scales:
 v=[r['scale_checks'][str(k)] for r in table]
 last.append(dict(scale=k,comparable=sum(t['point'] is not None for t in v),within_bound=sum(t['point'] is True for t in v),within_widened=sum(t['plus_minus_1'] is True for t in v),missing=sum(t['point'] is None for t in v),within_by_material={m:sum(r['scale_checks'][str(k)]['plus_minus_1'] is True for r in table if r['material']==m) for m in ('OMB','PBS')}))
groups=json.loads((P/'figure9.json').read_text())['groups']
x=np.array([g['vol'] for g in groups]);y=np.array([g['endpoint'] for g in groups]);m,k=np.polyfit(x,y,1)
f9=[]
for i,g in enumerate(groups):
 t=np.array(g['times']);fr=np.array(g['pct'])
 ce=crossing(t,fr,.5,100);j=np.flatnonzero(fr>=50)[0];mc,bc=np.polyfit(np.delete(x,i),np.delete(y,i),1)
 chamber_hi=(g['vol']/100*1410+(1-g['vol']/100)*55)*.05/2.05/.032
 f9.append(dict(vol=g['vol'],endpoint=g['endpoint'],reported_line_residual=g['endpoint']-(6*x[i]+53.6),loo_residual=g['endpoint']-(mc*x[i]+bc),crossing_linear=ce,crossing_monotone_bracket=[int(t[j-1]),int(t[j])],mean_T50=g['t50'],diff=ce-g['t50'],conditional_cap_chamber_nmol_ml=chamber_hi))
out=dict(curve_prediction=scores,source_D_E=table,comparison_summary=last,endpoint_check=endpoints,f9_ols_coef=[m,k],f9_residuals=f9,gas50=dict(assumed_gas_mg_L=705.,liquid_50pct_if55=27.5,conditional_combined_mg_L=732.5,gas_ug=.025*1.41*1000,expected_chamber_if_50pct_gas_and_all_dissolves_nmol_mL=705/1.312,highest_C_mg_L=float(bars[-1]['mean']),highest_C_apparent_fraction_of_total=float(bars[-1]['mean'])/732.5,highest_C_implied_recovered_ug=float(bars[-1]['mean'])*.05,highest_F8B_implied_recovered_ug=float(native[-1]['B200'])*2.05*.032))
save('reference.json',out)
print(json.dumps({k:out[k] for k in ['comparison_summary','endpoint_check','f9_ols_coef','curve_prediction','f9_residuals']},indent=2))
