# gateway-integration-003: lifecycle (A) + audit findings D1–D6

Prose: CC-BY-4.0. Code: MIT (see LICENSE). Static contribution by Claude (Anthropic), coordinated by Red for
Richard (Andrei) Pemberton. Design: Coda (Codex Lily) with Richard Pemberton (DESIGN.md); original
interface/relay/simulator/tests: Lilitari (Lily); lifecycle implementation (A) and independent audit (B):
Claude (Anthropic), earlier waves; execution receipts: Red. **Nothing here was executed by the author.**
Private computational research on models only; not empirical validation, not a safety certification, not a
hardware design recommendation, not a public release.

## Files
- `src/interface.py` — identical to (A) wave 6 (expected sha256 `559d4a22…`). No change was needed: the D1
  interface half (deep nesting is a `ValueError` before the decoder recurses) already exists as
  `check_json_depth` / `MAX_JSON_DEPTH = 32`; the audit's byte-level `MAX_NESTING = 16` variant is superseded
  (lifecycle tests pin 32 allowed / 33 rejected). Red: if the extracted file's hash differs, the copy is wrong.
- `src/relay.py` — (A) wave 9 plus:
  - **D1** `_step` catches `Exception` from `admit` (after the `ValueError`/`UnicodeError` branch), logs a
    `rejected_invalid_request` event with fixed `reason` and `error_type`, and returns a `Gateway.restore` of the
    pre-admission snapshot (`asdict(g)`), so a partially-mutated in-memory gateway is never committed. This is a
    rollback of uncommitted memory, not a repair: nothing before the commit point counts (DESIGN.md). Note
    `load_state`'s gateway shares `s['gateway']['cache']` by reference, which is why the snapshot is taken
    before `admit`, not after. Exceptions from `mark_dispatched`/`record_*` (contract violations) still propagate
    with nothing written.
  - **D2** every request event carries `request_bytes_sha256`, `request_bytes_len`; rejections carry `error_type`.
    `executed` was already on every event in (A). (`request_sha256` inside receipts remains the canonical-parsed
    hash for duplicate detection — audit DQ3; both are documented by field name.)
  - **D3** `atomic` unlinks its temp file on any exception and re-raises.
  - **D4** `writer_lock` writes `pid=… token=…`, reports the holder in the `RuntimeError`, releases only while the
    file still carries its own token, and removes an owner-less lock if the token write itself fails.
  - **D5** `packet`, `candidate_transition`, `_advance_episode` and `observed_sensor` read `cfg['dynamics']`,
    `cfg['observations']`, `cfg['profiles']['primary']['delay']`; operand order matches `Episode.step` exactly so
    bitwise parity (audit C1) is unchanged.
  - **D6** `init(directory, seed, actor, allow_frozen_seed=False)` refuses seeds inside the frozen development
    and evaluation ranges (checked before any directory or lock is created); CLI `--allow-frozen-seed`. Also
    rejects non-int seeds and blank actor labels.
  - `migrate` now routes its export through `_export_after_commit` with the migration event (same decision below).

## Decision: post-commit export failure propagates, as a distinct error carrying the committed event
Options: (a) bare `OSError` (original behaviour, audit control test), (b) absorb and return the event with an
`export_failed` flag (audit DQ5 variant), (c) wrapped `RuntimeError` (A), (d) **chosen**: `ExportAfterCommitError`
(subclass of `RuntimeError`, `__cause__` = the export exception, attributes `event`, `committed=True`); the CLI
prints `{"committed": true, "export_failed": true, "event": …, "recovery": …}` and exits 3.
Reasons, citing the design:
1. DESIGN.md: *"Saved private_state remains the atomic simulation commit point … A failure after replacement but
   before export is recovered by regenerating export from private_state, never replaying a transition."* The step
   is committed, so it is never relabelled a failure (rules out a false `verified_failure`), never retried by
   this code, and the ledger is not retroactively annotated (that would be an unverified edit of committed
   evidence) — this rules out (b)'s honest form, since the returned event would differ from the committed one.
2. Relay docstring: *"export files are regenerable views, not independent witnesses."* But `packet.json` is the
   only thing a candidate sees; returning normally while the candidate-facing view is known stale would let a
   stale truth claim pass silently. The relay fails loud, consistent with the gateway's fail-closed posture.
