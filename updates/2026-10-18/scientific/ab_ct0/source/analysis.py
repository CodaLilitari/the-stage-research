"""Saved-result checks and deterministic contrast selection; no transport calls."""
import math


def matching(rows, **fields):
    found = [r for r in rows if all(r[k] == v for k, v in fields.items())]
    if len(found) != 1:
        raise ValueError(f'Expected one match: {fields}, got {len(found)}')
    return found[0]


def anchor_ids(primary):
    return {p: matching(primary, profile=p, mu=1, P=5e-5, flow_mode='envelope')['case_id'] for p in ('D', 'L', 'H_eq')}


def field_distance(a, b):
    if a['y_cell_centers'] != b['y_cell_centers'] or [r['z'] for r in a['stations']] != [r['z'] for r in b['stations']]:
        raise ValueError('Field comparison requires matching coordinates')
    return max(abs(x-y) for ra, rb in zip(a['stations'], b['stations'])
               for x, y in zip([ra['c_lumen']]+ra['tissue'], [rb['c_lumen']]+rb['tissue']))


def analytic_error(result, cfg):
    s = result['summary']
    errors = []
    if s['reaction'] == 'linear':
        gamma = math.sqrt(s['kt'] / cfg['D'])
        G = 1 / (1 / s['P'] + 1 / (cfg['D'] * gamma * math.tanh(gamma * cfg['d'])))
        denom = math.cosh(gamma * cfg['d']) + cfg['D'] * gamma / s['P'] * math.sinh(gamma * cfg['d'])
        for row in result['stations']:
            bulk = cfg['cin'] * math.exp(-cfg['w'] * G * row['z'] / (s['Q'] * s['beta']))
            errors.append(abs(row['c_lumen'] - bulk))
            errors.extend(abs(c - bulk * math.cosh(gamma * (cfg['d']-y)) / denom)
                          for y, c in zip(result['y_cell_centers'], row['tissue']))
    elif s['reaction'] == 'zero_order' and s['clamped']:
        for row in result['stations']:
            errors.extend(abs(c - (cfg['cin'] - s['Rmax'] * cfg['d']/s['P'] - s['Rmax']/cfg['D'] * (cfg['d']*y-y*y/2)))
                          for y,c in zip(result['y_cell_centers'],row['tissue']))
    else:
        raise ValueError('No declared continuum control for this case')
    return max(errors)


def check_controls(results, primary, cfg, reference, include_dependencies=True):
    checks=[]
    def add(name, ok, **detail):
        checks.append(dict(name=name, passed=bool(ok), **detail))
    cs={v['summary']['purpose']:v for v in results.values() if v['summary']['phase']=='control'}
    floor=cfg['domain_relative_tol']*cfg['cin']
    fluxfloor=cfg['zero_flux_relative_tol']*cfg['Qref']*cfg['cin']
    z=cs['zero_demand']; s=z['summary']
    uniform=max(abs(v-cfg['cin']) for row in z['stations'] for v in [row['c_lumen']]+row['tissue'])
    add('zero_demand_uniform',uniform<=floor,error=uniform)
    add('zero_demand_zero_flux',max(abs(s[k]) for k in ('uptake_mol_s','wall_mol_s','lumen_loss_mol_s'))<=fluxfloor)
    add('zero_demand_bound_unchanged',abs(s['outlet_bound']-s['inlet_bound'])<=floor)
    z=cs['no_wall'];s=z['summary']
    add('no_wall_isolated_tissue_zero',max(abs(c) for r in z['stations'] for c in r['tissue'])<=floor)
    add('no_wall_lumen_unchanged',all(abs(r['c_lumen']-cfg['cin'])<=floor for r in z['stations']))
    add('no_wall_zero_flux',max(abs(s[k]) for k in ('uptake_mol_s','wall_mol_s','lumen_loss_mol_s'))<=fluxfloor)
    errors={}
    for label in ('linear_sink_beta1','linear_sink_beta5','clamped_zero_order'):
        e0=analytic_error(cs[label+'_base'],cfg);e1=analytic_error(cs[label+'_doubled'],cfg)
        errors[label]={'base':e0,'doubled':e1}
        add(label+'_continuum',e1<=cfg['analytic_doubled_concentration_tol'] and (e1<e0 or max(e0,e1)<=floor),base_error=e0,doubled_error=e1)
    a=cs['clamped_zero_order_doubled']['summary'];b=cs['clamped_zero_order_larger_wall']['summary']
    add('clamped_local_wall_monotonic',b['minimum_tissue']>=a['minimum_tissue']-floor)
    if include_dependencies:
        ids=anchor_ids(primary)
        base=results[ids['D']]['summary'];ref=reference['row_as_original_strings']
        for out,col in [('minimum_tissue','minimum_free_tissue_mol_m3'),('outlet_free','outlet_free_mol_m3')]:
            err=abs(base[out]-float(ref[col]))
            add('saved_PF0_'+out,err<=cfg['saved_pf0_concentration_tol'],error=err)
        eq=results[ids['H_eq']]
        e100=field_distance(cs['finite_H_high_rate100'],eq);e1000=field_distance(cs['finite_H_high_rate1000'],eq)
        add('large_k_approaches_equilibrium',e1000<e100 or max(e100,e1000)<=floor,error_k100=e100,error_k1000=e1000)
        err=field_distance(cs['linear_Q_beta_equivalence'],results[ids['L']])
        add('linear_Q_beta_equivalence',err<=cfg['saved_pf0_concentration_tol'],error=err)
    return {'checks':checks,'passed':all(x['passed'] for x in checks),'analytic_errors':errors,
            'dependency_primary_ids':anchor_ids(primary),'dependencies_checked':include_dependencies}


