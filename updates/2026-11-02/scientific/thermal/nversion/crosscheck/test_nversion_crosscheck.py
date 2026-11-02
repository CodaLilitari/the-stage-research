"""Unit tests for nversion_crosscheck.py (standard library only; in-memory fixtures; no file writes).
Transcribed target numbers come from the task bundle receipts (reference_results.json, FV compact copy,
RAD compact copy); agreement here tests the analytic solver and the comparison logic, nothing physical."""
import unittest

import nversion_crosscheck as nv

A_H1, B_H1, RCONV = 0.21768518518518518, 12.717685185185186, 12.5


def fv_run(stack="H1", case="F1", surf_peak=59.780334051985264, t_peak=901.5):
    return {"stack": stack, "case": case, "perturbation": {},
            "parameters": {"stack": {"t_silicone_outer": 0.0005 if stack == "H1" else 0.002, "t_silicone_inner": 0.0005, "t_film": 5e-5, "area": 0.01},
                           "materials": {"k_silicone": 0.27, "k_film": 0.2, "rho_silicone": 1030.0, "cp_silicone": 1500.0},
                           "boundary_initial": {"h": 8.0, "r_c_outer": 2e-4, "r_c_inner": 2e-4, "r_rej": 2.0},
                           "boundary_final": {"h": 8.0, "r_c_outer": 2e-4, "r_c_inner": 2e-4, "r_rej": "inf"},
                           "mesh": {"front_convection_resistance_K_per_W": 12.5}},
            "peaks": {"surface_actual": {"value_C": surf_peak, "time_s": t_peak}, "sensor_actual": {"value_C": 60.408, "time_s": 900.5},
                      "H": {"value_C": 61.14079562308128, "time_s": 900.0}},
            "checkpoints": {"600": {"time_s": 600.0, "surface_actual_C": 33.5543, "sensor_actual_C": 33.7033, "H_C": 33.8306, "front_flux_W": 0.68435, "rear_flux_W": 4.4153}},
            "samples_60s": [{"time_s": 0.0, "surface_actual_C": 25.0, "sensor_actual_C": 25.0, "H_C": 25.0, "front_flux_W": 0.0, "rear_flux_W": 0.0},
                            {"time_s": 60.0, "surface_actual_C": 30.124073470622918, "sensor_actual_C": 30.26629435940986, "H_C": 30.474065557340715,
                             "front_flux_W": 0.4099258776498334, "rear_flux_W": 2.7370327786703577}],
            "energy": {"stored_change_J": 49.63496890046552, "exported_front_to_ambient_J": 2434.131031936886, "exported_rear_to_reservoir_J": 2376.233999163477},
            "long_time_target_if_final_conditions_held": {"status": "unique", "surface_C": 26.24999999999794, "sensor_C": 26.27176851851642,
                                                          "H_C": 26.27176851851639, "front_W": 0.0999999999998352, "rear_W": 0.0},
            "final_state": {"H_C": 26.373439186119526, "body_power_W": 0.0, "sensor_power_W": 0.1}}


STEADY = {"rows": [
    {"stack": "H1", "a": A_H1, "b": B_H1, "convection_resistance": RCONV, "body_power": 5.0, "sensor_power": 0.1, "rear_blocked": False,
     "H": 33.83119986113005, "S": 33.70398462379287, "surface": 33.55500086793716, "front": 0.6844000694349729, "rear": 4.415599930565027},
    {"stack": "H1", "a": A_H1, "b": B_H1, "convection_resistance": RCONV, "body_power": 5.0, "sensor_power": 0.1, "rear_blocked": True,
     "H": 90.94862037037036, "S": 89.86019444444445, "surface": 88.75, "front": 5.1, "rear": 0.0}]}

RAD = {"steady_rows": [{"stack": "H1", "body_power_W": 1.0, "sensor_power_W": 0.1, "h_W_m2K": 3.0, "eps": 0.0, "rear_blocked": False, "R_rej_K_W": 2.0,
                        "T_H_C": 27.075770252289658, "T_S_C": 27.08401728299026, "T_O_C": 27.07049579517235,
                        "q_front_W": 0.062114873855170456, "q_rear_W": 1.037885126144829}],
       "blocked_rear_rows": [{"stack": "H1", "body_power_W": 5.0, "sensor_power_W": 0.1, "h_W_m2K": 3.0, "eps": 0.0, "rear_blocked": True, "R_rej_K_W": None,
                              "T_H_C": 197.1986203703704, "T_S_C": 196.11019444444446, "T_O_C": 195.0, "q_front_W": 5.1, "q_rear_W": 0.0}],
       "transient_runs": [{"stack": "H1", "eps": 0.0, "h_W_m2K": 8.0, "case": "rear_loss", "dt_s": 1.0,
                           "peaks": {"peak_H": {"C": 61.14348016398628, "time_s": 900.0}, "peak_S": {"C": 60.35227038414962, "time_s": 901.0},
                                     "peak_surface": {"C": 59.74715511252339, "time_s": 901.0}},
                           "checkpoints": {"600": {"time_s": 600.0, "H_C": 33.83048177710879, "S_C": 33.70323770615113, "O_C": 33.554266735083104,
                                                   "front_W": 0.6843413388066483, "rear_W": 4.4152408885543935}},
                           "final": {"time_s": 3600.0, "H_C": 26.374204319376418, "S_C": 26.37324129419727, "O_C": 26.349735893561956, "front_W": 0.108, "rear_W": 0.0},
                           "samples_60s": [{"time_s": 60.0, "H_C": 30.46350391838422, "S_C": 30.20106374398074, "O_C": 30.112038539489333,
                                            "front_W": 0.40896308315914665, "rear_W": 2.73175195919211}]}]}

