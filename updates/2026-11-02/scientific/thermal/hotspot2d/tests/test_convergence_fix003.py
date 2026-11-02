"""fix-003: diagnosis of the wave-10 T_H 'order 0.27' and the corrected
mesh-convergence criterion. WAVE10_* fixtures are Red's executed numbers
(receipts afe808b6... / f00ce120..., Linux, CPython 3.13); everything else is
computed here. Model only."""
import math
import os
import sys
import unittest
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hotspot2d import model as M  # noqa: E402
from hotspot2d import convergence as C  # noqa: E402

WAVE10_T_H = (33.843532217632365, 33.842843219043225, 33.84227188231695)
WAVE10_T_MID_CENTRE = (32.821243935195, 32.79809332526317, 32.794176118033434)
WAVE10_ORDER_T_H = 0.27015975749952653
WAVE10_ORDER_T_MID_CENTRE = 2.5631528461192166
WAVE10_DY_M = (5e-3, 2.5e-3, 1.25e-3)


@lru_cache(maxsize=None)
def resolved_sequence(overhang_cells: int):
    return C.run_sequence(M.Params(stack="H1"), overhang_cells=overhang_cells)


class TestDiscreteFinModel(unittest.TestCase):
    def test_decay_factor_definition_and_limits(self):
        for x in (1e-3, 0.1, 0.5, 2.0, 10.0):
            lam = C.discrete_decay_factor(x)
            self.assertTrue(0.0 < lam < 1.0)
            self.assertAlmostEqual(lam + 1.0 / lam, 2.0 + x * x, places=9)
        self.assertAlmostEqual(C.discrete_decay_factor(1e-3), math.exp(-1e-3), delta=1e-6)
        self.assertAlmostEqual(C.discrete_decay_factor(10.0) * 102.0, 1.0, delta=0.02)

    def test_series_resistance_is_second_order_in_dy(self):
        for ell_u, ell_f in ((0.68e-3, 1.6e-3), (2.5e-3, 3.65e-3)):
            cont = ell_u + ell_f
            for dy in (1e-4, 5e-5):
                r = C.discrete_fin_series_resistance(dy, (ell_u, ell_f))
                second = dy * dy / 8.0 * (1.0 / ell_u + 1.0 / ell_f)
                self.assertGreater(r, cont)
                self.assertLess(abs(r - cont - second), 0.05 * second)
            self.assertAlmostEqual(C.exchange_fraction(1e-7, ell_u, ell_f), 1.0, delta=1e-6)


class TestWave10Diagnosis(unittest.TestCase):
    def test_wave10_sequence_violates_resolution_precondition_at_every_level(self):
        p = M.Params(stack="H1")
        ell_u = M.modal_spreading_length(p, p.r_c)
        for r in (1, 2, 4):
            zm, ym = C.wave10_level(p, r)
            self.assertGreater(C.edge_resolution(ym, ell_u), C.RESOLUTION_LIMIT, msg=f"refine {r}")

    def test_wave10_differences_are_far_above_the_noise_floor(self):
        rep = C.convergence_report(WAVE10_T_H)
        self.assertEqual(rep["status"], "order_defined")
        self.assertGreater(rep["e2_K"], 1e5 * C.NOISE_FLOOR_K)
        self.assertAlmostEqual(rep["order"], WAVE10_ORDER_T_H, places=9)
        self.assertAlmostEqual(C.convergence_report(WAVE10_T_MID_CENTRE)["order"], WAVE10_ORDER_T_MID_CENTRE, places=9)

    def test_discrete_fin_model_reproduces_executed_T_H_order(self):
        p = M.Params(stack="H1")
        ell_u = M.modal_spreading_length(p, p.r_c)
        ell_f = M.modal_spreading_length(p, p.r_fault)
        pred = C.predicted_pre_asymptotic_order(WAVE10_DY_M, ell_u, ell_f)
        self.assertLess(abs(pred - WAVE10_ORDER_T_H), 0.15, msg=f"predicted {pred}")
        f = [C.exchange_fraction(d, ell_u, ell_f) for d in WAVE10_DY_M]
        e1, e2 = abs(WAVE10_T_H[0] - WAVE10_T_H[1]), abs(WAVE10_T_H[1] - WAVE10_T_H[2])
        shift1, shift2 = e1 / (f[1] - f[0]), e2 / (f[2] - f[1])
        self.assertLess(abs(shift1 - shift2) / shift2, 0.10)   # one lateral effect explains both pairs
        self.assertTrue(2e-3 < shift2 < 4e-3, msg=f"implied lateral effect on T_H {shift2} K")

    def test_wave10_coarsest_level_is_reproduced(self):
        p = M.Params(stack="H1")
        zm, ym = C.wave10_level(p, 1)
        lv = C.solve_level(p, zm, ym)
        self.assertEqual(lv["n_unknowns"], 101)
        self.assertAlmostEqual(lv["T_H"], WAVE10_T_H[0], delta=1e-9)
        self.assertAlmostEqual(lv["T_mid_centre"], WAVE10_T_MID_CENTRE[0], delta=1e-9)


