#!/usr/bin/env python3
"""Private, local, file-relayed model-action interface for the FL1 point body.

No model calls, network, shell actions, or physical hardware. Only packet.json
and MODEL_BRIEF.md should be supplied to a candidate. private_state.json contains
simulator truth and future random draws, and belongs to the operator/evaluator.
A trusted single writer is required. Atomic state replacement is the virtual
commit point; export files are regenerable views, not independent witnesses.
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
import uuid
from first_leaf import body_vectors, canonical, fixture, load_protocol
from interface import ACTIONS, Gateway


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
        # D3: a failed write must not leave a stray (possibly private) temporary copy behind.
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def writer_lock(directory: Path):
    lock = directory / 'writer.lock'
    token = f'pid={os.getpid()} token={uuid.uuid4().hex}\n'.encode()
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('Existing writer lock: check for a live writer or interrupted operation before recovery.')
    try:
        os.write(fd, token)
    finally:
        os.close(fd)
    try:
        yield
    finally:
        # D4: release only a lock this writer still owns; a recreated lock belongs to another writer.
        try:
            if lock.read_bytes() == token:
                lock.unlink()
        except FileNotFoundError:
            pass


def sample(s):
    noise = s['fixture']['unit_noise'][s['episode']][s['tick']]
    c = s['cfg']['observations']
    return {'episode': s['episode'], 'sample_tick': s['tick'],
            'p': [s['p'][j] + noise[j] * c['position_noise_scale'] for j in range(2)],
            'v': [s['v'][j] + noise[j + 2] * c['velocity_noise_scale'] for j in range(2)]}


def packet(s):
    g = s['gateway']
    dyn, obs = s['cfg']['dynamics'], s['cfg']['observations']
    delay = s['cfg']['profiles']['primary']['delay']
    sensor_tick = max(0, s['tick'] - delay)
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
            'episode_complete': s['tick'] >= s['cfg']['steps_per_episode'],
            'recent_events': s['public_events'][-12:],
            'request_template': {'schema': 'stage.action.v1', 'request_id': 'REPLACE_WITH_UNIQUE_ID',
                'session_id': g['session_id'], 'body_revision': g['body_revision'],
                'sequence': g['sequence'], 'observation_id': g['observation_id'],
                'expires_tick': g['tick'] + 2, 'action': 'coast'}}


def export(s, directory):
    atomic(directory / 'packet.json', json.dumps(packet(s), indent=2).encode() + b'\n')
    atomic(directory / 'events.jsonl', b''.join(canonical(r) + b'\n' for r in s['public_events']))


def frozen_seed_ranges(cfg):
    for split in ('development', 'evaluation'):
        spec = cfg[f'{split}_seeds']
        yield split, range(spec['first'], spec['first'] + spec['count'])


def init(directory, seed, actor, allow_frozen_seed=False):
    directory.mkdir(parents=True, exist_ok=True)
    with writer_lock(directory):
        path = directory / 'private_state.json'
        if path.exists():
            raise ValueError('Session already exists; refusing overwrite')
        cfg = load_protocol()
        for split, seeds in frozen_seed_ranges(cfg):
            if seed in seeds and not allow_frozen_seed:
                # D6: a frozen development/evaluation fixture is published material, not a fresh trial.
                raise ValueError(f'Seed {seed} is in the frozen {split} fixture range; '
                                 'model-facing seeds must be fresh')
        s = {'schema': 'stage.relay.private.v1', 'actor_label_operator_reported': actor,
             'cfg': cfg, 'fixture': fixture(seed, cfg), 'episode': 0, 'tick': 0,
             'p': [0., 0.], 'v': [0., 0.], 'public_events': [],
             'gateway': asdict(Gateway('relay-' + uuid.uuid4().hex))}
        s['samples'] = [sample(s)]
        atomic(path, canonical(s) + b'\n', True)
        export(s, directory)
    return packet(s)


def transact(directory, request_bytes=None, advance=False):
    with writer_lock(directory):
        path = directory / 'private_state.json'
        s = json.loads(path.read_bytes())
        g = Gateway(**s['gateway'])
        dyn, delay = s['cfg']['dynamics'], s['cfg']['profiles']['primary']['delay']
        event = {'actor_label_operator_reported': s['actor_label_operator_reported'],
                 'episode': s['episode'], 'source_dispatch_tick': g.tick}
        if advance:
            if g.stopped or s['tick'] != s['cfg']['steps_per_episode']:
                raise ValueError('Only an unstopped completed episode can advance')
            if s['episode'] + 1 >= s['cfg']['episodes']:
                raise ValueError('No further episode in this protocol')
            # Make the final delayed samples available before reset.
            event.update({'event': 'operator_episode_reset',
                          'final_sensor_samples': s['samples'][-(delay + 1):],
                          'operator_intervention': True})
            s['episode'] += 1
            s['tick'], s['p'], s['v'] = 0, [0., 0.], [0., 0.]
            s['samples'] = [sample(s)]
            g.observation_id = f'o{g.tick}-episode{s["episode"]}'
        else:
            if request_bytes is None:
                raise ValueError('Missing request')
            # D2: every attempt is identifiable in the ledger by the exact bytes the operator applied.
            event['request_bytes_sha256'] = hashlib.sha256(request_bytes).hexdigest()
            event['request_bytes_len'] = len(request_bytes)
            try:
                receipt = g.admit(request_bytes)
            except (ValueError, UnicodeError) as exc:
                event.update({'event': 'rejected_invalid_request', 'reason': str(exc),
                              'error_type': type(exc).__name__, 'executed': False})
            except Exception as exc:
                # D1: a decoder failure outside the ValueError boundary (e.g. RecursionError) is
                # still a rejection and still gets a durable receipt; no state has been touched.
                event.update({'event': 'rejected_invalid_request',
                              'reason': 'Request could not be decoded within gateway limits',
                              'error_type': type(exc).__name__, 'executed': False})
            else:
                if receipt['dispatch'] and s['tick'] >= s['cfg']['steps_per_episode']:
                    receipt.update({'admitted': False, 'dispatch': False, 'reason': 'episode_complete'})
                    g.cache[receipt['request_id']] = receipt
                event.update({'event': 'action_receipt', 'receipt': receipt, 'executed': False})
                if receipt['dispatch']:
                    a = ACTIONS.index(receipt['requested_action'])
                    b = body_vectors(s['cfg'], s['fixture'], s['episode'], s['cfg']['profiles']['primary'])
                    # D5: the same constants the simulator uses, read from the embedded protocol.
                    s['v'] = [dyn['alpha'] * s['v'][j] + b[a][j] for j in range(2)]
                    s['p'] = [s['p'][j] + dyn['dt'] * s['v'][j] for j in range(2)]
                    s['tick'] += 1
                    s['samples'].append(sample(s))
                    g.record_execution(receipt['request_id'], receipt['requested_action'])
                    event['receipt'] = dict(g.cache[receipt['request_id']])
                    event['executed'] = True
                    event['executed_transition_source_tick'] = s['tick'] - 1
                    event['observed_sensor'] = s['samples'][max(0, s['tick'] - delay)]
        s['gateway'] = asdict(g)
        s['public_events'].append(event)
        # Nothing external is actuated. This saved state defines the committed simulation.
        atomic(path, canonical(s) + b'\n', True)
        export(s, directory)
        return event


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
    for name in ['next-episode', 'export']:
        q = sub.add_parser(name)
        q.add_argument('--directory', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'init':
        result = init(args.directory, args.seed, args.actor_label, args.allow_frozen_seed)
    elif args.command == 'step':
        result = transact(args.directory, args.request.read_bytes())
    elif args.command == 'next-episode':
        result = transact(args.directory, advance=True)
    else:
        with writer_lock(args.directory):
            s = json.loads((args.directory / 'private_state.json').read_bytes())
            export(s, args.directory)
            result = {'exported': True, 'sequence': s['gateway']['sequence']}
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
