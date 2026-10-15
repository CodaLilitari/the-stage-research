"""Independent checks of saved PF0 results and an analytic dilute limit."""
import csv, hashlib, importlib.util, json, math
from pathlib import Path

root = Path(__file__).parent / 'artificial_blood'
spec = importlib.util.spec_from_file_location('pf0', root / 'pf0.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
rows = list(csv.DictReader((root / 'cases.csv').open()))
result = json.loads((root / 'results.json').read_text())
checks = {}
checks['source_matches_frozen_run'] = hashlib.sha256((root/'pf0.py').read_bytes()).hexdigest() == result['code_sha256']
checks['144_unique_cases'] = len(rows) == 144 and len({tuple(r[k] for k in ['depth_um','flow_uL_min','wall_permeability_mm_s','beta_hypothetical']) for r in rows}) == 144
checks['recount_threshold_outcomes'] = sum(float(r['minimum_free_tissue_mol_m3']) >= .05 for r in rows) == 55
checks['recount_beta_outcomes'] = {str(b):sum(float(r['minimum_free_tissue_mol_m3'])>=.05 for r in rows if float(r['beta_hypothetical'])==b) for b in [1.,4.,16.]} == {'1.0':16,'4.0':19,'16.0':20}
worst_balance = 0
for r in rows:
    q = float(r['flow_uL_min'])*1e-9/60
    delivered = q*float(r['beta_hypothetical'])*(.2-float(r['outlet_free_mol_m3']))
    uptake = float(r['uptake_mol_s'])
    worst_balance=max(worst_balance,abs(delivered-uptake)/max(abs(delivered),abs(uptake),1e-20))
checks['independent_unit_conversion_and_mass_balance'] = worst_balance < 1e-6

# Dilute MM tends to first-order uptake k*C. The continuous Robin/no-flux slab
# has C(x)=A*cosh(lambda*(L-x)), A=Cb/(cosh(lambda*L)+D*lambda/P*sinh(lambda*L)).
# No PF0 linear-system implementation is used for this reference calculation.
params=dict(m.CONFIG['source_parameters'])
cb, L, P = 1e-7, 200e-6, 50e-6
lam=math.sqrt(params['qmax_mol_m3_s']/params['Km_mol_m3']/params['D_m2_s'])
A=cb/(math.cosh(lam*L)+params['D_m2_s']*lam/P*math.sinh(lam*L))
dilute=[]
for n in [24,48,96]:
    actual=m.slab(cb,L,P,params,n)['c'][-1]
    reference=A*math.cosh(lam*L/(2*n))
    dilute.append({'cells':n,'actual':actual,'linear_analytic_cell_center':reference,'relative_error':abs(actual-reference)/reference})
checks['dilute_analytic_limit_refines'] = dilute[2]['relative_error'] < dilute[1]['relative_error'] < dilute[0]['relative_error']
checks['dilute_analytic_limit_within_0_1_percent'] = dilute[2]['relative_error'] < .001

# Four saved benchmark cases are re-executed, not the whole original run.
reruns=[]
for i in [0,35,73,143]:
    r=rows[i]
    a=m.simulate(float(r['depth_um'])*1e-6,float(r['flow_uL_min']),float(r['wall_permeability_mm_s'])*1e-3,float(r['beta_hypothetical']))
    difference=abs(a['minimum_free_tissue_mol_m3']-float(r['minimum_free_tissue_mol_m3']))
    reruns.append({'row':i,'absolute_difference':difference})
checks['four_saved_cases_reproduce'] = max(x['absolute_difference'] for x in reruns)<1e-12
out={'checks':checks,'passed':sum(checks.values()),'count':len(checks),'dilute_limit':dilute,'reruns':reruns,'worst_mass_balance':worst_balance,'scope':'Independent arithmetic, analytic limiting solution and subset reproducibility. Not validation against living tissue. PF0 original monotonicity failure remains a reported failure.'}
(root/'independent_verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
if not all(checks.values()): raise SystemExit(1)
