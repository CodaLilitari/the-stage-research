"""Unit and integration tests for the First Leaf public-packet oracle baseline (tasks firstleaf-oracle-001/-003).

Place next to the package's tests/; package-dependent tests skip when src/ or inputs/ are absent.
Set FL_PACKAGE_ROOT to run the relay-dependent tests against another package tree (e.g. the
integrated lifecycle relay); otherwise the tree containing this tests/ directory is used.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = Path(os.environ.get("FL_PACKAGE_ROOT", str(ROOT))).resolve()
sys.path.insert(0, str(ROOT / "oracle"))
sys.path.insert(0, str(PKG_ROOT / "src"))

import first_leaf_oracle as flo  # noqa: E402
import fl_harness as hz  # noqa: E402
import fl_local_sim as sim  # noqa: E402
import fl_scoring as sc  # noqa: E402

try:
    import first_leaf  # noqa: E402
    import relay  # noqa: E402
    CFG = first_leaf.load_protocol()
    PACKAGE = True
except Exception:  # package or its inputs not present
    PACKAGE = False
LIFECYCLE = PACKAGE and hasattr(relay, "ExportAfterCommitError")


def receipt_event(episode, tick, action, observed):
    return {"event": "action_receipt", "episode": episode, "source_dispatch_tick": tick,
            "receipt": {"execution_status": flo.EXECUTED, "executed_action": action,
                        "requested_action": action, "dispatch": True},
            "executed_transition_source_tick": tick, "observed_sensor": observed}


def sample(episode, tick, v, p=(0.0, 0.0)):
    return {"episode": episode, "sample_tick": tick, "p": list(p), "v": list(v)}


class EvidenceTests(unittest.TestCase):
    def test_duplicate_samples_and_receipts_are_single_evidence(self):
        log = flo.EvidenceLog()
        s0, s1 = sample(0, 0, [0.0, 0.0]), sample(0, 1, [0.3, 0.0])
        ev = receipt_event(0, 0, "k2", s0)
        log.ingest_packet({"sensor": s1, "recent_events": [ev, ev]})
        log.ingest_packet({"sensor": s1, "recent_events": [ev]})
        self.assertEqual(len(log.samples), 2)
        self.assertEqual(log.actions, {(0, 0): 2})
        # Five presentations (s1, s0, s0 | s1, s0) of two distinct keys: three duplicates, not four
        # (the first s0 is the first time key (0, 0) is seen).  Receipt ev is presented three times.
        self.assertEqual(log.duplicate_samples, 3)
        self.assertEqual(log.duplicate_receipts, 2)
        self.assertEqual(log.conflicting_receipts, 0)
        eqs = log.new_equations(0.75)
        self.assertEqual(len(eqs), 1)
        e, u, a, y = eqs[0]
        self.assertEqual((e, u, a), (0, 0, 2))
        self.assertAlmostEqual(y[0], 0.3)
        self.assertEqual(log.new_equations(0.75), [])  # no repeated learning credit

    def test_equation_pairs_source_tick_not_latest_receipt(self):
        log = flo.EvidenceLog()
        s0, s1, s2 = sample(0, 0, [0.0, 0.0]), sample(0, 1, [0.3, 0.0]), sample(0, 2, [0.225, 0.3])
        log.ingest_packet({"sensor": s2, "recent_events": [receipt_event(0, 0, "k0", s0),
                                                           receipt_event(0, 1, "k1", s1)]})
        eqs = log.new_equations(0.75)
        self.assertEqual([(e, u, a) for e, u, a, _ in eqs], [(0, 0, 0), (0, 1, 1)])
        self.assertAlmostEqual(eqs[0][3][0], 0.3)      # k0 -> +x
        self.assertAlmostEqual(eqs[1][3][0], 0.0)      # k1 -> +y (0.225 - 0.75*0.3 = 0)
        self.assertAlmostEqual(eqs[1][3][1], 0.3)

    def test_rejected_and_duplicate_receipts_commit_nothing(self):
        log = flo.EvidenceLog()
        dup = {"event": "action_receipt", "episode": 0, "receipt": {"execution_status": flo.EXECUTED,
               "executed_action": "k0", "duplicate": True}}
        rej = {"event": "rejected_invalid_request", "episode": 0, "reason": "x", "executed": False}
        log.ingest_packet({"sensor": sample(0, 0, [0, 0]), "recent_events": [dup, rej]})
        self.assertEqual(log.actions, {})
        self.assertEqual(log.ignored_events, 2)

    def test_lifecycle_receipt_with_consumed_dispatch_is_committed(self):
        """Integrated relay: the committed receipt of an executed step has dispatch False (authorization
        consumed at mark_dispatched) and events carry D2 fields; evidence keys on execution_status only."""
        log = flo.EvidenceLog()
        ev = receipt_event(0, 0, "k1", sample(0, 0, [0, 0]))
        ev["receipt"]["dispatch"] = False
        ev.update({"executed": True, "request_bytes_sha256": "00" * 32, "request_bytes_len": 200})
        failure = {"event": "action_receipt", "episode": 0, "executed": False,
                   "receipt": {"execution_status": "known_failure_example", "requested_action": "k2",
                               "dispatch": False}}
        migration = {"event": "operator_state_migration", "episode": 0, "operator_intervention": True}
        log.ingest_packet({"sensor": sample(0, 1, [0, 0.3]), "recent_events": [ev, failure, migration]})
        self.assertEqual(log.actions, {(0, 0): 1})
        self.assertEqual(log.ignored_events, 2)
        self.assertEqual([(e, u, a) for e, u, a, _ in log.new_equations(0.75)], [(0, 0, 1)])

    def test_episode_reset_samples_complete_previous_episode(self):
        log = flo.EvidenceLog()
        log.ingest_packet({"sensor": sample(0, 78, [0, 0]),
                           "recent_events": [receipt_event(0, 77, "k3", sample(0, 76, [0, 0])),
                                             receipt_event(0, 78, "k3", sample(0, 77, [0, 0])),
                                             receipt_event(0, 79, "k3", sample(0, 78, [0, 0]))]})
        self.assertEqual(len(log.new_equations(0.75)), 1)   # only (0,77) has both samples
        log.ingest_packet({"sensor": sample(1, 0, [0, 0]),
                           "recent_events": [{"event": "operator_episode_reset", "episode": 0,
                                              "final_sensor_samples": [sample(0, 78, [0, 0]),
                                                                       sample(0, 79, [0, -0.3]),
                                                                       sample(0, 80, [0, -0.525])]}]})
        eqs = log.new_equations(0.75)
        self.assertEqual([(e, u) for e, u, _, _ in eqs], [(0, 78), (0, 79)])
        self.assertAlmostEqual(eqs[1][3][1], -0.3)


class DetectionTests(unittest.TestCase):
    def bank(self, **over):
        params = dict(flo.DEFAULT_PARAMS)
        params.update(over)
        return flo.RegimeBank(params, 0.00046875, 0.0525)

    def test_noise_within_contract_is_absorbed(self):
        b = self.bank()
        for i in range(40):
            b.observe(0, [0.3 + 0.05 * (-1) ** i, 0.0], (0, i))
        self.assertEqual(len(b.regimes), 1)
        self.assertEqual(b.switches, [])
        self.assertAlmostEqual(b.regimes[0].actions[0].mean()[0], 0.3, places=3)

    def test_hard_shift_opens_regime_and_return_revisits(self):
        b = self.bank()
        for i in range(10):
            b.observe(0, [0.3, 0.0], (0, i))
        ev = b.observe(0, [0.0, 0.39], (3, 0))
        self.assertEqual((ev["kind"], ev["trigger"], b.active), ("new", "hard", 1))
        for i in range(1, 5):
            b.observe(0, [0.0, 0.39], (3, i))
        ev = b.observe(0, [0.3, 0.0], (5, 0))
        self.assertEqual((ev["kind"], b.active), ("revisit", 0))
        self.assertEqual(b.regimes[0].actions[0].n, 11)
        self.assertEqual(b.regimes[1].actions[0].n, 5)

    def test_soft_detector_catches_sub_contract_shift(self):
        b = self.bank()
        for i in range(20):
            b.observe(0, [0.3, 0.0], (0, i))
        for i in range(4):
            b.observe(0, [0.39, 0.0], (1, i))   # 0.09 shift: inside the 0.105 hard bound
        self.assertEqual(len(b.switches), 1)
        self.assertEqual(b.switches[0]["trigger"], "soft")

    def test_coast_audits_the_contract(self):
        b = self.bank()
        b.observe(4, [0.02, -0.05], (0, 0))
        self.assertEqual(b.contract_violations, 0)
        b.observe(4, [0.1, 0.0], (0, 1))
        self.assertEqual(b.contract_violations, 1)
        self.assertFalse(b.hard_enabled())

    def test_information_gain_prefers_unobserved_actuator(self):
        post = flo.ActionPosterior(0.00046875, 1.0, 4)
        g0 = post.info_gain()
        post.update([0.3, 0.0])
        self.assertGreater(g0, 7.0)
        self.assertLess(post.info_gain(), 1.0)


class AgentProtocolTests(unittest.TestCase):
    def test_one_valid_request_per_packet(self):
        s, agent, ids = sim.LocalRelay(7), flo.OracleAgent(), set()
        for _ in range(20):
            pk = s.packet()
            req = agent.act(pk)
            flo.validate_request(req, pk)
            self.assertNotIn(req["request_id"], ids)
            ids.add(req["request_id"])
            ev = s.step(flo.canonical(req))
            self.assertEqual(ev["receipt"]["execution_status"], flo.EXECUTED)
        self.assertEqual(s.tick, 20)

    def test_probe_order_then_control(self):
        s, agent, actions = sim.LocalRelay(11), flo.OracleAgent(), []
        for _ in range(6):
            req = agent.act(s.packet())
            actions.append(req["action"])
            s.step(flo.canonical(req))
        self.assertEqual(actions[:4], ["k0", "k1", "k2", "k3"])
        self.assertEqual(agent.last_decision["reason"], "control")

    def test_no_request_when_episode_complete_or_stopped(self):
        s, agent = sim.LocalRelay(3), flo.OracleAgent()
        pk = s.packet()
        self.assertIsNone(agent.act({**pk, "episode_complete": True}))
        self.assertIsNone(agent.act({**pk, "stopped": True}))
        self.assertIsNotNone(agent.act(pk))

    def test_random_and_constant_agents_follow_protocol(self):
        s = sim.LocalRelay(5)
        for agent in (flo.RandomAgent(1), flo.ConstantAgent("coast")):
            pk = s.packet()
            req = agent.act(pk)
            flo.validate_request(req, pk)
            self.assertEqual(s.step(flo.canonical(req))["receipt"]["execution_status"], flo.EXECUTED)

    def test_packet_only_memory_still_acts(self):
        s, agent = sim.LocalRelay(9), flo.OracleAgent({"memory": "packet_only"})
        for _ in range(30):
            req = agent.act(s.packet())
            self.assertEqual(s.step(flo.canonical(req))["receipt"]["execution_status"], flo.EXECUTED)


class HarnessGuardTests(unittest.TestCase):
    def test_harness_refuses_packet_with_in_flight_receipt(self):
        class Wrapped(hz.LocalDriver):
            def packet(self):
                pk = super().packet()
                pk["active_request"] = {"request_id": "x", "execution_status": "admitted_pending"}
                return pk
        with self.assertRaises(RuntimeError):
            hz.run_trial(Wrapped(1), flo.OracleAgent(), episodes=1, steps_per_episode=1)

    def test_verified_event_shape_is_checked(self):
        ev = receipt_event(0, 0, "k0", sample(0, 0, [0, 0]))
        self.assertIs(hz.check_verified_event(ev), ev["receipt"])
        broken = dict(ev, receipt={"execution_status": flo.EXECUTED})
        with self.assertRaises(RuntimeError):
            hz.check_verified_event(broken)

    def test_reserved_seeds_from_protocol_or_fallback(self):
        cfg = {"development_seeds": {"first": 500, "count": 3}, "evaluation_seeds": {"first": 900, "count": 1}}
        self.assertEqual(hz.reserved([499, 500, 502, 503, 900, 901], cfg), [500, 502, 900])
        self.assertEqual(hz.reserved([99, 100, 115, 116, 10000, 20001]), [100, 115, 10000])


class IdentificationTests(unittest.TestCase):
    def test_clean_stationary_identifies_body(self):
        driver = hz.LocalDriver(21, {"profile": {"noise": False, "change": False}})
        agent = flo.OracleAgent()
        result = hz.run_trial(driver, agent, episodes=1)
        true_b = driver.sim.true_b()
        for i in range(4):
            self.assertLess(abs(agent.vectors()[i][0] - true_b[i][0]), 1e-3)
            self.assertLess(abs(agent.vectors()[i][1] - true_b[i][1]), 1e-3)
        self.assertLess(result["records"][-1]["body_model_error"], 1e-3)
        self.assertEqual(agent.summary()["switches"], [])

    def test_noisy_identification_within_contract(self):
        driver = hz.LocalDriver(22)
        agent = flo.OracleAgent()
        hz.run_trial(driver, agent, episodes=1)
        true_b = driver.sim.true_b()
        for i in range(4):
            self.assertLess(max(abs(agent.vectors()[i][j] - true_b[i][j]) for j in range(2)), 0.03)
        self.assertEqual(agent.summary()["contract_violations"], 0)


class EndToEndLocalTests(unittest.TestCase):
    def test_remap_detected_and_original_body_revisited(self):
        driver, agent = hz.LocalDriver(31), flo.OracleAgent()
        hz.run_trial(driver, agent, episodes=6)
        summary = agent.summary()
        self.assertEqual(summary["contract_violations"], 0)
        self.assertEqual(summary["missing_receipts"], 0)
        switches = summary["switches"]
        self.assertTrue(any(s["when"][0] == 3 and s["when"][1] <= 3 and s["kind"] == "new"
                            and s["trigger"] == "hard" for s in switches))
        self.assertTrue(any(s["when"][0] == 5 and s["when"][1] <= 3 and s["kind"] == "revisit"
                            and s["to"] == 0 for s in switches))
        self.assertFalse(any(s["when"][0] in (0, 1, 2, 4) for s in switches))

    def test_oracle_beats_random_and_coast(self):
        rows, _ = hz.run(["public_oracle", "random", "coast_only"], [1, 2], "local", None, 6)
        rep = sc.report(rows)
        oracle = rep["agents"]["public_oracle"]["all"]["mean"]
        rnd = rep["agents"]["random"]["all"]["mean"]
        self.assertAlmostEqual(rep["agents"]["coast_only"]["all"]["mean"], 1.0, places=9)
        self.assertLess(oracle, rnd - 0.2)
        self.assertLess(oracle, 0.6)
        self.assertGreater(rep["normalised"]["coast_only"]["all"]["mean"], -1.0)
        self.assertGreater(rep["normalised_pooled"]["coast_only"]["all"]["mean"], -1.0)


class ScoringTests(unittest.TestCase):
    def test_bootstrap_deterministic_and_centred(self):
        vals = [0.1 * i for i in range(10)]
        a, b = sc.bootstrap_mean(vals, 500), sc.bootstrap_mean(vals, 500)
        self.assertEqual(a, b)
        self.assertLessEqual(a["lo"], a["mean"])
        self.assertLessEqual(a["mean"], a["hi"])
        self.assertEqual(sc.bootstrap_mean([])["n"], 0)

    def test_normalised_score_endpoints(self):
        rows = []
        for seed in range(3):
            for ep in range(6):
                base = {"seed": seed, "episode": ep, "mean_distance": 0.0, "early32_distance": 0.0,
                        "final_within_0_15": 1}
                rows.append({**base, "agent": "public_oracle", "mean_distance": 0.3})
                rows.append({**base, "agent": "random", "mean_distance": 1.0})
                rows.append({**base, "agent": "same_as_oracle", "mean_distance": 0.3})
                rows.append({**base, "agent": "same_as_random", "mean_distance": 1.0})
        rep = sc.report(rows, resamples=100)
        self.assertAlmostEqual(rep["normalised"]["same_as_oracle"]["all"]["mean"], 1.0)
        self.assertAlmostEqual(rep["normalised"]["same_as_random"]["all"]["mean"], 0.0)
        self.assertAlmostEqual(rep["normalised_pooled"]["same_as_oracle"]["all"]["mean"], 1.0)
        self.assertAlmostEqual(rep["normalised_pooled"]["same_as_random"]["all"]["mean"], 0.0)
        self.assertAlmostEqual(rep["contrasts"]["same_as_oracle - random"]["stable"]["mean"], -0.7)

    def test_pooled_normalisation_survives_a_zero_denominator_seed(self):
        rows = []
        for seed in range(3):
            for ep in range(6):
                rnd = 0.3 if seed == 0 else 1.0          # seed 0: random equals the oracle
                rows.append({"seed": seed, "episode": ep, "agent": "public_oracle", "mean_distance": 0.3})
                rows.append({"seed": seed, "episode": ep, "agent": "random", "mean_distance": rnd})
                rows.append({"seed": seed, "episode": ep, "agent": "cand", "mean_distance": 0.65})
        rep = sc.report(rows, resamples=200)
        self.assertEqual(rep["normalised"]["cand"]["all"]["excluded_seeds_zero_denominator"], [0])
        pooled = rep["normalised_pooled"]["cand"]["all"]
        # means: random 2.3/3, oracle 0.3, candidate 0.65 -> (2.3/3 - 0.65) / (2.3/3 - 0.3) = 0.25
        self.assertEqual(pooled["n"], 3)
        self.assertAlmostEqual(pooled["mean"], 0.25)
        self.assertEqual(rep["normalised_pooled"]["cand"]["remap_early32"]["n"], 0)   # metric absent

    @unittest.skipUnless(PACKAGE, "package not importable")
    def test_episode_metrics_match_first_leaf(self):
        records = [{"tick": t, "distance": 1.0 - t / 100, "velocity_mse": 0.001,
                    "body_model_error": 0.2 if t < 20 else 0.05} for t in range(80)]
        self.assertEqual(sc.episode_metrics(records), first_leaf.episode_metrics(records))


@unittest.skipUnless(PACKAGE, "package not importable")
class PackageParityTests(unittest.TestCase):
    def test_fixture_and_body_replica_match_package(self):
        for seed in (103, 20001):
            fx_pkg, fx_loc = first_leaf.fixture(seed, CFG), sim.fixture(seed, sim.DEFAULT_CFG)
            self.assertEqual(first_leaf.canonical(fx_pkg), sim.canonical(fx_loc))
            for ep in range(6):
                self.assertEqual(first_leaf.body_vectors(CFG, fx_pkg, ep, CFG["profiles"]["primary"]),
                                 sim.body_vectors(sim.DEFAULT_CFG, fx_loc, ep, sim.DEFAULT_CFG["profile"]))

    def test_local_sim_matches_relay_inproc(self):
        local = hz.run_trial(hz.LocalDriver(20001), flo.OracleAgent(), episodes=2)
        driver = hz.InprocRelayDriver(20001, PKG_ROOT)
        try:
            remote = hz.run_trial(driver, flo.OracleAgent(), episodes=2)
        finally:
            driver.close()
        self.assertEqual(len(local["records"]), 160)
        self.assertEqual(remote["export_recoveries"], 0)
        for a, b in zip(local["records"], remote["records"]):
            self.assertEqual(a["executed"], b["executed"])
            self.assertAlmostEqual(a["distance"], b["distance"], places=12)

    def test_session_rows_match_live_records(self):
        driver = hz.InprocRelayDriver(20003, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            result = hz.run_trial(driver, agent, episodes=2)
            live = hz.episode_rows("public_oracle", 20003, "inproc", result, agent.summary())
            post = hz.session_rows(driver.dir, "public_oracle")
        finally:
            driver.close()
        self.assertEqual(len(post), 2)
        for a, b in zip(live, post):
            for key in ("episode", "seed", "mean_distance", "early32_distance", "final_distance",
                        "final_within_0_15", "executed_steps", "rejections"):
                self.assertEqual(a[key], b[key], key)
            self.assertIsNone(b["body_model_error"])

    def test_subprocess_relay_smoke(self):
        driver = hz.SubprocessRelayDriver(20002, PKG_ROOT)
        try:
            result = hz.run_trial(driver, flo.OracleAgent(), episodes=1, steps_per_episode=5)
            packet = driver.packet()
        finally:
            driver.close()
        self.assertEqual(len(result["records"]), 5)
        self.assertEqual(packet["sequence"], 5)
        self.assertEqual([r["executed"] for r in result["records"]][:4], ["k0", "k1", "k2", "k3"])

    @unittest.skipUnless(LIFECYCLE, "lifecycle relay (ExportAfterCommitError) not importable")
    def test_export_failure_after_commit_is_recovered_without_replay(self):
        driver = hz.InprocRelayDriver(20004, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            original = driver.relay.export
            calls = {"n": 0}

            def failing_export(s, directory):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError("simulated export failure after commit")
                return original(s, directory)

            driver.relay.export = failing_export
            try:
                event = driver.step(flo.canonical(agent.act(driver.packet())))
            finally:
                driver.relay.export = original
            self.assertEqual(event["receipt"]["execution_status"], flo.EXECUTED)
            self.assertEqual(driver.export_recoveries, 1)
            self.assertEqual(calls["n"], 2)                      # failed once, regenerated once, no replay
            self.assertEqual(driver.packet()["sequence"], 1)
            self.assertEqual(driver.truth()["tick"], 1)
        finally:
            driver.close()

    @unittest.skipUnless(LIFECYCLE, "lifecycle relay not importable")
    def test_lifecycle_receipt_fields_as_seen_by_the_agent(self):
        driver = hz.InprocRelayDriver(20005, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            driver.step(flo.canonical(agent.act(driver.packet())))
            packet = driver.packet()
            agent.act(packet)
        finally:
            driver.close()
        self.assertIsNone(packet["active_request"])
        last = packet["recent_events"][-1]
        self.assertTrue(last["executed"])
        self.assertFalse(last["receipt"]["dispatch"])             # authorization consumed at mark_dispatched
        self.assertEqual(agent.log.summary()["receipts"], 1)      # ...and the oracle still commits the action
        self.assertEqual(agent.log.summary()["ignored_events"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
