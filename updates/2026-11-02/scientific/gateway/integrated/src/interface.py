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
