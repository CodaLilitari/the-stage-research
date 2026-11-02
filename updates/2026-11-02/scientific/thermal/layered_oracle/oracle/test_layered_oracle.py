"""Tests for layered_oracle.py (unittest, stdlib only). Expected values are independent of the
code under test: Coda's exact rational rows (copied verbatim from reference_results.json),
textbook plane-wall series, the one-node exponential, and analytic identities.

Fix 003: the mode-structure test uses the conditioning-corrected root-accuracy estimate
(derivation A.11), the Weyl test uses the rigorous Dirichlet-Neumann bracket (A.10), and two
independent cross-counts are added (Sturm index, A.9; argument principle on complex F)."""
import math
import os
import sys
import unittest
from dataclasses import replace
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layered_oracle as lo  # noqa: E402

# (stack, P_body, blocked, H, S, surface, front, rear) from reference_results.json (Coda)
REFERENCE_ROWS = [
    ("H1", 1, False, 26.90248230028146, 26.891868221020427, 26.85948562324088, 0.14875884985927018, 0.9512411501407299),
    ("H1", 5, False, 33.83119986113005, 33.70398462379287, 33.55500086793716, 0.6844000694349729, 4.415599930565027),
    ("H1", 10, False, 42.492096812190795, 42.21913012725842, 41.92439492380752, 1.3539515939046014, 8.7460484060954),
    ("H1", 5, True, 90.94862037037036, 89.86019444444445, 88.75, 5.1, 0.0),
    ("H2", 1, False, 26.907261860110584, 26.88858113572823, 26.829613374308842, 0.14636906994470728, 0.9536309300552928),
    ("H2", 5, False, 33.86190245732054, 33.6326495680521, 33.36310964174662, 0.6690487713397297, 4.430951228660271),
    ("H2", 10, False, 42.55520320383298, 42.062735108456934, 41.52997997604385, 1.3223983980835077, 8.777601601916492),
    ("H2", 5, True, 92.81899074074074, 90.80463888888889, 88.75, 5.1, 0.0),
    ("H3", 1, False, 26.916159074909697, 26.883744465399086, 26.774005781814406, 0.1419204625451524, 0.9580795374548476),
    ("H3", 5, False, 33.91905575238601, 33.501140687023764, 33.00590154758745, 0.6404721238069959, 4.459527876193004),
    ("H3", 10, False, 42.6726765992314, 41.772885964054616, 40.79577125480375, 1.2636617003843003, 8.836338299615699),
    ("H3", 5, True, 96.55973148148148, 92.69352777777777, 88.75, 5.1, 0.0),
]


def textbook_plane_wall(theta_i, Bi, Fo, xi, nterms=80):
    """Plane wall, insulated face xi=0, convection at xi=1 (Carslaw & Jaeger; Incropera Table 5.1)."""
    total = 0.0
    for n in range(1, nterms + 1):
        lo_, hi_ = (n - 1) * math.pi + 1e-12, (n - 1) * math.pi + math.pi / 2 - 1e-9
        for _ in range(300):
            mid = 0.5 * (lo_ + hi_)
            if mid <= lo_ or mid >= hi_:
                break
            if mid * math.tan(mid) - Bi < 0.0:
                lo_ = mid
            else:
                hi_ = mid
        z = 0.5 * (lo_ + hi_)
        Cn = 4.0 * math.sin(z) / (2.0 * z + math.sin(2.0 * z))
        total += Cn * math.exp(-z * z * Fo) * math.cos(z * xi)
    return theta_i * total


