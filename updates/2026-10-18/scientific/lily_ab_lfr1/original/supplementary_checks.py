"""Post-first-run flux audit and portable reference export on SAME frozen cases.
No changes to cases, tolerances, physical model or original acceptance criteria.
"""
from pathlib import Path
import csv,json,datetime,hashlib,unittest,math
import mpmath as mp
from benchmark import exact_state,exact_fluxes
r=Path(__file__).resolve().parent
cfg=json.loads((r/'FROZEN_CASES.json').read_text())
rows=[];fails=[]
for case in cfg['cases']:
 for fraction in cfg['time_fractions']:
  with mp.workdps(90):
   a,k,g,T,c0=map(mp.mpf,[case['alpha_s_inv'],case['k_s_inv'],case['gamma'],case['T_s'],case['c0_mol_m3']])
   t=T*mp.mpf(fraction)
   M=mp.matrix([[-a-k*g,k],[k*g,-k]])
   z=mp.expm(M*t)*mp.matrix([c0,g*c0])
   sr=a*z[0];rr=k*(z[1]-g*z[0])
   af,kf,gf,tf,cf=map(float,[a,k,g,t,c0])
   sink,release=exact_fluxes(af,kf,gf,tf,cf)
   c,b=exact_state(af,kf,gf,tf,cf)
   scale=float(a*c0) or 1.
   ratio=max(abs(sink-float(sr))/(2e-13*scale+3e-12*abs(float(sr))),abs(release-float(rr))/(2e-13*scale+3e-12*abs(float(rr))))
   direct=kf*(b-gf*c)
   row=dict(case_id=case['id'],fraction=fraction,t_s=float(t),c_ref=float(z[0]),b_ref=float(z[1]),sink_ref=float(sr),release_ref=float(rr),sink=sink,release=release,direct_release=direct,direct_release_abs_error=abs(direct-float(rr)),max_tolerance_ratio=ratio,passed=ratio<=1)
   rows.append(row)
   if ratio>1:fails.append(row)
out=r/'supplementary';out.mkdir(exist_ok=False)
(out/'flux_checks.json').write_text(json.dumps({'status':'post-first-run numerical flux audit on unchanged frozen fixtures','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'count':len(rows),'passed':len(rows)-len(fails),'failures':fails,'max_tolerance_ratio':max(q['max_tolerance_ratio'] for q in rows),'max_direct_subtraction_abs_error':max(q['direct_release_abs_error'] for q in rows),'rows':rows},indent=2)+'\n')
# Golden file contains high-precision references rounded to binary64, not exact-real certificates.
(r/'GOLDEN_STATES.json').write_text(json.dumps({'source':'mpmath 1.3.0 augmented matrix reference in run 001; states/rates here reevaluated via 2x2 expm at 90 dps and rounded to binary64','frozen_cases_sha256':hashlib.sha256((r/'FROZEN_CASES.json').read_bytes()).hexdigest(),'rows':[{k:v for k,v in row.items() if k in ['case_id','fraction','t_s','c_ref','b_ref','sink_ref','release_ref']} for row in rows]},indent=2)+'\n')
print(json.dumps({k:v for k,v in json.loads((out/'flux_checks.json').read_text()).items() if k!='rows'},indent=2))
raise SystemExit(bool(fails))