class TestResolvedRefinement(unittest.TestCase):
    """Corrected predeclared criterion: precondition, noise floor, absolute
    tolerance, order floor 1.0 (unchanged) on a resolved sequence."""

    def test_precondition_and_predeclared_criterion(self):
        seq = resolved_sequence(0)
        self.assertLessEqual(seq["precondition_dy_over_ell_coarsest"], C.RESOLUTION_LIMIT)
        for lv in seq["levels"]:
            self.assertAlmostEqual(lv["faulted_area_m2"], 2 * 5e-3 * M.PANEL_SIDE, places=12)
            self.assertLess(abs(lv["balance_W"]), 1e-9)
        for k in ("T_H", "T_mid_centre", "T_surf_min"):
            rep = seq["reports"][k]
            self.assertLessEqual(rep["e2_K"], C.ABS_TOL_FINEST_PAIR_K, msg=f"{k}: {rep}")
            self.assertNotEqual(rep["status"], "not_decreasing", msg=f"{k}: {rep}")
            if rep["status"] == "order_defined":
                self.assertGreaterEqual(rep["order"], C.ORDER_FLOOR_PREDECLARED, msg=f"{k}: {rep}")

    def test_resolved_values_confirm_the_diagnosis(self):
        seq = resolved_sequence(0)
        p = M.Params(stack="H1")
        ref = M.reference_1d_steady(p)
        th = [lv["T_H"] for lv in seq["levels"]]
        # more captured lateral exchange -> lower T_H, monotonically
        self.assertGreater(th[0], th[1])
        self.assertGreater(th[1], th[2])
        # resolved T_H lies below the under-resolved wave-10 finest value ...
        self.assertLess(th[-1], WAVE10_T_H[-1] - 1e-4)
        # ... and above the unfaulted reference (HYP1 lower bound)
        self.assertGreater(th[-1], ref["H"])
        # cool spot over the patch centre (open rear), as in the executed study
        self.assertLess(seq["levels"][-1]["T_mid_centre"], ref["S"])

    def test_tightened_second_order_floor_fix003(self):
        """Tightened in fix-003 (scheme is second order; discrete-fin expansion).
        If this fails while the predeclared test passes, report the value; do
        not loosen either floor."""
        seq = resolved_sequence(0)
        for k in ("T_H", "T_mid_centre"):
            rep = seq["reports"][k]
            if rep["status"] == "order_defined":
                self.assertGreaterEqual(rep["order"], C.ORDER_FLOOR_TIGHTENED, msg=f"{k}: {rep}")

    def test_criterion_rejects_a_first_order_edge_defect(self):
        """Non-vacuity check: a fault boundary one cell off the mesh faces is a
        first-order inconsistency; the tightened floor must reject it."""
        clean, defective = resolved_sequence(0), resolved_sequence(1)
        for a, b in zip(clean["levels"], defective["levels"]):
            self.assertGreater(b["faulted_area_m2"], a["faulted_area_m2"])
            self.assertGreater(b["T_H"], a["T_H"])     # more faulted area -> hotter H
        rep = defective["reports"]["T_H"]
        self.assertEqual(rep["status"], "order_defined", msg=str(rep))
        self.assertLess(rep["order"], C.ORDER_FLOOR_TIGHTENED, msg=str(rep))
        self.assertTrue(0.7 <= rep["order"] <= 1.3, msg=f"expected ~first order, got {rep}")


if __name__ == "__main__":
    unittest.main()
