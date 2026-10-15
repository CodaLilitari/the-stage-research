"""Independent bounded HB-STRUCT0 review: no producer import, no Biopython."""
from pathlib import Path
import datetime, hashlib, json, math, re, shlex
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(text,prefix):
    lines=text.splitlines();start=next(i for i,l in enumerate(lines) if l.startswith(prefix+'.'))
    headers=[];i=start
    while lines[i].startswith(prefix+'.'):
        headers.append(lines[i].strip().split('.',1)[1]);i+=1
    tokens=[]
    while i<len(lines) and not lines[i].startswith('#'):
        tokens.extend(shlex.split(lines[i]));i+=1
    if len(tokens)%len(headers):raise ValueError('Unexpected wrapped table')
    return [dict(zip(headers,tokens[j:j+len(headers)])) for j in range(0,len(tokens),len(headers))]
def scalar(text,key):return shlex.split(re.search(r'^'+re.escape(key)+r'\s+(.+)$',text,re.M).group(1))[0]
def coord(row):return np.array([float(row['Cartn_'+a]) for a in 'xyz'],dtype=float)
def key(row):return (row['auth_asym_id'],row['auth_comp_id'],int(row['auth_seq_id']),row['auth_atom_id'])
def quat_rms(x,y):
    # Horn quaternion maximum-eigenvalue formula; unlike producer SVD/Kabsch.
    x=x-x.mean(axis=0);y=y-y.mean(axis=0);m=x.T@y
    xx,xy,xz,yx,yy,yz,zx,zy,zz=m.ravel()
    k=np.array([[xx+yy+zz,yz-zy,zx-xz,xy-yx],
                [yz-zy,xx-yy-zz,xy+yx,zx+xz],
                [zx-xz,xy+yx,-xx+yy-zz,yz+zy],
                [xy-yx,zx+xz,yz+zy,-xx-yy+zz]])
    ev=np.linalg.eigvalsh(k)[-1]
    return math.sqrt(max(0.,(np.sum(x*x)+np.sum(y*y)-2*ev)/len(x)))
