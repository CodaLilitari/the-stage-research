"""unittest suite for T0-RAD-1 / T0-LUMP2-RAD-1 (thermal-radiation-001).  Standard library only.
Expected values come from independent closed forms, exact rational arithmetic, or Coda's
transcribed executed fixtures -- never from the functions under test."""
import math
import os
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thermal_radiation as tr  # noqa: E402
import reference_fixture as fx  # noqa: E402

STACKS = ("H1", "H2", "H3")
POWERS = (1, 5, 10)
H_VALUES = (3.0, 8.0, 15.0)
EPS_VALUES = (0.0, 0.1, 0.5, 0.9)
T25 = tr.kelvin(25.0)


def coda_linear_step(params, H, S, P, J, step):
    """Coda's documented T0-LUMP2-1 backward-Euler 2x2 formula (rc_transient.simulate), with
    ga = 1/(R_SO + 1/(hA)) as the eps = 0 elimination of the massless surface."""
    ga = 1.0/(params.R_SO + 1.0/params.front.hA)
    A = params.ch/step + params.gr
    B = params.cs/step + ga
    det = A*B + params.g*(A + B)
    bh = params.ch*H/step + P + params.gr*params.reservoir_K
    bs = params.cs*S/step + J + ga*params.front.T_amb_K
    return (bh*(B + params.g) + params.g*bs)/det, (bs*(A + params.g) + params.g*bh)/det


class TestExactReference(unittest.TestCase):
    def test_eps_zero_fraction_equality_with_coda_rows(self):
        for row in fx.STEADY_ROWS:
            with self.subTest(stack=row["stack"], P=row["body_power"], blocked=row["rear_blocked"]):
                exact = tr.nominal_steady_exact(row["stack"], row["body_power"], blocked_rear=row["rear_blocked"])
                self.assertEqual(exact["status"], "unique")
                self.assertEqual(str(exact["front"]), row["front_exact"])
                self.assertEqual(exact["balance"], Fraction(0))
                for key in ("H", "S", "surface", "front", "rear"):
                    self.assertEqual(float(exact[key]), row[key])

    def test_eps_zero_newton_path_matches_reference_floats(self):
        for row in fx.STEADY_ROWS:
            with self.subTest(stack=row["stack"], P=row["body_power"], blocked=row["rear_blocked"]):
                out = tr.nominal_steady(row["stack"], row["body_power"], h=8.0, eps=0.0,
                                        blocked_rear=row["rear_blocked"])
                self.assertEqual(out["status"], "unique")
                self.assertLessEqual(abs(out["T_H_C"] - row["H"]), 1e-9)
                self.assertLessEqual(abs(out["T_S_C"] - row["S"]), 1e-9)
                self.assertLessEqual(abs(out["T_O_C"] - row["surface"]), 1e-9)
                self.assertLessEqual(abs(out["q_front_W"] - row["front"]), 1e-9)
                self.assertLessEqual(abs(out["q_rear_W"] - row["rear"]), 1e-9)
                self.assertEqual(out["q_rad_W"], 0.0)


