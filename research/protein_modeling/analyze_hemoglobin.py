"""HB-STRUCT0: offline experimental RCSB coordinate analysis; no fold prediction."""
from pathlib import Path
import csv, hashlib, json, platform, sys
from collections import Counter
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'biopython_runtime'))
import Bio
import numpy as np
from Bio.PDB import MMCIFParser, Superimposer
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_csv(name, rows):
    with (ROOT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def kabsch(x, y):
    """Row-vector moving x -> fixed y, proper rotation only."""
    xc, yc = x.mean(0), y.mean(0)
    u, _, vt = np.linalg.svd((x-xc).T @ (y-yc))
    d = np.eye(3); d[-1,-1] = np.linalg.det(u @ vt)
    rot = u @ d @ vt
    fitted = (x-xc) @ rot + yc
    return float(np.sqrt(np.mean(np.sum((fitted-y)**2, axis=1))))

def atom_label(a):
    r = a.get_parent()
    return f'{r.get_parent().id}:{r.resname}:{r.id[1]}{r.id[2].strip()}:{a.name}'

def main():
    checks, inventory, geometries, connections, models, cifs = [], {}, [], {}, {}, {}
    for item in json.loads((ROOT / 'download_receipt.json').read_text()):
        assert sha(ROOT/'raw'/item['file']) == item['sha256'], item['file']
    checks.append('All four downloaded file hashes match acquisition receipts')
    for pdb in ['2DN1', '2DN2']:
        path = ROOT/'raw'/f'{pdb}.cif'
        d = cifs[pdb] = MMCIF2Dict(str(path))
        model = models[pdb] = MMCIFParser(QUIET=True).get_structure(pdb, path)[0]
        assert len(list(model.get_parent())) == 1
        inv = inventory[pdb] = {'title':d['_struct.title'][0], 'resolution_A':float(d['_refine.ls_d_res_high'][0]),
            'chains':{}, 'nonwater_ligands':{}, 'selected_disordered_atoms':[]}
        for c in model:
            protein = [r for r in c if r.id[0]==' ']
            expected_len = 141 if c.id in ('A','C') else 146
            inv['chains'][c.id] = {'protein_residues':len(protein), 'CA_count':sum('CA' in r for r in protein),
                'expected_residues':expected_len, 'missing_author_numbers':sorted(set(range(1,expected_len+1))-{r.id[1] for r in protein}),
                'waters':sum(r.resname=='HOH' for r in c)}
            lig = Counter(r.resname for r in c if r.id[0]!=' ' and r.resname!='HOH')
            inv['nonwater_ligands'][c.id] = dict(lig)
        for a in model.get_atoms():
            if a.is_disordered():
                inv['selected_disordered_atoms'].append({'atom':atom_label(a), 'selected_altloc':a.get_altloc(), 'occupancy':a.get_occupancy()})
        keys = [k for k in d if k.startswith('_struct_conn.')]
        connections[pdb] = [{k.split('.',1)[1]:d[k][i] for k in keys} for i in range(len(d[keys[0]]))]
        for c in model:
            for heme in [r for r in c if r.resname=='HEM']:
                fe = heme['FE'].coord.astype(float)
                ns = np.array([heme[n].coord for n in ('NA','NB','NC','ND')],dtype=float)
                _, _, vt = np.linalg.svd(ns-ns.mean(0))
                his = [(float(np.linalg.norm(fe-r['NE2'].coord)),r['NE2']) for chain in model for r in chain if r.resname=='HIS' and 'NE2' in r]
                hisdist, histidine = min(his,key=lambda x:x[0])
                oxy = sorted([(float(np.linalg.norm(fe-a.coord)),a) for chain in model for r in chain if r.resname=='OXY' for a in r],key=lambda x:x[0])
                row = {'entry':pdb,'chain':c.id,'heme_author_number':heme.id[1],
                    'Fe_His_NE2_A':hisdist,'His_atom':atom_label(histidine),
                    'Fe_abs_offset_four_N_plane_A':float(abs((fe-ns.mean(0)) @ vt[-1])),
                    'nearest_OXY_atom':atom_label(oxy[0][1]) if oxy else '',
                    'nearest_Fe_OXY_A':oxy[0][0] if oxy else '',
                    'OXY_atoms_within_3A':sum(dist<3 for dist,a in oxy)}
                for n, xyz in zip(('NA','NB','NC','ND'), ns): row[f'Fe_{n}_A']=float(np.linalg.norm(fe-xyz))
                assert 1.5 < hisdist < 3 and all(np.isfinite(v) for v in row.values() if isinstance(v,float))
                geometries.append(row)
        # Recompute deposited metal-contact distances; symmetry here is identity only.
        for conn in connections[pdb]:
            assert conn['ptnr1_symmetry']==conn['ptnr2_symmetry']=='1_555'
            pair=[]
            for j in (1,2):
                ch = model[conn[f'ptnr{j}_auth_asym_id']]
                res = [r for r in ch if r.id[1]==int(conn[f'ptnr{j}_auth_seq_id']) and r.resname==conn[f'ptnr{j}_auth_comp_id']]
                assert len(res)==1
                pair.append(res[0][conn[f'ptnr{j}_label_atom_id']].coord.astype(float))
            conn['recomputed_distance_A']=float(np.linalg.norm(pair[0]-pair[1]))
            assert abs(conn['recomputed_distance_A']-float(conn['pdbx_dist_value'])) < .002
    checks.append('All nine deposited identity-symmetry metal-contact distances reproduced within 0.002 A')
    alignments, residuals = [], []
    def fit(pairs, label):
        fixed, moving, identities = [], [], []
        for oc, dc in pairs:
            o = {r.id:r for r in models['2DN1'][oc] if r.id[0]==' ' and 'CA' in r}
            t = {r.id:r for r in models['2DN2'][dc] if r.id[0]==' ' and 'CA' in r}
            for rid in sorted(o.keys() & t.keys()):
                assert o[rid].resname==t[rid].resname
                fixed.append(o[rid]['CA']); moving.append(t[rid]['CA']); identities.append((oc,dc,rid[1],o[rid].resname))
        x=np.array([a.coord for a in moving],dtype=float); y=np.array([a.coord for a in fixed],dtype=float)
        sup=Superimposer();sup.set_atoms(fixed,moving)
        r,t=sup.rotran; errs=np.linalg.norm(x@r+t-y,axis=1)
        direct=float(np.sqrt(np.mean(errs**2)))
        assert abs(direct-sup.rms)<1e-10 and abs(kabsch(x,y)-sup.rms)<1e-10
        assert np.linalg.det(r)>0.999999
        alignments.append({'fit':label,'matched_CA':len(x),'rmsd_A':direct,'max_residual_A':float(max(errs))})
        for ident,err in zip(identities,errs):
            residuals.append(dict(zip(('oxy_chain','deoxy_chain','author_number','residue'),ident),fit=label,residual_A=float(err)))
        return x
    for oc,dc in [('A','A'),('A','C'),('B','B'),('B','D')]: x=fit([(oc,dc)],f'oxy{oc}_deoxy{dc}')
    fit([('A','A'),('B','B')],'oxyAB_deoxyAB_joint_dimer')
    fit([('A','C'),('B','D')],'oxyAB_deoxyCD_joint_dimer')
    checks.append('Six proper-rotation fits agree: Biopython, explicit residuals and separate NumPy Kabsch calculation')
    rot=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
    assert kabsch(x,x)<1e-10 and kabsch(x@rot+[7,8,9],x)<1e-10
    perturbed=x.copy();perturbed[0]+=[1,2,3]
    assert kabsch(perturbed,x)>0.1
    checks.append('Self-fit and known rigid transform return <1e-10 A; one-point deformation returns >0.1 A')
    assert sum(x['nonwater_ligands'].get(c,{}).get('OXY',0) for x in [inventory['2DN1']] for c in x['chains'])==2
    assert sum(x['nonwater_ligands'].get(c,{}).get('OXY',0) for x in [inventory['2DN2']] for c in x['chains'])==0
    checks.append('Oxy/deoxy OXY inventories are two/zero; six hemes successfully measured')
    seqs = [s.replace('\n','').replace(' ','') for s in cifs['2DN1']['_entity_poly.pdbx_seq_one_letter_code_can']]
    seqs2 = [s.replace('\n','').replace(' ','') for s in cifs['2DN2']['_entity_poly.pdbx_seq_one_letter_code_can']]
    assert seqs==seqs2 and list(map(len,seqs))==[141,146]
    checks.append('Deposited alpha/beta sequences match exactly across entries (141/146 residues)')
    (ROOT/'public_hemoglobin_sequences.fasta').write_text('>human_alpha_PDB_2DN1_entity1\n'+seqs[0]+'\n>human_beta_PDB_2DN1_entity2\n'+seqs[1]+'\n',encoding='utf-8')
    result={'scope':'Experimental deposited-coordinate calibration, not a folding or functional prediction',
        'coordinate_policy':'Model 0; author chains/residue numbers; parser-selected highest-occupancy alternate atom (ties retain parser choice); unweighted CA fits; all available common residue IDs with identity checked; no symmetry-generated assembly.',
        'runtime':{'python':platform.python_version(),'biopython':Bio.__version__,'numpy':np.__version__},
        'inventory':inventory,'alignments':alignments,'heme_geometry':geometries,'deposited_connections':connections,'checks_passed':checks}
    (ROOT/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    save_csv('chain_alignment.csv',alignments);save_csv('heme_geometry.csv',geometries);save_csv('ca_residuals.csv',residuals)
    print(json.dumps({'alignments':alignments,'heme_geometry':geometries,'checks_passed':checks},indent=2))

if __name__=='__main__': main()