def check_primary(results, primary, cfg):
    rows=[results[c['case_id']]['summary'] for c in primary]
    checks=[]
    tol=cfg['saved_pf0_concentration_tol']
    for r in rows:
        if r['profile']=='H_finite' and r['k']==0:
            d=matching(rows,profile='D',mu=r['mu'],P=r['P'],flow_mode='envelope')
            dist=field_distance(results[r['case_id']],results[d['case_id']])
            checks.append({'name':'k0_dissolved_match_'+r['case_id'],'passed':dist<=tol,'field_error':dist,'reference':d['case_id']})
            checks.append({'name':'k0_bound_retained_'+r['case_id'],'passed':r['inlet_bound']==r['outlet_bound']})
        if r['flow_mode']=='envelope':
            checks.append({'name':'hydraulic_budget_'+r['case_id'],'passed':not r['pressure_violation'] and not r['power_violation']})
    return {'checks':checks,'passed':all(x['passed'] for x in checks)}


def contrasts(rows, cfg):
    h1=[];h2=[];h3=[]
    for r in rows:
        if r['phase']=='A' and r['profile'] in ('L','H_eq') and r['mu']==4 and r['flow_mode']=='envelope':
            d=matching(rows,phase='A',profile='D',mu=1,P=r['P'],flow_mode='envelope')
            h1.append({'left':d['case_id'],'right':r['case_id'],'distal_delta':r['distal_tissue']-d['distal_tissue']})
        if r['profile']=='H_finite' and r['k']>0:
            e=matching(rows,profile='H_eq',mu=r['mu'],P=r['P'],flow_mode='envelope')
            h2.append({'left':r['case_id'],'right':e['case_id'],'uptake_delta':e['uptake_mol_s']-r['uptake_mol_s'],
                       'fraction':(e['uptake_mol_s']-r['uptake_mol_s'])/max(abs(e['uptake_mol_s']),cfg['zero_flux_relative_tol']*cfg['Qref']*cfg['cin'])})
    groups={}
    # Fixed global geometry, inlet, Km, Hill law are bound by config.json.
    keys=('profile','mu','flow_mode','Q','k','beta','reaction','Rmax','kt','clamped','ny','nz')
    for r in rows:
        groups.setdefault(tuple(r[k] for k in keys),[]).append(r)
    for group in groups.values():
        group.sort(key=lambda r:(r['P'],r['case_id']))
        for a,b in zip(group,group[1:]):
            if not a['P']<b['P']:
                raise ValueError('Non-unique permeability within H3 key')
            h3.append({'left':a['case_id'],'right':b['case_id'],'distal_delta':b['distal_tissue']-a['distal_tissue'],
                       'uptake_delta':b['uptake_mol_s']-a['uptake_mol_s']})
    return {'H1':h1,'H2':h2,'H3':h3}


