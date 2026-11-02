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