ORACLE = {"cases": [{"stack": "H1", "scenario": "F1",
                     "segments": [{"projection_defect": 5.0e-6, "tail_estimate_K_at_dt_1s": {"surface": 1e-29}}],
                     "rows": [{"t_s": 0.0, "surface_C": 25.0, "sensor_C": 25.0, "H_C": 25.0, "front_W": 0.0, "rear_W": 0.0},
                              {"t_s": 60.0, "surface_C": 30.136979411731506, "sensor_C": 30.27932395957631, "H_C": 30.486629624370707,
                               "front_W": 0.4109583529385205, "rear_W": 2.7433148121853534},
                              {"t_s": 600.0, "surface_C": 33.5543, "sensor_C": 33.7033, "H_C": 33.8306, "front_W": 0.68435, "rear_W": 0.0}],
                     "energy_audits": [{"t_s": 3600.0, "stored_J": 49.62327152558472, "front_loss_J": 2434.143819555101, "rear_loss_J": 2376.232908809072}]}]}

FV = {"runs": [fv_run()],
      "verification": {"time_refinement": {"details": [{"stack": "H1", "case": "F1", "pairs_K": {"0.5_vs_0.25": {
                           "surface_actual_C": 0.012195967557730114, "sensor_actual_C": 0.00953017428463454, "H_C": 0.00632790270602257}}}]},
                       "mesh_refinement": {"details": [{"stack": "H1", "case": "F1", "max_difference_K": {"surface_actual_C": 0.002531133543673292,
                                                        "sensor_actual_C": 0.0023258409317321593, "H_C": 0.0022207826944153908}},
                                                       {"stack": "H1", "case": "F1", "max_difference_K": {"surface_actual_C": 6.620261302714425e-06,
                                                        "sensor_actual_C": 0.0002641043254065778, "H_C": 7.291664083197702e-06}}]},
                       "steady_match": {"details": [{"stack": "H1", "mesh": [1, 1], "rear_blocked": True,
                                                     "fv": {"H_C": 90.94862037037139, "sensor_C": 89.86019444444544, "surface_C": 88.75000000000098, "front_W": 5.100000000000078, "rear_W": 0.0}}]}},
      "cross_check_against_lump2": {"rows": [{"stack": "H1", "case": "F1", "lump2": {"peak_H_C": 61.14348, "peak_H_time_s": 900.0, "peak_surface_C": 59.747155,
                                                                                    "peak_surface_time_s": 901.0, "H_3600_C": 26.374204}}]}}


class TestAnalytic(unittest.TestCase):
    def test_reference_open_p5(self):
        an = nv.analytic_steady(A_H1, B_H1, RCONV, 2.0, 5.0, 0.1, False)
        ref = STEADY["rows"][0]
        for q in ("H", "S", "surface", "front", "rear"):
            self.assertAlmostEqual(an[q], ref[q], delta=1e-9, msg=q)

    def test_reference_blocked(self):
        an = nv.analytic_steady(A_H1, B_H1, RCONV, None, 5.0, 0.1, True)
        for q, v in (("H", 90.94862037037036), ("S", 89.86019444444445), ("surface", 88.75), ("front", 5.1), ("rear", 0.0)):
            self.assertAlmostEqual(an[q], v, delta=1e-9, msg=q)

    def test_rad_h3_row(self):
        r_conv = 1.0 / (3.0 * 0.01)
        an = nv.analytic_steady(A_H1, B_H1 - RCONV + r_conv, r_conv, 2.0, 1.0, 0.1, False)
        row = RAD["steady_rows"][0]
        for q, k in (("H", "T_H_C"), ("S", "T_S_C"), ("surface", "T_O_C"), ("front", "q_front_W"), ("rear", "q_rear_W")):
            self.assertAlmostEqual(an[q], row[k], delta=1e-9, msg=q)

    def test_sensor_only_targets(self):
        blocked = nv.analytic_steady(A_H1, B_H1, RCONV, None, 0.0, 0.1, True)
        self.assertAlmostEqual(blocked["surface"], 26.25, delta=1e-9)
        self.assertAlmostEqual(blocked["H"], 26.27176851851639, delta=1e-9)
        open_ = nv.analytic_steady(A_H1, B_H1, RCONV, 2.0, 0.0, 0.1, False)
        self.assertAlmostEqual(open_["H"], 25.170302910069037, delta=1e-9)
        self.assertAlmostEqual(open_["S"], 25.188839120327046, delta=1e-9)
        self.assertAlmostEqual(open_["surface"], 25.18560681206654, delta=1e-9)


