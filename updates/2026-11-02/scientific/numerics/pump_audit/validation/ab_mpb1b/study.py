# SPDX-License-Identifier: Apache-2.0
# Coda (Codex Lily), native agent stage_site0_recovery.
"""Record all frozen AB-MPB1B rows and explicitly separated contrasts."""
from dataclasses import asdict
from pathlib import Path
import csv,json,math,time
from admitted import ROOT,A,A_ROWS,DESIGN,initial,read,sha,verify_a
import pump

ENDPOINTS=('distal_wall_concentration','minimum_wall_concentration','consumed_umol','net_wall_transfer_umol')
def check_freeze(name):
    data=read(ROOT/name)
    for e in data['files']:
        if sha(ROOT/e['path'])!=e['sha256']:raise RuntimeError('Frozen file changed: '+e['path'])
def write_csv(path,rows,fields):
    with path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
def main():
    start=time.perf_counter();cpu=time.process_time()
    check_freeze('FREEZE.json');check_freeze('IMPLEMENTATION_FREEZE.json');verify_a()
    green=read(ROOT/'receipts/green.json')
    assert green['exit_code']==0 and not green['timed_out'] and green['pump_sha256']==sha(ROOT/'pump.py')
    out=ROOT/'run_001';out.mkdir(exist_ok=False)
    caps=pump.PumpCaps(DESIGN['pressure_cap_kpa'],DESIGN['hydraulic_power_cap_mw'])
    config=A.Config(**DESIGN['configuration']);rows=[]
    for cond in DESIGN['conditions']:
        model,y=initial(config,cond);oxygen,sites=A.inventories(model,y)
        assert math.isclose(oxygen,cond['expected_oxygen_umol'],abs_tol=1e-13,rel_tol=0)
        assert math.isclose(sites,cond['expected_sites_umol'],abs_tol=1e-13,rel_tol=0)
        for ratio in DESIGN['resistance_ratios']:
            resistance=DESIGN['resistance_reference_kpa_s_per_ml']*ratio
            for duration in DESIGN['times_s']:
                solved=pump.solve_pumped(config,y,duration,DESIGN['dt_s'],resistance,caps)
                result=solved['result'];point=solved['pump'];values=result['amounts']
                walls=[values[3*model.n+j]/volume for j,volume in enumerate(model.wall_volumes)]
                net=math.fsum(values[3*model.n:])-math.fsum(y[3*model.n:])
                assert result['minimum_seen']>=DESIGN['minimum_amount_tolerance_umol']
                assert result['max_oxygen_error']<DESIGN['inventory_tolerance_umol'] and result['max_site_error']<DESIGN['inventory_tolerance_umol']
                assert point['actual_pressure_kpa']<=caps.pressure_kpa*(1+DESIGN['pump_relative_tolerance'])
                assert point['actual_hydraulic_power_mw']<=caps.hydraulic_power_mw*(1+DESIGN['pump_relative_tolerance'])
                baseline=next(r for r in A_ROWS if r['condition']==cond['name'] and r['time_s']==duration)
                difference=max(abs(a-b) for a,b in zip(values,baseline['final_amounts']))
                if ratio==1:assert difference<=DESIGN['matched_A_full_state_tolerance_umol']
                rows.append({'condition':cond['name'],'resistance_ratio':ratio,'time_s':duration,
                    'configuration':solved['configuration'],**point,
                    'initial_free_concentration':cond['free_concentration'],'initial_site_concentration':cond['site_concentration'],'initial_occupied_fraction':cond['bound_fraction'],
                    'initial_oxygen_umol':oxygen,'initial_sites_umol':sites,
                    'initial_free_umol':math.fsum(y[:model.n]),'initial_bound_umol':math.fsum(y[model.n:2*model.n]),'initial_empty_sites_umol':math.fsum(y[2*model.n:3*model.n]),
                    'initial_wall_umol':math.fsum(y[3*model.n:-1]),'initial_consumed_umol':y[-1],
                    'wall_concentrations':walls,'distal_wall_concentration':walls[-1],'minimum_wall_concentration':min(walls),
                    'consumed_umol':values[-1],'net_wall_transfer_umol':net,'final_amounts':list(values),
                    'A_fixed_flow_state_difference_umol':difference,
                    **{k:v for k,v in result.items() if k!='amounts'}})
    assert len(rows)==DESIGN['row_count']==27
    assert len({(r['condition'],r['resistance_ratio'],r['time_s']) for r in rows})==27
    contrasts=[]
    def contrast(kind,row,base,base_label):
        entry={'comparison':kind,'condition':row['condition'],'resistance_ratio':row['resistance_ratio'],'time_s':row['time_s'],'baseline':base_label,
               'case_initial_oxygen_umol':row['initial_oxygen_umol'],'baseline_initial_oxygen_umol':base['initial_oxygen_umol'],
               'case_flow_ml_s':row['flow_ml_s'],'baseline_flow_ml_s':base.get('flow_ml_s',.4)}
        for endpoint in ENDPOINTS:
            basevalue=base['total_wall_transfer_umol'] if endpoint=='net_wall_transfer_umol' and 'total_wall_transfer_umol' in base else base[endpoint]
            entry[endpoint+'_difference']=row[endpoint]-basevalue
        contrasts.append(entry)
    for row in rows:
        same=next(r for r in rows if r['condition']=='no_sites' and r['resistance_ratio']==row['resistance_ratio'] and r['time_s']==row['time_s'])
        base=next(r for r in rows if r['condition']=='no_sites' and r['resistance_ratio']==1 and r['time_s']==row['time_s'])
        if row['condition']=='no_sites' and row['resistance_ratio']!=1:contrast('resistance_only_no_sites',row,base,'no_sites_R0')
        if row['condition']!='no_sites':
            contrast('within_resistance_inventory_binding',row,same,'no_sites_same_R')
            if row['resistance_ratio']!=1:contrast('assigned_resistance_penalty',row,base,'no_sites_R0')
        baseline=next(r for r in A_ROWS if r['condition']==row['condition'] and r['time_s']==row['time_s'])
        contrast('prescribed_flow_A_ablation',row,baseline,'A_same_condition_Q0.4')
    assert len(contrasts)==63
    fields=['condition','resistance_ratio','resistance_kpa_s_per_ml','time_s','flow_ml_s','pressure_cap_kpa','hydraulic_power_cap_mw','actual_pressure_kpa','actual_hydraulic_power_mw','active_constraint','initial_free_concentration','initial_site_concentration','initial_occupied_fraction','initial_oxygen_umol','initial_sites_umol','initial_free_umol','initial_bound_umol','initial_empty_sites_umol',*ENDPOINTS,'steps','actual_dt','exit_bound','minimum_seen','max_oxygen_error','max_site_error','A_fixed_flow_state_difference_umol']
    write_csv(out/'comparison.csv',rows,fields)
    write_csv(out/'contrasts.csv',contrasts,list(contrasts[0]))
    check_freeze('FREEZE.json');check_freeze('IMPLEMENTATION_FREEZE.json');preserved=verify_a()
    record={'study':'AB-MPB1B','status':'Executed frozen synthetic comparison; independent review pending','rows':rows,'contrasts':contrasts,
        'row_count':len(rows),'contrast_count':len(contrasts),'A_manifest_members_unchanged':preserved,
        'pump_sha256':sha(ROOT/'pump.py'),'test_sha256':sha(ROOT/'test_pump.py'),'design_sha256':sha(ROOT/'STUDY_DESIGN.json'),
        'freeze_sha256':sha(ROOT/'FREEZE.json'),'implementation_freeze_sha256':sha(ROOT/'IMPLEMENTATION_FREEZE.json'),
        'max_oxygen_error_umol':max(r['max_oxygen_error'] for r in rows),'max_site_error_umol':max(r['max_site_error'] for r in rows),
        'minimum_seen':min(r['minimum_seen'] for r in rows),'max_matched_A_state_difference_umol':max(r['A_fixed_flow_state_difference_umol'] for r in rows if r['resistance_ratio']==1),
        'resources':{'cpu_seconds':time.process_time()-cpu,'internal_wall_seconds':time.perf_counter()-start},
        'limits':['Synthetic R, no empirical viscosity or hardware inference','Simultaneous caps, different active constraints; actual pressure and power are not both matched','Inventory/partition and resistance comparisons remain separate','Wall sink does not imply tissue growth or human compatibility','No electrical-power, thermal or pump-efficiency model']}
    with (out/'numerical_receipt.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps({k:record[k] for k in ('row_count','contrast_count','A_manifest_members_unchanged','max_oxygen_error_umol','max_site_error_umol','max_matched_A_state_difference_umol','resources')}))
if __name__=='__main__':main()
