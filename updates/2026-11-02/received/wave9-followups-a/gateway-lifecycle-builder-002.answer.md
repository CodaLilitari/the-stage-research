# GW-ASYNC0 implementation — continuation (static contribution, not executed)

**Status.** Everything below is static reasoning against the verbatim bundle; I executed nothing and read no files beyond the sources quoted in the request. Every "passes"/"fails" statement is a traced prediction for Red to confirm or refute in the sandbox. `src/interface.py` is treated as fixed; I found no blocking defect in it, so no diff is proposed. Credits: original interface/relay/simulator/tests — Lilitari (Lily), via ChatGPT; lifecycle requirements — Lily's review; design and `interface.py` lifecycle — Coda (Codex Lily) with Richard (Andrei) Pemberton; invariant table, intentional-update list and `interface.py` text — the truncated Claude Fable 5.1 contribution; this relay completion, the lifecycle tests and the note — Claude (Anthropic), coordinated by Red. `first_leaf.py`, `inputs/protocol.json`, `tests/test_relay.py` (sha256 b4ea09e1…) and the frozen `tests/test_gateway_regressions_v2.py` are untouched.

## 1. `src/relay.py` (complete)

FILE: src/relay.py
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Original relay: Lilitari (Lily), via ChatGPT.
# GW-ASYNC0 explicit dispatch/outcome recording, validated restore, pre-commit failure handling
# and explicit legacy migration: Coda (Codex Lily), collaborating with Richard Pemberton, 2026-11.
# Relay body completed from the truncated Claude Fable 5.1 draft: Claude (Anthropic), coordinated by
# Red, 2026-11. MIT License; see LICENSE.
"""Private, local, file-relayed model-action interface for the FL1 point body.

No model calls, network, shell actions, or physical hardware. Only packet.json
and MODEL_BRIEF.md should be supplied to a candidate. private_state.json contains
simulator truth and future random draws, and belongs to the operator/evaluator.
A trusted single writer is required. Atomic state replacement is the virtual
commit point; export files are regenerable views, not independent witnesses.

Lifecycle (GW-ASYNC0): within one writer-locked transaction the relay admits a
request, explicitly marks dispatch, computes the candidate simulator transition
without touching the loaded state, records either the verified transition or the
known failure, and commits gateway and simulator state in one atomic replacement.
There is no external actuator: an exception or crash before the replacement leaves
no record and implies no action; an exception after the replacement leaves a
committed state whose export views are regenerated with `export`, never by
replaying a transition. Legacy stage.relay.private.v1 state is refused until the
explicit `migrate` command converts it (and fails closed on ambiguous receipts).

This relay never produces an unknown outcome itself (gateway and simulator commit
together). A restored in-flight receipt, which can only come from an operator edit,
is exposed in the packet as `active_request`, blocks new actions (`command_pending`)
and blocks `next-episode` until it is resolved with the Gateway API.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import uuid
from first_leaf import body_vectors, canonical, fixture, load_protocol
from interface import ACTIONS, VERIFIED_SIMULATOR_TRANSITION, Gateway, migrate_legacy_gateway

STATE_SCHEMA = 'stage.relay.private.v2'
LEGACY_STATE_SCHEMA = 'stage.relay.private.v1'
LEGACY_BACKUP_NAME = 'private_state.legacy-v1.json'


def atomic(path: Path, data: bytes, private: bool = False) -> None:
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600 if private else 0o644)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


@contextmanager
def writer_lock(directory: Path):
    lock = directory / 'writer.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('Existing writer lock: check for a live writer or interrupted operation before recovery.')
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def sample(s):
    noise = s['fixture']['unit_noise'][s['episode']][s['tick']]
    c = s['cfg']['observations']
    return {'episode': s['episode'], 'sample_tick': s['tick'],
            'p': [s['p'][j] + noise[j] * c['position_noise_scale'] for j in range(2)],
            'v': [s['v'][j] + noise[j + 2] * c['velocity_noise_scale'] for j in range(2)]}


def candidate_transition(s, action):
    """Pure candidate step: the next simulator state for `action`, computed from `s` without
    mutating it. The formulas are the original relay's, moved out of the transaction body."""
    cfg = s['cfg']
    a = ACTIONS.index(action)
    b = body_vectors(cfg, s['fixture'], s['episode'], cfg['profiles']['primary'])
    v = [.75 * s['v'][j] + b[a][j] for j in range(2)]
    p = [s['p'][j] + .1 * v[j] for j in range(2)]
    if not all(math.isfinite(x) for x in v + p):
        raise ArithmeticError('non-finite candidate simulator state')
    probe = dict(s, p=p, v=v, tick=s['tick'] + 1)  # shallow copy: sample() only reads it
    return {'p': p, 'v': v, 'tick': probe['tick'], 'sample': sample(probe)}


