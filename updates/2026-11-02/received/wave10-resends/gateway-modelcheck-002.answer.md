# gateway-modelcheck-001 — independent design verification of GW-ASYNC0

Red (Claude, Anthropic), coordinating with Richard Pemberton. Design under review: GW-ASYNC0 `DESIGN.md`/`PLAN.md` by Coda (Codex Lily), implementing Lily's reviewed lifecycle; original `interface.py`/`relay.py` by Lilitari (Lily) via ChatGPT, MIT. Earlier Claude Fable 5.1 contributions are not among the verbatim sources for this task, so none are cited here.

**Status of everything below:** static reasoning only. I have executed nothing and read no files beyond the verbatim bundle. All "predicted" counterexample lengths and the "no violations" claim for the clarified baseline are predictions that Red's sandbox run will confirm or correct. This is model verification of a design, not empirical validation, not a safety certification, and not a hardware recommendation. No hardware actuation is modelled or proposed.

Deliverable layout (every file self-contained, stdlib only, deterministic, no network, writes only to a caller-supplied `--output` path):

- `MODEL.md` — (a) abstract state model, (c) predicted counterexamples + smallest clarifications, (e) mapping to `interface.py`/`relay.py`, assumptions, unimplemented list.
- `gateway_modelcheck/model.py` — state, configuration/variants, successor relation, restore-consistency predicate.
- `gateway_modelcheck/checker.py` — invariants, breadth-first explicit-state checker with state hashing, depth bound, state cap, shortest-trace reconstruction, replay.
- `gateway_modelcheck/run_check.py` — CLI, JSON report to `--output`.
- `gateway_modelcheck/tests/test_checker.py` — unittest suite; seeded-bug detection, trace replay, determinism.

---

