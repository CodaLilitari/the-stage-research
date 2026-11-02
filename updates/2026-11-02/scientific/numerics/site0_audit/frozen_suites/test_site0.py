# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), native agent stage_budget_runner.
import math
import unittest
from site0 import Vessel
from validation_helpers import grid_cases, rk4_bound
import mutants


class SiteTests(unittest.TestCase):
    def close(self, actual, expected, tolerance=2e-13):
        self.assertTrue(math.isclose(actual,expected,rel_tol=tolerance,abs_tol=tolerance),
                        (actual,expected))

    def test_zero_sites_never_bind(self):
        v = Vessel(2,3,0,4,2)
        self.assertEqual(v.at(0,100).free_umol,3)
        self.assertEqual(v.at(0,100).bound_umol,0)
        eq=v.equilibrium()
        self.assertIsNotNone(eq)
        self.assertEqual(eq.bound_umol,0)

    def test_zero_oxygen_leaves_sites_empty(self):
        r = Vessel(2,0,3,4,2).at(0,100)
        self.assertEqual((r.free_umol,r.bound_umol,r.empty_umol),(0,0,3))

    def test_zero_rates_identity_and_no_unique_equilibrium(self):
        v=Vessel(2,3,2,0,0)
        self.assertEqual(v.at(.7,1000),v.at(.7,0))
        self.assertIsNone(v.equilibrium())

    def test_pure_release_matches_exponential(self):
        v=Vessel(2,3,2,0,.8)
        r=v.at(.75,3.7)
        b=.75*math.exp(-.8*3.7)
        self.close(r.bound_umol,b)
        self.close(r.free_umol,3-b)
        self.close(r.empty_umol,2-b)
        eq=v.equilibrium()
        self.assertIsNotNone(eq)
        self.close(eq.bound_umol,0)

    def test_equal_irreversible_roots_have_rational_solution(self):
        r=Vessel(4,2,2,2,0).at(.5,3)
        self.close(r.free_umol,6/13)
        self.close(r.bound_umol,20/13)
        self.close(r.empty_umol,6/13)

    def test_unequal_irreversible_roots_match_separated_solution(self):
        v=Vessel(2,3,1,1,0)
        r=v.at(0,2)
        self.close(r.bound_umol,3*(1-math.exp(-2))/(3-math.exp(-2)))
        eq=v.equilibrium()
        self.assertIsNotNone(eq)
        self.close(eq.bound_umol,1)

    def test_equilibrium_root_and_independent_rate_balance(self):
        v=Vessel(2,3,2,4,2)
        r=v.equilibrium()
        self.assertIsNotNone(r)
        self.close(r.bound_umol,3-math.sqrt(3))
        self.close(r.free_umol,math.sqrt(3))
        self.close(r.empty_umol,math.sqrt(3)-1)
        self.close(4*r.free_umol/2*r.empty_umol-2*r.bound_umol,0)

    def test_stationary_root_and_monotone_approach_from_both_sides(self):
        v=Vessel(2,3,2,2,2)
        for t in (0,1e-5,1,1000):
            self.close(v.at(1,t).bound_umol,1)
        below=[v.at(.2,t).bound_umol for t in (0,.1,1,10)]
        above=[v.at(1.8,t).bound_umol for t in (0,.1,1,10)]
        self.assertTrue(all(x<y<=1 for x,y in zip(below,below[1:])))
        self.assertTrue(all(x>y>=1 for x,y in zip(above,above[1:])))

    def test_initial_slope_uses_declared_volume(self):
        r=Vessel(3,4,2,1.2,.7).at(.6,1e-6)
        self.assertLess(abs((r.bound_umol-.6)/1e-6-1.484),4e-6)

    def test_volume_and_inventory_scaling_preserves_concentrations(self):
        a=Vessel(3,4,2,1.2,.7).at(.6,2)
        b=Vessel(30,40,20,1.2,.7).at(6,2)
        for field in ('free_umol','bound_umol','empty_umol'):
            self.close(getattr(b,field),10*getattr(a,field))

    def test_independent_rk4_refines_toward_analytic_transient(self):
        v=Vessel(3,4,2,1.2,.7)
        target=v.at(.6,2).bound_umol
        errors=[abs(rk4_bound(v,.6,2,n)-target) for n in (20,40,80)]
        for old,new in zip(errors,errors[1:]):
            self.assertGreater(old/new,12)
            self.assertLess(old/new,22)
        self.assertLess(errors[-1],1e-7)

    def test_physical_grid_nonnegative_and_both_totals_conserved(self):
        for v,b,t in grid_cases(Vessel):
            r=v.at(b,t)
            self.assertGreaterEqual(min(r.free_umol,r.bound_umol,r.empty_umol),0)
            self.assertLessEqual(r.bound_umol,min(v.oxygen_umol,v.sites_umol))
            self.close(r.free_umol+r.bound_umol,v.oxygen_umol,3e-13)
            self.close(r.empty_umol+r.bound_umol,v.sites_umol,3e-13)

    def test_rapid_release_approaches_mostly_free_equilibrium(self):
        r=Vessel(2,3,2,1,1e6).at(1,1)
        self.assertLess(r.bound_umol,3e-6)
        self.assertGreater(r.free_umol,2.999997)

    def test_nearly_coalescing_roots_approach_irreversible_limit(self):
        r=Vessel(4,2,2,2,1e-24).at(.5,3)
        self.close(r.free_umol,6/13,1e-12)
        self.close(r.bound_umol,20/13,1e-12)

    def test_very_small_binding_retains_nonzero_equilibrium(self):
        r=Vessel(4,2,3,1e-20,1).equilibrium()
        self.assertIsNotNone(r)
        self.assertTrue(math.isclose(r.bound_umol,1.5e-20,rel_tol=1e-14))

    def test_tiny_time_retains_nonzero_initial_binding(self):
        r=Vessel(4,2,3,1,1).at(0,1e-100)
        self.assertTrue(math.isclose(r.bound_umol,1.5e-100,rel_tol=1e-14))

    def test_irreversible_saturation_limited_by_each_inventory(self):
        for m,s,want in ((3,1,1),(1,3,1),(2,2,2)):
            r=Vessel(2,m,s,1,0).at(0,1e12)
            self.assertGreaterEqual(min(r.free_umol,r.empty_umol),0)
            self.assertLess(abs(r.bound_umol-want),5e-12)

    def test_semigroup_advancing_twice_matches_combined_interval(self):
        v=Vessel(.3,4,2,1.2,.7)
        a=v.at(.6,.07)
        twice=v.at(a.bound_umol,.13)
        once=v.at(.6,.2)
        for field in ('free_umol','bound_umol','empty_umol'):
            self.close(getattr(twice,field),getattr(once,field))

    def test_rejects_invalid_physical_inputs(self):
        for field,value in ((0,0),(0,-1),(1,-1),(2,-1),(3,-1),(4,-1),
                            (0,float('inf')),(1,float('nan')),(2,True)):
            values=[2,3,2,1,.5]
            values[field]=value
            with self.assertRaises(ValueError): Vessel(*values)
        v=Vessel(2,3,2,1,.5)
        for b,t in ((-1,1),(2.1,1),(0,-1),(0,float('inf')),(float('nan'),1)):
            with self.assertRaises(ValueError): v.at(b,t)
        with self.assertRaises(ValueError): Vessel(2,1,3,1,.5).at(1.1,1)

    def test_wrong_volume_conserves_totals_but_fails_transient(self):
        v=Vessel(4,2,2,2,0)
        wrong=mutants.omit_volume(v,.5,3)
        self.close(wrong.free_umol+wrong.bound_umol,2)
        self.close(wrong.empty_umol+wrong.bound_umol,2)
        self.assertGreater(abs(wrong.bound_umol-20/13),.3)
        self.close(v.at(.5,3).bound_umol,20/13)

    def test_concentration_as_site_amount_fails_physical_site_inventory(self):
        v=Vessel(4,2,3,1,.5)
        wrong=mutants.concentration_as_site_amount(v,0,2)
        self.assertGreater(abs(wrong.bound_umol+wrong.empty_umol-3),2)
        right=v.at(0,2)
        self.close(right.bound_umol+right.empty_umol,3)

    def test_independent_amount_clamping_creates_oxygen(self):
        v=Vessel(1,1,3,2,0)
        wrong=mutants.independent_amount_clamp(v,0,1)
        self.close(wrong.free_umol+wrong.bound_umol-1,2)
        right=v.at(0,1)
        self.close(right.free_umol+right.bound_umol,1)
        self.assertLessEqual(right.bound_umol,1)

    def test_empty_sites_are_not_released_oxygen(self):
        v=Vessel(2,2,3,0,1)
        wrong=mutants.empty_sites_create_oxygen(v,1,1)
        self.close(wrong.free_umol+wrong.bound_umol-2,2)
        right=v.at(1,1)
        self.close(right.free_umol+right.bound_umol,2)


if __name__=='__main__':
    unittest.main()