def packet(s):
    g = s['gateway']
    sensor_tick = max(0, s['tick'] - s['cfg']['profiles']['primary']['delay'])
    active_id = g['active_request_id']
    return {'schema': 'stage.observation.v1', 'session_id': g['session_id'],
            'body_revision': g['body_revision'], 'sequence': g['sequence'],
            'observation_id': g['observation_id'], 'dispatch_tick': g['tick'],
            'sensor': s['samples'][sensor_tick], 'episode': s['episode'],
            'goal': s['fixture']['goals'][s['episode']],
            'known_dynamics': {'dt': .1, 'velocity_retention': .75},
            'sensor_contract': {'position_noise_bound': .01, 'velocity_noise_bound': .03,
                                'delay_ticks': 2, 'actuator_mapping': 'unknown and may change'},
            'actions': list(ACTIONS), 'stopped': g['stopped'],
            'active_request': None if active_id is None else dict(g['cache'][active_id]),
            'episode_complete': s['tick'] >= s['cfg']['steps_per_episode'],
            'recent_events': s['public_events'][-12:],
            'request_template': {'schema': 'stage.action.v1', 'request_id': 'REPLACE_WITH_UNIQUE_ID',
                'session_id': g['session_id'], 'body_revision': g['body_revision'],
                'sequence': g['sequence'], 'observation_id': g['observation_id'],
                'expires_tick': g['tick'] + 2, 'action': 'coast'}}


def export(s, directory):
    atomic(directory / 'packet.json', json.dumps(packet(s), indent=2).encode() + b'\n')
    atomic(directory / 'events.jsonl', b''.join(canonical(r) + b'\n' for r in s['public_events']))


def load_state(path: Path):
    """Load committed private state and strictly restore its gateway.

    Legacy v1 state is refused with a pointer to the explicit `migrate` command; nothing is
    repaired here. Gateway.restore re-validates every receipt and the active identity."""
    s = json.loads(path.read_bytes())
    schema = s.get('schema') if isinstance(s, dict) else None
    if schema != STATE_SCHEMA:
        hint = ' Run the explicit `migrate` command first.' if schema == LEGACY_STATE_SCHEMA else ''
        raise ValueError(f'Unsupported private state schema {schema!r}; expected {STATE_SCHEMA!r}.{hint}')
    return s, Gateway.restore(s['gateway'])


def init(directory, seed, actor):
    directory.mkdir(parents=True, exist_ok=True)
    with writer_lock(directory):
        path = directory / 'private_state.json'
        if path.exists():
            raise ValueError('Session already exists; refusing overwrite')
        cfg = load_protocol()
        s = {'schema': STATE_SCHEMA, 'actor_label_operator_reported': actor,
             'cfg': cfg, 'fixture': fixture(seed, cfg), 'episode': 0, 'tick': 0,
             'p': [0., 0.], 'v': [0., 0.], 'public_events': [],
             'gateway': asdict(Gateway('relay-' + uuid.uuid4().hex))}
        s['samples'] = [sample(s)]
        atomic(path, canonical(s) + b'\n', True)
        export(s, directory)
    return packet(s)