3. A bare `OSError` (a) is indistinguishable from the pre-commit replacement failure (also `OSError`, see
   `test_commit_exception_writes_nothing…`). The one distinction an operator must make without opening
   `private_state.json` is "nothing happened" vs "committed, views stale"; the type carries it. (c) is kept as the
   base class so (A)'s test still passes; the audit's DQ5 reporting suggestion is adopted at the CLI.
Operator recovery is `export`; an accidental re-`step` of the same `action.json` is a truthful duplicate.

## Adapted audit assertions (tests/test_audit_first_leaf_v2.py)
| Test | Original assertion | Adapted | Why |
|---|---|---|---|
| `control_idempotency…` | `first['receipt']['dispatch']` is True | `first['executed']` True, `duplicate` False, status `verified_simulator_transition`, `dispatch` False | Deliberate design change: `dispatch` means "a single dispatch is currently authorized" and is consumed at `mark_dispatched` (I2); the committed receipt of an executed step cannot still authorize one. The intent "dispatched exactly once, duplicates never re-dispatch" is preserved via `executed`/status and the unchanged duplicate loop. |
| `control_single_commit_point…` | `assertRaises(OSError)` | `assertRaises(relay.ExportAfterCommitError)`, `isinstance(RuntimeError)`, `__cause__` is `OSError`, `.committed`, `.event` status verified | Deliberate design change (decision above). Commit-survives / stale-view / `export` regenerates / retry-is-duplicate assertions unchanged. |
| `finding_D1_non_valueerror…` | `exploding_admit(self, raw)` | `exploding_admit(self, raw, block_reason=None)`; plus `error_type == 'RecursionError'`, committed gateway unchanged | API adaptation only: (A) passes `block_reason`; without it the injected failure would be an incidental `TypeError`. Intent preserved and sharpened. |
| `finding_D2`, `finding_D6`, `PriorFinding*` | — | small additive assertions (`error_type`, `allow_frozen_seed=True` path, docstring) | Strengthening only; the two prior-finding tests are now controls fixed by the lifecycle. |
All other audit tests are verbatim.

## Coda's v2 regressions → v3 (tests/test_gateway_regressions_v3.py)
Keep 6 / Adapt 8 / Retire 0 — see the v3 module docstring for the per-test table. Two adaptation kinds only:
(i) `mark_dispatched` inserted before `record_execution` (dispatch is an explicit boundary, I2), and
(ii) status vocabulary `not_dispatched` → `admitted_pending`, `cancelled_pending_by_stop` →
`cancelled_before_dispatch` (same states; the lifecycle names say what was cancelled, DESIGN.md). The v2 file
stays frozen as evidence; its receipt (6 pass, 3 fail, 5 error) is unchanged by this integration.

## Predicted results (static; Red to confirm)
- `test_stage.py` 36/36; original `test_relay.py` 7/7; `test_gateway_lifecycle.py` 26/26; `test_relay_lifecycle.py` 9/9.
- `test_audit_first_leaf_v2.py` 16/16 (`D1_deep_nesting_probe` is environment-dependent but passes through the
  depth bound). Original `test_audit_first_leaf.py` against this code: 14 pass, 2 fail (the two un-adapted control
  assertions); its original `D1_non_valueerror` passes incidentally because the `TypeError` is itself caught by D1.
- `test_gateway_regressions_v3.py` 14/14. Frozen v2: 6 pass / 3 fail / 5 error (unchanged attribution).
- Highest-risk predictions: (1) `writer_lock` token release relies on `Path.read_bytes()` of a 0600 file by the
  same user — true in the sandbox; (2) D1 rollback `Gateway.restore(asdict(g))` must round-trip every committed
  gateway — guaranteed by `g.validate()` having passed at load; (3) `events[-1] == event` relies on exact JSON
  round-trip of the new string/int fields — trivially stable.

## Not implemented (explicit)
- No relay CLI to resolve an `unknown_outcome` (Gateway API only), unchanged from (A).
- Audit DQ1 (pending-sample delivery at the end of the last/stopped episode), DQ2 (high-entropy session seed),
  DQ6 (directory fsync), DQ7 (CLI reads the request file before the size check), DQ8 (`goal` publication) — left
  as coordinator decisions; none is a defect against the current brief.
- README text (stale `*.tmp` sweep after hard crashes, lock-owner check, `--allow-frozen-seed`) not written.
- `init` keeps the random `uuid4` session id.
