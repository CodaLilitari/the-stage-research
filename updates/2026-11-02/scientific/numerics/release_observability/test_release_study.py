"""Unit tests for release_model.py and release_study.py (standard library only).

Cross-check values quoted from AB-LFR1 REPORT.md (Lilitari) and the terminal
rows reproduced in Muse Code's independent check; they are values of the same
synthetic model, not external facts.  Run:  python -m unittest test_release_study -v
"""
import json
import math
import unittest

import release_model as rm
import release_study as rs


def solve_tridiag_2m1(r):
    """Solve (D D^T) z = r with D the first-difference operator (diag 2, off -1)."""
    m = len(r)
    cp, dp = [0.0] * m, [0.0] * m
    cp[0], dp[0] = -0.5, r[0] / 2.0
    for i in range(1, m):
        denom = 2.0 + cp[i - 1]
        cp[i] = -1.0 / denom if i < m - 1 else 0.0
        dp[i] = (r[i] + dp[i - 1]) / denom
    z = [0.0] * m
    z[-1] = dp[-1]
    for i in range(m - 2, -1, -1):
        z[i] = dp[i] - cp[i] * z[i + 1]
    return z


class TestModel(unittest.TestCase):
    CASES = [rm.Params(1.0, 1.0, 4.0, 1.0), rm.Params(1.0, 100.0, 4.0, 1.0),
             rm.Params(1.0, 1000.0, 4.0, 1.0), rm.Params(0.5, 2.0, 4.0, 0.2),
             rm.Params(3.0, 0.1, 0.5, 2.0), rm.Params(1.0, 0.05, 0.2, 1.0)]

    def test_params_validation(self):
        for bad in ((0.0, 1.0, 1.0, 1.0), (1.0, -1.0, 1.0, 1.0), (1.0, 1.0, float("inf"), 1.0),
                    (1.0, 1.0, 1.0, 0.0)):
            with self.assertRaises(ValueError):
                rm.Params(*bad)

    def test_initial_condition_and_amplitude_identities(self):
        for p in self.CASES:
            m = rm.modes(p)
            c, b = rm.finite_state(p, 0.0, m)
            self.assertAlmostEqual(c / p.c0, 1.0, delta=1e-14)
            self.assertAlmostEqual(b / (p.gamma * p.c0), 1.0, delta=1e-14)
            self.assertAlmostEqual((m.r_f - m.r_s) / m.delta, 1.0, delta=1e-13)
            self.assertAlmostEqual(m.r_s * m.r_f / (p.alpha * p.k), 1.0, delta=1e-13)
            self.assertAlmostEqual((m.r_eq - m.r_s) / m.rate_shift, 1.0, delta=1e-9)
            self.assertAlmostEqual((m.kappa * (1 + p.gamma) - 1.0) / m.kappa_defect, 1.0, delta=1e-9)

    def test_ode_residual(self):
        for p in self.CASES:
            m = rm.modes(p)
            for t in (0.01, 0.3, 2.0):
                c, b = rm.finite_state(p, t, m)
                dc, db = rm.finite_derivative(p, t, m)
                rhs_c = -(p.alpha + p.k * p.gamma) * c + p.k * b
                rhs_b = p.k * p.gamma * c - p.k * b
                scale = (p.alpha + p.k * p.gamma) * abs(c) + p.k * abs(b) + 1e-300
                self.assertLess(abs(dc - rhs_c) / scale, 1e-10)
                self.assertLess(abs(db - rhs_b) / scale, 1e-10)
                # release flux = -b'
                self.assertLess(abs(rm.release_flux(p, t, m) + db) / (abs(db) + 1e-300), 1e-9)

    def test_report_crosschecks(self):
        # REPORT.md one-second family, binary64 terminal rows as quoted by Muse's script.
        rows = {1.0: (0.7194121558656852, 3.4711913532255587),
                100.0: (0.8176831359534535, 3.2772766223496683),
                1000.0: (0.8186259591066365, 3.2751587633867185),
                1e12: (0.8187307530778771, 3.274923012312163)}
        for k, (c_ref, b_ref) in rows.items():
            c, b = rm.finite_state(rm.Params(1.0, k, 4.0, 1.0), 1.0)
            self.assertAlmostEqual(c, c_ref, delta=1e-13)
            self.assertAlmostEqual(b, b_ref, delta=4e-13)
        c, b = rm.finite_state(rm.Params(0.5, 2.0, 4.0, 0.2), 3.0)   # C19 fixture
        self.assertAlmostEqual(c, 0.14402585951785102, delta=1e-13)
        self.assertAlmostEqual(b, 0.6051881664743007, delta=2e-13)
        # normalized endpoint differences reported: 1.047617e-3 (k=100), 1.047940e-4 (k=1000), 1.04694e-13 (k=1e12)
        for k, ref, tol in ((100.0, 1.047617e-3, 1e-9), (1000.0, 1.047940e-4, 1e-10), (1e12, 1.04694e-13, 1e-15)):
            dc, db, _ = rm.relative_differences(rm.Params(1.0, k, 4.0, 1.0), 1.0)
            self.assertAlmostEqual(max(abs(dc), abs(db)), ref, delta=tol)
        # stiff flux k=1e12, t=1e-3 (stable identity value reported 0.7998400160)
        self.assertAlmostEqual(rm.release_flux(rm.Params(1.0, 1e12, 4.0, 1.0), 1e-3), 0.7998400160, delta=1e-9)

    def test_stable_differences_match_direct_subtraction(self):
        for p in self.CASES[:4]:
            m = rm.modes(p)
            for t in (0.05, 0.5, 1.0):
                dc, db, dJ = rm.relative_differences(p, t, m)
                c, b = rm.finite_state(p, t, m)
                ce, be = rm.equilibrium_state(p.alpha, p.gamma, p.c0, t)
                self.assertAlmostEqual(dc, (c - ce) / p.c0, delta=2e-15)
                self.assertAlmostEqual(db, (b - be) / (p.gamma * p.c0), delta=2e-15)
                js = rm.flux_scale(p.alpha, p.gamma, p.c0)
                dJ_direct = (rm.release_flux(p, t, m) - rm.equilibrium_flux(p.alpha, p.gamma, p.c0, t)) / js
                self.assertAlmostEqual(dJ, dJ_direct, delta=4e-15)

    def test_impostor_reproduces_slow_modes_exactly(self):
        for p in self.CASES:
            m = rm.modes(p)
            c0i, gi, ai = rm.impostor_params(p, m)
            self.assertAlmostEqual(ai / (1.0 + gi) / m.r_s, 1.0, delta=1e-13)
            for t in (0.3 / m.r_f, 1.0 / m.r_f, 3.0 / m.r_f, 1.0):
                c, b = rm.finite_state(p, t, m)
                ci, bi = rm.equilibrium_state(ai, gi, c0i, t)
                fc, fb, fJ = rm.fast_mode_relative(p, t, m)
                self.assertAlmostEqual((c - ci) / p.c0, fc, delta=1e-13)
                self.assertAlmostEqual((b - bi) / (p.gamma * p.c0), fb, delta=1e-13)
                js = rm.flux_scale(p.alpha, p.gamma, p.c0)
                self.assertAlmostEqual((rm.release_flux(p, t, m) - rm.equilibrium_flux(ai, gi, c0i, t)) / js,
                                       fJ, delta=1e-12)

    def test_leading_order_endpoint_large_k(self):
        p = rm.Params(1.0, 1e6, 4.0, 1.0)
        exact = rm.relative_differences(p, 1.0)
        lead = rm.leading_order_endpoint(p, 1.0)
        for e, l in zip(exact, lead):
            self.assertLess(abs(e / l - 1.0), 1e-3)
        t_c, t_j = rm.blind_spot_times(p)
        self.assertAlmostEqual(t_c, 5.0)
        self.assertAlmostEqual(t_j, 3.75)
        # at the c blind spot the leading-order term vanishes identically
        self.assertAlmostEqual(rm.leading_order_endpoint(p, t_c)[0], 0.0, delta=1e-30)


