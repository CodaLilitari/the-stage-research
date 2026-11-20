"""Read the original marker geometry of Fig 1; retain coincident painted markers."""
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import defaultdict
import csv,hashlib,re
import numpy as np

ROOT=Path(__file__).resolve().parent
NAMES=('Sysmex XN-20','Siemens Advia 2120i','Abbott Alinity Hq','Abbott Cell Dyn Sapphire')
HASH='0b373848cfe9ffef84bce62cdc89f828cc85a65d13faa1733501c89744b4cf9f'
def parts(x):
    return [float(s) for s in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',x)]
def read():
    assert hashlib.sha256((ROOT/'paper.pdf').read_bytes()).hexdigest()==HASH
    geo=defaultdict(list);markers=[]
    for path in ET.parse(ROOT/'plot.svg').getroot().iter():
        color=path.get('stroke','')
        if not color.startswith(('rgb(21.','rgb(75.','rgb(90.','rgb(68.')):continue
        d=path.get('d');cmd=''.join(re.findall('[MLCZ]',d));a,b,c,f,dx,dy=parts(path.get('transform'))
        assert b==c==0
        xy=np.asarray(parts(d)).reshape(-1,2)*[a,f]+[dx,dy]
        lo=xy.min(axis=0);hi=xy.max(axis=0);x,y=(lo+hi)/2
        # The four plot rectangles are separated by broad white gutters.
        if not (80<x<540 and (75<y<260 or 305<y<492)):continue
        panel=int(x>310)+2*int(y>290)
        if color.startswith(('rgb(90.','rgb(68.')):
            if cmd=='ML':geo[panel].append((x,y,hi[0]-lo[0],hi[1]-lo[1],color[:7]))
            continue
        if cmd not in ('MCCCCZM','MLLLZM','MLLZM'):continue
        if hi[0]-lo[0]<3 or hi[0]-lo[0]>9:continue
        concentration=5 if color.startswith('rgb(21.') else 10
        obs=('total' if (concentration==10 and cmd=='MCCCCZM') or (concentration==5 and cmd=='MLLLZM') else 'cellular')
        markers.append((panel,obs,concentration,x,y))
    rows=[];qc={}
    for panel,name in enumerate(NAMES):
        geom=geo[panel]
        x_marks=sorted(v[0] for v in geom if v[2]<.1 and v[3]>110)
        y_marks=sorted(v[1] for v in geom if v[2]>110 and v[3]<.1)
        assert len(x_marks) in (3,4)
        xfit=np.polyfit(x_marks,[2,3,4,5][-len(x_marks):],1)
        y_zero=[v[1] for v in geom if v[2]>110 and v[3]<.1 and v[4]=='rgb(68.']
        assert len(y_zero)==1
        y0=y_zero[0]
        yu=[round((y0-y)/16.66)*.2 for y in y_marks]
        yfit=np.polyfit(y_marks,yu,1)
        griderr=max(abs(np.polyval(yfit,y_marks)-yu))
        assert griderr<.005 and 3<=len(y_marks)<=12
        qc[name]={'x_ticks':x_marks,'y_ticks':y_marks,'y_tick_values':yu,'y_max_resid':griderr}
        for i,(p,obs,conc,x,y) in enumerate(markers):
            if p==panel:rows.append(dict(instrument=name,observable=obs,condition=conc,control_g_dl=round(float(np.polyval(xfit,x)),5),delta_g_dl=round(float(np.polyval(yfit,y)),5),svg_x=round(x,4),svg_y=round(y,4)))
    return rows,qc
if __name__=='__main__':
    import json
    rows,qc=read()
    with (ROOT/'points.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (ROOT/'axis-qc.json').write_text(json.dumps(qc,indent=2))
    for name in NAMES:
        for obs in ['total','cellular']:
            for conc in [5,10]:
                rr=[r for r in rows if (r['instrument'],r['observable'],r['condition'])==(name,obs,conc)]
                if rr:print(name,obs,conc,len(rr),round(np.mean([r['delta_g_dl'] for r in rr]),4),round(min(r['control_g_dl'] for r in rr),3),round(max(r['control_g_dl'] for r in rr),3))
