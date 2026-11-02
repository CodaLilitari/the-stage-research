# gateway-conformance-004 — conformance of the integrated gateway/relay to the checker's clarified semantics

Claude (Anthropic), coordinated by Red (Claude, Anthropic) for Richard (Andrei) Pemberton. Inputs: the wave-10 model checker and its sandbox receipts (Claude via Red); integrated `interface.py`/`relay.py` (original: Lilitari (Lily) via ChatGPT, MIT; GW-ASYNC0 lifecycle: Coda (Codex Lily); relay body draft: Claude Fable 5.1; audit integration: Claude, gateway-integration-003); execution receipts: Red. **Everything below is static reasoning; I executed nothing and read no files beyond the verbatim bundle.** Private computational research on an actuator-free simulator model; not empirical validation, not a safety certification, not a hardware recommendation.

## 1. Verdicts

### 1.1 Invariants

| Checker invariant | Verdict for the integrated implementation | Where tested |
|---|---|---|
| INV_ONE_UNRESOLVED | conforms: `admit` → `command_pending`; `validate` refuses >1 in flight or a mismatched `active_request_id` | `GatewayApiInvariants`, `TraceCE4…inflight` |
| INV_NO_REDISPATCH | conforms: cached duplicate returns `dispatch=False`, state unchanged; cache never evicts; `mark_dispatched` twice raises | sweep, `GatewayApiInvariants` |
| INV_NO_DOUBLE_DISPATCH (ghost: durable mark) | **does not hold as modelled, by documented decision**: the relay's dispatch mark is in-memory; its docstring declares "a crash before the replacement leaves no record and implies no action". This is clarification **C1 option (b)**, not (a). Not a defect; DESIGN.md should say it in one sentence. | `TraceCE1…` |
| INV_STOP_LATCH | conforms: monotone (no code path clears `stopped`), dispatched/unknown never relabelled, stays latched after resolution, fresh move after stop rejected | `TraceCE3…` |
| INV_ONLY_VERIFIED_ADVANCES | conforms: only `_verify_transition` advances; relay simulator tick moves only with `record_execution` in the same replacement | sweep, API |
| INV_FAILURE_RELEASES | conforms | sweep |
| INV_RESTORE_REJECTS_INCONSISTENT | **partial (N-2)**: receipt structure, in-flight count, active identity, stop/pending are checked; counter/simulator cross-consistency (model's `seq == tick == obs == len(sim)`, verified ⇔ transition) is not | `TraceCE4…` (3 expected failures) |
| INV_RESTORE_ACCEPTS_CONSISTENT | conforms | sweep, API |
| INV_EXPORT_NEVER_REPLAYS | conforms for `export`/`regenerate_views`; the derived "idle ⇒ view current" fails after an **ambiguous replacement** (**N-1**) | `TraceCE2…` (1 expected failure) |
| INV_NO_FALSE_OUTCOME | conforms: verified ⇔ committed in the same replacement; failures only pre-commit; no false `verified_failure` after an ambiguous replacement | `TraceCE2…`, sweep |

### 1.2 The four as-written traces

| Trace | Expressible against the real code? | Result |
|---|---|---|
| CE-1 `begin; admit(a); mark_dispatched; crash; recover; begin; admit(a); mark_dispatched` | yes — crash = `os.replace` fails for `private_state.json`; hard-crash lock = dead `writer.lock` (operator removes); recover = `regenerate_views` | replay is a **fresh** admission, dispatched again. Matches the declared memory-only reading (C1-b). Substitute invariant holds: no record ⇒ no transition; once committed, replay never redispatches. |
| CE-2 `… commit_ambiguous(replaced=True); persist_unknown_blind` | `commit_ambiguous(replaced=True)` yes (replace succeeds, then raises); `persist_unknown_blind` **not expressible** — the relay writes nothing after the exception | conforms to C2's "never write memory back"; C2's explicit re-read is deferred to the next transaction, so the error surfaces as a bare `OSError` (the type the integration note reserves for "nothing happened") and views are stale while the lock is free → **N-1**, diff D-1 |
| CE-3 `… mark_dispatched; stop/admit(b); … commit_ambiguous(replaced=False); resolve_unknown_trusted` | **not expressible in the relay** (one request per transaction, no re-read inside one); the stop-after-dispatch half is expressible at the Gateway API; `resolve_unknown_trusted`-with-re-read has no counterpart | API-level conforms: latch kept, dispatched work outstanding, receipts preserved across `asdict`/`restore`; relay-level the stop is its own committed transaction |
| CE-4 `tamper(kind); begin` | yes, all 7 kinds | `active_dangling`, `orphan_dispatched`, `two_pending`, `stopped_with_pending` refused; `counter_skew`, `sim_skew`, `false_verified` **accepted** → **N-2**, diff D-2 |

## 2. Deliverable

FILE: tests/test_gateway_conformance.py
```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Conformance replay of the GW-ASYNC0 model-checker traces against the real gateway/relay:
# Claude (Anthropic), coordinated by Red (Claude, Anthropic) for Richard Pemberton, 2026-11,
# task gateway-conformance-004. Model, invariants and traces: gateway-modelcheck-001/002 (Claude via
# Red). Code under test: interface.py/relay.py — Lilitari (Lily) via ChatGPT (original, MIT); Coda
# (Codex Lily) (GW-ASYNC0 lifecycle); Claude Fable 5.1 (relay draft); Claude (Anthropic)
# (gateway-integration-003). Standard library only; deterministic; writes only inside its own
# tempfile.TemporaryDirectory (test fixture), never elsewhere.
"""Replay the checker's four as-written counterexample traces, and its clarified invariants, against
the REAL interface.py / relay.py.

    python -m unittest -v tests.test_gateway_conformance

Mapping of model actions to the implementation (see docs/gateway_lifecycle_v1/CONFORMANCE_NOTE.md):
  begin / recover            relay.transact re-reads private_state via load_state (Gateway.restore)
  admit / mark_dispatched /
  compute_* / commit_ok      one relay.transact call (one request per writer-locked transaction)
  crash before replacement   os.replace raises for private_state.json (nothing replaced; D3 cleanup)
  commit_ambiguous(True)     os.replace replaces private_state.json and THEN raises
  hard crash with lock held  a dead writer.lock left behind; the operator removes it (labelled)
  export_fail                relay.export raises after the commit -> ExportAfterCommitError
  compute_fail               relay.candidate_transition raises -> record_failure
  tamper(kind)               the test edits private_state.json in its own temporary directory
  persist_unknown_blind,
  resolve_unknown_trusted    NOT expressible: the relay never writes after a failed replacement and
                             never re-reads inside a transaction (the next transaction re-reads)
  API interleaving           NOT expressible in the relay; replayed on an in-memory Gateway instead

Expected failures (@unittest.expectedFailure) document genuine non-conformance to the clarified
semantics (findings N-1, N-2 in the note). Applying diffs D-1/D-2 turns them into "unexpected
successes": then remove the decorators.

Static reasoning by the author; nothing here was executed by the author. Red's sandbox run decides.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


def _import_targets():
    """Import interface/relay from sys.path, else from a src/ (or same) directory near this file."""
    try:
        return importlib.import_module('interface'), importlib.import_module('relay')
    except ImportError:
        pass
    here = Path(__file__).resolve()
    tried = []
    for base in [here.parent, *list(here.parents)[1:4]]:
        for cand in (base / 'src', base):
            if cand in tried:
                continue
            tried.append(cand)
            if (cand / 'relay.py').is_file() and (cand / 'interface.py').is_file():
                sys.path.insert(0, str(cand))
                return importlib.import_module('interface'), importlib.import_module('relay')
    raise ImportError('interface.py/relay.py not found on sys.path nor in src/ near %s' % here)


interface, relay = _import_targets()

ADMITTED_PENDING = interface.ADMITTED_PENDING
DISPATCHED = interface.DISPATCHED
VERIFIED = interface.VERIFIED_SIMULATOR_TRANSITION
VERIFIED_FAILURE = interface.VERIFIED_FAILURE
CANCELLED = interface.CANCELLED_BEFORE_DISPATCH
UNKNOWN_OUTCOME = interface.UNKNOWN_OUTCOME
REJECTED = interface.REJECTED
STOP_ACKNOWLEDGED = interface.STOP_ACKNOWLEDGED

SEED = 20000  # the relay CLI default; allow_frozen_seed=True keeps the test independent of the ranges
ACTOR = 'conformance replay (test harness, not model-facing)'
SESSION = 'conformance-session'

# Status graph of the clarified lifecycle (model.ALLOWED_NEXT); everything else is terminal.
ALLOWED_NEXT = {
    ADMITTED_PENDING: {DISPATCHED, CANCELLED},
    DISPATCHED: {VERIFIED, VERIFIED_FAILURE, UNKNOWN_OUTCOME},
    UNKNOWN_OUTCOME: {VERIFIED, VERIFIED_FAILURE},
}


# --------------------------------------------------------------------------- request / state helpers

def request_for(gw: dict, request_id: str, action: str = 'coast', **overrides) -> bytes:
    """A valid stage.action.v1 request for the gateway dict `gw` (asdict(Gateway) or state['gateway'])."""
    r = {'schema': 'stage.action.v1', 'request_id': request_id, 'session_id': gw['session_id'],
         'body_revision': gw['body_revision'], 'sequence': gw['sequence'],
         'observation_id': gw['observation_id'], 'expires_tick': gw['tick'] + 2, 'action': action}
    r.update(overrides)
    return json.dumps(r, sort_keys=True).encode()


def receipt(request_id: str, status: str, action: str = 'coast', **extra) -> dict:
    """A structurally valid cached receipt (passes interface.validate_receipt) for tamper scenarios."""
    r = {'request_id': request_id, 'request_sha256': hashlib.sha256(request_id.encode()).hexdigest(),
         'requested_action': action, 'admitted': status != REJECTED,
         'reason': 'sequence_mismatch' if status == REJECTED else None, 'duplicate': False,
         'dispatch': status == ADMITTED_PENDING, 'stop_latched': False, 'execution_status': status}
    if status == VERIFIED:
        r['executed_action'] = action
    r.update(extra)
    return r


def read_state(directory: Path) -> dict:
    return json.loads((directory / 'private_state.json').read_bytes())


def read_packet(directory: Path) -> dict:
    return json.loads((directory / 'packet.json').read_bytes())


def write_state(directory: Path, s: dict) -> None:
    """Test-side edit of the test's own temporary private_state.json (models tamper / operator edits)."""
    (directory / 'private_state.json').write_bytes(relay.canonical(s) + b'\n')


def sim_log(s: dict) -> list:
    """Simulator truth as committed request ids: one executed event per verified transition."""
    return [ev['receipt']['request_id'] for ev in s['public_events'] if ev.get('executed')]


def verified_ids(s: dict) -> set:
    return {k for k, e in s['gateway']['cache'].items() if e['execution_status'] == VERIFIED}


def consistency_issues(s: dict) -> list:
    """The clarified restore predicate (checker clarification C4) in the implementation's terms."""
    g = s['gateway']
    cache = g['cache']
    issues = []
    unresolved = sorted(k for k, e in cache.items() if e['execution_status'] in interface.IN_FLIGHT)
    if len(unresolved) > 1:
        issues.append('multiple_unresolved')
    expected_active = unresolved[0] if len(unresolved) == 1 else None
    if g['active_request_id'] != expected_active:
        issues.append('active_mismatch' if unresolved else 'active_dangling')
    if g['stopped'] and any(e['execution_status'] == ADMITTED_PENDING for e in cache.values()):
        issues.append('stopped_with_pending')
    log = sim_log(s)
    verified = verified_ids(s)
    if len(set(log)) != len(log) or verified != set(log):
        issues.append('verified_sim_mismatch')
    expected_tick = s['episode'] * s['cfg']['steps_per_episode'] + s['tick']
    if not (g['sequence'] == g['tick'] == len(verified) == expected_tick):
        issues.append('counter_skew')
    if len(s['samples']) != s['tick'] + 1:
        issues.append('sample_skew')
    if g['observation_id'] not in ('o%d' % g['tick'], 'o%d-episode%d' % (g['tick'], s['episode'])):
        issues.append('observation_skew')
    if any(e['execution_status'] not in interface.STATUSES for e in cache.values()):
        issues.append('unknown_status')
    return issues


def step_issues(s1: dict, s2: dict) -> list:
    """Transition invariants between two committed states (checker._gw_step on durable state)."""
    g1, g2 = s1['gateway'], s2['gateway']
    issues = []
    for rid, e1 in g1['cache'].items():
        e2 = g2['cache'].get(rid)
        if e2 is None:
            issues.append('receipt %s lost' % rid)
            continue
        st1, st2 = e1['execution_status'], e2['execution_status']
        if st1 != st2 and st2 not in ALLOWED_NEXT.get(st1, set()):
            issues.append('%s: %s -> %s' % (rid, st1, st2))
    if g1['stopped'] and not g2['stopped']:
        issues.append('stop unlatched')
    d = (g2['sequence'] - g1['sequence'], g2['tick'] - g1['tick'])
    newly = verified_ids(s2) - verified_ids(s1)
    if d not in ((0, 0), (1, 1)) or len(newly) != d[0]:
        issues.append('counters moved %r with %r newly verified' % (d, sorted(newly)))
    log1, log2 = sim_log(s1), sim_log(s2)
    if log2[:len(log1)] != log1:
        issues.append('simulator log rolled back')
    elif len(log2) - len(log1) != d[0]:
        issues.append('simulator log and counters diverged')
    if s1['episode'] == s2['episode'] and s2['tick'] - s1['tick'] != d[0]:
        issues.append('simulator tick and gateway counters diverged')
    return issues


@contextlib.contextmanager
def replacement_failure(ambiguous: bool):
    """Make the replacement of private_state.json fail.

    ambiguous=False: crash/failure before the replacement (nothing replaced).
    ambiguous=True:  the replacement really happens, then an error is reported to the caller
                     (model action commit_ambiguous(replaced=True))."""
    original = os.replace

    def fake(src, dst, *args, **kwargs):
        if Path(dst).name == 'private_state.json':
            if ambiguous:
                original(src, dst, *args, **kwargs)
                raise OSError('simulated ambiguous replacement: replaced, then an error was observed')
            raise OSError('simulated pre-commit failure: the replacement did not happen')
        return original(src, dst, *args, **kwargs)

    with mock.patch.object(os, 'replace', fake):
        yield


# --------------------------------------------------------------------------- relay test base

class RelayCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name) / 'session'
        relay.init(self.directory, SEED, ACTOR, allow_frozen_seed=True)
        self.path = self.directory / 'private_state.json'

    def state(self) -> dict:
        return read_state(self.directory)

    def assertQuiescent(self):
        self.assertFalse((self.directory / 'writer.lock').exists(), 'writer lock still held')
        self.assertEqual([], sorted(p.name for p in self.directory.glob('*.tmp')), 'stray temp file')

    def assertConsistent(self, s: dict):
        self.assertEqual([], consistency_issues(s))

    def assertStep(self, before: dict, after: dict):
        self.assertEqual([], step_issues(before, after))

    def assertViewCurrent(self):
        s = self.state()
        g = s['gateway']
        p = read_packet(self.directory)
        self.assertEqual((g['sequence'], g['observation_id'], g['tick'], g['stopped'], s['episode']),
                         (p['sequence'], p['observation_id'], p['dispatch_tick'], p['stopped'], p['episode']))
        expected_active = None if g['active_request_id'] is None else g['cache'][g['active_request_id']]
        self.assertEqual(expected_active, p['active_request'])

    def step(self, request: bytes):
        """One committed transaction with every state and step invariant asserted."""
        before = self.state()
        event = relay.transact(self.directory, request)
        after = self.state()
        self.assertQuiescent()
        self.assertConsistent(after)
        self.assertStep(before, after)
        self.assertViewCurrent()
        self.assertEqual(event, after['public_events'][-1])
        return event, after


# --------------------------------------------------------------------------- invariant sweep

class RelayInvariantSweep(RelayCase):
    """Relay-level sweep over the clarified invariants with mixed outcomes in one session."""

    def test_lifecycle_sweep_holds_every_state_and_step_invariant(self):
        s0 = self.state()
        self.assertConsistent(s0)
        self.assertViewCurrent()
        # begin; admit(a); mark_dispatched; compute_ok; commit_ok; export_ok
        req_a = request_for(s0['gateway'], 'a')
        ev, s1 = self.step(req_a)
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertTrue(ev['executed'])
        self.assertFalse(ev['receipt']['dispatch'])  # the single authorization is consumed
        self.assertEqual((1, 1, 'o1'), (s1['gateway']['sequence'], s1['gateway']['tick'], s1['gateway']['observation_id']))
        self.assertEqual(1, s1['tick'])
        self.assertEqual(['a'], sim_log(s1))
        # duplicate replay of a: cached view, dispatch=False, nothing changes (INV_NO_REDISPATCH)
        ev, s2 = self.step(req_a)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertFalse(ev['receipt']['dispatch'])
        self.assertFalse(ev['executed'])
        self.assertEqual(s1['gateway'], s2['gateway'])
        # stale x: sequence_mismatch, cached as a rejection; its replay is the cached rejection
        req_x = request_for(s2['gateway'], 'x', sequence=s2['gateway']['sequence'] + 5)
        ev, s3 = self.step(req_x)
        self.assertEqual((REJECTED, 'sequence_mismatch'), (ev['receipt']['execution_status'], ev['receipt']['reason']))
        ev, s4 = self.step(req_x)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(REJECTED, ev['receipt']['execution_status'])
        self.assertEqual(s3['gateway'], s4['gateway'])
        # compute_fail on b: verified_failure releases the slot without advancing (INV_FAILURE_RELEASES)
        req_b = request_for(s4['gateway'], 'b', action='k1')
        with mock.patch.object(relay, 'candidate_transition', side_effect=ArithmeticError('simulated non-finite candidate')):
            ev, s5 = self.step(req_b)
        self.assertEqual(VERIFIED_FAILURE, ev['receipt']['execution_status'])
        self.assertIn('ArithmeticError', ev['receipt']['failure_reason'])
        self.assertFalse(ev['executed'])
        self.assertIsNone(s5['gateway']['active_request_id'])
        self.assertEqual(s4['gateway']['sequence'], s5['gateway']['sequence'])
        self.assertEqual(s4['tick'], s5['tick'])
        # fresh c at the same sequence is admitted and verified; b stays a failure on replay
        ev, s6 = self.step(request_for(s5['gateway'], 'c', action='k1'))
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertEqual(['a', 'c'], sim_log(s6))
        ev, s7 = self.step(req_b)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED_FAILURE, ev['receipt']['execution_status'])
        self.assertEqual(s6['gateway'], s7['gateway'])
        # export_fail after commit (d): committed, loud, distinct; export regenerates; replay is a duplicate
        req_d = request_for(s7['gateway'], 'd', action='k2')
        with mock.patch.object(relay, 'export', side_effect=OSError('simulated export failure')):
            with self.assertRaises(relay.ExportAfterCommitError) as cm:
                relay.transact(self.directory, req_d)
        self.assertTrue(cm.exception.committed)
        self.assertIsInstance(cm.exception.__cause__, OSError)
        s8 = self.state()
        self.assertQuiescent()
        self.assertConsistent(s8)
        self.assertStep(s7, s8)
        self.assertEqual(cm.exception.event, s8['public_events'][-1])
        self.assertEqual(VERIFIED, s8['gateway']['cache']['d']['execution_status'])
        self.assertEqual(s7['gateway']['sequence'], read_packet(self.directory)['sequence'])  # view stale
        durable = self.path.read_bytes()
        relay.regenerate_views(self.directory)
        self.assertEqual(durable, self.path.read_bytes())  # export never touches durable state
        self.assertViewCurrent()
        ev, s9 = self.step(req_d)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(s8['gateway'], s9['gateway'])
        self.assertEqual(['a', 'c', 'd'], sim_log(s9))
        # stop s: acknowledged, distinct from a rejection, nothing in flight so nothing cancelled
        req_s = request_for(s9['gateway'], 's', action='stop')
        ev, s10 = self.step(req_s)
        self.assertEqual(STOP_ACKNOWLEDGED, ev['receipt']['execution_status'])
        self.assertTrue(ev['receipt']['admitted'])
        self.assertNotIn('cancelled_request_id', ev['receipt'])
        self.assertTrue(s10['gateway']['stopped'])
        # fresh e after stop is rejected stop_latched; duplicates of s and a are truthful views
        ev, s11 = self.step(request_for(s10['gateway'], 'e'))
        self.assertEqual((REJECTED, 'stop_latched'), (ev['receipt']['execution_status'], ev['receipt']['reason']))
        ev, s12 = self.step(req_s)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(STOP_ACKNOWLEDGED, ev['receipt']['execution_status'])
        ev, s13 = self.step(req_a)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertTrue(s13['gateway']['stopped'])
        self.assertEqual(3, s13['gateway']['sequence'])
        self.assertEqual(['a', 'c', 'd'], sim_log(s13))
        # INV_RESTORE_ACCEPTS_CONSISTENT: every reachable committed state restores and round-trips
        s, g = relay.load_state(self.path)
        self.assertEqual(asdict(g), s['gateway'])
        interface.Gateway.restore(asdict(g))


# --------------------------------------------------------------------------- CE-1

class TraceCE1NonDurableDispatchMark(RelayCase):
    """as_written_nondurable_dispatch_mark, INV_NO_DOUBLE_DISPATCH (length 8):
    begin; admit(a); mark_dispatched; crash; recover; begin; admit(a); mark_dispatched

    The relay's mark_dispatched is in-memory and the relay docstring declares the consequence
    ("a crash before the replacement leaves no record and implies no action"): clarification C1
    option (b). The model's ghost invariant (an id is marked dispatched at most once across
    crashes) is therefore not what the implementation guarantees; the declared substitute is
    asserted instead: no record => no transition, and a committed dispatch never happens twice."""

    def test_crash_before_replacement_leaves_no_record_and_the_replay_is_a_fresh_admission(self):
        s0 = self.state()
        req_a = request_for(s0['gateway'], 'a')
        durable = self.path.read_bytes()
        packet = (self.directory / 'packet.json').read_bytes()
        # begin; admit(a); mark_dispatched; compute_ok; crash (replacement never happens)
        with replacement_failure(ambiguous=False):
            with self.assertRaises(OSError):
                relay.transact(self.directory, req_a)
        self.assertEqual(durable, self.path.read_bytes(), 'nothing may be recorded before the commit point')
        self.assertEqual(packet, (self.directory / 'packet.json').read_bytes())
        self.assertQuiescent()
        s_after = self.state()
        self.assertNotIn('a', s_after['gateway']['cache'])
        self.assertEqual(0, s_after['tick'])
        self.assertEqual([], sim_log(s_after))
        # recover: a hard crash would leave writer.lock; the relay refuses to run until the operator
        # removes it (PLAN forbids workers from deleting locks) -- labelled operator intervention.
        lock = self.directory / 'writer.lock'
        lock.write_bytes(b'pid=0 token=deadbeef\n')
        with self.assertRaises(RuntimeError) as cm:
            relay.transact(self.directory, req_a)
        self.assertIn('Existing writer lock', str(cm.exception))
        self.assertEqual(durable, self.path.read_bytes())
        lock.unlink()  # operator intervention
        relay.regenerate_views(self.directory)
        self.assertEqual(durable, self.path.read_bytes())  # recover never replays
        self.assertViewCurrent()
        # begin; admit(a); mark_dispatched: a FRESH admission at the same sequence, dispatched and committed
        ev, s1 = self.step(req_a)
        self.assertFalse(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertTrue(ev['executed'])
        self.assertEqual(1, s1['tick'])
        self.assertEqual(['a'], sim_log(s1))
        # once committed, the replay is a duplicate view: no second dispatch, no second transition
        ev, s2 = self.step(req_a)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertFalse(ev['receipt']['dispatch'])
        self.assertEqual(1, s2['tick'])
        self.assertEqual(['a'], sim_log(s2))


# --------------------------------------------------------------------------- CE-2

class TraceCE2BlindUnknownPersist(RelayCase):
    """as_written_blind_unknown_persist, INV_NO_FALSE_OUTCOME / INV_ONLY_VERIFIED_ADVANCES (length 6):
    begin; admit(a); mark_dispatched; compute_ok; commit_ambiguous(replaced=True); persist_unknown_blind

    persist_unknown_blind is not expressible: the relay writes nothing after the replacement raised.
    The clarified resolution (re-read the file, outcome follows the file) happens at the next
    transaction, which is asserted here. The view-currency half of C2 is finding N-1 (expected failure)."""

    def _ambiguous_commit(self, req: bytes):
        raised = None
        try:
            with replacement_failure(ambiguous=True):
                relay.transact(self.directory, req)
        except OSError as exc:  # today: a bare OSError (finding N-1). After diff D-1: no exception.
            raised = exc
        return raised

    def test_ambiguous_replacement_is_resolved_by_the_file_never_by_memory(self):
        s0 = self.state()
        req_a = request_for(s0['gateway'], 'a')
        durable0 = self.path.read_bytes()
        raised = self._ambiguous_commit(req_a)
        self.assertNotIsInstance(raised, relay.ExportAfterCommitError)
        self.assertQuiescent()
        s1 = self.state()
        self.assertNotEqual(durable0, self.path.read_bytes(), 'the replacement did happen')
        self.assertConsistent(s1)
        self.assertStep(s0, s1)
        self.assertEqual(VERIFIED, s1['gateway']['cache']['a']['execution_status'])
        self.assertEqual(1, s1['tick'])
        self.assertEqual(['a'], sim_log(s1))
        # persist_unknown_blind did not happen: no unknown_outcome, no rewind, no false failure
        statuses = {e['execution_status'] for e in s1['gateway']['cache'].values()}
        self.assertNotIn(UNKNOWN_OUTCOME, statuses)
        self.assertNotIn(VERIFIED_FAILURE, statuses)
        # resolve_unknown_trusted ~ the next transaction re-reads durable truth: a truthful duplicate
        ev, s2 = self.step(req_a)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertFalse(ev['executed'])
        self.assertEqual((1, 1), (s2['gateway']['sequence'], s2['tick']))
        self.assertEqual(['a'], sim_log(s2))

    def test_unreplaced_failure_produces_no_false_verified_failure(self):
        """commit_ambiguous(replaced=False): nothing replaced => nothing recorded; the replay is a fresh
        admission (CE-1 behaviour) and no verified_failure is ever invented for the attempt."""
        s0 = self.state()
        req_a = request_for(s0['gateway'], 'a')
        durable0 = self.path.read_bytes()
        with replacement_failure(ambiguous=False):
            with self.assertRaises(OSError):
                relay.transact(self.directory, req_a)
        self.assertEqual(durable0, self.path.read_bytes())
        self.assertQuiescent()
        ev, s1 = self.step(req_a)
        self.assertFalse(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertNotIn(VERIFIED_FAILURE, {e['execution_status'] for e in s1['gateway']['cache'].values()})
        self.assertEqual(['a'], sim_log(s1))

    @unittest.expectedFailure
    def test_export_view_is_current_after_an_ambiguous_replacement(self):
        """Clarified C2 + INV_EXPORT_NEVER_REPLAYS ('idle => export == durable view'). Finding N-1:
        today the replacement succeeded, the lock is released, yet packet.json still shows the old
        sequence because the bare OSError skipped the export. Diff D-1 (re-read, then export) fixes it;
        when this test unexpectedly succeeds, remove the decorator."""
        s0 = self.state()
        self._ambiguous_commit(request_for(s0['gateway'], 'a'))
        s1 = self.state()
        self.assertEqual(1, s1['gateway']['sequence'])
        self.assertEqual(s1['gateway']['sequence'], read_packet(self.directory)['sequence'])


# --------------------------------------------------------------------------- CE-3

class TraceCE3GatewayApiLevel(unittest.TestCase):
    """as_written_reread_without_latch_merge, INV_STOP_LATCH / INV_NO_REDISPATCH (length 7):
    begin; admit(a); mark_dispatched; stop | admit(b); compute_ok; commit_ambiguous(False); resolve_unknown_trusted

    Not expressible in the relay (one request per transaction; no re-read inside one). The in-process
    half is replayed on one Gateway: the latch and the rejected receipt live in the same object that
    is serialized, so there is nothing to merge; a re-read with a lost latch cannot occur."""

    def test_stop_after_dispatch_is_outstanding_not_cancelled_and_stays_latched(self):
        g = interface.Gateway(SESSION)
        req_a = request_for(asdict(g), 'a')
        self.assertTrue(g.admit(req_a)['dispatch'])
        g.mark_dispatched('a')
        req_b = request_for(asdict(g), 'b')
        rb = g.admit(req_b)
        self.assertEqual((REJECTED, 'command_pending'), (rb['execution_status'], rb['reason']))
        rs = g.admit(request_for(asdict(g), 's', action='stop'))
        self.assertEqual(STOP_ACKNOWLEDGED, rs['execution_status'])
        self.assertEqual(('a', DISPATCHED), (rs['outstanding_request_id'], rs['outstanding_status']))
        self.assertNotIn('cancelled_request_id', rs)
        self.assertEqual(DISPATCHED, g.cache['a']['execution_status'])  # never relabelled
        self.assertTrue(g.stopped)
        ra = g.record_execution('a', 'coast')  # the dispatched step completes (assumption A5 / C5)
        self.assertEqual(VERIFIED, ra['execution_status'])
        self.assertTrue(ra['stop_latched'])
        self.assertTrue(g.stopped)
        self.assertEqual((1, 1, None), (g.sequence, g.tick, g.active_request_id))
        # serialize / restore keeps the latch and every receipt (the merge CE-3 asks for is a non-issue)
        g2 = interface.Gateway.restore(asdict(g))
        self.assertTrue(g2.stopped)
        self.assertEqual({'a', 'b', 's'}, set(g2.cache))
        rb2 = g2.admit(req_b)  # identical bytes: the cached rejection, never a redispatch
        self.assertTrue(rb2['duplicate'])
        self.assertEqual((REJECTED, 'command_pending', False), (rb2['execution_status'], rb2['reason'], rb2['dispatch']))
        rc = g2.admit(request_for(asdict(g2), 'c'))
        self.assertEqual((REJECTED, 'stop_latched'), (rc['execution_status'], rc['reason']))
        self.assertTrue(g2.stopped)

    def test_unknown_outcome_resolution_keeps_the_stop_latch(self):
        for outcome, action, advance in ((VERIFIED_FAILURE, None, 0), (VERIFIED, 'coast', 1)):
            with self.subTest(outcome=outcome):
                g = interface.Gateway(SESSION)
                g.admit(request_for(asdict(g), 'a'))
                g.mark_dispatched('a')
                g.admit(request_for(asdict(g), 's', action='stop'))
                g.mark_unknown('a', 'simulated ambiguous replacement')
                self.assertEqual('a', g.active_request_id)
                self.assertTrue(g.stopped)
                r = g.resolve_unknown('a', outcome, action)
                self.assertEqual(outcome, r['execution_status'])
                self.assertEqual(UNKNOWN_OUTCOME, r['resolved_from'])
                self.assertTrue(g.stopped)  # stop stays latched after resolution
                self.assertIsNone(g.active_request_id)
                self.assertEqual((advance, advance), (g.sequence, g.tick))
                interface.Gateway.restore(asdict(g))


class TraceCE3RelayLevel(RelayCase):
    """Relay counterpart: stop is its own committed transaction; the latch is re-read from the file."""

    def test_stop_is_its_own_committed_transaction_and_survives_the_re_read(self):
        s0 = self.state()
        req_a = request_for(s0['gateway'], 'a')
        _, s1 = self.step(req_a)
        ev, s2 = self.step(request_for(s1['gateway'], 's', action='stop'))
        self.assertEqual(STOP_ACKNOWLEDGED, ev['receipt']['execution_status'])
        self.assertNotIn('cancelled_request_id', ev['receipt'])
        self.assertTrue(s2['gateway']['stopped'])
        _, g = relay.load_state(self.path)  # begin: the latch comes from the file
        self.assertTrue(g.stopped)
        ev, s3 = self.step(request_for(s2['gateway'], 'c'))
        self.assertEqual((REJECTED, 'stop_latched'), (ev['receipt']['execution_status'], ev['receipt']['reason']))
        ev, s4 = self.step(req_a)
        self.assertTrue(ev['receipt']['duplicate'])
        self.assertEqual(VERIFIED, ev['receipt']['execution_status'])
        self.assertEqual(1, s4['tick'])
        self.assertTrue(s4['gateway']['stopped'])

    def test_a_stop_whose_commit_fails_leaves_no_record_and_is_reported(self):
        """Observation O-2: an uncommitted stop is 'nothing happened' (the operator sees the error and
        retries); the same crash-before-persist loss exists in the model."""
        s0 = self.state()
        req_s = request_for(s0['gateway'], 's', action='stop')
        durable = self.path.read_bytes()
        with replacement_failure(ambiguous=False):
            with self.assertRaises(OSError):
                relay.transact(self.directory, req_s)
        self.assertEqual(durable, self.path.read_bytes())
        self.assertQuiescent()
        self.assertFalse(self.state()['gateway']['stopped'])
        ev, s1 = self.step(req_s)  # operator retry: a fresh acknowledgement, not a duplicate
        self.assertFalse(ev['receipt']['duplicate'])
        self.assertEqual(STOP_ACKNOWLEDGED, ev['receipt']['execution_status'])
        self.assertTrue(s1['gateway']['stopped'])


# --------------------------------------------------------------------------- CE-4

class TraceCE4RestoreValidation(RelayCase):
    """as_written_weak_restore_validation (length 2): tamper(kind); begin, for all seven tamper kinds.
    One committed transition first so that counters and the simulator log are non-trivial."""

    def setUp(self):
        super().setUp()
        self.step(request_for(self.state()['gateway'], 'a'))

    def tampered(self, mutate) -> dict:
        s = self.state()
        mutate(s)
        write_state(self.directory, s)
        return s

    def assertRestoreRefused(self, s: dict):
        self.assertTrue(consistency_issues(s), 'the clarified predicate must flag this tamper')
        durable = self.path.read_bytes()
        with self.assertRaises(ValueError):
            relay.load_state(self.path)
        with self.assertRaises(ValueError):
            relay.transact(self.directory, request_for(s['gateway'], 'n'))
        with self.assertRaises(ValueError):
            relay.regenerate_views(self.directory)
        self.assertEqual(durable, self.path.read_bytes(), 'rejected state must not be repaired or rewritten')
        self.assertQuiescent()

    def test_active_dangling_is_refused(self):
        def mutate(s):
            s['gateway']['active_request_id'] = 'zz'
        self.assertRestoreRefused(self.tampered(mutate))

    def test_orphan_dispatched_is_refused(self):
        def mutate(s):
            s['gateway']['cache']['y'] = receipt('y', DISPATCHED)  # active_request_id stays None
        self.assertRestoreRefused(self.tampered(mutate))

    def test_two_pending_is_refused(self):
        def mutate(s):
            s['gateway']['cache']['y'] = receipt('y', ADMITTED_PENDING)
            s['gateway']['cache']['z'] = receipt('z', ADMITTED_PENDING)
            s['gateway']['active_request_id'] = 'y'
        self.assertRestoreRefused(self.tampered(mutate))

    def test_stopped_with_pending_is_refused(self):
        def mutate(s):
            s['gateway']['cache']['y'] = receipt('y', ADMITTED_PENDING)
            s['gateway']['active_request_id'] = 'y'
            s['gateway']['stopped'] = True
        self.assertRestoreRefused(self.tampered(mutate))

    @unittest.expectedFailure
    def test_counter_skew_is_refused(self):
        """Finding N-2: gateway tick != sequence is accepted by Gateway.validate and load_state. Diff D-2."""
        def mutate(s):
            s['gateway']['tick'] += 1
        self.assertRestoreRefused(self.tampered(mutate))

    @unittest.expectedFailure
    def test_sim_skew_is_refused(self):
        """Finding N-2: a simulator transition without a verified receipt is not cross-checked. Diff D-2."""
        def mutate(s):
            s['tick'] += 1
            s['samples'].append(dict(s['samples'][-1]))
        self.assertRestoreRefused(self.tampered(mutate))

    @unittest.expectedFailure
    def test_false_verified_is_refused(self):
        """Finding N-2: a verified receipt with no committed transition is structurally valid. Diff D-2."""
        y = receipt('y', VERIFIED)
        interface.validate_receipt('y', y)  # guard: acceptance below is genuine, not a malformed receipt

        def mutate(s):
            s['gateway']['cache']['y'] = y
        self.assertRestoreRefused(self.tampered(mutate))

    def test_consistent_inflight_receipt_restores_blocks_and_is_resolved_from_durable_truth(self):
        """An operator-inserted dispatched receipt with matching identity is consistent: it loads,
        blocks new actions (INV_ONE_UNRESOLVED), is never relabelled by stop, and is resolved by
        the operator from durable truth (no committed transition => verified_failure, no advance).
        The relay has no CLI for this resolution (known, unimplemented); the Gateway API is used."""
        def mutate(s):
            s['gateway']['cache']['op1'] = receipt('op1', DISPATCHED)
            s['gateway']['active_request_id'] = 'op1'
        s = self.tampered(mutate)
        self.assertEqual([], consistency_issues(s))
        _, g = relay.load_state(self.path)
        self.assertEqual('op1', g.active_request_id)
        ev, s3 = self.step(request_for(s['gateway'], 'n'))
        self.assertEqual((REJECTED, 'command_pending'), (ev['receipt']['execution_status'], ev['receipt']['reason']))
        self.assertEqual('op1', read_packet(self.directory)['active_request']['request_id'])
        ev, s4 = self.step(request_for(s3['gateway'], 'st', action='stop'))
        self.assertEqual('op1', ev['receipt'].get('outstanding_request_id'))
        self.assertEqual(DISPATCHED, s4['gateway']['cache']['op1']['execution_status'])
        self.assertTrue(s4['gateway']['stopped'])
        with relay.writer_lock(self.directory):  # operator resolution under the writer lock
            s5, g = relay.load_state(self.path)
            self.assertNotIn('op1', sim_log(s5))  # durable truth: no committed transition for op1
            g.record_failure('op1', 'operator resolution: no committed transition for this dispatch in private_state')
            g.validate()
            s5['gateway'] = asdict(g)
            relay.atomic(self.path, relay.canonical(s5) + b'\n', True)
        s6 = self.state()
        self.assertConsistent(s6)
        self.assertStep(s4, s6)
        self.assertIsNone(s6['gateway']['active_request_id'])
        self.assertTrue(s6['gateway']['stopped'])
        self.assertEqual(s4['gateway']['sequence'], s6['gateway']['sequence'])
        relay.regenerate_views(self.directory)
        self.assertViewCurrent()
        self.assertQuiescent()


# --------------------------------------------------------------------------- Gateway API invariants

class GatewayApiInvariants(unittest.TestCase):
    def test_one_unresolved_slot_and_single_dispatch_authorization(self):
        g = interface.Gateway(SESSION)
        ra = g.admit(request_for(asdict(g), 'a'))
        self.assertEqual((ADMITTED_PENDING, True), (ra['execution_status'], ra['dispatch']))
        rb = g.admit(request_for(asdict(g), 'b'))
        self.assertEqual((REJECTED, 'command_pending'), (rb['execution_status'], rb['reason']))
        self.assertEqual('a', g.active_request_id)
        self.assertEqual(1, sum(1 for e in g.cache.values() if e['execution_status'] in interface.IN_FLIGHT))
        with self.assertRaises(ValueError):
            g.mark_dispatched('b')
        with self.assertRaises(ValueError):
            g.record_execution('a', 'coast')  # not dispatched yet
        g.mark_dispatched('a')
        with self.assertRaises(ValueError):
            g.mark_dispatched('a')  # the single authorization is consumed
        interface.Gateway.restore(asdict(g))

    def test_duplicate_replay_never_changes_state_in_any_status(self):
        scenarios = {}

        def fresh_with_a():
            g = interface.Gateway(SESSION)
            raw = request_for(asdict(g), 'a')
            g.admit(raw)
            return g, raw

        g, raw = fresh_with_a()
        scenarios[ADMITTED_PENDING] = (g, raw)
        g, raw = fresh_with_a()
        g.mark_dispatched('a')
        scenarios[DISPATCHED] = (g, raw)
        g, raw = fresh_with_a()
        g.mark_dispatched('a')
        g.record_execution('a', 'coast')
        scenarios[VERIFIED] = (g, raw)
        g, raw = fresh_with_a()
        g.mark_dispatched('a')
        g.record_failure('a', 'simulated failure')
        scenarios[VERIFIED_FAILURE] = (g, raw)
        g, raw = fresh_with_a()
        g.mark_dispatched('a')
        g.mark_unknown('a', 'simulated ambiguity')
        scenarios[UNKNOWN_OUTCOME] = (g, raw)
        g, raw = fresh_with_a()
        g.admit(request_for(asdict(g), 's', action='stop'))
        scenarios[CANCELLED] = (g, raw)
        g = interface.Gateway(SESSION)
        raw = request_for(asdict(g), 'x', sequence=9)
        g.admit(raw)
        scenarios[REJECTED] = (g, raw)
        g = interface.Gateway(SESSION)
        raw = request_for(asdict(g), 's', action='stop')
        g.admit(raw)
        scenarios[STOP_ACKNOWLEDGED] = (g, raw)
        self.assertEqual(set(interface.STATUSES), set(scenarios))
        for status, (g, raw) in scenarios.items():
            with self.subTest(status=status):
                before = asdict(g)
                view = g.admit(raw)
                self.assertEqual(before, asdict(g))
                self.assertTrue(view['duplicate'])
                self.assertFalse(view['dispatch'])
                self.assertEqual(status, view['execution_status'])
                interface.Gateway.restore(asdict(g))  # every reachable in-memory state is consistent

    def test_only_verified_transitions_advance_counters(self):
        g = interface.Gateway(SESSION)
        g.admit(request_for(asdict(g), 'a'))
        g.mark_dispatched('a')
        g.record_failure('a', 'simulated failure')
        self.assertEqual((0, 0, 'o0', None), (g.sequence, g.tick, g.observation_id, g.active_request_id))
        g.admit(request_for(asdict(g), 'b'))
        g.mark_dispatched('b')
        g.mark_unknown('b', 'simulated ambiguity')
        self.assertEqual('b', g.active_request_id)
        with self.assertRaises(ValueError):
            g.resolve_unknown('b', VERIFIED)  # a transition needs the explicit executed action
        with self.assertRaises(ValueError):
            g.resolve_unknown('b', VERIFIED_FAILURE, 'coast')  # a failure carries none
        g.resolve_unknown('b', VERIFIED_FAILURE)
        self.assertEqual((0, 0, None), (g.sequence, g.tick, g.active_request_id))
        g.admit(request_for(asdict(g), 'c'))
        g.mark_dispatched('c')
        g.mark_unknown('c', 'simulated ambiguity')
        g.resolve_unknown('c', VERIFIED, 'coast')
        self.assertEqual((1, 1, 'o1'), (g.sequence, g.tick, g.observation_id))
        g.admit(request_for(asdict(g), 'd'))
        g.mark_dispatched('d')
        with self.assertRaises(ValueError):
            g.record_execution('d', 'k1')  # substitution refused
        g.record_execution('d', 'coast')
        self.assertEqual((2, 2, 'o2', None), (g.sequence, g.tick, g.observation_id, g.active_request_id))
        self.assertEqual(2, sum(1 for e in g.cache.values() if e['execution_status'] == VERIFIED))
        interface.Gateway.restore(asdict(g))


if __name__ == '__main__':
    unittest.main()
```

FILE: docs/gateway_lifecycle_v1/CONFORMANCE_NOTE.md
```markdown
# gateway-conformance-004 — model-checker traces vs. the integrated implementation

Prose CC-BY-4.0; code MIT. Claude (Anthropic), coordinated by Red for Richard (Andrei) Pemberton.
Inputs: wave-10 model checker and its sandbox receipts (Claude via Red); `interface.py` sha256
`559d4a22…`, `relay.py` sha256 `51b7a663…` (Lily original; Coda lifecycle; Claude Fable 5.1 draft;
Claude integration-003); INTEGRATION_NOTE.md; DESIGN.md (Coda). **Static reasoning only; nothing executed
by the author.** Not a safety certification, not a hardware recommendation.

## Mapping of model actions to the implementation
begin/recover = `load_state` (strict `Gateway.restore`) at the start of every `transact`;
admit…commit_ok = one `transact`; crash before replacement = `os.replace` of `private_state.json`
raises (nothing replaced; D3 removes the temp file); `commit_ambiguous(replaced=True)` = `os.replace`
succeeds then raises; export_fail = `export` raises after commit → `ExportAfterCommitError`;
compute_fail = `candidate_transition` raises → `record_failure`; tamper = edit of the test's own
`private_state.json`; hard crash with lock held = dead `writer.lock`, removed by the operator.
Simulator truth = `s['tick']`, `s['samples']`, and the executed events (one per verified transition).
Not expressible: `persist_unknown_blind`, `resolve_unknown_trusted` (the relay writes nothing after a
failed replacement and never re-reads inside a transaction), API interleaving inside a transaction.

## Findings
**C1-b (decision, no diff).** The relay's `mark_dispatched` is in-memory; the relay docstring states the
consequence (crash before replacement ⇒ no record, no action; replay is fresh). This is the checker's
C1 option (b). The model's ghost INV_NO_DOUBLE_DISPATCH does not hold and is not claimed; the declared
substitute (no record ⇒ no transition; committed dispatch never repeats) is tested. DESIGN.md should
add the one sentence; a durable mark (option a) would add a replacement per step and a restore rule.

**N-1 (minor non-conformance to C2 / view currency).** After an ambiguous replacement (file replaced,
exception observed) `transact` raises a bare `OSError` — the type INTEGRATION_NOTE reserves for
"nothing happened" — while the step IS committed, the lock is released and `packet.json` is stale.
Durable invariants hold; the next transaction re-reads the file and refreshes the view, so no false
outcome and no replay can follow. Diff D-1 implements C2's "re-read before deciding":

```diff
--- src/relay.py
+++ src/relay.py
@@ def transact(directory, request_bytes=None, advance=False):
-        atomic(path, canonical(s) + b'\n', True)
+        data = canonical(s) + b'\n'
+        try:
+            atomic(path, data, True)
+        except Exception:
+            # C2: an exception around the replacement is ambiguous. The file is the truth; re-read it
+            # before deciding anything and never write memory back. Not replaced => nothing happened.
+            if path.read_bytes() != data:
+                raise
+            # replaced => the step IS committed; continue to regenerate the views.
         _export_after_commit(s, directory, event)
```
Risk: low (a pre-commit failure still raises unchanged). Test: `test_export_view_is_current_after_an_
ambiguous_replacement` (expectedFailure) becomes an unexpected success → remove the decorator.

**N-2 (partial conformance to C4).** `Gateway.validate` checks receipt structure, in-flight count,
active identity and stop/pending; it does not cross-check counters, and `load_state` does not compare
the gateway with simulator truth. Tampers `counter_skew`, `sim_skew`, `false_verified` load. Diff D-2:

```diff
--- src/relay.py
+++ src/relay.py
@@ def load_state(path: Path):
-    return s, Gateway.restore(s['gateway'])
+    g = Gateway.restore(s['gateway'])
+    _check_counters(s, g)
+    return s, g
+
+
+def _check_counters(s, g):
+    """C4 cross-check: gateway counters == verified receipts == simulator tick; samples per tick. Never repairs."""
+    verified = sum(1 for e in g.cache.values() if e['execution_status'] == VERIFIED_SIMULATOR_TRANSITION)
+    expected_tick = s['episode'] * s['cfg']['steps_per_episode'] + s['tick']
+    if not (g.sequence == g.tick == verified == expected_tick) or len(s['samples']) != s['tick'] + 1:
+        raise ValueError('Inconsistent private state: gateway counters %r, verified receipts %d, simulator '
+                         'tick %d, samples %d disagree; refusing to load' %
+                         ((g.sequence, g.tick), verified, expected_tick, len(s['samples'])))
```
Risk: medium — any existing fixture that hand-builds `private_state.json` with inconsistent counters
would start failing (intended), and migrated legacy state must satisfy the equalities (it should: the
legacy gateway advanced `sequence`/`tick` once per verified receipt and the cache never evicts).
An optional `sequence == tick` check in `Gateway.validate` is not proposed: it may break lifecycle
fixtures that construct gateways with counters but no receipts. Tests: the three expectedFailure
tamper tests become unexpected successes → remove the decorators.

**O-2 (observation).** A stop whose commit fails is "nothing happened"; the operator sees the error and
retries. Same loss exists in the model (crash before persist). No change proposed.

## Predicted run (static)
20 tests: 16 pass, 4 expected failures (N-1: 1, N-2: 3), 0 failures/errors, alongside the existing 108.
Highest-risk predictions: (1) the import bootstrap finds `src/` (tests/ and src/ as siblings assumed);
(2) `event == public_events[-1]` relies on exact JSON round-trip through `canonical` (already relied on
by existing tests); (3) `init(..., allow_frozen_seed=True)` with seed 20000.

## Assumptions and scope
Single episode in all relay tests; one stop id per scenario; ambiguous failure modelled only for the
transition commit; `canonical` is deterministic bytes. Left unimplemented: relay CLI for unknown-outcome
resolution (known gap), episode-advance conformance, parser/JSON-depth boundary, multi-session checks.
```

## 3. How Red should run it

```
python -m unittest -v tests.test_gateway_conformance
python -m unittest discover -s tests -v     # alongside the existing 108
```

If `relay`/`interface` are not importable from the repo root, the module searches `src/` next to and above `tests/`; failure to import is itself a finding to send back. Any test outside the four `@expectedFailure` ones that fails is either a conformance defect I mis-predicted or a harness assumption (listed above) that the sandbox layout violates — please return the full traceback and I will correct.

## 4. Left unimplemented (explicit)

- Conformance of `next-episode` (`_advance_episode`) to the counter predicate across episodes (predicate written, not exercised).
- A relay CLI for unknown-outcome resolution (known gap in the integration note); the test performs the operator resolution with the Gateway API under the writer lock.
- Replay of the model's eight seeded-bug variants against the implementation (they are checker self-tests, not design traces).
- Applying diffs D-1/D-2 to the source files (proposed only; Coda/Richard decide; D-2 may require fixture adjustments).