def select_refinement(results, primary, cfg):
    rows=[results[c['case_id']]['summary'] for c in primary]
    cc=contrasts(rows,cfg)
    pairs={'H1':min(cc['H1'],key=lambda p:(p['distal_delta'],p['left'],p['right'])),
           'H2':min(cc['H2'],key=lambda p:(-p['fraction'],p['left'],p['right']))}
    increasing=[p for p in cc['H3'] if p['uptake_delta']>0]
    pairs['H3']=min(increasing,key=lambda p:(p['distal_delta'],p['left'],p['right'])) if increasing else min(cc['H3'],key=lambda p:(p['left'],p['right']))
    selected={p[k] for p in pairs.values() for k in ('left','right')}
    fill=sorted(rows,key=lambda r:(-max(r['mass_relative_error'],r['maximum_segment_relative_error']),r['distal_tissue'],r['case_id']))
    for r in fill:
        if len(selected)==6:break
        selected.add(r['case_id'])
    return {'selection':'Prespecified paired selection; diagnostic witnesses, not a random sample','pairs':pairs,'selected_case_ids':sorted(selected),'coarse_contrasts':cc}


def refined_decisions(results, selection, cfg):
    metrics=('distal_tissue','minimum_tissue','uptake_mol_s')
    convergence={}
    for cid in selection['selected_case_ids']:
        stages=[results[cid]['summary'],results[cid+'-R1']['summary'],results[cid+'-R2']['summary']]
        changes={}
        for key in metrics:
            first=abs(stages[1][key]-stages[0][key]);last=abs(stages[2][key]-stages[1][key])
            floor=cfg['zero_flux_relative_tol']*cfg['Qref']*cfg['cin'] if key=='uptake_mol_s' else cfg['domain_relative_tol']*cfg['cin']
            threshold=max(floor,cfg['uptake_refinement_relative_tol']*abs(stages[2][key])) if key=='uptake_mol_s' else cfg['concentration_refinement_tol']
            changes[key]={'base':stages[0][key],'middle':stages[1][key],'fine':stages[2][key],
                          'previous_change':first,'last_change':last,'converged':last<threshold and (last<first or max(first,last)<=floor)}
        convergence[cid]=changes
    decisions={}
    for name,pair in selection['pairs'].items():
        a,b=pair['left'],pair['right']
        cases_converged=all(convergence[cid][metric]['converged'] for cid in (a,b) for metric in metrics)
        keys=('uptake_mol_s',) if name=='H2' else ('distal_tissue','uptake_mol_s') if name=='H3' else ('distal_tissue',)
        diagnostics={}
        for key in keys:
            ca,cb=convergence[a][key],convergence[b][key]
            delta=cb['fine']-ca['fine'];guard=2*max(ca['last_change'],cb['last_change'])
            diagnostics[key]={'fine_delta_right_minus_left':delta,'two_last_change_guard':guard,
                              'resolved':cases_converged and abs(delta)>guard}
        resolved=all(d['resolved'] for d in diagnostics.values())
        expected=(diagnostics['uptake_mol_s']['fine_delta_right_minus_left']>0) if name=='H2' else (diagnostics['distal_tissue']['fine_delta_right_minus_left']<0)
        if name=='H3':expected=expected and diagnostics['uptake_mol_s']['fine_delta_right_minus_left']>0
        decisions[name]={'pair':pair,'both_cases_pass_all_convergence_metrics':cases_converged,'diagnostics':diagnostics,'status':'resolved_selected_witness_supports' if resolved and expected else 'resolved_selected_witness_does_not_support' if resolved else 'unresolved_selected_witness',
                         'scope':'Only selected pairs are refined. Coarse remaining rows do not support a uniform numerical-error or universal absence claim.'}
    return {'convergence':convergence,'decisions':decisions,'secondary_three_way_rank_reversal':'Not evaluated: no extra reserve solves are automatically used; all three refined members would be required.'}