def _advance_episode(s, g, event):
    cfg = s['cfg']
    if g.active_request_id is not None:
        raise ValueError(f'Cannot advance while receipt {g.active_request_id!r} is in flight')
    if g.stopped or s['tick'] != cfg['steps_per_episode']:
        raise ValueError('Only an unstopped completed episode can advance')
    if s['episode'] + 1 >= cfg['episodes']:
        raise ValueError('No further episode in this protocol')
    # Make the final delayed samples available before reset.
    event.update({'event': 'operator_episode_reset',
                  'final_sensor_samples': s['samples'][-3:],
                  'operator_intervention': True})
    s['episode'] += 1
    s['tick'], s['p'], s['v'] = 0, [0., 0.], [0., 0.]
    s['samples'] = [sample(s)]
    g.observation_id = f'o{g.tick}-episode{s["episode"]}'


def _step(s, g, event, request_bytes):
    """Admit; for an authorized dispatch, mark dispatch, compute the pure candidate step and
    record the outcome. Nothing here touches the disk; `transact` commits the result."""
    block = 'episode_complete' if s['tick'] >= s['cfg']['steps_per_episode'] else None
    try:
        receipt = g.admit(request_bytes, block_reason=block)
    except (ValueError, UnicodeError) as exc:
        event.update({'event': 'rejected_invalid_request', 'reason': str(exc), 'executed': False})
        return
    event.update({'event': 'action_receipt', 'receipt': receipt, 'executed': False})
    if not receipt['dispatch']:
        return  # duplicate view, rejection or stop acknowledgement: nothing to dispatch
    rid, action = receipt['request_id'], receipt['requested_action']
    g.mark_dispatched(rid)  # explicit boundary: the single authorization is consumed before computing
    try:
        step = candidate_transition(s, action)
    except Exception as exc:  # pure computation failed before anything was written: a known failure
        event['receipt'] = g.record_failure(
            rid, f'pre-commit computation failure: {type(exc).__name__}: {exc}')
        return
    event['receipt'] = g.record_execution(rid, action)
    s['p'], s['v'], s['tick'] = step['p'], step['v'], step['tick']
    s['samples'].append(step['sample'])
    event.update({'executed': event['receipt']['execution_status'] == VERIFIED_SIMULATOR_TRANSITION,
                  'executed_transition_source_tick': s['tick'] - 1,
                  'observed_sensor': s['samples'][max(0, s['tick'] - 2)]})


def _export_after_commit(s, directory):
    try:
        export(s, directory)
    except Exception as exc:
        raise RuntimeError('Simulation state is committed but regenerating the export views failed; '
                           'run `export` to rebuild packet.json and events.jsonl. Never replay the step.') from exc


def transact(directory, request_bytes=None, advance=False):
    with writer_lock(directory):
        path = directory / 'private_state.json'
        s, g = load_state(path)
        event = {'actor_label_operator_reported': s['actor_label_operator_reported'],
                 'episode': s['episode'], 'source_dispatch_tick': g.tick}
        if advance:
            _advance_episode(s, g, event)
        else:
            if request_bytes is None:
                raise ValueError('Missing request')
            _step(s, g, event, request_bytes)
        g.validate()  # the lifecycle left a consistent gateway, or nothing is written
        s['gateway'] = asdict(g)
        s['public_events'].append(event)
        # Nothing external is actuated. This replacement is the only commit point: an exception
        # before or inside it leaves no record and implies no action, so nothing is recorded for it.
        atomic(path, canonical(s) + b'\n', True)
        _export_after_commit(s, directory)
        return event


def regenerate_views(directory):
    """Rebuild packet.json and events.jsonl from the committed state. Never replays a step."""
    with writer_lock(directory):
        s, g = load_state(directory / 'private_state.json')
        export(s, directory)
        return {'exported': True, 'sequence': g.sequence, 'active_request_id': g.active_request_id}


