#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Original relay: Lilitari (Lily), via ChatGPT.
# GW-ASYNC0 explicit dispatch/outcome recording, validated restore, pre-commit failure handling
# and explicit legacy migration: Coda (Codex Lily), collaborating with Richard Pemberton, 2026-11.
# Relay body completed from the truncated Claude Fable 5.1 draft: Claude (Anthropic), coordinated by
# Red, 2026-11. Audit findings D1-D6 (independent audit, Claude (Anthropic), wave 7) integrated with the
# lifecycle, plus the explicit post-commit export decision: Claude (Anthropic), coordinated by Red,
# 2026-11, task gateway-integration-003. MIT License; see LICENSE.
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
no record and implies no action. Legacy stage.relay.private.v1 state is refused
until the explicit `migrate` command converts it (fails closed on ambiguous receipts).

Post-commit export failure (decision, see docs/gateway_lifecycle_v1/INTEGRATION_NOTE.md):
the step IS committed, so it is never relabelled a failure and never retried by this
code; but packet.json is the only thing a candidate sees, so a stale view must not pass
silently. `transact` therefore raises the distinct `ExportAfterCommitError` (carrying
the committed event) instead of returning normally or leaking a bare OSError that is
indistinguishable from a pre-commit replacement failure. Recovery is `export`, never
replaying the step (the same request is a truthful duplicate anyway).

Audit integrations (D1-D6): every request attempt leaves a durable event identified by
the exact bytes applied (request_bytes_sha256/len, error_type); an admission failure
outside the ValueError boundary (e.g. RecursionError) is a logged rejection and the
in-memory gateway is rolled back to the committed one; a failed write leaves no *.tmp;
the writer lock records its owner and is released only by that owner; every constant the
relay states or integrates with is read from the embedded protocol; `init` refuses the
frozen development/evaluation seed ranges unless explicitly allowed.

This relay never produces an unknown outcome itself (gateway and simulator commit
together). A restored in-flight receipt, which can only come from an operator edit,
is exposed in the packet as `active_request`, blocks new actions (`command_pending`)
and blocks `next-episode` until it is resolved with the Gateway API.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import uuid
from first_leaf import body_vectors, canonical, fixture, load_protocol
from interface import ACTIONS, VERIFIED_SIMULATOR_TRANSITION, Gateway, migrate_legacy_gateway

STATE_SCHEMA = 'stage.relay.private.v2'
LEGACY_STATE_SCHEMA = 'stage.relay.private.v1'
LEGACY_BACKUP_NAME = 'private_state.legacy-v1.json'
UNDECODABLE_REASON = 'Request could not be decoded within gateway limits'  # D1: fixed text, no interpreter internals


class ExportAfterCommitError(RuntimeError):
    """private_state.json is committed but packet.json/events.jsonl could not be regenerated.

    Distinct from every pre-commit failure so that 'nothing happened' and 'committed, views stale'
    can never be confused by an operator or script. `event` is the committed event. Recover with
    the `export` command; never replay the step."""

    def __init__(self, message: str, event: dict):
        super().__init__(message)
        self.event = event
        self.committed = True


def atomic(path: Path, data: bytes, private: bool = False) -> None:
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600 if private else 0o644)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # D3: a failed write or replacement must not leave a stray (possibly private) copy behind.
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def writer_lock(directory: Path):
    """Exclusive-create lock that records its owner; released only while it still carries this token (D4)."""
    lock = directory / 'writer.lock'
    token = f'pid={os.getpid()} token={uuid.uuid4().hex}\n'.encode()
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            holder = lock.read_bytes().decode('utf-8', 'replace').strip() or 'no owner recorded'
        except OSError:
            holder = 'unreadable'
        raise RuntimeError(f'Existing writer lock ({holder}): check for a live writer or interrupted '
                           'operation before recovery.') from None
    try:
        os.write(fd, token)
    except BaseException:
        os.close(fd)
        lock.unlink(missing_ok=True)  # never leave an owner-less lock behind
        raise
    os.close(fd)
    try:
        yield
    finally:
        try:
            if lock.read_bytes() == token:
                lock.unlink()
        except FileNotFoundError:
            pass  # removed by an operator; a lock recreated by another writer is left alone


def sample(s):
    noise = s['fixture']['unit_noise'][s['episode']][s['tick']]
    c = s['cfg']['observations']
    return {'episode': s['episode'], 'sample_tick': s['tick'],
            'p': [s['p'][j] + noise[j] * c['position_noise_scale'] for j in range(2)],
            'v': [s['v'][j] + noise[j + 2] * c['velocity_noise_scale'] for j in range(2)]}


