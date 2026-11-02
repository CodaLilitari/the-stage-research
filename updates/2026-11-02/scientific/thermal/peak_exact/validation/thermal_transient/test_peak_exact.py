"""Tests for peak_exact.py (unexecuted by the author; Red executes).  Standard library only."""
import math
import unittest
from dataclasses import replace

import peak_exact as pe

try:
    import rc_transient as rc
except ImportError:  # pragma: no cover
    rc = None

# Coda's executed backward-Euler values from REPORT.md (dt assumed 1 s); used only with loose
# tolerances that allow first-order discretization error.  Not physical validation.
REPORT = {
    ("H1", "intact", 0.1): dict(H900=33.831193, pk=33.554994, tpk=900.0, H3600=25.170303),
    ("H1", "rear_loss", 0.1): dict(H900=61.143480, pk=59.747155, tpk=901.0, H3600=26.374204),
    ("H1", "rear_loss", 0.0): dict(H900=60.446481, pk=59.055570, tpk=901.0, H3600=25.104135),
    ("H2", "intact", 0.1): dict(H900=33.861287, pk=33.362444, tpk=900.0, H3600=25.168602),
    ("H2", "rear_loss", 0.1): dict(H900=55.545063, pk=53.153638, tpk=904.0, H3600=26.798252),
    ("H2", "rear_loss", 0.0): dict(H900=54.963957, pk=52.578375, tpk=904.0, H3600=25.520601),
    ("H3", "intact", 0.1): dict(H900=33.884652, pk=32.963939, tpk=900.0, H3600=25.165436),
    ("H3", "rear_loss", 0.1): dict(H900=50.169875, pk=45.881263, tpk=914.0, H3600=28.187988),
    ("H3", "rear_loss", 0.0): dict(H900=49.704285, pk=45.421846, tpk=913.0, H3600=26.934740),
}


def all_phases():
    return [pe.manufactured_phase()] + [pe.stack_phase(s, intact, p, j) for s in ("H1", "H2", "H3")
                                        for intact in (True, False) for p in (0.0, 5.0) for j in (0.0, 0.1)]


class ParameterTests(unittest.TestCase):
    def test_resistance_and_capacities_match_coda_nominal(self):
        self.assertAlmostEqual(pe.front_resistance(0.0005), 2351 / 10800, places=12)
        self.assertAlmostEqual(pe.surface_node_capacity(0.0005), 16.2239, places=9)
        self.assertAlmostEqual(pe.surface_node_capacity(0.001), 31.6739, places=9)
        self.assertAlmostEqual(pe.surface_node_capacity(0.002), 62.5739, places=9)


class ModeTests(unittest.TestCase):
    def test_eigenpairs_satisfy_matrix_equation_and_ordering(self):
        for ph in all_phases():
            md = pe.modes(ph)
            self.assertLess(md.lam_fast, md.lam_slow)
            self.assertLess(md.lam_slow, 0.0)
            for lam, r in ((md.lam_slow, md.r_slow), (md.lam_fast, md.r_fast)):
                row1 = (-(ph.g + ph.gr) + ph.g * r) / ph.ch - lam
                row2 = (ph.g - (ph.g + ph.gb) * r) / ph.cs - lam * r
                self.assertLess(abs(row1), 1e-12)
                self.assertLess(abs(row2), 1e-12)

    def test_steady_state_satisfies_both_equations(self):
        for ph in all_phases():
            md = pe.modes(ph)
            h, s = ph.ambient + md.x_inf, ph.ambient + md.y_inf
            self.assertLess(abs(-ph.g * (h - s) - ph.gr * (h - ph.ambient) + ph.p), 1e-9)
            self.assertLess(abs(ph.g * (h - s) + ph.j - ph.gb * (s - ph.ambient)), 1e-9)

    def test_per_mode_energy_identity(self):
        for ph in all_phases():
            for res in pe.mode_energy_identity_residuals(ph, pe.modes(ph)):
                self.assertLess(abs(res), 1e-10)

    def test_degenerate_cases_raise_instead_of_invalid_sqrt_or_log(self):
        ph = pe.manufactured_phase()
        with self.assertRaises(pe.DegenerateCase):
            pe.modes(replace(ph, g=0.0))
        with self.assertRaises(pe.DegenerateCase):
            pe.modes(replace(ph, gb=0.0, gr=0.0))


