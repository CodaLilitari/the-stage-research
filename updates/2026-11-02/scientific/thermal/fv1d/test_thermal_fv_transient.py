"""Acceptance tests for thermal_fv_transient.py (T0-FV1D-1).  Written before execution by Red's Claude
contributor; nothing here has been run by the author.  Expected values are independent of the functions
under test: hand-derived structure, exact-rational series elimination (Fraction), and Coda's executed
references transcribed from the source bundle.  Passing proves model numerics only, never physical accuracy."""
import json
import math
import os
import tempfile
import unittest
from fractions import Fraction as F

import thermal_fv_transient as m

CODA_5W = {"H1": (33.83119986113005, 33.70398462379287, 33.55500086793716, 0.6844000694349729, 4.415599930565027),
           "H2": (33.86190245732054, 33.6326495680521, 33.36310964174662, 0.6690487713397297, 4.430951228660271),
           "H3": (33.91905575238601, 33.501140687023764, 33.00590154758745, 0.6404721238069959, 4.459527876193004)}
CODA_BLOCKED = {"H1": (90.94862037037036, 89.86019444444445), "H2": (92.81899074074074, 90.80463888888889),
                "H3": (96.55973148148148, 92.69352777777777)}
CODA_1W_10W_H1 = {1: (26.90248230028146, 26.85948562324088), 10: (42.492096812190795, 41.92439492380752)}
CODA_A_B = {"H1": (0.21768518518518518, 12.717685185185186), "H2": (0.4028703703703704, 12.90287037037037),
            "H3": (0.7732407407407408, 13.273240740740741)}
CODA_CS = {"H1": 16.2239, "H2": 31.6739, "H3": 62.5739}
DT1 = m.Numerics(dt_s=1.0)


def spec(stack, case, pert=None):
    return {"run_id": f"t-{stack}-{case}", "stack": stack, "case": case, "perturbation": pert or {}}


class MeshAndNetwork(unittest.TestCase):
    def test_mesh_structure_production(self):
        mesh = m.build_mesh(m.STACKS["H1"], 2, 1)
        self.assertEqual(mesh.node_count, 6)
        self.assertEqual(mesh.layer_of_node, ("outer_silicone", "outer_silicone", "film", "inner_silicone", "inner_silicone", "H"))
        self.assertEqual(mesh.sensor_node, 2)
        self.assertEqual(mesh.h_node, 5)
        self.assertAlmostEqual(mesh.center_depth_m[2], 0.000525, delta=1e-15)
        self.assertAlmostEqual(mesh.interface_depths_m[0], 0.0005, delta=1e-15)
        self.assertAlmostEqual(mesh.interface_depths_m[1], 0.00055, delta=1e-15)
        with self.assertRaises(ValueError):
            m.build_mesh(m.STACKS["H1"], 2, 2)

    def test_capacities_match_contract_totals(self):
        for stack, cs in CODA_CS.items():
            for ns, nf in ((1, 1), (2, 1), (4, 3)):
                asm = m.build_assembly(stack, n_silicone=ns, n_film=nf)
                caps = asm.capacities()
                self.assertAlmostEqual(math.fsum(caps[:-1]), cs, delta=1e-10)
                self.assertEqual(caps[-1], 20.0)

    def test_series_resistances_are_mesh_invariant(self):
        for stack, (a, b) in CODA_A_B.items():
            for ns, nf in ((1, 1), (2, 1), (4, 3), (3, 5)):
                asm = m.build_assembly(stack, n_silicone=ns, n_film=nf)
                self.assertAlmostEqual(m.series_resistance_midplane_to_H(asm), a, delta=1e-12)
                self.assertAlmostEqual(m.series_resistance_ambient_to_midplane(asm), b, delta=1e-12)

    def test_contact_only_at_physical_interfaces(self):
        asm = m.build_assembly("H2", n_silicone=4, n_film=3)
        comps = asm.face_components()
        contacts = [i for i, (_, c, _) in enumerate(comps) if c > 0.0]
        self.assertEqual(contacts, [asm.mesh.outer_film_face, asm.mesh.film_inner_face])
        self.assertAlmostEqual(comps[contacts[0]][1], 2.0e-4 / 0.01, delta=1e-15)
        self.assertEqual(comps[-1][2], 0.0)  # H side has no half-cell and no attachment contact

    def test_surface_reconstruction_identity(self):
        op = m.build_assembly("H3").operator()
        temps = [31.0, 30.5, 30.2, 29.9, 29.1, 33.0]
        q = m.front_flux(op, temps)
        self.assertAlmostEqual(m.surface_temperature(op, temps), 25.0 + q * 12.5, delta=1e-12)
        blocked = m.build_assembly("H3", boundary=m.Boundary(h=0.0)).operator()
        self.assertEqual(m.front_flux(blocked, temps), 0.0)
        self.assertEqual(m.surface_temperature(blocked, temps), temps[0])

    def test_passive_exchange_sum_cancels_internal_faces(self):
        op = m.build_assembly("H1", n_silicone=3, n_film=3).operator()
        temps = [25.0 + 0.7 * i * (i - 3) for i in range(op.node_count)]
        self.assertAlmostEqual(m.passive_exchange_sum(op, temps), -(m.front_flux(op, temps) + m.rear_flux(op, temps)), delta=1e-12)


