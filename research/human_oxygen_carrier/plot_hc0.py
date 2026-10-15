"""Post-run publication-layout revision using unchanged HC0 CSV data."""
from pathlib import Path
import csv,json,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/'freeze.json').read_text())['config']
with (ROOT/'sensitivity.csv').open(newline='') as handle:
    rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(handle)]
load,unload=cfg['plot_pair_mmHg'];optimum=math.sqrt(load*unload)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(13.6,6.2));fig.subplots_adjust(left=.075,right=.97,bottom=.22,top=.76,wspace=.28)
for n,col in zip(cfg['hill_coefficients'],['#6f8792','#c27834','#197a8c','#715f9b']):
    selected=[r for r in rows if r['load_pressure_mmHg']==load and r['unload_pressure_mmHg']==unload and r['hill_n']==n and r['relative_capacity']==1]
    axes[0].plot([r['P50_mmHg'] for r in selected],[r['delta_saturation'] for r in selected],label=f'Hill n = {n:g}',color=col,lw=2.2)
axes[0].axvline(optimum,color='#64747e',ls='--',lw=1.3)
axes[0].text(.03,.96,f'All curves peak at\nP50 = {optimum:.2f} mmHg',transform=axes[0].transAxes,va='top',fontsize=10)
axes[0].set(xlabel='Hypothetical P50 (mmHg)',ylabel='Equilibrium saturation difference',ylim=(0,1.02),xlim=(5,100),title='A   Higher affinity does not always increase release')
axes[0].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(frameon=False,loc='lower right',fontsize=10)
for cap,col in zip(cfg['relative_capacity_units'],['#6f8792','#197a8c','#c27834']):
    selected=[r for r in rows if r['load_pressure_mmHg']==load and r['unload_pressure_mmHg']==unload and r['hill_n']==cfg['plot_hill_coefficient'] and r['relative_capacity']==cap]
    axes[1].plot([r['P50_mmHg'] for r in selected],[r['normalized_equilibrium_content_difference'] for r in selected],label=f'Relative capacity {cap:g}',color=col,lw=2.2)
axes[1].set(xlabel='Hypothetical P50 (mmHg)',ylabel='Normalized equilibrium content difference',xlim=(5,100),ylim=(0,1.9),title='B   Capacity scales the content difference by assumption')
axes[1].legend(frameon=False,loc='upper right',fontsize=10)
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('HC0  |  Hypothetical oxygen binding and unloading',x=.075,ha='left',y=.96,fontsize=19,weight='bold')
fig.text(.075,.86,f'Illustrative fixed pressures: loading {load:g} mmHg, unloading {unload:g} mmHg.  Panel B uses hypothetical n = {cfg["plot_hill_coefficient"]:g}.',fontsize=11,color='#4f616d')
fig.text(.075,.075,'Equilibrium sensitivity only: not measured carrier performance, tissue delivery, a product ranking, or clinical guidance.\nAll parameter values are hypothetical; relative capacity has no conversion to a concentration or dose.',fontsize=10.5,color='#4f616d',linespacing=1.5)
fig.savefig(ROOT/'HC0_binding_unloading.png',dpi=200);fig.savefig(ROOT/'HC0_binding_unloading.pdf');plt.close(fig)
print('Publication figure regenerated from unchanged CSV data; frozen model source untouched.')
