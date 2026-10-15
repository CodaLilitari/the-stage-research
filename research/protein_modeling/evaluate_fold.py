"""Evaluate the one frozen public alpha-chain prediction against retained coordinates."""
from pathlib import Path
import csv,hashlib,json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'biopython_runtime'))
import numpy as np
from Bio.PDB import PDBParser,MMCIFParser,Superimposer
from Bio.SeqUtils import seq1
from analyze_hemoglobin import kabsch
out=ROOT/'fold_single_sequence'
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
result={'status':'Prediction executed; low-confidence, poor structural recovery in this single-sequence setting',
 'sequence_mapping':'Prediction/PDB mature index i (1..141) = UniProt P69905 full-translation position i+1 (2..142). Initiator Met at UniProt1 absent from input. All fits use mature2..141 (140 CA) because 2DN1 mature1 is unmodeled.',
 'prediction_file':preds[0].name,'prediction_sha256':hashlib.sha256(preds[0].read_bytes()).hexdigest(),
 'plddt_mean':float(np.mean(score['plddt'])),'plddt_min':min(score['plddt']),'plddt_max':max(score['plddt']),
 'plddt_below_50_count':sum(v<50 for v in score['plddt']),'ptm_rounded_score_json':score['ptm'],
 'fits':fits,'checks':['141 predicted amino acids exactly match source input','Public P69905 mature-sequence mapping exact','All 420 evaluated residue identities match','Three Kabsch and Biopython RMSDs agree within 1e-10 A']}
(ROOT/'fold_evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
with (ROOT/'fold_residuals.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(result,indent=2))
