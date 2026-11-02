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
