"""Independent Coda implementation audit of the preserved Grok Build screen.

Run from any directory: python research/grok_build_qa/verify.py
Writes only inside this QA directory. No external calls.
"""
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location('grok_qa_'+name, HERE/(name+'.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def clean(x):
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    if isinstance(x, (tuple, list)):
        return [clean(v) for v in x]
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    return x

# Expected answers fixed before loading/executing either implementation.
CASES = [
 ('linear_zero_power_positive_demand', 'feasible_interval_linear', [1e-16,1,1,1,0,1], None),
 ('fixed_dp_zero_power_positive_demand', 'feasible_interval_fixed_dp', [1e-16,1,1,1,0,1], None),
 ('positive_but_reversed_interval', '_interval_or_empty', [1+5e-13,1], None),
 ('zero_flow_positive_branch_demand', 'local_supply_met', [0,[1],1,1,[1],[1e-16]], False),
 ('stagnant_branch_positive_demand', 'local_supply_met', [1,[1,0],1,1,[1,1],[.5,1e-16]], False),
 ('zero_transfer_ceiling_positive_demand', 'local_supply_met', [1,[1],1,1,[0],[1e-16]], False),
 ('zero_power_positive_flow', 'power_ok_linear', [1e-8,1,0,1], False),
 ('thousandfold_power_budget_excess', 'power_ok_linear', [1e-6,1,1e-15,1], False),
 ('zero_power_complete_flag', 'complete_flag', [1e-8,1,1,1e-9,0,1], False),
 ('outlet_above_inlet', 'delivered_oxygen_mol_s', [1,0,1e-16], 'ValueError'),
 ('negative_pressure', 'hydraulic_power', [-1,1], 'ValueError'),
 ('gamma_infinite_demand', 'gamma_linear', [math.inf,1,1,1,1,1], 'ValueError'),
 ('gamma_nan_concentration', 'gamma_linear', [1,1,math.nan,1,1,1], 'ValueError'),
 ('global_negative_demand', 'global_supply_met', [1,1,1,-1], 'ValueError'),
 ('global_nan_zero_demand', 'global_supply_met', [math.nan,1,1,0], 'ValueError'),
 ('local_negative_demand', 'local_supply_met', [1,[1],1,1,[1],[-1]], 'ValueError'),
 ('local_nan_fraction', 'local_supply_met', [1,[math.nan],1,1,[1],[1]], 'ValueError'),
 ('local_bad_late_branch', 'local_supply_met', [0,[.5,.5],1,1,[1,1],[1,math.nan]], 'ValueError'),
 ('branch_fraction_above_one', 'branch_delivered', [1,1.1,1,1,1], 'ValueError'),
 ('series_mismatched_arrays', 'series_path', [1,1,[.2,.3],[1]], 'ValueError'),
 ('series_nan_drop', 'series_path', [1,1,[math.nan],[1]], 'ValueError'),
 ('local_mismatched_arrays', 'local_supply_met', [1,[1],1,1,[],[1]], 'ValueError'),
 ('zero_supply_zero_demand', 'local_supply_met', [0,[1],0,1,[0],[0]], True),
 ('zero_power_zero_demand_interval', 'feasible_interval_linear', [0,1,1,1,0,1], [0.0,0.0]),
 ('positive_interior_local', 'local_supply_met', [1,[.5,.5],1,1,[1,1],[.4,.4]], True),
 ('positive_interior_power', 'power_ok_linear', [.25,.5,1,1], True),
 ('zero_content_positive_demand', 'feasible_interval_linear', [1,1,0,1,1,1], None),
 ('zero_flow_global_positive_demand', 'global_supply_met', [0,1,1,1e-16], False),
 ('fraction_sum_invalid', 'local_supply_met', [1,[.2,.2],1,1,[1,1],[.1,.1]], 'ValueError'),
]
freeze = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
          'test_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'cases': [{'id': n, 'function': f, 'arguments': clean(a), 'expected': e} for n,f,a,e in CASES],
          'policy': 'Test definitions frozen before imports/execution; expected physical boundaries derived from inequalities, not output snapshots.'}
(HERE/'test_freeze.json').write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf-8')
original, corrected = load('original'), load('corrected')
checks = []
for name, fn, args, expected in CASES:
    observed = {}
    for label, mod in [('original',original),('corrected',corrected)]:
        try:
            if fn == 'complete_flag':
                q,c,alpha,m,p,r = args
                value = mod.model_survival_flag(mod.global_supply_met(q,c,alpha,m),
                    mod.local_supply_met(q,[1],c,alpha,[1],[m]),mod.power_ok_linear(q,1,p,r))
            else:
                value = getattr(mod,fn)(*args)
            value = clean(value)
        except Exception as exc:
            value = type(exc).__name__
        observed[label] = value
    checks.append({'id': name, 'expected': expected, **observed,
                   'original_pass': observed['original'] == expected,
                   'corrected_pass': observed['corrected'] == expected})

run = HERE/'corrected_run'
run.mkdir(exist_ok=True)
proc = subprocess.run([sys.executable,str(HERE/'corrected.py')], cwd=run, capture_output=True,text=True,encoding='utf-8',timeout=30)
(run/'execution.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
assert proc.returncode == 0, proc.stderr
old_result=json.loads((HERE/'original_run/toy_perfusion_out/screen.json').read_text(encoding='utf-8'))
new_result=json.loads((run/'toy_perfusion_out/screen.json').read_text(encoding='utf-8'))
with (HERE/'original_run/toy_perfusion_out/sweep.csv').open(encoding='utf-8',newline='') as f:
    old_rows=list(csv.DictReader(f))
with (run/'toy_perfusion_out/sweep.csv').open(encoding='utf-8',newline='') as f:
    new_rows=list(csv.DictReader(f))

# Independent Decimal formulas; avoids simply calling the same helper twice.
arithmetic=[]
def record(name, expected, actual, tol=1e-12):
    passed=math.isclose(float(expected),actual,rel_tol=tol,abs_tol=0)
    arithmetic.append({'id':name,'decimal_expected':str(expected),'binary64_actual':actual,'passed':passed})
with localcontext() as context:
    context.prec=60
    D=Decimal
    q,c,r,eta,alpha,m,p=map(D,['0.00002','1','100000000','0.5','1','0.000002','10'])
    record('hydraulic_power_W',r*q*q,corrected.hydraulic_power(float(r*q),float(q)))
    record('electrical_power_W',r*q*q/eta,corrected.electrical_power(float(r*q),float(q),float(eta)))
    record('q_min_m3_s',m/(alpha*c),corrected.q_min_for_demand(float(m),float(alpha),float(c)))
    record('q_max_m3_s',(eta*p/r).sqrt(),corrected.q_max_for_power_linear(float(eta),float(p),float(r)))
    record('Gamma_dimensionless',alpha**2*c**2*eta*p/(m*m*r),corrected.gamma_linear(float(m),float(alpha),float(c),float(eta),float(p),float(r)))
    # Three serial segments: 0.6, then 0.3 limited by ceiling, then 0.1 remaining.
    path=corrected.series_path(2,1,[.6,.6,.6],[2,.6,2])
    for i,expected in enumerate(['1.2','.6','.2']):
        record('series_segment_'+str(i)+'_mol_s',D(expected),path['segment_delivery_mol_s'][i])
    record('series_total_mol_s',D(2),path['delivered_once_mol_s'])
    record('series_end_to_end_mol_s',D(2),path['end_to_end_mol_s'])
    # Conditional liquid conversion only; neither SLPM interpretation nor actual device measurement established.
    liquid_q=D(40)*D('.001')/D(60)
    liquid_p=D(100)*D('4.4482216152605')/(D('.0254')**2)*liquid_q
    record('conditional_actual_liquid_product_W',liquid_p,corrected.conditional_nameplate()['interpretation_actual_liquid_L_per_min']['P_hyd_W'])

# Double-counting is wrong even when the global carrier bound does not catch it.
small=corrected.series_path(1,1,[.1,.1],[1,1])
double=small['delivered_once_mol_s']+small['end_to_end_mol_s']
prose_counterexample={'two_series_drops': [.1,.1], 'Q':1,'C_in':1,
    'correct_delivery':small['delivered_once_mol_s'],'double_counted_delivery':double,
    'carrier_capacity':1,'double_counted_value_still_below_capacity':double<1,
    'implication':'A carrier upper-bound check is necessary but not sufficient to detect oxygen double counting.'}
counts={label:dict(Counter(row['scenario'] for row in rows if row['model_survival_flag']=='True')) for label,rows in [('original',old_rows),('corrected',new_rows)]}
out={
 'completed_utc':datetime.now(timezone.utc).isoformat(),
 'authorship':{'original':'Grok Build (xAI route)','audit_and_corrected_derivative':'Coda/local team working with Richard Pemberton'},
 'original_script_sha256':hashlib.sha256((HERE/'original.py').read_bytes()).hexdigest(),
 'corrected_script_sha256':hashlib.sha256((HERE/'corrected.py').read_bytes()).hexdigest(),
 'supplied_checks':{'original_count':len(old_result['checks']),'corrected_count':len(new_result['checks']),
                    'original':old_result['checks'],'corrected':new_result['checks']},
 'sweep':{'original_rows':len(old_rows),'corrected_rows':len(new_rows),'exact_csv_fields_equal':old_rows==new_rows,'model_flag_true_counts':counts},
 'boundary_cases':checks,'boundary_summary':{'total':len(checks),'original_pass':sum(x['original_pass'] for x in checks),'corrected_pass':sum(x['corrected_pass'] for x in checks)},
 'independent_arithmetic':arithmetic,'arithmetic_pass_count':sum(x['passed'] for x in arithmetic),
 'double_counting_counterexample':prose_counterexample,
 'corrected_process_exit_code':proc.returncode,
 'limits':['Original and corrected are toy algebra only; no empirical pump, carrier, tissue or clinical validation.',
           'This is local independent review of Grok Build, not external validation of Coda corrections.',
           'Strict binary64 comparisons preserve zero boundaries but can conservatively reject near-boundary rounding.',
           'Finite validation is not a proof against overflow/underflow over all finite IEEE-754 values.',
           'Local ceilings and branch flow fractions remain assumed independent inputs, not solved transport or vessel geometry.',
           'The model flag is an inequality conjunction; relabel it as model-constraint flag in scientific interpretation.',
           'Conditional nameplate calculation is unverified and is not a simultaneous measured operating point.']}
(HERE/'results.json').write_text(json.dumps(clean(out),indent=2)+'\n',encoding='utf-8')
assert all(x['corrected_pass'] for x in checks)
assert all(x['passed'] for x in arithmetic)
assert old_rows==new_rows and len(old_rows)==105
print(json.dumps({'boundary_summary':out['boundary_summary'],'supplied_check_count':len(old_result['checks']),'arithmetic_checks':len(arithmetic),'sweep_identical':old_rows==new_rows,'model_flag_true_counts':counts}))
