"""Real figure internal consistency and a synthetic shared-filter ambiguity."""
import csv,json
from pathlib import Path
import numpy as np
P=Path(__file__).parent
r=list(csv.DictReader((P/'curves.csv').open()));s=json.loads((P/'summary.json').read_text())['cells']
contr=[]
for c in s:
 for q in c['points']:
  panel='8B' if c['material']=='OMB' else '8A';raw=next(v for v in r if v['panel']==panel and int(v['rpm'])==c['rpm'] and int(v['t'])==q['t'])
  if raw['mean'] is None or raw['mean']=='':continue
  contr.append(dict(material=c['material'],rpm=c['rpm'],t=q['t'],D_minus_trace=q['D']-float(raw['mean'])))
ref=json.loads((P/'reference.json').read_text())
common={};tight={}
for item in ref['source_D_E']:
 if item['scale_checks']['1.0']['limit'] is None:continue
 c=next(c for c in s if c['material']==item['material'] and c['rpm']==item['rpm'])
 q=next(t for t in c['points'] if t['t']==item['t']);m=c['C'];R=q['E']/100
 D=q['D'];E=q['Esd']/100;g=(c['n']-1)/c['n'];u=g*c['Csd']*E
 def interval(w):
  cov=g*(c['Csd']+w)*(E+w/100)
  return [(max(0,m-w)*max(0,R-w/100)-cov)/(D+w),((m+w)*(R+w/100)+cov)/(D-w) if D>w else np.inf]
 key=(c['material'],c['rpm'],q['t']); common[str(key)]=interval(1);tight[str(key)]=interval(0)
def intersect(rows,tag):return [max(v[0] for k,v in rows.items() if tag in k),min(v[1] for k,v in rows.items() if tag in k)]
# Construct a shared-filter relabeling. Mean sensor response lag vs material lag changes.
A=np.array([.6,.4]);B=np.array([.2,.3,.5]);buffer=np.array([.75,.25])
mats=[np.array([.1,.2,.3,.4]),np.array([.7,.2,.1])]
e=[]
for old_source in [buffer]+mats:
 old=np.convolve(np.convolve(A,B),old_source);new=np.convolve(A,np.convolve(B,old_source));e.append(max(abs(old-new)))
t=np.arange(len(B));assert max(e)<3e-16
k=(445-294)/(748-294);amp0=s[3]['B200'];amp1=s[5]['B200'];interp=amp0+(amp1-amp0)*k;curved=amp0+(amp1-amp0)*k**2
summary=dict(DminusTrace=contr,OMB_max_time5=max(abs(q['D_minus_trace']) for q in contr if q['material']=='OMB' and q['t']==5),OMB_max_time10_30_60=max(abs(q['D_minus_trace']) for q in contr if q['material']=='OMB' and q['t']>=10),C_covariance_1unit_all_intersection=intersect(common,''),C_covariance_1unit_OMB_intersection=intersect(common,'OMB'),necessary_factor_by_point=common,point_factors_no_widening=tight,negative_width_means_empty=True,matched_composite=dict(max_absolute_identity_error=max(e),equipment_mean_lag_old_samples=float(np.dot(np.arange(4),np.convolve(A,B))),equipment_mean_lag_new_samples=float(A[1]),released_mean_lag_shift=float(np.dot(t,B))),speed_law_witness=dict(rpm_linear_endpoint=interp,rpm_squared_fraction_endpoint=curved,interior_difference=interp-curved))
(P/'additional-checks.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k not in ['DminusTrace','necessary_factor_by_point','point_factors_no_widening']},indent=2))
