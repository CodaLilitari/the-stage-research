from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
with (ROOT/'screen_cases.csv').open() as f:rows=list(csv.DictReader(f))
central=[r for r in rows if r['set']=='central'];fig,axes=plt.subplots(1,2,figsize=(12,4.8))
colors=['#176b87','#c65f23','#25855b'];ps=['','5e-05','0.0002'];labels=['Ideal transfer','Wall P = 0.05 mm/s','Wall P = 0.2 mm/s']
for p,col,label in zip(ps,colors,labels):
 part=[r for r in central if r['diameter_um']=='200' and r['wall_P_m_s']==p and r['Q_min_mL_min']]
 axes[0].plot([int(r['n_channels']) for r in part],[float(r['Q_min_mL_min']) for r in part],color=col,label=label)
part=[r for r in central if r['diameter_um']=='200' and r['wall_P_m_s']=='']
axes[0].plot([int(r['n_channels']) for r in part],[float(r['Q_max_mL_min']) for r in part],ls='--',color='black',label='Pressure/shear/power flow cap')
axes[0].axvspan(118,150,color='grey',alpha=.15,label='Channel fraction > 10%')
axes[0].set(yscale='log',ylim=(.5,30),xlim=(1,150),xlabel='Number of 200 µm channels',ylabel='Total flow (mL/min)',title='Oxygen flow requirement versus hydraulic cap')
axes[0].legend(fontsize=8)
for d,col in zip(['100','200','300'],colors):
 part=[r for r in central if r['diameter_um']==d and r['wall_P_m_s']=='5e-05' and r['feasible_under_assumptions']=='True']
 axes[1].plot([int(r['n_channels']) for r in part],[float(r['hydraulic_power_at_Qmin_uW']) for r in part],color=col,label=f'Diameter {d} µm')
axes[1].set(yscale='log',xlabel='Number of channels',ylabel='Minimum fluid hydraulic power (µW)',title='Model-feasible layouts | wall P = 0.05 mm/s')
axes[1].legend(fontsize=8)
for a in axes:a.grid(alpha=.2)
fig.suptitle('MECH1 | coupled tissue-distance and pump tradeoff under declared assumptions',fontsize=12)
fig.text(.5,.015,'1 mL consuming tissue; 30 mm channels; q = 0.0018 mol/m³/s. No electrical overhead, manifolds, deformation or biological validation.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.055,1,.93]);fig.savefig(ROOT/'coupled_tradeoff.png',dpi=170)
result=json.loads((ROOT/'screen_results.json').read_text())
print(json.dumps([{'P':r['P_m_s'],'diameter':r['diameter_um'],'row':r['first_feasible']} for r in result['minimum_feasible_channel_counts'] if r['diameter_um']==200],indent=2))