FILE: MODEL.md
```markdown
# GW-ASYNC0 abstract lifecycle model and design-check findings

CC-BY-4.0 (prose). Red (Claude, Anthropic) for The Stage, coordinating with Richard Pemberton.
Design under review: GW-ASYNC0 DESIGN.md / PLAN.md by Coda (Codex Lily), implementing Lily's
reviewed lifecycle requirements. Original interface.py / relay.py: Lilitari (Lily) via ChatGPT, MIT.
Everything here is static reasoning about a model of the design; nothing was executed by the author.
Red's sandbox run of `run_check.py` is the only execution evidence and supersedes the predictions below.
Scope: the local actuator-free FL1 simulator relay. Not a hardware controller, not a safety certification.

## (a) Abstract state model

The model (gateway_modelcheck/model.py) has one relay/gateway process ("mem"), one durable
private_state ("dur"), one regenerable export view, a writer lock, and environment ghosts.

Gateway `Gw = (seq, tick, obs, stopped, active, receipts)`; a receipt is
`(request_id, kind, request_sequence, status)` with status in
{admitted_pending, dispatched, verified_simulator_transition, verified_failure,
 cancelled_before_dispatch, unknown_outcome, rejected, stop_receipt}.
`rejected` and `stop_receipt` are distinct, as DESIGN.md requires.
Simulator truth is an append-only log of committed request ids (`sim`); `len(sim)` is the simulator tick.

Global state: `phase, lock, mem, mem_sim, dur, dur_sim, export, pending, tampered, dispatched_ids,
double_dispatch`. Phases: idle, loaded, admitted, dispatched, computed, ambiguous, persist_pending,
committed, export_failed, crashed, rejected_state (terminal).

Request pool (bounded): fresh moves `a`, `b` (content fixed at first admission: sequence = gateway
sequence then), a stale move `x` (always sequence_mismatch), one stop `s`. Replaying any id is a
duplicate replay (identical content). Reuse-with-different-content is a pure parser/ValueError
rejection and is not modelled.

Actions and the crash points between durable writes:

| action | precondition | effect | durable write? |
|---|---|---|---|
| begin | idle | lock; restore(dur) → mem (validated); in-flight receipt resolved from durable truth | no |
| admit(rid) | loaded (+ api-level in admitted/dispatched/ambiguous) | duplicate → cached status, no change; fresh → rejected(stop_latched/command_pending/sequence_mismatch) or admitted_pending, active=rid | no |
| stop | same as admit | stopped=True, stop_receipt; cancels only an admitted_pending active receipt | no (persisted with the transaction) |
| mark_dispatched | admitted | status dispatched; ghost dispatched_ids | **design-ambiguous**: cfg.durable_dispatch_mark |
| compute_ok / compute_fail | dispatched | candidate ready / record_failure: verified_failure, active=None, no advance | no |
| commit_ok | computed | verified, seq/tick/obs+1, sim+rid, dur=mem | yes (atomic replace) |
| commit_fail_before_replace | computed | record_failure as above | no |
| commit_ambiguous(replaced=T/F) | computed | exception around os.replace; durable is new or old; process marks unknown_outcome in mem | yes/no (nondeterministic) |
| resolve_unknown_trusted | ambiguous, or loaded with unknown receipt | re-read durable truth; verified iff rid ∈ dur_sim else verified_failure; merges in-process latches | no (then persist) |
| persist_unknown_blind | ambiguous (variant) | dur=mem from pre-commit memory | yes |
| persist | persist_pending | dur=mem | yes |
| export_ok / export_fail | committed | export=view(dur), unlock / process dies with lock held | export files only |
| crash | any live phase | mem lost, lock held | — |
| recover | crashed, export_failed | restore(dur) validated; resolve in-flight from durable truth; regenerate export; unlock | no (export regenerated, never a transition) |
| tamper(kind) | idle, once | corrupt dur (7 kinds) to model disk corruption / ambiguous old-format migration | — |

Restore-consistency predicate (my proposed clarification C4; the design does not enumerate one):
seq == tick == obs == len(sim); at most one unresolved receipt; active equals that receipt's id,
None otherwise; stopped ⇒ no admitted_pending; {verified receipts} == set(sim) with sim duplicate-free;
every status is a known value. Any failure ⇒ rejected_state, never repaired.

## (b) Invariants checked (checker.py)

INV_ONE_UNRESOLVED, INV_NO_REDISPATCH (status graph never re-enters pending/dispatched; duplicate replay
changes nothing; no cached receipt is lost), INV_NO_DOUBLE_DISPATCH (ghost: an id is marked dispatched at
most once across crashes), INV_STOP_LATCH (monotone; dispatched/unknown never → cancelled; stopped ⇒ no
admitted_pending; fresh move after stop rejected), INV_ONLY_VERIFIED_ADVANCES (counters move only by
+1 together with exactly one newly verified receipt; counters == len(sim)), INV_FAILURE_RELEASES,
INV_RESTORE_REJECTS_INCONSISTENT (tampered durable state never loads), INV_RESTORE_ACCEPTS_CONSISTENT
(sanity), INV_EXPORT_NEVER_REPLAYS (export/recover leave durable state unchanged; idle ⇒ export ==
durable view), INV_NO_FALSE_OUTCOME (verified ⇔ in sim; verified_failure ⇒ not in sim; sim never rolls
back or repeats).

## (c) Predicted counterexamples for the design as written, and smallest clarifications

Predicted by static reasoning; Red's run gives the actual traces. Lengths are BFS-shortest.

CE-1 (variant as_written_nondurable_dispatch_mark; relay-reachable, no API interleaving needed).
`begin, admit(a), mark_dispatched, crash, recover, begin, admit(a), mark_dispatched` → INV_NO_DOUBLE_DISPATCH.
If "marks dispatch" is in-memory only, a crash before commit erases the admission; the replay is a fresh
admission and is dispatched again. DESIGN.md half-accepts this ("a crash before replacement does not imply
an external action") but also says serialization "preserves every pending or unknown receipt", which is
vacuous if dispatch is never durable. Clarification C1: state that mark_dispatched performs a private_state
replacement recording `dispatched` before the transition is computed, and that on restore a `dispatched`
receipt whose transition is absent from private_state resolves to verified_failure with reason
`no_commit_found_after_restart` (trusted: file truth). If the team instead keeps the in-memory reading,
write down explicitly that it is valid only for an actuator-free simulator and that a crash before commit
makes a replay a fresh request.

CE-2 (variant as_written_blind_unknown_persist; relay-reachable).
`begin, admit(a), mark_dispatched, compute_ok, commit_ambiguous(replaced=True), persist_unknown_blind`
→ INV_NO_FALSE_OUTCOME (verified → unknown, simulator log rolled back) and INV_ONLY_VERIFIED_ADVANCES.
DESIGN.md requires mark_unknown and later resolution but does not say how the unknown marking is persisted.
Writing the pre-commit in-memory state (now carrying `unknown_outcome`) back to private_state after an
ambiguous os.replace overwrites a replacement that did succeed: the simulated world rewinds one step and
a verified transition is demoted. Clarification C2: after any exception around the replacement, re-read
private_state before any write; derive the outcome from the re-read (transition present ⇒ verified,
absent ⇒ verified_failure/no-commit); never write gateway or simulator state derived from pre-commit memory.
`mark_unknown` is therefore an in-process marker whose durable form only exists when the re-read itself
fails, in which case the lock stays held and the operator resolves.

CE-3 (variant as_written_reread_without_latch_merge; API-level only, not reachable through the serial relay).
`begin, admit(a), mark_dispatched, stop, compute_ok, commit_ambiguous(replaced=*), resolve_unknown_trusted`
→ INV_STOP_LATCH (stop latched in memory, lost by the re-read). Clarification C3: the re-read merges
in-process state recorded since load (stop latch and stop receipt, rejected receipts); or, equivalently,
stop is itself a durable write. Moot for the relay, which never interleaves API calls inside a transaction.

CE-4 (variant as_written_weak_restore_validation).
`tamper(active_dangling), begin` → INV_RESTORE_REJECTS_INCONSISTENT and INV_ONE_UNRESOLVED. DESIGN.md says
inconsistent restored state is rejected but does not define "inconsistent"; a type-only check (which is
what `Gateway(**state)` does today) admits a dangling active identity, an orphan dispatched receipt, or a
verified receipt with no simulator transition. Clarification C4: adopt the enumerated predicate above.

No counterexample is predicted for the clarified baseline (durable mark, re-read with merge, full
predicate). Stop-after-dispatch is modelled per DESIGN.md: the dispatched step completes and is recorded
with stopped=true (assumption A5; the design should say this in one sentence — clarification C5).

## (d) Checker self-test
tests/test_checker.py requires: no violation in the clarified baseline (depth 9, with tampering);
each seeded bug variant (second admission, stop cancels dispatched, duplicate redispatch, failure advances,
silent restore repair, export replays, untrusted resolution, resolution unlatches stop) is detected under
its expected invariant; each as-written reading fails as predicted; every reported trace replays
deterministically to the recorded final-state digest; two runs produce identical JSON.

## (e) Mapping to the original interface.py / relay.py (MIT, Lily)

| abstract action | original code | difference from DESIGN.md |
|---|---|---|
| admit | `Gateway.admit` inside `relay.transact` under `writer_lock` | no `command_pending` check: a second distinct command is admitted at the same pending sequence (RED receipt failures); receipt uses `dispatch`/`execution_status` ∈ {not_dispatched, verified_simulator_transition} rather than the six lifecycle states; `rejected` is `admitted=False` in the same receipt shape |
| mark_dispatched | absent; `transact` runs the transition immediately when `receipt['dispatch']` | no in-memory or durable dispatch state distinct from admission (SCOPE_GAP) |
| compute | inline in `transact` (`body_vectors`, velocity/position update, `sample`) | exceptions propagate; no `record_failure`, no event; `writer_lock`'s `finally` releases the lock on exceptions (only a hard crash leaves it) |
| transition commit | `g.record_execution` (advances seq/tick/observation in memory) then `atomic(private_state)` | matches "saved private_state is the commit point"; in-memory advance before the write is harmless because memory is discarded on exception |
| commit_ambiguous / mark_unknown / resolve_unknown | absent; an exception in `atomic` propagates | because every transaction re-reads private_state, the original accidentally behaves like non-durable-mark + re-read: no false verified failure, but the attempt leaves no receipt/event, and a replay is a fresh admission (CE-1 behaviour) |
| export | `export(s, directory)` after the replace; `relay.py export` regenerates from private_state | matches "never replays a transition"; but `export` subcommand needs the lock free, so after a crash the operator must remove `writer.lock` manually (PLAN forbids workers from deleting locks) |
| stop | `admit` with action `stop` sets `stopped=True` before sequence/observation checks | does not cancel a pending admission; later `record_execution` of the pending receipt still verifies (RED receipt) |
| duplicate replay | cache hit returns `{**entry, duplicate: True, dispatch: False}`; different content raises ValueError → `rejected_invalid_request` event | already "never authorises redispatch"; `episode_complete` override rewrites the cached receipt in `transact` |
| serialize / restore | `asdict(g)` / `Gateway(**s['gateway'])` | no validation at all; inconsistent state is silently accepted (CE-4) |
| crash between durable writes | one private_state replace, then two export replaces per transaction; `init` likewise | design adds a durable dispatch mark (if C1 is adopted), i.e. one more crash window, resolved at restore |
| parser boundary | `parse_request` → `json.loads` | RecursionError escapes the `except (ValueError, UnicodeError)` in `transact` (RED receipt); outside this lifecycle model |

## Assumptions (labelled)
A1 Single episode; `episode_complete` and `advance` are not modelled. A2 One stop id; a second stop while
stopped is a no-op in the original and is not modelled. A3 Ambiguous failure is modelled only for the
transition commit; the persist of a failure/stop receipt is modelled as crash-before/after only.
A4 Request pool {a, b, x, s}; counters bounded by the depth bound. A5 Stop after dispatch lets the
dispatched step complete (DESIGN.md: "cancels only an undispatched admission"). A6 "Trusted resolution"
for the simulator = reading private_state. A7 api_interleaving=True over-approximates the serial relay;
findings reachable only with it are labelled API-level.

## Not implemented
Parser/JSON-depth boundary; episode reset; multi-session/body mismatch; reuse-of-id-with-different-content;
liveness (a stuck slot is not a safety violation here); partial-order reduction (not needed at this size).
```

---

FILE: gateway_modelcheck/__init__.py
```python
# SPDX-License-Identifier: MIT
"""Explicit-state design check for the GW-ASYNC0 gateway/relay lifecycle (stdlib only)."""
```

---