class TestSteady(unittest.TestCase):
    def test_matches_reference_rows(self):
        for stack, P, blocked, H, S, surf, front, rear in REFERENCE_ROWS:
            p = lo.nominal_params(stack, P_body=float(P), G_rej=0.0 if blocked else 0.5)
            st = lo.steady_state(p)
            for got, exp in ((st["H"], H), (st["S"], S), (st["surface"], surf),
                             (st["front"], front), (st["rear"], rear)):
                self.assertAlmostEqual(got, exp, delta=1e-9, msg=f"{stack} P={P} blocked={blocked}")
            self.assertAlmostEqual(st["balance"], 0.0, delta=1e-12)
            self.assertAlmostEqual(st["H_from_profile"], st["H"], delta=1e-9)

    def test_exact_fraction_h1_5w_front(self):
        st = lo.steady_state(lo.nominal_params("H1", P_body=5.0))
        self.assertAlmostEqual(st["front"], float(Fraction(1103951, 1613020)), delta=1e-12)

    def test_profile_interface_jumps(self):
        p = lo.nominal_params("H2", P_body=5.0)
        st = lo.steady_state(p)
        segs = st["segments"]
        for i, r in enumerate(lo.interface_resistances(p)):
            T_minus = segs[i]["T0"] + segs[i]["slope"] * segs[i]["ell"]
            T_plus = segs[i + 1]["T0"]
            self.assertAlmostEqual(T_minus - T_plus, r * segs[i]["q"], delta=1e-12)
        self.assertAlmostEqual(segs[2]["T0"], st["S"], delta=1e-9)
        self.assertAlmostEqual((segs[2]["q"] - segs[1]["q"]) * p.area, p.P_sensor, delta=1e-12)

    def test_long_time_limit_equals_steady(self):
        p = lo.nominal_params("H3", P_body=5.0)
        sol = lo.solve([(0.0, p)], [1.0e6])
        st = lo.steady_state(p)
        self.assertAlmostEqual(sol.temperature("surface", 1.0e6), st["surface"], delta=1e-9)
        self.assertAlmostEqual(sol.temperature("sensor", 1.0e6), st["S"], delta=1e-9)
        self.assertAlmostEqual(sol.temperature("H", 1.0e6), st["H"], delta=1e-9)


