"""MECH1: analytic, assumption-driven channel/oxygen/pump screen. Not a tissue design."""
from pathlib import Path
import math,json,csv,hashlib,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
CONFIG={'L_m':.03,'Cin_mol_m3':.181,'floor_mol_m3':.052,'mu_Pa_s':.00078,'liquid_density_kg_m3':1000.,'pressure_limit_Pa':2000.,'shear_limit_Pa':2.,'hydraulic_power_limit_W':1e-4,'channel_volume_fraction_limit':.1,
 'diameters_um':[100,200,300,500],'central_counts':list(range(1,257)),
 'wall_permeabilities_m_s':[None,5e-5,2e-4],
 'central':{'tissue_mL':1.,'q_mol_m3_s':.0018,'D_m2_s':2.69e-9},
 'sensitivity':{'volumes_mL':[.1,1.],'q_mol_m3_s':[.0001,.0018,.012],'D_m2_s':[2e-9,2.69e-9],'mu_Pa_s':[.00078,.0012],'counts':[10,25,50,100,200]},
 'scope':'Uniform cylindrical tissue territories around identical parallel lumen channels; zero-order demand; no-flux territory perimeter, no external oxygen, fully developed laminar Newtonian flow, no extra plumbing losses. All thresholds and geometry are illustrative. Territories are an equal-volume approximation, not a tessellation of a physical finite block.'}
def finite(x,positive=False):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or (x<=0 if positive else x<0):raise ValueError('Expected finite '+('positive' if positive else 'nonnegative')+' scalar')
 return x
def evaluate(V_mL,q,D,mu,d_um,n,P=None):
 for x in [V_mL,D,mu,d_um]:finite(x,True)
 finite(q)
 if type(n) is not int or n<1:raise ValueError('positive integer channel count required')
 if P is not None:finite(P,True)
 c=CONFIG;L=c['L_m'];r=d_um*1e-6/2;V=V_mL*1e-6
 R=math.sqrt(r*r+V/(n*math.pi*L));demand=q*V
 radial=q/(4*D)*(2*R*R*math.log(R/r)-R*R+r*r)
 wall=0. if P is None else q*(R*R-r*r)/(2*r*P)
 margin=c['Cin_mol_m3']-c['floor_mol_m3']-radial-wall
 hydR=8*mu*L/(n*math.pi*r**4)
 caps={'pressure':c['pressure_limit_Pa']/hydR,'shear':c['shear_limit_Pa']*n*math.pi*r**3/(4*mu),'power':math.sqrt(c['hydraulic_power_limit_W']/hydR)}
 cap=min(caps.values());required=(demand/margin if margin>0 else None) if demand else 0.
 vch=n*math.pi*r*r*L;fraction=vch/(V+vch)
 packing=fraction<=c['channel_volume_fraction_limit']
 feasible=required is not None and required<=cap and packing
 # Oxygen output is valid only when the assumed zero-order domain remains physically meaningful.
 flow=required if required is not None else None
 dp=hydR*flow if flow is not None else None
 shear=4*mu*(flow/n)/(math.pi*r**3) if flow is not None else None
 power=hydR*flow*flow if flow is not None else None
 re=c['liquid_density_kg_m3']*(flow/(n*math.pi*r*r))*2*r/mu if flow is not None else None
 return {'V_tissue_mL':V_mL,'q_mol_m3_s':q,'D_m2_s':D,'mu_Pa_s':mu,'diameter_um':d_um,'n_channels':n,'wall_P_m_s':P,'territory_radius_um':R*1e6,'radial_drop_mol_m3':radial,'wall_drop_mol_m3':wall,'remaining_axial_drop_budget':margin,'Q_min_mL_min':None if flow is None else flow*6e7,'Q_max_mL_min':cap*6e7,'active_hydraulic_cap':min(caps,key=caps.get),'pressure_at_Qmin_Pa':dp,'shear_at_Qmin_Pa':shear,'hydraulic_power_at_Qmin_uW':None if power is None else power*1e6,'Re_at_Qmin':re,'channel_volume_mL':vch*1e6,'channel_fraction':fraction,'geometry_fraction_passes':packing,'feasible_under_assumptions':feasible}
