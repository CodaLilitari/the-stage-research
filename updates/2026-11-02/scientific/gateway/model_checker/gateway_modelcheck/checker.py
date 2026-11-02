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