class TestSteadyProperties(unittest.TestCase):
    def test_grid_unique_balanced_bracketed(self):
        for blocked, powers in ((False, POWERS), (True, (5,))):
            for stack in STACKS:
                for P in powers:
                    for h in H_VALUES:
                        for eps in EPS_VALUES:
                            with self.subTest(stack=stack, P=P, h=h, eps=eps, blocked=blocked):
                                out = tr.nominal_steady(stack, P, h=h, eps=eps, blocked_rear=blocked)
                                self.assertEqual(out["status"], "unique")
                                self.assertLessEqual(abs(out["balance_W"]), 1e-9)
                                self.assertLessEqual(abs(out["node_balance_H_W"]), 1e-9)
                                self.assertLessEqual(abs(out["residual_front_K"]), 1e-9)
                                n = out["newton"]
                                self.assertLessEqual(n["iterations"], 60)
                                self.assertGreaterEqual(out["T_O_K"], n["bracket_lo_K"] - 1e-6)
                                self.assertLessEqual(out["T_O_K"], n["bracket_hi_K"] + 1e-6)
                                self.assertGreaterEqual(out["T_O_K"], T25 - 1e-9)
                                self.assertGreaterEqual(out["q_rad_W"], 0.0)
                                self.assertEqual(out["comparator_label"], "study_comparator_only")

    def test_strict_monotonicity_in_eps_and_h(self):
        for stack in STACKS:
            for P in POWERS:
                for h in H_VALUES:
                    rows = [tr.nominal_steady(stack, P, h=h, eps=e) for e in EPS_VALUES]
                    for a, b in zip(rows, rows[1:]):
                        self.assertLess(b["T_O_K"], a["T_O_K"])
                        self.assertLess(b["T_S_K"], a["T_S_K"])
                        self.assertLess(b["T_H_K"], a["T_H_K"])
                        self.assertGreater(b["q_front_W"], a["q_front_W"])
                        self.assertLess(b["q_rear_W"], a["q_rear_W"])
                for eps in EPS_VALUES:
                    rows = [tr.nominal_steady(stack, P, h=h, eps=eps) for h in H_VALUES]
                    for a, b in zip(rows, rows[1:]):
                        self.assertLess(b["T_O_K"], a["T_O_K"])
                        self.assertLess(b["T_H_K"], a["T_H_K"])
                        self.assertGreater(b["q_front_W"], a["q_front_W"])

    def test_blocked_rear_front_carries_all_power_and_is_hotter(self):
        for stack in STACKS:
            for eps in (0.1, 0.5, 0.9):
                blocked = tr.nominal_steady(stack, 5, h=8.0, eps=eps, blocked_rear=True)
                opened = tr.nominal_steady(stack, 5, h=8.0, eps=eps, blocked_rear=False)
                self.assertLessEqual(abs(blocked["q_front_W"] - 5.1), 1e-9)
                self.assertEqual(blocked["q_rear_W"], 0.0)
                self.assertLess(blocked["T_O_C"], 88.75)        # radiation adds an exit vs the eps = 0 row
                self.assertGreater(blocked["T_O_K"], opened["T_O_K"])
                self.assertGreater(blocked["T_H_K"], opened["T_H_K"])

    def test_degenerate_statuses(self):
        self.assertEqual(tr.nominal_steady("H1", 5, h=0.0, eps=0.0, blocked_rear=True)["status"],
                         "no_finite_steady_state")
        self.assertEqual(tr.nominal_steady("H1", 0, h=0.0, eps=0.0, blocked_rear=True,
                                           sensor_power=0.0)["status"], "nonunique")

    def test_closed_front_finite_rear(self):
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs("H2", h=0.0, eps=0.0)
        out = tr.steady_radiative(R_HS, R_SO, R_rej, front, 5.0, 0.1, T_res)
        self.assertEqual(out["status"], "unique")
        self.assertLessEqual(abs(out["q_front_W"]), 1e-12)
        self.assertLessEqual(abs(out["T_H_K"] - (T_res + 2.0*5.1)), 1e-9)
        self.assertLessEqual(abs(out["T_S_K"] - (T_res + 2.0*5.1 + R_HS*0.1)), 1e-9)
        self.assertLessEqual(abs(out["T_O_K"] - out["T_S_K"]), 1e-9)

    def test_pure_radiation_front(self):
        out = tr.nominal_steady("H1", 5, h=0.0, eps=0.5)
        self.assertEqual(out["status"], "unique")
        self.assertEqual(out["q_conv_W"], 0.0)
        self.assertGreater(out["T_O_K"], T25)
        self.assertLessEqual(abs(out["balance_W"]), 1e-9)
        self.assertLessEqual(abs(out["q_front_W"] - out["q_rad_W"]), 1e-12)

    def test_warm_reservoir_signed_flux(self):
        out = tr.nominal_steady("H1", 0, h=8.0, eps=0.5, T_res_C=60.0, sensor_power=0.0)
        self.assertEqual(out["status"], "unique")
        self.assertLess(out["q_rear_W"], 0.0)                 # reservoir supplies heat
        self.assertGreater(out["q_front_W"], 0.0)
        self.assertTrue(T25 < out["T_O_K"] < out["T_S_K"] < out["T_H_K"] < tr.kelvin(60.0))
        self.assertLessEqual(abs(out["balance_W"]), 1e-9)

    def test_solve_canonical_against_closed_forms(self):
        rad = tr.FrontBoundary(h=0.0, eps=0.9, area=0.01, T_amb_K=T25, T_sur_K=T25)
        sol = tr.solve_canonical(0.0, 1.0, 50.0, rad)
        T_closed = (50.0/rad.radiation_constant + T25**4)**0.25
        self.assertLessEqual(abs(sol.T_K - T_closed), 1e-10*T_closed)
        self.assertLessEqual(sol.iterations, 60)
        conv = tr.FrontBoundary(h=5.0, eps=0.0, area=0.01, T_amb_K=T25, T_sur_K=T25)
        K, M, D = 0.1, 2.0, 40.0
        sol = tr.solve_canonical(K, M, D, conv)
        T_lin = (D + M*conv.hA*T25)/(K + M*conv.hA)
        self.assertLessEqual(abs(sol.T_K - T_lin), 1e-10*T_lin)
        self.assertLessEqual(sol.bracket_lo_K, sol.T_K + 1e-6)
        self.assertGreaterEqual(sol.bracket_hi_K, sol.T_K - 1e-6)
        with self.assertRaises(ValueError):
            tr.solve_canonical(0.0, 1.0, 1.0, tr.FrontBoundary(0.0, 0.0, 0.01, T25, T25))


