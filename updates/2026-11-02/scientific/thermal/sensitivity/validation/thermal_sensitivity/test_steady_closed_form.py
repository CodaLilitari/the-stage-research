"""Unit tests for steady_closed_form (thermal-sensitivity-001). Expected values come from Coda's
executed reference and predeclared fixtures, not from the functions under test."""
from fractions import Fraction
import itertools
import math
import unittest

import steady_closed_form as scf

F = Fraction


class ClosedFormTests(unittest.TestCase):
    def test_coda_resistance_fixtures_1_to_7(self):
        s = scf.steady_from_resistances(1, 1, 0, 1, 1, 0)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(2, 3), F(1, 3), F(1, 3), F(2, 3)))
        s = scf.steady_from_resistances(1, 1, 0, 1, 0, 1)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(1, 3), F(2, 3), F(2, 3), F(1, 3)))
        s = scf.steady_from_resistances(1, 1, 0, 1, 0, 0, T_amb=0, T_res=10)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(20, 3), F(10, 3), F(10, 3), F(-10, 3)))
        s = scf.steady_from_resistances(2, 2, 1, None, 1, 2, T_amb=10, T_res=0)  # rear absent, b=3 incl. c=1
        self.assertEqual((s["F"], s["T_S"], s["T_H"], s["T_surface"]), (3, 19, 21, 13))
        s = scf.steady_from_resistances(0, 1, 0, 1, 1, 0)
        self.assertEqual((s["T_H"], s["T_S"]), (F(1, 2), F(1, 2)))
        base = scf.steady_from_resistances(1, 1, 0, 1, 1, 0)
        shifted = scf.steady_from_resistances(1, 1, 0, 1, 1, 0, T_amb=37, T_res=37)
        for k in ("T_H", "T_S", "T_surface"):
            self.assertEqual(shifted[k] - base[k], 37)
        self.assertEqual((shifted["F"], shifted["B"]), (base["F"], base["B"]))

    def test_coda_fixture_8_and_9(self):
        p = scf.make_params("H1", P=5)
        s = scf.steady(p)
        self.assertEqual(s["a"], F(2351, 10800))
        self.assertEqual(s["b"], F(2351, 10800) + F(25, 2))
        self.assertEqual(s["F"], F(1103951, 1613020))
        sym = scf.partials(p, "t_i")["F"] + scf.partials(p, "t_o")["F"]  # = (dF/da + dF/db)/(k_s A)
        self.assertEqual(sym * p["k_s"] * p["A"] * s["D"] ** 2, F(-1895, 100))
        self.assertLess(sym, 0)

    def test_reference_rows_ac1(self):
        rows = scf.reference_rows_check()
        self.assertEqual(len(rows), 12)
        for row in rows:
            self.assertTrue(row["passed"], row)

    def test_internal_identity_T_H_equals_T_res_plus_rB(self):
        for stack in scf.STACKS:
            for P in (1, 5, 10):
                s = scf.steady(scf.make_params(stack, P=P, T_res=30, T_amb=20, h=F("4.5"), r=F(7, 3)))
                self.assertEqual(s["T_H"], s["T_res"] + s["r"] * s["B"])
                self.assertEqual(s["F"] + s["B"], s["P"] + s["J"])

    def test_partials_match_dual_exactly_ac2(self):
        for stack, P, blocked in itertools.product(scf.STACKS, (1, 5, 10), (False, True)):
            p = scf.make_params(stack, P=P, r=None if blocked else 2)
            for x in scf.FACTOR_NAMES:
                if blocked and x == "r":
                    with self.assertRaises(ValueError):
                        scf.partials(p, x)
                    continue
                hand, dual = scf.partials(p, x), scf.partials_by_dual(p, x)
                for k in scf.OUTPUT_KEYS:
                    self.assertEqual(hand[k], dual[k], (stack, P, blocked, x, k))

    def test_partials_match_central_differences(self):
        for stack, blocked in itertools.product(scf.STACKS, (False, True)):
            p = scf.make_params(stack, P=5, r=None if blocked else 2, T_res=27)
            for x in scf.FACTOR_NAMES:
                if blocked and x == "r":
                    continue
                hand, cd = scf.partials(p, x), scf.partials_by_central_difference(p, x)
                for k in scf.OUTPUT_KEYS:
                    self.assertLessEqual(abs(hand[k] - cd[k]), F(1, 10 ** 9) * (1 + abs(hand[k])), (stack, x, k))

    def test_translation_partials(self):
        p = scf.make_params("H2", P=5)
        for k in ("T_surface", "T_S", "T_H"):
            self.assertEqual(scf.partials(p, "T_amb")[k] + scf.partials(p, "T_res")[k], 1)
        pb = scf.make_params("H2", P=5, r=None)
        for k in ("T_surface", "T_S", "T_H"):
            self.assertEqual(scf.partials(pb, "T_amb")[k], 1)
            self.assertEqual(scf.partials(pb, "T_res")[k], 0)

    def test_nominal_reversal_direction(self):
        s1, s3 = (scf.steady(scf.make_params(s, P=5)) for s in ("H1", "H3"))
        self.assertEqual(scf.brute_force_class(s1, s3), "reference")
        self.assertEqual(scf.analytic_class(s1, s3), "reference")
        self.assertEqual(scf.discriminant(s1, s3), scf.symmetric_discriminant(s1, s3))
        self.assertEqual(s1["T_surface"] - s3["T_surface"], s1["c"] * (s1["F"] - s3["F"]))
        self.assertEqual(s1["T_H"] - s3["T_H"], -s1["r"] * (s1["F"] - s3["F"]))

    def test_flip_condition_kappa_and_examples(self):
        self.assertEqual(scf.kappa(1), F(100, 21))
        self.assertEqual(scf.kappa(5), F(100, 101))
        self.assertEqual(scf.kappa(10), F(100, 201))
        flipped = [scf.steady(scf.make_params(s, P=1, h=3, r=F(3, 2))) for s in ("H1", "H3")]
        self.assertEqual(scf.brute_force_class(*flipped), "flipped")
        self.assertEqual(scf.analytic_class(*flipped), "flipped")
        tie = [scf.steady(scf.make_params(s, P=1, h=3, r=F(100, 63))) for s in ("H1", "H3")]  # r = kappa/h exactly
        self.assertEqual(scf.brute_force_class(*tie), "tie")
        self.assertEqual(scf.analytic_class(*tie), "tie")
        blocked = [scf.steady(scf.make_params(s, P=5, r=None)) for s in ("H1", "H3")]
        self.assertEqual(scf.brute_force_class(*blocked), "tie_surface")
        self.assertEqual(scf.analytic_class(*blocked), "tie_surface")

    def test_reversal_condition_vs_brute_force_on_grid(self):
        import thermal_sensitivity as ts
        for mode in ts.MODES:
            for P in (1, 5, 10):
                for blocked in (False, True):
                    g = ts.classify_grid(mode, P, blocked, stride=7)
                    self.assertGreater(g["checked"], 50)
                    self.assertEqual(g["analytic_agreement"], g["checked"], g)
                    self.assertEqual(g["pair_pattern_identical"], g["checked"], g)
                    self.assertNotIn("same_direction", g["counts_H1_vs_H3"])
                    if blocked:
                        self.assertEqual(g["counts_H1_vs_H3"], {"tie_surface": g["checked"]})
                    else:
                        for k in ("tie", "tie_surface", "tie_interior"):
                            self.assertNotIn(k, g["counts_H1_vs_H3"])
                    if P != 1 and not blocked:
                        self.assertEqual(g["counts_H1_vs_H3"].get("flipped", 0), 0)

    def test_prediction_P1_full_grid(self):
        import thermal_sensitivity as ts
        g = ts.classify_grid("common_bias", 1, False, stride=1)
        self.assertEqual(g["flipped_cells_h_R"], ts.P1_FLIPPED_CELLS)
        self.assertEqual(g["cells_with_mixed_classes"], [])
        self.assertEqual(g["counts_H1_vs_H3"]["flipped"], 12 * 81)

    def test_uniform_flip_fraction(self):
        kap = float(scf.kappa(1))
        n = 200000
        hits = 0
        for i in range(n):  # deterministic midpoint check against the closed form
            h = 3 + 12 * (i % 500 + 0.5) / 500
            r = 1 + 9 * (i // 500 + 0.5) / 400
            hits += r < kap / h
        self.assertAlmostEqual(scf.uniform_flip_fraction(kap), hits / n, delta=5e-4)
        self.assertAlmostEqual(scf.uniform_flip_fraction(kap), 0.0041, delta=3e-4)
        self.assertEqual(scf.uniform_flip_fraction(scf.kappa(5)), 0.0)
        self.assertEqual(scf.uniform_flip_fraction(scf.kappa(10)), 0.0)

    def test_thickness_modes(self):
        self.assertEqual(scf.thicknesses("H3"), (F(1, 500), F(1, 20000), F(1, 500)))
        self.assertEqual(scf.thicknesses("H1", "common_bias", {"delta_all": F(1, 10)}),
                         (F(11, 20000), F(11, 200000), F(11, 20000)))
        t_o, t_f, t_i = scf.thicknesses("H2", "independent_layers",
                                        {"delta_outer": F(-1, 10), "delta_film": 0, "delta_inner": F(1, 10)})
        self.assertEqual((t_o, t_f, t_i), (F(9, 10000), F(1, 20000), F(11, 10000)))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            scf.make_params("H1", k_s=0)
        with self.assertRaises(ValueError):
            scf.make_params("H1", h=-1)
        with self.assertRaises(ValueError):
            scf.make_params("H1", r=0)
        with self.assertRaises(ValueError):
            scf.make_params("H1", P=-1)
        with self.assertRaises(ValueError):
            scf.make_params("H9")
        with self.assertRaises(ValueError):
            scf.make_params("H1", bogus=1)
        with self.assertRaises(ValueError):
            scf.partials(scf.make_params("H1"), "nope")
        self.assertIsNone(scf.make_params("H1", r=math.inf)["r"])


if __name__ == "__main__":
    unittest.main()
