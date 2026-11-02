"""Unit tests for the 2D-PATCH-EXT-1 model. Expected values for the 1-D
limits are (i) Coda's executed reference_results.json numbers (fixtures below,
sha256 e97cf35c...) and (ii) the transcribed two-node reference; both are
independent of the finite-volume code under test."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hotspot2d import model as M  # noqa: E402

# Coda, validation/thermal/reference_results.json, 5 W body + 0.1 W sensor, rear R=2 K/W
CODA_5W = {"H1": (33.83119986113005, 33.70398462379287, 33.55500086793716, 0.6844000694349729, 4.415599930565027),
           "H2": (33.86190245732054, 33.6326495680521, 33.36310964174662, 0.6690487713397297, 4.430951228660271),
           "H3": (33.91905575238601, 33.501140687023764, 33.00590154758745, 0.6404721238069959, 4.459527876193004)}
CODA_5W_BLOCKED_H = {"H1": 90.94862037037036, "H2": 92.81899074074074, "H3": 96.55973148148148}


def small_mesh(p, geom="planar", w=0.0, refine=1, nz=2):
    zm = M.build_zmesh(p, nz, 1, nz)
    ym = M.default_ymesh(geom, w, dy_fine=2e-3, dy_coarse=10e-3, margin=4e-3, refine=refine)
    return zm, ym


class TestMeshAndAssembly(unittest.TestCase):
    def test_areas_sum_to_panel_area(self):
        for geom in ("planar", "axisymmetric"):
            ym = M.default_ymesh(geom, 5e-3)
            self.assertAlmostEqual(ym.total_area, M.PANEL_AREA, places=12)

    def test_patch_membership_and_faulted_faces(self):
        p = M.Params()
        zm, ym = small_mesh(p, w=5e-3)
        c = M.PANEL_SIDE / 2
        for j in range(ym.n):
            self.assertEqual(ym.in_patch[j], abs(ym.centres[j] - c) < 5e-3)
        self.assertTrue(any(abs(f - (c - 5e-3)) < 1e-12 for f in ym.faces))
        self.assertTrue(any(abs(f - (c + 5e-3)) < 1e-12 for f in ym.faces))
        net = M.Network(p, zm, ym, True, True, 5.0)
        self.assertEqual(sorted(net.faulted_cells), [j for j in range(ym.n) if ym.in_patch[j]])
        self.assertAlmostEqual(ym.patch_area, 2 * 5e-3 * M.PANEL_SIDE, places=12)
        self.assertEqual(M.Network(p, zm, ym, False, True, 5.0).faulted_cells, [])

    def test_matrix_symmetric_and_positive_definite(self):
        p = M.Params(R_rej=math.inf)
        zm, ym = small_mesh(p, w=3e-3)
        net = M.Network(p, zm, ym, True, False, 5.0)
        self.assertTrue(net.is_symmetric())
        for seed in range(3):
            x = [math.sin(0.37 * k + seed) for k in range(net.n)]
            self.assertGreater(net.quadratic_form(x), 0.0)
        self.assertGreater(net.quadratic_form([1.0] * net.n), 0.0)  # boundary term makes constants non-null


class TestSteadyLimits(unittest.TestCase):
    def test_w_zero_recovers_1d_reference_all_stacks(self):
        for stack, (H, S, surf, front, rear) in CODA_5W.items():
            p = M.Params(stack=stack)
            zm, ym = small_mesh(p, w=0.0)
            net = M.Network(p, zm, ym, True, True, 5.0)  # fault flag on, but no patch cells
            for method, tol in (("direct", 1e-9), ("pcg", 1e-7)):
                T, info = M.solve_steady(net, method)
                self.assertTrue(info["converged"])
                s = M.steady_summary(net, T)
                self.assertAlmostEqual(s["T_H"], H, delta=tol)
                self.assertAlmostEqual(s["T_mid_centre"], S, delta=tol)
                self.assertAlmostEqual(s["T_mid_edge"], S, delta=tol)
                self.assertAlmostEqual(s["T_surf_centre"], surf, delta=tol)
                self.assertAlmostEqual(s["front_W"], front, delta=tol)
                self.assertAlmostEqual(s["rear_W"], rear, delta=tol)
                self.assertLess(abs(s["balance_W"]), 1e-9)

    def test_blocked_rear_w_zero_recovers_coda_blocked_values(self):
        for stack, H in CODA_5W_BLOCKED_H.items():
            p = M.Params(stack=stack, R_rej=math.inf)
            zm, ym = small_mesh(p, w=0.0)
            net = M.Network(p, zm, ym, True, False, 5.0)
            T, _ = M.solve_steady(net, "direct")
            s = M.steady_summary(net, T)
            self.assertAlmostEqual(s["T_H"], H, delta=1e-9)
            self.assertAlmostEqual(s["T_surf_centre"], 88.75, delta=1e-9)
            self.assertAlmostEqual(s["front_W"], 5.1, delta=1e-9)

    def test_full_patch_recovers_uniform_F2_both_geometries(self):
        for geom in ("planar", "axisymmetric"):
            for stack in ("H1", "H3"):
                p = M.Params(stack=stack)
                zm, ym = small_mesh(p, geom=geom, w=M.full_patch_width(geom))
                self.assertTrue(all(ym.in_patch))
                net = M.Network(p, zm, ym, True, True, 5.0)
                T, _ = M.solve_steady(net, "direct")
                s = M.steady_summary(net, T)
                ref = M.reference_1d_steady(p, r_inner=p.r_fault)
                self.assertAlmostEqual(s["T_H"], ref["H"], delta=1e-9)
                self.assertAlmostEqual(s["T_mid_centre"], ref["S"], delta=1e-9)
                self.assertAlmostEqual(s["T_surf_centre"], ref["surface"], delta=1e-9)
                self.assertAlmostEqual(s["front_W"], ref["front"], delta=1e-9)
                self.assertLess(s["T_mid_max"] - s["T_mid_min"], 1e-9)  # laterally uniform

    def test_transcribed_reference_matches_coda_fixture(self):
        for stack, (H, S, surf, front, rear) in CODA_5W.items():
            ref = M.reference_1d_steady(M.Params(stack=stack))
            self.assertAlmostEqual(ref["H"], H, places=10)
            self.assertAlmostEqual(ref["S"], S, places=10)
            self.assertAlmostEqual(ref["surface"], surf, places=10)
            self.assertAlmostEqual(ref["front"], front, places=10)

    def test_pcg_agrees_with_direct_on_patch_case(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=6e-3)
        net = M.Network(p, zm, ym, True, True, 5.0)
        Td, _ = M.solve_steady(net, "direct")
        Tp, info = M.solve_steady(net, "pcg", tol=1e-14)
        self.assertTrue(info["converged"])
        self.assertLess(max(abs(a - b) for a, b in zip(Td, Tp)), 1e-8)
        self.assertLess(net.residual_norm(Td), 1e-10)

    def test_steady_energy_balance_with_patch(self):
        for rear_open in (True, False):
            p = M.Params(stack="H1", R_rej=2.0 if rear_open else math.inf)
            zm, ym = small_mesh(p, w=8e-3)
            net = M.Network(p, zm, ym, True, rear_open, 5.0)
            T, _ = M.solve_steady(net, "direct")
            s = M.steady_summary(net, T)
            self.assertAlmostEqual(s["source_W"], 5.1, places=12)
            self.assertLess(abs(s["balance_W"]), 1e-9)

    # test_mesh_refinement_observed_order (wave 10) was removed in fix-003: its
    # sequence (dy = 5/2.5/1.25 mm) never resolved the lateral decay length, so
    # the order it computed was pre-asymptotic. See tests/test_convergence_fix003.py.


class TestTransient(unittest.TestCase):
    def test_uniform_no_source_stays_uniform(self):
        p = M.Params(P_body=0.0, P_sensor=0.0)
        zm, ym = small_mesh(p, w=4e-3)
        segs = [M.Segment(0.0, 50.0, 0.0, True, True)]
        res = M.simulate(p, zm, ym, segs, 5.0, T_initial=[25.0] * (zm.n * ym.n + 1))
        self.assertLess(max(abs(x - 25.0) for x in res.final_state), 1e-12)
        self.assertLess(abs(res.audit["residual_J"]), 1e-9)

    def test_energy_audit_closes_with_fault_event(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=60.0, body_off_time=120.0, horizon=200.0)
        res = M.simulate(p, zm, ym, segs, 4.0)
        a = res.audit
        self.assertGreater(a["injected_J"], 0.0)
        self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["injected_J"]))
        # bookkeeping path (recorded injected/exported) agrees with reconstruction from states
        self.assertAlmostEqual(res.E[-1] - res.E[0], res.injected[-1] - res.exported[-1], delta=1e-7)

    def test_state_continuity_at_fault_instant(self):
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=40.0, body_off_time=80.0, horizon=100.0)
        res = M.simulate(p, zm, ym, segs, 2.0)
        b40 = [b for b in res.segment_boundaries if abs(b["t"] - 40.0) < 1e-9][0]
        k40 = [k for k, t in enumerate(res.t) if abs(t - 40.0) < 1e-9]
        self.assertEqual(len(k40), 1)
        self.assertAlmostEqual(res.T_H[k40[0]], b40["T_H"], places=12)
        self.assertAlmostEqual(res.T_mid_centre[k40[0]], b40["T_mid_centre"], places=12)

    def test_full_patch_transient_is_y_independent_and_matches_1d(self):
        p = M.Params(stack="H1")
        zm = M.build_zmesh(p, 2, 1, 2)
        segs = M.event_schedule(fault_time=30.0, body_off_time=60.0, horizon=90.0)
        ym1 = M.ymesh_from_faces("planar", [0.0, M.PANEL_SIDE], M.PANEL_SIDE / 2)
        ym8 = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, M.PANEL_SIDE], [8]), M.PANEL_SIDE / 2)
        r1 = M.simulate(p, zm, ym1, segs, 3.0)
        r8 = M.simulate(p, zm, ym8, segs, 3.0)
        self.assertLess(max(abs(a - b) for a, b in zip(r1.T_H, r8.T_H)), 1e-9)
        self.assertLess(max(abs(a - b) for a, b in zip(r1.T_mid_centre, r8.T_mid_centre)), 1e-9)
        self.assertLess(max(a - b for a, b in zip(r8.T_mid_max, r8.T_mid_min)), 1e-9)

    def test_long_time_transient_tends_to_steady(self):
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = [M.Segment(0.0, 2000.0, 5.0, True, True)]
        res = M.simulate(p, zm, ym, segs, 10.0)
        net = M.Network(p, zm, ym, True, True, 5.0)
        T, _ = M.solve_steady(net, "direct")
        self.assertLess(max(abs(a - b) for a, b in zip(res.final_state, T)), 1e-3)

    def test_time_refinement_first_order(self):
        """Backward Euler: observed temporal order predeclared in [0.6, 1.5]."""
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=100.0, body_off_time=200.0, horizon=240.0)
        vals = []
        for dt in (20.0, 10.0, 5.0):
            res = M.simulate(p, zm, ym, segs, dt)
            vals.append(res.value_at("T_H", 240.0))
        order = M.observed_order(*vals)
        self.assertIsNotNone(order)
        self.assertGreaterEqual(order, 0.6)
        self.assertLessEqual(order, 1.5)

    def test_pcg_transient_matches_direct(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=4e-3)
        segs = [M.Segment(0.0, 20.0, 5.0, True, True)]
        rd = M.simulate(p, zm, ym, segs, 5.0, method="direct")
        rp = M.simulate(p, zm, ym, segs, 5.0, method="pcg", pcg_tol=1e-13)
        self.assertLess(max(abs(a - b) for a, b in zip(rd.final_state, rp.final_state)), 1e-7)


class TestSpreadingLength(unittest.TestCase):
    def test_modal_limits(self):
        p = M.Params(stack="H1", h=1e-9, r_c=0.0)
        # R_f -> film only (small): x -> pi/4 within the small-film correction
        ell = M.modal_spreading_length(p, 0.0, include_convection=False)
        self.assertAlmostEqual(ell / (4 * p.t_s / math.pi), 1.0, delta=0.08)
        # large R_f: ell ~ sqrt(R_f k_s t)
        big = 10.0
        ell_big = M.modal_spreading_length(p, big, include_convection=False)
        self.assertAlmostEqual(ell_big / math.sqrt(big * p.k_s * p.t_s), 1.0, delta=0.05)

    def test_fin_within_factor_two_of_modal(self):
        for stack in ("H1", "H2", "H3"):
            p = M.Params(stack=stack)
            for r in (p.r_c, p.r_fault):
                ratio = M.fin_spreading_length(p, r) / M.modal_spreading_length(p, r)
                self.assertTrue(0.5 <= ratio <= 2.0, msg=f"{stack} r={r} ratio={ratio}")

    def test_numerical_decay_length_matches_modal_H3(self):
        """Predeclared: fitted decay length within 25 % of the modal value."""
        p = M.Params(stack="H3")
        ell = M.modal_spreading_length(p, p.r_c)
        zm = M.build_zmesh(p, 4, 1, 4)
        ym = M.default_ymesh("planar", 10e-3, dy_fine=0.5e-3, dy_coarse=2.5e-3, margin=20e-3)
        net = M.Network(p, zm, ym, True, True, 5.0)
        T, _ = M.solve_steady(net, "direct")
        fit = M.fit_decay_length(ym, net.film_midplane(T), ell)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["ell_fit_m"] / ell, 1.0, delta=0.25,
                               msg=f"fit {fit['ell_fit_m']} vs modal {ell}")


if __name__ == "__main__":
    unittest.main()
