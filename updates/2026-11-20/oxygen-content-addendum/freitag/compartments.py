"""Source-internal checks after outcome release. No forecast is altered."""
import json,re
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
pages=(P/'source-layout.txt').read_text(encoding='utf8').split('\f')
def tab(p,start,end=None):
 h=pages[p].split(start)[1]
 if end:h=h.split(end)[0]
 rows=[]
 for ln in h.splitlines():
  if re.match(r'^\s*(Baseline|20 min|60 min|100 min)\s{2,}',ln):rows.append([[float(i),float(j)] for i,j in re.findall(r'(-?\d+(?:\.\d+)?)\s*±\s*(-?\d+(?:\.\d+)?)',ln)])
 return rows[:8]
II=tab(2,'TABLE II Parameters');III=tab(4,'TABLE III Parameters','TABLE IV Parameter');IV=tab(4,'TABLE IV Parameter')
rows=[]
for i,(a,b,c) in enumerate(zip(II,III,IV)):
 A,pul=a[3][0],a[4][0];port,cav,av=b[0][0],b[1][0],b[2][0];V,delta=c[0][0],c[1][0]
 H=(A+2*port)/3
 rows.append(dict(idx=i,weighted_input=H,published_hepatic_av=av,portal_cava_residual=H-cav-av,portal_pulmonary_residual=H-pul-av,reconstructed_arterial_if_cava=3*(av+cav)-2*port,reconstructed_arterial_if_muscle=V+delta,printed_A=A))
def summ(name):return max(abs(r[name]) for j,r in enumerate(rows) if j!=4)
out=dict(rows=rows,seven_max_residual_caval=summ('portal_cava_residual'),seven_max_residual_pulmonary=summ('portal_pulmonary_residual'),mixed_mean_residual_caval=float(np.mean([abs(r['portal_cava_residual']) for r in rows])),mixed_mean_residual_pulmonary=float(np.mean([abs(r['portal_pulmonary_residual']) for r in rows])))
(P/'compartment-qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
