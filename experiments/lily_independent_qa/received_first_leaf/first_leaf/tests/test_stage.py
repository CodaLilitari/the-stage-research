import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from first_leaf import (Agent, Episode, MeanModel, canonical, checkpoint_check, fixture,
                        load_protocol, replay_check, run_trial, body_vectors)
from interface import Gateway, parse_request

CFG = load_protocol()

def request(**changes):
    value = {"schema": "stage.action.v1", "request_id": "r0", "session_id": "test",
             "body_revision": "planar-v1", "sequence": 0, "observation_id": "o0",
             "expires_tick": 2, "action": "k0"}
    value.update(changes)
    return canonical(value)

class ExperimentTests(unittest.TestCase):
    def test_fixture_reproducible(self):
        self.assertEqual(canonical(fixture(103, CFG)), canonical(fixture(103, CFG)))

    def test_seed_sets_disjoint(self):
        a, b = CFG["development_seeds"], CFG["evaluation_seeds"]
        self.assertTrue(set(range(a["first"], a["first"] + a["count"])).isdisjoint(
            range(b["first"], b["first"] + b["count"])))

    def test_mapping_derangement(self):
        fx = fixture(103, CFG)
        self.assertEqual(sorted(fx["mapping_A"]), list(range(4)))
        self.assertTrue(all(a != b for a, b in zip(fx["mapping_A"], fx["mapping_B"])))

    def test_body_change(self):
        fx = fixture(103, CFG)
        a = body_vectors(CFG, fx, 2, CFG["profiles"]["primary"])
        b = body_vectors(CFG, fx, 3, CFG["profiles"]["primary"])
        self.assertTrue(all(x != y for x, y in zip(a[:4], b[:4])))

    def test_stationary_profile_no_change(self):
        fx = fixture(103, CFG)
        self.assertEqual(body_vectors(CFG, fx, 2, CFG["profiles"]["stationary"]),
                         body_vectors(CFG, fx, 3, CFG["profiles"]["stationary"]))

    def test_mean_learning(self):
        m = MeanModel()
        m.update(0, [0.3, -0.2]); m.update(0, [0.5, -0.4])
        self.assertAlmostEqual(m.vectors()[0][0], 0.4)
        self.assertAlmostEqual(m.vectors()[0][1], -0.3)
        self.assertEqual(m.vectors()[4], [0.0, 0.0])

    def test_window_revises_old_mean(self):
        m = MeanModel(24)
        for _ in range(40): m.update(0, [0.3, 0.0])
        for _ in range(24): m.update(0, [0.0, 0.4])
        self.assertAlmostEqual(m.vectors()[0][0], 0.0, places=12)
        self.assertAlmostEqual(m.vectors()[0][1], 0.4, places=12)
        self.assertEqual(len(m.events), 24)

    def test_no_information_does_not_learn(self):
        a = Agent("no_information", CFG)
        ep = Episode(CFG, fixture(103, CFG), "primary", 0, a)
        for _ in range(80): ep.step()
        ep.finish()
        self.assertEqual(a.model.n, [0, 0, 0, 0])

    def test_duplicate_frames_do_not_learn_twice(self):
        a = Agent("window", CFG); a.start_episode(0, [1, 0])
        a.receive({"tick": 0, "p": [0, 0], "v": [0, 0]})
        a.history = [0]
        obs = {"tick": 1, "p": [0, 0], "v": [0.3, 0]}
        a.receive(obs); before = canonical(a.model.state()); a.receive(obs)
        self.assertEqual(before, canonical(a.model.state()))

    def test_nonadjacent_frame_rejected(self):
        a = Agent("window", CFG); a.start_episode(0, [1, 0])
        a.receive({"tick": 0, "p": [0, 0], "v": [0, 0]}); a.history = [0, 1]
        with self.assertRaises(ValueError):
            a.receive({"tick": 2, "p": [0, 0], "v": [0.3, 0]})

    def test_clean_oracle_predicts_velocity(self):
        rows, _ = run_trial(CFG, fixture(103, CFG), "clean", "oracle")
        self.assertTrue(all(r["velocity_mse"] < 1e-25 for r in rows))

    def test_same_seed_same_full_output_digest(self):
        fx = fixture(103, CFG)
        self.assertEqual(run_trial(CFG, fx, "primary", "window"),
                         run_trial(CFG, fx, "primary", "window"))

    def test_replay_equality(self):
        r = replay_check(CFG, fixture(103, CFG))
        self.assertTrue(r["identical"]); self.assertEqual(r["comparisons"], 486)

    def test_full_checkpoint(self):
        self.assertTrue(checkpoint_check(CFG, fixture(103, CFG))["full_state_exact"])

    def test_checkpoint_context_hash_rejected(self):
        fx = fixture(103, CFG)
        ep = Episode(CFG, fx, "primary", 0, Agent("window", CFG)); ep.step()
        state = ep.checkpoint(); state["protocol_digest"] = "bad"
        with self.assertRaises(ValueError): Episode.restore(state, CFG, fx)

    def test_cross_process_resume(self):
        fx = fixture(103, CFG)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); r = checkpoint_check(CFG, fx, root)
            out = root / "resumed.jsonl"
            subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "src/first_leaf.py"),
                            "resume", "--checkpoint", str(root / "checkpoint.json"), "--fixture",
                            str(root / "checkpoint_fixture.json"), "--out", str(out)], check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), r["reference_sha256"])

    def test_alignment_ablation_no_delay_identity(self):
        fx = fixture(103, CFG)
        _, a = run_trial(CFG, fx, "no_delay", "window")
        _, b = run_trial(CFG, fx, "no_delay", "misaligned")
        self.assertEqual(a, b)

    def test_frozen_stops_updating_after_episode_zero(self):
        a = Agent("frozen", CFG); fx = fixture(103, CFG)
        ep = Episode(CFG, fx, "primary", 0, a)
        for _ in range(80): ep.step()
        ep.finish(); before = canonical(a.model.state())
        ep = Episode(CFG, fx, "primary", 1, a)
        for _ in range(80): ep.step()
        ep.finish(); self.assertEqual(before, canonical(a.model.state()))