class ManufacturedCaseTests(unittest.TestCase):
    def setUp(self):
        self.ph = pe.manufactured_phase()
        self.md = pe.modes(self.ph)
        self.amp = pe.amplitudes(self.ph, self.md, 60.0, 58.0)
        self.res = pe.post_shutoff_peak(self.ph, 60.0, 58.0, 0.0)

    def test_initial_conditions_and_both_odes_pointwise(self):
        st0 = pe.state(self.ph, self.md, self.amp, 0.0)
        self.assertAlmostEqual(st0["H"], 60.0, places=9)
        self.assertAlmostEqual(st0["S"], 58.0, places=9)
        for t in (0.0, 0.5, 3.75, 50.0, 1000.0):
            st = pe.state(self.ph, self.md, self.amp, t)
            r_h = self.ph.ch * st["dH"] + self.ph.g * (st["H"] - st["S"]) + self.ph.gr * (st["H"] - 25.0) - self.ph.p
            r_s = self.ph.cs * st["dS"] - self.ph.g * (st["H"] - st["S"]) - self.ph.j + self.ph.gb * (st["S"] - 25.0)
            self.assertLess(abs(r_h), 1e-9)
            self.assertLess(abs(r_s), 1e-9)

    def test_hand_estimates(self):
        res, ext, md = self.res, self.res["extremum"], self.md
        self.assertEqual(ext["status"], "post_shutoff_maximum")
        self.assertTrue(3.70 < ext["t_star"] < 3.80)
        self.assertAlmostEqual(res["peak_surface"], 57.964, delta=0.01)
        self.assertAlmostEqual(res["peak_S"], 58.538, delta=0.01)
        self.assertAlmostEqual(res["H_at_peak"], 59.090, delta=0.01)
        self.assertAlmostEqual(res["dS0"], 0.4125, delta=0.002)
        self.assertLess(res["dH0"], 0.0)
        self.assertAlmostEqual(res["surface0"], 57.435, delta=0.002)
        self.assertAlmostEqual(md.lam_slow, -0.0021594, delta=1e-5)
        self.assertAlmostEqual(md.lam_fast, -0.51553, delta=1e-3)
        self.assertAlmostEqual(res["surface_inf"], 26.25, places=9)
        self.assertTrue(res["rising_criterion_met"])

    def test_stationarity_balance_at_peak(self):
        pk = pe.state(self.ph, self.md, self.amp, self.res["extremum"]["t_star"])
        self.assertLess(abs(pk["dS"]), 1e-9)
        self.assertLess(abs(self.ph.g * (pk["H"] - pk["S"]) + self.ph.j - self.ph.gb * (pk["S"] - 25.0)), 1e-9)

    def test_rk4_independent_integration_matches_modal_solution(self):
        samples = pe.rk4_integrate(self.ph, 60.0, 58.0, 20.0, 0.01)
        worst = max(abs(s - pe.state(self.ph, self.md, self.amp, t)["S"]) for t, h, s in samples)
        self.assertLess(worst, 1e-7)
        t_max, _h, s_max = max(samples, key=lambda row: row[2])
        self.assertLess(abs(t_max - self.res["extremum"]["t_star"]), 0.011)
        self.assertLess(abs(s_max - self.res["peak_S"]), 1e-5)

    def test_energy_identity_vs_shape(self):
        # Identity holds for ANY amplitudes (here deliberately wrong ones): it cannot verify the shape.
        wrong = pe.Amplitudes(a_slow=1.0, a_fast=-3.0)
        for t in (0.0, 2.0, 100.0):
            st = pe.state(self.ph, self.md, wrong, t)
            lhs = self.ph.ch * st["dH"] + self.ph.cs * st["dS"]
            rhs = self.ph.j - self.ph.gb * (st["S"] - 25.0)
            self.assertLess(abs(lhs - rhs), 1e-9)
        self.assertGreater(abs(pe.state(self.ph, self.md, wrong, 0.0)["H"] - 60.0), 1.0)


class ClassificationTests(unittest.TestCase):
    def test_zero_fast_amplitude_is_single_mode_monotone(self):
        md = pe.modes(pe.manufactured_phase())
        ext = pe.surface_extremum(md, pe.Amplitudes(a_slow=1.0, a_fast=0.0))
        self.assertEqual(ext.status, "single_mode_monotone")
        self.assertIsNone(ext.t_star)

    def test_state_on_slow_mode_has_no_post_shutoff_extremum(self):
        ph = pe.manufactured_phase()
        md = pe.modes(ph)
        res = pe.post_shutoff_peak(ph, 25.0 + md.x_inf + 1.0, 25.0 + md.y_inf + md.r_slow, 0.0)
        self.assertNotIn(res["extremum"]["status"], ("post_shutoff_maximum", "post_shutoff_minimum"))

    def test_equal_initial_temperatures_do_not_rise(self):
        res = pe.post_shutoff_peak(pe.manufactured_phase(), 58.0, 58.0, 0.0)
        self.assertLess(res["dS0"], 0.0)
        self.assertEqual(res["peak_kind"], "at_shutoff")
        self.assertEqual(res["peak_time"], 0.0)