FILE: gateway_modelcheck/model.py
```python
# SPDX-License-Identifier: MIT
"""Abstract state model of the GW-ASYNC0 gateway + file-relay lifecycle.

Red (Claude, Anthropic) for The Stage, coordinating with Richard Pemberton.
Derived from DESIGN.md (Coda, Codex Lily, implementing Lily's review) and the
original MIT interface.py/relay.py (Lilitari/Lily). This models a design for an
actuator-free local simulator; it is not a hardware controller.

Conventions: frozen dataclasses, tuples (never sets) inside states so repr and
hashing are deterministic; Python 3.10+ standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

# Receipt statuses (DESIGN.md) plus the two semantically distinct non-action receipts.
ADMITTED = 'admitted_pending'
DISPATCHED = 'dispatched'
VERIFIED = 'verified_simulator_transition'
FAILED = 'verified_failure'
CANCELLED = 'cancelled_before_dispatch'
UNKNOWN = 'unknown_outcome'
REJECTED = 'rejected'
STOP_RECEIPT = 'stop_receipt'

UNRESOLVED = frozenset({ADMITTED, DISPATCHED, UNKNOWN})
ALLOWED_NEXT = {
    ADMITTED: frozenset({DISPATCHED, CANCELLED}),
    DISPATCHED: frozenset({VERIFIED, FAILED, UNKNOWN}),
    UNKNOWN: frozenset({VERIFIED, FAILED}),
    VERIFIED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
    REJECTED: frozenset(),
    STOP_RECEIPT: frozenset(),
}

MOVE_IDS = ('a', 'b')
STALE_ID = 'x'      # content always carries sequence -1: deterministic sequence_mismatch
STOP_ID = 's'
TAMPER_KINDS = ('active_dangling', 'orphan_dispatched', 'two_pending',
                'stopped_with_pending', 'counter_skew', 'sim_skew', 'false_verified')

Receipt = Tuple[str, str, int, str]  # (request_id, kind, request_sequence, status)


@dataclass(frozen=True)
class Config:
    """Design readings (as written vs clarified) and seeded bugs for checker self-tests."""
    durable_dispatch_mark: bool = True       # C1: mark_dispatched is a private_state replacement
    unknown_persist: str = 'reread'          # C2: 'reread' (re-read durable truth) | 'blind' (write memory)
    reread_merges_latches: bool = True       # C3: re-read keeps in-process stop latch / receipts
    restore_check: str = 'full'              # C4: 'full' | 'weak' (counters only) | 'repair' (silent)
    api_interleaving: bool = True            # gateway API calls may interleave inside a transaction
    allow_tamper: bool = True                # environment may corrupt durable state once
    bug_second_admission: bool = False
    bug_stop_cancels_dispatched: bool = False
    bug_duplicate_redispatch: bool = False
    bug_failure_advances: bool = False
    bug_export_replays: bool = False
    bug_blind_resolve: bool = False
    bug_resolution_unlatches: bool = False


@dataclass(frozen=True)
class Gw:
    seq: int = 0
    tick: int = 0
    obs: int = 0
    stopped: bool = False
    active: Optional[str] = None
    receipts: Tuple[Receipt, ...] = ()

    def get(self, rid: str) -> Optional[Receipt]:
        for r in self.receipts:
            if r[0] == rid:
                return r
        return None

    def put(self, rid: str, kind: str, req_seq: int, status: str, **changes) -> 'Gw':
        others = tuple(r for r in self.receipts if r[0] != rid)
        recs = tuple(sorted(others + ((rid, kind, req_seq, status),)))
        return replace(self, receipts=recs, **changes)

    def unresolved(self) -> Tuple[Receipt, ...]:
        return tuple(r for r in self.receipts if r[3] in UNRESOLVED)

    def advanced(self) -> 'Gw':
        return replace(self, seq=self.seq + 1, tick=self.tick + 1, obs=self.obs + 1)


def view(g: Gw) -> Tuple[int, int, int, bool]:
    """What packet.json shows: sequence, dispatch tick, observation index, stopped."""
    return (g.seq, g.tick, g.obs, g.stopped)


@dataclass(frozen=True)
class State:
    phase: str = 'idle'
    lock: bool = False
    mem: Optional[Gw] = None               # in-process gateway (None when no process is alive)
    mem_sim: Tuple[str, ...] = ()          # in-process simulator log (committed request ids)
    dur: Gw = Gw()                         # private_state.json gateway section
    dur_sim: Tuple[str, ...] = ()          # private_state.json simulator truth
    export: Tuple[int, int, int, bool] = (0, 0, 0, False)   # last exported packet view
    pending: Optional[str] = None          # request id handled by the live transaction
    tampered: Optional[str] = None         # environment corrupted dur (kind)
    dispatched_ids: Tuple[str, ...] = ()   # ghost: ids ever marked dispatched
    double_dispatch: bool = False          # ghost: an id was marked dispatched twice


INITIAL = State()


# ----------------------------------------------------------------------------- consistency

def consistency_issues(g: Gw, sim: Tuple[str, ...]) -> List[str]:
    """Proposed restore predicate (clarification C4). Empty list means consistent."""
    issues: List[str] = []
    if not (g.seq == g.tick == g.obs == len(sim)):
        issues.append('counter_skew')
    unres = g.unresolved()
    if len(unres) > 1:
        issues.append('multiple_unresolved')
    if len(unres) == 1 and g.active != unres[0][0]:
        issues.append('active_mismatch')
    if not unres and g.active is not None:
        issues.append('active_dangling')
    if g.stopped and any(r[3] == ADMITTED for r in g.receipts):
        issues.append('stopped_with_pending')
    verified = {r[0] for r in g.receipts if r[3] == VERIFIED}
    if verified != set(sim) or len(set(sim)) != len(sim):
        issues.append('verified_sim_mismatch')
    if any(r[3] not in ALLOWED_NEXT for r in g.receipts):
        issues.append('unknown_status')
    return issues


def weak_consistency_issues(g: Gw, sim: Tuple[str, ...]) -> List[str]:
    """What a type/counter-only restore (like Gateway(**state)) would notice."""
    return ['counter_skew'] if not (g.seq == g.tick == g.obs == len(sim)) else []


def _repair(g: Gw, sim: Tuple[str, ...]) -> Gw:
    """Seeded bug: silently 'repair' instead of rejecting."""
    recs = tuple(r for r in g.receipts
                 if r[3] not in UNRESOLVED and not (r[3] == VERIFIED and r[0] not in sim))
    n = len(sim)
    return replace(g, seq=n, tick=n, obs=n, active=None, receipts=recs)


# ----------------------------------------------------------------------------- actions

def _restore(s: State, cfg: Config, resume: bool) -> State:
    """begin (from idle) or recover (after crash/export failure): validated load from dur."""
    dur, dsim = s.dur, s.dur_sim
    if cfg.restore_check == 'weak':
        issues = weak_consistency_issues(dur, dsim)
    else:
        issues = consistency_issues(dur, dsim)
    mem = dur
    if issues:
        if cfg.restore_check == 'repair':
            mem = _repair(dur, dsim)
        else:
            return replace(s, phase='rejected_state', lock=True, mem=None, mem_sim=(), pending=None)
    inflight = [r for r in mem.receipts if r[3] in (DISPATCHED, UNKNOWN)]
    if inflight:
        # Trusted resolution from durable truth before anything else may run.
        rid, kind, req_seq, _ = inflight[0]
        if rid in dsim:
            mem = mem.put(rid, kind, req_seq, VERIFIED, active=None).advanced()
        else:
            mem = mem.put(rid, kind, req_seq, FAILED, active=None)
        return replace(s, phase='persist_pending', lock=True, mem=mem, mem_sim=dsim, pending=None)
    if resume:
        dur2, dsim2 = dur, dsim
        if cfg.bug_export_replays and dsim:
            dur2 = dur.advanced()
            dsim2 = dsim + (dsim[-1],)
        return replace(s, phase='idle', lock=False, mem=None, mem_sim=(), dur=dur2, dur_sim=dsim2,
                       export=view(dur2), pending=None)
    return replace(s, phase='loaded', lock=True, mem=mem, mem_sim=dsim, pending=None)


def _admit(s: State, cfg: Config, rid: str) -> State:
    mem, ph = s.mem, s.phase
    after = 'persist_pending' if ph == 'loaded' else ph
    existing = mem.get(rid)
    if existing is not None:  # duplicate replay: cached receipt returned, nothing re-authorised
        if (cfg.bug_duplicate_redispatch and existing[3] in (FAILED, CANCELLED, REJECTED)
                and mem.active is None):
            new = mem.put(rid, existing[1], existing[2], ADMITTED, active=rid)
            return replace(s, mem=new, pending=rid, phase='admitted' if ph == 'loaded' else ph)
        return replace(s, phase=after)
    req_seq = -1 if rid == STALE_ID else mem.seq
    reason = None
    if mem.stopped:
        reason = 'stop_latched'
    elif mem.active is not None and not cfg.bug_second_admission:
        reason = 'command_pending'
    elif req_seq != mem.seq:
        reason = 'sequence_mismatch'
    if reason is not None:
        return replace(s, mem=mem.put(rid, 'move', req_seq, REJECTED), phase=after)
    new = mem.put(rid, 'move', req_seq, ADMITTED, active=rid)
    if ph == 'loaded':
        return replace(s, mem=new, pending=rid, phase='admitted')
    return replace(s, mem=new)  # API-level second admission (only with bug_second_admission)


def _stop(s: State, cfg: Config) -> State:
    mem, ph = s.mem, s.phase
    after = 'persist_pending' if ph == 'loaded' else ph
    if mem.get(STOP_ID) is not None:
        return replace(s, phase=after)
    new = mem.put(STOP_ID, 'stop', -1, STOP_RECEIPT, stopped=True)
    pending = s.pending
    if mem.active is not None:
        rec = mem.get(mem.active)
        cancel = rec[3] == ADMITTED or (
            cfg.bug_stop_cancels_dispatched and rec[3] in (DISPATCHED, UNKNOWN))
        if cancel:
            new = new.put(rec[0], rec[1], rec[2], CANCELLED, active=None)
            if pending == rec[0]:
                pending = None
            after = 'persist_pending'
    return replace(s, mem=new, pending=pending, phase=after)


def _mark_dispatched(s: State, cfg: Config) -> State:
    rid = s.pending
    rec = s.mem.get(rid)
    new = s.mem.put(rid, rec[1], rec[2], DISPATCHED)
    double = s.double_dispatch or rid in s.dispatched_ids
    ids = tuple(sorted(set(s.dispatched_ids) | {rid}))
    if cfg.durable_dispatch_mark:
        return replace(s, mem=new, dur=new, dur_sim=s.mem_sim, phase='dispatched',
                       dispatched_ids=ids, double_dispatch=double)
    return replace(s, mem=new, phase='dispatched', dispatched_ids=ids, double_dispatch=double)


def _record_failure(s: State, cfg: Config) -> State:
    rid = s.pending
    rec = s.mem.get(rid)
    new = s.mem.put(rid, rec[1], rec[2], FAILED, active=None)
    if cfg.bug_failure_advances:
        new = new.advanced()
    return replace(s, mem=new, pending=None, phase='persist_pending')


def _commit_ok(s: State, cfg: Config) -> State:
    rid = s.pending
    rec = s.mem.get(rid)
    new = s.mem.put(rid, rec[1], rec[2], VERIFIED, active=None).advanced()
    sim = s.mem_sim + (rid,)
    return replace(s, mem=new, mem_sim=sim, dur=new, dur_sim=sim, pending=None, phase='committed')


def _commit_ambiguous(s: State, cfg: Config, replaced: bool) -> State:
    rid = s.pending
    rec = s.mem.get(rid)
    committed = s.mem.put(rid, rec[1], rec[2], VERIFIED, active=None).advanced()
    unknown = s.mem.put(rid, rec[1], rec[2], UNKNOWN)   # mark_unknown in process; slot retained
    if replaced:
        return replace(s, mem=unknown, dur=committed, dur_sim=s.mem_sim + (rid,), phase='ambiguous')
    return replace(s, mem=unknown, phase='ambiguous')


def _persist_unknown_blind(s: State) -> State:
    """As-written reading: write the pre-commit memory (now unknown) over private_state."""
    return replace(s, dur=s.mem, dur_sim=s.mem_sim, phase='committed', pending=None)


def _resolve_trusted(s: State, cfg: Config) -> State:
    """Re-read durable truth; outcome follows the file, never memory."""
    mem = s.mem
    rid = s.pending
    if rid is None:
        rid = next(r[0] for r in mem.receipts if r[3] == UNKNOWN)
    rec = mem.get(rid)
    dur, dsim = s.dur, s.dur_sim
    base = dur
    if cfg.reread_merges_latches:
        if mem.stopped and not base.stopped:
            base = replace(base, stopped=True)
        for r in mem.receipts:
            if r[0] != rid and base.get(r[0]) is None:
                base = base.put(r[0], r[1], r[2], r[3])
    if rid in dsim:
        cur = base.get(rid)
        if cur is None or cur[3] != VERIFIED:
            base = base.put(rid, rec[1], rec[2], VERIFIED, active=None)
        new = base
    else:
        new = base.put(rid, rec[1], rec[2], FAILED, active=None)
    if cfg.bug_resolution_unlatches:
        new = replace(new, stopped=False)
    phase = 'committed' if new == dur else 'persist_pending'
    return replace(s, mem=new, mem_sim=dsim, phase=phase, pending=None)


def _resolve_untrusted(s: State, outcome: str) -> State:
    """Seeded bug: outcome chosen without consulting the simulator truth."""
    rid = s.pending
    rec = s.mem.get(rid)
    new = s.mem.put(rid, rec[1], rec[2], outcome, active=None)
    if outcome == VERIFIED:
        new = new.advanced()
    return replace(s, mem=new, dur=new, phase='committed', pending=None)


def _tamper(s: State, kind: str) -> State:
    g, sim = s.dur, s.dur_sim
    if kind == 'active_dangling':
        g = replace(g, active='zz')
    elif kind == 'orphan_dispatched':
        g = g.put('y', 'move', g.seq, DISPATCHED)
    elif kind == 'two_pending':
        g = g.put('y', 'move', g.seq, ADMITTED).put('z', 'move', g.seq, ADMITTED, active='y')
    elif kind == 'stopped_with_pending':
        g = g.put('y', 'move', g.seq, ADMITTED, active='y', stopped=True)
    elif kind == 'counter_skew':
        g = replace(g, tick=g.tick + 1)
    elif kind == 'sim_skew':
        sim = sim + ('zz',)
    elif kind == 'false_verified':
        g = g.put('y', 'move', g.seq, VERIFIED)
    else:
        raise ValueError(kind)
    return replace(s, dur=g, dur_sim=sim, tampered=kind)


def successors(s: State, cfg: Config) -> List[Tuple[str, State]]:
    """All enabled (label, next_state) pairs, in a fixed deterministic order."""
    out: List[Tuple[str, State]] = []
    ph = s.phase
    if ph == 'idle':
        out.append(('begin', _restore(s, cfg, resume=False)))
        if cfg.allow_tamper and s.tampered is None:
            for kind in TAMPER_KINDS:
                out.append(('tamper(%s)' % kind, _tamper(s, kind)))
        return out
    if ph == 'rejected_state':
        return out
    if ph in ('crashed', 'export_failed'):
        out.append(('recover', _restore(s, cfg, resume=True)))
        return out
    api_ok = ph == 'loaded' or (cfg.api_interleaving and ph in ('admitted', 'dispatched', 'ambiguous'))
    if api_ok:
        for rid in MOVE_IDS + (STALE_ID,):
            out.append(('admit(%s)' % rid, _admit(s, cfg, rid)))
        out.append(('stop', _stop(s, cfg)))
    if ph == 'loaded' and any(r[3] == UNKNOWN for r in s.mem.receipts):
        out.append(('resolve_unknown_trusted', _resolve_trusted(s, cfg)))
    if ph == 'admitted':
        out.append(('mark_dispatched', _mark_dispatched(s, cfg)))
    elif ph == 'dispatched':
        out.append(('compute_ok', replace(s, phase='computed')))
        out.append(('compute_fail', _record_failure(s, cfg)))
    elif ph == 'computed':
        out.append(('commit_ok', _commit_ok(s, cfg)))
        out.append(('commit_fail_before_replace', _record_failure(s, cfg)))
        out.append(('commit_ambiguous(replaced=True)', _commit_ambiguous(s, cfg, True)))
        out.append(('commit_ambiguous(replaced=False)', _commit_ambiguous(s, cfg, False)))
    elif ph == 'ambiguous':
        if cfg.unknown_persist == 'blind':
            out.append(('persist_unknown_blind', _persist_unknown_blind(s)))
        else:
            out.append(('resolve_unknown_trusted', _resolve_trusted(s, cfg)))
        if cfg.bug_blind_resolve:
            out.append(('resolve_unknown_untrusted(%s)' % VERIFIED, _resolve_untrusted(s, VERIFIED)))
            out.append(('resolve_unknown_untrusted(%s)' % FAILED, _resolve_untrusted(s, FAILED)))
    elif ph == 'persist_pending':
        out.append(('persist', replace(s, dur=s.mem, dur_sim=s.mem_sim, phase='committed')))
    elif ph == 'committed':
        out.append(('export_ok', replace(s, phase='idle', lock=False, mem=None, mem_sim=(),
                                         pending=None, export=view(s.dur))))
        out.append(('export_fail', replace(s, phase='export_failed', mem=None, mem_sim=(), pending=None)))
    out.append(('crash', replace(s, phase='crashed', mem=None, mem_sim=(), pending=None)))
    return out


# ----------------------------------------------------------------------------- variants

VARIANTS = {
    'clarified_baseline': Config(),
    'clarified_relay_only': Config(api_interleaving=False),
    'as_written_nondurable_dispatch_mark': Config(durable_dispatch_mark=False),
    'as_written_blind_unknown_persist': Config(unknown_persist='blind'),
    'as_written_reread_without_latch_merge': Config(reread_merges_latches=False),
    'as_written_weak_restore_validation': Config(restore_check='weak'),
    'bug_second_admission': Config(bug_second_admission=True),
    'bug_stop_cancels_dispatched': Config(bug_stop_cancels_dispatched=True),
    'bug_duplicate_redispatch': Config(bug_duplicate_redispatch=True),
    'bug_failure_advances': Config(bug_failure_advances=True),
    'bug_restore_silently_repairs': Config(restore_check='repair'),
    'bug_export_replays': Config(bug_export_replays=True),
    'bug_untrusted_resolution': Config(bug_blind_resolve=True),
    'bug_resolution_unlatches_stop': Config(bug_resolution_unlatches=True),
}

# Static predictions (unexecuted). Red's run decides. Empty set = no violation expected.
EXPECTED_VIOLATIONS = {
    'clarified_baseline': set(),
    'clarified_relay_only': set(),
    'as_written_nondurable_dispatch_mark': {'INV_NO_DOUBLE_DISPATCH'},
    'as_written_blind_unknown_persist': {'INV_NO_FALSE_OUTCOME'},
    'as_written_reread_without_latch_merge': {'INV_STOP_LATCH'},
    'as_written_weak_restore_validation': {'INV_RESTORE_REJECTS_INCONSISTENT'},
    'bug_second_admission': {'INV_ONE_UNRESOLVED'},
    'bug_stop_cancels_dispatched': {'INV_STOP_LATCH'},
    'bug_duplicate_redispatch': {'INV_NO_REDISPATCH'},
    'bug_failure_advances': {'INV_FAILURE_RELEASES'},
    'bug_restore_silently_repairs': {'INV_RESTORE_REJECTS_INCONSISTENT'},
    'bug_export_replays': {'INV_EXPORT_NEVER_REPLAYS'},
    'bug_untrusted_resolution': {'INV_NO_FALSE_OUTCOME'},
    'bug_resolution_unlatches_stop': {'INV_STOP_LATCH'},
}
```