class TestLinearization(unittest.TestCase):
    def setUp(self):
        self.front = tr.FrontBoundary(h=8.0, eps=0.7, area=0.01, T_amb_K=T25, T_sur_K=T25)

    def test_flux_identities_and_bound_B1(self):
        Tw = self.front.T_sur_K
        for T in (298.15, 300.0, 320.0, 350.0, 400.0):
            dT = T - Tw
            Tbar = 0.5*(T + Tw)
            mean = tr.flux_linearization(self.front, T, Tbar)
            self.assertLessEqual(abs(mean["exact_W"] - mean["mean_identity_W"]), 1e-12*max(1.0, abs(mean["exact_W"])))
            self.assertLessEqual(abs(mean["exact_W"] - mean["linear_W"]*(1.0 + mean["e_mean_relative"])),
                                 1e-12*max(1.0, abs(mean["exact_W"])))
            self.assertGreaterEqual(mean["error_W"], -1e-15)              # mean coefficient underestimates
            cold = tr.flux_linearization(self.front, T, Tw)
            x = dT/Tw
            series = 4.0*self.front.radiation_constant*Tw**3*dT*(1.0 + 1.5*x + x*x + 0.25*x**3)
            self.assertLessEqual(abs(cold["exact_W"] - series), 1e-12*max(1.0, abs(series)))
            for T_m in (280.0, 298.15, 310.0, 340.0, 420.0):
                lin = tr.flux_linearization(self.front, T, T_m)
                self.assertTrue(lin["bound_B1_holds"])
                self.assertLessEqual(abs(lin["error_W"]), lin["bound_B1_W"]*(1.0 + 1e-12) + 1e-300)

    def test_solution_identity_B2_bound_B3_and_signs(self):
        for blocked in (False, True):
            for stack in STACKS:
                for P in POWERS:
                    for h in H_VALUES:
                        for eps in (0.1, 0.5, 0.9):
                            R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs(stack, h=h, eps=eps, blocked_rear=blocked)
                            exact = tr.steady_radiative(R_HS, R_SO, R_rej, front, float(P), 0.1, T_res)
                            Tbar = 0.5*(exact["T_O_K"] + front.T_sur_K)
                            for T_m in (front.T_sur_K, Tbar, Tbar + 15.0):
                                with self.subTest(stack=stack, P=P, h=h, eps=eps, blocked=blocked, T_m=T_m):
                                    an = tr.linearization_error_analysis(R_HS, R_SO, R_rej, front, float(P), 0.1,
                                                                         T_res, T_m, exact_row=exact)
                                    self.assertLessEqual(abs(an["identity_B2_residual_K"]), 1e-8)
                                    self.assertLessEqual(abs(an["identity_H_residual_K"]), 1e-8)
                                    self.assertTrue(an["bound_B3_holds"])
                                    if T_m <= Tbar:
                                        self.assertGreaterEqual(an["error_O_K"], -1e-9)   # hot-side (conservative) error
                                    if T_m == Tbar:
                                        self.assertLessEqual(abs(an["error_O_K"] - an["mean_cubic_law_K"]), 1e-8)


