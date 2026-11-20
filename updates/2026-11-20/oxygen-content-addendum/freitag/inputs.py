"""Display and save only the independent test features, never response columns."""
from pathlib import Path
import json,re
P=Path(__file__).parent
pages=(P/'source-layout.txt').read_text(encoding='utf-8').split('\f')
runs={}
for table,body,col in [('II',pages[2].split('TABLE II Parameters')[1],3),('IV',pages[4].split('TABLE IV Parameter')[1],2)]:
 current=None;parts=[]
 for line in body.splitlines():
  t=line.strip()
  if t=='Group 1' or t=='Group 2':current=t[-1];continue
  pairs=re.findall(r'(-?\d+(?:\.\d+)?)\s*±\s*(-?\d+(?:\.\d+)?)',t)
  if current and len(pairs)>=col+1:
   name=t[:re.search(r'\d+(?:\.\d+)?\s*±',t).start()].strip()
   if name.startswith(('Baseline','Control','Hemo','IHD','HBOC','IHD','Time','Post','Ringer','60','Measurement')) or len(name)<35:
    parts.append((current,name,*map(float,pairs[col])))
  if len(parts)>=6 and (t.startswith(('CvO','Hct ','HR ','Flow-popl','CI ','CaO'))):break
 runs[table]=parts
print(json.dumps(runs,indent=2))
(P/'covariates-only.json').write_text(json.dumps(runs,indent=2),encoding='utf8')