def main():
    result=json.loads((ROOT/'results.json').read_text());receipt=json.loads((ROOT/'download_receipt.json').read_text())
    checks={};details={}
    checks['acquisition_four_hashes']=len(receipt)==4 and all(sha(ROOT/'raw'/r['file'])==r['sha256'] and (ROOT/'raw'/r['file']).stat().st_size==r['bytes'] for r in receipt)
    manifest=json.loads((ROOT/'manifest.json').read_text())
    relevant=[x for x in manifest['files'] if not x['path'].startswith('biopython_runtime/')]
    checks['analysis_artifact_manifest_hashes']=all(sha(ROOT/x['path'])==x['sha256'] for x in relevant)
    texts={p:(ROOT/'raw'/f'{p}.cif').read_text() for p in ['2DN1','2DN2']}
    atoms={p:table(t,'_atom_site') for p,t in texts.items()}
    checks['one_model_no_altloc_or_insertion']=all(a['pdbx_PDB_model_num']=='1' and a['label_alt_id']=='.' and a['pdbx_PDB_ins_code']=='?' for v in atoms.values() for a in v)
    lookups={p:{key(a):coord(a) for a in v} for p,v in atoms.items()}
    checks['atom_keys_unique']=all(len(lookups[p])==len(v) for p,v in atoms.items())
    ca={p:{c:{int(a['auth_seq_id']):(a['auth_comp_id'],coord(a)) for a in v if a['group_PDB']=='ATOM' and a['auth_atom_id']=='CA' and a['auth_asym_id']==c} for c in sorted({a['auth_asym_id'] for a in v if a['group_PDB']=='ATOM'})} for p,v in atoms.items()}
    counts={p:{c:len(v) for c,v in cs.items()} for p,cs in ca.items()}
    checks['asymmetric_unit_counts']=counts=={'2DN1':{'A':140,'B':145},'2DN2':{'A':141,'B':146,'C':141,'D':146}}
    assembly={p:{'oligomeric_count':scalar(t,'_pdbx_struct_assembly.oligomeric_count'),'operators':scalar(t,'_pdbx_struct_assembly_gen.oper_expression')} for p,t in texts.items()}
    checks['assembly_caveat_supported']=assembly=={'2DN1':{'oligomeric_count':'4','operators':'1,2'},'2DN2':{'oligomeric_count':'4','operators':'1'}} and 'No symmetry-generated biological assembly' in (ROOT/'report.txt').read_text()
    fits=[('oxyA_deoxyA',[('A','A')]),('oxyA_deoxyC',[('A','C')]),('oxyB_deoxyB',[('B','B')]),('oxyB_deoxyD',[('B','D')]),('oxyAB_deoxyAB_joint_dimer',[('A','A'),('B','B')]),('oxyAB_deoxyCD_joint_dimer',[('A','C'),('B','D')])]
    independent=[];identity=True
    for label,pairs in fits:
        x=[];y=[]
        for oc,dc in pairs:
            for n in sorted(set(ca['2DN1'][oc])&set(ca['2DN2'][dc])):
                aa,a=ca['2DN1'][oc][n];bb,b=ca['2DN2'][dc][n];identity &= aa==bb;x.append(a);y.append(b)
        observed=quat_rms(np.array(x),np.array(y));expected=next(a for a in result['alignments'] if a['fit']==label)
        independent.append({'fit':label,'matched_CA':len(x),'rmsd_A':observed,'difference_from_saved_A':observed-expected['rmsd_A']})
    checks['1140_matched_residue_pairs_identical']=identity and sum(r['matched_CA'] for r in independent)==1140
    checks['six_independent_quaternion_rmsds']=max(abs(r['difference_from_saved_A']) for r in independent)<1e-5
    geom=[]
    for r in result['heme_geometry']:
        p=r['entry'];c=r['chain'];n=r['heme_author_number'];lookup=lookups[p]
        fe=lookup[c,'HEM',n,'FE'];ns=np.array([lookup[c,'HEM',n,a] for a in ['NA','NB','NC','ND']]);center=ns.mean(axis=0);z=ns-center
        _,vec=np.linalg.eigh(z.T@z);normal=vec[:,0];offset=abs(float((fe-center)@normal))
        his_n=87 if c in 'AC' else 92;hd=float(np.linalg.norm(fe-lookup[c,'HIS',his_n,'NE2']))
        geom.append({'entry':p,'chain':c,'independent_plane_offset_A':offset,'offset_error_A':offset-r['Fe_abs_offset_four_N_plane_A'],'independent_His_distance_A':hd,'His_error_A':hd-r['Fe_His_NE2_A']})
    checks['six_heme_four_N_eigenplane_and_His_distances']=all(abs(r['offset_error_A'])<1e-5 and abs(r['His_error_A'])<1e-5 for r in geom)
    conn=[]
    for p,t in texts.items():
        for r in table(t,'_struct_conn'):
            assert r['ptnr1_symmetry']==r['ptnr2_symmetry']=='1_555'
            xyz=[lookups[p][r[f'ptnr{j}_auth_asym_id'],r[f'ptnr{j}_auth_comp_id'],int(r[f'ptnr{j}_auth_seq_id']),r[f'ptnr{j}_label_atom_id']] for j in [1,2]]
            d=float(np.linalg.norm(xyz[0]-xyz[1]));conn.append({'entry':p,'id':r['id'],'distance_A':d,'deposited_error_A':d-float(r['pdbx_dist_value'])})
    checks['nine_independent_deposited_contacts']=len(conn)==9 and max(abs(r['deposited_error_A']) for r in conn)<.002
    # Numerical positive/negative controls independent of the biological coordinates.
    p=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    rot=np.array([[0,-1.,0],[1.,0,0],[0,0,1.]])
    mutated=p.copy();mutated[0,0]+=.5
    checks['independent_fit_controls']=quat_rms(p,p@rot+[7,8,9])<1e-7 and quat_rms(p,mutated)>.1
    report={'scope':'Independent bounded HB-STRUCT0 coordinate QA only; no fold/inference/runtime-install QA',
            'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_sha256':sha(ROOT/'analyze_hemoglobin.py'),'qa_source_sha256':sha(Path(__file__)),
            'saved_results_sha256':sha(ROOT/'results.json'),'input_sha256':{r['file']:sha(ROOT/'raw'/r['file']) for r in receipt},
            'methods':'Separate direct mmCIF table parser, float64 coordinates, Horn quaternion eigenvalue fit, covariance eigenvector four-N plane; no producer or Biopython imports. NumPy remains shared library family.',
            'comparison_tolerance_A':1e-5,'tolerance_reason':'Producer Biopython stores coordinates as float32; independent parser uses float64 from deposited decimals.',
            'checks':checks,'passed':sum(checks.values()),'total':len(checks),'all_passed':all(checks.values()),
            'counts':counts,'assembly_metadata':assembly,'independent_fits':independent,'independent_geometry':geom,'independent_contacts':conn,
            'limitations':['No electron-density re-refinement or experimental replication.','Common author numbering and residue identities verified for this specific entry pair; no generic aligner validation.','Asymmetric units compared, not symmetry-completed tetramer transitions.','Geometry cannot establish oxygen affinity, therapeutic safety or tissue delivery.','No active folding installation or outputs inspected.']}
    (ROOT/'independent_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'total':report['total'],'checks':checks,'max_fit_error_A':max(abs(r['difference_from_saved_A']) for r in independent),'max_plane_error_A':max(abs(r['offset_error_A']) for r in geom)},indent=2))
    if not all(checks.values()):raise SystemExit(2)
if __name__=='__main__':main()
