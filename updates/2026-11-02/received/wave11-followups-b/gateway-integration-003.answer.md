# gateway-integration-003 — integrated GW-ASYNC0 gateway with audit findings D1–D6

Static contribution by Claude (Anthropic), coordinated by Red for Richard (Andrei) Pemberton. **Nothing below was executed by me**; every predicted outcome is from reading the verbatim sources. Credits: original interface/relay/simulator/tests — Lilitari (Lily); GW-ASYNC0 lifecycle design and v2 regressions — Coda (Codex Lily) with Richard Pemberton; invariant table — truncated Claude Fable 5.1 contribution; lifecycle implementation (A) and audit (B) — Claude (Anthropic) in earlier waves; execution receipts — Red.

## Summary of what this delivers

| File | Status |
|---|---|
| `src/interface.py` | **Byte-identical to (A) wave 6** (sha256 `559d4a22…`). D1's interface half (bounded nesting → `ValueError`) is already there as `check_json_depth`/`MAX_JSON_DEPTH = 32`; the audit's `MAX_NESTING = 16` variant is superseded (lifecycle tests pin 32). Reproduced in full so extraction is mechanical. |
| `src/relay.py` | (A)'s lifecycle + D1 (durable rejection for non-`ValueError` admission failures, with in-memory rollback to the committed gateway), D2 (`request_bytes_sha256`, `request_bytes_len`, `error_type`), D3 (temp-file cleanup), D4 (owned writer lock), D5 (all constants from the embedded protocol), D6 (frozen-seed guard, `--allow-frozen-seed`), and the explicit post-commit export decision (`ExportAfterCommitError`). |
| `tests/test_audit_first_leaf_v2.py` | The 16 audit tests adapted to the lifecycle API (3 adapted assertions, each annotated `# ADAPTED`). Predicted 16/16. |
| `tests/test_gateway_regressions_v3.py` | Coda's 14 v2 regressions translated (6 kept, 8 adapted, 0 retired) with the intent map in the docstring and below. Predicted 14/14. |
| `docs/gateway_lifecycle_v1/INTEGRATION_NOTE.md` | Decision record, adaptation tables, predictions, unimplemented list. |