class GatewayTests(unittest.TestCase):
    def test_valid_request(self):
        g = Gateway("test"); r = g.admit(request())
        self.assertTrue(r["dispatch"])
        g.record_execution("r0", "k0"); self.assertEqual(g.sequence, 1)

    def test_unknown_field(self):
        with self.assertRaises(ValueError): parse_request(request(shell="rm"))

    def test_unknown_action(self):
        with self.assertRaises(ValueError): parse_request(request(action="run_shell"))

    def test_bool_is_not_sequence(self):
        with self.assertRaises(ValueError): parse_request(request(sequence=True))

    def test_duplicate_json_key(self):
        raw = request().replace(b'{', b'{"sequence":0,', 1)
        with self.assertRaises(ValueError): parse_request(raw)

    def test_nonfinite(self):
        with self.assertRaises(ValueError): parse_request(request().replace(b'"sequence":0', b'"sequence":NaN'))

    def test_size_limit(self):
        with self.assertRaises(ValueError): parse_request(b' ' * 16385)

    def test_duplicate_suppresses_second_dispatch(self):
        g = Gateway("test"); g.admit(request()); g.record_execution("r0", "k0")
        r = g.admit(request()); self.assertTrue(r["duplicate"]); self.assertFalse(r["dispatch"])
        self.assertEqual(g.sequence, 1)

    def test_duplicate_id_changed_content_rejected(self):
        g = Gateway("test"); g.admit(request())
        with self.assertRaises(ValueError): g.admit(request(action="k1"))

    def test_stale_observation(self):
        self.assertEqual(Gateway("test").admit(request(observation_id="old"))["reason"], "observation_mismatch")

    def test_expired_deadline(self):
        g = Gateway("test", tick=3)
        self.assertEqual(g.admit(request(expires_tick=2))["reason"], "invalid_deadline")

    def test_body_revision_mismatch(self):
        self.assertEqual(Gateway("test").admit(request(body_revision="different"))["reason"], "body_mismatch")

    def test_session_mismatch(self):
        self.assertEqual(Gateway("test").admit(request(session_id="other"))["reason"], "session_mismatch")

    def test_stop_latches(self):
        g = Gateway("test"); r = g.admit(request(action="stop"))
        self.assertTrue(r["stop_latched"]); self.assertFalse(r["dispatch"])
        self.assertEqual(g.admit(request(request_id="r1"))["reason"], "stop_latched")

    def test_stop_does_not_need_fresh_frame(self):
        g = Gateway("test"); r = g.admit(request(action="stop", observation_id="old"))
        self.assertTrue(r["stop_latched"])

    def test_cannot_falsely_record_execution(self):
        g = Gateway("test")
        with self.assertRaises(ValueError): g.record_execution("missing", "k0")

    def test_substitution_not_silent(self):
        g = Gateway("test"); g.admit(request())
        with self.assertRaises(ValueError): g.record_execution("r0", "k1")

    def test_cannot_execute_twice(self):
        g = Gateway("test"); g.admit(request()); g.record_execution("r0", "k0")
        with self.assertRaises(ValueError): g.record_execution("r0", "k0")

if __name__ == '__main__': unittest.main(verbosity=2)
