# SPDX-License-Identifier: Apache-2.0
import unittest,importlib.util,json,copy,io,tempfile,math
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('thermal_candidate',ROOT/'fixed/thermal_contract.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE=json.loads((ROOT/'original/sample_plan.json').read_text())
class AuditTests(unittest.TestCase):
    def test_unique_extreme_solution_survives_unavailable_gauss_check(self):
        try:s=m.solve_two_node(5,0,1e-17,5,.1,25,25)
        except Exception as e:self.fail('Solvable admitted case crashed: '+type(e).__name__)
        self.assertEqual(s['status'],'solved');self.assertIsNone(s['T_H_gauss'])
        self.assertAlmostEqual(s['T_H']/5.1e17,1,delta=1e-12);self.assertAlmostEqual(s['T_S']/5.1e17,1,delta=1e-12)
    def assert_rejected_config(self,cfg):
        try:m.validate_config(cfg)
        except m.ConfigError:return
        except Exception as e:self.fail('Wrong exception '+type(e).__name__)
        self.fail('Malformed configuration admitted')
    def test_top_section_types(self):
        for name in ('geometry','materials','contacts','thickness_perturbation','boundaries','sources','comparators','numerics'):
            with self.subTest(section=name):
                cfg=copy.deepcopy(BASE);cfg[name]=[];self.assert_rejected_config(cfg)
    def test_nested_section_types(self):
        for parent,key in [('materials','silicone_ref'),('materials','polyimide_film_ref'),('sources','body'),('sources','sensor')]:
            with self.subTest(parent=parent,key=key):
                cfg=copy.deepcopy(BASE);cfg[parent][key]=[];self.assert_rejected_config(cfg)
    def test_stack_object_and_identifier_types(self):
        for bad in (None,[],{'stack_id':[]}):
            with self.subTest(bad=bad):
                cfg=copy.deepcopy(BASE);cfg['stacks'][0]=bad;self.assert_rejected_config(cfg)
    def test_huge_integer_is_configuration_error(self):
        cfg=copy.deepcopy(BASE);cfg['geometry']['area_m2']=10**399;self.assert_rejected_config(cfg)
    def test_positive_h_underflow_exits_cleanly_without_output(self):
        cfg=copy.deepcopy(BASE);cfg['boundaries']['h_W_m2K']=5e-324;cfg['boundaries']['h_assumed_range_W_m2K']=[5e-324,15]
        with tempfile.TemporaryDirectory(dir=ROOT/'execution') as tmp:
            inp=Path(tmp)/'input.json';out=Path(tmp)/'out.json';inp.write_text(json.dumps(cfg));err=io.StringIO()
            try:
                with redirect_stdout(io.StringIO()),redirect_stderr(err):code=m.main(['run','--config',str(inp),'--out',str(out)])
            except Exception as e:self.fail('CLI leaked '+type(e).__name__)
            self.assertEqual(code,1);self.assertTrue(err.getvalue().startswith('error:'));self.assertFalse(out.exists())
    def test_equal_film_claim_is_enforced(self):
        cfg=copy.deepcopy(BASE);cfg['stacks'][1]['t_film_m']=1e-4;self.assert_rejected_config(cfg)
    def test_normal_sample_and_finite_gauss_control(self):
        m.validate_config(copy.deepcopy(BASE));s=m.solve_two_node(5,.5,.25,5,.1,25,25)
        self.assertIsNotNone(s['T_H_gauss']);self.assertAlmostEqual(s['T_H_gauss'],s['T_H'],delta=1e-9)
if __name__=='__main__':unittest.main(verbosity=2)
