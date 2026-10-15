from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,layout='constrained')
for folder,label,color in [(ROOT,'HB-FOLD1: query only','#bb5b30'),(HERE,'HB-FOLD2: MSA','#237ba3')]:
 rows=[r for r in csv.DictReader((folder/'fold_residuals.csv').open()) if r['reference']=='2DN1']
 axes[0].plot([int(r['mature_author_position']) for r in rows],[float(r['residual_A']) for r in rows],label=label,color=color,lw=1.6)
 scorefolder=ROOT/'fold_single_sequence' if folder==ROOT else HERE/'prediction'
 scores=json.loads(next(scorefolder.glob('*scores*.json')).read_text())['plddt']
 axes[1].plot(range(1,142),scores,color=color,lw=1.6)
axes[0].set(title='Human alpha-globin: controlled MSA comparison',ylabel='Aligned C-alpha residual (angstrom)')
axes[0].legend(frameon=False);axes[0].set_ylim(bottom=0)
axes[1].set(xlabel='Mature alpha-globin position (UniProt position minus 1)',ylabel='Predicted pLDDT',ylim=(0,100),xlim=(1,141))
for ax in axes:ax.grid(alpha=.2)
fig.savefig(HERE/'fold_comparison.png',dpi=150)
