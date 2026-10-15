"""Summarize saved computations; no solver execution."""
from pathlib import Path
import csv,json,hashlib,shutil
ROOT=Path(__file__).resolve().parent
provider=ROOT/'returned'/'stage_skin';out=ROOT/'corrected'
rows=list(csv.DictReader((out/'cases.csv').open()))
original=list(csv.DictReader((provider/'pf1s_cases.csv').open()))
axes={}
for key in ['q_scenario','density_case','D_case','surface_case','wall_case','height_case']:
 groups={}
 for val in sorted(set(r[key] for r in rows)):
  rr=[r for r in rows if r[key]==val];groups[val]={'n':len(rr),'passes':sum(r['aligned_pass']=='True' for r in rr)}
 rates=[g['passes']/g['n'] for g in groups.values()]
 axes[key]={'groups':groups,'pass_rate_range':max(rates)-min(rates)}
manifest_checks=[]
for line in (provider/'MANIFEST.sha256').read_text().splitlines():
 expected,name=line.split(None,1);name=name.strip()
 actual=hashlib.sha256((provider/name).read_bytes()).hexdigest()
 manifest_checks.append({'file':name,'match':actual==expected})
assert all(v['match'] for v in manifest_checks)
# Public evidence already retrieved during this project: copy exact snapshots with provenance.
copies=[('research/muse_pf_data1/primary/article.html','stucker2002.html'),
        ('research/muse_pf_data1/primary/article_text.txt','stucker2002.txt'),
        ('research/grokbot_mechanics/sources/kawai_correction.html','kawai_correction.html'),
        ('research/grokbot_mechanics/sources/kawai_correction.txt','kawai_correction.txt')]
project=ROOT.parents[1];copied=[]
for src,dst in copies:
 p=project/src;d=ROOT/'sources'/dst;shutil.copyfile(p,d)
 copied.append({'source_project_path':src,'destination':str(d.relative_to(ROOT)),
  'sha256':hashlib.sha256(d.read_bytes()).hexdigest(),'method':'Exact copy of earlier same-project public-source retrieval; content re-inspected now.'})
(ROOT/'sources'/'copied_source_receipt.json').write_text(json.dumps(copied,indent=2))
summary={'aligned_axis_effects':axes,'provider_manifest':manifest_checks,
 'provider_thiele_squared_ranges':{k:[min(float(r[k]) for r in original),max(float(r[k]) for r in original)] for k in ['thiele_modulus_dermis','thiele_modulus_epidermis']},
 'note':'Marginal ranges depend on analyst grid; they are not importance measures over a biological population.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,(a,b)=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1.25,1]})
labels=['Bulk occlusion conversion\n0.0001 (scenario)','Assumed resting bulk\n0.003 (scenario)','Reported per-cell × ROI density\n0.00972 (scenario)']
nums=[243,243,216]
a.barh(range(3),nums,color=['#277da8','#519e84','#7b659f'])
for i,n in enumerate(nums):a.text(n+3,i,f'{n}/243',va='center',fontsize=10)
a.set_yticks(range(3),labels);a.invert_yaxis();a.set_xlim(0,290)
a.set_xlabel('Cases meeting assumed Cmin ≥ 0.05 mol/m³')
a.set_title('Corrected units, aligned layer interface',loc='left',fontsize=12)
r=json.loads((out/'results.json').read_text());change=r['mesh_classification_changes'][0]
fine=next(x for x in r['near_threshold_refinements'] if x['id']==change['id'])
vals=[change['original_min'],change['aligned_min'],fine['fine_min']]
b.plot(range(3),vals,'o-',color='#9b3d46',linewidth=2)
b.axhline(.05,color='#333333',ls='--');b.text(0.05,.0504,'Assumed classification line',fontsize=9)
for i,v in enumerate(vals):b.annotate(f'{v:.5f}',(i,v),xytext=(0,-17),textcoords='offset points',ha='center')
b.set_xticks(range(3),['Original\n36 × 54','Aligned\n36 × 100','Refined\n72 × 200'])
b.set_ylim(.0445,.052);b.set_ylabel('Minimum C (mol/m³)')
b.set_title('One classification changes with layer geometry',loc='left',fontsize=12)
for ax in (a,b):ax.spines[['top','right']].set_visible(False)
fig.suptitle('Cowork PF1-S audit: unit repair and layer-interface sensitivity',fontsize=14,y=.99)
fig.text(.02,.025,'Hypothetical reaction–diffusion screen; rates are not measured skin qmax. Counts are grid summaries, not probabilities.\nSame reviewed solver reused for replay and refinement; independent analytic check and separate local QA are distinguished.',fontsize=9)
fig.tight_layout(rect=[0,.12,1,.94]);fig.savefig(out/'audit_figure.png',dpi=180);plt.close(fig)
print(json.dumps(summary,indent=2))
