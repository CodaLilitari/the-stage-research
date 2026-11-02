"""Independent exact-arithmetic comparison and material regression checks.
Executed only under coordinate.py's 60-second child deadline.
"""
import argparse
from contextlib import redirect_stdout
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--candidate',choices=['original','fixed'],default='original')
ARGS=parser.parse_args()


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


mod=load_module('reviewed_thermal',ROOT/ARGS.candidate/'thermal_contract.py')
independent=load_module('exact_reference',ROOT.parent/'thermal'/'thermal_reference.py')
cfg=json.loads((ROOT/'original'/'sample_plan.json').read_text(encoding='utf-8'))
expected_plan=json.loads((ROOT/'expected_plan.json').read_text(encoding='utf-8'))
results=json.loads((ROOT/'execution'/(ARGS.candidate+'_results.json')).read_text(encoding='utf-8'))
observations={}


def exact_case(stack,condition):
    # Derived independently from the declared table/config; no model assembler.
    area=F(str(cfg['geometry']['area_m2']))
    k=F(str(condition.get('k_sil',cfg['materials']['silicone_ref']['k_W_mK'])))
    kfilm=F(str(condition.get('k_film',cfg['materials']['polyimide_film_ref']['k_W_mK'])))
    bias=1+F(str(condition.get('t_bias',0)))
    inner=F(str(stack['t_inner_silicone_m']))*bias*(1+F(str(condition.get('t_dev_inner',0))))
    outer=F(str(stack['t_outer_silicone_m']))*bias*(1+F(str(condition.get('t_dev_outer',0))))
    half_film=F(str(stack['t_film_m']))/(2*kfilm*area)
    common=condition.get('r_c',cfg['contacts']['r_c_m2K_W'])
    rin=F(str(condition.get('r_c_inner',common)))/area
    rout=F(str(condition.get('r_c_outer',common)))/area
    h=F(str(condition.get('h',cfg['boundaries']['h_W_m2K'])))
    convection=1/(h*area)
    a=inner/(k*area)+rin+half_film
    b=outer/(k*area)+rout+half_film+convection
    rear=condition.get('R_rej',cfg['boundaries']['R_rej_K_W'])
    rear=math.inf if rear=='blocked' else F(str(rear))
    power=F(str(condition['P_body']))
    sensor=F(str(condition.get('P_sensor',cfg['sources']['sensor']['P_W'])))
    sol=independent.steady(a,b,rear,power,sensor,25,25,convection)
    expected={'T_H_C':sol['H'],'T_S_C':sol['S'],'T_outer_C':sol['surface'],
              'Q_front_W':sol['front'],'Q_rear_W':sol['rear'],'Q_HS_W':sol['front']-sensor,
              'R_HS_K_W':a,'R_SA_K_W':b,'R_conv_K_W':convection}
    return expected


