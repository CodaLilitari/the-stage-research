from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
rows=list(csv.DictReader((ROOT/'sweep.csv').open()));result=json.loads((ROOT/'results.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
for key,label,color in [('constant_relaxation','Constant relaxation rates','#237ba3'),('hypothetical_p50_dependent_unloading','Hypothetical unloading-rate scaling','#bb5b30')]:
 data=[r for r in rows if r['case']==key];p=[float(r['p50']) for r in data]
 axes[0].plot(p,[float(r['q_per_volume']) for r in data],label=label,color=color)
 axes[1].plot(p,[float(r['kinetic_factor']) for r in data],label=label,color=color)
for ax in axes:
 ax.axvline(result['optima']['equilibrium_analytic'],ls=':',color='gray',label='Equilibrium optimum')
 ax.set_xlabel('P50 (hypothetical mmHg)');ax.grid(alpha=.2)
axes[0].set_ylabel('Bound oxygen exchanged (mol / m³ carrier / cycle)')
axes[1].set_ylabel('Kinetic attenuation factor');axes[1].set_ylim(0,1)
axes[0].legend(frameon=False,fontsize=8)
fig.suptitle('OK0: finite-contact toy model — hypothetical parameters, no biological fit',fontsize=12)
fig.savefig(ROOT/'OK0_kinetic_comparison.png',dpi=150)
