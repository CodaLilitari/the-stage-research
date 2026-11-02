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
