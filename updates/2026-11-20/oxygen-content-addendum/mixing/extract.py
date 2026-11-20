"""Kakiuchi and Borden 2025. Native JPEG graphical estimates. Integer pixels start upper left."""
from pathlib import Path
import csv,json
import numpy as np
from PIL import Image
from scipy.ndimage import label,find_objects
P=Path(__file__).parent
A=np.asarray(Image.open(P/'figure8.jpg')).astype(float)
def dump_csv(name,rows):
 with (P/name).open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]))
  writer.writeheader();writer.writerows(rows)
def val(y,y0,dist,maxval):
 if y is None:return None
 return round((y0-y)*maxval/dist,4)
def sd(yhi,ylo,center,scale):
 if yhi is not None and ylo is not None:return round((ylo-yhi)*scale/2,4)
 if yhi is not None:return round((center-yhi)*scale,4)
 if ylo is not None:return round((ylo-center)*scale,4)
 return None
curves=[]
pal={294:[248,64,64],445:[1,192,0],748:[0,0,254]}
for panel,origin in [('8A',293.2),('8B',1318.5)]:
 for rpm,clr in pal.items():
  for t in range(201):
   x=int(round(origin+t*(467.5/200)))
   strip=A[191:539,x-1:x+2]
   hits=np.sum((strip-np.array(clr))**2,-1)<45**2
   if panel=='8A':hits[:264]=False
   yy=np.where(hits.sum(1)>=1)[0]+191
   y=float(np.median(yy)) if len(yy) else None
   # A width <6px for green/blue often means a marginal sliver of an occluded mean stroke.
   status='resolved' if y is not None else 'occluded'
   if panel=='8A' and rpm!=294 and y is not None and len(yy)<6:status='visible edge; center unresolved';y=None
   if panel=='8A' and rpm!=294 and y is not None and t<4:status='near overlapping injection';y=None
   if panel=='8B' and t<3:status='near overlapping injection';y=None
   if t==200:status+='; at terminal line cap'
   lower=upper=None
   if y is not None and (panel=='8B' or (panel=='8A' and rpm==294)):
    r,g,b=strip.transpose(2,0,1)
    if rpm==294:colored=(r-g>17)&(r-b>17)
    elif rpm==445:colored=(g-r>16)&(g-b>16)
    else:colored=(b-r>17)&(b-g>17)
    segs=find_objects(label(colored.sum(1)>=2)[0])
    seg=next((s[0] for s in segs if s[0].start+191<=y+1 and s[0].stop+191>=y),None)
    if seg:
     top=seg.start+191;bottom=seg.stop-1+191
     if y-top>=5.5 and (panel!="8A" or yy[0]-top>=4):upper=val(top,538,467,400)
     if bottom-y>=5.5 and (panel!="8A" or bottom-yy[-1]>=4):lower=val(bottom,538,467,400)
   edge_low=edge_high=None
   if panel=='8A' and rpm!=294 and len(yy) and t>=30:
    # Only a sliver of core color appears. A near-horizontal stroke at this scale has
    # 10-12 pixels full width. Intersect all visible edge pixels +/- 6px; calibration
    # conditional on that measured stroke width. These are center bounds, not a mean or SD.
    center_low_y=yy[-1]-6;center_high_y=yy[0]+6
    if center_low_y<=center_high_y:
     edge_low=val(center_high_y,538,467,400);edge_high=val(center_low_y,538,467,400)
   curves.append(dict(panel=panel,rpm=rpm,t=t,x=x,y=y,mean=val(y,538,467,400),lower=lower,upper=upper,
                      visible_core_pixels=len(yy),edge_center_lower=edge_low,edge_center_upper=edge_high,status=status))