class TestModes(unittest.TestCase):
    def test_structure_all_stacks(self):
        for stack in ("H1", "H2", "H3"):
            with self.subTest(stack=stack):
                p = lo.nominal_params(stack)
                ms = lo.compute_modes(p, n_modes=40)
                lams = [m.lam for m in ms.modes]
                self.assertEqual(len(lams), 40)
                self.assertGreater(lams[0], 0.0)
                self.assertTrue(all(b > a for a, b in zip(lams, lams[1:])))
                self.assertTrue(ms.diagnostics["alternation_ok"])
                self.assertTrue(ms.diagnostics["sturm_index_ok"])
                # Root accuracy, conditioning-corrected (A.11): |dlam|/lam; 1e-13 ~ 450 ulp.
                self.assertLess(ms.diagnostics["max_root_rel_error_est"], 1e-13)
                # Raw identity residual == |F(lam_hat)|, amplified by N_n/|psi_n(L)| ~ lam_n;
                # informational, loose sanity cap only (a wrong root would be O(1)).
                self.assertLess(ms.diagnostics["max_energy_identity_residual_rel"], 1e-6)
                self.assertLess(ms.diagnostics["dirichlet_residual_max"], 1e-9)
                d = ms.diagnostics["dirichlet"]
                for n in range(39):            # interlacing lam_n < d_n < lam_{n+1}
                    self.assertLess(lams[n], d[n])
                    self.assertLess(d[n], lams[n + 1])

    def test_orthogonality_and_derivative_identity(self):
        p = lo.nominal_params("H1")
        ms = lo.compute_modes(p, n_modes=12)
        for i in range(12):
            for j in range(i + 1, 12):
                ip = lo._mode_inner(ms, ms.modes[i], ms.modes[j])
                self.assertLess(abs(ip) / math.sqrt(ms.modes[i].norm * ms.modes[j].norm), 1e-8)
        for m in ms.modes:
            eps = 1e-6 * m.lam
            dF = (lo.characteristic(p, m.lam + eps) - lo.characteristic(p, m.lam - eps)) / (2 * eps)
            self.assertAlmostEqual(dF * m.psi_L / m.norm, 1.0, delta=1e-5)

    def test_weyl_count_rigorous_bracket(self):
        # Dirichlet-Neumann bracketing (A.10): E - 3 < N(lam) < E + 4 for every lam, so with the
        # N-th found eigenvalue -3 < N - E < 4. The old tolerance 2.0 only held in the
        # transparent-interface regime (r k mu << 1); at lam ~ 5e3 1/s (H1, 60 modes) the
        # interfaces decouple and N - E drifts toward the decoupled range (1.5, 3.5].
        for stack in ("H1", "H2", "H3"):
            with self.subTest(stack=stack):
                ms = lo.compute_modes(lo.nominal_params(stack), n_modes=60)
                off = 60 - ms.diagnostics["weyl_estimate_at_lam_max"]
                self.assertGreater(off, -3.0)
                self.assertLess(off, 4.0)
                self.assertAlmostEqual(off, ms.diagnostics["weyl_offset"], delta=1e-12)

    def test_cross_count_sturm_index(self):
        # Independent per-root count (A.9): the lifted phase at each eigenvalue, swept in x at
        # fixed lam, must place it at its own index. A missed root shifts all later indices.
        for stack in ("H1", "H2", "H3"):
            for over in ({}, {"G_rej": 0.0}, {"r_inner": 2.0e-3}):
                with self.subTest(stack=stack, over=over):
                    p = lo.nominal_params(stack, **over)
                    ms = lo.compute_modes(p, n_modes=60)
                    for n, m in enumerate(ms.modes):
                        self.assertEqual(lo.sturm_index(p, m.lam), n)
                    self.assertTrue(ms.diagnostics["sturm_index_ok"])

    def test_cross_count_argument_principle(self):
        # Fully independent of the Dirichlet bracketing: winding number of the entire function
        # F around a rectangle enclosing (0, b) counts the zeros below b exactly.
        for stack in ("H1", "H2", "H3"):
            with self.subTest(stack=stack):
                p = lo.nominal_params(stack)
                ms = lo.compute_modes(p, n_modes=61)
                lams = [m.lam for m in ms.modes]
                b = 0.5 * (lams[59] + lams[60])
                self.assertEqual(lo.count_zeros_argument_principle(p, b), 60)
        # The default lam_max policy sets used by the nine cases: all zeros below the last
        # Dirichlet point must be exactly the modes found.
        for p in (lo.nominal_params("H1", G_rej=0.0), lo.nominal_params("H1", r_inner=2.0e-3),
                  lo.nominal_params("H3", r_inner=2.0e-3)):
            with self.subTest(G_rej=p.G_rej, r_inner=p.r_inner, L=p.outer.thickness):
                ms = lo.compute_modes(p, lam_max=50.0)
                d_last = ms.diagnostics["dirichlet"][-1]
                self.assertEqual(lo.count_zeros_argument_principle(p, d_last), len(ms.modes))

    def test_lifted_phase_monotone_and_dirichlet_zero(self):
        p = lo.nominal_params("H1")
        geo, ifaces = lo.segment_geometry(p), lo.interface_resistances(p)
        prev = -math.inf
        for i in range(1, 400):
            s = 0.25 * i
            th = lo.lifted_terminal_phase(geo, ifaces, p.h, s * s)[0]
            self.assertGreater(th, prev)
            prev = th
        ms = lo.compute_modes(p, n_modes=30)
        for j, d in enumerate(ms.diagnostics["dirichlet"]):
            th, psiL, qL = lo.lifted_terminal_phase(geo, ifaces, p.h, d)
            self.assertAlmostEqual(th, 0.5 * math.pi + j * math.pi, delta=1e-9)
            self.assertEqual(lo.sturm_index(p, ms.modes[j].lam), j)

    def test_lam_max_policy_includes_all_below(self):
        p = lo.nominal_params("H2")
        ms = lo.compute_modes(p, lam_max=200.0)
        ref = lo.compute_modes(p, n_modes=len(ms.modes) + 5)
        for a, b in zip(ms.modes, ref.modes):
            self.assertAlmostEqual(a.lam, b.lam, delta=1e-12 * max(1.0, a.lam))
        self.assertGreater(ref.modes[len(ms.modes)].lam, 200.0 - 1e-9)