FILE: src/interface.py
```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Original interface contract: Lilitari (Lily), via ChatGPT.
# GW-ASYNC0 lifecycle, validated restoration, legacy migration and bounded JSON depth:
# Coda (Codex Lily), collaborating with Richard Pemberton, 2026-11. MIT License; see LICENSE.
"""Strict simulation-only action gateway; no network, shell, or hardware path.

This is a unit-tested reference contract, not a physical safety controller.

GW-ASYNC0 receipt lifecycle (local simulator scope):

  admit(action)   -> admitted_pending    dispatch=True: exactly one dispatch is authorized
  admit(stop)     -> stop_acknowledged   latches session/body; cancels only an undispatched admission
  admit(invalid)  -> rejected            reason recorded; never admitted
  mark_dispatched    admitted_pending -> dispatched
  record_execution   dispatched       -> verified_simulator_transition  (advances sequence/tick/observation)
  record_failure     dispatched       -> verified_failure               (slot released, no advance)
  mark_unknown       dispatched       -> unknown_outcome                (slot retained)
  resolve_unknown    unknown_outcome  -> verified_simulator_transition | verified_failure
  stop               admitted_pending -> cancelled_before_dispatch      (dispatched/unknown work is
                                                                         reported outstanding, never relabelled)

At most one receipt is in flight (admitted_pending, dispatched, unknown_outcome); `active_request_id`
names it and a distinct action meanwhile is rejected with reason `command_pending`. Cached duplicates
return the current receipt with dispatch=False and never change state. Restoring a serialized gateway
re-validates every receipt and the active identity and refuses inconsistent state instead of repairing it.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field, fields as dataclass_fields
import hashlib
import json
from typing import Any

ACTIONS = ("k0", "k1", "k2", "k3", "coast", "stop")
FIELDS = {"schema", "request_id", "session_id", "body_revision", "sequence",
          "observation_id", "expires_tick", "action"}
MAX_REQUEST_BYTES = 16384
MAX_JSON_DEPTH = 32  # a valid request has depth 1; the bound keeps rejection of deep input a ValueError

GATEWAY_SCHEMA = "stage.gateway.v2"
LEGACY_EXECUTION_STATUS = "not_dispatched"  # pre-lifecycle catch-all status; migrated explicitly only

ADMITTED_PENDING = "admitted_pending"
DISPATCHED = "dispatched"
VERIFIED_SIMULATOR_TRANSITION = "verified_simulator_transition"
VERIFIED_FAILURE = "verified_failure"
CANCELLED_BEFORE_DISPATCH = "cancelled_before_dispatch"
UNKNOWN_OUTCOME = "unknown_outcome"
REJECTED = "rejected"
STOP_ACKNOWLEDGED = "stop_acknowledged"
IN_FLIGHT = frozenset({ADMITTED_PENDING, DISPATCHED, UNKNOWN_OUTCOME})
RESOLUTIONS = frozenset({VERIFIED_SIMULATOR_TRANSITION, VERIFIED_FAILURE})
STATUSES = IN_FLIGHT | RESOLUTIONS | {CANCELLED_BEFORE_DISPATCH, REJECTED, STOP_ACKNOWLEDGED}
RECEIPT_FIELDS = frozenset({"request_id", "request_sha256", "requested_action", "admitted", "reason",
                            "duplicate", "dispatch", "stop_latched", "execution_status"})


def _reject_constant(name: str) -> Any:
    raise ValueError("Nonfinite JSON")


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in items:
        if key in obj:
            raise ValueError("Duplicate JSON key")
        obj[key] = value
    return obj


def check_json_depth(text: str, limit: int = MAX_JSON_DEPTH) -> None:
    """Bound container nesting iteratively before json.loads, so deep input is a ValueError.

    Only `[`/`{` outside JSON strings count; string escapes are honoured. Malformed text is
    left for json.loads to reject (JSONDecodeError is a ValueError).
    """
    depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise ValueError(f"JSON nesting deeper than {limit} levels")
        elif ch in "]}":
            depth -= 1


def parse_request(raw: bytes | bytearray | str) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")  # UnicodeEncodeError is a ValueError
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("Request must be bytes")
    data = bytes(raw)
    if len(data) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds 16 KiB")
    text = data.decode(json.detect_encoding(data))  # UnicodeDecodeError is a ValueError
    check_json_depth(text)
    request = json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    if not isinstance(request, dict) or set(request) != FIELDS:
        raise ValueError("Request has missing or undeclared fields")
    for key in ("schema", "request_id", "session_id", "body_revision", "observation_id", "action"):
        if not isinstance(request[key], str) or not 1 <= len(request[key]) <= 128:
            raise ValueError("Invalid text field")
    if request["schema"] != "stage.action.v1" or request["action"] not in ACTIONS:
        raise ValueError("Unknown schema or action")
    for key in ("sequence", "expires_tick"):
        if type(request[key]) is not int or not 0 <= request[key] < 2**53:
            raise ValueError("Invalid integer field")
    return request


def request_digest(request: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"A non-empty {label} is required")
    return value


def validate_receipt(key: str, entry: Any) -> None:
    """Reject a cached receipt whose fields are inconsistent with its execution_status."""
    if not isinstance(entry, dict) or not RECEIPT_FIELDS <= set(entry):
        raise ValueError(f"Receipt {key!r} is missing required fields")
    if entry["request_id"] != key:
        raise ValueError(f"Receipt {key!r} carries a different request_id")
    sha = entry["request_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or set(sha) - set("0123456789abcdef"):
        raise ValueError(f"Receipt {key!r} has an invalid request_sha256")
    status = entry["execution_status"]
    if status not in STATUSES:
        raise ValueError(f"Receipt {key!r} has unknown execution_status {status!r}; explicit migration required")
    for name in ("admitted", "duplicate", "dispatch", "stop_latched"):
        if type(entry[name]) is not bool:
            raise ValueError(f"Receipt {key!r} field {name!r} must be a bool")
    if entry["duplicate"]:
        raise ValueError(f"Receipt {key!r}: the cache stores originals, never duplicate views")
    if entry["dispatch"] != (status == ADMITTED_PENDING):
        raise ValueError(f"Receipt {key!r}: dispatch authorization inconsistent with status {status!r}")
    action = entry["requested_action"]
    if action not in ACTIONS:
        raise ValueError(f"Receipt {key!r} has unknown requested_action {action!r}")
    if status == REJECTED:
        if entry["admitted"] or not isinstance(entry["reason"], str) or not entry["reason"]:
            raise ValueError(f"Receipt {key!r}: a rejected receipt is not admitted and carries a reason")
    else:
        if not entry["admitted"] or entry["reason"] is not None:
            raise ValueError(f"Receipt {key!r}: an admitted receipt carries no rejection reason")
        if (action == "stop") != (status == STOP_ACKNOWLEDGED):
            raise ValueError(f"Receipt {key!r}: stop receipts and action receipts are distinct")
    if ("executed_action" in entry) != (status == VERIFIED_SIMULATOR_TRANSITION):
        raise ValueError(f"Receipt {key!r}: executed_action belongs only to verified transitions")
    if status == VERIFIED_SIMULATOR_TRANSITION and entry["executed_action"] != action:
        raise ValueError(f"Receipt {key!r}: executed action differs from requested action")


@dataclass
class Gateway:
    session_id: str
    body_revision: str = "planar-v1"
    sequence: int = 0
    tick: int = 0
    observation_id: str = "o0"
    stopped: bool = False
    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_request_id: str | None = None
    schema: str = GATEWAY_SCHEMA

    def __post_init__(self) -> None:
        self.validate()

    # -- restoration ------------------------------------------------------------------
    @classmethod
    def restore(cls, state: dict[str, Any]) -> Gateway:
        """Strict restoration from a serialized dict: exact v2 key set, then full validation."""
        names = {f.name for f in dataclass_fields(cls)}
        if not isinstance(state, dict) or set(state) != names:
            raise ValueError("Gateway state keys do not match stage.gateway.v2; explicit migration required")
        return cls(**state)

    def validate(self) -> None:
        """Reject inconsistent state. Never repairs: the caller decides what the evidence supports."""
        if self.schema != GATEWAY_SCHEMA:
            raise ValueError(f"Unsupported gateway schema {self.schema!r}; explicit migration required")
        for name in ("session_id", "body_revision", "observation_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Gateway {name} must be a non-empty string")
        for name in ("sequence", "tick"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"Gateway {name} must be a non-negative integer")
        if type(self.stopped) is not bool:
            raise ValueError("Gateway stopped flag must be a bool")
        if not isinstance(self.cache, dict):
            raise ValueError("Gateway cache must be a dict keyed by request_id")
        if self.active_request_id is not None and not isinstance(self.active_request_id, str):
            raise ValueError("Gateway active_request_id must be a string or None")
        pending_keys = []
        for key, entry in self.cache.items():
            validate_receipt(key, entry)
            if entry["execution_status"] in IN_FLIGHT:
                pending_keys.append(key)
        if len(pending_keys) > 1:
            raise ValueError(f"Inconsistent gateway state: {len(pending_keys)} receipts in flight: {sorted(pending_keys)}")
        expected = pending_keys[0] if pending_keys else None
        if self.active_request_id != expected:
            raise ValueError(f"Inconsistent gateway state: active_request_id {self.active_request_id!r} "
                             f"does not match the in-flight receipt {expected!r}")
        if self.stopped and expected is not None and self.cache[expected]["execution_status"] == ADMITTED_PENDING:
            raise ValueError("Inconsistent gateway state: a stopped gateway cannot hold an undispatched admission")

    # -- views ------------------------------------------------------------------------
    def receipt(self, request_id: str) -> dict[str, Any]:
        entry = self.cache.get(request_id)
        if entry is None:
            raise ValueError(f"Unknown request_id {request_id!r}")
        return dict(entry)

    def in_flight(self) -> dict[str, Any] | None:
        return None if self.active_request_id is None else dict(self.cache[self.active_request_id])

    # -- admission --------------------------------------------------------------------
    def admit(self, raw: bytes | bytearray | str, block_reason: str | None = None) -> dict[str, Any]:
        """Validate a request and issue a receipt.

        `block_reason` is a caller-side condition (the relay passes 'episode_complete') that
        rejects a fresh non-stop action after every gateway check passes. Stop is never blocked.
        """
        if block_reason is not None:
            _require_text(block_reason, "block_reason")
        r = parse_request(raw)
        sha = request_digest(r)
        key = r["request_id"]
        entry = self.cache.get(key)
        if entry is not None:
            if entry["request_sha256"] != sha:
                raise ValueError("Request ID reused with different content")
            return {**entry, "duplicate": True, "dispatch": False}  # current state; never a redispatch
        reason: str | None = None
        extra: dict[str, Any] = {}
        if r["session_id"] != self.session_id:
            reason = "session_mismatch"
        elif r["body_revision"] != self.body_revision:
            reason = "body_mismatch"
        elif r["action"] == "stop":
            extra = self._latch_stop(key)  # current-session stop needs no fresh frame or free slot
        elif self.stopped:
            reason = "stop_latched"
        elif self.active_request_id is not None:
            reason = "command_pending"
        elif r["sequence"] != self.sequence:
            reason = "sequence_mismatch"
        elif r["observation_id"] != self.observation_id:
            reason = "observation_mismatch"
        elif r["expires_tick"] < self.tick or r["expires_tick"] > self.tick + 5:
            reason = "invalid_deadline"
        elif block_reason is not None:
            reason = block_reason
        if reason is not None:
            status = REJECTED
        elif r["action"] == "stop":
            status = STOP_ACKNOWLEDGED
        else:
            status = ADMITTED_PENDING
        receipt = {"request_id": key, "request_sha256": sha, "requested_action": r["action"],
                   "admitted": reason is None, "reason": reason, "duplicate": False,
                   "dispatch": status == ADMITTED_PENDING, "stop_latched": self.stopped,
                   "execution_status": status, **extra}
        self.cache[key] = receipt
        if status == ADMITTED_PENDING:
            self.active_request_id = key
        return dict(receipt)

    def _latch_stop(self, stop_request_id: str) -> dict[str, Any]:
        """Latch stop now. Cancel only an undispatched admission; report dispatched or unknown
        work as outstanding, because this gateway has no evidence that it did not happen."""
        self.stopped = True
        rid = self.active_request_id
        if rid is None:
            return {}
        entry = self.cache[rid]
        if entry["execution_status"] == ADMITTED_PENDING:
            entry.update({"execution_status": CANCELLED_BEFORE_DISPATCH, "dispatch": False,
                          "stop_latched": True, "cancelled_by": stop_request_id})
            self.active_request_id = None
            return {"cancelled_request_id": rid}
        return {"outstanding_request_id": rid, "outstanding_status": entry["execution_status"]}

    # -- dispatch and outcome boundaries ----------------------------------------------
    def _require_active(self, request_id: str, allowed: frozenset[str]) -> dict[str, Any]:
        entry = self.cache.get(request_id)
        found = None if entry is None else entry["execution_status"]
        if entry is None or self.active_request_id != request_id or found not in allowed:
            raise ValueError(f"No active receipt {request_id!r} in state {sorted(allowed)}; found {found!r}")
        return entry

    def mark_dispatched(self, request_id: str) -> dict[str, Any]:
        """Explicit dispatch boundary: the single authorized dispatch is now consumed."""
        entry = self._require_active(request_id, frozenset({ADMITTED_PENDING}))
        if self.stopped:  # unreachable in a consistent state (stop cancels undispatched admissions)
            raise ValueError("Stopped gateway cannot dispatch")
        entry.update({"execution_status": DISPATCHED, "dispatch": False, "stop_latched": self.stopped})
        return dict(entry)

    def record_execution(self, request_id: str, executed_action: str) -> dict[str, Any]:
        """Verified simulator transition for a dispatched command; with resolve_unknown, the
        only path that advances sequence/tick/observation."""
        entry = self._require_active(request_id, frozenset({DISPATCHED}))
        if executed_action != entry["requested_action"]:
            raise ValueError("Substitution requires a distinct, explicit contract")
        return self._verify_transition(entry, executed_action)

    def record_failure(self, request_id: str, reason: str) -> dict[str, Any]:
        """Known failure of a dispatched command: releases the slot without advancing."""
        _require_text(reason, "failure reason")
        entry = self._require_active(request_id, frozenset({DISPATCHED}))
        entry.update({"execution_status": VERIFIED_FAILURE, "failure_reason": reason,
                      "dispatch": False, "stop_latched": self.stopped})
        self.active_request_id = None
        return dict(entry)

    def mark_unknown(self, request_id: str, reason: str) -> dict[str, Any]:
        """Outcome of a dispatched command is unresolved: the slot stays held."""
        _require_text(reason, "unknown-outcome reason")
        entry = self._require_active(request_id, frozenset({DISPATCHED}))
        entry.update({"execution_status": UNKNOWN_OUTCOME, "unknown_reason": reason,
                      "dispatch": False, "stop_latched": self.stopped})
        return dict(entry)

    def resolve_unknown(self, request_id: str, outcome: str,
                        executed_action: str | None = None) -> dict[str, Any]:
        """Explicit trusted resolution of an unknown outcome. The caller supplies the evidence
        decision; a transition needs the explicit executed action, a failure must not carry one."""
        entry = self._require_active(request_id, frozenset({UNKNOWN_OUTCOME}))
        if outcome == VERIFIED_SIMULATOR_TRANSITION:
            if executed_action is None:
                raise ValueError("Resolving a transition requires the explicit executed action")
            if executed_action != entry["requested_action"]:
                raise ValueError("Substitution requires a distinct, explicit contract")
            entry["resolved_from"] = UNKNOWN_OUTCOME
            return self._verify_transition(entry, executed_action)
        if outcome == VERIFIED_FAILURE:
            if executed_action is not None:
                raise ValueError("A verified failure carries no executed action")
            entry.update({"execution_status": VERIFIED_FAILURE, "resolved_from": UNKNOWN_OUTCOME,
                          "failure_reason": "unknown outcome resolved as verified failure",
                          "dispatch": False, "stop_latched": self.stopped})
            self.active_request_id = None
            return dict(entry)
        raise ValueError(f"Unsupported resolution outcome {outcome!r}")

    def _verify_transition(self, entry: dict[str, Any], executed_action: str) -> dict[str, Any]:
        entry.update({"execution_status": VERIFIED_SIMULATOR_TRANSITION, "executed_action": executed_action,
                      "dispatch": False, "stop_latched": self.stopped})
        self.active_request_id = None
        self.sequence += 1
        self.tick += 1
        self.observation_id = f"o{self.tick}"
        return dict(entry)


def migrate_legacy_gateway(state: dict[str, Any]) -> dict[str, Any]:
    """Explicit one-way migration of a pre-lifecycle gateway dict. Fails closed on ambiguity.

    Legacy receipts used execution_status "not_dispatched" for rejections, stop receipts and
    admitted-but-unrecorded actions alike, and verified receipts kept dispatch=True. A legacy
    receipt admitted for dispatch but never recorded cannot be classified from the saved state
    alone, so migration refuses rather than guessing its outcome. The input is not mutated.
    """
    legacy_keys = {"session_id", "body_revision", "sequence", "tick", "observation_id", "stopped", "cache"}
    if not isinstance(state, dict) or set(state) != legacy_keys:
        raise ValueError("Not a legacy gateway state (expected exactly the pre-lifecycle keys)")
    out = copy.deepcopy(state)
    for key, entry in out["cache"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"Legacy receipt {key!r} is not an object")
        status = entry.get("execution_status")
        if status == VERIFIED_SIMULATOR_TRANSITION:
            if entry.get("executed_action") != entry.get("requested_action"):
                raise ValueError(f"Legacy verified receipt {key!r} has an inconsistent executed_action")
            entry["dispatch"] = False
        elif status == LEGACY_EXECUTION_STATUS:
            if entry.get("dispatch") is True:
                raise ValueError(f"Ambiguous legacy receipt {key!r}: admitted for dispatch but never "
                                 "recorded; refusing to guess its outcome")
            if entry.get("admitted") is True and entry.get("requested_action") == "stop" and entry.get("reason") is None:
                entry["execution_status"] = STOP_ACKNOWLEDGED
            elif entry.get("admitted") is False and isinstance(entry.get("reason"), str) and entry.get("reason"):
                entry["execution_status"] = REJECTED
            else:
                raise ValueError(f"Unclassifiable legacy receipt {key!r}")
        else:
            raise ValueError(f"Legacy receipt {key!r} has unexpected execution_status {status!r}")
    out["active_request_id"] = None
    out["schema"] = GATEWAY_SCHEMA
    Gateway.restore(out)  # full consistency validation; raises before anything is returned
    return out
```

FILE: src/relay.py
```python
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
```

FILE: tests/test_audit_first_leaf_v2.py
```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Audit tests: Claude (Anthropic) for Red, wave 7 (firstleaf-sim-audit-001). Adaptation to the GW-ASYNC0
# lifecycle API: Claude (Anthropic), coordinated by Red, 2026-11 (gateway-integration-003). Written
# statically; not executed by the author.
"""Audit tests (firstleaf-sim-audit-001) adapted to the integrated GW-ASYNC0 relay.

Run from the package root:  python -m unittest tests.test_audit_first_leaf_v2 -v

Every test is now expected to PASS on the integrated code. Three assertions were adapted; each
is marked `# ADAPTED (lifecycle)` with the reason:
  control_idempotency        receipt['dispatch'] means "a dispatch is currently authorized" and is
                             consumed at mark_dispatched, so the committed receipt of an executed step
                             carries dispatch=False; "it was dispatched exactly once" is asserted via
                             event['executed'] and execution_status instead (intent preserved).
  control_single_commit      a post-commit export failure is deliberately raised as the distinct
                             ExportAfterCommitError (RuntimeError subclass, __cause__ = the OSError)
                             carrying the committed event, never as a bare OSError that could be mistaken
                             for a pre-commit replacement failure (design change; see INTEGRATION_NOTE).
  finding_D1_non_valueerror  Gateway.admit now takes block_reason; the stand-in accepts it so the injected
                             failure is the RecursionError under test rather than an incidental TypeError.
The two PriorFinding tests (Coda's SCOPE_GAP defects) are fixed by the lifecycle and are now controls.
Deviation from the "no file writes" convention: sessions live in a tempfile.TemporaryDirectory
(AUDIT_TMPDIR overrides the location), like the package's own relay tests; os.fsync is a no-op here.
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
    """Properties the static reading says HOLD on the integrated code."""

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
        # ADAPTED (lifecycle): the original asserted first['receipt']['dispatch'] is True. Under GW-ASYNC0
        # `dispatch` is the *current* single-dispatch authorization, consumed by mark_dispatched, so the
        # committed receipt of an executed step carries dispatch=False. The audit's intent, "this request
        # was dispatched exactly once and executed", is asserted directly:
        self.assertTrue(first['executed'])
        self.assertFalse(first['receipt']['duplicate'])
        self.assertEqual(first['receipt']['execution_status'], 'verified_simulator_transition')
        self.assertFalse(first['receipt']['dispatch'], 'authorization is consumed, not re-issuable')
        self.assertEqual(self.state()['tick'], 1)
        for _ in range(3):
            again = transact(self.d, raw)
            self.assertTrue(again['receipt']['duplicate'])
            self.assertFalse(again['receipt']['dispatch'])
            self.assertFalse(again['executed'])
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

        # ADAPTED (lifecycle): the original expected the bare OSError to propagate. The integrated relay
        # deliberately raises the distinct ExportAfterCommitError (a RuntimeError whose __cause__ is the
        # OSError) carrying the committed event, so "committed, views stale" can never be confused with a
        # pre-commit replacement failure. The audit's intent (commit survives, retry is a truthful
        # duplicate, `export` regenerates) is unchanged and asserted below.
        with mock.patch.object(relay, 'export', failing_export):
            with self.assertRaises(relay.ExportAfterCommitError) as ctx:
                transact(self.d, raw2)
        self.assertIsInstance(ctx.exception, RuntimeError)
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertTrue(ctx.exception.committed)
        self.assertEqual(ctx.exception.event['receipt']['execution_status'], 'verified_simulator_transition')
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
    """Audit findings D1-D6; expected PASS on the integrated code."""

    def test_finding_D1_non_valueerror_from_admit_is_still_logged(self):
        # ADAPTED (lifecycle): Gateway.admit now takes block_reason; the stand-in must accept it so the
        # injected failure is the RecursionError under test rather than an incidental TypeError.
        def exploding_admit(self_gateway, raw, block_reason=None):
            raise RecursionError('synthetic: decoder recursion limit')

        before = self.state()
        with mock.patch.object(interface.Gateway, 'admit', exploding_admit):
            try:
                event = transact(self.d, self.req('k0', 'deep'))
            except RecursionError:
                event = None
        events = self.events()
        self.assertEqual(len(events), 1, 'the attempt left no durable receipt')
        self.assertIsNotNone(event, 'transact raised instead of returning a rejection event')
        self.assertEqual(events[0]['event'], 'rejected_invalid_request')
        self.assertEqual(events[0]['error_type'], 'RecursionError')
        self.assertFalse(events[0]['executed'])
        self.assertEqual(self.state()['tick'], 0)
        self.assertEqual(self.state()['gateway'], before['gateway'], 'the committed gateway is untouched')
        self.assertFalse((self.d / 'writer.lock').exists())

    def test_finding_D1_deep_nesting_probe_in_child_process(self):
        """ENVIRONMENT-DEPENDENT. 8000-level nesting (16,000 bytes, under the 16 KiB cap) is fed to the
        relay in a child process so a possible interpreter crash cannot take down this run. With the
        gateway's nesting bound the input is rejected as a ValueError before the decoder recurses."""
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
        self.assertEqual(event.get('error_type'), 'JSONDecodeError')
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
                self.assertFalse((Path(tmp) / 'private_state.json').exists())
            with tempfile.TemporaryDirectory(dir=os.environ.get('AUDIT_TMPDIR')) as tmp:
                init(Path(tmp), seed, ACTOR, allow_frozen_seed=True)  # explicit, non-model-facing override
                self.assertTrue((Path(tmp) / 'private_state.json').exists())


class PriorFindingGatewayTests(unittest.TestCase):
    """Coda (Codex Lily), SCOPE_GAP.md: standalone Gateway pending-state defects. Fixed by the GW-ASYNC0
    lifecycle (implementation A); kept verbatim as controls, expected PASS."""

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

FILE: tests/test_gateway_regressions_v3.py
```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held.
# Scenarios: Coda (Codex Lily), tests/test_gateway_regressions_v2.py (kept frozen). Translation to the
# GW-ASYNC0 lifecycle API: Claude (Anthropic), coordinated by Red, 2026-11 (gateway-integration-003).
# Written statically; not executed by the author.
"""v3: Coda's 14 frozen v2 regressions translated to the GW-ASYNC0 lifecycle API.

Intent map (K = kept verbatim, A = adapted; nothing retired, every v2 scenario has a lifecycle meaning):
  PendingCommandTests
    second_distinct_pending_request_is_rejected           K
    duplicate_pending_suppression_does_not_release_slot   A  'not_dispatched' -> ADMITTED_PENDING (the legacy
                                                             catch-all status was split into explicit states);
                                                             mark_dispatched before record_execution (dispatch
                                                             is an explicit boundary, never implied by admission)
    fresh_state_request_after_execution_is_admitted       A  explicit mark_dispatched
    pending_rejection_is_not_silently_retried             A  explicit mark_dispatched
  StopPendingTests
    stop_cancels_and_preserves_pending_receipt            A  'cancelled_pending_by_stop' -> CANCELLED_BEFORE_DISPATCH:
                                                             same state, design vocabulary (stop cancels only an
                                                             undispatched admission); every other assertion identical
    record_after_stop_cannot_verify_or_advance            K
    duplicate_cancelled_request_remains_cancelled         A  status rename only
    invalid_session_stop_does_not_cancel_pending          A  explicit mark_dispatched
    invalid_body_stop_does_not_cancel_pending             A  explicit mark_dispatched
    stop_preserves_verified_earlier_transition            A  explicit mark_dispatched + status rename
    cancelled_state_round_trip_does_not_reenable_execution K  (asdict round trip carries schema/active_request_id)
  NestedJsonTests (3)                                     K  bounded nesting is a ValueError containing 'JSON nesting';
                                                             relay events now also carry request_bytes_* / error_type,
                                                             all JSON-stable, so events[-1] == event still holds
"""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from first_leaf import canonical
from interface import ADMITTED_PENDING, CANCELLED_BEFORE_DISPATCH, DISPATCHED, Gateway, parse_request
from relay import init, transact


def request(**changes):
    value = {'schema': 'stage.action.v1', 'request_id': 'r0', 'session_id': 'test',
             'body_revision': 'planar-v1', 'sequence': 0, 'observation_id': 'o0',
             'expires_tick': 2, 'action': 'k0'}
    value.update(changes)
    return canonical(value)


def caught(call):
    try:
        return call(), None
    except Exception as exc:
        return None, exc


def nested_request():
    # Schema is deliberately invalid, but the decoder must reject with a
    # handled input exception before schema validation, not lose the receipt.
    value = b'{"x":' + b'[' * 6000 + b'0' + b']' * 6000 + b'}'
    assert len(value) < 16384
    return value


class PendingCommandTests(unittest.TestCase):
    def test_second_distinct_pending_request_is_rejected(self):  # K
        g = Gateway('test')
        first = g.admit(request())
        second = g.admit(request(request_id='r1', action='k1'))
        self.assertTrue(first['dispatch'])
        self.assertFalse(second['admitted'], 'Two distinct commands admitted at one pending sequence')
        self.assertFalse(second['dispatch'])
        self.assertEqual(second['reason'], 'command_pending')
        self.assertEqual((g.sequence, g.tick, g.observation_id), (0, 0, 'o0'))

    def test_duplicate_pending_suppression_does_not_release_slot(self):  # A
        g = Gateway('test'); g.admit(request())
        duplicate = g.admit(request())
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertEqual(g.cache['r0']['execution_status'], ADMITTED_PENDING)  # was 'not_dispatched'
        self.assertEqual(g.active_request_id, 'r0', 'the duplicate view did not release the slot')
        with self.assertRaises(ValueError):
            g.admit(request(action='k1'))
        g.mark_dispatched('r0')  # explicit boundary added by the lifecycle
        self.assertEqual(g.cache['r0']['execution_status'], DISPATCHED)
        g.record_execution('r0', 'k0')
        self.assertEqual((g.sequence, g.tick), (1, 1))

    def test_fresh_state_request_after_execution_is_admitted(self):  # A
        g = Gateway('test'); g.admit(request()); g.mark_dispatched('r0'); g.record_execution('r0', 'k0')
        result = g.admit(request(request_id='r2', sequence=1, observation_id='o1', expires_tick=3))
        self.assertTrue(result['admitted']); self.assertTrue(result['dispatch'])

    def test_pending_rejection_is_not_silently_retried(self):  # A
        g = Gateway('test'); g.admit(request())
        raw = request(request_id='r1')
        rejected = g.admit(raw)
        self.assertFalse(rejected['admitted'])
        g.mark_dispatched('r0'); g.record_execution('r0', 'k0')
        duplicate = g.admit(raw)
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertFalse(duplicate['admitted']); self.assertEqual(duplicate['reason'], 'command_pending')


class StopPendingTests(unittest.TestCase):
    def test_stop_cancels_and_preserves_pending_receipt(self):  # A (status rename only)
        g = Gateway('test'); admitted = g.admit(request())
        stopped = g.admit(request(request_id='stop', action='stop', observation_id='old', expires_tick=0))
        self.assertTrue(stopped['admitted']); self.assertFalse(stopped['dispatch'])
        retained = g.cache['r0']
        self.assertEqual(retained['request_sha256'], admitted['request_sha256'])
        self.assertTrue(retained['admitted'], 'Preserve the earlier admission as historical fact')
        self.assertFalse(retained['dispatch'], 'Stop must revoke the pending gateway dispatch')
        self.assertEqual(retained['execution_status'], CANCELLED_BEFORE_DISPATCH)  # was 'cancelled_pending_by_stop'
        self.assertTrue(retained['stop_latched'])
        self.assertNotIn('executed_action', retained)
        self.assertEqual((g.sequence, g.tick), (0, 0))

    def test_record_after_stop_cannot_verify_or_advance(self):  # K
        g = Gateway('test'); g.admit(request()); g.admit(request(request_id='stop', action='stop'))
        _, error = caught(lambda: g.record_execution('r0', 'k0'))
        self.assertIsInstance(error, ValueError, 'Stopped gateway accepted a pending execution record')
        self.assertEqual((g.sequence, g.tick), (0, 0))
        self.assertNotIn('executed_action', g.cache['r0'])

    def test_duplicate_cancelled_request_remains_cancelled(self):  # A (status rename only)
        g = Gateway('test'); raw = request(); g.admit(raw)
        g.admit(request(request_id='stop', action='stop'))
        duplicate = g.admit(raw)
        self.assertTrue(duplicate['duplicate']); self.assertFalse(duplicate['dispatch'])
        self.assertEqual(duplicate['execution_status'], CANCELLED_BEFORE_DISPATCH)

    def test_invalid_session_stop_does_not_cancel_pending(self):  # A
        g = Gateway('test'); g.admit(request())
        result = g.admit(request(request_id='foreign-stop', action='stop', session_id='foreign'))
        self.assertEqual(result['reason'], 'session_mismatch'); self.assertFalse(g.stopped)
        self.assertEqual(g.cache['r0']['execution_status'], ADMITTED_PENDING)
        g.mark_dispatched('r0'); g.record_execution('r0', 'k0'); self.assertEqual(g.tick, 1)

    def test_invalid_body_stop_does_not_cancel_pending(self):  # A
        g = Gateway('test'); g.admit(request())
        result = g.admit(request(request_id='foreign-stop', action='stop', body_revision='foreign'))
        self.assertEqual(result['reason'], 'body_mismatch'); self.assertFalse(g.stopped)
        self.assertEqual(g.cache['r0']['execution_status'], ADMITTED_PENDING)
        g.mark_dispatched('r0'); g.record_execution('r0', 'k0'); self.assertEqual(g.tick, 1)

    def test_stop_preserves_verified_earlier_transition(self):  # A
        g = Gateway('test'); g.admit(request()); g.mark_dispatched('r0'); g.record_execution('r0', 'k0')
        earlier = copy.deepcopy(g.cache['r0'])
        g.admit(request(request_id='r1', sequence=1, observation_id='o1'))
        g.admit(request(request_id='stop', action='stop'))
        self.assertEqual(g.cache['r0'], earlier)
        self.assertEqual(g.cache['r1']['execution_status'], CANCELLED_BEFORE_DISPATCH)
        self.assertEqual((g.tick, g.sequence), (1, 1))

    def test_cancelled_state_round_trip_does_not_reenable_execution(self):  # K
        g = Gateway('test'); g.admit(request()); g.admit(request(request_id='stop', action='stop'))
        restored = Gateway(**json.loads(canonical(asdict(g))))
        _, error = caught(lambda: restored.record_execution('r0', 'k0'))
        self.assertIsInstance(error, ValueError)
        self.assertEqual(restored.tick, 0); self.assertTrue(restored.stopped)


class NestedJsonTests(unittest.TestCase):  # K
    def test_nested_decoder_exception_is_a_handled_value_error(self):
        _, error = caught(lambda: parse_request(nested_request()))
        self.assertIsInstance(error, ValueError, 'Deep request escaped as ' + type(error).__name__)
        self.assertIn('JSON nesting', str(error))

    def assert_relay_receipt(self, stopped):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            packet = init(directory, 20000, 'scripted_regression_not_hosted_model')
            if stopped:
                stop = dict(packet['request_template'], request_id='stop', action='stop')
                transact(directory, canonical(stop))
            before = json.loads((directory/'private_state.json').read_text())
            event, error = caught(lambda: transact(directory, nested_request()))
            self.assertIsNone(error, 'Relay raised instead of recording rejection: ' + type(error).__name__)
            self.assertEqual(event['event'], 'rejected_invalid_request')
            self.assertFalse(event['executed']); self.assertIn('JSON nesting', event['reason'])
            after = json.loads((directory/'private_state.json').read_text())
            for key in ['tick', 'episode', 'p', 'v', 'gateway', 'samples']:
                self.assertEqual(after[key], before[key], key)
            self.assertEqual(len(after['public_events']), len(before['public_events']) + 1)
            events = [json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1], event)
            self.assertFalse((directory/'writer.lock').exists())

    def test_nested_request_gets_durable_relay_rejection(self):
        self.assert_relay_receipt(False)

    def test_nested_request_after_stop_does_not_reset_session(self):
        self.assert_relay_receipt(True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
```

FILE: docs/gateway_lifecycle_v1/INTEGRATION_NOTE.md
```markdown
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
```

## Integration note (short form)

- **Design kept**: all of (A)'s GW-ASYNC0 lifecycle and `interface.py` byte-for-byte.
- **Fixed**: D1 (durable rejection + in-memory rollback to the committed gateway), D2 (byte-identified request events, `error_type`), D3 (no `*.tmp` residue), D4 (owned lock, owner-only release), D5 (protocol-derived constants everywhere the relay speaks or integrates), D6 (frozen-seed refusal with explicit override).
- **Decision**: post-commit export failure **propagates** as `ExportAfterCommitError` (a `RuntimeError` carrying the committed event; CLI reports `committed=true, export_failed=true`, exit 3). Cited: DESIGN.md's commit-point/regenerate-never-replay rule, the relay's "views are not witnesses" principle, and the need to distinguish "nothing happened" from "committed, views stale" without reading private state.
- **Assumptions (labelled)**: bundle text is byte-faithful; CPython ≥ 3.10; POSIX file semantics in Red's sandbox; `os.fsync` patched to a no-op in the audit base as before. All test outcomes above are predictions; Red's run is the arbiter and I will correct against the actual receipts.