class TestTolerances(unittest.TestCase):
    def test_t3_budget_richardson_and_fallback(self):
        dts, meshes = nv.fv_refinement(FV)
        tol, note = nv.t3_budget("H1", "F1", "surface", dts, meshes, 1e-3)
        expect = 1.5 * (2 * 0.012195967557730114 + (4 / 3) * (0.002531133543673292 + 6.620261302714425e-06)) + 1e-3
        self.assertAlmostEqual(tol, expect, places=12)
        self.assertIn("richardson", note)
        tol0, _ = nv.t3_budget("H1", "F0", "surface", dts, meshes, 1e-3)  # F0 borrows F1/F2 budget
        self.assertAlmostEqual(tol0, expect, places=12)
        tolx, notex = nv.t3_budget("H3", "F1", "H", dts, meshes, 1e-3)
        self.assertAlmostEqual(tolx, 1.5 * (2 * 0.05 + (4 / 3) * 0.1) + 1e-3, places=12)
        self.assertIn("fallback", notex)

    def test_oracle_allowance_floor(self):
        self.assertEqual(nv.oracle_allowance(ORACLE), 1e-3)

    def test_peak_surface_time_tol(self):
        tol1, _ = nv.peak_surface_time_tol(fv_run("H1"))
        tol3, note3 = nv.peak_surface_time_tol(fv_run("H3"))
        self.assertEqual(tol1, 1.5)
        self.assertAlmostEqual(tol3, 4e-6 / (0.27 / (1030.0 * 1500.0)), delta=1e-9)
        self.assertIn("L_outer^2/alpha", note3)


class TestComparisons(unittest.TestCase):
    def test_trace_matching_excludes_event_fluxes(self):
        L = nv.Ledger()
        n = nv.compare_traces(L, "T3", "c", "a|b", "H1", "F1", nv.fv_trace(fv_run()), nv.oracle_trace(ORACLE["cases"][0]), lambda v: (0.05, ""))
        quantities_at_600 = {r["quantity"] for r in L.records if r["t_s"] == 600.0}
        self.assertEqual(quantities_at_600, {"surface", "sensor", "H"})
        self.assertEqual(n, 5 + 5 + 3)
        self.assertTrue(all(r["passed"] for r in L.records))

    def test_fail_detected_and_summarised(self):
        L = nv.Ledger()
        L.add("T4", "x", "a|b", "H1", "F1", "peak_H_C", None, 50.0, 53.0, 2.0)
        L.add("T4", "x", "a|b", "H1", "F1", "peak_H_C", None, 50.0, 50.5, 2.0)
        L.add("T3", "y", "a|b", "H1", "F1", "info", None, 1.0, 2.0, None)
        groups, tiers, failures = nv.summarize(L.records)
        self.assertEqual(len(failures), 1)
        self.assertEqual(tiers["T4"]["failed"], 1)
        self.assertEqual([g["result"] for g in groups], ["INFO", "FAIL"])
        self.assertEqual(groups[1]["max_abs_diff"], 3.0)

    def test_full_pipeline_on_fixture(self):
        res = nv.run_crosscheck(FV, ORACLE, RAD, STEADY)
        checks = {g["check"] for g in res["groups"]}
        for c in ("reference_vs_analytic", "rad_eps0_steady_vs_analytic", "fv_steady_match_vs_reference", "fv_long_time_target_vs_analytic",
                  "rad_eps0_reproduces_lump2", "fv_embedded_lump2_transcription", "fv_vs_oracle_trajectory", "fv_vs_oracle_energy_3600",
                  "lump2_table_vs_fv_peaks", "rad_eps0_vs_fv_peaks", "rad_eps0_vs_fv_trajectory"):
            self.assertIn(c, checks)
        self.assertEqual(res["failures"], [], msg=[(f["check"], f["quantity"], f["abs_diff"], f["tol"]) for f in res["failures"]])
        text = nv.render(res["groups"], res["tiers"], res["failures"], res["oracle_allowance_K"])
        self.assertIn("OVERALL (judged tiers): PASS", text)


if __name__ == "__main__":
    unittest.main()
