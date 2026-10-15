"""Local QA and unit-corrected hypothetical sensitivity; not a skin prediction.

Imports the reviewed, unchanged returned solver. Thus this is a replay/refinement,
not an independent PDE implementation. Outputs stay outside preserved source.
"""
import csv, hashlib, importlib.util, itertools, json, sys, time
from dataclasses import asdict, replace
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'returned'/'stage_skin'/'pf1s_skin.py'
spec=importlib.util.spec_from_file_location('reviewed_pf1s', SOURCE)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
OUT=ROOT/'corrected';OUT.mkdir(exist_ok=True)
qcases={'bulk_occlusion_unit_corrected_scenario':1e-4,
        'assumed_resting_bulk_scenario':.003,
        'reported_per_cell_times_ROI_density_scenario':.00972}
freeze={'utc':datetime.now(timezone.utc).isoformat(),
 'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'audit_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'q_epi_scenarios_mol_m3_s':qcases,
 'all_other_axes':'unchanged provider 3 density x 3 D x 3 surface x 3 wall x 3 H',
 'mesh':'original 36x54 and aligned 36x(H/10um); h_epi=100um exactly on interface',
 'refinement':'six closest aligned cases to assumed .05 line, ties original order, doubled both axes',
 'scope':'Arithmetic scenarios only: observed/derived rates are not measured qmax; no clinical or wetlab inference',
 'timeout_internal_seconds':300}
(OUT/'freeze.json').write_text(json.dumps(freeze,indent=2))
t0=time.monotonic()
def checked(c):
 if time.monotonic()-t0>300:raise TimeoutError('bounded 300 second analysis')
 r=m.solve_case(c)
 if r is None or not r['converged'] or not np.isfinite(r['field']).all():raise RuntimeError('solve failed')
 return r
def loadcsv(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
original=loadcsv(SOURCE.parent/'pf1s_cases.csv')
replay=loadcsv(ROOT/'original_replay'/'pf1s_cases.csv')
assert len(original)==len(replay)==972
maximum={};mismatch=[]
for a,b in zip(original,replay):
 for k in a:
  try:
   e=abs(float(a[k])-float(b[k]));maximum[k]=max(maximum.get(k,0),e)
  except ValueError:
   if a[k]!=b[k]:mismatch.append([k,a[k],b[k]])
assert not mismatch
assert maximum['min_free_O2_mol_m3']<1e-10
assert sum(r['all_above_PF0_threshold']=='True' for r in original)==460
# Exact decimal unit accounting, retaining the article's unresolved discrepancy.
vol_L=D(200)*D('1e-12');cells=D(200)
bulk_mol_L_s=D('.1')*D('1e-6')
percell=bulk_mol_L_s*vol_L/cells
printed_percell=D('.035')*D('1e-6')/(D('1e6')*D(3600))
arithmetic={'source_units':'micromoles, not millimoles',
 'bulk_mol_m3_s':str(bulk_mol_L_s*D(1000)),
 'derived_mol_cell_s':str(percell),
 'derived_umol_per_million_cells_hour':str(percell*D('1e6')*D(3600)/D('1e-6')),
 'printed_mol_cell_s':str(printed_percell),
 'printed_over_derived':str(printed_percell/percell),
 'rhee_final_collagen_mg_ml_before_contraction':str(D(3)*D(90)/D(200)),
 'rhee_required_net_extra_inflow_ul_min_if_steady_liquid':str(D(12)-D(10)),
 'mm_slope_at_C005_over_slope_at_zero':float((D('.028')/(D('.028')+D('.05')))**2),
 'mm_fraction_qmax_at_C005':float(D('.05')/(D('.028')+D('.05')))}
records=[];cases=[]
axes=itertools.product(qcases.items(),m.RHEE_DENSITY_READINGS.items(),m.DERMAL_DIFFUSIVITY.items(),
 m.SURFACE_CONDUCTANCE.items(),m.WALL_PERMEABILITY.items(),m.CONSTRUCT_THICKNESS.items())
for i,((qk,q),(nk,n),(dk,d),(sk,s),(wk,w),(hk,h)) in enumerate(axes):
 c=m.Case(q_epi=q,q_derm=n*m.Q_CELL_HDF,D_derm=d,D_epi=1e-9,P_wall=w,P_surf=s,H=h,h_epi=1e-4,Km=.028)
 rr=checked(c);ca=replace(c,ny=round(h/1e-5));ra=checked(ca)
 rec={'id':i,'q_scenario':qk,'density_case':nk,'D_case':dk,'surface_case':sk,'wall_case':wk,'height_case':hk,**asdict(c),
 'original_min':rr['min_free_O2_mol_m3'],'aligned_min':ra['min_free_O2_mol_m3'],
 'original_pass':rr['all_above_PF0_threshold'],'aligned_pass':ra['all_above_PF0_threshold'],
 'aligned_ny':ca.ny,'original_epi_um':sum(m._layer_arrays(c)[3])*h/c.ny*1e6,
 'aligned_epi_um':sum(m._layer_arrays(ca)[3])*h/ca.ny*1e6,
 'aligned_mass_balance':ra['relative_mass_balance_error']}
 records.append(rec);cases.append(ca)
near=sorted(records,key=lambda r:abs(r['aligned_min']-.05))[:6]
refine=[]
for r in near:
 c=cases[r['id']];f=checked(replace(c,nx=c.nx*2,ny=c.ny*2))
 refine.append({'id':r['id'],'coarse_min':r['aligned_min'],'fine_min':f['min_free_O2_mol_m3'],
 'coarse_pass':r['aligned_pass'],'fine_pass':f['all_above_PF0_threshold'],
 'absolute_difference':abs(r['aligned_min']-f['min_free_O2_mol_m3']),
 'fine_mass_balance':f['relative_mass_balance_error']})
# Independent analytic zero-order 1D Robin slab minimum (finite wall resistance).
q=.002;d=2e-9;L=2e-4;p=5e-5;C=.2
ana=C-q*L/p-q*L*L/(2*d)
c=m.Case(q,q,d,d,p,0,.001,0,1e-10,Lx=L,nx=200,ny=8)
r=checked(c)
check={'analytic_min':ana,'solver_cell_center_min':r['min_free_O2_mol_m3'],
 'absolute_difference':abs(ana-r['min_free_O2_mol_m3']),
 'pass':abs(ana-r['min_free_O2_mol_m3'])<1e-6}
assert check['pass']
group={k:{'n':sum(r['q_scenario']==k for r in records),
 'original_pass':sum(r['q_scenario']==k and r['original_pass'] for r in records),
 'aligned_pass':sum(r['q_scenario']==k and r['aligned_pass'] for r in records)} for k in qcases}
changes=[r for r in records if r['original_pass']!=r['aligned_pass']]
result={'scope':freeze['scope'],'arithmetic':arithmetic,'provider_replay':{'n':972,'pass':460,'numeric_max_abs_differences':maximum,'categorical_mismatches':mismatch},
 'corrected_scenario_count':len(records),'group_counts':group,
 'original_mesh_passes':sum(r['original_pass'] for r in records),
 'aligned_mesh_passes':sum(r['aligned_pass'] for r in records),
 'max_mesh_min_difference':max(abs(r['aligned_min']-r['original_min']) for r in records),
 'max_aligned_mass_balance':max(r['aligned_mass_balance'] for r in records),
 'mesh_classification_changes':changes,'near_threshold_refinements':refine,
 'independent_analytic_robin_check':check,'seconds':time.monotonic()-t0}
with (OUT/'cases.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
(OUT/'results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['provider_replay','mesh_classification_changes']},indent=2))
