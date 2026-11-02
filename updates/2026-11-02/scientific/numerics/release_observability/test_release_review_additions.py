"""Unit tests for release_review_additions.py (standard library only).
Run:  python -m unittest test_release_review_additions -v
"""
import json
import math
import unittest

import release_model as rm
import release_study as rs
import release_review_additions as ra


class TestHelpers(unittest.TestCase):
    def test_mean_exp_on_grid_matches_brute_force(self):
        for rate, T, n in ((5.83, 1.0, 7), (500.8, 1.0, 64), (50.0, 3.0, 1024), (0.4, 0.5, 16), (1e5, 1.0, 1)):
            brute = math.fsum(math.exp(-rate * i * T / n) for i in range(1, n + 1)) / n
            closed = ra.mean_exp_on_grid(rate, T, n)
            self.assertLessEqual(abs(closed - brute), 1e-12 * brute + 1e-300)
        with self.assertRaises(ValueError):
            ra.mean_exp_on_grid(1.0, 1.0, 0)

    def test_profile_fits_pure_equilibrium_exactly(self):
        grid = rs.time_grid(1.0, 32, 0.0)
        r = 0.2
        xc = [0.9 * math.exp(-r * t) for t in grid]
        xb = [0.9 * math.exp(-r * t) for t in grid]
        self.assertLess(ra.profile_residual_rms(xc, xb, grid, r, True), 1e-15)
        best, r_best = ra.profile_minimum(xc, xb, grid, 0.3, True)   # centre deliberately off
        self.assertLess(best, 1e-9)
        self.assertAlmostEqual(r_best / r, 1.0, delta=1e-4)
        xb2 = [0.7 * math.exp(-r * t) for t in grid]
        self.assertLess(ra.profile_residual_rms(xc, xb2, grid, r, False), 1e-15)
        self.assertGreater(ra.profile_residual_rms(xc, xb2, grid, r, True), 1e-3)

    def test_profile_minimum_never_above_author_bound(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        grid = rs.time_grid(1.0, 64, 0.0)
        arr = rs.evaluate_arrays(p, m, grid)
        bound_gk = rs.rms(arr["rc"] + arr["rb"])
        bound_gf = rs.rms(arr["fc"] + arr["fb"])
        xc, xb = ra.relative_finite_data(p, m, grid)
        prof_gk, _ = ra.profile_minimum(xc, xb, grid, m.r_s, True)
        prof_gf, _ = ra.profile_minimum(xc, xb, grid, m.r_s, False)
        self.assertLessEqual(prof_gk, bound_gk * (1.0 + 1e-9))
        self.assertLessEqual(prof_gf, bound_gf * (1.0 + 1e-9) + 1e-12)
        self.assertGreater(prof_gk, 0.5 * bound_gk)

    def test_filter_geometry_consistent_with_study_indices(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[1] for t in rs.time_grid(1.0, 64, 0.0)]
        nw2, ndtd2 = ra.filter_geometry(delta)
        ci = rs.computed_flux_indices(delta)
        self.assertAlmostEqual(nw2 / math.sqrt(ndtd2) / ci["d_real"], 1.0, delta=1e-12)
        self.assertAlmostEqual(math.sqrt(nw2 / 2.0) / ci["d_naive"], 1.0, delta=1e-12)

    def test_naive_filter_stats_deterministic_and_variance_sane(self):
        delta = [1e-3 * (i / 15.0) ** 2 for i in range(16)]
        sigma = 1e-4
        a = ra.naive_filter_stats(delta, sigma, 200, 99)
        b = ra.naive_filter_stats(delta, sigma, 200, 99)
        self.assertEqual(a, b)
        nw2, ndtd2 = ra.filter_geometry(delta)
        self.assertGreater(2.0 * nw2 / ndtd2, 1.0)        # smooth delta: naive variance overstates
        var_ratio = a[1] / (sigma * sigma * ndtd2)
        self.assertLess(abs(var_ratio - 1.0), 0.5)         # 400 draws: SE ~ 7%
        self.assertTrue(0.0 <= a[0] <= 1.0)


class TestPipeline(unittest.TestCase):
    def test_quick_pipeline_produces_all_additions(self):
        grids = [1, 4, 16, 64]
        res = rs.run_study(grid_sizes=grids, reps=20)
        adds = ra.evaluate_additions(res, grids, reps=20)
        ids = [a["id"] for a in adds]
        for want in ("N1a", "N1b", "N1c", "N2a", "N2b", "N2c", "N3", "S1", "S2", "S3"):
            self.assertIn(want, ids)
        for a in adds:
            self.assertIn("passed", a)
            self.assertIn("details", a)
        json.dumps(adds, default=str)
        n3 = next(a for a in adds if a["id"] == "N3")
        self.assertIn("A:100.0", n3["details"])
        self.assertIsInstance(n3["details"]["A:100.0"], dict)


if __name__ == "__main__":
    unittest.main()