class ReviewTests(unittest.TestCase):
    def test_36_by_3_plan_and_all_outputs_match_independent_exact_reference(self):
        # Catches missing/altered cases, shared-condition drift and wrong assembly.
        actual_conditions=[{k:v for k,v in c.items() if k!='group'} for c in results['conditions']]
        self.assertEqual(actual_conditions,expected_plan)
        self.assertEqual(len(results['cases']),108)
        by_id={c['case_id']:c for c in results['cases']}
        self.assertEqual(len(by_id),108)
        maxima={k:0.0 for k in exact_case(cfg['stacks'][0],expected_plan[0])}
        for cond in expected_plan:
            for stack in cfg['stacks']:
                key=stack['stack_id']+'__'+cond['condition_id']
                row=by_id[key]
                for field,exact in exact_case(stack,cond).items():
                    error=abs(row[field]-float(exact))
                    maxima[field]=max(maxima[field],error)
                    self.assertLess(error,1e-9,(key,field,error))
        observations['all_108_exact_comparison']={'max_absolute_errors':maxima,'case_count':108,
            'max_internal_energy_residual_W':max(abs(c['energy_residual_W']) for c in results['cases']),
            'summary':results['summary']}

    def test_original_12_frozen_rows_remain_consistent(self):
        frozen=json.loads((ROOT.parent/'thermal'/'reference_results.json').read_text())
        by_id={c['case_id']:c for c in results['cases']}
        maxerr=0.0
        for row in frozen['rows']:
            group='B_rear_blocked' if row['rear_blocked'] else 'A_nominal'
            key=f"{row['stack']}__{group}_P{row['body_power']:g}"
            for their,ours in [('H','T_H_C'),('S','T_S_C'),('surface','T_outer_C'),('front','Q_front_W'),('rear','Q_rear_W')]:
                maxerr=max(maxerr,abs(row[their]-by_id[key][ours]))
        observations['frozen_12_row_max_error']=maxerr
        self.assertLess(maxerr,1e-9)

    def test_parallel_split_validation_uses_only_the_front_branch_power(self):
        R,sol,res=mod._solve(mod._ref_stack(),mod._ref_params(P_sensor=0))
        exact_front=5*R['R_rej_K_W']/(R['R_HS_K_W']+R['R_SA_K_W']+R['R_rej_K_W'])
        expected_drop=exact_front*R['R_HS_K_W']
        observed_drop=res['T_H_C']-res['T_S_C']
        observations['v03']={'actual_drop_K':observed_drop,'correct_front_branch_drop_K':expected_drop,
                             'incorrect_body_power_drop_K':5*R['R_HS_K_W'],
                             'self_check_result':mod.v03_no_sensor_parallel_split()}
        self.assertAlmostEqual(observed_drop,expected_drop,delta=1e-11)
        self.assertTrue(mod.v03_no_sensor_parallel_split()[0])

    def test_disconnected_balanced_sources_cannot_be_a_steady_family(self):
        # Independent node equations are 0=+1 and 0=-1; global zero is insufficient.
        sol=mod.solve_two_node(0,0,0,1,-1,20,30)
        observations['disconnected_balanced_sources']=sol
        self.assertTrue(sol['status'].startswith('no_finite_steady_state'))

    def test_separately_pinned_nodes_are_unique_without_irreducibility(self):
        sol=mod.solve_two_node(0,.5,.25,2,1,20,30)
        observations['separately_pinned']=sol
        self.assertEqual(sol['status'],'solved')
        self.assertAlmostEqual(sol['T_H'],38)
        self.assertAlmostEqual(sol['T_S'],22)

    def test_zero_rear_resistance_does_not_silently_return_nan_as_solved(self):
        # This is outside sample-config admission; either reject or implement pinning.
        try:
            sol=mod.solve_two_node(2,.5,math.inf,2,1,20,30)
        except ValueError as exc:
            observations['zero_rear_resistance']={'rejected':True,'message':str(exc)}
            return
        observations['zero_rear_resistance']={'rejected':False,'finite_temperatures':
                                             all(math.isfinite(sol[k]) for k in ['T_H','T_S'])}
        self.assertAlmostEqual(sol['T_H'],30)
        self.assertAlmostEqual(sol['T_S'],28.4)

    def test_infinite_h_does_not_remove_the_solid_front_resistance(self):
        R,sol,res=mod._solve(mod._ref_stack(),mod._ref_params(h=1e30))
        observations['large_h']={'R_conv_K_W':R['R_conv_K_W'],'R_SA_K_W':R['R_SA_K_W'],
                                 'T_S_C':res['T_S_C'],'T_outer_C':res['T_outer_C']}
        self.assertGreater(R['R_SA_K_W'],.2)
        self.assertGreater(res['T_S_C'],25.1)
        self.assertAlmostEqual(res['T_outer_C'],25,delta=1e-12)

    def test_blocked_exits_and_merge_limits(self):
        self.assertTrue(mod.solve_two_node(2,0,0,1,0,20,20)['status'].startswith('no_finite'))
        self.assertTrue(mod.solve_two_node(2,0,0,0,0,20,20)['status'].startswith('nonunique_constant'))
        self.assertTrue(mod.solve_two_node(2,0,0,1,-1,20,20)['status'].startswith('nonunique_offset'))
        self.assertTrue(mod.solve_two_node(0,0,0,0,0,20,20)['status'].startswith('nonunique_independent'))
        merged=mod.solve_two_node(math.inf,.5,.25,2,1,20,30)
        self.assertAlmostEqual(merged['T_H'],82/3)
        self.assertAlmostEqual(merged['T_S'],82/3)

    def test_existing_output_is_preserved_without_force(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'execution') as tmp:
            target=Path(tmp)/'output.json'; target.write_text('sentinel')
            with self.assertRaises(OSError):
                mod.run_study(str(ROOT/'original'/'sample_plan.json'),str(target))
            self.assertEqual(target.read_text(),'sentinel')

    def test_no_force_creation_race_cannot_overwrite_another_writer(self):
        # Simulate creation after the preflight exists check; the final open must be exclusive.
        with tempfile.TemporaryDirectory(dir=ROOT/'execution') as tmp:
            target=Path(tmp)/'output.json'; target.write_text('concurrent-writer-sentinel')
            real_exists=os.path.exists
            def stale_exists(path):
                return False if os.path.abspath(path)==str(target) else real_exists(path)
            error=None
            with patch.object(mod.os.path,'exists',side_effect=stale_exists),redirect_stdout(io.StringIO()):
                try: mod.run_study(str(ROOT/'original'/'sample_plan.json'),str(target))
                except OSError as exc: error=type(exc).__name__
            preserved=target.read_text()=='concurrent-writer-sentinel'
            observations['overwrite_race']={'error_type':error,'sentinel_preserved':preserved}
            self.assertTrue(preserved)

    def test_force_cannot_overwrite_the_input_config(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'execution') as tmp:
            target=Path(tmp)/'config.json'; original=(ROOT/'original'/'sample_plan.json').read_bytes()
            target.write_bytes(original); error=None
            with redirect_stdout(io.StringIO()):
                try: mod.run_study(str(target),str(target),force=True)
                except OSError as exc: error=type(exc).__name__
            after=target.read_bytes()
            observations['input_overwrite']={'error_type':error,'input_preserved':after==original,
                'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest()}
            self.assertEqual(after,original)


if __name__=='__main__':
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests))
    observations.update(candidate=ARGS.candidate,tests_run=result.testsRun,
                        failures=[str(t) for t,_ in result.failures],errors=[str(t) for t,_ in result.errors])
    (ROOT/'execution'/(ARGS.candidate+'_independent_review.json')).write_text(
        json.dumps(observations,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(stream.getvalue())
    raise SystemExit(not result.wasSuccessful())
