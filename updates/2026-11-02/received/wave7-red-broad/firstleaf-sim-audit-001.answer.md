# Audit report — TASK firstleaf-sim-audit-001

**Author of this contribution:** Claude (Anthropic), working for Red, who coordinates for Richard (Andrei) Pemberton. **Method:** static reading of the verbatim sources in the bundle only. **Nothing below was executed by me**; every "actual" behaviour is derived from the code text, every test outcome is a prediction, and Red's sandbox run is the arbiter.

**Prior work I rely on and credit:** the original simulator, gateway, relay, and tests are Lilitari's (per `COVERAGE_AND_ATTRIBUTION.md` and `SCOPE_GAP.md`); the standalone-Gateway pending-admission/stop defects and the RecursionError parser-boundary witness are Coda's (`SCOPE_GAP.md`). Red's note mentions earlier "Claude Fable 5.1" contributions "identified in the sources"; I found no explicit such attribution in the supplied bundle, so I attribute nothing to that name here.

---

## 0. Verdict in one paragraph

Against its own brief the simulator and relay are **dynamically consistent**: both implement `v' = 0.75·v + b[a]`, `p' = p + 0.1·v'`, coast = zero actuator, bounded uniform noise (`0.01`, `0.03`), two-tick delivery delay with the sample labelled by `(episode, sample_tick)`, and the episode-indexed mapping/gain change via the shared `body_vectors`. By static reasoning the relay and `Episode` should produce **bit-identical** states and samples for the same action sequence (control test C1). I found **no direct leak** of mapping, noise, negative labels, seed, or true state through the packet, receipts, event ledger, file names, or error strings; `packet()` reads only public-by-design fields (control test C2). Idempotency (same ID + same content never re-dispatches; changed content with a reused ID is rejected) and the stop latch hold in the serial relay, including across process restarts and the episode-complete override (C3, C4). The commit point is a single `os.replace` of `private_state.json` preceded by nothing persistent and followed only by regenerable views (C5). The definite defects are in the periphery: an **un-logged exception path** (Medium; relay-level consequence of Coda's parser-boundary finding), **non-identifying rejection receipts**, **temp-file residue on failed writes**, an **owner-less writer lock**, **duplicated protocol constants**, and a **missing fresh-seed guard**. One ambiguity in the task statement: the task lists "target" as evaluator-only, but the package deliberately publishes `goal` ("the policy sees … the target", module docstring; `MODEL_BRIEF.md`). Red should confirm which is intended; I treated `goal` as public by design.

---

## 1. Findings, ranked by severity

Severity scale: High (wrong truth to candidate / leak / silent double-advance), Medium (process-integrity defect that breaks a stated guarantee), Low (hygiene, latent, or recoverable). "Definite" = contradicts the code's own brief/README/protocol by static reading. "Design question" = not a contradiction, but a choice worth a coordinator decision.

### F1 — Medium, definite (relay) · Decoder failures outside the ValueError boundary leave no durable receipt
*Prior identification: Coda, `SCOPE_GAP.md` (6,000-level witness raised `RecursionError`; "missing-receipt consequence remains supported by source control flow"). Independently confirmed here by control-flow reading; two reproductions given.*

- **Where:** `relay.py` `transact`, `except (ValueError, UnicodeError) as exc:`; `interface.py` `parse_request` has no nesting guard.
- **Reproduction (deterministic):** `init(d, 20000, 'x')`; monkeypatch `interface.Gateway.admit` to raise `RecursionError`; `transact(d, <any valid request bytes>)`.
- **Reproduction (decoder-dependent):** `transact(d, b'[' * 8000 + b']' * 8000)` — 16,000 bytes, so it passes the 16 KiB check. Whether CPython raises `RecursionError`, accepts the nesting and then raises `ValueError("Request has missing or undeclared fields")` (list, not dict), or overflows the C stack depends on the interpreter's C-recursion limit. Coda reports `RecursionError` at 6,000 levels on her runtime while 1,200 did not trigger it. **Assumption-free statement:** I do not know which outcome Red's runtime produces; the child-process test reports it.
- **Expected (brief/README):** "Requests may be rejected … A receipt … establishes whether the simulator committed"; run manifests must record "all attempts". Every attempt should yield a `rejected_invalid_request` event, state unchanged.
- **Actual (code):** any non-`ValueError`/`UnicodeError` exception propagates out of `with writer_lock(...)`; the lock is removed by `finally`, `atomic`/`export` never run, `events.jsonl` is unchanged, the CLI prints a traceback and exits non-zero. State is *not* corrupted (no partial commit), so this is a ledger-completeness defect, not an advance defect.
- **Patch:** `interface.py` byte-level nesting pre-check (raises `ValueError("Request nesting too deep")` before `json.loads` can recurse) **and** `relay.py` `except Exception` fallback that logs a fixed reason plus `error_type`. Both hunks are small.

### F2 — Medium, definite (standalone `Gateway` contract; no relay impact while serial) · Pending admission is not exclusive; stop does not revoke a pending admission
*Prior identification: Coda, `SCOPE_GAP.md`. Reproduced, credited, **not patched here** — SCOPE_GAP correctly argues a lifecycle redesign needs coordinator agreement.*

- **Reproduction:** `g = Gateway('test'); g.admit(req('r0','k0')); r = g.admit(req('r1','k1'))` → `r['dispatch'] is True` (expected: blocked while `r0` is pending). `g.admit(req('r2','stop')); g.record_execution('r0','k0')` succeeds (expected: `ValueError`).
- **Why the relay is unaffected today:** `transact` performs `admit` → simulate → `record_execution` inside one lock hold, so no pending window is observable. Any future caller that separates admission from execution inherits the defect.

### F3 — Low–Medium, definite · Rejection events do not identify the rejected request
- **Where:** `relay.py` `transact`, `event.update({'event': 'rejected_invalid_request', 'reason': str(exc), 'executed': False})`.
- **Reproduction:** `transact(d, b'{bad')` → event has no hash/length of the bytes. `transact(d, r0:k0)` (executes), then `transact(d, r0:k1)` → event reason `"Request ID reused with different content"` with **no** request ID and no bytes hash.
- **Expected:** README: keep a manifest of "all attempts"; `MODEL_BRIEF.md`: "A changed request must use a new ID" — the ledger should show *which* ID/bytes were refused so an operator can correlate with the saved `action.json`.
- **Actual:** the only identification is a free-text `reason`; also the `executed` key exists only on invalid-request rejections, not on admitted-but-not-dispatched receipts (schema inconsistency).
- **Patch:** record `request_bytes_sha256`, `request_bytes_len`, `error_type` on every request event; add `executed: bool` to every `action_receipt` event. (Note the existing `request_sha256` inside receipts hashes the *canonical parsed* JSON, not the bytes — correct for duplicate detection, but a manifest that hashes `action.json` cannot match it. See DQ3.)

### F4 — Low, definite · `atomic()` leaves temporary files (including a full private-state copy) on a failed write/replace or hard crash
- **Where:** `relay.py` `atomic`.
- **Reproduction:** make `os.replace` raise for `private_state.json` (or SIGKILL between `fsync` and `replace`); then list `d/*.tmp` → `private_state.json.<uuid>.tmp` (mode 0600, containing the *new* private state) remains; `packet.json.<uuid>.tmp`/`events.jsonl.<uuid>.tmp` (0644) likewise if the failure is later.
- **Expected (relay docstring):** "Atomic state replacement is the virtual commit point" — a failed commit should leave nothing but the committed file.
- **Actual:** no cleanup path; no recovery command sweeps residue; README recovery notes mention only `writer.lock`. The private copy is 0600 (POSIX only — on Windows the mode argument is ignored), so this is a custody-hygiene risk inside the session directory rather than a candidate-visible leak.
- **Patch:** unlink the temp file on any exception and re-raise. Hard-crash residue still needs an operator sweep; recommend adding "remove stale `*.tmp`" to the README recovery steps.

### F5 — Low, definite · `writer_lock` has no owner identity and releases unconditionally
- **Where:** `relay.py` `writer_lock`: empty lock file; `finally: lock.unlink(missing_ok=True)`.
- **Reproduction:** A: `cm_a = writer_lock(d); cm_a.__enter__()`; operator removes `writer.lock` believing it stale; B: `cm_b = writer_lock(d); cm_b.__enter__()`; A exits → **B's lock is deleted**; C can now acquire while B is still writing. Also `cat writer.lock` is empty, so the README instruction "check for a live writer" cannot be performed from the lock.
- **Patch:** write `pid=… token=…` into the lock; on release unlink only if the content still equals this writer's token.

### F6 — Low, definite-latent · Relay duplicates protocol constants as literals
- **Where:** `relay.py` `packet` (`'dt': .1, 'velocity_retention': .75`, `.01`, `.03`, `'delay_ticks': 2`), `transact` (`.75 *`, `.1 *`, `s['tick'] - 2`, `s['samples'][-3:]`).
- **Reproduction:** change `cfg.dynamics.alpha` to `0.5` (in `inputs/protocol.json` before `init`, or in the embedded `private_state.json`); the packet still tells the candidate `0.75`, and `transact` still integrates with `0.75`, while `body_vectors`, `sample()` and the simulator read `cfg`.
- **Expected:** the relay's statements to the candidate and its dynamics should be the protocol's (`cfg["dynamics"]`, `cfg["observations"]`, `cfg["profiles"]["primary"]["delay"]`). Today the literals happen to equal the protocol, so **no present untruth**, but the invariant is unprotected and the two codebases (simulator vs relay) can silently diverge.
- **Patch:** read from `s['cfg']`.

### F7 — Low, definite missing guard (also a design question) · `init` accepts frozen development/evaluation seeds; the default seed is a fixed constant
- **Where:** `relay.py` `init`, `main` (`--seed` default `20000`).
- **Reproduction:** `init(d, 10000, 'x')` succeeds. `10000 = evaluation_seeds.first`: this fixture is published in `inputs/evaluation_fixtures.jsonl.gz` and has a full raw witness trace in `results/`. A candidate that saw those files knows the mapping and every noise draw.
- **Expected (README):** "Model-facing trial seeds must be fresh relative to any fixture or score material the candidate has already seen."
- **Actual:** no check; and a fixed default means every operator using defaults reuses the *same* fixture (any prior session's `events.jsonl` reveals its mapping behaviourally).
- **Patch:** refuse seeds inside the two frozen ranges unless `--allow-frozen-seed`. The default-seed question is left to the coordinator (see DQ2).

### Design questions (not defects)

- **DQ1 — Final delayed samples of the last episode (and of a stopped/un-advanced episode) are never delivered.** `Episode.finish()` drains samples 79–80 into every baseline agent; the relay only surfaces them via `operator_episode_reset.final_sensor_samples`, which cannot occur after episode 5 ("No further episode") or after a stop. Baselines and a relayed candidate therefore see slightly different evidence at the end. Option: include `pending_sensor_samples` in the packet when `episode_complete` or `stopped`.
- **DQ2 — `goal` (and the exact-zero-state first sample of each episode) is a deterministic fingerprint of a small-integer seed.** With the generator (source) in hand, brute-forcing the seed from one `goal` value recovers the entire fixture, including future noise and `mapping_B`. This is exactly the custody boundary the README already states (source must stay out of the candidate's reach). A cheap hardening that does not depend on custody: use a high-entropy session seed (e.g., 128-bit) recorded only in `private_state.json`; reproducibility is preserved because `fixture.seed` is stored. Not patched; coordinator choice.
- **DQ3 — `request_sha256` is a hash of the canonical *parsed* request.** Correct for duplicate detection (two byte-encodings of the same object are the same request), but should be documented; F3's `request_bytes_sha256` gives the manifest-matchable value.
- **DQ4 — Two clocks in one event.** `source_dispatch_tick` is the gateway's cumulative tick; `executed_transition_source_tick` is the per-episode tick. Both are correct; the names could say so. Duplicate receipts replay the *original* `stop_latched`; `observation_id` alternates between `o{tick}` and `o{tick}-episode{n}`. Harmless (no collisions: gateway tick is cumulative).
- **DQ5 — Post-commit `export` failure surfaces as a CLI error although the transition is committed.** Idempotency makes the operator's retry a truthful duplicate receipt (control test C5), so this is acceptable, but the CLI could report `committed=True, export_failed=True`.
- **DQ6 — Durability/platform.** No directory fsync after `os.replace` (power-loss window); `0o600` is advisory on Windows.
- **DQ7 — CLI `step` reads the whole request file before the 16 KiB check.** Operator-side only.
- **DQ8 — "target" in the task's evaluator-only list** vs the package's deliberate publication of `goal`. Needs confirmation.

---

## 2. Separation walk-through (what the candidate can see, and where it comes from)

| Candidate-visible item | Source in `private_state.json` | Evaluator-only? |
|---|---|---|
| `packet.sensor`, `event.observed_sensor`, `final_sensor_samples` | `samples[k]` = true state + bounded noise, labelled `episode`, `sample_tick` | No (by design; delayed, noisy) |
| `packet.goal` | `fixture.goals[episode]` (current episode only) | Public by design (see DQ8/DQ2) |
| `sequence`, `observation_id`, `dispatch_tick`, `expires_tick` | gateway counters | No |
| `known_dynamics`, `sensor_contract` | literals (F6) | No |
| `recent_events` / `events.jsonl` | receipts, sensors, operator resets, `actor_label_operator_reported` | No |
| `reason` strings | gateway/`json` error text about the candidate's own bytes | No |
| file names | fixed names + `uuid4` temp names + operator-chosen directory | No |
| timing | none recorded; turn-based; file mtimes show operator cadence only | No |
| exception paths | tracebacks to operator stderr; no locals printed | No (but F1: un-logged) |
| never exported | `fixture.mapping_A/B`, `unit_noise`, `negative_labels`, `seed`, `cfg.body_schedule`, gains, true `p`/`v`, gateway cache | — |

`packet()` touches only `tick`, `episode`, `samples`, `public_events`, `gateway`, `cfg.profiles.primary.delay`, `cfg.steps_per_episode`, `fixture.goals[episode]` (C2 proves this structurally by feeding a redacted state).

## 3. Correctness walk-through (dynamics parity argument)

Simulator: `v = alpha*v + true_b[a]; p = p + dt*v`; sample `p + (1.0*0.01)*n[j]`, `v + (1.0*0.03)*n[j+2]`, `unit_noise[ep][tick]`, delivered index `max(0, t-2)`. Relay: `.75*v + b[a]; p + .1*v`; sample `p + n[j]*0.01`, `v + n[j+2]*0.03`, same noise index, same delivered index. `alpha`/`dt` from JSON equal the literals exactly; IEEE multiplication is commutative, so `0.01*n == n*0.01` bit-for-bit; JSON round-trips of floats are exact; `body_vectors` is shared. Hence identical action sequences give identical `p`, `v`, and samples (C1). Mapping/gain change: `body_vectors(cfg, fx, episode, primary)` with `body_schedule = [A,A,A,B,B,A]` → episodes 3–4 use `mapping_B` and `gain_B_x/y` (control test with operator-side state surgery). Probe schedule, `MeanModel` window semantics, `finish()` drain, `misaligned`/`shuffled` labelling, and checkpoint restore were read and found consistent with the protocol text; no defect found there.

---

## 4. Test module (run against the ORIGINAL code first)

Place beside the existing tests; run from the package root. `test_control_*` should PASS on the original; `test_finding_D*` should FAIL on the original and PASS after the patches; `test_prior_finding_*` reproduce Coda's findings and remain FAILING (unpatched by design). Deviation from the "no file writes" convention: like the package's own `test_relay.py`, sessions are created in a `tempfile.TemporaryDirectory` (override location with `AUDIT_TMPDIR`), cleaned up afterwards. `os.fsync` is patched to a no-op inside the parent process for speed (durability is not under test; SCOPE_GAP reports relay tests exceeding 60 s on slow disks).

FILE: tests/test_audit_first_leaf.py
```python
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
```

---

## 5. Patches (unified diffs, separate from tests)

Apply from the original package root: `patch -p1 --dry-run < patches/interface.py.diff && patch -p1 < patches/interface.py.diff`, same for `relay.py.diff`. Hunk bodies were derived from the verbatim bundle text; if the on-disk files differ in whitespace the hunks may need fuzz, and each hunk is labelled with its finding so manual application is unambiguous. The two existing suites (`test_stage.py`, `test_relay.py`) should remain green by static reading (the seed used there, 20000, is outside the frozen ranges; the nesting pre-check only rejects inputs the existing tests never send).

FILE: patches/interface.py.diff
```diff
--- a/src/interface.py
+++ b/src/interface.py
@@ -12,10 +12,32 @@
 ACTIONS = ("k0", "k1", "k2", "k3", "coast", "stop")
 FIELDS = {"schema", "request_id", "session_id", "body_revision", "sequence",
           "observation_id", "expires_tick", "action"}
+MAX_NESTING = 16  # a valid request is one flat object; deep nesting is never legitimate
+
+def _check_nesting(raw: bytes) -> None:
+    """Reject deeply nested JSON before the decoder can recurse (ValueError, never RecursionError)."""
+    depth, in_string, escaped = 0, False, False
+    for byte in raw:
+        if in_string:
+            if escaped:
+                escaped = False
+            elif byte == 0x5C:  # backslash
+                escaped = True
+            elif byte == 0x22:  # double quote
+                in_string = False
+        elif byte == 0x22:
+            in_string = True
+        elif byte in (0x5B, 0x7B):  # [ or {
+            depth += 1
+            if depth > MAX_NESTING:
+                raise ValueError("Request nesting too deep")
+        elif byte in (0x5D, 0x7D):  # ] or }
+            depth = max(0, depth - 1)
 
 def parse_request(raw: bytes) -> dict[str, Any]:
     if len(raw) > 16384:
         raise ValueError("Request exceeds 16 KiB")
+    _check_nesting(raw)
     def pairs(items):
         obj = {}
         for k, v in items:
```

FILE: patches/relay.py.diff
```diff
--- a/src/relay.py
+++ b/src/relay.py
@@ -11,6 +11,7 @@
 import argparse
 from contextlib import contextmanager
 from dataclasses import asdict
+import hashlib
 import json
 import math
 import os
@@ -23,25 +24,42 @@
 def atomic(path: Path, data: bytes, private: bool = False) -> None:
     tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
     fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600 if private else 0o644)
-    with os.fdopen(fd, 'wb') as f:
-        f.write(data)
-        f.flush()
-        os.fsync(f.fileno())
-    os.replace(tmp, path)
+    try:
+        with os.fdopen(fd, 'wb') as f:
+            f.write(data)
+            f.flush()
+            os.fsync(f.fileno())
+        os.replace(tmp, path)
+    except BaseException:
+        # D3: a failed write must not leave a stray (possibly private) temporary copy behind.
+        try:
+            os.unlink(tmp)
+        except FileNotFoundError:
+            pass
+        raise
 
 
 @contextmanager
 def writer_lock(directory: Path):
     lock = directory / 'writer.lock'
+    token = f'pid={os.getpid()} token={uuid.uuid4().hex}\n'.encode()
     try:
         fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
     except FileExistsError:
         raise RuntimeError('Existing writer lock: check for a live writer or interrupted operation before recovery.')
-    os.close(fd)
+    try:
+        os.write(fd, token)
+    finally:
+        os.close(fd)
     try:
         yield
     finally:
-        lock.unlink(missing_ok=True)
+        # D4: release only a lock this writer still owns; a recreated lock belongs to another writer.
+        try:
+            if lock.read_bytes() == token:
+                lock.unlink()
+        except FileNotFoundError:
+            pass
 
 
 def sample(s):
@@ -54,15 +72,19 @@
 
 def packet(s):
     g = s['gateway']
-    sensor_tick = max(0, s['tick'] - s['cfg']['profiles']['primary']['delay'])
+    dyn, obs = s['cfg']['dynamics'], s['cfg']['observations']
+    delay = s['cfg']['profiles']['primary']['delay']
+    sensor_tick = max(0, s['tick'] - delay)
     return {'schema': 'stage.observation.v1', 'session_id': g['session_id'],
             'body_revision': g['body_revision'], 'sequence': g['sequence'],
             'observation_id': g['observation_id'], 'dispatch_tick': g['tick'],
             'sensor': s['samples'][sensor_tick], 'episode': s['episode'],
             'goal': s['fixture']['goals'][s['episode']],
-            'known_dynamics': {'dt': .1, 'velocity_retention': .75},
-            'sensor_contract': {'position_noise_bound': .01, 'velocity_noise_bound': .03,
-                                'delay_ticks': 2, 'actuator_mapping': 'unknown and may change'},
+            # D5: state the protocol's actual constants rather than duplicated literals.
+            'known_dynamics': {'dt': dyn['dt'], 'velocity_retention': dyn['alpha']},
+            'sensor_contract': {'position_noise_bound': obs['position_noise_scale'],
+                                'velocity_noise_bound': obs['velocity_noise_scale'],
+                                'delay_ticks': delay, 'actuator_mapping': 'unknown and may change'},
             'actions': list(ACTIONS), 'stopped': g['stopped'],
             'episode_complete': s['tick'] >= s['cfg']['steps_per_episode'],
             'recent_events': s['public_events'][-12:],
@@ -77,13 +99,24 @@
     atomic(directory / 'events.jsonl', b''.join(canonical(r) + b'\n' for r in s['public_events']))
 
 
-def init(directory, seed, actor):
+def frozen_seed_ranges(cfg):
+    for split in ('development', 'evaluation'):
+        spec = cfg[f'{split}_seeds']
+        yield split, range(spec['first'], spec['first'] + spec['count'])
+
+
+def init(directory, seed, actor, allow_frozen_seed=False):
     directory.mkdir(parents=True, exist_ok=True)
     with writer_lock(directory):
         path = directory / 'private_state.json'
         if path.exists():
             raise ValueError('Session already exists; refusing overwrite')
         cfg = load_protocol()
+        for split, seeds in frozen_seed_ranges(cfg):
+            if seed in seeds and not allow_frozen_seed:
+                # D6: a frozen development/evaluation fixture is published material, not a fresh trial.
+                raise ValueError(f'Seed {seed} is in the frozen {split} fixture range; '
+                                 'model-facing seeds must be fresh')
         s = {'schema': 'stage.relay.private.v1', 'actor_label_operator_reported': actor,
              'cfg': cfg, 'fixture': fixture(seed, cfg), 'episode': 0, 'tick': 0,
              'p': [0., 0.], 'v': [0., 0.], 'public_events': [],
@@ -99,45 +132,57 @@
         path = directory / 'private_state.json'
         s = json.loads(path.read_bytes())
         g = Gateway(**s['gateway'])
+        dyn, delay = s['cfg']['dynamics'], s['cfg']['profiles']['primary']['delay']
         event = {'actor_label_operator_reported': s['actor_label_operator_reported'],
                  'episode': s['episode'], 'source_dispatch_tick': g.tick}
         if advance:
             if g.stopped or s['tick'] != s['cfg']['steps_per_episode']:
                 raise ValueError('Only an unstopped completed episode can advance')
             if s['episode'] + 1 >= s['cfg']['episodes']:
                 raise ValueError('No further episode in this protocol')
             # Make the final delayed samples available before reset.
             event.update({'event': 'operator_episode_reset',
-                          'final_sensor_samples': s['samples'][-3:],
+                          'final_sensor_samples': s['samples'][-(delay + 1):],
                           'operator_intervention': True})
             s['episode'] += 1
             s['tick'], s['p'], s['v'] = 0, [0., 0.], [0., 0.]
             s['samples'] = [sample(s)]
             g.observation_id = f'o{g.tick}-episode{s["episode"]}'
         else:
             if request_bytes is None:
                 raise ValueError('Missing request')
+            # D2: every attempt is identifiable in the ledger by the exact bytes the operator applied.
+            event['request_bytes_sha256'] = hashlib.sha256(request_bytes).hexdigest()
+            event['request_bytes_len'] = len(request_bytes)
             try:
                 receipt = g.admit(request_bytes)
             except (ValueError, UnicodeError) as exc:
                 event.update({'event': 'rejected_invalid_request', 'reason': str(exc),
-                              'executed': False})
+                              'error_type': type(exc).__name__, 'executed': False})
+            except Exception as exc:
+                # D1: a decoder failure outside the ValueError boundary (e.g. RecursionError) is
+                # still a rejection and still gets a durable receipt; no state has been touched.
+                event.update({'event': 'rejected_invalid_request',
+                              'reason': 'Request could not be decoded within gateway limits',
+                              'error_type': type(exc).__name__, 'executed': False})
             else:
                 if receipt['dispatch'] and s['tick'] >= s['cfg']['steps_per_episode']:
                     receipt.update({'admitted': False, 'dispatch': False, 'reason': 'episode_complete'})
                     g.cache[receipt['request_id']] = receipt
-                event.update({'event': 'action_receipt', 'receipt': receipt})
+                event.update({'event': 'action_receipt', 'receipt': receipt, 'executed': False})
                 if receipt['dispatch']:
                     a = ACTIONS.index(receipt['requested_action'])
                     b = body_vectors(s['cfg'], s['fixture'], s['episode'], s['cfg']['profiles']['primary'])
-                    s['v'] = [.75 * s['v'][j] + b[a][j] for j in range(2)]
-                    s['p'] = [s['p'][j] + .1 * s['v'][j] for j in range(2)]
+                    # D5: the same constants the simulator uses, read from the embedded protocol.
+                    s['v'] = [dyn['alpha'] * s['v'][j] + b[a][j] for j in range(2)]
+                    s['p'] = [s['p'][j] + dyn['dt'] * s['v'][j] for j in range(2)]
                     s['tick'] += 1
                     s['samples'].append(sample(s))
                     g.record_execution(receipt['request_id'], receipt['requested_action'])
                     event['receipt'] = dict(g.cache[receipt['request_id']])
+                    event['executed'] = True
                     event['executed_transition_source_tick'] = s['tick'] - 1
-                    event['observed_sensor'] = s['samples'][max(0, s['tick'] - 2)]
+                    event['observed_sensor'] = s['samples'][max(0, s['tick'] - delay)]
         s['gateway'] = asdict(g)
         s['public_events'].append(event)
         # Nothing external is actuated. This saved state defines the committed simulation.
@@ -153,15 +198,17 @@
     start.add_argument('--directory', type=Path, required=True)
     start.add_argument('--seed', type=int, default=20000)
     start.add_argument('--actor-label', required=True)
+    start.add_argument('--allow-frozen-seed', action='store_true',
+                       help='permit a seed inside the frozen development/evaluation ranges (not model-facing)')
     act = sub.add_parser('step')
     act.add_argument('--directory', type=Path, required=True)
     act.add_argument('--request', type=Path, required=True)
     for name in ['next-episode', 'export']:
         q = sub.add_parser(name)
         q.add_argument('--directory', type=Path, required=True)
     args = p.parse_args()
     if args.command == 'init':
-        result = init(args.directory, args.seed, args.actor_label)
+        result = init(args.directory, args.seed, args.actor_label, args.allow_frozen_seed)
     elif args.command == 'step':
         result = transact(args.directory, args.request.read_bytes())
     elif args.command == 'next-episode':
```

---

## 6. Predicted outcomes for Red's run (static predictions, not results)

| Test | Original | After both patches |
|---|---|---|
| 6 × `test_control_*` | PASS | PASS |
| `test_finding_D1_non_valueerror_from_admit_is_still_logged` | FAIL | PASS |
| `test_finding_D1_deep_nesting_probe_in_child_process` | FAIL if the runtime raises `RecursionError`/crashes at depth 8000 (Coda's runtime did at 6000); PASS if the decoder tolerates it (non-reproduction on that runtime — report it) | PASS |
| `test_finding_D2_*`, `D3_*`, `D4a_*`, `D4b_*`, `D5_*`, `D6_*` | FAIL | PASS |
| 2 × `test_prior_finding_*` (Coda, Gateway) | FAIL | FAIL (intentionally unpatched) |
| existing `tests/test_stage.py`, `tests/test_relay.py` | PASS (per package) | PASS (predicted) |

If a `test_control_*` fails, that is itself a new finding and I would want the assertion text and the first differing values.

## 7. Assumptions, limits, unimplemented

- **Assumptions:** the bundle text is byte-faithful to the files (hunks depend on it); CPython ≥ 3.10; POSIX semantics for `0o600`/`os.replace`; `random` draw order stable across the tested interpreters (the package already relies on this). Depth-8000 behaviour is explicitly runtime-dependent.
- **Not changed, by choice:** F2/SCOPE_GAP lifecycle (`admitted_pending`/`dispatched`/`cancelled_before_dispatch`/`unknown_outcome`) — needs coordinator-agreed outcome-resolution rules; DQ1 pending-sample delivery; DQ2 high-entropy session seed; DQ5 CLI reporting of post-commit export failure; README text additions (stale `*.tmp` sweep, lock-token check, `--allow-frozen-seed`).
- **Not audited:** `check_package.py`, `reproduce.py`, `verify_runs.py`, analysis/bootstrap code, the optional MuJoCo files — not in the bundle.
- **Scope statement:** private computational research on a model; not empirical validation, not a safety certification, not a hardware design recommendation, not a public release.