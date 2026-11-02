"""Unit tests: plant fidelity to Coda's executed numbers, state machine, detectors,
counterexamples where any controller using only the reported sensor must fail.
fix-003: T1/T2 expectation fixes, bounds derived from the configuration in force, new tests for
time constants / derived schedules / liveness evidence, and a regression test pinning H1/H2 to
Red's executed wave-10 receipts (their derived schedule equals the base schedule)."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plant import nominal, build, step, surface, steady_state, blocked, Params  # noqa: E402
from supervisor import (Supervisor, SupervisorConfig, RUN, TRIP_LIMIT, TRIP_SENSOR,  # noqa: E402
                        TRIP_MODEL, TRIPPED, derive_config)
from harness import (scenario_matrix, run_scenario, run_scenario_detailed, Scenario, SensorSpec,  # noqa: E402
                     ActuatorSpec, in_design_box, HOT_CORNER, COLD_CORNER, NOMINAL_PROPERTIES)
import detectability  # noqa: E402
from dataclasses import replace  # noqa: E402

MATRIX = {s.name: s for s in scenario_matrix()}
CODA_TABLE = {  # Coda's executed REPORT.md values (dt = 1 s, 1 s sample peaks)
    "H1": dict(intact=(33.831193, 900, 33.554994, 900, 25.170303), loss=(61.143480, 900, 59.747155, 901, 26.374204)),
    "H2": dict(intact=(33.861287, 900, 33.362444, 900, 25.168602), loss=(55.545063, 900, 53.153638, 904, 26.798252)),
    "H3": dict(intact=(33.884652, 900, 32.963939, 900, 25.165436), loss=(50.169875, 900, 45.881263, 914, 28.187988)),
}
# Red's executed wave-10 receipts for H1/H2 supervisor runs (base schedule; must reproduce).
RECEIPTS_H1_H2 = {
    "H1_sup1_rearloss600_noise": (TRIP_MODEL, 611), "H2_sup1_rearloss600_noise": (TRIP_MODEL, 614),
    "H1_sup1_rearloss100_noise": (TRIP_MODEL, 111), "H2_sup1_rearloss100_noise": (TRIP_MODEL, 115),
    "H1_sup1_freeze600_rearloss600_noise": (TRIP_SENSOR, 720), "H2_sup1_freeze600_rearloss600_noise": (TRIP_SENSOR, 720),
    "H1_sup1_biasstep600_rearloss600_noise": (TRIP_MODEL, 602), "H2_sup1_biasstep600_rearloss600_noise": (TRIP_MODEL, 602),
    "H1_sup1_dropout600_noise": (TRIP_SENSOR, 602), "H2_sup1_dropout600_noise": (TRIP_SENSOR, 602),
    "H1_sup2_freeze600_rearloss600_noise": (TRIP_SENSOR, 613), "H2_sup2_freeze600_rearloss600_noise": (TRIP_SENSOR, 620),
    "H1_sup1_idle_rearloss1500_redemand2400_noise": (TRIP_MODEL, 1838),
    "H2_sup1_idle_rearloss1500_redemand2400_noise": (TRIP_MODEL, 2050),
    "H1_sup1_freeze600_rearloss600_period240_noise": (TRIP_MODEL, 795),
    "H1_sup1_noprobe_freeze600_rearloss600_ideal": (TRIP_MODEL, 911),
    "H1_sup1_outofbox_rrej10_intact_noise": (TRIP_MODEL, 67),
    "H1_sup1_actdelay5_intact_noise": (TRIP_MODEL, 71), "H2_sup1_actdelay5_intact_noise": (RUN, None),
    "H1_sup1_intact_noise": (RUN, None), "H2_sup1_intact_noise": (RUN, None),
}
_CACHE = {}


def run(name):
    if name not in _CACHE:
        _CACHE[name] = run_scenario(MATRIX[name])
    return _CACHE[name]


def f1_peak(stack):
    return run(stack + "_ol_rearloss600")["peak_H"]


def freeze_bound(result, fault_time=600):
    """G3 worst case: probe_period + probe_duration + 5 s after the fault (config in force)."""
    c = result["supervisor_config"]
    return fault_time + c["probe_period"] + c["probe_duration"] + 5


class PlantFidelity(unittest.TestCase):
    def test_capacities_and_steady_state_match_coda(self):
        for stack, cs, H, S in (("H1", 16.2239, 33.8311998611, 33.7039846238),
                                ("H2", 31.6739, 33.8619024573, 33.6326495681),
                                ("H3", 62.5739, 33.9190557524, 33.5011406870)):
            p = nominal(stack)
            self.assertAlmostEqual(p.cs, cs, delta=1e-10)
            h, s = steady_state(p, 5.0, 0.1)
            self.assertAlmostEqual(h, H, delta=1e-8)
            self.assertAlmostEqual(s, S, delta=1e-8)
        for stack, Hb in (("H1", 90.9486203704), ("H2", 92.8189907407), ("H3", 96.5597314815)):
            h, s = steady_state(blocked(nominal(stack)), 5.0, 0.1)
            self.assertAlmostEqual(h, Hb, delta=1e-8)
            self.assertAlmostEqual(surface(nominal(stack), s), 88.75, delta=1e-8)

    def test_open_loop_reproduces_coda_executed_table(self):
        for stack, rows in CODA_TABLE.items():
            for case, name in (("intact", "_ol_intact"), ("loss", "_ol_rearloss600")):
                r = run(stack + name)
                pH, tH, pSu, tSu, fH = rows[case]
                with self.subTest(stack=stack, case=case):
                    self.assertAlmostEqual(r["peak_H"], pH, delta=2e-5)
                    self.assertEqual(r["peak_H_time"], tH)
                    self.assertAlmostEqual(r["peak_surface"], pSu, delta=2e-5)
                    self.assertEqual(r["peak_surface_time"], tSu)
                    self.assertAlmostEqual(r["final_H"], fH, delta=2e-5)
                    self.assertAlmostEqual(r["energy_applied_J"], 4500.0, delta=1e-9)

    def test_crosscheck_rc_transient_when_available(self):
        here = Path(__file__).resolve().parent
        candidates = [os.environ.get("RC_TRANSIENT_PATH"), str(here / "rc_transient.py"),
                      str(here.parent / "validation" / "thermal_transient" / "rc_transient.py")]
        path = next((c for c in candidates if c and Path(c).exists()), None)
        if path is None:
            self.skipTest("rc_transient.py not available; set RC_TRANSIENT_PATH to enable")
        spec = importlib.util.spec_from_file_location("rc_transient", path)
        rc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rc)
        for stack in ("H1", "H2", "H3"):
            cp = rc.nominal(stack)
            p = nominal(stack)
            ref = rc.simulate(cp, (25.0, 25.0), [dict(duration=600.0, p=5.0, j=0.1),
                                                 dict(duration=300.0, p=5.0, j=0.1, gr=0.0),
                                                 dict(duration=2700.0, p=0.0, j=0.1, gr=0.0)], 1.0)["trace"]
            H = S = 25.0
            for k in range(3600):
                q = blocked(p) if k >= 600 else p
                H, S = step(q, H, S, 5.0 if k < 900 else 0.0, 0.1, 1.0)
                self.assertAlmostEqual(H, ref[k + 1]["H"], delta=1e-9)
                self.assertAlmostEqual(S, ref[k + 1]["S"], delta=1e-9)

    def test_rear_loss_unobservable_without_rear_flux(self):
        # T1 fix: the identity holds mathematically; the two Euler coefficient sets round
        # differently at 1e-14, so compare within 1e-9 instead of exact float equality.
        p = nominal("H1")
        Hi = Si = Hb = Sb = 25.0
        for _ in range(600):
            Hi, Si = step(p, Hi, Si, 0.0, 0.0, 1.0)
            Hb, Sb = step(blocked(p), Hb, Sb, 0.0, 0.0, 1.0)
        for v in (Hi, Si, Hb, Sb):
            self.assertAlmostEqual(v, 25.0, delta=1e-9)
        self.assertAlmostEqual(Si, Sb, delta=1e-9)
        self.assertAlmostEqual(Hi, Hb, delta=1e-9)

    def test_rear_loss_signature_positive_and_growing_under_load(self):
        for stack in ("H1", "H2", "H3"):
            p = nominal(stack)
            H, S = steady_state(p, 5.0, 0.1)
            sig = detectability.rear_loss_signature(p, H, S, 5.0, 0.1, 120)
            values = [d for _, d in sig]
            self.assertTrue(all(b >= a for a, b in zip(values, values[1:])))
            self.assertGreater(values[60], 1.0)
            self.assertGreater(p.gr * (H - p.reservoir), 4.0)

    def test_design_box_membership(self):
        self.assertTrue(in_design_box(NOMINAL_PROPERTIES))
        self.assertTrue(in_design_box(HOT_CORNER) and in_design_box(COLD_CORNER))
        self.assertFalse(in_design_box({**NOMINAL_PROPERTIES, "r_rej": 10.0}))

    def test_time_constants_hand_values(self):
        # hand-derived from the 2x2 eigenproblem (README B.1); tolerance covers rounding
        for stack, tau_slow, tau_fast, tau_blocked in (("H1", 63.4, 1.9, 463.0),
                                                       ("H2", 94.4, 4.6, 670.0),
                                                       ("H3", 169.1, 9.5, 1100.0)):
            p = nominal(stack)
            ts, tf = detectability.time_constants(p)
            with self.subTest(stack=stack):
                self.assertAlmostEqual(ts, tau_slow, delta=1.5)
                self.assertAlmostEqual(tf, tau_fast, delta=0.3)
                self.assertAlmostEqual(detectability.time_constants(blocked(p))[0], tau_blocked,
                                       delta=0.03 * tau_blocked)
        self.assertEqual(detectability.time_constants(replace(nominal("H1"), gr=0.0, ga=0.0))[0],
                         float("inf"))


class Derivation(unittest.TestCase):
    def test_periodic_signature_orders_stacks_and_h3_base_schedule_is_small(self):
        sig = {s: detectability.periodic_probe_signature(nominal(s), 5.0, 0.1, 3.0, 60, 150, 5)
               for s in ("H1", "H2", "H3")}
        self.assertLess(sig["H1"], sig["H2"])          # all negative: H1 largest magnitude
        self.assertLess(sig["H2"], sig["H3"])
        self.assertGreaterEqual(abs(sig["H1"]), 1.0)
        self.assertGreaterEqual(abs(sig["H2"]), 1.0)
        self.assertGreater(abs(sig["H3"]), 0.6)       # above the floor ...
        self.assertLess(abs(sig["H3"]), 1.0)          # ... but below the margin target (D2)
        # executed wave-10 probe statistics in the periodic regime (H1/H2 freeze runs, t = 720)
        self.assertAlmostEqual(sig["H1"], -2.425, delta=0.03)
        self.assertAlmostEqual(sig["H2"], -1.576, delta=0.03)

    def test_derived_configs(self):
        base = SupervisorConfig()
        for s in ("H1", "H2"):
            cfg, info = derive_config(nominal(s), base)
            with self.subTest(stack=s):
                self.assertEqual((cfg.probe_duration, cfg.probe_period, cfg.watchdog_powered_s), (60, 150, 360))
                self.assertTrue(info["derivation_ok"])
                self.assertEqual(cfg, base)
        cfg3, info3 = derive_config(nominal("H3"), base)
        self.assertEqual(cfg3.probe_duration, 90)
        self.assertIn(cfg3.probe_period, (180, 210, 240))
        self.assertEqual(cfg3.watchdog_powered_s, 2 * cfg3.probe_period + cfg3.probe_duration)
        self.assertGreaterEqual(abs(info3["periodic_signature_K"]), info3["signature_target_K"])
        self.assertTrue(info3["derivation_ok"])
        self.assertGreater(info3["tau_slow_s"], 150.0)
        # overrides win and are not derived
        cfg_o, _ = derive_config(nominal("H1"), base, dict(probe_period=240))
        self.assertEqual((cfg_o.probe_period, cfg_o.watchdog_powered_s), (240, 540))
        cfg_o2, _ = derive_config(nominal("H1"), base, dict(probe_period=240, watchdog_powered_s=360))
        self.assertEqual(cfg_o2.watchdog_powered_s, 360)
        cfg_o3, _ = derive_config(nominal("H3"), base, dict(probe_enabled=False, watchdog_enabled=False))
        self.assertFalse(cfg_o3.probe_enabled)


class StateMachine(unittest.TestCase):
    def test_latches_and_never_restarts(self):
        sup = Supervisor(nominal("H1"))
        self.assertEqual(sup.update(0, 25.0, None, 5.0), 5.0)
        self.assertEqual(sup.state, RUN)
        self.assertEqual(sup.update(1, 80.0, None, 5.0), 0.0)
        self.assertEqual(sup.state, TRIP_LIMIT)
        for t in range(2, 50):
            self.assertEqual(sup.update(t, 25.0, None, 5.0), 0.0)
            self.assertEqual(sup.state, TRIP_LIMIT)
        self.assertEqual(sup.trip_time, 1)

    def test_dropout_implausible_and_second_sensor_limit(self):
        sup = Supervisor(nominal("H1"))
        sup.update(0, 25.0, None, 5.0)
        for t in (1, 2):
            sup.update(t, None, None, 5.0)
            self.assertEqual(sup.state, RUN)
        sup.update(3, None, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        sup = Supervisor(nominal("H1"))
        sup.update(0, 25.0, None, 5.0)
        sup.update(1, -50.0, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        sup = Supervisor(nominal("H1"), SupervisorConfig(dual_sensor=True))
        sup.update(0, 25.0, 25.0, 5.0)
        sup.update(1, 25.0, 50.0, 5.0)
        self.assertEqual(sup.state, TRIP_LIMIT)
        sup = Supervisor(nominal("H1"))
        for t in range(3):
            sup.update(t, None, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)

    def test_disagreement_guard(self):
        sup = Supervisor(nominal("H1"), SupervisorConfig(dual_sensor=True))
        sup.update(0, 25.0, 25.0, 5.0)
        for t in (1, 2):
            sup.update(t, 25.0, 27.0, 5.0)
            self.assertEqual(sup.state, RUN)
        sup.update(3, 25.0, 27.0, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        self.assertIn("disagreement", sup.trip_cause)

    def test_liveness_watchdog(self):
        cfg = SupervisorConfig(probe_enabled=False, watchdog_enabled=True, watchdog_powered_s=20)
        sup = Supervisor(nominal("H1"), cfg)
        y = 25.0
        for t in range(40):
            sup.update(t, y, None, 5.0)
            if sup.state != RUN:
                break
            y = sup.Shat  # perfect agreement with the model; window too short for movement evidence
        self.assertEqual(sup.state, TRIP_SENSOR)
        self.assertEqual(sup.trip_time, 21)
        self.assertIn("watchdog", sup.trip_cause)

    def test_transient_is_liveness_evidence_but_stuck_channel_is_not(self):
        # R4: a healthy channel tracking the heating transient refreshes the watchdog without any
        # probe; a channel stuck at its initial value never does (it is tripped by the level test).
        cfg = SupervisorConfig(probe_enabled=False, watchdog_enabled=False)
        sup = Supervisor(nominal("H3"), cfg)
        y = 25.0
        for t in range(251):
            sup.update(t, y, None, 5.0)
            y = sup.Shat
        self.assertEqual(sup.state, RUN)
        self.assertGreater(sup.live_windows, 50)
        self.assertLessEqual(sup.powered_since_evidence, 5)
        sup = Supervisor(nominal("H3"), cfg)
        for t in range(251):
            sup.update(t, 25.0, None, 5.0)
            if sup.state != RUN:
                break
        self.assertEqual(sup.state, TRIP_MODEL)
        self.assertEqual(sup.live_windows, 0)

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            SupervisorConfig(probe_period=30, probe_duration=60)
        with self.assertRaises(ValueError):
            SupervisorConfig(tau_rel_probe=1.0)
        with self.assertRaises(ValueError):
            SupervisorConfig(watchdog_powered_s=100)          # < probe_period + probe_duration
        SupervisorConfig(watchdog_powered_s=100, probe_enabled=False)   # allowed without probes


class ClosedLoop(unittest.TestCase):
    def test_intact_ideal_zero_residual_and_probe_cost(self):
        # T2 fix: informativeness is a property of the predicted net window change; the first
        # probe(s) during the heating transient may be uninformative. Assert what the design
        # guarantees: every scheduled probe is executed and evaluated, the energy cost follows
        # the derived schedule, probes ending in the quasi-steady regime are informative and
        # pass, the residual is zero, and the heating transient supplies liveness evidence.
        for stack in ("H1", "H2", "H3"):
            r, sup = run_scenario_detailed(MATRIX[stack + "_sup1_intact_ideal"])
            c = sup.cfg
            starts = [t for t in range(c.probe_first, 900, c.probe_period)]
            withheld = sum(c.probe_depth * max(0, min(s + c.probe_duration, 900) - s) for s in starts)
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], RUN)
                self.assertEqual(r["probes_ok"] + r["probes_uninformative"], len(starts))
                self.assertEqual([e[0] for e in r["probe_log"]], [s + c.probe_duration for s in starts])
                late = [e for e in r["probe_log"] if e[0] >= 500]
                self.assertTrue(late)
                self.assertTrue(all(e[3] == "ok" for e in late), r["probe_log"])
                self.assertGreaterEqual(r["probes_ok"], len(starts) - 2)
                self.assertAlmostEqual(r["energy_applied_J"], 4500.0 - withheld, delta=1e-6)
                self.assertGreater(r["live_windows"], 0)
                residual = max(abs(h[1] - h[3]) for h in sup.history if h[1] is not None and h[3] is not None)
                self.assertLess(residual, 1e-9)

    def test_no_false_alarm_inside_design_box(self):
        for stack in ("H1", "H2", "H3"):
            for short in ("sup1_intact_noise", "sup1_hotcorner_noise", "sup1_coldcorner_noise", "sup2_intact_noise"):
                r = run(stack + "_" + short)
                with self.subTest(run=r["name"]):
                    self.assertEqual(r["final_state"], RUN, r["trip_cause"])
                    self.assertFalse(r["false_alarm"])

    def test_f4_naive_counterexample(self):
        for stack in ("H1", "H2", "H3"):
            frozen = run(stack + "_naive45_frozen600_rearloss600")
            truthful = run(stack + "_naive45_truthful_rearloss600")
            with self.subTest(stack=stack):
                self.assertFalse(frozen["tripped"])
                self.assertAlmostEqual(frozen["peak_H"], f1_peak(stack), delta=1e-9)
                self.assertTrue(truthful["tripped"])
                self.assertLess(truthful["trip_time"], 900)
                self.assertLess(truthful["peak_H"], frozen["peak_H"])

    def test_single_sensor_without_excitation_must_fail(self):
        base = MATRIX["H1_sup1_noprobe_freeze600_rearloss600_ideal"]
        for stack, bound in (("H1", 0.01), ("H2", 0.1), ("H3", 0.3)):
            sc = replace(base, stack=stack, name=stack + "_noprobe_counterexample")
            r, sup = run_scenario_detailed(sc)
            with self.subTest(stack=stack):
                self.assertTrue(r["trip_time"] is None or r["trip_time"] >= 900)
                self.assertAlmostEqual(r["peak_H"], f1_peak(stack), delta=1e-6)
                gap = max(abs(h[1] - h[3]) for h in sup.history if 600 <= h[0] < 900)
                self.assertLess(gap, bound)          # reported history indistinguishable from healthy
                self.assertGreater(r["state_at_trip"]["true_S"] if r["state_at_trip"] else r["peak_S"], 45.0)

    def test_rear_loss_with_live_sensor_detected(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], TRIP_MODEL, r["trip_cause"])
                self.assertLessEqual(r["trip_time"], 660)
                self.assertLess(r["peak_H"], 45.0)
                self.assertLess(r["peak_H"], f1_peak(stack) - 5.0)
            r = run(stack + "_sup1_rearloss100_noise")
            with self.subTest(stack=stack, early=True):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], 250)
                self.assertLess(r["peak_H"], 45.0)

    def test_freeze_detected_with_bounded_latency_by_probe_scheme(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_freeze600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], freeze_bound(r))
                self.assertLess(r["peak_H"], f1_peak(stack) - 5.0)
                st = r["state_at_trip"]
                self.assertGreater(st["true_S"] - st["reported_y1"], 1.0)   # observability gap at trip
            r = run(stack + "_sup1_freeze600_only_noise")
            with self.subTest(stack=stack, hazard=False):
                self.assertEqual(r["final_state"], TRIP_SENSOR, r["trip_cause"])
                self.assertLessEqual(r["trip_time"], freeze_bound(r))
                self.assertLess(r["peak_H"], 36.0)

    def test_dual_sensor_detects_freeze_quickly(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup2_freeze600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], TRIP_SENSOR)
                self.assertLessEqual(r["trip_time"], 700)
                self.assertLess(r["peak_H"], 45.0)
                self.assertEqual(r["energy_withheld_J"] > 0, True)

    def test_bias_step_and_dropout(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_biasstep600_rearloss600_noise")
            with self.subTest(stack=stack, fault="bias"):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], 620)
            r = run(stack + "_sup1_dropout600_noise")
            with self.subTest(stack=stack, fault="dropout"):
                self.assertEqual(r["final_state"], TRIP_SENSOR)
                self.assertEqual(r["trip_time"], 602)

    def test_stuck_on_actuator_detected_but_not_protected(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_stuckon600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertGreaterEqual(r["trip_time"], 600)      # the trip must follow the fault
                self.assertGreater(r["final_H"], 60.0)   # study comparator only

    def test_idle_rear_loss_latent_then_detected_on_redemand(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_idle_rearloss1500_redemand2400_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertGreaterEqual(r["trip_time"], 1500)
                self.assertLessEqual(r["trip_time"], 2600)
                self.assertLess(r["peak_H"], 50.0)

    def test_modelled_actuator_delay_does_not_trip(self):
        # wave-10 receipt: H1 unmodelled 5 s delay tripped at 71. With the delay modelled, the
        # supervisor's p_hist aligns with the actuator's transport delay sample for sample.
        base = MATRIX["H1_sup1_actdelay5_intact_noise"]
        sc = replace(base, name="H1_actdelay5_modelled", supervisor=dict(actuator_delay_model=5))
        r = run_scenario(sc)
        self.assertEqual(r["final_state"], RUN, r["trip_cause"])
        sc0 = replace(base, name="H1_actdelay5_ideal_modelled", sensor1=SensorSpec(),
                      supervisor=dict(actuator_delay_model=5))
        r0, sup0 = run_scenario_detailed(sc0)
        residual = max(abs(h[1] - h[3]) for h in sup0.history if h[1] is not None and h[3] is not None)
        self.assertLess(residual, 1e-9)

    def test_h1_h2_reproduce_wave10_receipts(self):
        # The derived schedule for H1/H2 equals the base schedule and the only behavioural change
        # (evidence source of the watchdog) never fired for them: results must be unchanged.
        for name, (state, trip) in RECEIPTS_H1_H2.items():
            r = run(name)
            with self.subTest(run=name):
                self.assertEqual(r["final_state"], state, r["trip_cause"])
                self.assertEqual(r["trip_time"], trip)
        self.assertAlmostEqual(run("H1_sup1_freeze600_rearloss600_noise")["peak_H"], 40.497, delta=2e-3)
        self.assertAlmostEqual(run("H2_sup1_freeze600_rearloss600_noise")["peak_H"], 38.393, delta=2e-3)
        self.assertAlmostEqual(run("H1_sup1_intact_ideal")["energy_applied_J"], 3420.0, delta=1e-6)

    def test_h3_schedule_in_force_and_no_watchdog_trips_in_matrix(self):
        for name, sc in MATRIX.items():
            if sc.controller != "supervisor":
                continue
            r = run(name)
            with self.subTest(run=name):
                if r["trip_cause"]:
                    self.assertNotIn("watchdog", r["trip_cause"])
                if sc.stack == "H3" and sc.supervisor.get("probe_enabled", True):
                    self.assertEqual(r["supervisor_config"]["probe_duration"], 90)
                    self.assertGreater(r["supervisor_config"]["probe_period"], 150)

    def test_matrix_predeclared_and_deterministic(self):
        runs = scenario_matrix()
        self.assertLessEqual(len(runs), 60)
        self.assertEqual(len({s.name for s in runs}), len(runs))
        a = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        b = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        self.assertEqual(a, b)

    def test_detectability_summary(self):
        for stack in ("H1", "H2", "H3"):
            cfg, _ = derive_config(nominal(stack), SupervisorConfig())
            d = detectability.summary_for_stack(stack, cfg)
            self.assertTrue(d["probe_informative"] and d["frozen_channel_detected_by_probe"])
            self.assertIsNotNone(d["increment_detection_time_estimate_s"])
            self.assertLess(d["idle_rear_flux_W"], 0.1)
            self.assertGreater(d["idle_S_blocked"], d["idle_S_intact"])
            self.assertGreaterEqual(abs(d["periodic_probe_signature_K"]), 1.0)
            self.assertGreater(d["tau_slow_blocked_s"], d["tau_slow_s"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