---

FILE: gateway_modelcheck/checker.py
```python
# SPDX-License-Identifier: MIT
"""Breadth-first explicit-state checker for the GW-ASYNC0 lifecycle model.

Red (Claude, Anthropic) for The Stage. Standard library only, deterministic.
Finds, for every invariant, the shortest violating trace (BFS order) within a
depth bound and a state cap. Violating states are recorded but not expanded.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Dict, List, Optional, Tuple

from .model import (ADMITTED, ALLOWED_NEXT, CANCELLED, DISPATCHED, FAILED, INITIAL, REJECTED,
                    VERIFIED, Config, Gw, State, successors, view)

INV_ONE_UNRESOLVED = 'INV_ONE_UNRESOLVED'
INV_NO_REDISPATCH = 'INV_NO_REDISPATCH'
INV_NO_DOUBLE_DISPATCH = 'INV_NO_DOUBLE_DISPATCH'
INV_STOP_LATCH = 'INV_STOP_LATCH'
INV_ONLY_VERIFIED_ADVANCES = 'INV_ONLY_VERIFIED_ADVANCES'
INV_FAILURE_RELEASES = 'INV_FAILURE_RELEASES'
INV_RESTORE_REJECTS_INCONSISTENT = 'INV_RESTORE_REJECTS_INCONSISTENT'
INV_RESTORE_ACCEPTS_CONSISTENT = 'INV_RESTORE_ACCEPTS_CONSISTENT'
INV_EXPORT_NEVER_REPLAYS = 'INV_EXPORT_NEVER_REPLAYS'
INV_NO_FALSE_OUTCOME = 'INV_NO_FALSE_OUTCOME'

ALL_INVARIANTS = (INV_ONE_UNRESOLVED, INV_NO_REDISPATCH, INV_NO_DOUBLE_DISPATCH, INV_STOP_LATCH,
                  INV_ONLY_VERIFIED_ADVANCES, INV_FAILURE_RELEASES, INV_RESTORE_REJECTS_INCONSISTENT,
                  INV_RESTORE_ACCEPTS_CONSISTENT, INV_EXPORT_NEVER_REPLAYS, INV_NO_FALSE_OUTCOME)

Violation = Tuple[str, str]  # (invariant id, detail)


def state_digest(s: State) -> str:
    """Deterministic content hash of a state (tuples only; no set ordering involved)."""
    return hashlib.sha256(repr(s).encode('utf-8')).hexdigest()[:16]


def _op(label: str) -> str:
    return label.split('(', 1)[0]


# ----------------------------------------------------------------------------- state invariants

def state_violations(t: State) -> List[Violation]:
    v: List[Violation] = []
    for name, g, sim in (('mem', t.mem, t.mem_sim), ('dur', t.dur, t.dur_sim)):
        if g is None:
            continue
        if name == 'dur' and t.tampered is not None:
            continue  # corrupted on purpose; the question is whether restore loads it
        unres = g.unresolved()
        if len(unres) > 1:
            v.append((INV_ONE_UNRESOLVED, '%s: %d unresolved receipts %s' % (name, len(unres), unres)))
        elif len(unres) == 1 and g.active != unres[0][0]:
            v.append((INV_ONE_UNRESOLVED, '%s: active=%r but unresolved=%r' % (name, g.active, unres[0][0])))
        elif not unres and g.active is not None:
            v.append((INV_ONE_UNRESOLVED, '%s: dangling active=%r' % (name, g.active)))
        if not (g.seq == g.tick == g.obs == len(sim)):
            v.append((INV_ONLY_VERIFIED_ADVANCES,
                      '%s: counters %r inconsistent with simulator log length %d' % (name, view(g)[:3], len(sim))))
        if g.stopped and any(r[3] == ADMITTED for r in g.receipts):
            v.append((INV_STOP_LATCH, '%s: stopped with an admitted_pending receipt' % name))
        for r in g.receipts:
            if r[3] == VERIFIED and r[0] not in sim:
                v.append((INV_NO_FALSE_OUTCOME, '%s: %s verified but absent from simulator log' % (name, r[0])))
            if r[3] == FAILED and r[0] in sim:
                v.append((INV_NO_FALSE_OUTCOME, '%s: %s verified_failure but its transition is committed' % (name, r[0])))
        if len(set(sim)) != len(sim):
            v.append((INV_NO_FALSE_OUTCOME, '%s: a transition appears twice in the simulator log' % name))
    if t.phase == 'idle' and t.tampered is None and t.export != view(t.dur):
        v.append((INV_EXPORT_NEVER_REPLAYS, 'idle with stale export %r vs durable %r' % (t.export, view(t.dur))))
    if t.tampered is not None and t.mem is not None:
        v.append((INV_RESTORE_REJECTS_INCONSISTENT, 'inconsistent durable state (%s) was loaded' % t.tampered))
    if t.double_dispatch:
        v.append((INV_NO_DOUBLE_DISPATCH, 'a request id was marked dispatched twice'))
    return v


# ----------------------------------------------------------------------------- transition invariants

def _gw_step(g1: Gw, s1: Tuple[str, ...], g2: Gw, s2: Tuple[str, ...], name: str, op: str) -> List[Violation]:
    v: List[Violation] = []
    newly_verified = 0
    for r1 in g1.receipts:
        r2 = g2.get(r1[0])
        if r2 is None:
            v.append((INV_NO_REDISPATCH, '%s: cached receipt %s lost during %s' % (name, r1[0], op)))
            continue
        if r2[3] != r1[3]:
            if r2[3] not in ALLOWED_NEXT[r1[3]]:
                if r2[3] == CANCELLED:
                    inv = INV_STOP_LATCH
                elif r2[3] in (ADMITTED, DISPATCHED):
                    inv = INV_NO_REDISPATCH
                else:
                    inv = INV_NO_FALSE_OUTCOME
                v.append((inv, '%s: %s %s -> %s during %s' % (name, r1[0], r1[3], r2[3], op)))
            if r2[3] == VERIFIED:
                newly_verified += 1
    for r2 in g2.receipts:
        if g1.get(r2[0]) is None and r2[3] == VERIFIED:
            newly_verified += 1
    if g1.stopped and not g2.stopped:
        v.append((INV_STOP_LATCH, '%s: stop unlatched during %s' % (name, op)))
    d = (g2.seq - g1.seq, g2.tick - g1.tick, g2.obs - g1.obs)
    if d not in ((0, 0, 0), (1, 1, 1)):
        v.append((INV_ONLY_VERIFIED_ADVANCES, '%s: counters moved %r during %s' % (name, d, op)))
    elif d == (1, 1, 1) and newly_verified != 1:
        v.append((INV_ONLY_VERIFIED_ADVANCES,
                  '%s: counters advanced with %d newly verified transitions during %s' % (name, newly_verified, op)))
    elif d == (0, 0, 0) and newly_verified:
        v.append((INV_ONLY_VERIFIED_ADVANCES, '%s: verified transition without advance during %s' % (name, op)))
    if s2[:len(s1)] != s1:
        v.append((INV_NO_FALSE_OUTCOME, '%s: simulator log rolled back during %s' % (name, op)))
    elif len(s2) - len(s1) != d[0]:
        v.append((INV_ONLY_VERIFIED_ADVANCES, '%s: simulator log and counters diverged during %s' % (name, op)))
    return v


def transition_violations(label: str, pre: State, post: State) -> List[Violation]:
    op = _op(label)
    v: List[Violation] = []
    if op != 'tamper':
        v += _gw_step(pre.dur, pre.dur_sim, post.dur, post.dur_sim, 'dur', op)
    if pre.mem is not None and post.mem is not None:
        v += _gw_step(pre.mem, pre.mem_sim, post.mem, post.mem_sim, 'mem', op)
    if op in ('export_ok', 'export_fail', 'recover', 'begin') and (pre.dur, pre.dur_sim) != (post.dur, post.dur_sim):
        v.append((INV_EXPORT_NEVER_REPLAYS, '%s changed durable state' % op))
    if op in ('compute_fail', 'commit_fail_before_replace') and pre.pending is not None and post.mem is not None:
        rec = post.mem.get(pre.pending)
        if rec is None or rec[3] != FAILED or post.mem.active is not None or view(post.mem)[:3] != view(pre.mem)[:3]:
            v.append((INV_FAILURE_RELEASES, 'known failure did not release the slot without advancing'))
    if op == 'admit' and pre.mem is not None and post.mem is not None:
        rid = label[len('admit('):-1]
        before, after = pre.mem.get(rid), post.mem.get(rid)
        if before is not None and after != before:
            v.append((INV_NO_REDISPATCH, 'duplicate replay of %s changed its receipt %r -> %r' % (rid, before, after)))
        if before is None and after is not None and pre.mem.stopped and after[3] != REJECTED:
            v.append((INV_STOP_LATCH, 'fresh move %s admitted after stop' % rid))
    if op in ('begin', 'recover') and pre.tampered is None and post.phase == 'rejected_state':
        v.append((INV_RESTORE_ACCEPTS_CONSISTENT, 'reachable durable state rejected at restore'))
    return v


# ----------------------------------------------------------------------------- BFS

@dataclass
class Counterexample:
    invariant: str
    detail: str
    trace: List[str]
    length: int
    final_digest: str
    final_summary: dict


@dataclass
class Report:
    variant: str
    config: dict
    depth_bound: int
    max_states: int
    states_explored: int
    transitions_checked: int
    frontier_exhausted: bool
    truncated: bool
    counterexamples: Dict[str, Counterexample] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['counterexamples'] = {k: asdict(v) for k, v in sorted(self.counterexamples.items())}
        d['violated_invariants'] = sorted(self.counterexamples)
        return d


def summarize(s: State) -> dict:
    def g(gw: Optional[Gw]):
        if gw is None:
            return None
        return {'view': list(view(gw)), 'active': gw.active, 'receipts': [list(r) for r in gw.receipts]}
    return {'phase': s.phase, 'lock': s.lock, 'mem': g(s.mem), 'mem_sim': list(s.mem_sim),
            'dur': g(s.dur), 'dur_sim': list(s.dur_sim), 'export': list(s.export),
            'pending': s.pending, 'tampered': s.tampered, 'dispatched_ids': list(s.dispatched_ids),
            'double_dispatch': s.double_dispatch}


def _trace_to(parent: Dict[State, Tuple[Optional[State], Optional[str]]], s: State) -> List[str]:
    labels: List[str] = []
    while True:
        p, label = parent[s]
        if p is None:
            break
        labels.append(label)
        s = p
    labels.reverse()
    return labels


def check(cfg: Config, depth_bound: int = 12, max_states: int = 200000, variant: str = 'custom') -> Report:
    parent: Dict[State, Tuple[Optional[State], Optional[str]]] = {INITIAL: (None, None)}
    frontier: List[State] = [INITIAL]
    found: Dict[str, Counterexample] = {}
    transitions = 0
    truncated = False
    for depth in range(depth_bound):
        nxt: List[State] = []
        for s in frontier:
            for label, t in successors(s, cfg):
                transitions += 1
                viol = transition_violations(label, s, t) + state_violations(t)
                new = t not in parent
                if new:
                    parent[t] = (s, label)
                if viol:
                    trace = _trace_to(parent, s) + [label]
                    for inv, detail in viol:
                        if inv not in found:
                            found[inv] = Counterexample(inv, detail, trace, len(trace), state_digest(t), summarize(t))
                elif new:
                    nxt.append(t)
                if len(parent) >= max_states:
                    truncated = True
                    break
            if truncated:
                break
        frontier = nxt
        if truncated or not frontier:
            break
    return Report(variant=variant, config=asdict(cfg), depth_bound=depth_bound, max_states=max_states,
                  states_explored=len(parent), transitions_checked=transitions,
                  frontier_exhausted=not frontier and not truncated, truncated=truncated,
                  counterexamples=found)


def replay(cfg: Config, labels: List[str]) -> Tuple[State, List[Violation]]:
    """Deterministically replay a trace from INITIAL; returns the final state and the violations
    raised by its last step (transition + state)."""
    s = INITIAL
    last: List[Violation] = []
    for label in labels:
        options = dict(successors(s, cfg))
        if label not in options:
            raise KeyError('label %r not enabled; enabled: %r' % (label, sorted(options)))
        t = options[label]
        last = transition_violations(label, s, t) + state_violations(t)
        s = t
    return s, last


def format_report(r: Report) -> str:
    lines = ['variant=%s depth=%d states=%d transitions=%d exhausted=%s truncated=%s' % (
        r.variant, r.depth_bound, r.states_explored, r.transitions_checked, r.frontier_exhausted, r.truncated)]
    if not r.counterexamples:
        lines.append('  no invariant violated within the bound')
    for inv, ce in sorted(r.counterexamples.items()):
        lines.append('  %s (length %d): %s' % (inv, ce.length, ce.detail))
        lines.append('    trace: ' + ' ; '.join(ce.trace))
    return '\n'.join(lines)


def report_json(reports: List[Report]) -> str:
    return json.dumps([r.to_dict() for r in reports], indent=2, sort_keys=True)
```