class TestTransient(unittest.TestCase):
    def test_eps_zero_step_matches_coda_2x2_algebra(self):
        params = tr.nominal_transient("H2", h=8.0, eps=0.0)
        H = Hc = 310.0
        S = Sc = 305.0
        for _ in range(50):
            H, S, O, q, sol = tr.implicit_step(params, H, S, 5.0, 0.1, 1.0)
            Hc, Sc = coda_linear_step(params, Hc, Sc, 5.0, 0.1, 1.0)
            self.assertLessEqual(abs(H - Hc), 1e-8)
            self.assertLessEqual(abs(S - Sc), 1e-8)
            self.assertLessEqual(abs((S - O)/params.R_SO - q), 1e-9)

    def test_one_node_limit_against_coda_fixture(self):
        one = fx.ONE_NODE
        closed = tr.FrontBoundary(h=0.0, eps=0.0, area=0.01, T_amb_K=T25, T_sur_K=T25)
        params = tr.TransientParameters(ch=float(one["capacity_J_K"]), cs=1.0, g=0.0, R_SO=0.1,
                                        gr=1.0/one["resistance_K_W"], reservoir_K=tr.kelvin(one["bath_C"]), front=closed)
        exact = one["bath_C"] + one["power_W"]*one["resistance_K_W"]*(-math.expm1(-one["time_s"]/(one["resistance_K_W"]*one["capacity_J_K"])))
        self.assertLessEqual(abs(exact - one["exact_C"]), 1e-12)
        errors = []
        for dt in (1.0, 0.5, 0.25):
            run = tr.simulate(params, (tr.kelvin(one["initial_C"]), tr.kelvin(one["initial_C"])),
                              [dict(duration=one["time_s"], p=one["power_W"], j=0.0)], dt)
            final = run["trace"][-1]
            self.assertLessEqual(abs(final["S_K"] - tr.kelvin(one["initial_C"])), 1e-9)   # decoupled S
            err = abs(tr.celsius(final["H_K"]) - exact)
            self.assertLessEqual(abs(err - one["backward_euler_abs_error_K"][dt]), 1e-9)
            errors.append(err)
        for a, b in zip(errors, errors[1:]):
            self.assertTrue(1.8 <= a/b <= 2.1)

    def test_coupled_eigenmodes_translated_to_kelvin(self):
        base = 300.0
        front = tr.FrontBoundary(h=200.0, eps=0.0, area=0.01, T_amb_K=base, T_sur_K=base)   # hA = 2
        params = tr.TransientParameters(ch=1.0, cs=1.0, g=1.0, R_SO=0.5, gr=1.0, reservoir_K=base, front=front)
        errors = []
        for dt in (0.1, 0.05, 0.025):
            run = tr.simulate(params, (base + 1.0, base), [dict(duration=1.0, p=0.0, j=0.0)], dt)
            final = run["trace"][-1]
            H_exact = 0.5*(math.exp(-1.0) + math.exp(-3.0))
            S_exact = 0.5*(math.exp(-1.0) - math.exp(-3.0))
            errors.append(max(abs(final["H_K"] - base - H_exact), abs(final["S_K"] - base - S_exact)))
        for err, ref in zip(errors, fx.TWO_NODE_MODE_ERRORS_K):
            self.assertLessEqual(abs(err - ref), 1e-9)
        for a, b in zip(errors, errors[1:]):
            self.assertTrue(1.7 <= a/b <= 2.2)

    def test_long_time_equilibrium_matches_nonlinear_steady(self):
        for stack in STACKS:
            for eps in (0.0, 0.5, 0.9):
                with self.subTest(stack=stack, eps=eps):
                    params = tr.nominal_transient(stack, h=8.0, eps=eps)
                    run = tr.simulate(params, (T25, T25), [dict(duration=10000.0, p=5.0, j=0.1)], 10.0)
                    final = run["trace"][-1]
                    steady = tr.nominal_steady(stack, 5, h=8.0, eps=eps)
                    self.assertLessEqual(abs(final["H_K"] - steady["T_H_K"]), 1e-8)
                    self.assertLessEqual(abs(final["S_K"] - steady["T_S_K"]), 1e-8)
                    self.assertLessEqual(abs(final["O_K"] - steady["T_O_K"]), 1e-8)
                    self.assertLessEqual(abs(final["front_W"] - steady["q_front_W"]), 1e-9)
                    self.assertLessEqual(abs(final["rear_W"] - steady["q_rear_W"]), 1e-9)

    def test_equilibrium_is_held(self):
        steady = tr.nominal_steady("H3", 5, h=8.0, eps=0.5)
        params = tr.nominal_transient("H3", h=8.0, eps=0.5)
        run = tr.simulate(params, (steady["T_H_K"], steady["T_S_K"]), [dict(duration=1000.0, p=5.0, j=0.1)], 10.0)
        for row in run["trace"]:
            self.assertLessEqual(abs(row["H_K"] - steady["T_H_K"]), 1e-8)
            self.assertLessEqual(abs(row["S_K"] - steady["T_S_K"]), 1e-8)

    def test_energy_accounting_and_trace_reconstruction(self):
        params = tr.nominal_transient("H3", h=8.0, eps=0.9)
        run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
        self.assertLessEqual(run["max_energy_residual_abs_J"], run["energy_tolerance_J"])
        net = sum(r["dt"]*(r["p_W"] + r["j_W"] - r["front_W"] - r["rear_W"]) for r in run["trace"][1:])
        self.assertLessEqual(abs(net - run["final_stored_energy_change_J"]), run["energy_tolerance_J"])
        self.assertLessEqual(abs(run["injected_J"] - (900*5.0 + 3600*0.1)), 1e-8)
        for r in run["trace"]:
            self.assertLessEqual(abs(r["front_W"] - r["conv_W"] - r["rad_W"]), 1e-12)

    def test_rear_loss_event_continuity_and_zero_rear_flux(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.5)
        run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
        event = run["events"][1]
        self.assertEqual(event["time"], 600.0)
        self.assertEqual(event["before_state_K"], event["after_state_K"])
        self.assertEqual(event["old_gr"], 0.5)
        self.assertEqual(event["new_gr"], 0.0)
        self.assertEqual(run["events"][2]["new_gr"], 0.0)                 # loss persists
        for r in run["trace"]:
            if r["time"] > 600.0:
                self.assertEqual(r["rear_W"], 0.0)

    def test_pointwise_eps_ordering(self):
        for stack in STACKS:
            for loss in (False, True):
                runs = [tr.simulate(tr.nominal_transient(stack, h=8.0, eps=e), (T25, T25),
                                    fx.fault_segments(loss=loss), 1.0) for e in (0.0, 0.5, 0.9)]
                for cooler, warmer in zip(runs[1:], runs[:-1]):
                    self.assertEqual(len(cooler["trace"]), len(warmer["trace"]))
                    for a, b in zip(cooler["trace"], warmer["trace"]):
                        self.assertEqual(a["time"], b["time"])
                        self.assertLessEqual(a["H_K"], b["H_K"] + 1e-9)
                        self.assertLessEqual(a["S_K"], b["S_K"] + 1e-9)
                        self.assertLessEqual(a["O_K"], b["O_K"] + 1e-9)

    def test_rear_loss_at_least_as_warm_as_intact(self):
        for eps in (0.0, 0.5):
            params = tr.nominal_transient("H2", h=8.0, eps=eps)
            intact = tr.simulate(params, (T25, T25), fx.fault_segments(loss=False), 1.0)
            loss = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
            for a, b in zip(loss["trace"], intact["trace"]):
                self.assertGreaterEqual(a["H_K"], b["H_K"] - 1e-9)
                self.assertGreaterEqual(a["S_K"], b["S_K"] - 1e-9)
            self.assertGreater(tr.trace_peak(loss["trace"], "H_K")["H_K"], tr.trace_peak(intact["trace"], "H_K")["H_K"])

    def test_eps_zero_cross_check_against_coda_report(self):
        """ASSUMPTION: Coda's REPORT scenarios used dt = 1 s (not stated); tolerance 1e-5 K on
        6-decimal printed values."""
        for (stack, case), ref in fx.TRANSIENT_REPORT.items():
            with self.subTest(stack=stack, case=case):
                run = tr.simulate(tr.nominal_transient(stack, h=8.0, eps=0.0), (T25, T25),
                                  fx.fault_segments(loss=(case == "rear_loss")), fx.TRANSIENT_REPORT_DT_ASSUMED_S)
                peak_H = tr.trace_peak(run["trace"], "H_K")
                self.assertEqual(peak_H["time"], ref["peak_H_time_s"])
                self.assertLessEqual(abs(tr.celsius(peak_H["H_K"]) - ref["peak_H_C"]), 1e-5)
                peak_O = tr.trace_peak(run["trace"], "O_K")
                self.assertLessEqual(abs(tr.celsius(peak_O["O_K"]) - ref["peak_surface_C"]), 1e-5)
                self.assertLessEqual(abs(tr.celsius(run["trace"][-1]["H_K"]) - ref["H_3600_C"]), 1e-5)

    def test_initial_row_surface_satisfies_massless_relation(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.9)
        run = tr.simulate(params, (T25 + 20.0, T25 + 10.0), [dict(duration=5.0, p=1.0, j=0.1)], 1.0)
        row = run["trace"][0]
        self.assertLessEqual(abs((row["S_K"] - row["O_K"])/params.R_SO - row["front_W"]), 1e-9)
        self.assertEqual(row["time"], 0.0)