def migrate(directory):
    """Explicit one-way migration of stage.relay.private.v1 state.

    Fails closed: an admitted-but-unrecorded legacy receipt aborts before anything is written.
    The legacy file content is kept as a backup that is never overwritten."""
    with writer_lock(directory):
        path = directory / 'private_state.json'
        raw = path.read_bytes()
        s = json.loads(raw)
        schema = s.get('schema') if isinstance(s, dict) else None
        if schema != LEGACY_STATE_SCHEMA:
            raise ValueError(f'Only {LEGACY_STATE_SCHEMA!r} state can be migrated; found {schema!r}')
        gateway = migrate_legacy_gateway(s['gateway'])  # raises on ambiguity; input is not mutated
        migrated = dict(s, schema=STATE_SCHEMA, gateway=gateway)
        migrated['public_events'] = list(s['public_events']) + [{
            'actor_label_operator_reported': s['actor_label_operator_reported'],
            'episode': s['episode'], 'source_dispatch_tick': gateway['tick'],
            'event': 'operator_state_migration', 'from_schema': LEGACY_STATE_SCHEMA,
            'to_schema': STATE_SCHEMA, 'operator_intervention': True, 'executed': False}]
        backup = directory / LEGACY_BACKUP_NAME
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)  # refuse to clobber an earlier backup
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        atomic(path, canonical(migrated) + b'\n', True)
        export(migrated, directory)
        return {'migrated': True, 'schema': STATE_SCHEMA, 'receipts': len(gateway['cache']),
                'backup': backup.name}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    start = sub.add_parser('init')
    start.add_argument('--directory', type=Path, required=True)
    start.add_argument('--seed', type=int, default=20000)
    start.add_argument('--actor-label', required=True)
    act = sub.add_parser('step')
    act.add_argument('--directory', type=Path, required=True)
    act.add_argument('--request', type=Path, required=True)
    for name in ['next-episode', 'export', 'migrate']:
        q = sub.add_parser(name)
        q.add_argument('--directory', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'init':
        result = init(args.directory, args.seed, args.actor_label)
    elif args.command == 'step':
        result = transact(args.directory, args.request.read_bytes())
    elif args.command == 'next-episode':
        result = transact(args.directory, advance=True)
    elif args.command == 'migrate':
        result = migrate(args.directory)
    else:
        result = regenerate_views(args.directory)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
```

## 2. New acceptance tests

FILE: tests/test_gateway_lifecycle.py
```python
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
```

FILE: tests/test_relay_lifecycle.py
```python
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
```

## 3. Intentionally updated old test file (complete)

Only `tests/test_stage.py` changes (four lines in `GatewayTests`, exactly the diff in the Fable partial answer). `tests/test_relay.py` is unchanged and `tests/test_gateway_regressions_v2.py` stays frozen as evidence.

FILE: tests/test_stage.py
```python
# Original tests: Lilitari (Lily), via ChatGPT. GW-ASYNC0 adaptation (explicit mark_dispatched before
# record_execution in four GatewayTests; rationale in docs/gateway_lifecycle_v1/MIGRATION_NOTE.md).
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
        g.mark_dispatched("r0")
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
        g = Gateway("test"); g.admit(request()); g.mark_dispatched("r0"); g.record_execution("r0", "k0")
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
        g = Gateway("test"); g.admit(request()); g.mark_dispatched("r0")  # otherwise passes for the weaker "not dispatched" reason
        with self.assertRaises(ValueError): g.record_execution("r0", "k1")

    def test_cannot_execute_twice(self):
        g = Gateway("test"); g.admit(request()); g.mark_dispatched("r0"); g.record_execution("r0", "k0")
        with self.assertRaises(ValueError): g.record_execution("r0", "k0")

if __name__ == '__main__': unittest.main(verbosity=2)
```

## 4. Migration / design note

FILE: docs/gateway_lifecycle_v1/MIGRATION_NOTE.md
```markdown
# GW-ASYNC0 relay completion: migration and design note

Prose: CC-BY-4.0. Code: MIT (see LICENSE). Static contribution by Claude (Anthropic), coordinated by Red,
completing the truncated Claude Fable 5.1 answer; design by Coda (Codex Lily) with Richard (Andrei) Pemberton;
original interface/relay/simulator/tests by Lilitari (Lily). Nothing here was executed by the author.

## What changed (relay)
- `transact` restores the gateway with `Gateway.restore` (strict) and runs admit -> `mark_dispatched` ->
  `candidate_transition` (pure, does not touch the loaded state) -> `record_execution` or `record_failure`
  -> `g.validate()` -> one atomic replacement of private_state.json -> export. Only the replacement commits.
- A computation exception before any write becomes `verified_failure` (slot released, no advance). An exception
  from the replacement itself propagates with nothing recorded (no false failure for an ambiguous replacement).
  An export exception after the replacement is wrapped in RuntimeError; recover with `export` (regenerates
  views from the committed state), never by stepping again — the original request replays as a duplicate.
- `episode_complete` is a genuine gateway rejection (`admit(..., block_reason='episode_complete')`), no longer
  a rewritten admission. `next-episode` refuses while a receipt is in flight.
- Packet gains one additive key, `active_request` (in-flight receipt view or null). Events gain `executed`
  on every event type; `rejected_invalid_request` keeps `executed: False`.
- Private state schema is `stage.relay.private.v2`. `stage.relay.private.v1` is refused by `step`,
  `next-episode` and `export` until the explicit `migrate` command converts it; migration fails closed on an
  admitted-but-unrecorded legacy receipt and on the v2-candidate placeholder `cancelled_pending_by_stop`,
  keeps the legacy bytes as `private_state.legacy-v1.json` (never overwritten) and appends an
  `operator_state_migration` event.
- The relay never produces `unknown_outcome` (gateway and simulator commit together). A restored in-flight
  receipt (operator edit) blocks actions (`command_pending`), blocks `next-episode`, is reported by stop as
  outstanding, and is exposed as `active_request`. Resolving it is a Gateway-API operator action.
- `next-episode` still rewrites `observation_id` to `o<tick>-episode<n>` without advancing sequence/tick, as
  in the original; this is an operator intervention, not a verified transition (unchanged behaviour).

## Intentional old-test updates
`tests/test_stage.py`: `mark_dispatched("r0")` inserted in `test_valid_request`,
`test_duplicate_suppresses_second_dispatch`, `test_cannot_execute_twice` (would otherwise error) and
`test_substitution_not_silent` (would otherwise pass for the weaker reason). `tests/test_relay.py`: unchanged.
`tests/test_gateway_regressions_v2.py`: frozen; its 3 failures/5 errors in Red's receipt are exactly the
vocabulary split (b) and explicit dispatch (a); every scenario is re-covered under the new names in
`tests/test_gateway_lifecycle.py` and `tests/test_relay_lifecycle.py`.

## Predicted results (static; Red to confirm)
- test_stage.py: 36/36. test_relay.py: 7/7. v2 frozen: 6 pass, 3 fail, 5 error (unchanged attribution).
- test_gateway_lifecycle.py: 22 tests, all predicted pass. test_relay_lifecycle.py: 9 tests, all predicted pass.
- Highest-risk predictions: `mock.patch('relay.<name>')` relies on `transact` resolving `candidate_transition`,
  `atomic` and `export` as module globals at call time (it does); `events[-1] == event` relies on exact float
  JSON round-trip of `canonical` (already relied on by the v2 relay tests, which passed).
- Run from the tree root: `python -m unittest discover -s tests -v` (tests insert `src` on sys.path).

## Not implemented (explicit)
- No relay CLI for resolving an unknown outcome; use `Gateway.resolve_unknown` against the private state.
- No top-level validation of legacy private-state keys beyond the gateway dict and schema string.
- `init` keeps the original random session id (`uuid4`); not made deterministic.
- No `interface.py` change: no blocking defect found, so no diff is proposed.
```

## 5. Checklist for Red
- Install `src/relay.py`, the two new test files, the adapted `tests/test_stage.py` and the note; keep `tests/test_relay.py` and the frozen v2 file as they are.
- Run the discovery command above and return the receipt; I will reconcile any deviation from the predictions in §4 (most likely spots: mock patch targets, the `events[-1] == event` float round-trip, and the `'Ambiguous'`/`'migrate'` substrings in exception messages).