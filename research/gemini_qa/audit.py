"""Bounded Coda audit of the preserved, unexecuted Gemini carrier draft.
Original proposal retained. No biological or clinical validation.
"""
from pathlib import Path
import csv, hashlib, importlib.util, json, subprocess, sys

root=Path(__file__).resolve().parent
project=root.parents[1]
source=root/'original'  # Public-export pointer adaptation; primary-source audit inputs remain excluded.
original=root/'original'
original.mkdir(exist_ok=True)
for name in ('stage_oxygen_carrier_model.py','oxygen_carriers_primary_data.csv'):
    if (original/name).exists():
        assert (original/name).read_bytes()==(source/name).read_bytes()
    else:
        (original/name).write_bytes((source/name).read_bytes())
run=subprocess.run([sys.executable,'stage_oxygen_carrier_model.py'],cwd=original,capture_output=True,text=True)
(root/('original_execution_after_dependencies.txt' if (root/'original_execution.txt').exists() else 'original_execution.txt')).write_text(run.stdout+'\nSTDERR:\n'+run.stderr,encoding='utf-8')
assert run.returncode==0
rows=list(csv.DictReader((original/'stage_carrier_ranking_comparison.csv').open(newline='')))
spec=importlib.util.spec_from_file_location('gemini_original',original/'stage_oxygen_carrier_model.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
claimed={'hRBC_Banerjee2022':.583,'NMU_HbV_PLP_Ref':.579,'PEG_LEH_256nm_Banerjee2022':.391,'HBOC201_Hemopure_Ref':.457,'hHb_Banerjee2022':.207}
exact=[]
for r in rows:
    actual=float(mod.hill_saturation(80,float(r['P50_mmHg']),float(r['hill_n']))-mod.hill_saturation(20,float(r['P50_mmHg']),float(r['hill_n'])))
    exact.append({'sample':r['sample_id'],'at_means':actual,'claimed':claimed.get(r['sample_id']),'monte_carlo_mean':float(r['delta_S_eq_mean'])})
report={'original_execution_exit':run.returncode,'ranking_rows':len(rows),'mean_equilibrium_comparison':exact,
 'primary_table_inspected':'Banerjee2022Table1 publisher PNG and main text,2026-10-15',
 'material_source_issues':[
  'RBC diameter2000–8000nm is a range; Gemini encodes5000mean/3000SD, which is not a reported mean/SD.',
  'Rameez suspension Hb11–13 and internalHb50–75 are ranges; Gemini midpoint/half-range are not SDs.',
  'Rameez metHb<1.0% does not support0.8mean/0.2SD.',
  'HBOC201/NMU reference rows contain source-unverified point estimates and SDs; exclude from empirical rankings pending verification.',
  'Main text specifies SF-17/SX17MV; draft says SX-18MV. Additional equilibrium buffer claims require their own source.',
  '20C kinetic constants cannot be silently treated as calibrated37C mission kinetics.'
 ],
 'model_issues':[
  'NO-radius relation,precapillary penalty,redox scaling and missing-rate defaults are hypothetical; no fitted physiological linkage supplied.',
  'Intrinsic equilibrium ranks are compared to unequal-concentration net-content ranks; normalization comment is not implemented.',
  'MonteCarlo SDs are neither calibrated population uncertainty nor confidence intervals; several source SDs were invented from ranges.',
  'Held-out checks use synthetic Hill samples,not withheld experimental measurements; FIM condition depends on parameter units.',
  'P50 is half-saturation,not generally the linear-pressure Hill inflection.'
 ],
 'disposition':'Preserve original proposal and local run; do not accept product ranking or clinical inference. Correct verified-table subset separately before integration.',
 'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'banerjee2022.html',root/'banerjee2022_table1.png')},
 'limits':'Bounded audit, not verification of all clinical/regulatory claims or all sources.'}
(root/'audit_receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
