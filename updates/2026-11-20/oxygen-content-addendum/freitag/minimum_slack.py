"""Local exact solution of the rounded pooled fixed-demand model; historical group means only."""
from fractions import Fraction as F
from pathlib import Path
import json,itertools
P=Path(__file__).resolve().parent
data=json.loads((P/'standl-means.json').read_text())['groups'];r=[]
for arm,rows in data.items():
 for j,row in enumerate(rows):
  q,a,v=[F(str(vals[0])) for vals in row];lo=(q-F(1,2))/100;hi=(q+F(1,2))/100;d=a-v
  r.append((arm+str(j),lo*(d-F(1,10)),lo,hi*(d+F(1,10)),hi))
# Every pair of lower/upper coefficient lines must overlap after the common vertical slack.
eps,left,right=max(((l0-h0)/(l1+h1),li,hi) for li,l0,l1,_,_ in r for hi,_,_,h0,h1 in r)
eps=max(F(0),eps)
lo=max(l0-l1*eps for _,l0,l1,_,_ in r);hi=min(h0+h1*eps for _,_,_,h0,h1 in r);assert lo==hi and lo>0
p=json.loads((P/'prediction-input.json').read_text());tr=json.loads((P/'score-only.json').read_text())
pred={q['id']:float(F(str(q['A']))-100*lo/F(str(q['Q']))) for q in p['query']}
e=[pred[q['id']]-tr[q['id']]['V'] for q in p['query'] if q['phase']!='baseline']
out=dict(exact_extra_V_mL_dL=str(eps),extra_V_mL_dL=float(eps),exact_U_mL_min=str(lo),U_mL_min=float(lo),binding_rows=[left,right],predictions=pred,post_baseline_RMSE=(sum(x*x for x in e)/len(e))**.5,post_baseline_MAE=sum(abs(x) for x in e)/len(e))
(P/'minimum-slack-check.json').write_text(json.dumps(out,indent=2));print(out)
