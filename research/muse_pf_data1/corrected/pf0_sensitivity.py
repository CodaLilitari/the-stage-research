"""Conditional PF0 sensitivity; literature volumetric demand does not identify MM qmax."""
from pathlib import Path
import itertools, hashlib, importlib.util, csv, json, time
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parent; BASE=ROOT.parent
CONFIG={
 'scenarios':[
  {'name':'low_as_saturating','qmax':1470/(60*24465),'interpretation':'lower literature demand at assumed 25C gas volume, treated as saturating qmax'},
  {'name':'high_as_saturating','qmax':2110/(60*22414),'interpretation':'upper literature demand at assumed 0C gas volume, treated as saturating qmax'},
  {'name':'high_at_inlet_reference','qmax':2110/(60*22414)*(0.2+0.028)/0.2,'interpretation':'upper demand at assumed 0C gas volume, matched to MM consumption at Cref=0.2 using retained illustrative Km=0.028'}],
 'grid':'Unchanged original 144 PF0 geometry/flow/wall/beta combinations per demand scenario',
 'retained_assumptions':'D=2e-9, Km=.028, inlet=.2, threshold=.05 and all geometry are uncalibrated for these subjects. Gas basis is not established by inspected primary source. No claim these endpoints bound real constructs.',
 'checks':'Conservation, boundedness, no-demand limit, equal Q*beta, demand ordering; eight prespecified high-demand low-wall corner refinements plus closest-threshold case per scenario. Classifications near threshold flagged.',
 'numerical_limits':{'mass_balance':1e-6,'refinement_difference_over_inlet':.01}}
def dump(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
 freeze=json.loads((BASE/'freeze.json').read_text()); assert freeze['pf0_sensitivity_config']==CONFIG
 for f in ['corrected/pf0_sensitivity.py','corrected/pf0_source.py']:
  assert hashlib.sha256((BASE/f).read_bytes()).hexdigest()==freeze['sha256'][f]
 spec=importlib.util.spec_from_file_location('pf0',ROOT/'pf0_source.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 start=time.perf_counter(); stamp=datetime.now(timezone.utc).isoformat(); rows=[]
 cases=list(itertools.product(m.CONFIG['analyst_selected_geometry']['slab_depths_m'],m.CONFIG['flows_uL_min'],m.CONFIG['wall_permeabilities_m_s'],m.CONFIG['capacity_multipliers']))
 for scenario in CONFIG['scenarios']:
  for case in cases: rows.append({'scenario':scenario['name'],'qmax_mol_m3_s':scenario['qmax'],**m.simulate(*case,qmax=scenario['qmax'])})
  print('completed',scenario['name'],len(cases),flush=True)
 with (ROOT/'pf0_cases.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 grouped={s['name']:[r for r in rows if r['scenario']==s['name']] for s in CONFIG['scenarios']}
 refinements=[]
 selected=[(CONFIG['scenarios'][-1],case) for case in itertools.product([.00005,.0004],[.5,32.],[.000005],[1.,16.])]
 for s in CONFIG['scenarios']:
  near=min(grouped[s['name']],key=lambda r:abs(r['minimum_free_tissue_mol_m3']-.05))
  selected.append((s,(near['depth_um']*1e-6,near['flow_uL_min'],near['wall_permeability_mm_s']*1e-3,near['beta_hypothetical'])))
 for s,case in selected:
  coarse=m.simulate(*case,qmax=s['qmax']);fine=m.simulate(*case,qmax=s['qmax'],tissue_cells=48,axial_segments=64)
  refinements.append({'scenario':s['name'],'case':case,'coarse_minimum':coarse['minimum_free_tissue_mol_m3'],'fine_minimum':fine['minimum_free_tissue_mol_m3'],'difference_over_inlet':abs(coarse['minimum_free_tissue_mol_m3']-fine['minimum_free_tissue_mol_m3'])/.2,'classification_agrees':coarse['all_cells_above_threshold']==fine['all_cells_above_threshold']})
 monotonic=[]
 for name,part in grouped.items():
  for axis in ['flow_uL_min','wall_permeability_mm_s','beta_hypothetical']:
   other=[k for k in ['depth_um','flow_uL_min','wall_permeability_mm_s','beta_hypothetical'] if k!=axis];groups={}
   for r in part:groups.setdefault(tuple(r[k] for k in other),[]).append((r[axis],r['minimum_free_tissue_mol_m3']))
   for key,vals in groups.items():
    vals.sort()
    if any(b[1]<a[1]-1e-9 for a,b in zip(vals,vals[1:])):monotonic.append({'scenario':name,'axis':axis,'group_fields':other,'group':key,'values':vals})
 zero=m.simulate(.0004,.5,.000005,1,qmax=0)
 equal_products=[]
 for part in grouped.values():
  for d,p in itertools.product([50.,100.,200.,400.],[.005,.05,.2]):
   a=next(r for r in part if r['depth_um']==d and r['wall_permeability_mm_s']==p and r['flow_uL_min']==2 and r['beta_hypothetical']==4)
   b=next(r for r in part if r['depth_um']==d and r['wall_permeability_mm_s']==p and r['flow_uL_min']==8 and r['beta_hypothetical']==1)
   equal_products.append(abs(a['minimum_free_tissue_mol_m3']-b['minimum_free_tissue_mol_m3']))
 checks={'all_mass_balances':max(r['relative_mass_balance_error'] for r in rows)<1e-6,'all_concentrations_bounded':all(0<=r['minimum_free_tissue_mol_m3']<=r['outlet_free_mol_m3']<=.2 for r in rows),'zero_demand_uniform':zero['minimum_free_tissue_mol_m3']==.2 and zero['uptake_mol_s']==0,'Q_times_beta_equivalence':max(equal_products)<1e-12,'demand_ordering':all(rows[i]['minimum_free_tissue_mol_m3']>=rows[i+144]['minimum_free_tissue_mol_m3']-1e-9>=rows[i+288]['minimum_free_tissue_mol_m3']-2e-9 for i in range(144)),'refinement_within_frozen_limit':max(r['difference_over_inlet'] for r in refinements)<.01,'refined_classifications_agree':all(r['classification_agrees'] for r in refinements),'passing_cases_obey_necessary_bounds':all(r['necessary_local_bound_passes'] and r['necessary_supply_bound_passes'] for r in rows if r['all_cells_above_threshold'])}
 result={'started_utc':stamp,'elapsed_seconds':time.perf_counter()-start,'cases':len(rows),'config':CONFIG,'checks':checks,'by_scenario':{name:{'above_threshold':sum(r['all_cells_above_threshold'] for r in part),'of':len(part),'above_by_beta_of_48':{str(b):sum(r['all_cells_above_threshold'] for r in part if r['beta_hypothetical']==b) for b in [1,4,16]},'400um_above_of_36':sum(r['all_cells_above_threshold'] for r in part if r['depth_um']==400),'minimum_free_range':[min(r['minimum_free_tissue_mol_m3'] for r in part),max(r['minimum_free_tissue_mol_m3'] for r in part)]} for name,part in grouped.items()},'maximum_relative_mass_balance_error':max(r['relative_mass_balance_error'] for r in rows),'refinements':refinements,'monotonicity_decreases':monotonic}
 dump('pf0_results.json',result); print(json.dumps(result,indent=2))
if __name__=='__main__':main()
