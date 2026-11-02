# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# GW-ASYNC0 relay acceptance tests (invariants I11, I12 and the relay side of I6, I10). Design: Coda
# (Codex Lily) with Richard Pemberton; tests: Claude (Anthropic), coordinated by Red, 2026-11.
# Written statically; not executed by the author. Failure injection uses unittest.mock only.
"""Relay-level acceptance tests for the GW-ASYNC0 lifecycle in relay.py."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from first_leaf import canonical
from interface import (LEGACY_EXECUTION_STATUS, REJECTED, STOP_ACKNOWLEDGED, UNKNOWN_OUTCOME,
                       VERIFIED_FAILURE, VERIFIED_SIMULATOR_TRANSITION, Gateway)
import relay
from relay import LEGACY_STATE_SCHEMA, STATE_SCHEMA, atomic, init, migrate, regenerate_views, transact

HIDDEN = ['fixture', 'mapping_A', 'mapping_B', 'true_b', 'unit_noise', 'seed', 'body_schedule']
LEGACY_GATEWAY_KEYS = ('session_id', 'body_revision', 'sequence', 'tick', 'observation_id', 'stopped', 'cache')


class RelayLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        init(self.d, 20000, 'scripted_test_not_hosted_model')

    def tearDown(self):
        self.tmp.cleanup()

    def req(self, action='k0', uid='one', **over):
        r = self.packet()['request_template']
        r.update(action=action, request_id=uid, **over)
        return canonical(r)

    def state(self):
        return json.loads((self.d / 'private_state.json').read_text())

    def packet(self):
        return json.loads((self.d / 'packet.json').read_text())

    def events(self):
        return [json.loads(line) for line in (self.d / 'events.jsonl').read_text().splitlines()]

    def write_state(self, s):
        atomic(self.d / 'private_state.json', canonical(s) + b'\n', True)

    def test_step_runs_the_explicit_lifecycle_and_commits_gateway_with_simulator(self):  # I11
        raw = self.req()
        event = transact(self.d, raw)
        self.assertEqual(event['event'], 'action_receipt'); self.assertTrue(event['executed'])
        r = event['receipt']
        self.assertEqual(r['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertEqual(r['executed_action'], 'k0'); self.assertFalse(r['dispatch']); self.assertFalse(r['duplicate'])
        self.assertEqual(event['executed_transition_source_tick'], 0)
        s = self.state()
        self.assertEqual(s['schema'], STATE_SCHEMA); self.assertEqual(s['tick'], 1); self.assertEqual(len(s['samples']), 2)
        g = Gateway.restore(s['gateway'])
        self.assertEqual((g.sequence, g.tick, g.observation_id), (1, 1, 'o1')); self.assertIsNone(g.active_request_id)
        self.assertEqual(g.cache['one']['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        p = self.packet()
        self.assertEqual((p['sequence'], p['observation_id'], p['dispatch_tick']), (1, 'o1', 1))
        self.assertIsNone(p['active_request'])
        self.assertEqual(self.events(), [event])
        self.assertFalse((self.d / 'writer.lock').exists())
        dup = transact(self.d, raw)
        self.assertTrue(dup['receipt']['duplicate']); self.assertFalse(dup['receipt']['dispatch'])
        self.assertFalse(dup['executed']); self.assertEqual(dup['receipt']['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertEqual(self.state()['tick'], 1); self.assertEqual(len(self.events()), 2)

    def test_episode_complete_is_a_real_rejection_and_advance_needs_a_clear_slot(self):  # I12
        with self.assertRaises(ValueError): transact(self.d, advance=True)  # mid-episode
        for t in range(80):
            transact(self.d, self.req('k' + str(t % 4), str(t)))
        self.assertTrue(self.packet()['episode_complete']); self.assertEqual(self.state()['tick'], 80)
        raw = self.req('k0', 'extra')
        event = transact(self.d, raw); r = event['receipt']
        self.assertFalse(r['admitted']); self.assertEqual(r['reason'], 'episode_complete'); self.assertFalse(r['dispatch'])
        self.assertEqual(r['execution_status'], REJECTED); self.assertFalse(event['executed'])
        s = self.state(); self.assertEqual(s['tick'], 80); self.assertEqual(s['gateway']['sequence'], 80)
        self.assertEqual(s['gateway']['cache']['extra']['execution_status'], REJECTED)
        self.assertIsNone(s['gateway']['active_request_id'])
        dup = transact(self.d, raw)['receipt']
        self.assertTrue(dup['duplicate']); self.assertEqual(dup['reason'], 'episode_complete')
        self.assertEqual(dup['execution_status'], REJECTED); self.assertEqual(self.state()['tick'], 80)
        reset = transact(self.d, advance=True)
        self.assertEqual(reset['event'], 'operator_episode_reset')
        s = self.state(); self.assertEqual((s['episode'], s['tick']), (1, 0)); self.assertEqual(self.packet()['sequence'], 80)

    def test_stop_latches_in_relay_without_claiming_cancellation(self):  # I6, I7
        event = transact(self.d, self.req('stop', 'halt')); r = event['receipt']
        self.assertEqual(r['execution_status'], STOP_ACKNOWLEDGED); self.assertTrue(r['stop_latched'])
        self.assertNotIn('cancelled_request_id', r); self.assertNotIn('outstanding_request_id', r)
        self.assertFalse(event['executed']); self.assertTrue(self.packet()['stopped'])
        later = transact(self.d, self.req('k0', 'later'))['receipt']
        self.assertEqual((later['reason'], later['execution_status']), ('stop_latched', REJECTED))
        self.assertEqual(self.state()['tick'], 0)
        with self.assertRaises(ValueError): transact(self.d, advance=True)

    def test_pre_commit_computation_failure_is_a_verified_failure_without_advance(self):  # I11
        raw = self.req('k0', 'fails')
        with mock.patch('relay.candidate_transition', side_effect=ArithmeticError('simulated computation failure')):
            event = transact(self.d, raw)
        r = event['receipt']
        self.assertEqual(r['execution_status'], VERIFIED_FAILURE)
        self.assertIn('simulated computation failure', r['failure_reason'])
        self.assertFalse(r['dispatch']); self.assertFalse(event['executed']); self.assertNotIn('executed_action', r)
        s = self.state()
        self.assertEqual(s['tick'], 0); self.assertEqual(len(s['samples']), 1); self.assertEqual(s['gateway']['sequence'], 0)
        self.assertIsNone(s['gateway']['active_request_id'])
        self.assertEqual(s['gateway']['cache']['fails']['execution_status'], VERIFIED_FAILURE)
        self.assertEqual(self.packet()['sequence'], 0); self.assertEqual(len(self.events()), 1)
        dup = transact(self.d, raw)['receipt']
        self.assertTrue(dup['duplicate']); self.assertEqual(dup['execution_status'], VERIFIED_FAILURE)
        fresh = transact(self.d, self.req('k0', 'after'))
        self.assertTrue(fresh['executed']); self.assertEqual(self.state()['tick'], 1)

    def test_commit_exception_writes_nothing_and_records_no_false_failure(self):  # I11
        raw = self.req('k0', 'lost'); before = self.state(); packet_before = self.packet()
        with mock.patch('relay.atomic', side_effect=OSError('simulated ambiguous replacement')):
            with self.assertRaises(OSError): transact(self.d, raw)
        self.assertEqual(self.state(), before); self.assertEqual(self.packet(), packet_before)
        self.assertEqual(self.events(), []); self.assertFalse((self.d / 'writer.lock').exists())
        self.assertNotIn('lost', before['gateway']['cache'])
        event = transact(self.d, raw)  # nothing was recorded, so this is the first and only dispatch
        self.assertFalse(event['receipt']['duplicate']); self.assertTrue(event['executed'])
        self.assertEqual(self.state()['tick'], 1)

    def test_export_failure_after_commit_leaves_committed_state_regenerable_without_replay(self):  # I11
        raw = self.req('k0', 'committed'); stale_packet = self.packet()
        with mock.patch('relay.export', side_effect=OSError('simulated export failure')):
            with self.assertRaises(RuntimeError) as ctx: transact(self.d, raw)
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        s = self.state()
        self.assertEqual(s['tick'], 1); self.assertEqual(s['gateway']['sequence'], 1)
        self.assertEqual(s['gateway']['cache']['committed']['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertEqual(self.packet(), stale_packet, 'views are stale until regenerated')
        self.assertFalse((self.d / 'writer.lock').exists())
        result = regenerate_views(self.d)
        self.assertEqual(result['sequence'], 1); self.assertEqual(self.state(), s, 'regeneration never replays')
        self.assertEqual(self.packet()['sequence'], 1); self.assertEqual(len(self.events()), 1)
        dup = transact(self.d, raw)['receipt']
        self.assertTrue(dup['duplicate']); self.assertEqual(self.state()['tick'], 1)

    def test_restored_in_flight_receipt_blocks_actions_and_advance_and_is_exposed(self):  # I12
        s = self.state(); g = Gateway.restore(s['gateway'])
        g.admit(self.req('k0', 'pending')); g.mark_dispatched('pending')
        g.mark_unknown('pending', 'operator-injected unresolved outcome')
        s['gateway'] = asdict(g); self.write_state(s)
        regenerate_views(self.d)
        p = self.packet()
        self.assertEqual(p['active_request']['request_id'], 'pending')
        self.assertEqual(p['active_request']['execution_status'], UNKNOWN_OUTCOME)
        text = json.dumps(p)
        for key in HIDDEN:
            self.assertNotIn(key, text)
        blocked = transact(self.d, self.req('k1', 'other'))['receipt']
        self.assertEqual((blocked['reason'], blocked['execution_status']), ('command_pending', REJECTED))
        with self.assertRaises(ValueError): transact(self.d, advance=True)
        stop = transact(self.d, self.req('stop', 'halt'))['receipt']
        self.assertEqual(stop['outstanding_request_id'], 'pending'); self.assertEqual(stop['outstanding_status'], UNKNOWN_OUTCOME)
        self.assertNotIn('cancelled_request_id', stop)
        s = self.state()
        self.assertEqual(s['tick'], 0); self.assertEqual(s['gateway']['active_request_id'], 'pending')
        self.assertEqual(s['gateway']['cache']['pending']['execution_status'], UNKNOWN_OUTCOME)
        self.assertTrue(s['gateway']['stopped'])

    def test_legacy_state_is_refused_until_explicit_migration(self):  # I10
        transact(self.d, self.req('k0', 'one'))                      # one verified transition
        transact(self.d, self.req('k1', 'stale', sequence=0))        # one sequence_mismatch rejection
        s = self.state()
        legacy = {k: s['gateway'][k] for k in LEGACY_GATEWAY_KEYS}
        legacy['cache']['one']['dispatch'] = True                                # legacy kept dispatch=True
        legacy['cache']['stale']['execution_status'] = LEGACY_EXECUTION_STATUS   # legacy catch-all status
        s['schema'] = LEGACY_STATE_SCHEMA; s['gateway'] = legacy; self.write_state(s)
        with self.assertRaises(ValueError) as ctx: transact(self.d, self.req('k0', 'two'))
        self.assertIn('migrate', str(ctx.exception))
        with self.assertRaises(ValueError): regenerate_views(self.d)
        self.assertEqual(self.state()['schema'], LEGACY_STATE_SCHEMA)
        result = migrate(self.d)
        self.assertTrue(result['migrated']); s = self.state()
        self.assertEqual(s['schema'], STATE_SCHEMA); g = Gateway.restore(s['gateway'])
        self.assertEqual(g.cache['one']['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertFalse(g.cache['one']['dispatch'])
        self.assertEqual(g.cache['stale']['execution_status'], REJECTED); self.assertIsNone(g.active_request_id)
        self.assertEqual(s['public_events'][-1]['event'], 'operator_state_migration')
        self.assertTrue((self.d / relay.LEGACY_BACKUP_NAME).exists())
        with self.assertRaises(ValueError): migrate(self.d)  # already migrated: not legacy
        event = transact(self.d, self.req('k0', 'two'))
        self.assertTrue(event['executed']); self.assertEqual(self.state()['tick'], 2)

    def test_migration_fails_closed_on_ambiguous_legacy_receipt_and_writes_nothing(self):  # I10
        s = self.state()
        legacy = {k: s['gateway'][k] for k in LEGACY_GATEWAY_KEYS}
        legacy['cache'] = {'ghost': {'request_id': 'ghost', 'request_sha256': '0' * 64, 'requested_action': 'k0',
                                     'admitted': True, 'reason': None, 'duplicate': False, 'dispatch': True,
                                     'stop_latched': False, 'execution_status': LEGACY_EXECUTION_STATUS}}
        s['schema'] = LEGACY_STATE_SCHEMA; s['gateway'] = legacy; self.write_state(s); before = self.state()
        with self.assertRaises(ValueError) as ctx: migrate(self.d)
        self.assertIn('Ambiguous', str(ctx.exception))
        self.assertEqual(self.state(), before); self.assertFalse((self.d / relay.LEGACY_BACKUP_NAME).exists())
        self.assertFalse((self.d / 'writer.lock').exists())
        with self.assertRaises(ValueError): transact(self.d, self.req('k0', 'two'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
