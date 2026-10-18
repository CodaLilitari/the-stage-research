"""Standard-library-only replay of frozen, binary64-rounded reference fixtures."""
import hashlib,json,math,unittest
from pathlib import Path
from benchmark import exact_state,propagator,equilibrium_state,backward_euler,exact_fluxes,geometry_to_rates
ROOT=Path(__file__).resolve().parent
class PortableTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cfg=json.loads((ROOT/'FROZEN_CASES.json').read_text())
  cls.cases={x['id']:x for x in cls.cfg['cases']}
  cls.golden=json.loads((ROOT/'GOLDEN_STATES.json').read_text())
 def test_frozen_hash(self):
  self.assertEqual(hashlib.sha256((ROOT/'FROZEN_CASES.json').read_bytes()).hexdigest(),self.golden['frozen_cases_sha256'])
 def test_all_198_states_and_rates(self):
  for row in self.golden['rows']:
   with self.subTest(case=row['case_id'],fraction=row['fraction']):
    v=self.cases[row['case_id']]
    a,k,g,c0=map(float,[v['alpha_s_inv'],v['k_s_inv'],v['gamma'],v['c0_mol_m3']])
    c,b=exact_state(a,k,g,row['t_s'],c0);s,r=exact_fluxes(a,k,g,row['t_s'],c0)
    for got,key,scale in [(c,'c_ref',c0 or 1.),(b,'b_ref',max(c0,g*c0) or 1.),(s,'sink_ref',a*c0 or 1.),(r,'release_ref',a*c0 or 1.)]:
     self.assertLessEqual(abs(got-row[key]),2e-13*scale+3e-12*abs(row[key]))
 def test_repeated_eigenvalue_offdiagonal(self):
  p=propagator(1.,1.,0.,1.)
  self.assertAlmostEqual(p[0][1],math.exp(-1.),places=15)
 def test_no_binding_capacity_all_rates(self):
  for cid in ['C01','C02','C03']:
   v=self.cases[cid];c,b=exact_state(float(v['alpha_s_inv']),float(v['k_s_inv']),0.,1.)
   self.assertAlmostEqual(c,math.exp(-1.),places=15);self.assertEqual(b,0.)
 def test_k_zero_keeps_storage_inaccessible(self):
  c,b=exact_state(1.,0.,4.,1.)
  self.assertEqual(b,4.);self.assertAlmostEqual(c,math.exp(-1.),places=15)
  self.assertNotEqual(c,equilibrium_state(1.,4.,1.)[0])
 def test_be_positive_conservative(self):
  for cid,v in self.cases.items():
   with self.subTest(case=cid):
    a,k,g,t,c0=map(float,[v['alpha_s_inv'],v['k_s_inv'],v['gamma'],v['T_s'],v['c0_mol_m3']])
    z=backward_euler(a,k,g,t,128,c0)
    self.assertGreaterEqual(z['min_state'],0.)
    self.assertLessEqual(abs(z['global_residual']),5e-10*((1+g)*c0 or 1.))
 def test_negative_and_nonfinite_inputs_rejected(self):
  for index in range(4):
   for bad in [-1.,float('nan'),float('inf')]:
    x=[1.,1.,4.,1.];x[index]=bad
    with self.subTest(index=index,bad=str(bad)),self.assertRaises(ValueError):propagator(*x)
  for bad in [-1.,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):exact_state(1.,1.,4.,1.,bad)
 def test_unsupported_zero_flow_rejected(self):
  with self.assertRaises(ValueError):geometry_to_rates(1e-7,1e-3,1e-3,0.,5e-5)
 def test_segment_count_validation(self):
  for n in [0,-1,True,1.5]:
   with self.assertRaises(ValueError):backward_euler(1.,1.,4.,1.,n)
 def test_rate_overflow_is_explicit(self):
  with self.assertRaises(OverflowError):propagator(1.,1e308,4.,1.)
if __name__=='__main__':unittest.main(verbosity=2)