class TestStudy(unittest.TestCase):
    def test_phi(self):
        self.assertAlmostEqual(rs.phi(0.0), 0.5, delta=1e-15)
        self.assertAlmostEqual(rs.phi(-rs.Z95), 0.05, delta=1e-9)
        self.assertAlmostEqual(rs.phi(-rs.D_STAR / 2.0), 0.05, delta=1e-9)

    def test_time_grid(self):
        g = rs.time_grid(1.0, 4, 0.0)
        self.assertEqual(len(g), 4)
        self.assertAlmostEqual(g[0], 0.25)
        self.assertAlmostEqual(g[-1], 1.0)
        g = rs.time_grid(3.0, 2, 0.5)
        self.assertAlmostEqual(g[0], 2.25)
        self.assertAlmostEqual(g[-1], 3.0)
        with self.assertRaises(ValueError):
            rs.time_grid(1.0, 0)

    def test_projection_theorem_for_computed_flux(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[1] for t in rs.time_grid(1.0, 64, 0.0)]
        ci = rs.computed_flux_indices(delta)
        n = len(delta)
        r = [delta[i + 1] - delta[i] for i in range(n - 1)]
        z = solve_tridiag_2m1(r)
        d2_gls = math.fsum(a * b for a, b in zip(r, z))
        self.assertAlmostEqual(d2_gls / ci["d_comp"] ** 2, 1.0, delta=1e-9)
        self.assertLessEqual(ci["d_real"], ci["d_comp"] * (1 + 1e-12))
        self.assertLessEqual(ci["d_comp"], ci["d_b"] * (1 + 1e-12))
        # Cauchy-Schwarz bound: d_real >= d_naive/sqrt(2) since ||D^T D|| <= 4
        self.assertGreaterEqual(ci["d_real"], ci["d_naive"] / math.sqrt(2.0) * (1 - 1e-12))

    def test_mc_deterministic_and_calibrated(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[0] for t in rs.time_grid(1.0, 64, 0.0)]
        sigma = rs.norm(delta) / 3.0
        a = rs.mc_direct(delta, sigma, 400, 12345)
        b = rs.mc_direct(delta, sigma, 400, 12345)
        self.assertEqual(a, b)
        p_pred = rs.phi(-1.5)
        self.assertLessEqual(abs(a - p_pred), 3.0 * math.sqrt(p_pred * (1 - p_pred) / 800.0))
        # computed-flux MC runs and returns a probability
        e = rs.mc_computed_flux(delta, sigma, 50, 7)
        self.assertTrue(0.0 <= e <= 1.0)

    def test_run_study_quick_pipeline(self):
        res = rs.run_study(grid_sizes=[1, 4, 16], reps=20)
        self.assertIn("families", res)
        self.assertIn("predictions", res)
        self.assertEqual(len(res["monte_carlo"]), 4)
        cell = res["families"]["A"]["per_k"]["100.0"]["windows"]["full"]["16"]
        for key in ("rms_known", "rms_impostor_bound", "eps_required", "distinguishable", "computed_flux_from_b"):
            self.assertIn(key, cell)
        self.assertNotIn("computed_flux_from_b", res["families"]["A"]["per_k"]["100.0"]["windows"]["late"]["16"])
        json.dumps(res)   # serializable
        # endpoint cell (n=1) equals the exact endpoint difference
        ep = res["families"]["A"]["per_k"]["100.0"]["endpoint"]["exact"]["c"]
        self.assertAlmostEqual(cell_n1 := res["families"]["A"]["per_k"]["100.0"]["windows"]["full"]["1"]["rms_known"]["c"],
                               abs(ep), delta=1e-15)
        self.assertGreater(cell_n1, 0.0)


if __name__ == "__main__":
    unittest.main()