class SteadyAndAnalytic(unittest.TestCase):
    def test_steady_matches_fraction_and_coda(self):
        for stack, want in CODA_5W.items():
            for ns, nf in ((1, 1), (2, 1), (4, 3)):
                asm = m.build_assembly(stack, n_silicone=ns, n_film=nf)
                op = asm.operator()
                fv = m.steady_network(op, m.source_vector(op, 5.0, 0.1))
                frac = m.reference_two_node_steady(asm.stack, asm.materials, asm.boundary, 5.0, 0.1)
                for key, w in zip(("H_C", "sensor_C", "surface_C", "front_W", "rear_W"), want):
                    self.assertAlmostEqual(fv[key], w, delta=1e-9)
                    self.assertAlmostEqual(frac[key], w, delta=1e-12)
                self.assertAlmostEqual(fv["balance_W"], 0.0, delta=1e-12)

    def test_steady_rear_blocked_and_other_powers(self):
        for stack, (h, s) in CODA_BLOCKED.items():
            op = m.build_assembly(stack, boundary=m.Boundary(r_rej=math.inf)).operator()
            fv = m.steady_network(op, m.source_vector(op, 5.0, 0.1))
            self.assertAlmostEqual(fv["H_C"], h, delta=1e-9)
            self.assertAlmostEqual(fv["sensor_C"], s, delta=1e-9)
            self.assertAlmostEqual(fv["surface_C"], 88.75, delta=1e-9)
            self.assertEqual(fv["rear_W"], 0.0)
        op = m.build_assembly("H1").operator()
        for power, (h, surf) in CODA_1W_10W_H1.items():
            fv = m.steady_network(op, m.source_vector(op, float(power), 0.1))
            self.assertAlmostEqual(fv["H_C"], h, delta=1e-9)
            self.assertAlmostEqual(fv["surface_C"], surf, delta=1e-9)

    def test_no_steady_state_when_isolated(self):
        op = m.build_assembly("H1", boundary=m.Boundary(h=0.0, r_rej=math.inf)).operator()
        self.assertEqual(m.steady_network(op, m.source_vector(op, 0.0, 0.1))["status"], "no_finite_steady_state")
        self.assertEqual(m.steady_network(op, [0.0] * op.node_count)["status"], "nonunique_isolated_zero_net_source")

    def test_uniform_hold(self):
        r = m.check_uniform_hold()
        self.assertLessEqual(r["observed_max_deviation_K"], 1e-11)

    def test_insulated_inventory(self):
        r = m.check_insulated_inventory()
        self.assertLessEqual(r["error_J"], 1e-9)
        self.assertEqual(r["exports_J"], [0.0, 0.0])

    def test_one_node_exponential_matches_coda(self):
        r = m.check_one_node_exponential()
        self.assertLessEqual(r["max_abs_difference_to_coda_errors_K"], 1e-9)
        self.assertLessEqual(r["exact_difference_to_coda_K"], 1e-12)
        for ratio in r["ratios"]:
            self.assertTrue(1.8 < ratio < 2.1, ratio)

    def test_two_node_insulated_modes(self):
        r = m.check_two_node_insulated_modes()
        self.assertTrue(r["passed"], r)

    def test_long_time_approach_and_fixed_point(self):
        r = m.check_long_time_approach(("H1", "H3"))
        self.assertLessEqual(r["observed_approach_K"], 1e-9)
        self.assertLessEqual(r["observed_hold_K"], 1e-10)

    def test_maximum_principle(self):
        r = m.check_maximum_principle()
        self.assertLessEqual(r["max_extremum_violation_K"], 1e-10)
        self.assertLess(r["stored_change_J"], 0.0)