class TestTransient(unittest.TestCase):
    def test_truncation_convergence(self):
        sched = lo.schedule_F0("H1")
        t = 0.05
        vals = {}
        for N in (6, 12, 24, 48, 96):
            sol = lo.solve(sched, [t], n_modes=N)
            vals[N] = [sol.temperature(loc, t) for loc in lo.LOCATIONS]
        d = {N: max(abs(a - b) for a, b in zip(vals[N], vals[2 * N])) for N in (6, 12, 24, 48)}
        self.assertGreater(d[6], d[24])
        self.assertLess(d[24], 1e-6)
        self.assertLess(d[48], 1e-9)

    def test_energy_balance_F0(self):
        sol = lo.solve(lo.schedule_F0("H1"), [1.0, 10.0, 100.0, 600.0, 900.0, 1000.0, 3600.0])
        for t in (1.0, 10.0, 100.0, 600.0, 900.0, 1000.0, 3600.0):
            a = sol.energy_audit(t)
            self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["input_J"]), t)
        self.assertAlmostEqual(sol.energy_audit(3600.0)["input_J"], 5.0 * 900.0 + 0.1 * 3600.0, delta=1e-9)

    def test_energy_balance_F1_F2_with_events(self):
        for sched in (lo.schedule_F1("H2"), lo.schedule_F2("H3")):
            sol = lo.solve(sched, [601.0, 901.0, 3600.0])
            a = sol.energy_audit(3600.0)
            self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["input_J"]))
            self.assertEqual(len(a["event_energy_jumps_J"]), 2)
            for j in a["event_energy_jumps_J"]:
                self.assertLess(abs(j), 0.05)        # truncation at the projection, J

    def test_initial_energy_defect_decreases(self):
        sched = lo.schedule_F0("H1")
        defects = [abs(lo.solve(sched, [1.0], n_modes=N).energy_audit(1.0)["initial_energy_defect_J"])
                   for N in (8, 32, 128)]
        self.assertGreater(defects[0], defects[1])
        self.assertGreater(defects[1], defects[2])
        self.assertLess(defects[2], 0.1)

    def test_event_state_continuity_F1(self):
        sol = lo.solve(lo.schedule_F1("H1"), [600.0, 600.05])
        self.assertLess(abs(sol.temperature("H", 600.05) - sol.temperature("H", 600.0)), 0.05)
        self.assertLess(abs(sol.temperature("surface", 600.05) - sol.temperature("surface", 600.0)), 0.01)
        self.assertLess(abs(sol.temperature("sensor", 600.05) - sol.temperature("sensor", 600.0)), 0.01)
        seg2 = sol.segments[1]
        self.assertLess(seg2.defect / seg2.theta2, 1e-2)
        sol_big = lo.solve(lo.schedule_F1("H1"), [600.0, 600.05], n_modes=120)
        self.assertLess(sol_big.segments[1].defect / sol_big.segments[1].theta2, seg2.defect / seg2.theta2)

    def test_F2_interface_jump_and_flux_continuity(self):
        sched = lo.schedule_F2("H1")
        sol = lo.solve(sched, [700.0])
        p = sched[1][1]
        x_i = p.outer.thickness + p.film.thickness
        q_minus, q_plus = sol.flux_at(x_i, 700.0, -1), sol.flux_at(x_i, 700.0, +1)
        self.assertLess(abs(q_minus - q_plus), 1e-9 * max(1.0, abs(q_minus)))
        jump = sol.temperature_at(x_i, 700.0, -1) - sol.temperature_at(x_i, 700.0, +1)
        self.assertAlmostEqual(jump, p.r_inner * q_minus, delta=1e-9)
        x_o = p.outer.thickness
        jump_o = sol.temperature_at(x_o, 700.0, -1) - sol.temperature_at(x_o, 700.0, +1)
        self.assertAlmostEqual(jump_o, p.r_outer * sol.flux_at(x_o, 700.0, -1), delta=1e-9)

    def test_blocked_steady_from_F1_segment(self):
        sol = lo.solve(lo.schedule_F1("H1", body_off_s=1.0e9), [700.0])
        st = sol.segments[1].steady
        self.assertAlmostEqual(st["H"], 90.94862037037036, delta=1e-9)
        self.assertAlmostEqual(st["surface"], 88.75, delta=1e-9)


