# SPDX-License-Identifier: MIT
"""Frozen v2: exact 6000-level JSON witness; v1 assumption and evidence retained."""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from first_leaf import canonical
from interface import Gateway, parse_request
from relay import init, transact


def request(**changes):
    value = {'schema': 'stage.action.v1', 'request_id': 'r0', 'session_id': 'test',
             'body_revision': 'planar-v1', 'sequence': 0, 'observation_id': 'o0',
             'expires_tick': 2, 'action': 'k0'}
    value.update(changes)
    return canonical(value)


def caught(call):
    try:
        return call(), None
    except Exception as exc:
        return None, exc


def nested_request():
    # Schema is deliberately invalid, but the decoder must reject with a
    # handled input exception before schema validation, not lose the receipt.
    value = b'{"x":' + b'[' * 6000 + b'0' + b']' * 6000 + b'}'
    assert len(value) < 16384
    return value


class PendingCommandTests(unittest.TestCase):
    def test_second_distinct_pending_request_is_rejected(self):
        g = Gateway('test')
        first = g.admit(request())
        second = g.admit(request(request_id='r1', action='k1'))
        self.assertTrue(first['dispatch'])
        self.assertFalse(second['admitted'], 'Two distinct commands admitted at one pending sequence')
        self.assertFalse(second['dispatch'])
        self.assertEqual(second['reason'], 'command_pending')
        self.assertEqual((g.sequence, g.tick, g.observation_id), (0, 0, 'o0'))

    def test_duplicate_pending_suppression_does_not_release_slot(self):
        g = Gateway('test'); g.admit(request())
        duplicate = g.admit(request())
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertEqual(g.cache['r0']['execution_status'], 'not_dispatched')
        with self.assertRaises(ValueError):
            g.admit(request(action='k1'))
        g.record_execution('r0', 'k0')
        self.assertEqual((g.sequence, g.tick), (1, 1))

    def test_fresh_state_request_after_execution_is_admitted(self):
        g = Gateway('test'); g.admit(request()); g.record_execution('r0', 'k0')
        result = g.admit(request(request_id='r2', sequence=1, observation_id='o1', expires_tick=3))
        self.assertTrue(result['admitted']); self.assertTrue(result['dispatch'])

    def test_pending_rejection_is_not_silently_retried(self):
        g = Gateway('test'); g.admit(request())
        raw = request(request_id='r1')
        rejected = g.admit(raw)
        self.assertFalse(rejected['admitted'])
        g.record_execution('r0', 'k0')
        duplicate = g.admit(raw)
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertFalse(duplicate['admitted']); self.assertEqual(duplicate['reason'], 'command_pending')


class StopPendingTests(unittest.TestCase):
    def test_stop_cancels_and_preserves_pending_receipt(self):
        g = Gateway('test'); admitted = g.admit(request())
        stopped = g.admit(request(request_id='stop', action='stop', observation_id='old', expires_tick=0))
        self.assertTrue(stopped['admitted']); self.assertFalse(stopped['dispatch'])
        retained = g.cache['r0']
        self.assertEqual(retained['request_sha256'], admitted['request_sha256'])
        self.assertTrue(retained['admitted'], 'Preserve the earlier admission as historical fact')
        self.assertFalse(retained['dispatch'], 'Stop must revoke the pending gateway dispatch')
        self.assertEqual(retained['execution_status'], 'cancelled_pending_by_stop')
        self.assertTrue(retained['stop_latched'])
        self.assertNotIn('executed_action', retained)
        self.assertEqual((g.sequence, g.tick), (0, 0))

    def test_record_after_stop_cannot_verify_or_advance(self):
        g = Gateway('test'); g.admit(request()); g.admit(request(request_id='stop', action='stop'))
        _, error = caught(lambda: g.record_execution('r0', 'k0'))
        self.assertIsInstance(error, ValueError, 'Stopped gateway accepted a pending execution record')
        self.assertEqual((g.sequence, g.tick), (0, 0))
        self.assertNotIn('executed_action', g.cache['r0'])

    def test_duplicate_cancelled_request_remains_cancelled(self):
        g = Gateway('test'); raw = request(); g.admit(raw)
        g.admit(request(request_id='stop', action='stop'))
        duplicate = g.admit(raw)
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertEqual(duplicate['execution_status'], 'cancelled_pending_by_stop')

    def test_invalid_session_stop_does_not_cancel_pending(self):
        g = Gateway('test'); g.admit(request())
        result = g.admit(request(request_id='foreign-stop', action='stop', session_id='foreign'))
        self.assertEqual(result['reason'], 'session_mismatch'); self.assertFalse(g.stopped)
        g.record_execution('r0', 'k0'); self.assertEqual(g.tick, 1)

    def test_invalid_body_stop_does_not_cancel_pending(self):
        g = Gateway('test'); g.admit(request())
        result = g.admit(request(request_id='foreign-stop', action='stop', body_revision='foreign'))
        self.assertEqual(result['reason'], 'body_mismatch'); self.assertFalse(g.stopped)
        g.record_execution('r0', 'k0'); self.assertEqual(g.tick, 1)

    def test_stop_preserves_verified_earlier_transition(self):
        g = Gateway('test'); g.admit(request()); g.record_execution('r0', 'k0')
        earlier = copy.deepcopy(g.cache['r0'])
        g.admit(request(request_id='r1', sequence=1, observation_id='o1'))
        g.admit(request(request_id='stop', action='stop'))
        self.assertEqual(g.cache['r0'], earlier)
        self.assertEqual(g.cache['r1']['execution_status'], 'cancelled_pending_by_stop')
        self.assertEqual((g.tick, g.sequence), (1, 1))

    def test_cancelled_state_round_trip_does_not_reenable_execution(self):
        g = Gateway('test'); g.admit(request()); g.admit(request(request_id='stop', action='stop'))
        restored = Gateway(**json.loads(canonical(asdict(g))))
        _, error = caught(lambda: restored.record_execution('r0', 'k0'))
        self.assertIsInstance(error, ValueError)
        self.assertEqual(restored.tick, 0); self.assertTrue(restored.stopped)


class NestedJsonTests(unittest.TestCase):
    def test_nested_decoder_exception_is_a_handled_value_error(self):
        _, error = caught(lambda: parse_request(nested_request()))
        self.assertIsInstance(error, ValueError, 'Deep request escaped as ' + type(error).__name__)
        self.assertIn('JSON nesting', str(error))

    def assert_relay_receipt(self, stopped):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            packet = init(directory, 20000, 'scripted_regression_not_hosted_model')
            if stopped:
                stop = dict(packet['request_template'], request_id='stop', action='stop')
                transact(directory, canonical(stop))
            before = json.loads((directory/'private_state.json').read_text())
            event, error = caught(lambda: transact(directory, nested_request()))
            self.assertIsNone(error, 'Relay raised instead of recording rejection: ' + type(error).__name__)
            self.assertEqual(event['event'], 'rejected_invalid_request')
            self.assertFalse(event['executed']); self.assertIn('JSON nesting', event['reason'])
            after = json.loads((directory/'private_state.json').read_text())
            for key in ['tick', 'episode', 'p', 'v', 'gateway', 'samples']:
                self.assertEqual(after[key], before[key], key)
            self.assertEqual(len(after['public_events']), len(before['public_events']) + 1)
            events = [json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1], event)
            self.assertFalse((directory/'writer.lock').exists())

    def test_nested_request_gets_durable_relay_rejection(self):
        self.assert_relay_receipt(False)

    def test_nested_request_after_stop_does_not_reset_session(self):
        self.assert_relay_receipt(True)