def candidate_transition(s, action):
    """Pure candidate step: the next simulator state for `action`, computed from `s` without
    mutating it. Operand order matches first_leaf.Episode.step exactly (bitwise parity), and the
    constants are the embedded protocol's (D5), not duplicated literals."""
    cfg = s['cfg']
    dyn = cfg['dynamics']
    a = ACTIONS.index(action)
    b = body_vectors(cfg, s['fixture'], s['episode'], cfg['profiles']['primary'])
    v = [dyn['alpha'] * s['v'][j] + b[a][j] for j in range(2)]
    p = [s['p'][j] + dyn['dt'] * v[j] for j in range(2)]
    if not all(math.isfinite(x) for x in v + p):
        raise ArithmeticError('non-finite candidate simulator state')
    probe = dict(s, p=p, v=v, tick=s['tick'] + 1)  # shallow copy: sample() only reads it
    return {'p': p, 'v': v, 'tick': probe['tick'], 'sample': sample(probe)}


def packet(s):
    g = s['gateway']
    dyn, obs = s['cfg']['dynamics'], s['cfg']['observations']
    delay = s['cfg']['profiles']['primary']['delay']
    sensor_tick = max(0, s['tick'] - delay)
    active_id = g['active_request_id']
    return {'schema': 'stage.observation.v1', 'session_id': g['session_id'],
            'body_revision': g['body_revision'], 'sequence': g['sequence'],
            'observation_id': g['observation_id'], 'dispatch_tick': g['tick'],
            'sensor': s['samples'][sensor_tick], 'episode': s['episode'],
            'goal': s['fixture']['goals'][s['episode']],
            # D5: state the protocol's actual constants rather than duplicated literals.
            'known_dynamics': {'dt': dyn['dt'], 'velocity_retention': dyn['alpha']},
            'sensor_contract': {'position_noise_bound': obs['position_noise_scale'],
                                'velocity_noise_bound': obs['velocity_noise_scale'],
                                'delay_ticks': delay, 'actuator_mapping': 'unknown and may change'},
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


def frozen_seed_ranges(cfg):
    for split in ('development', 'evaluation'):
        spec = cfg[f'{split}_seeds']
        yield split, range(spec['first'], spec['first'] + spec['count'])


def init(directory, seed, actor, allow_frozen_seed=False):
    if type(seed) is not int:
        raise ValueError('Seed must be an int')
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError('A non-empty actor label is required')
    cfg = load_protocol()
    if not allow_frozen_seed:
        for split, seeds in frozen_seed_ranges(cfg):
            if seed in seeds:
                # D6: a frozen development/evaluation fixture is published material, not a fresh trial.
                raise ValueError(f'Seed {seed} is in the frozen {split} fixture range; model-facing seeds '
                                 'must be fresh (pass --allow-frozen-seed only for non-model-facing use)')
    directory.mkdir(parents=True, exist_ok=True)
    with writer_lock(directory):
        path = directory / 'private_state.json'
        if path.exists():
            raise ValueError('Session already exists; refusing overwrite')
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
    delay = cfg['profiles']['primary']['delay']
    if g.active_request_id is not None:
        raise ValueError(f'Cannot advance while receipt {g.active_request_id!r} is in flight')
    if g.stopped or s['tick'] != cfg['steps_per_episode']:
        raise ValueError('Only an unstopped completed episode can advance')
    if s['episode'] + 1 >= cfg['episodes']:
        raise ValueError('No further episode in this protocol')
    # Make the final delayed samples available before reset.
    event.update({'event': 'operator_episode_reset',
                  'final_sensor_samples': s['samples'][-(delay + 1):],
                  'operator_intervention': True})
    s['episode'] += 1
    s['tick'], s['p'], s['v'] = 0, [0., 0.], [0., 0.]
    s['samples'] = [sample(s)]
    g.observation_id = f'o{g.tick}-episode{s["episode"]}'


def _step(s, g, event, request_bytes):
    """Admit; for an authorized dispatch, mark dispatch, compute the pure candidate step and
    record the outcome. Nothing here touches the disk; `transact` commits the result.

    Returns the gateway to commit: `g` itself, or (when admission aborted abnormally) a fresh
    restoration of the committed gateway, so a partially-mutated in-memory gateway is never
    written. Rolling back uncommitted memory is not repair: nothing before the commit point counts."""
    if isinstance(request_bytes, str):
        request_bytes = request_bytes.encode('utf-8', 'surrogatepass')
    if not isinstance(request_bytes, (bytes, bytearray)):
        raise ValueError('Request must be bytes')  # operator/programming error: nothing is recorded
    data = bytes(request_bytes)
    # D2: every attempt is identifiable in the ledger by the exact bytes the operator applied.
    event.update({'request_bytes_sha256': hashlib.sha256(data).hexdigest(), 'request_bytes_len': len(data)})
    block = 'episode_complete' if s['tick'] >= s['cfg']['steps_per_episode'] else None
    committed_gateway = asdict(g)  # deep snapshot of the committed gateway; the rollback target
    try:
        receipt = g.admit(data, block_reason=block)
    except (ValueError, UnicodeError) as exc:
        event.update({'event': 'rejected_invalid_request', 'reason': str(exc),
                      'error_type': type(exc).__name__, 'executed': False})
        return Gateway.restore(committed_gateway)
    except Exception as exc:
        # D1: a failure outside the ValueError boundary (e.g. RecursionError) is still a rejection
        # and still gets a durable receipt. The fixed reason keeps interpreter internals out of the
        # candidate-visible ledger; error_type identifies the class for the operator.
        event.update({'event': 'rejected_invalid_request', 'reason': UNDECODABLE_REASON,
                      'error_type': type(exc).__name__, 'executed': False})
        return Gateway.restore(committed_gateway)
    event.update({'event': 'action_receipt', 'receipt': receipt, 'executed': False})
    if not receipt['dispatch']:
        return g  # duplicate view, rejection or stop acknowledgement: nothing to dispatch
    rid, action = receipt['request_id'], receipt['requested_action']
    g.mark_dispatched(rid)  # explicit boundary: the single authorization is consumed before computing
    try:
        step = candidate_transition(s, action)
    except Exception as exc:  # pure computation failed before anything was written: a known failure
        event['receipt'] = g.record_failure(
            rid, f'pre-commit computation failure: {type(exc).__name__}: {exc}')
        return g
    event['receipt'] = g.record_execution(rid, action)
    s['p'], s['v'], s['tick'] = step['p'], step['v'], step['tick']
    s['samples'].append(step['sample'])
    delay = s['cfg']['profiles']['primary']['delay']
    event.update({'executed': event['receipt']['execution_status'] == VERIFIED_SIMULATOR_TRANSITION,
                  'executed_transition_source_tick': s['tick'] - 1,
                  'observed_sensor': s['samples'][max(0, s['tick'] - delay)]})
    return g


def _export_after_commit(s, directory, event):
    try:
        export(s, directory)
    except Exception as exc:
        raise ExportAfterCommitError(
            'Simulation state is committed but regenerating the export views failed; run `export` to '
            'rebuild packet.json and events.jsonl. Never replay the step.', event) from exc


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
            g = _step(s, g, event, request_bytes)
        g.validate()  # the lifecycle left a consistent gateway, or nothing is written
        s['gateway'] = asdict(g)
        s['public_events'].append(event)
        # Nothing external is actuated. This replacement is the only commit point: an exception
        # before or inside it leaves no record and implies no action, so nothing is recorded for it.
        atomic(path, canonical(s) + b'\n', True)
        _export_after_commit(s, directory, event)
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
        event = {'actor_label_operator_reported': s['actor_label_operator_reported'],
                 'episode': s['episode'], 'source_dispatch_tick': gateway['tick'],
                 'event': 'operator_state_migration', 'from_schema': LEGACY_STATE_SCHEMA,
                 'to_schema': STATE_SCHEMA, 'operator_intervention': True, 'executed': False}
        migrated = dict(s, schema=STATE_SCHEMA, gateway=gateway)
        migrated['public_events'] = list(s['public_events']) + [event]
        backup = directory / LEGACY_BACKUP_NAME
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)  # refuse to clobber an earlier backup
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        atomic(path, canonical(migrated) + b'\n', True)
        _export_after_commit(migrated, directory, event)
        return {'migrated': True, 'schema': STATE_SCHEMA, 'receipts': len(gateway['cache']),
                'backup': backup.name}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    start = sub.add_parser('init')
    start.add_argument('--directory', type=Path, required=True)
    start.add_argument('--seed', type=int, default=20000)
    start.add_argument('--actor-label', required=True)
    start.add_argument('--allow-frozen-seed', action='store_true',
                       help='permit a seed inside the frozen development/evaluation ranges (not model-facing)')
    act = sub.add_parser('step')
    act.add_argument('--directory', type=Path, required=True)
    act.add_argument('--request', type=Path, required=True)
    for name in ['next-episode', 'export', 'migrate']:
        q = sub.add_parser(name)
        q.add_argument('--directory', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == 'init':
            result = init(args.directory, args.seed, args.actor_label, args.allow_frozen_seed)
        elif args.command == 'step':
            result = transact(args.directory, args.request.read_bytes())
        elif args.command == 'next-episode':
            result = transact(args.directory, advance=True)
        elif args.command == 'migrate':
            result = migrate(args.directory)
        else:
            result = regenerate_views(args.directory)
    except ExportAfterCommitError as exc:
        # Committed, views stale: report the committed event and the recovery, exit non-zero (distinct code).
        print(json.dumps({'committed': True, 'export_failed': True, 'event': exc.event,
                          'recovery': 'run the export command; never replay the step'}, indent=2))
        cause = exc.__cause__
        print(f'error: {exc} ({type(cause).__name__}: {cause})', file=sys.stderr)
        sys.exit(3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
