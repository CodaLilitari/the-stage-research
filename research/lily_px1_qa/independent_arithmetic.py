"""Coda's independent Decimal arithmetic checks of Lily's PX1 and local replay.

Does not call the producing solver. This verifies the reduced model, not tissue.
"""
from pathlib import Path
from decimal import Decimal, localcontext
import csv, hashlib, json, math, platform

ROOT = Path(__file__).resolve().parent
local = ROOT / 'local_replay'
received = ROOT / 'received/blood_and_tissue/results/execution'
comparisons = []
max_difference = 0.0
for filename in ('S_transport.csv', 'H_equilibrium.csv', 'H_kinetic_controls.csv'):
    a = list(csv.DictReader((local/filename).open(newline='')))
    b = list(csv.DictReader((received/filename).open(newline='')))
    assert len(a) == len(b)
    assert list(a[0]) == list(b[0])
    for ar, br in zip(a,b):
        for key in ar:
            delta = abs(float(ar[key])-float(br[key]))
            max_difference=max(max_difference,delta)
            assert math.isclose(float(ar[key]),float(br[key]),rel_tol=1e-12,abs_tol=1e-14), (filename,key)
    comparisons.append({'file':filename,'rows':len(a),'local_sha256':hashlib.sha256((local/filename).read_bytes()).hexdigest()})

with localcontext() as ctx:
    ctx.prec=60
    ds = lambda value: Decimal(str(value))
    errors=[]
    for row in csv.DictReader((local/'S_transport.csv').open(newline='')):
        da,f=ds(row['Da']),ds(row['wall_fraction'])
        cb=(-da*f).exp()
        expected={'channel_out':cb,'distal_tissue':f*cb,'extraction_fraction':1-cb,'distal_derivative_wrt_f':cb*(1-da*f)}
        errors += [abs(float(value)-float(row[key])) for key,value in expected.items()]
    assert max(errors)<1e-14
    for row in csv.DictReader((local/'H_equilibrium.csv').open(newline='')):
        load,unload,n=map(ds,(row['loading_mmHg'],row['unloading_mmHg'],row['Hill_n']))
        optimum=(load*unload).sqrt()
        assert abs(float(optimum)-float(row['exact_optimum_p50_mmHg']))<1e-12
        ratio=(load/unload)**(n/2)
        extraction=(ratio-1)/(ratio+1)
        assert abs(float(extraction)-float(row['maximum_bound_fraction_unloaded']))<1e-14
    for row in csv.DictReader((local/'H_kinetic_controls.csv').open(newline='')):
        t, inactive=ds(row['contact_time_over_tau']),ds(row['inactive_fraction'])
        expected=(1-inactive)*(1-(-t).exp())
        assert abs(float(expected)-float(row['available_fraction_of_equilibrium_capacity']))<1e-14

report={'status':'pass','author':'Coda independent verification','python':platform.python_version(),
 'local_execution':'270 transport integrations,18 equilibrium and9 kinetic cases already executed in local_replay',
 'source_comparison':comparisons,'maximum_numeric_difference_from_returned_csv':max_difference,
 'independent_decimal_analytical_error':max(errors),
 'limits':'Reduced mathematical model only; no PF0 replication, skin calibration, biological or clinical validation.'}
(ROOT/'independent_arithmetic_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
