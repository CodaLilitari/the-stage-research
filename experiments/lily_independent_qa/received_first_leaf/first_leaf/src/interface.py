"""Strict simulation-only action gateway; no network, shell, or hardware path.

This is a unit-tested reference contract, not a physical safety controller.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

ACTIONS = ("k0", "k1", "k2", "k3", "coast", "stop")
FIELDS = {"schema", "request_id", "session_id", "body_revision", "sequence",
          "observation_id", "expires_tick", "action"}

def parse_request(raw: bytes) -> dict[str, Any]:
    if len(raw) > 16384:
        raise ValueError("Request exceeds 16 KiB")
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise ValueError("Duplicate JSON key")
            obj[k] = v
        return obj
    request = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
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

@dataclass
class Gateway:
    session_id: str
    body_revision: str = "planar-v1"
    sequence: int = 0
    tick: int = 0
    observation_id: str = "o0"
    stopped: bool = False
    cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def admit(self, raw: bytes) -> dict[str, Any]:
        r = parse_request(raw)
        sha = hashlib.sha256(json.dumps(r, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = r["request_id"]
        if key in self.cache:
            entry = self.cache[key]
            if entry["request_sha256"] != sha:
                raise ValueError("Request ID reused with different content")
            return {**entry, "duplicate": True, "dispatch": False}
        reason = None
        if r["session_id"] != self.session_id:
            reason = "session_mismatch"
        elif r["body_revision"] != self.body_revision:
            reason = "body_mismatch"
        elif r["action"] == "stop":
            self.stopped = True  # Current-session stop does not require a fresh sensor frame.
        elif self.stopped:
            reason = "stop_latched"
        elif r["sequence"] != self.sequence:
            reason = "sequence_mismatch"
        elif r["observation_id"] != self.observation_id:
            reason = "observation_mismatch"
        elif r["expires_tick"] < self.tick or r["expires_tick"] > self.tick + 5:
            reason = "invalid_deadline"
        admitted = reason is None
        receipt = {"request_id": key, "request_sha256": sha, "requested_action": r["action"],
                   "admitted": admitted, "reason": reason, "duplicate": False,
                   "dispatch": admitted and r["action"] != "stop", "stop_latched": self.stopped,
                   "execution_status": "not_dispatched"}
        self.cache[key] = receipt
        return dict(receipt)

    def record_execution(self, request_id: str, executed_action: str) -> None:
        receipt = self.cache.get(request_id)
        if not receipt or not receipt["dispatch"] or receipt["execution_status"] != "not_dispatched":
            raise ValueError("No unique admitted pending command")
        if executed_action != receipt["requested_action"]:
            raise ValueError("Substitution requires a distinct, explicit contract")
        receipt["execution_status"] = "verified_simulator_transition"
        receipt["executed_action"] = executed_action
        self.sequence += 1
        self.tick += 1
        self.observation_id = f"o{self.tick}"
