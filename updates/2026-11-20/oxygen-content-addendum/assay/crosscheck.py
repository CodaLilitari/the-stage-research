"""Cross-check vector coordinates with independently rasterized page and original Table 2."""
from collections import Counter
import json
from PIL import Image
import numpy as np
from extract import ROOT,NAMES,read

EXPECTED={
    (0,'total'):(9,.680,1.271),(0,'cellular'):(8,.040,.021),
    (1,'total'):(9,.590,1.181),(1,'cellular'):(9,-.018,0.),
    (2,'total'):(9,.625,1.215),(2,'cellular'):(9,.018,.034),
    (3,'total'):(9,.612,1.246)}
def main():
    rows,geo=read();rgb=np.array(Image.open(ROOT/'preview.png').convert('RGB'),int)
    h,w,_=rgb.shape;sx=w/595.276;sy=h/782.362
    dist=[];assert len(rows)==124
    for s in rows:
        cx,cy=s['svg_x']*sx,s['svg_y']*sy
        r=6;x=int(cx);y=int(cy);pix=rgb[y-r:y+r+1,x-r:x+r+1]
        rr,g,b=pix.transpose(2,0,1)
        match=(rr-np.maximum(g,b)>35) if s['condition']==10 else (b-rr>28)&(b-g>12)
        yy,xx=np.where(match);assert len(xx)>0,(s,cx,cy)
        d=((xx+x-r-cx)**2+(yy+y-r-cy)**2)**.5
        assert d.min()<6.1,(s,d.min())
        dist.append(d.min())
    t=[];coincidences=[]
    for (i,obs),(n,first,second) in EXPECTED.items():
        for cond,ref in [(5,first),(10,second)]:
            rr=[s for s in rows if s['instrument']==NAMES[i] and s['observable']==obs and s['condition']==cond]
            assert len(rr)==n
            tablediff=np.mean([s['delta_g_dl'] for s in rr])-ref
            assert abs(tablediff)<.0011
            t.append({'instrument':NAMES[i],'assay':obs,'condition':cond,'n':n,'mean_bias':ref+tablediff,'table2_bias':ref})
            unique=len({(round(s['svg_x'],1),round(s['svg_y'],1)) for s in rr});coincidences.append(n-unique)
    qa={'n_figure_markers':len(rows),'retained_coincident_markers_within_series':sum(coincidences),'all_same_hue_in_raster_radius_px':max(dist),'max_y_grid_residual_g_dl':max(v['y_max_resid'] for v in geo.values()),'table_replay':t}
    (ROOT/'extraction-qc.json').write_text(json.dumps(qa,indent=2))
    print({k:v for k,v in qa.items() if k!='table_replay'})
if __name__=='__main__':main()