class TestInputRejection(unittest.TestCase):
    def test_front_boundary_guards(self):
        for kwargs in (dict(h=-1.0), dict(eps=1.5), dict(eps=float("nan")), dict(h=float("inf")),
                       dict(area=0.0), dict(T_amb_K=0.0), dict(T_sur_K=-5.0), dict(eps=True)):
            base = dict(h=8.0, eps=0.5, area=0.01, T_amb_K=T25, T_sur_K=T25)
            base.update(kwargs)
            with self.assertRaises(ValueError):
                tr.FrontBoundary(**base)

    def test_steady_guards(self):
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs("H1", eps=0.5)
        for args in ((-1.0, R_SO, R_rej, front, 5.0, 0.1, T_res), (R_HS, R_SO, 0.0, front, 5.0, 0.1, T_res),
                     (R_HS, R_SO, R_rej, front, -5.0, 0.1, T_res), (R_HS, R_SO, R_rej, front, 5.0, -0.1, T_res),
                     (R_HS, R_SO, R_rej, front, 5.0, 0.1, 0.0), (R_HS, R_SO, R_rej, "front", 5.0, 0.1, T_res),
                     (R_HS, R_SO, float("nan"), front, 5.0, 0.1, T_res)):
            with self.assertRaises(ValueError):
                tr.steady_radiative(*args)
        with self.assertRaises(ValueError):
            tr.nominal_steady("H4", 5)

    def test_transient_guards(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.5)
        good = [dict(duration=10, p=1, j=0.1)]
        with self.assertRaises(ValueError):
            tr.TransientParameters(ch=0.0, cs=1.0, g=1.0, R_SO=0.1, gr=0.5, reservoir_K=T25, front=params.front)
        with self.assertRaises(ValueError):
            tr.TransientParameters(ch=1.0, cs=1.0, g=1.0, R_SO=0.1, gr=-0.5, reservoir_K=T25, front=params.front)
        for segments, dt in (([dict(duration=10, p=11, j=0.1)], 1.0), ([dict(duration=10, p=1, j=0.3)], 1.0),
                             ([dict(duration=10, p=1, j=0.1, bogus=1)], 1.0), ([dict(duration=10, p=1)], 1.0),
                             ([dict(duration=1e9, p=1, j=0.1)], 1.0), ([], 1.0), (good, 0.0),
                             (good, float("nan")), ([dict(duration=-1, p=1, j=0.1)], 1.0),
                             ([dict(duration=10, p=1, j=0.1, gr=-1.0)], 1.0)):
            with self.assertRaises(ValueError):
                tr.simulate(params, (T25, T25), segments, dt)
        with self.assertRaises(ValueError):
            tr.simulate(params, (0.0, T25), good, 1.0)
        with self.assertRaises(ValueError):
            tr.simulate(params, (T25,), good, 1.0)
        with self.assertRaises(ValueError):
            tr.simulate("params", (T25, T25), good, 1.0)


if __name__ == "__main__":
    unittest.main()