def verify():
 checks={}
 a=evaluate(1,.0018,2.69e-9,.00078,200,100,None)
 checks['radial_independent_quadrature']=False
 r=1e-4;R=a['territory_radius_um']*1e-6;N=20000;dr=(R-r)/N
 integrated=sum(.0018/(2*2.69e-9)*(R*R/(r+(i+.5)*dr)-(r+(i+.5)*dr))*dr for i in range(N))
 checks['radial_independent_quadrature']=abs(integrated-a['radial_drop_mol_m3'])<1e-9
 checks['oxygen_budget_at_required_flow']=abs(.181-.0018*1e-6/(a['Q_min_mL_min']/6e7)-a['radial_drop_mol_m3']-.052)<1e-14
 checks['pressure_shear_identity']=abs(a['pressure_at_Qmin_Pa']*200e-6/(4*.03)-a['shear_at_Qmin_Pa'])<1e-12
 checks['zero_demand_requires_zero_flow']=evaluate(1,0,2e-9,.00078,200,10)['Q_min_mL_min']==0
 b=evaluate(1,.0018,2.69e-9,.00078,200,100,2e-4)
 checks['finite_wall_increases_required_flow']=b['Q_min_mL_min']>a['Q_min_mL_min']
 checks['weak_wall_impossible_even_infinite_flow']=evaluate(1,.0018,2.69e-9,.00078,200,10,1e-6)['Q_min_mL_min'] is None
 rejected=0
 for args in [(1,float('nan'),2e-9,.00078,200,10),(1,.0018,0,.00078,200,10),(1,.0018,2e-9,.00078,200,1.5),(1,.0018,2e-9,.00078,200,True),(1,-1,2e-9,.00078,200,10)]:
  try:evaluate(*args)
  except ValueError:rejected+=1
 checks['five_invalid_inputs_rejected']=rejected==5
 return checks
def run():
 freeze=json.loads((ROOT/'freeze.json').read_text());assert freeze['config']==CONFIG and freeze['screen_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 rows=[];c=CONFIG['central'];s=CONFIG['sensitivity']
 for p in CONFIG['wall_permeabilities_m_s']:
  for d in CONFIG['diameters_um']:
   for n in CONFIG['central_counts']:rows.append({'set':'central',**evaluate(c['tissue_mL'],c['q_mol_m3_s'],c['D_m2_s'],CONFIG['mu_Pa_s'],d,n,p)})
 import itertools
 for V,q,D,mu,d,n,p in itertools.product(s['volumes_mL'],s['q_mol_m3_s'],s['D_m2_s'],s['mu_Pa_s'],CONFIG['diameters_um'],s['counts'],CONFIG['wall_permeabilities_m_s']):rows.append({'set':'sensitivity',**evaluate(V,q,D,mu,d,n,p)})
 with (ROOT/'screen_cases.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 minima=[]
 for p,d in itertools.product(CONFIG['wall_permeabilities_m_s'],CONFIG['diameters_um']):
  part=[r for r in rows if r['set']=='central' and r['wall_P_m_s']==p and r['diameter_um']==d and r['feasible_under_assumptions']]
  minima.append({'P_m_s':p,'diameter_um':d,'first_feasible':min(part,key=lambda r:r['n_channels']) if part else None,'feasible_count':len(part)})
 # Original midcase has fixed 50% extraction; evaluate its territory oxygen separately.
 Q=.0018*1e-6/(.5*.181);mid=evaluate(1,.0018,2.69e-9,.00078,200,10,None)
 original={'Q_mL_min':Q*6e7,'pressure_Pa':128*.00078*.03*Q/(math.pi*(200e-6)**4*10),'shear_Pa':32*.00078*Q/(math.pi*(200e-6)**3*10),'radial_drop':mid['radial_drop_mol_m3'],'outlet_bulk_C':.181-.0018*1e-6/Q,'formal_minimum_C':.181-.0018*1e-6/Q-mid['radial_drop_mol_m3'],'interpretation':'A negative formal zero-order concentration indicates infeasibility of the assumed uniformly consuming tissue territory, not a physical prediction of negative oxygen.'}
 original['hydraulic_power_uW']=original['pressure_Pa']*Q*1e6
 original['electric_power_uW_scenarios']={str(e):original['hydraulic_power_uW']/e for e in [.1,.5]}
 out={'utc':datetime.now(timezone.utc).isoformat(),'central_rows':sum(r['set']=='central' for r in rows),'sensitivity_rows':sum(r['set']=='sensitivity' for r in rows),'minimum_feasible_channel_counts':minima,'original_midcase':original,'checks':verify(),'feasible_rows':sum(r['feasible_under_assumptions'] for r in rows),'maximum_Re_among_feasible':max(r['Re_at_Qmin'] for r in rows if r['feasible_under_assumptions']),'scope':CONFIG['scope']}
 (ROOT/'screen_results.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 print(json.dumps({'rows':len(rows),'checks':out['checks'],'original_midcase':original,'minimum_counts':[{'P':r['P_m_s'],'d':r['diameter_um'],'n':r['first_feasible']['n_channels'] if r['first_feasible'] else None} for r in minima]},indent=2))
if __name__=='__main__':
 if sys.argv[1:]==['--freeze']:
  p=ROOT/'freeze.json'
  if p.exists():raise SystemExit('Freeze exists')
  p.write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'config':CONFIG,'screen_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'original_code_sha256':hashlib.sha256((ROOT/'returned/stage-mech/calc/o2_perfusion.py').read_bytes()).hexdigest(),'status':'Local freeze after reading returned calculations and sources, before local replay or new screen; no biological fit'},indent=2)+'\n',encoding='utf-8')
 else:run()