dump_csv('curves.csv',curves)
# Mean, upper cap and lower cap in native pixels. Some small caps hidden beneath symbols.
# 'estimated' means color center inferred from adjacent line or overlapping triangles. Empty caps remain missing.
D={
('OMB',294):[(1292, None,None),(1255,1228,1281),(1233,1204.5,1260.5),(1223.5,1190.5,1256.5)],
('OMB',445):[(1272,None,None),(1211.5,1192,None),(1142,1117.5,1166.5),(1119,1096,1141)],
('OMB',748):[(1242.5,None,None),(1080.5,1035,1126),(903.5,889.5,916),(874,860,887.5)],
('PBS',294):[(1250,1228,1272),(1240,None,None),(1230,None,None),(1226,None,None)],
('PBS',445):[(1244,1214,1274),(1231,None,None),(1226.5,None,None),(1227,None,None)],
('PBS',748):[(1268,None,None),(1241,None,None),(1230,None,None),(1229,None,None)]}
# OMB 5 s 748 marker center directly visible. Certain error-bar identities at 5 s masked by PBS.
E={
('OMB',294):[(1261,1239,1282),(1078,992,1164),(969,938.5,1000),(929,895,962)],
('OMB',445):[(1227,1219.5,1237),(1066,1042,None),(886.5,855,917.5),(824.5,None,848)],
('OMB',748):[(1226,1202,None),(1032,967,None),(816.5,None,842),(780,None,None)],
('PBS',294):[(1029,956.5,None),(899,846,950.5),(796,786,805.5),(790.5,781,800)],
('PBS',445):[(1061,984,None),(889,877.5,None),(795,None,None),(790,None,None)],
('PBS',748):[(1080, None,1127.5),(870,848.5,None),(792,None,None),(786,None,None)]}
de=[]
for panel,table,h in [('8D',D,300),('8E',E,100)]:
 for (mat,rpm),points in table.items():
  for time,(y,u,l) in zip((5,10,30,60),points):
   uncertain=mat=='PBS' or (time==5 and mat=='OMB' and rpm!=294) or (time==60 and panel=='8E' and rpm==748)
   de.append(dict(panel=panel,material=mat,rpm=rpm,t=time,y=y,cap_above=u,cap_below=l,mean=val(y,1301,526,h),sd=sd(u,l,y,h/526),marker='overlap or line-inferred' if uncertain else 'resolved',sd_source='both caps' if u and l else 'one cap' if (u or l) else 'unresolved'))
dump_csv('points-8DE.csv',de)
# 8C bars and individual dots. Individual PBS amplitudes can meet ink; one native pixel is 0.760 mg/L.
bar_meta={
('PBS',294):(1227.5,[1230.5,1225.5,1227.0],None,None),
('PBS',445):(1225.5,[1226.5,1224.5,1226.5,1225.5],None,None),
('PBS',748):(1228.5,[1231.5,1226.5,1228.5,1226.5],None,None),
('OMB',294):(1198.5,[1156,1183,1205,1246],1159.5,1236.5),
('OMB',445):(1104.5,[1080,1095,1112,1128],1083.5,1125.5),
('OMB',748):(878,[869,863,894,883],863.5,890.5)}
bars=[]
for (mat,rpm),(y,ys,u,l) in bar_meta.items():
 vals=[val(q,1301,526,400) for q in ys]
 bars.append(dict(material=mat,rpm=rpm,n=len(ys),y=y,mean=val(y,1301,526,400),sd=round(np.std(vals,ddof=1),3) if u is None else sd(u,l,y,400/526),sd_source='overlapping dot centroids' if u is None else 'whiskers',approx_dot_mean=round(np.mean(vals),3),approx_dot_sd=round(np.std(vals,ddof=1),3),dot_values=json.dumps(vals)))
dump_csv('bars-8C.csv',bars)
# 9B groups: source plots first marker at x=823 (about 1 second) instead of baseline tick x=814.
# At t=5 the red center falls behind blue; adjacent red segment gives y~541.
# At 30 and 60s high markers partly hidden; nearby straight colored segments or visible white circle.
G={0:[(435,371.5,None),(196,171.5,219.5),(126.5,None,None),(119,None,None)],25:[(502,None,None),(210,None,None),(117,None,None),(113,None,None)],50:[(553.5,529.5,578),(285,265,305),(118,None,None),(111,None,None)],60:[(542,None,604),(320,None,424.5),(144.5,None,182.5),(114,None,None)]}
ac9={0:((602.5,None,None),(417.5,391,444)),25:((436.5,415.5,457.5),(368.5,343,393.5)),50:((289.5,272.5,306.5),(317,289.5,345.5)),60:((191.5,168.5,214.5),(276,183,368.5))}
groups=[]
for vol,pts in G.items():
 (a,au,al),(c,cu,cl)=ac9[vol]
 groups.append(dict(vol=vol,endpoint=val(a,664.5,554.5,500),endpoint_sd=sd(au,al,a,500/554.5),t50=val(c,663.5,553.5,12),t50_sd=sd(cu,cl,c,12/553.5),times=[1,5,10,30,60],pct=[0]+[val(y,664.5,554.5,100) for y,*_ in pts],pct_sd=[None]+[sd(u,l,y,100/554.5) for y,u,l in pts]))
(P/'figure9.json').write_text(json.dumps({'groups':groups},indent=2))
print('Bar endpoint vs digitized replicates',[(b['material'],b['rpm'],round(b['mean']-b['approx_dot_mean'],2)) for b in bars])
for p in ('8A','8B'):
 for rpm in pal:
  rr=[c for c in curves if c['panel']==p and c['rpm']==rpm and c['mean'] is not None]
  print(p,rpm,len(rr),'last 4',[(r['t'],r['mean'],r['lower'],r['upper']) for r in rr[-4:]])
