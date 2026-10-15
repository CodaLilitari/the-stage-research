"""Evaluate the one frozen public alpha-chain prediction against retained coordinates."""
from pathlib import Path
import csv,hashlib,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'biopython_runtime'))
import numpy as np
from Bio.PDB import PDBParser,MMCIFParser,Superimposer
from Bio.SeqUtils import seq1
sys.path.insert(1,str(ROOT))
from analyze_hemoglobin import kabsch
out=HERE/'prediction'
preds=list(out.glob('*unrelaxed*.pdb'));assert len(preds)==1
pred=PDBParser(QUIET=True).get_structure('prediction',preds[0])[0]['A']
sequence=(ROOT/'human_alpha_141.fasta').read_text().splitlines()[1]
assert ''.join(seq1(r.resname) for r in pred if r.id[0]==' ')==sequence
assert [r.id[1] for r in pred if r.id[0]==' ']==list(range(1,142))
uniprot=json.loads((ROOT/'raw/P69905.json').read_text())
assert uniprot['sequence']['value'][1:]==sequence
score=json.loads(next(out.glob('*scores*.json')).read_text())
assert len(score['plddt'])==141
rows=[];fits=[]
for pdb,chain in [('2DN1','A'),('2DN2','A'),('2DN2','C')]:
 ref=MMCIFParser(QUIET=True).get_structure(pdb,ROOT/'raw'/f'{pdb}.cif')[0][chain]
 ids=list(range(2,142)) # common mature-chain positions; oxy position 1 is unmodeled
 fixed=[];moving=[]
 for i in ids:
  assert ref[i].resname==pred[i].resname
  fixed.append(ref[i]['CA']);moving.append(pred[i]['CA'])
 sup=Superimposer();sup.set_atoms(fixed,moving)
 x=np.array([a.coord for a in moving],dtype=float);y=np.array([a.coord for a in fixed],dtype=float)
 assert abs(kabsch(x,y)-sup.rms)<1e-10
 r,t=sup.rotran;errors=np.linalg.norm(x@r+t-y,axis=1)
 fits.append({'reference':pdb,'chain':chain,'matched_CA':len(ids),'rmsd_A':sup.rms,'max_residual_A':float(errors.max())})
 for i,e in zip(ids,errors):rows.append({'reference':pdb,'chain':chain,'mature_author_position':i,'uniprot_position':i+1,'residue':sequence[i-1],'residual_A':float(e),'predicted_plddt':score['plddt'][i-1]})
result={'status':'HB-FOLD2 prediction executed; interpret coordinate and confidence measurements together',
 'sequence_mapping':'Prediction/PDB mature index i (1..141) = UniProt P69905 full-translation position i+1 (2..142). Initiator Met at UniProt1 absent from input. All fits use mature2..141 (140 CA) because 2DN1 mature1 is unmodeled.',
 'prediction_file':preds[0].name,'prediction_sha256':hashlib.sha256(preds[0].read_bytes()).hexdigest(),
 'plddt_mean':float(np.mean(score['plddt'])),'plddt_min':min(score['plddt']),'plddt_max':max(score['plddt']),
 'plddt_below_50_count':sum(v<50 for v in score['plddt']),'ptm_rounded_score_json':score['ptm'],
 'fits':fits,'checks':['141 predicted amino acids exactly match source input','Public P69905 mature-sequence mapping exact','All 420 evaluated residue identities match','Three Kabsch and Biopython RMSDs agree within 1e-10 A']}
(HERE/'fold_evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
with (HERE/'fold_residuals.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
baseline=json.loads((ROOT/'fold_evaluation.json').read_text())
freeze1=json.loads((ROOT/'fold_run_freeze.json').read_text());freeze2=json.loads((HERE/'fold_run_freeze.json').read_text())
changed=[i for i,(a,b) in enumerate(zip(freeze1['command'],freeze2['command'])) if a!=b]
assert changed==[1,2,4] and len(freeze1['command'])==len(freeze2['command'])
assert freeze1['environment_overrides']==freeze2['environment_overrides']
assert freeze1['input_sha256']==freeze2['input_sha256'] and freeze1['weight_sha256']==freeze2['weight_sha256']
manifest=json.loads((ROOT/'fold_manifest.json').read_text())
for item in manifest['files']:
 assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
ca=np.array([res['CA'].coord for res in pred],dtype=float)
steps=np.linalg.norm(np.diff(ca,axis=0),axis=1);assert np.isfinite(ca).all()
comparison={'fold1_mean_plddt':baseline['plddt_mean'],'fold2_mean_plddt':result['plddt_mean'],
 'fold1_ptm_rounded':baseline['ptm_rounded_score_json'],'fold2_ptm_rounded':result['ptm_rounded_score_json'],
 'rmsd_comparison':[{'reference':old['reference'],'chain':old['chain'],'matched_CA':old['matched_CA'],'fold1_rmsd_A':old['rmsd_A'],'fold2_rmsd_A':new['rmsd_A']} for old,new in zip(baseline['fits'],result['fits'])],
 'adjacent_CA_distance_min_A':float(steps.min()),'adjacent_CA_distance_max_A':float(steps.max()),
 'baseline_manifest_files_unchanged':len(manifest['files']),'changed_command_positions':changed,
 'setting_check':'Only input/output paths and MSA-mode value changed; model, seed, recycle, max-MSA, templates, relaxation, weights and environment match.',
 'comparison_limit':'One known target, one stochastic seed; max-MSA1:1 retained. No biological or novel-fold validation.'}
(HERE/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
print(json.dumps({'evaluation':result,'comparison':comparison},indent=2))
