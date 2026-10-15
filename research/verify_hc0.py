"""Independent arithmetic/analytic review of saved HC0 (does not import HC0)."""
from pathlib import Path
import csv, json, math, hashlib

p=Path(__file__).parent/'human_oxygen_carrier'
rows=list(csv.DictReader((p/'sensitivity.csv').open()))
saved=json.loads((p/'results.json').read_text())
worst=0.
for r in rows:
    u,d,h,n,c=[float(r[k]) for k in ['load_pressure_mmHg','unload_pressure_mmHg','P50_mmHg','hill_n','relative_capacity']]
    a,b,x=u**n,d**n,h**n
    # Algebraically independent of subtracting two logistic saturation values.
    diff=x*(a-b)/((a+x)*(b+x))
    worst=max(worst,abs(c*diff-float(r['normalized_equilibrium_content_difference'])))
optima=json.loads((p/'optima.json').read_text())
sign_checks=[]
for r in optima:
    u,d,n=r['load_pressure_mmHg'],r['unload_pressure_mmHg'],r['hill_n']
    a,b=u**n,d**n
    opt=math.sqrt(u*d)
    # d[unloading]/dx has sign(ab-x^2), x=P50^n.
    sign_checks.append((a*b-(.9*opt)**(2*n)>0) and (a*b-(1.1*opt)**(2*n)<0) and abs(opt-r['analytic_P50_mmHg'])<1e-12)
checks={
    'all_10368_saved_rows_independent_algebra': len(rows)==10368 and worst<1e-12,
    'all_36_optima_analytic_derivative_sign_change': len(optima)==36 and all(sign_checks),
    'table_hash_matches_report':hashlib.sha256((p/'sensitivity.csv').read_bytes()).hexdigest()==saved['csv_sha256'],
    'source_hash_matches_report':hashlib.sha256((p/'hc0.py').read_bytes()).hexdigest()==saved['source_sha256'],
}
out={'checks':checks,'maximum_absolute_content_error':worst,'passed':sum(checks.values()),'count':len(checks),'scope':'Independent algebra on every saved row and analytic optimum signs. Model assumptions are not empirically validated; not a clinical optimum or material ranking.'}
(p/'independent_verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
if not all(checks.values()):raise SystemExit(1)