---

FILE: gateway_modelcheck/run_check.py
```python
# SPDX-License-Identifier: MIT
"""CLI: run the GW-ASYNC0 design check for one or all variants.

Writes a JSON report only to the caller-supplied --output path; prints a text summary.
Example: python -m gateway_modelcheck.run_check --variant all --depth 12 --output report.json
"""
from __future__ import annotations

import argparse
import sys

from .checker import check, format_report, report_json
from .model import EXPECTED_VIOLATIONS, VARIANTS


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', default='all', help='variant name or "all"')
    p.add_argument('--depth', type=int, default=12)
    p.add_argument('--max-states', type=int, default=200000)
    p.add_argument('--output', default=None, help='path for the JSON report (only file written)')
    args = p.parse_args(argv)
    names = sorted(VARIANTS) if args.variant == 'all' else [args.variant]
    reports = []
    mismatches = 0
    for name in names:
        if name not in VARIANTS:
            print('unknown variant %r; known: %s' % (name, ', '.join(sorted(VARIANTS))))
            return 2
        r = check(VARIANTS[name], args.depth, args.max_states, variant=name)
        reports.append(r)
        print(format_report(r))
        expected = EXPECTED_VIOLATIONS.get(name, set())
        got = set(r.counterexamples)
        if expected and not expected <= got:
            mismatches += 1
            print('  PREDICTION MISMATCH: expected %s not found' % sorted(expected - got))
        if not expected and got:
            mismatches += 1
            print('  PREDICTION MISMATCH: unexpected violations %s' % sorted(got))
        print()
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report_json(reports) + '\n')
        print('report written to %s' % args.output)
    print('prediction mismatches: %d' % mismatches)
    return 0 if mismatches == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
```

