"""Driver-level tests: transient wrapper against Coda's rc_transient, energy audits, reproducibility."""
import json
import unittest

import steady_closed_form as scf
import thermal_sensitivity as ts
import transient_wrapper as tw

QUICK = {"morris_r": 2, "sobol_n": 8, "transient_morris_r": 1, "transient_sobol_n": 2, "grid_stride": 97}


class TransientWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.rc, cls.rc_file = tw.load_rc_transient()
        except FileNotFoundError as exc:
            raise unittest.SkipTest("rc_transient.py unavailable (deviation to report): %s" % exc)

    def test_lump_parameters_match_rc_nominal(self):
        for stack in scf.STACKS:
            ref = self.rc.nominal(stack)
            mine = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            for f in ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv"):
                self.assertAlmostEqual(getattr(mine, f), getattr(ref, f),
                                       delta=1e-12 * max(1.0, abs(getattr(ref, f))), msg=(stack, f))
        self.assertAlmostEqual(tw.lump_parameters(self.rc, scf.make_params("H1", exact_arithmetic=False)).cs, 16.2239, places=4)

    def test_blocked_rear_gives_zero_rear_conductance(self):
        mine = tw.lump_parameters(self.rc, scf.make_params("H2", exact_arithmetic=False, r=None))
        self.assertEqual(mine.gr, 0.0)

    def test_nominal_peaks_match_coda_table_ac7(self):
        for (stack, case), (cH, tH, cS, tS) in ts.CODA_TRANSIENT_PEAKS.items():
            params = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            res = tw.run_case(self.rc, params, tw.scenario_segments(case, 5.0, horizon=1800.0), 1.0)
            self.assertAlmostEqual(res["peak_H"], cH, delta=1e-5, msg=(stack, case))
            self.assertAlmostEqual(res["peak_surface"], cS, delta=1e-5, msg=(stack, case))
            self.assertLessEqual(abs(res["t_peak_H"] - tH), 1.0)
            self.assertLessEqual(abs(res["t_peak_surface"] - tS), 1.0)
            self.assertTrue(res["energy_ok"])
            self.assertLessEqual(max(res["t_peak_H"], res["t_peak_surface"]), 1800.0 - ts.LATE_PEAK_MARGIN_S)

    def test_steady_state_limit_of_transient_matches_closed_form(self):
        for stack in scf.STACKS:
            params = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            res = tw.run_case(self.rc, params, [{"duration": 10000.0, "p": 5.0, "j": 0.1}], 10.0)
            s = scf.steady(scf.make_params(stack, P=5))
            self.assertAlmostEqual(res["final_H"], float(s["T_H"]), delta=1e-9)
            self.assertAlmostEqual(res["final_S"], float(s["T_S"]), delta=1e-9)
            self.assertAlmostEqual(res["final_surface"], float(s["T_surface"]), delta=1e-9)

    def test_scenario_schedules(self):
        seg = tw.scenario_segments("rear_loss_sensor_on", 5, horizon=1800.0)
        self.assertEqual([s["duration"] for s in seg], [600.0, 300.0, 900.0])
        self.assertEqual(seg[1]["gr"], 0.0)
        self.assertEqual([s["p"] for s in seg], [5.0, 5.0, 0.0])
        self.assertEqual(tw.scenario_segments("rear_blocked_from_start", 1)[0]["gr"], 0.0)
        with self.assertRaises(ValueError):
            tw.scenario_segments("unknown", 5)


class DriverTests(unittest.TestCase):
    def test_quick_run_core_acceptance_and_reproducibility_ac6(self):
        first = ts.run(QUICK)
        second = ts.run(QUICK)
        for r in (first, second):
            r.pop("timing_s")
        self.assertEqual(json.dumps(ts.jsonable(first), sort_keys=True), json.dumps(ts.jsonable(second), sort_keys=True))
        status = {a["id"]: a["passed"] for a in first["acceptance"]}
        for ident in ("AC1", "AC2", "AC3", "AC4", "AC4b", "AC5", "AC6"):
            self.assertTrue(status[ident], (ident, first["acceptance"]))
        self.assertTrue(first["grid_classification"]["predictions"]["P4"]["passed"])
        self.assertTrue(first["grid_classification"]["predictions"]["P2"]["passed"])
        self.assertTrue(any("grid_stride" in d for d in first["deviations"]))
        self.assertEqual(len(first["closed_form_nominal"]), 18)
        self.assertEqual(first["analytic_condition"]["per_P"]["5"]["uniform_measure_flip_fraction_h3_15_R1_10"], 0.0)

    def test_summary_is_json_serialisable(self):
        result = ts.run(dict(QUICK, skip_transient=True))
        text = json.dumps(ts.jsonable(ts.summary(result)), sort_keys=True)
        self.assertIn("AC1", text)
        self.assertIn("transient section skipped", result["deviations"])


if __name__ == "__main__":
    unittest.main()
