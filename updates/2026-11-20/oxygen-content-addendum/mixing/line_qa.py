"""Use intervening line pixels independently of 8D/E marker centers. Drop superposed same-color paths."""
import csv,json
from pathlib import Path
import numpy as np
from PIL import Image
p=Path(__file__).parent
a=np.array(Image.open(p/'figure8.jpg'),dtype=int);r,g,b=a.transpose(2,0,1)
masks={294:(r-g>25)&(r-b>25),445:(g-r>25)&(g-b>25),748:(b-r>30)&(b-g>30)}
data=list(csv.DictReader((p/'points-8DE.csv').open()))
out=[]
for panel,x0 in [('8D',815),('8E',1499.5)]:
 for rpm,m in masks.items():
  coords={mat:np.array([float(r['y']) for r in data if r['panel']==panel and r['material']==mat and int(r['rpm'])==rpm]) for mat in ('PBS','OMB')}
  xx=np.array([5,10,30,60])*526/60+x0
  for mat in coords:
   yy=coords[mat];other=coords['PBS' if mat=='OMB' else 'OMB']
   for t0,(x,z,y,v) in enumerate(zip(xx,xx[1:],yy,yy[1:])):
    X=[];Y=[]
    for u in range(round(x)+10,round(z)-10):
     q=(u-x)/(z-x);target=y*(1-q)+v*q;alt=other[t0]*(1-q)+other[t0+1]*q
     if abs(target-alt)<6:continue
     yr=np.arange(int(target)-11,int(target)+13);ys=yr[m[yr,u]]
     if len(ys)==0 or len(ys)>8:continue
     X.append(u);Y.append(np.median(ys))
    if len(X)<8 or max(X)-min(X)<.26*(z-x):continue
    # Remove adjacent-component contamination and repeat standard line fit.
    X=np.asarray(X);Y=np.asarray(Y);sel=np.ones(len(X),dtype=bool)
    for k in range(3):
     coef=np.polyfit(X[sel]-x,Y[sel],1);res=Y-np.polyval(coef,X-x);sel=np.abs(res-np.median(res[sel]))<max(1.2,3*np.median(np.abs(res[sel]-np.median(res[sel]))))
    est=coef[1],np.polyval(coef,z-x)
    out.append(dict(panel=panel,rpm=rpm,material=mat,span=[(5,10,30)[t0],(10,30,60)[t0]],pixels=int(sel.sum()),fraction=float((max(X[sel])-min(X[sel]))/(z-x)),native_delta_px=[round(est[0]-y,2),round(est[1]-v,2)]))
(p/'line-qa.json').write_text(json.dumps(out,indent=2))
for row in out:print(row)
