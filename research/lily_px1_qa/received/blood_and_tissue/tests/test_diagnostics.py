import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from diagnostics import exact_transport, integrate, saturation, equilibrium_unloading, kinetic_release_fraction

class DiagnosticsTests(unittest.TestCase):
    def test_no_wall_transfer(self):
        r=exact_transport(4,0)
        self.assertEqual(r['channel_out'],1)
        self.assertEqual(r['extraction_fraction'],0)
    def test_counterexample(self):
        a,b=exact_transport(4,.25),exact_transport(4,.9)
        self.assertLess(b['distal_tissue'],a['distal_tissue'])
        self.assertGreater(b['extraction_fraction'],a['extraction_fraction'])
    def test_fixed_supply(self):
        self.assertLess(exact_transport(4,.25)['clamped_supply_tissue'],exact_transport(4,.9)['clamped_supply_tissue'])
    def test_nondimensional_no_depletion(self):
        self.assertEqual(exact_transport(0,.9)['channel_out'],1)
    def test_grid_convergence(self):
        a,b=integrate(4,.9,32),integrate(4,.9,64)
        self.assertLess(b['channel_out_abs_error'],a['channel_out_abs_error']/10)
    def test_mass_balance(self):
        self.assertLess(integrate(8,.99,512)['mass_balance_abs_error'],1e-8)
    def test_distal_optimum(self):
        self.assertEqual(exact_transport(4,.25)['distal_derivative_wrt_f'],0)
    def test_hill_half_saturation(self):
        self.assertEqual(saturation(26,26,2.7),.5)
    def test_hill_zero(self):
        self.assertEqual(saturation(0,26,2.7),0)
    def test_hill_optimum(self):
        p=math.sqrt(100*40)
        best=equilibrium_unloading(100,40,p,2.7)
        self.assertGreater(best,equilibrium_unloading(100,40,p/2,2.7))
        self.assertGreater(best,equilibrium_unloading(100,40,p*2,2.7))
    def test_kinetics(self):
        self.assertEqual(kinetic_release_fraction(0),0)
        self.assertLess(kinetic_release_fraction(.1),kinetic_release_fraction(1))
        self.assertAlmostEqual(kinetic_release_fraction(100),1)
    def test_bad_numeric_inputs(self):
        for args in [(math.nan,.5),(-1,.5),(1,2)]:
            with self.assertRaises(ValueError): exact_transport(*args)
        with self.assertRaises(ValueError): integrate(1,.5,3)
        with self.assertRaises(ValueError): saturation(1,0,2.7)
        with self.assertRaises(ValueError): equilibrium_unloading(20,40,26,2.7)
        with self.assertRaises(ValueError): kinetic_release_fraction(-1)

if __name__=='__main__': unittest.main()