class Scenarios(unittest.TestCase):
    def test_grid_and_input_guards(self):
        asm = m.build_assembly("H1")
        with self.assertRaises(ValueError):
            m.run_scenario(asm, m.scenario_for_case("F1"), m.Numerics(dt_s=0.3))
        with self.assertRaises(ValueError):
            m.run_scenario(asm, m.scenario_for_case("F0"), m.Numerics(dt_s=2.0, sample_period_s=1.0))
        with self.assertRaises(ValueError):
            m.run_scenario(asm, m.scenario_for_case("F0"), m.Numerics(dt_s=1e-4, horizon_s=3600.0))
        with self.assertRaises(ValueError):
            m.Scenario(case="X", body_power_W=11.0)
        with self.assertRaises(ValueError):
            m.Scenario(case="X", sensor_power_W=0.3)
        with self.assertRaises(ValueError):
            m.scenario_for_case("F9")
        for bad in ({"h": -1.0}, {"r_rej": 0.0}, {"r_rej": math.nan}, {"c_h": 0.0}, {"r_c_inner": -1.0}):
            with self.assertRaises(ValueError):
                m.Boundary(**bad)
        with self.assertRaises(ValueError):
            m.Materials(cp_silicone=0.0)
        with self.assertRaises(ValueError):
            m.apply_perturbation(m.Materials(), m.Boundary(), {"bogus": 1.0})

    def test_perturbations_share_origin(self):
        mat, bnd = m.apply_perturbation(m.Materials(), m.Boundary(), {"r_c": 2e-3, "cp_silicone": 1000.0})
        self.assertEqual((bnd.r_c_outer, bnd.r_c_inner), (2e-3, 2e-3))
        caps = m.build_assembly("H1", mat, bnd).capacities()
        nominal = m.build_assembly("H1").capacities()
        for i, layer in enumerate(m.build_mesh(m.STACKS["H1"]).layer_of_node):
            if layer.endswith("silicone"):
                self.assertAlmostEqual(caps[i], nominal[i] * 1000.0 / 1500.0, delta=1e-12)
            else:
                self.assertEqual(caps[i], nominal[i])

    def test_run_list_is_51_unique(self):
        runs = m.deterministic_run_list()
        self.assertEqual(len(runs), 51)
        self.assertEqual(len({r["run_id"] for r in runs}), 51)
        self.assertEqual(sum(1 for r in runs if r["case"] == "F4F"), 3)

    def test_f1_energy_audit_events_and_reservoir_zero_after_fault(self):
        res = m.run_from_spec(spec("H1", "F1"), DT1)
        s = res.summary
        self.assertTrue(s["energy"]["within_predeclared_tolerance"], s["energy"])
        self.assertLessEqual(abs(s["energy"]["reconstructed_residual_J"]), 1e-8)
        self.assertLessEqual(s["energy"]["max_instantaneous_power_residual_W"], 1e-8)
        self.assertAlmostEqual(s["energy"]["injected_J"], 900 * 5.0 + 3600 * 0.1, delta=1e-6)
        self.assertEqual([e["kind"] for e in s["events"]], ["fault", "scheduled_body_shutdown"])
        self.assertEqual(s["events"][0]["time_s"], 600.0)
        self.assertEqual(s["events"][0]["state_before_C"], s["events"][0]["state_after_C"])
        self.assertEqual(s["events"][0]["fluxes_after"]["rear_W"], 0.0)
        self.assertGreater(s["events"][0]["fluxes_before"]["rear_W"], 0.0)
        for row in res.rows[601:]:
            self.assertEqual(row.rear_flux_W, 0.0)
        self.assertEqual(s["body_power_end_s"], 900.0)
        self.assertEqual(s["long_time_target_if_final_conditions_held"]["status"], "unique")
        self.assertEqual(s["comparators_study_comparator_only"]["surface_actual_40C"]["label"], "study_comparator_only")

    def test_f0_f1_identical_until_fault_and_f0_cooler(self):
        f0 = m.run_from_spec(spec("H1", "F0"), DT1)
        f1 = m.run_from_spec(spec("H1", "F1"), DT1)
        self.assertEqual(f0.rows[:601], f1.rows[:601])
        self.assertGreater(f1.summary["peaks"]["H"]["value_C"], f0.summary["peaks"]["H"]["value_C"])
        self.assertEqual(f0.summary["comparators_study_comparator_only"]["H_60C"]["status"], "not_crossed_in_horizon")

    def test_f1_f3_physical_identity_only_observation_differs(self):
        r = m.check_f1_f3_identity(DT1, "H1")
        self.assertLessEqual(r["max_physical_trace_difference"], 1e-12)
        self.assertEqual(r["reported_difference_before_600s_K"], 0.0)
        self.assertGreater(r["max_reported_difference_from_600s_K"], 0.0)
        f3 = m.run_from_spec(spec("H1", "F3"), DT1).summary
        self.assertEqual(f3["sensor_observability"]["mode"], "frozen_from_sample")
        frozen = f3["sensor_observability"]["frozen_reported_C"]
        for sample in f3["samples_60s"]:
            if sample["time_s"] >= 600.0:
                self.assertEqual(sample["sensor_reported_C"], frozen)

    def test_f2_changes_only_inner_interface(self):
        f2 = m.run_from_spec(spec("H2", "F2"), DT1)
        ev = [e for e in f2.summary["events"] if e["kind"] == "fault"][0]
        self.assertEqual(ev["operator_change"]["changed_face_indices"], [f2.assembly.mesh.film_inner_face])
        before, after = ev["operator_change"]["changed_face_conductances_W_per_K"][0]
        half_film = 0.5 * 5e-5 / (0.20 * 0.01)
        half_sil = 0.5 * 0.0005 / (0.27 * 0.01)
        self.assertAlmostEqual(after, 1.0 / (half_film + 2e-2 / 0.01 + half_sil), delta=1e-12)
        self.assertAlmostEqual(before, 1.0 / (half_film + 2e-4 / 0.01 + half_sil), delta=1e-12)
        self.assertFalse(ev["operator_change"]["capacities_changed"])
        self.assertEqual(ev["operator_change"]["rear_conductance_W_per_K"], [0.5, 0.5])

    def test_f4_truthful_trips_frozen_does_not(self):
        t = m.run_from_spec(spec("H1", "F4T"), DT1)
        f = m.run_from_spec(spec("H1", "F4F"), DT1)
        f1 = m.run_from_spec(spec("H1", "F1"), DT1)
        self.assertTrue(t.summary["controller"]["tripped"])
        self.assertTrue(600.0 < t.summary["controller"]["trip_time_s"] < 900.0)
        self.assertEqual(t.summary["body_power_end_kind"], "controller_latch")
        trip = t.summary["controller"]["trip_time_s"]
        self.assertGreaterEqual(t.samples[int(trip)]["sensor_reported_C"], 45.0)
        self.assertLess(t.samples[int(trip) - 1]["sensor_reported_C"], 45.0)
        self.assertFalse(f.summary["controller"]["tripped"])
        self.assertEqual(f.rows, f1.rows)  # frozen-sensor controller case is physically identical to F1
        self.assertLess(t.summary["peaks"]["H"]["value_C"], f1.summary["peaks"]["H"]["value_C"])

    def test_f5_accumulates_energy_without_steady_state(self):
        res = m.run_from_spec(spec("H1", "F5"), DT1)
        s = res.summary
        for row in res.rows[601:]:
            self.assertEqual((row.front_flux_W, row.rear_flux_W), (0.0, 0.0))
        self.assertEqual(s["long_time_target_if_final_conditions_held"]["status"], "no_finite_steady_state")
        caps = res.segments[0][1].capacities
        e600 = math.fsum(c * t for c, t in zip(caps, res.rows[600].temperatures_C))
        e3600 = math.fsum(c * t for c, t in zip(caps, res.rows[3600].temperatures_C))
        self.assertAlmostEqual(e3600 - e600, 300 * 5.0 + 3000 * 0.1, delta=1e-7)
        self.assertGreater(res.rows[3600].temperatures_C[-1], res.rows[900].temperatures_C[-1])
        self.assertTrue(s["energy"]["within_predeclared_tolerance"])

    def test_time_refinement_machinery_full_horizon_h1_f1(self):
        r = m.check_time_refinement(("H1",), 3600.0, cases=("F1",))
        pairs = r["details"][0]["pairs_K"]
        self.assertIn("1_vs_0.5", pairs)
        self.assertIn("0.5_vs_0.25", pairs)
        for key in ("surface_actual_C", "sensor_actual_C", "H_C"):
            self.assertLess(pairs["0.5_vs_0.25"][key], 0.05, (key, pairs))
            self.assertLess(pairs["0.5_vs_0.25"][key], pairs["1_vs_0.5"][key] + 1e-12, (key, pairs))

    def test_mesh_refinement_invariants_h1_f1(self):
        r = m.check_mesh_refinement(("H1",), DT1, cases=("F1",))
        for d in r["details"]:
            self.assertTrue(d["injected_identical"])
            self.assertTrue(d["interface_depths_identical"])
            self.assertLessEqual(d["steady_target_deviation_K"], 1e-9)
            for v in d["max_difference_K"].values():
                self.assertLess(v, 0.10, d)

    def test_acceptance_evaluator_flags_failures(self):
        fake = {"a": {"passed": True}, "b": {"passed": False}}
        out = m.evaluate_acceptance(fake, [], None)
        self.assertFalse(out["all_predeclared_checks_passed"])
        self.assertEqual(out["failed_checks"], ["b"])

    def test_write_results_only_to_caller_path(self):
        payload = m.run_suite(DT1, stacks=("H1",), run_ids=["H1-F0-nominal"], include_verification=False)
        self.assertEqual(payload["run_count"], 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.json")
            m.write_results(payload, path)
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            self.assertEqual(loaded["runs"][0]["run_id"], "H1-F0-nominal")
            self.assertEqual(loaded["runs"][0]["contract_version"], "T0-HYP-1")
            with self.assertRaises(FileExistsError):
                m.write_results(payload, path)
            self.assertEqual(sorted(os.listdir(tmp)), ["out.json"])


if __name__ == "__main__":
    unittest.main()
