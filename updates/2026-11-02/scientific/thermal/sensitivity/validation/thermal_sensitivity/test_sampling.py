"""Unit tests for sampling.py (Morris and Sobol estimators)."""
import math
import unittest

import sampling as smp


class SamplingTests(unittest.TestCase):
    def test_seed_derivation_is_deterministic_and_distinct(self):
        self.assertEqual(smp.derive_seed(1, "a"), smp.derive_seed(1, "a"))
        self.assertNotEqual(smp.derive_seed(1, "a"), smp.derive_seed(1, "b"))
        self.assertEqual(smp.rng_for(7).random(), smp.rng_for(7).random())

    def test_latin_hypercube_stratification(self):
        n, k = 16, 3
        pts = smp.latin_hypercube(n, k, smp.rng_for("lhs"))
        self.assertEqual(len(pts), n)
        for j in range(k):
            strata = sorted(int(pt[j] * n) for pt in pts)
            self.assertEqual(strata, list(range(n)))
            self.assertTrue(all(0.0 <= pt[j] < 1.0 for pt in pts))

    def test_morris_trajectory_structure(self):
        k, r, p = 5, 6, 4
        trajs = smp.morris_trajectories(k, r, p, smp.rng_for("m"))
        delta = smp.morris_delta(p)
        for tr in trajs:
            self.assertEqual(len(tr["points"]), k + 1)
            self.assertEqual(sorted(i for i, _ in tr["moves"]), list(range(k)))
            for (i, step), before, after in zip(tr["moves"], tr["points"], tr["points"][1:]):
                self.assertAlmostEqual(after[i] - before[i], step, places=12)
                self.assertAlmostEqual(abs(step), delta, places=12)
                for j in range(k):
                    if j != i:
                        self.assertEqual(after[j], before[j])
                    self.assertTrue(0.0 <= after[j] <= 1.0)
        with self.assertRaises(ValueError):
            smp.morris_trajectories(2, 1, 3, smp.rng_for("odd"))

    def test_morris_linear_exact_ac5(self):
        factors = [("x1", 0.0, 1.0), ("x2", -2.0, 2.0), ("x3", 0.0, 1.0)]
        # per unit of normalized range: x1 coefficient 2, x2 coefficient -3*4 = -12, x3 0.5
        res = smp.run_morris(factors, lambda v: {"f": 1.0 + 2.0 * v["x1"] - 3.0 * v["x2"] + 0.5 * v["x3"]},
                             ("test", "linear"), 8, 4)
        eff = res["effects"]["f"]
        for name, c in (("x1", 2.0), ("x2", -12.0), ("x3", 0.5)):
            self.assertAlmostEqual(eff[name]["mu"], c, delta=1e-9)
            self.assertAlmostEqual(eff[name]["mu_star"], abs(c), delta=1e-9)
            self.assertLessEqual(eff[name]["sigma"], 1e-9)
            self.assertEqual(eff[name]["count"], 8)
        self.assertEqual([r["factor"] for r in res["ranking_by_mu_star"]["f"]], ["x2", "x1", "x3"])
        self.assertEqual(res["evaluations"], 8 * 4)

    def test_sobol_test_function_ac5(self):
        factors = [("x1", 0.0, 1.0), ("x2", 0.0, 1.0), ("x3", 0.0, 1.0)]
        res = smp.run_sobol(factors, lambda v: {"f": v["x1"] + 2.0 * v["x2"] * v["x3"]}, ("test", "sobol"), 4096)
        S, ST = res["indices"]["f"]["S"], res["indices"]["f"]["ST"]
        for name, s, st in (("x1", 0.3, 0.3), ("x2", 0.3, 0.4), ("x3", 0.3, 0.4)):
            self.assertAlmostEqual(S[name], s, delta=0.05)
            self.assertAlmostEqual(ST[name], st, delta=0.05)
        self.assertAlmostEqual(res["indices"]["f"]["variance"], 5.0 / 18.0, delta=0.01)
        self.assertEqual(res["evaluations"], 5 * 4096)

    def test_sobol_constant_output(self):
        res = smp.run_sobol([("x1", 0.0, 1.0)], lambda v: {"f": 3.0}, ("test", "const"), 16)
        self.assertIsNone(res["indices"]["f"]["S"]["x1"])
        self.assertTrue(res["sanity"]["f"]["constant_output"])

    def test_reproducibility_ac6(self):
        factors = [("a", 0.0, 1.0), ("b", 1.0, 3.0)]
        f = lambda v: {"g": math.sin(v["a"]) * v["b"]}  # noqa: E731
        m1, m2 = (smp.run_morris(factors, f, ("seed", "x"), 5, 4) for _ in range(2))
        s1, s2 = (smp.run_sobol(factors, f, ("seed", "x"), 32) for _ in range(2))
        self.assertEqual(m1, m2)
        self.assertEqual(s1, s2)
        self.assertNotEqual(m1["design_sha256"], smp.run_morris(factors, f, ("seed", "y"), 5, 4)["design_sha256"])
        self.assertNotEqual(s1["design_sha256"], smp.run_sobol(factors, f, ("seed", "y"), 32)["design_sha256"])


if __name__ == "__main__":
    unittest.main()