---

FILE: gateway_modelcheck/tests/__init__.py
```python
# SPDX-License-Identifier: MIT
```

---

FILE: gateway_modelcheck/tests/test_checker.py
```python
# SPDX-License-Identifier: MIT
"""Self-tests for the GW-ASYNC0 model checker: seeded bugs must be found, traces must replay,
runs must be deterministic. Run: python -m unittest gateway_modelcheck.tests.test_checker"""
from __future__ import annotations

from dataclasses import replace
import unittest

from gateway_modelcheck import checker, model
from gateway_modelcheck.checker import (INV_NO_DOUBLE_DISPATCH, INV_NO_FALSE_OUTCOME,
                                        INV_RESTORE_REJECTS_INCONSISTENT, INV_STOP_LATCH,
                                        check, replay, report_json, state_violations)
from gateway_modelcheck.model import (EXPECTED_VIOLATIONS, INITIAL, TAMPER_KINDS, VARIANTS,
                                      Config, Gw, consistency_issues, successors)

BUG_DEPTH = 8
BASELINE_DEPTH = 9


class BaselineTests(unittest.TestCase):
    def test_clarified_baseline_has_no_violation(self):
        r = check(VARIANTS['clarified_baseline'], BASELINE_DEPTH, variant='clarified_baseline')
        self.assertFalse(r.truncated)
        self.assertEqual({}, r.counterexamples, checker.format_report(r))
        self.assertGreater(r.states_explored, 100)

    def test_relay_only_baseline_has_no_violation(self):
        r = check(VARIANTS['clarified_relay_only'], BASELINE_DEPTH, variant='clarified_relay_only')
        self.assertEqual({}, r.counterexamples, checker.format_report(r))

    def test_baseline_reaches_every_lifecycle_status(self):
        # Coverage sanity: the model must actually visit all six design states plus the two others.
        seen = set()
        frontier = [INITIAL]
        parent = {INITIAL}
        cfg = VARIANTS['clarified_baseline']
        for _ in range(BUG_DEPTH):
            nxt = []
            for s in frontier:
                for _label, t in successors(s, cfg):
                    for g in (t.mem, t.dur):
                        if g is not None:
                            seen.update(r[3] for r in g.receipts)
                    if t not in parent:
                        parent.add(t)
                        nxt.append(t)
            frontier = nxt
        for status in (model.ADMITTED, model.DISPATCHED, model.VERIFIED, model.FAILED,
                       model.CANCELLED, model.UNKNOWN, model.REJECTED, model.STOP_RECEIPT):
            self.assertIn(status, seen)


class SeededBugTests(unittest.TestCase):
    def test_each_seeded_bug_is_detected_under_its_expected_invariant(self):
        for name, cfg in sorted(VARIANTS.items()):
            if not name.startswith('bug_'):
                continue
            with self.subTest(variant=name):
                r = check(cfg, BUG_DEPTH, variant=name)
                for inv in EXPECTED_VIOLATIONS[name]:
                    self.assertIn(inv, r.counterexamples, checker.format_report(r))

    def test_as_written_readings_fail_as_predicted(self):
        for name in ('as_written_nondurable_dispatch_mark', 'as_written_blind_unknown_persist',
                     'as_written_reread_without_latch_merge', 'as_written_weak_restore_validation'):
            with self.subTest(variant=name):
                r = check(VARIANTS[name], BUG_DEPTH, variant=name)
                for inv in EXPECTED_VIOLATIONS[name]:
                    self.assertIn(inv, r.counterexamples, checker.format_report(r))

    def test_nondurable_mark_counterexample_is_a_crash_replay(self):
        r = check(VARIANTS['as_written_nondurable_dispatch_mark'], BUG_DEPTH)
        ce = r.counterexamples[INV_NO_DOUBLE_DISPATCH]
        self.assertLessEqual(ce.length, 8)
        self.assertIn('crash', ce.trace)
        self.assertEqual(2, sum(1 for l in ce.trace if l == 'mark_dispatched'))

    def test_blind_unknown_persist_rolls_back_a_committed_transition(self):
        r = check(VARIANTS['as_written_blind_unknown_persist'], BUG_DEPTH)
        ce = r.counterexamples[INV_NO_FALSE_OUTCOME]
        self.assertLessEqual(ce.length, 6)
        self.assertEqual('persist_unknown_blind', ce.trace[-1])
        self.assertIn('commit_ambiguous(replaced=True)', ce.trace)

    def test_latch_merge_finding_needs_api_interleaving(self):
        cfg = replace(VARIANTS['as_written_reread_without_latch_merge'], api_interleaving=False)
        r = check(cfg, BUG_DEPTH)
        self.assertNotIn(INV_STOP_LATCH, r.counterexamples)

    def test_weak_restore_accepts_a_dangling_active_identity(self):
        r = check(VARIANTS['as_written_weak_restore_validation'], 3)
        ce = r.counterexamples[INV_RESTORE_REJECTS_INCONSISTENT]
        self.assertEqual(2, ce.length)
        self.assertEqual('begin', ce.trace[-1])


class TraceAndDeterminismTests(unittest.TestCase):
    def test_every_reported_trace_replays_to_the_recorded_state(self):
        for name, cfg in sorted(VARIANTS.items()):
            r = check(cfg, BUG_DEPTH, variant=name)
            for inv, ce in r.counterexamples.items():
                with self.subTest(variant=name, invariant=inv):
                    final, viol = replay(cfg, ce.trace)
                    self.assertEqual(ce.final_digest, checker.state_digest(final))
                    self.assertIn(inv, {i for i, _ in viol})

    def test_runs_are_deterministic(self):
        a = report_json([check(VARIANTS[n], 6, variant=n) for n in sorted(VARIANTS)])
        b = report_json([check(VARIANTS[n], 6, variant=n) for n in sorted(VARIANTS)])
        self.assertEqual(a, b)

    def test_depth_bound_is_respected(self):
        r = check(VARIANTS['as_written_nondurable_dispatch_mark'], 5)
        self.assertNotIn(INV_NO_DOUBLE_DISPATCH, r.counterexamples)
        for ce in r.counterexamples.values():
            self.assertLessEqual(ce.length, 5)

    def test_state_cap_truncates(self):
        r = check(VARIANTS['clarified_baseline'], 12, max_states=50)
        self.assertTrue(r.truncated)
        self.assertLessEqual(r.states_explored, 50)


class ConsistencyPredicateTests(unittest.TestCase):
    def test_initial_state_is_consistent(self):
        self.assertEqual([], consistency_issues(Gw(), ()))

    def test_every_tamper_kind_is_inconsistent(self):
        for kind in TAMPER_KINDS:
            with self.subTest(kind=kind):
                t = model._tamper(INITIAL, kind)
                self.assertTrue(consistency_issues(t.dur, t.dur_sim))

    def test_full_restore_rejects_every_tamper_kind_without_loading(self):
        cfg = VARIANTS['clarified_baseline']
        for kind in TAMPER_KINDS:
            with self.subTest(kind=kind):
                final, viol = replay(cfg, ['tamper(%s)' % kind, 'begin'])
                self.assertEqual('rejected_state', final.phase)
                self.assertIsNone(final.mem)
                self.assertEqual([], viol)

    def test_state_violation_detects_false_verified(self):
        g = Gw(seq=1, tick=1, obs=1).put('a', 'move', 0, model.VERIFIED)
        s = replace(INITIAL, dur=g, dur_sim=())
        self.assertTrue(any(i == INV_NO_FALSE_OUTCOME for i, _ in state_violations(s)))


if __name__ == '__main__':
    unittest.main()
```