class VerifyTraceTests(unittest.TestCase):
    def test_exact_samples_pass_verification(self):
        ph = pe.manufactured_phase()
        md = pe.modes(ph)
        amp = pe.amplitudes(ph, md, 60.0, 58.0)
        trace = []
        for k in range(61):
            st = pe.state(ph, md, amp, float(k))
            trace.append(dict(time=900.0 + k, dt=0.0 if k == 0 else 1.0, H=st["H"], S=st["S"],
                              surface=st["surface"], front=ph.gb * (st["S"] - 25.0),
                              rear=ph.gr * (st["H"] - 25.0), p=0.0, j=ph.j))
        ver = pe.verify_trace(trace, ph)
        self.assertLess(ver["max_abs_dev_S"], 1e-9)
        self.assertLessEqual(abs(ver["discrete_peak_time"] - ver["exact"]["peak_time"]), 0.75)
        self.assertTrue(0.0 <= ver["exact"]["peak_surface"] - ver["discrete_peak_surface"] <= 0.01)
        self.assertTrue(ver["within_tolerance"])
        self.assertTrue(math.isfinite(ver["discrete_energy_residual_J"]))


class AnalyticVersusReportTests(unittest.TestCase):
    """Analytic chain vs Coda's executed table; loose tolerances absorb backward-Euler error.
    Depends on the ASSUMED schedule in peak_exact.scenario_segments."""

    def test_analytic_chain_against_report_values(self):
        for (stack, case, j), rep in REPORT.items():
            h900, s900 = pe.analytic_shutoff_state(stack, case, j)
            ph = pe.stack_phase(stack, case == "intact", 0.0, j)
            res = pe.post_shutoff_peak(ph, h900, s900, pe.SHUTOFF_S)
            self.assertAlmostEqual(h900, rep["H900"], delta=0.01 if case == "intact" else 0.1)
            self.assertAlmostEqual(res["peak_surface"], rep["pk"], delta=0.1)
            self.assertLessEqual(abs((res["peak_time"] or pe.SHUTOFF_S) - rep["tpk"]), 2.0)
            md = pe.modes(ph)
            h3600 = pe.state(ph, md, pe.amplitudes(ph, md, h900, s900), pe.HORIZON_S - pe.SHUTOFF_S)["H"]
            self.assertAlmostEqual(h3600, rep["H3600"], delta=0.05)
            if case == "intact":
                self.assertLess((res["peak_time"] or pe.SHUTOFF_S) - pe.SHUTOFF_S, 0.5)
                self.assertLess(res["peak_surface"] - res["surface0"], 1e-3)
            else:
                self.assertEqual(res["extremum"]["status"], "post_shutoff_maximum")


@unittest.skipUnless(rc is not None, "rc_transient.py not importable")
class ExecutedScenarioTests(unittest.TestCase):
    def test_h1_rear_loss_sensor_on_reproduces_report_and_verifies(self):
        sim = rc.simulate(rc.nominal("H1"), (25.0, 25.0), pe.scenario_segments("rear_loss", 0.1), 1.0)
        ver = pe.verify_trace(sim["trace"], pe.stack_phase("H1", False, 0.0, 0.1))
        self.assertAlmostEqual(ver["H900"], 61.143480, delta=1e-5)  # schedule assumption check
        self.assertEqual(ver["discrete_peak_time"], 901.0)
        self.assertAlmostEqual(ver["discrete_peak_surface"], 59.747155, delta=1e-5)
        self.assertAlmostEqual(sim["trace"][-1]["H"], 26.374204, delta=1e-5)
        self.assertLess(abs(ver["discrete_energy_residual_J"]), 1e-6)
        self.assertTrue(ver["within_tolerance"])

    def test_all_nine_scenarios_within_advisory_tolerance(self):
        for row in pe.run_executed_scenarios(rc, 1.0):
            self.assertTrue(row["executed"]["within_tolerance"], msg=f"{row['stack']}/{row['case']}/{row['sensor_w']}")


if __name__ == "__main__":
    unittest.main()
