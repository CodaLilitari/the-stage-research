"""Export convergence figure/data from frozen saved results only; no solver import."""
from pathlib import Path
import csv,hashlib,json,os
HERE=Path(__file__).resolve().parent
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR']=str(OUT/'mpl_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter

convergence=json.loads((HERE/'run/convergence.json').read_text())
series={x['name']:x for x in convergence['checks']}
rows=[]
for name,x in series.items():
    radial=name.startswith('RAD_');grid=[8,16,32,64] if radial else [32,64,128]
    for n,error in zip(grid,x['errors']):
        rows.append(dict(series=name,grid_cells=n,relative_mesh_width=1/n,normalized_error=error,last_observed_order=x['last_order']))
with (OUT/'convergence_data.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'legend.fontsize':9,'svg.fonttype':'none','pdf.fonttype':42})
fig,axs=plt.subplots(1,2,figsize=(11.5,5.7))
fig.subplots_adjust(left=.085,right=.975,bottom=.30,top=.78,wspace=.30)
fig.suptitle('AB-LA1: verification of production transport stepping',x=.085,y=.95,ha='left',fontsize=17,fontweight='bold')
fig.text(.085,.885,'Saved results only  |  47 positive attempts accepted  |  4 deliberate faults detected',fontsize=10,color='#405265')
colors=['#126782','#dd7b25','#794a97']
for group,label,color,marker in zip(['L00','L03','COUPLED'],['Dissolved, imposed flux','Finite release, imposed flux','Finite release, actual slab'],colors,['o','s','^']):
    item=series[group+':axial_convergence']
    axs[0].loglog([1/32,1/64,1/128],item['errors'],marker=marker,color=color,lw=1.8,label=label)
axs[0].set_title('Axial stepping: approximately first order',loc='left',pad=12)
axs[0].set_xlabel('Relative segment width, delta z / L')
axs[0].set_ylabel('Scaled endpoint state error')
axs[0].set_xticks([1/128,1/64,1/32],['1/128','1/64','1/32'])
axs[0].legend(loc='upper left',frameon=False)
for group,label,color in [('RAD_low','P = 5e-6 m/s','#126782'),('RAD_high','P = 2e-4 m/s','#dd7b25')]:
    for key,style,marker in [('G_relative_error','-','o'),('field_scaled_error','--','s')]:
        axs[1].loglog([1/8,1/16,1/32,1/64],series[group+':'+key]['errors'],style,marker=marker,lw=1.8,color=color,label=label if key=='G_relative_error' else '_nolegend_')
axs[1].set_title('Actual radial slab: approximately second order',loc='left',pad=12)
axs[1].set_xlabel('Relative cell width, delta y / d')
axs[1].set_ylabel('Normalized continuum error')
axs[1].set_xticks([1/64,1/32,1/16,1/8],['1/64','1/32','1/16','1/8'])
axs[1].legend(loc='upper left',frameon=False)
for ax in axs:
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.grid(True,which='major',alpha=.24);ax.grid(True,which='minor',alpha=.08)
    ax.spines[['top','right']].set_visible(False)
fig.text(.085,.12,'Axial: max(|c - exact| / c_in, |b - exact| / max(c_in, gamma c_in)).\nActual-slab axial reference uses its separately checked discrete conductance G_n.',fontsize=9,color='#405265')
fig.text(.56,.12,'Radial solid: |G_n / G_continuum - 1|.\nRadial dashed: max cell-centre |c - c_continuum| / c_in.',fontsize=9,color='#405265')
fig.text(.085,.055,'Hypothetical linear verification only. Imposed-flux arrays are not tissue fields. Local checks; no biological validation.',fontsize=9,color='#405265')
for suffix in ('png','svg','pdf'):
    fig.savefig(OUT/('AB_LA1_convergence.'+suffix),dpi=200,facecolor='white')
plt.close(fig)
source=HERE/'run/convergence.json'
receipt=dict(source_path='run/convergence.json',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
  all_series_in_csv=list(series),displayed_axial_series=['L00','L03','COUPLED'],
  selection='Representative dissolved/imposed-finite/real-slab finite traces for display; all prespecified convergence groups remain in CSV and run/convergence.json.',
  normalization='Dimensionless errors, no confidence intervals; mesh widths are 1/nz and 1/ny.',
  outputs=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(OUT.glob('*')) if p.is_file() and p.suffix in ('.png','.svg','.pdf','.csv')])
(OUT/'figure_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