---

## How Red should run it (sandbox)

```
python -m unittest -v gateway_modelcheck.tests.test_checker
python -m gateway_modelcheck.run_check --variant all --depth 12 --output report.json
```

The CLI exits non-zero if any static prediction in `EXPECTED_VIOLATIONS` mismatches the actual result, so a mismatch is itself a finding to send back. Expected runtime: the baseline at depth 12 should stay well under 10^5 states; if it exceeds `--max-states`, the report says `truncated: true` and the "no violation" claim is only valid to the depth reached.

## Summary of design findings (static; pending Red's run)

1. **Dispatch marking must be durable or explicitly declared memory-only (C1).** As written, the text supports both readings; the memory-only reading permits redispatch after a crash (CE-1), tolerable only because the simulator has no actuator.
2. **Ambiguous replacement must be resolved by re-reading private_state, never by writing memory back (C2).** The naive persistence of `unknown_outcome` rewinds the simulator and demotes a verified transition (CE-2). This is the most consequential gap: it violates the design's own commit-point principle.
3. **Re-read must merge in-process latches (C3)** — only matters if gateway API calls ever interleave inside a relay transaction; moot for the serial relay.
4. **"Inconsistent restored state" needs a definition (C4).** The predicate in `MODEL.md` is proposed; the current `Gateway(**state)` restore checks nothing (CE-4).
5. **Stop after dispatch (C5):** say in one sentence that the dispatched step completes and is recorded with `stopped=true`; the model assumes this.
6. The design otherwise holds the required invariants in the model: one unresolved slot, duplicates never redispatch, stop latches and never claims cancellation of dispatched/unknown work, only verified transitions advance, known failure releases without advancing, export recovery never replays.

**Left unimplemented:** parser/JSON-depth boundary (the RecursionError finding is outside this lifecycle model), episode reset, session/body mismatch, id-reuse-with-different-content, a second stop id, ambiguous failure of non-transition persists, liveness properties.