class TestLimits(unittest.TestCase):
    def test_single_slab_textbook(self):
        sil = lo.Layer(0.0005, 0.27, 1030.0, 1500.0)
        film = lo.Layer(5.0e-5, 0.27, 1030.0, 1500.0)
        p = lo.Params(outer=sil, film=film, inner=sil, r_outer=0.0, r_inner=0.0, h=200.0,
                      G_rej=0.0, C_H=0.0, P_body=0.0, P_sensor=0.0, T_amb=25.0, T_res=25.0)
        T_i = 35.0
        sol = lo.solve([(0.0, p)], [1.0, 5.0, 20.0], T_initial=T_i, n_modes=30)
        L = 2 * 0.0005 + 5.0e-5
        Bi, alpha = p.h * L / sil.k, sil.alpha
        for t in (1.0, 5.0, 20.0):
            Fo = alpha * t / (L * L)
            for x in (0.0, 0.3 * L, 0.5 * L, L):
                exp = 25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, (L - x) / L)
                self.assertAlmostEqual(sol.temperature_at(x, t), exp, delta=1e-8, msg=f"t={t} x={x}")
            self.assertAlmostEqual(sol.temperature("surface", t),
                                   25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, 1.0), delta=1e-8)
            self.assertAlmostEqual(sol.temperature("H", t),
                                   25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, 0.0), delta=1e-8)

    def test_one_node_limit(self):
        # Coda's predeclared fixture: C 10 J/K, R 2 K/W, P 3 W, T0=Tb=20 C -> 23.792723352971347 at 20 s
        thin = lo.Layer(0.0005, 0.27, 1.0e-6, 1.0)
        film = lo.Layer(5.0e-5, 0.20, 1.0e-6, 1.0)
        p = lo.Params(outer=thin, film=film, inner=thin, h=1.0e-9, G_rej=0.5, C_H=10.0,
                      T_amb=20.0, T_res=20.0, P_body=3.0, P_sensor=0.0)
        sol = lo.solve([(0.0, p)], [20.0], T_initial=20.0)
        self.assertAlmostEqual(sol.temperature("H", 20.0), 23.792723352971347, delta=1e-7)
        self.assertAlmostEqual(sol.temperature("H", 20.0),
                               20.0 + 6.0 * (-math.expm1(-20.0 / 20.0)), delta=1e-7)


class TestValidation(unittest.TestCase):
    def test_rejections(self):
        p = lo.nominal_params("H1")
        for bad in (replace(p, h=0.0), replace(p, h=-1.0), replace(p, C_H=-1.0), replace(p, G_rej=-0.1),
                    replace(p, r_inner=-1e-4), replace(p, area=0.0), replace(p, P_body=math.nan),
                    replace(p, T_amb=math.inf), replace(p, outer=lo.Layer(0.0, 0.27, 1030.0, 1500.0))):
            with self.assertRaises(ValueError):
                lo.validate(bad)
        with self.assertRaises(ValueError):
            lo.compute_modes(p)
        with self.assertRaises(ValueError):
            lo.solve([(1.0, p)], [2.0])
        with self.assertRaises(ValueError):
            lo.solve([(0.0, p), (600.0, lo.nominal_params("H2"))], [700.0])


if __name__ == "__main__":
    unittest.main()
