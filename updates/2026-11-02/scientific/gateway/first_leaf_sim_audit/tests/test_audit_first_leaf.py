"""Independent audit tests for the First Leaf simulator and file relay (task firstleaf-sim-audit-001).

Place at <package>/tests/test_audit_first_leaf.py and run from the package root:
    python -m unittest tests.test_audit_first_leaf -v
(first_leaf reads inputs/protocol.json relative to its own location.)

Naming convention
  test_control_*        properties the static reading says HOLD: expected PASS on the ORIGINAL code
  test_finding_D*       expected FAIL on the ORIGINAL code; expected PASS after patches/*.diff
  test_prior_finding_*  Coda's SCOPE_GAP standalone-Gateway findings; expected FAIL on the original;
                        deliberately NOT patched here (lifecycle redesign needs coordinator agreement)
Author: Claude (Anthropic) for Red. Nothing here was executed by the author; outcomes are predictions.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))

import interface  # noqa: E402
import relay  # noqa: E402
from first_leaf import Agent, Episode, body_vectors, canonical, fixture, load_protocol  # noqa: E402
from interface import ACTIONS, Gateway  # noqa: E402
from relay import init, transact, writer_lock  # noqa: E402

CFG = load_protocol()
SEED = 20000  # outside the frozen development (100..115) and evaluation (10000..10255) ranges
FX = fixture(SEED, CFG)
ACTOR = 'audit_scripted_test_not_hosted_model'


def gw_request(request_id='r0', action='k0', **changes):
    value = {'schema': 'stage.action.v1', 'request_id': request_id, 'session_id': 'test',
             'body_revision': 'planar-v1', 'sequence': 0, 'observation_id': 'o0',
             'expires_tick': 2, 'action': action}
    value.update(changes)
    return canonical(value)


def float_pairs(value, out=None):
    """All two-element float lists anywhere inside a JSON-like value."""
    out = [] if out is None else out
    if isinstance(value, list):
        if len(value) == 2 and all(isinstance(x, float) for x in value):
            out.append(value)
        for item in value:
            float_pairs(item, out)
    elif isinstance(value, dict):
        for item in value.values():
            float_pairs(item, out)
    return out


class RelayAuditBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('AUDIT_TMPDIR'))
        self.d = Path(self.tmp.name)
        # Durability is not under test; skipping fsync keeps the suite fast on slow disks.
        fsync_patch = mock.patch('os.fsync', lambda fd: None)
        fsync_patch.start()
        self.addCleanup(fsync_patch.stop)
        init(self.d, SEED, ACTOR)

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        return json.loads((self.d / 'private_state.json').read_bytes())

    def packet(self):
        return json.loads((self.d / 'packet.json').read_text())

    def events(self):
        text = (self.d / 'events.jsonl').read_text()
        return [json.loads(line) for line in text.splitlines()]

    def req(self, action='k0', uid='one'):
        r = self.packet()['request_template']
        r.update(action=action, request_id=uid)
        return canonical(r)


class ControlTests(RelayAuditBase):
    """Expected PASS on the original code."""

    def test_control_relay_episode0_matches_simulator_bitwise(self):
        # Drive the relay with the actions a simulator agent chooses; states and samples must be identical.
        agent = Agent('window', CFG)
        sim = Episode(CFG, FX, 'primary', 0, agent)
        for t in range(CFG['steps_per_episode']):
            pkt = self.packet()
            rec = sim.step()
            self.assertEqual(pkt['dispatch_tick'], t)
            self.assertEqual(pkt['episode'], 0)
            self.assertEqual(pkt['sensor']['episode'], 0)
            self.assertEqual(pkt['sensor']['sample_tick'], rec['sample_tick'])
            self.assertEqual(pkt['sensor']['p'], rec['observation']['p'])
            self.assertEqual(pkt['sensor']['v'], rec['observation']['v'])
            action = ACTIONS[rec['executed']]
            event = transact(self.d, self.req(action, f'ep0-{t}'))
            self.assertEqual(event['receipt']['execution_status'], 'verified_simulator_transition')
            self.assertEqual(event['receipt']['executed_action'], action)
            self.assertEqual(event['executed_transition_source_tick'], t)
            want = sim.samples[max(0, t - 1)]
            self.assertEqual(event['observed_sensor']['sample_tick'], max(0, t - 1))
            self.assertEqual(event['observed_sensor']['p'], want['p'])
            self.assertEqual(event['observed_sensor']['v'], want['v'])
            s = self.state()
            self.assertEqual(s['p'], rec['true_p'])
            self.assertEqual(s['v'], rec['true_v'])
        s = self.state()
        self.assertEqual(len(s['samples']), CFG['steps_per_episode'] + 1)
        self.assertEqual([x['p'] for x in s['samples']], [x['p'] for x in sim.samples])
        self.assertEqual([x['v'] for x in s['samples']], [x['v'] for x in sim.samples])
        self.assertTrue(self.packet()['episode_complete'])

    def test_control_relay_honours_episode_dependent_body(self):
        # Operator-side (evaluator role) state surgery to reach episode 3 cheaply; never candidate-facing.
        s = self.state()
        s.update(episode=3, tick=0, p=[0.0, 0.0], v=[0.0, 0.0])
        s['samples'] = [relay.sample(s)]
        relay.atomic(self.d / 'private_state.json', canonical(s) + b'\n', True)
        with writer_lock(self.d):
            relay.export(s, self.d)
        primary = CFG['profiles']['primary']
        b3, b0 = body_vectors(CFG, FX, 3, primary), body_vectors(CFG, FX, 0, primary)
        for k in range(4):
            self.assertNotEqual(b3[k], b0[k])
        event = transact(self.d, self.req('k2', 'm0'))
        self.assertEqual(self.state()['v'], b3[2])
        self.assertNotEqual(self.state()['v'], b0[2])
        self.assertEqual(event['observed_sensor']['episode'], 3)
        transact(self.d, self.req('coast', 'm1'))
        self.assertEqual(self.state()['v'], [0.75 * x for x in b3[2]])

    def test_control_packet_and_events_use_only_public_fields(self):
        for t in range(6):
            transact(self.d, self.req('k' + str(t % 4), f'w{t}'))
        s = self.state()
        redacted = {'tick': s['tick'], 'episode': s['episode'], 'samples': s['samples'],
                    'public_events': s['public_events'], 'gateway': s['gateway'],
                    'cfg': {'profiles': {'primary': {'delay': s['cfg']['profiles']['primary']['delay']}},
                            'steps_per_episode': s['cfg']['steps_per_episode'],
                            'dynamics': s['cfg']['dynamics'], 'observations': s['cfg']['observations']},
                    'fixture': {'goals': s['fixture']['goals'][:s['episode'] + 1]}}
        pkt = relay.packet(s)
        self.assertEqual(relay.packet(redacted), pkt)  # KeyError here would mean a private field is read
        public_text = json.dumps(pkt) + (self.d / 'events.jsonl').read_text()
        for needle in ('mapping_A', 'mapping_B', 'unit_noise', 'negative_labels', '"seed"',
                       'body_schedule', 'true_b', 'gain_A', 'gain_B', '"cfg"', '"fixture"'):
            self.assertNotIn(needle, public_text)
        self.assertNotEqual(s['p'], [0.0, 0.0])
        for pair in float_pairs(pkt) + float_pairs(self.events()):
            self.assertNotEqual(pair, s['p'])
            self.assertNotEqual(pair, s['v'])
        self.assertLessEqual(len(pkt['recent_events']), 12)

    def test_control_idempotency_same_id_same_content_and_changed_content(self):
        raw = self.req('k0', 'r0')
        first = transact(self.d, raw)
        self.assertTrue(first['receipt']['dispatch'])
        self.assertEqual(self.state()['tick'], 1)
        for _ in range(3):
            again = transact(self.d, raw)
            self.assertTrue(again['receipt']['duplicate'])
            self.assertFalse(again['receipt']['dispatch'])
            self.assertEqual(again['receipt']['execution_status'], 'verified_simulator_transition')
        self.assertEqual(self.state()['tick'], 1)
        reordered = json.dumps(json.loads(raw), indent=1).encode()  # same content, other serialization
        self.assertTrue(transact(self.d, reordered)['receipt']['duplicate'])
        changed = json.loads(raw)
        changed['action'] = 'k1'
        rejected = transact(self.d, canonical(changed))
        self.assertEqual(rejected['event'], 'rejected_invalid_request')
        self.assertIn('reused', rejected['reason'])
        stale = json.loads(raw)
        stale['request_id'] = 'r1'  # new ID, stale frame
        self.assertEqual(transact(self.d, canonical(stale))['receipt']['reason'], 'sequence_mismatch')
        self.assertEqual(self.state()['tick'], 1)
        self.assertEqual(self.state()['gateway']['sequence'], 1)

    def test_control_stop_latches_blocks_advance_and_persists(self):
        first_raw = None
        for t in range(CFG['steps_per_episode']):
            raw = self.req('coast', f's{t}')
            first_raw = first_raw or raw
            transact(self.d, raw)
        self.assertTrue(self.packet()['episode_complete'])
        halted = transact(self.d, self.req('stop', 'halt'))
        self.assertTrue(halted['receipt']['stop_latched'])
        self.assertFalse(halted['receipt']['dispatch'])
        with self.assertRaises(ValueError):
            transact(self.d, advance=True)
        later = transact(self.d, self.req('k0', 'after'))
        self.assertEqual(later['receipt']['reason'], 'stop_latched')
        replay = transact(self.d, first_raw)  # duplicate of a pre-stop executed request
        self.assertTrue(replay['receipt']['duplicate'])
        self.assertEqual(self.state()['tick'], CFG['steps_per_episode'])
        self.assertTrue(self.packet()['stopped'])
        self.assertTrue(self.state()['gateway']['stopped'])
        with self.assertRaises(ValueError):
            init(self.d, SEED, ACTOR)  # the latch cannot be reset by re-initialising the session

    def test_control_single_commit_point_and_post_commit_export_failure_is_idempotent(self):
        order = []
        real_atomic = relay.atomic

        def recording_atomic(path, data, private=False):
            self.assertTrue((path.parent / 'writer.lock').exists(), 'write outside the writer lock')
            order.append((path.name, private))
            return real_atomic(path, data, private)

        raw = self.req('k0', 'c0')
        with mock.patch.object(relay, 'atomic', recording_atomic):
            transact(self.d, raw)
        self.assertEqual(order, [('private_state.json', True), ('packet.json', False), ('events.jsonl', False)])

        raw2 = self.req('k1', 'c1')

        def failing_export(s, directory):
            raise OSError('synthetic export failure after the private commit')

        with mock.patch.object(relay, 'export', failing_export):
            with self.assertRaises(OSError):
                transact(self.d, raw2)
        self.assertFalse((self.d / 'writer.lock').exists())
        self.assertEqual(self.state()['tick'], 2)        # committed
        self.assertEqual(self.packet()['sequence'], 1)   # stale public view (regenerable)
        with writer_lock(self.d):                        # operator: relay.py export
            relay.export(self.state(), self.d)
        self.assertEqual(self.packet()['sequence'], 2)
        retry = transact(self.d, raw2)                   # operator re-applies the same action.json
        self.assertTrue(retry['receipt']['duplicate'])
        self.assertEqual(self.state()['tick'], 2)


class FindingTests(RelayAuditBase):
    """Expected FAIL on the original code; expected PASS after patches/relay.py.diff + patches/interface.py.diff."""

    def test_finding_D1_non_valueerror_from_admit_is_still_logged(self):
        def exploding_admit(self_gateway, raw):
            raise RecursionError('synthetic: decoder recursion limit')

        with mock.patch.object(interface.Gateway, 'admit', exploding_admit):
            try:
                event = transact(self.d, self.req('k0', 'deep'))
            except RecursionError:
                event = None
        events = self.events()
        self.assertEqual(len(events), 1, 'the attempt left no durable receipt')
        self.assertIsNotNone(event, 'transact raised instead of returning a rejection event')
        self.assertEqual(events[0]['event'], 'rejected_invalid_request')
        self.assertEqual(self.state()['tick'], 0)
        self.assertFalse((self.d / 'writer.lock').exists())

    def test_finding_D1_deep_nesting_probe_in_child_process(self):
        """ENVIRONMENT-DEPENDENT. 8000-level nesting (16,000 bytes, under the 16 KiB cap) is fed to the
        original relay in a child process so a possible interpreter crash cannot take down this run.
        Coda's SCOPE_GAP reports RecursionError at 6,000 levels on her runtime. If the local decoder
        tolerates the depth, the input is rejected as a non-object with ValueError and this test PASSES
        even on the original code: that is a non-reproduction on this runtime, not a refutation."""
        depth = 8000
        code = ("import sys; sys.path.insert(0, %r); from pathlib import Path; import relay; "
                "relay.transact(Path(%r), b'[' * %d + b']' * %d)" % (str(SRC), str(self.d), depth, depth))
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=300)
        tail = proc.stderr.strip().splitlines()[-1:]
        events = self.events()
        self.assertFalse((self.d / 'writer.lock').exists(),
                         f'child left a writer.lock (hard crash?) rc={proc.returncode} stderr={tail}')
        self.assertEqual(len(events), 1, f'no durable receipt; child rc={proc.returncode}; stderr tail={tail}')
        self.assertEqual(events[0]['event'], 'rejected_invalid_request')
        self.assertEqual(self.state()['tick'], 0)

    def test_finding_D2_rejection_events_identify_the_rejected_bytes(self):
        bad = b'{bad'
        event = transact(self.d, bad)
        self.assertEqual(event['event'], 'rejected_invalid_request')
        self.assertEqual(event.get('request_bytes_sha256'), hashlib.sha256(bad).hexdigest())
        self.assertEqual(event.get('request_bytes_len'), len(bad))
        raw = self.req('k0', 'r0')
        transact(self.d, raw)
        changed = json.loads(raw)
        changed['action'] = 'k1'
        reused = transact(self.d, canonical(changed))
        self.assertEqual(reused['event'], 'rejected_invalid_request')
        self.assertEqual(reused.get('request_bytes_sha256'), hashlib.sha256(canonical(changed)).hexdigest())
        self.assertIn('executed', transact(self.d, raw))  # admitted-but-not-dispatched events say so too

    def test_finding_D3_failed_replace_leaves_no_private_tmp(self):
        real_replace = os.replace

        def failing_replace(src, dst):
            if str(dst).endswith('private_state.json'):
                raise OSError('synthetic rename failure')
            return real_replace(src, dst)

        with mock.patch('os.replace', failing_replace):
            with self.assertRaises(OSError):
                transact(self.d, self.req('k0', 'd3'))
        self.assertEqual(self.state()['tick'], 0)                  # control: no partial commit (holds)
        self.assertFalse((self.d / 'writer.lock').exists())        # control: lock released (holds)
        leftovers = sorted(p.name for p in self.d.glob('*.tmp'))
        self.assertEqual(leftovers, [], f'stray temporary files after a failed commit: {leftovers}')

    def test_finding_D4a_lock_file_carries_owner_identity(self):
        lock = self.d / 'writer.lock'
        with writer_lock(self.d):
            self.assertTrue(lock.exists())
            self.assertTrue(lock.read_bytes().strip(), 'writer.lock is empty; a live writer cannot be checked')
        self.assertFalse(lock.exists())

    def test_finding_D4b_stale_holder_does_not_release_a_newer_writers_lock(self):
        lock = self.d / 'writer.lock'
        holder_a = writer_lock(self.d)
        holder_a.__enter__()
        lock.unlink()  # operator "recovers" the lock while A is in fact still alive
        holder_b = writer_lock(self.d)
        holder_b.__enter__()  # B now legitimately holds the lock
        try:
            holder_a.__exit__(None, None, None)
            self.assertTrue(lock.exists(), 'A released a lock that belonged to B')
        finally:
            holder_b.__exit__(None, None, None)
            lock.unlink(missing_ok=True)

    def test_finding_D5_relay_statements_and_dynamics_follow_the_embedded_protocol(self):
        # Synthetic protocol revision applied operator-side to the embedded cfg.
        s = self.state()
        s['cfg']['dynamics']['alpha'] = 0.5
        s['cfg']['dynamics']['dt'] = 0.2
        s['cfg']['observations']['velocity_noise_scale'] = 0.05
        relay.atomic(self.d / 'private_state.json', canonical(s) + b'\n', True)
        with writer_lock(self.d):
            relay.export(s, self.d)
        pkt = self.packet()
        self.assertEqual(pkt['known_dynamics'], {'dt': 0.2, 'velocity_retention': 0.5})
        self.assertEqual(pkt['sensor_contract']['velocity_noise_bound'], 0.05)
        transact(self.d, self.req('k0', 'a'))
        v1 = self.state()['v']
        transact(self.d, self.req('k0', 'b'))
        s2 = self.state()
        b = body_vectors(s2['cfg'], s2['fixture'], 0, s2['cfg']['profiles']['primary'])
        self.assertEqual(s2['v'], [0.5 * v1[j] + b[0][j] for j in range(2)])

    def test_finding_D6_init_refuses_frozen_fixture_seeds(self):
        for split in ('development', 'evaluation'):
            seed = CFG[f'{split}_seeds']['first']
            with tempfile.TemporaryDirectory(dir=os.environ.get('AUDIT_TMPDIR')) as tmp:
                with self.assertRaises(ValueError, msg=f'{split} seed {seed} is published material'):
                    init(Path(tmp), seed, ACTOR)


class PriorFindingGatewayTests(unittest.TestCase):
    """Coda (Codex Lily), SCOPE_GAP.md: standalone Gateway pending-state defects. Reproduced for completeness;
    expected FAIL on the original and still FAIL after the patches here (deliberately not patched).
    The serial relay is unaffected because admit and record_execution share one lock hold."""

    def test_prior_finding_gateway_pending_admission_is_not_exclusive(self):
        g = Gateway('test')
        self.assertTrue(g.admit(gw_request('r0', 'k0'))['dispatch'])
        second = g.admit(gw_request('r1', 'k1'))
        self.assertFalse(second['dispatch'], 'second distinct command admitted while r0 is pending')

    def test_prior_finding_stop_does_not_cancel_pending_admission(self):
        g = Gateway('test')
        g.admit(gw_request('r0', 'k0'))
        self.assertTrue(g.admit(gw_request('r2', 'stop'))['stop_latched'])
        with self.assertRaises(ValueError):
            g.record_execution('r0', 'k0')


if __name__ == '__main__':
    unittest.main(verbosity=2)
