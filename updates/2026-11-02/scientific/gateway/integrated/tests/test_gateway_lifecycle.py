# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# GW-ASYNC0 gateway acceptance tests (invariants I1-I10). Design: Coda (Codex Lily) with Richard
# Pemberton; invariant table: truncated Claude Fable 5.1 contribution; tests: Claude (Anthropic),
# coordinated by Red, 2026-11. Written statically; not executed by the author.
"""Gateway-level acceptance tests for the GW-ASYNC0 lifecycle in interface.py."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from first_leaf import canonical
from interface import (ADMITTED_PENDING, CANCELLED_BEFORE_DISPATCH, DISPATCHED, GATEWAY_SCHEMA,
                       LEGACY_EXECUTION_STATUS, REJECTED, STOP_ACKNOWLEDGED, UNKNOWN_OUTCOME,
                       VERIFIED_FAILURE, VERIFIED_SIMULATOR_TRANSITION, Gateway, check_json_depth,
                       migrate_legacy_gateway, parse_request)


def request(**changes):
    value = {'schema': 'stage.action.v1', 'request_id': 'r0', 'session_id': 'test',
             'body_revision': 'planar-v1', 'sequence': 0, 'observation_id': 'o0',
             'expires_tick': 2, 'action': 'k0'}
    value.update(changes)
    return canonical(value)


def snapshot(g):
    return json.loads(canonical(asdict(g)))


def clock(g):
    return (g.sequence, g.tick, g.observation_id)


def admitted():
    g = Gateway('test'); g.admit(request()); return g

def dispatched():
    g = admitted(); g.mark_dispatched('r0'); return g

def unknown():
    g = dispatched(); g.mark_unknown('r0', 'outcome not observed'); return g

def verified():
    g = dispatched(); g.record_execution('r0', 'k0'); return g

def failed():
    g = dispatched(); g.record_failure('r0', 'simulated known failure'); return g

def cancelled():
    g = admitted(); g.admit(request(request_id='stop', action='stop')); return g


class DispatchBoundaryTests(unittest.TestCase):
    def test_one_in_flight_blocks_distinct_requests_in_every_in_flight_state(self):  # I1
        for make, status in ((admitted, ADMITTED_PENDING), (dispatched, DISPATCHED), (unknown, UNKNOWN_OUTCOME)):
            with self.subTest(status=status):
                g = make(); before = snapshot(g)
                r = g.admit(request(request_id='r1', action='k1'))
                self.assertFalse(r['admitted']); self.assertFalse(r['dispatch'])
                self.assertEqual(r['reason'], 'command_pending'); self.assertEqual(r['execution_status'], REJECTED)
                self.assertEqual(g.active_request_id, 'r0')
                self.assertEqual(g.cache['r0']['execution_status'], status)
                self.assertEqual(clock(g), (0, 0, 'o0'))
                after = snapshot(g); del after['cache']['r1']
                self.assertEqual(after, before)

    def test_record_execution_requires_explicit_dispatch(self):  # I2
        g = admitted(); before = snapshot(g)
        with self.assertRaises(ValueError): g.record_execution('r0', 'k0')
        with self.assertRaises(ValueError): g.record_failure('r0', 'too early')
        with self.assertRaises(ValueError): g.mark_unknown('r0', 'too early')
        self.assertEqual(snapshot(g), before)
        view = g.mark_dispatched('r0')
        self.assertEqual(view['execution_status'], DISPATCHED); self.assertFalse(view['dispatch'])
        self.assertFalse(g.cache['r0']['dispatch'])
        self.assertEqual(g.active_request_id, 'r0'); self.assertEqual(clock(g), (0, 0, 'o0'))
        g.record_execution('r0', 'k0'); self.assertEqual(clock(g), (1, 1, 'o1'))

    def test_mark_dispatched_consumes_authorization_once(self):  # I2
        g = dispatched()
        with self.assertRaises(ValueError): g.mark_dispatched('r0')
        with self.assertRaises(ValueError): g.mark_dispatched('missing')
        self.assertEqual(g.cache['r0']['execution_status'], DISPATCHED)
        rejected = g.admit(request(request_id='r1', action='k1'))
        self.assertEqual(rejected['execution_status'], REJECTED)
        with self.assertRaises(ValueError): g.mark_dispatched('r1')  # rejected receipts are never dispatchable
        g.record_execution('r0', 'k0')
        with self.assertRaises(ValueError): g.mark_dispatched('r0')  # resolved receipts are final
        with self.assertRaises(ValueError): g.record_execution('r0', 'k0')
        self.assertEqual(clock(g), (1, 1, 'o1'))

    def test_verified_transition_alone_advances_and_releases(self):  # I3
        g = verified(); r = g.cache['r0']
        self.assertEqual(r['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertEqual(r['executed_action'], 'k0'); self.assertFalse(r['dispatch'])
        self.assertIsNone(g.active_request_id); self.assertEqual(clock(g), (1, 1, 'o1'))
        stale = g.admit(request(request_id='r2'))
        self.assertEqual(stale['reason'], 'sequence_mismatch')
        fresh = g.admit(request(request_id='r1', sequence=1, observation_id='o1', expires_tick=3))
        self.assertTrue(fresh['admitted']); self.assertTrue(fresh['dispatch'])
        self.assertEqual(g.active_request_id, 'r1')

    def test_known_failure_releases_slot_without_advance(self):  # I3, I4
        g = dispatched()
        with self.assertRaises(ValueError): g.record_failure('r0', '   ')  # a blank reason is not evidence
        self.assertEqual(g.cache['r0']['execution_status'], DISPATCHED)
        view = g.record_failure('r0', 'simulated known failure')
        self.assertEqual(view['execution_status'], VERIFIED_FAILURE)
        self.assertEqual(view['failure_reason'], 'simulated known failure'); self.assertFalse(view['dispatch'])
        self.assertNotIn('executed_action', view)
        self.assertIsNone(g.active_request_id); self.assertEqual(clock(g), (0, 0, 'o0'))
        retry = g.admit(request(request_id='r1'))  # the same frame is still current
        self.assertTrue(retry['dispatch']); self.assertEqual(g.active_request_id, 'r1')
        with self.assertRaises(ValueError): g.record_failure('r0', 'again')
        with self.assertRaises(ValueError): g.record_execution('r0', 'k0')


class UnknownOutcomeTests(unittest.TestCase):  # I4
    def test_unknown_outcome_retains_slot_and_blocks_everything_but_resolution(self):
        g = dispatched()
        with self.assertRaises(ValueError): g.mark_unknown('r0', '')
        view = g.mark_unknown('r0', 'outcome not observed')
        self.assertEqual(view['execution_status'], UNKNOWN_OUTCOME)
        self.assertEqual(view['unknown_reason'], 'outcome not observed'); self.assertFalse(view['dispatch'])
        self.assertEqual(g.active_request_id, 'r0')
        self.assertEqual(g.admit(request(request_id='r1', action='k1'))['reason'], 'command_pending')
        for attempt in (lambda: g.record_execution('r0', 'k0'), lambda: g.record_failure('r0', 'late'),
                        lambda: g.mark_unknown('r0', 'twice'), lambda: g.mark_dispatched('r0')):
            with self.assertRaises(ValueError): attempt()
        self.assertEqual(g.cache['r0']['execution_status'], UNKNOWN_OUTCOME)
        self.assertEqual(clock(g), (0, 0, 'o0'))

    def test_resolving_as_transition_needs_the_explicit_matching_action(self):
        g = unknown()
        with self.assertRaises(ValueError): g.resolve_unknown('r0', VERIFIED_SIMULATOR_TRANSITION)
        with self.assertRaises(ValueError): g.resolve_unknown('r0', VERIFIED_SIMULATOR_TRANSITION, 'k1')
        self.assertEqual(g.cache['r0']['execution_status'], UNKNOWN_OUTCOME); self.assertEqual(clock(g), (0, 0, 'o0'))
        view = g.resolve_unknown('r0', VERIFIED_SIMULATOR_TRANSITION, 'k0')
        self.assertEqual(view['execution_status'], VERIFIED_SIMULATOR_TRANSITION)
        self.assertEqual(view['executed_action'], 'k0'); self.assertEqual(view['resolved_from'], UNKNOWN_OUTCOME)
        self.assertIsNone(g.active_request_id); self.assertEqual(clock(g), (1, 1, 'o1'))

    def test_resolving_as_failure_carries_no_action_and_does_not_advance(self):
        g = unknown()
        with self.assertRaises(ValueError): g.resolve_unknown('r0', VERIFIED_FAILURE, 'k0')
        view = g.resolve_unknown('r0', VERIFIED_FAILURE)
        self.assertEqual(view['execution_status'], VERIFIED_FAILURE); self.assertEqual(view['resolved_from'], UNKNOWN_OUTCOME)
        self.assertNotIn('executed_action', view); self.assertIsNone(g.active_request_id)
        self.assertEqual(clock(g), (0, 0, 'o0'))
        self.assertTrue(g.admit(request(request_id='r1'))['dispatch'])
        with self.assertRaises(ValueError): g.resolve_unknown('r0', VERIFIED_FAILURE)

    def test_resolution_accepts_only_the_two_verified_outcomes(self):
        g = unknown(); before = snapshot(g)
        for outcome in (CANCELLED_BEFORE_DISPATCH, ADMITTED_PENDING, DISPATCHED, UNKNOWN_OUTCOME,
                        REJECTED, STOP_ACKNOWLEDGED, 'verified', ''):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValueError): g.resolve_unknown('r0', outcome)
        self.assertEqual(snapshot(g), before)


class DuplicateTests(unittest.TestCase):  # I5
    def test_duplicate_views_never_change_state_or_authorize_dispatch(self):
        base = request()
        cases = [
            (ADMITTED_PENDING, base, lambda g: g.admit(base)),
            (DISPATCHED, base, lambda g: (g.admit(base), g.mark_dispatched('r0'))),
            (UNKNOWN_OUTCOME, base, lambda g: (g.admit(base), g.mark_dispatched('r0'), g.mark_unknown('r0', 'x'))),
            (VERIFIED_SIMULATOR_TRANSITION, base,
             lambda g: (g.admit(base), g.mark_dispatched('r0'), g.record_execution('r0', 'k0'))),
            (VERIFIED_FAILURE, base, lambda g: (g.admit(base), g.mark_dispatched('r0'), g.record_failure('r0', 'x'))),
            (CANCELLED_BEFORE_DISPATCH, base,
             lambda g: (g.admit(base), g.admit(request(request_id='stop', action='stop')))),
            (REJECTED, request(observation_id='old'), lambda g: g.admit(request(observation_id='old'))),
            (STOP_ACKNOWLEDGED, request(action='stop'), lambda g: g.admit(request(action='stop'))),
        ]
        for status, raw, build in cases:
            with self.subTest(status=status):
                g = Gateway('test'); build(g); before = snapshot(g)
                for _ in range(2):
                    dup = g.admit(raw)
                    self.assertTrue(dup['duplicate']); self.assertFalse(dup['dispatch'])
                    self.assertEqual(dup['execution_status'], status)
                    self.assertEqual(dup['request_sha256'], g.cache['r0']['request_sha256'])
                self.assertFalse(g.cache['r0']['duplicate'], 'the cache stores originals')
                self.assertEqual(snapshot(g), before)

    def test_same_id_with_different_content_raises_without_state_change(self):
        for make in (admitted, dispatched, verified, cancelled):
            with self.subTest(state=make.__name__):
                g = make(); before = snapshot(g)
                with self.assertRaises(ValueError): g.admit(request(action='k1'))
                with self.assertRaises(ValueError): g.admit(request(expires_tick=3))
                self.assertEqual(snapshot(g), before)


class StopTests(unittest.TestCase):  # I6, I7
    def test_stop_cancels_only_an_undispatched_admission(self):
        g = admitted()
        stop = g.admit(request(request_id='stop', action='stop', observation_id='old', expires_tick=0))
        self.assertTrue(stop['admitted']); self.assertIsNone(stop['reason']); self.assertFalse(stop['dispatch'])
        self.assertTrue(stop['stop_latched']); self.assertEqual(stop['execution_status'], STOP_ACKNOWLEDGED)
        self.assertEqual(stop['cancelled_request_id'], 'r0'); self.assertNotIn('outstanding_request_id', stop)
        r = g.cache['r0']
        self.assertEqual(r['execution_status'], CANCELLED_BEFORE_DISPATCH)
        self.assertTrue(r['admitted'], 'the admission remains historical fact'); self.assertFalse(r['dispatch'])
        self.assertTrue(r['stop_latched']); self.assertEqual(r['cancelled_by'], 'stop')
        self.assertNotIn('executed_action', r)
        self.assertTrue(g.stopped); self.assertIsNone(g.active_request_id); self.assertEqual(clock(g), (0, 0, 'o0'))
        for attempt in (lambda: g.mark_dispatched('r0'), lambda: g.record_execution('r0', 'k0'),
                        lambda: g.record_failure('r0', 'x')):
            with self.assertRaises(ValueError): attempt()
        self.assertEqual(g.admit(request(request_id='r1'))['reason'], 'stop_latched')

    def test_stop_after_dispatch_reports_outstanding_work_and_never_relabels_it(self):
        for make, status in ((dispatched, DISPATCHED), (unknown, UNKNOWN_OUTCOME)):
            with self.subTest(status=status):
                g = make()
                stop = g.admit(request(request_id='stop', action='stop'))
                self.assertEqual(stop['execution_status'], STOP_ACKNOWLEDGED); self.assertTrue(stop['stop_latched'])
                self.assertEqual(stop['outstanding_request_id'], 'r0'); self.assertEqual(stop['outstanding_status'], status)
                self.assertNotIn('cancelled_request_id', stop)
                self.assertEqual(g.cache['r0']['execution_status'], status, 'dispatched work is not relabelled')
                self.assertNotIn('cancelled_by', g.cache['r0'])
                self.assertTrue(g.stopped); self.assertEqual(g.active_request_id, 'r0')
                self.assertEqual(clock(g), (0, 0, 'o0'))
                self.assertEqual(g.admit(request(request_id='r1', action='k1'))['reason'], 'stop_latched')

    def test_stop_stays_latched_after_outstanding_work_resolves(self):
        g = dispatched(); g.admit(request(request_id='stop', action='stop'))
        view = g.record_execution('r0', 'k0')  # the evidence says the dispatched step happened
        self.assertEqual(view['execution_status'], VERIFIED_SIMULATOR_TRANSITION); self.assertTrue(view['stop_latched'])
        self.assertEqual(clock(g), (1, 1, 'o1')); self.assertTrue(g.stopped); self.assertIsNone(g.active_request_id)
        self.assertEqual(g.admit(request(request_id='r1', sequence=1, observation_id='o1', expires_tick=3))['reason'],
                         'stop_latched')
        h = unknown(); h.admit(request(request_id='stop', action='stop'))
        h.resolve_unknown('r0', VERIFIED_FAILURE)
        self.assertTrue(h.stopped); self.assertEqual(clock(h), (0, 0, 'o0')); self.assertIsNone(h.active_request_id)
        self.assertEqual(h.admit(request(request_id='r1'))['reason'], 'stop_latched')
        self.assertTrue(h.admit(request(request_id='stop2', action='stop'))['stop_latched'])

    def test_stop_is_idempotent_and_distinct_from_rejection(self):  # I7
        g = Gateway('test')
        first = g.admit(request(request_id='s1', action='stop'))
        second = g.admit(request(request_id='s2', action='stop', observation_id='old'))
        for stop in (first, second):
            self.assertEqual(stop['execution_status'], STOP_ACKNOWLEDGED)
            self.assertTrue(stop['admitted']); self.assertIsNone(stop['reason']); self.assertFalse(stop['dispatch'])
            self.assertFalse(stop['duplicate']); self.assertNotIn('cancelled_request_id', stop)
        rejected = g.admit(request(request_id='r1'))
        self.assertEqual(rejected['execution_status'], REJECTED); self.assertFalse(rejected['admitted'])
        self.assertEqual(rejected['reason'], 'stop_latched'); self.assertFalse(rejected['dispatch'])
        self.assertTrue(rejected['stop_latched'])
        self.assertIsNone(g.active_request_id); self.assertEqual(clock(g), (0, 0, 'o0'))
        dup = g.admit(request(request_id='s1', action='stop'))
        self.assertTrue(dup['duplicate']); self.assertEqual(dup['execution_status'], STOP_ACKNOWLEDGED)

    def test_foreign_stops_do_nothing(self):
        g = admitted()
        for changes in ({'session_id': 'foreign'}, {'body_revision': 'foreign'}):
            with self.subTest(changes=changes):
                r = g.admit(request(request_id='foreign-' + next(iter(changes)), action='stop', **changes))
                self.assertEqual(r['execution_status'], REJECTED); self.assertFalse(r['admitted'])
                self.assertIn(r['reason'], ('session_mismatch', 'body_mismatch')); self.assertFalse(r['stop_latched'])
        self.assertFalse(g.stopped); self.assertEqual(g.active_request_id, 'r0')
        self.assertEqual(g.cache['r0']['execution_status'], ADMITTED_PENDING); self.assertTrue(g.cache['r0']['dispatch'])
        g.mark_dispatched('r0'); g.record_execution('r0', 'k0'); self.assertEqual(clock(g), (1, 1, 'o1'))

    def test_stop_preserves_verified_earlier_transition(self):
        g = verified(); earlier = copy.deepcopy(g.cache['r0'])
        g.admit(request(request_id='r1', sequence=1, observation_id='o1', expires_tick=3))
        stop = g.admit(request(request_id='stop', action='stop'))
        self.assertEqual(stop['cancelled_request_id'], 'r1')
        self.assertEqual(g.cache['r0'], earlier)
        self.assertEqual(g.cache['r1']['execution_status'], CANCELLED_BEFORE_DISPATCH)
        self.assertEqual(clock(g), (1, 1, 'o1')); self.assertIsNone(g.active_request_id)


class SerializationTests(unittest.TestCase):  # I8
    def test_round_trip_preserves_in_flight_receipts_and_active_identity(self):
        for make, status in ((admitted, ADMITTED_PENDING), (dispatched, DISPATCHED), (unknown, UNKNOWN_OUTCOME)):
            with self.subTest(status=status):
                g = make(); state = snapshot(g)
                restored = Gateway.restore(state)
                self.assertEqual(snapshot(restored), state)
                self.assertEqual(restored.active_request_id, 'r0')
                self.assertEqual(restored.in_flight()['execution_status'], status)
                self.assertEqual(restored.admit(request(request_id='r1', action='k1'))['reason'], 'command_pending')
        g = Gateway.restore(snapshot(dispatched()))
        g.record_execution('r0', 'k0'); self.assertEqual(clock(g), (1, 1, 'o1'))

    def test_round_trip_of_resolved_and_stopped_gateways(self):
        for make in (verified, failed, cancelled):
            with self.subTest(state=make.__name__):
                g = make(); state = snapshot(g)
                restored = Gateway.restore(state)
                self.assertEqual(snapshot(restored), state); self.assertIsNone(restored.in_flight())
                with self.assertRaises(ValueError): restored.record_execution('r0', 'k0')
                self.assertEqual(clock(restored), clock(g))
        restored = Gateway.restore(snapshot(cancelled()))
        self.assertTrue(restored.stopped)
        self.assertEqual(restored.admit(request())['execution_status'], CANCELLED_BEFORE_DISPATCH)
        self.assertEqual(restored.admit(request(request_id='r1'))['reason'], 'stop_latched')

    def test_restore_refuses_inconsistent_state_and_never_repairs(self):
        def active_points_at_resolved(s): s['active_request_id'] = 'r0'
        def in_flight_without_identity(s): s['active_request_id'] = None
        def two_in_flight(s): s['cache']['r1'] = dict(s['cache']['r0'], request_id='r1')
        def stopped_with_undispatched(s): s['stopped'] = True
        def stale_authorization(s): s['cache']['r0']['dispatch'] = True
        def stored_duplicate(s): s['cache']['r0']['duplicate'] = True
        def phantom_execution(s): s['cache']['r0']['executed_action'] = 'k0'
        def substituted_action(s): s['cache']['r0']['executed_action'] = 'k1'
        def legacy_status(s): s['cache']['r0']['execution_status'] = LEGACY_EXECUTION_STATUS
        def placeholder_status(s): s['cache']['r0']['execution_status'] = 'cancelled_pending_by_stop'
        def stop_as_action(s): s['cache']['r0']['requested_action'] = 'stop'
        def wrong_schema(s): s['schema'] = 'stage.gateway.v1'
        def missing_key(s): del s['active_request_id']
        def extra_key(s): s['pending'] = True
        cases = [(verified, active_points_at_resolved), (dispatched, in_flight_without_identity),
                 (admitted, two_in_flight), (admitted, stopped_with_undispatched),
                 (dispatched, stale_authorization), (verified, stored_duplicate),
                 (dispatched, phantom_execution), (verified, substituted_action),
                 (admitted, legacy_status), (cancelled, placeholder_status), (admitted, stop_as_action),
                 (verified, wrong_schema), (verified, missing_key), (verified, extra_key)]
        for make, corrupt in cases:
            with self.subTest(corruption=corrupt.__name__):
                state = snapshot(make()); corrupt(state); frozen = copy.deepcopy(state)
                with self.assertRaises(ValueError): Gateway.restore(state)
                self.assertEqual(state, frozen, 'restoration must not repair the input')
        broken = snapshot(dispatched()); broken['active_request_id'] = None
        with self.assertRaises(ValueError): Gateway(**broken)  # the constructor validates too


class ParserBoundsTests(unittest.TestCase):  # I9
    def test_deep_nesting_is_a_bounded_value_error(self):
        deep = b'{"x":' + b'[' * 6000 + b'0' + b']' * 6000 + b'}'
        self.assertLess(len(deep), 16384)
        with self.assertRaises(ValueError) as ctx: parse_request(deep)
        self.assertIn('JSON nesting', str(ctx.exception))
        check_json_depth('[' * 32 + ']' * 32)  # at the bound: allowed
        with self.assertRaises(ValueError): check_json_depth('[' * 33 + ']' * 33)
        with self.assertRaises(ValueError): check_json_depth('{"a":' * 33 + '0' + '}' * 33)

    def test_brackets_inside_strings_do_not_count(self):
        check_json_depth('{"a":"' + '[' * 100 + '{' * 100 + '"}')
        check_json_depth('{"a":"\\"' + '[' * 100 + '"}')
        with self.assertRaises(ValueError) as ctx: parse_request(b'{"a":"' + b'[' * 100 + b'"}')
        self.assertNotIn('JSON nesting', str(ctx.exception))  # schema rejection, not the depth bound

    def test_prior_strictness_checks_retained(self):
        self.assertEqual(parse_request(request())['action'], 'k0')
        self.assertEqual(parse_request(request().decode())['request_id'], 'r0')
        bad = [request(shell='rm'), request(action='run_shell'), request(sequence=True), request(sequence=-1),
               request(sequence=2 ** 53), request(request_id=''), request(request_id='x' * 129),
               request(schema='stage.action.v0'), request().replace(b'{', b'{"sequence":0,', 1),
               request().replace(b'"sequence":0', b'"sequence":NaN'),
               request().replace(b'"sequence":0', b'"sequence":0.0'), b' ' * 16385, b'[]', b'{bad', b'']
        for raw in bad:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ValueError): parse_request(raw)
        with self.assertRaises(ValueError): parse_request(123)


def legacy_receipt(rid, action, **over):
    base = {'request_id': rid, 'request_sha256': '0' * 64, 'requested_action': action, 'admitted': True,
            'reason': None, 'duplicate': False, 'dispatch': False, 'stop_latched': False,
            'execution_status': LEGACY_EXECUTION_STATUS}
    base.update(over)
    return base


def legacy_state(cache, **over):
    state = {'session_id': 'test', 'body_revision': 'planar-v1', 'sequence': 1, 'tick': 1,
             'observation_id': 'o1', 'stopped': False, 'cache': cache}
    state.update(over)
    return state


class LegacyMigrationTests(unittest.TestCase):  # I10
    def test_explicit_migration_classifies_unambiguous_legacy_receipts(self):
        cache = {'r0': legacy_receipt('r0', 'k0', dispatch=True, execution_status=VERIFIED_SIMULATOR_TRANSITION,
                                      executed_action='k0'),
                 'r1': legacy_receipt('r1', 'k1', admitted=False, reason='sequence_mismatch'),
                 'stop': legacy_receipt('stop', 'stop', stop_latched=True),
                 'r2': legacy_receipt('r2', 'k2', admitted=False, reason='stop_latched', stop_latched=True)}
        legacy = legacy_state(cache, stopped=True); frozen = copy.deepcopy(legacy)
        with self.assertRaises(ValueError): Gateway.restore(legacy)
        with self.assertRaises(ValueError): Gateway(**legacy)
        migrated = migrate_legacy_gateway(legacy)
        self.assertEqual(legacy, frozen, 'migration must not mutate its input')
        self.assertEqual(migrated['schema'], GATEWAY_SCHEMA); self.assertIsNone(migrated['active_request_id'])
        statuses = {k: v['execution_status'] for k, v in migrated['cache'].items()}
        self.assertEqual(statuses, {'r0': VERIFIED_SIMULATOR_TRANSITION, 'r1': REJECTED,
                                    'stop': STOP_ACKNOWLEDGED, 'r2': REJECTED})
        self.assertFalse(migrated['cache']['r0']['dispatch'])
        g = Gateway.restore(migrated)
        self.assertTrue(g.stopped); self.assertEqual(clock(g), (1, 1, 'o1'))
        self.assertEqual(g.admit(request(request_id='r3', sequence=1, observation_id='o1', expires_tick=3))['reason'],
                         'stop_latched')

    def test_migration_fails_closed_on_admitted_but_unrecorded_receipt(self):
        cache = {'r0': legacy_receipt('r0', 'k0', dispatch=True)}  # admitted for dispatch, outcome never recorded
        legacy = legacy_state(cache, sequence=0, tick=0, observation_id='o0'); frozen = copy.deepcopy(legacy)
        with self.assertRaises(ValueError) as ctx: migrate_legacy_gateway(legacy)
        self.assertIn('Ambiguous', str(ctx.exception)); self.assertEqual(legacy, frozen)

    def test_migration_refuses_unclassifiable_and_foreign_states(self):
        cases = {
            'placeholder_status': legacy_state(
                {'r0': legacy_receipt('r0', 'k0', execution_status='cancelled_pending_by_stop')}),
            'admitted_action_without_dispatch': legacy_state({'r0': legacy_receipt('r0', 'k0')}),
            'inconsistent_verified': legacy_state({'r0': legacy_receipt(
                'r0', 'k0', dispatch=True, execution_status=VERIFIED_SIMULATOR_TRANSITION, executed_action='k1')}),
            'already_v2': snapshot(verified()),
            'not_a_dict': [],
        }
        for name, state in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError): migrate_legacy_gateway(state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
