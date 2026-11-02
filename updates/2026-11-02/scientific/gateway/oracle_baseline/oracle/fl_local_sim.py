#!/usr/bin/env python3
"""Standard-library test double of relay.py's public packet protocol for First Leaf.

Labelled replica (not the package's code) of: fixture generation, body vectors,
dynamics, delayed noisy samples, the gateway admission checks, the public packet
schema (stage.observation.v1), event/receipt shapes and the operator episode reset,
mirroring src/first_leaf.py, src/interface.py and src/relay.py (Lilitari, MIT,
Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held).
It imports nothing from the package so agent tests can run without it; byte-level
parity of fixtures/body vectors and trajectory parity with relay.py are checked in
tests/test_oracle.py when the package is importable.  No I/O.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from typing import Any

ACTIONS = ("k0", "k1", "k2", "k3", "coast", "stop")
FIELDS = {"schema", "request_id", "session_id", "body_revision", "sequence",
          "observation_id", "expires_tick", "action"}
EXECUTED = "verified_simulator_transition"

# Values copied from inputs/protocol.json (STAGE-FL1-R-20261015-r1); 'profile' mirrors profiles.primary.
DEFAULT_CFG: dict[str, Any] = {
    "episodes": 6,
    "steps_per_episode": 80,
    "body_schedule": ["A", "A", "A", "B", "B", "A"],
    "dynamics": {"dt": 0.1, "alpha": 0.75, "gain_A": 0.3, "gain_B_x": 0.21, "gain_B_y": 0.39},
    "observations": {"position_noise_scale": 0.01, "velocity_noise_scale": 0.03},
    "profile": {"delay": 2, "noise": True, "change": True},
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def merged_cfg(overrides: dict[str, Any] | None) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CFG)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def fixture(seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    """Same draw order as first_leaf.fixture, so the same seed gives the same fixture."""
    rng = random.Random(seed)
    mapping = list(range(4))
    rng.shuffle(mapping)
    goals, noise, shuffle = [], [], []
    for _ in range(cfg["episodes"]):
        theta = rng.uniform(-math.pi, math.pi)
        goals.append([math.cos(theta), math.sin(theta)])
        noise.append([[rng.uniform(-1, 1) for _ in range(4)]
                      for _ in range(cfg["steps_per_episode"] + 1)])
        shuffle.append([rng.randrange(4) for _ in range(cfg["steps_per_episode"])])
    return {"seed": seed, "mapping_A": mapping,
            "mapping_B": [(d + 1) % 4 for d in mapping],
            "goals": goals, "unit_noise": noise, "negative_labels": shuffle}


def body_vectors(cfg: dict[str, Any], fx: dict[str, Any], ep: int, profile: dict[str, Any]) -> list[list[float]]:
    is_b = cfg["body_schedule"][ep] == "B" and profile["change"]
    mapping = fx["mapping_B"] if is_b else fx["mapping_A"]
    dynamics = cfg["dynamics"]
    gx = dynamics["gain_B_x"] if is_b else dynamics["gain_A"]
    gy = dynamics["gain_B_y"] if is_b else dynamics["gain_A"]
    dirs = [[gx, 0.0], [0.0, gy], [-gx, 0.0], [0.0, -gy]]
    return [dirs[i][:] for i in mapping] + [[0.0, 0.0]]


def parse_request(raw: bytes) -> dict[str, Any]:
    """Replica of interface.parse_request."""
    if len(raw) > 16384:
        raise ValueError("Request exceeds 16 KiB")

    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise ValueError("Duplicate JSON key")
            obj[k] = v
        return obj

    def nonfinite(_):
        raise ValueError("Nonfinite JSON")

    request = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(request, dict) or set(request) != FIELDS:
        raise ValueError("Request has missing or undeclared fields")
    for key in ("schema", "request_id", "session_id", "body_revision", "observation_id", "action"):
        if not isinstance(request[key], str) or not 1 <= len(request[key]) <= 128:
            raise ValueError("Invalid text field")
    if request["schema"] != "stage.action.v1" or request["action"] not in ACTIONS:
        raise ValueError("Unknown schema or action")
    for key in ("sequence", "expires_tick"):
        if type(request[key]) is not int or not 0 <= request[key] < 2 ** 53:
            raise ValueError("Invalid integer field")
    return request


class LocalRelay:
    """In-memory relay session with the same public packet/event schema as relay.py."""

    def __init__(self, seed: int, cfg: dict[str, Any] | None = None, session_id: str | None = None,
                 actor: str = "local_sim_scripted_not_hosted_model"):
        self.cfg = merged_cfg(cfg)
        self.profile = self.cfg["profile"]
        self.seed = seed
        self.fx = fixture(seed, self.cfg)
        self.actor = actor
        self.session_id = session_id or f"local-{seed}"
        self.body_revision = "planar-v1"
        self.episode = 0
        self.tick = 0
        self.p = [0.0, 0.0]
        self.v = [0.0, 0.0]
        self.sequence = 0
        self.gtick = 0                      # gateway tick: executed transitions across episodes
        self.observation_id = "o0"
        self.stopped = False
        self.cache: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.samples: list[dict[str, Any]] = [self.sample()]

    # -- environment -------------------------------------------------------------------
    def sample(self) -> dict[str, Any]:
        noise = self.fx["unit_noise"][self.episode][self.tick]
        obs = self.cfg["observations"]
        if self.profile["noise"]:
            p = [self.p[j] + noise[j] * obs["position_noise_scale"] for j in range(2)]
            v = [self.v[j] + noise[j + 2] * obs["velocity_noise_scale"] for j in range(2)]
        else:
            p, v = self.p[:], self.v[:]
        return {"episode": self.episode, "sample_tick": self.tick, "p": p, "v": v}

    def true_b(self) -> list[list[float]]:
        return body_vectors(self.cfg, self.fx, self.episode, self.profile)

    def goal(self) -> list[float]:
        return list(self.fx["goals"][self.episode])

    def complete(self) -> bool:
        return self.tick >= self.cfg["steps_per_episode"]

    # -- public view -------------------------------------------------------------------
    def packet(self) -> dict[str, Any]:
        delay = self.profile["delay"]
        sensor_tick = max(0, self.tick - delay)
        obs, dyn = self.cfg["observations"], self.cfg["dynamics"]
        return {"schema": "stage.observation.v1", "session_id": self.session_id,
                "body_revision": self.body_revision, "sequence": self.sequence,
                "observation_id": self.observation_id, "dispatch_tick": self.gtick,
                "sensor": copy.deepcopy(self.samples[sensor_tick]), "episode": self.episode,
                "goal": self.goal(),
                "known_dynamics": {"dt": dyn["dt"], "velocity_retention": dyn["alpha"]},
                "sensor_contract": {"position_noise_bound": obs["position_noise_scale"],
                                    "velocity_noise_bound": obs["velocity_noise_scale"],
                                    "delay_ticks": delay, "actuator_mapping": "unknown and may change"},
                "actions": list(ACTIONS), "stopped": self.stopped,
                "episode_complete": self.complete(),
                "recent_events": copy.deepcopy(self.events[-12:]),
                "request_template": {"schema": "stage.action.v1", "request_id": "REPLACE_WITH_UNIQUE_ID",
                                     "session_id": self.session_id, "body_revision": self.body_revision,
                                     "sequence": self.sequence, "observation_id": self.observation_id,
                                     "expires_tick": self.gtick + 2, "action": "coast"}}

    # -- gateway replica ---------------------------------------------------------------
    def admit(self, r: dict[str, Any]) -> dict[str, Any]:
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
            self.stopped = True
        elif self.stopped:
            reason = "stop_latched"
        elif r["sequence"] != self.sequence:
            reason = "sequence_mismatch"
        elif r["observation_id"] != self.observation_id:
            reason = "observation_mismatch"
        elif r["expires_tick"] < self.gtick or r["expires_tick"] > self.gtick + 5:
            reason = "invalid_deadline"
        admitted = reason is None
        receipt = {"request_id": key, "request_sha256": sha, "requested_action": r["action"],
                   "admitted": admitted, "reason": reason, "duplicate": False,
                   "dispatch": admitted and r["action"] != "stop", "stop_latched": self.stopped,
                   "execution_status": "not_dispatched"}
        self.cache[key] = receipt
        return dict(receipt)

    def step(self, raw: bytes) -> dict[str, Any]:
        event: dict[str, Any] = {"actor_label_operator_reported": self.actor, "episode": self.episode,
                                 "source_dispatch_tick": self.gtick}
        try:
            r = parse_request(raw)
            receipt = self.admit(r)
        except (ValueError, UnicodeError) as exc:
            event.update({"event": "rejected_invalid_request", "reason": str(exc), "executed": False})
        else:
            if receipt["dispatch"] and self.complete():
                receipt.update({"admitted": False, "dispatch": False, "reason": "episode_complete"})
                self.cache[receipt["request_id"]] = receipt
            event.update({"event": "action_receipt", "receipt": receipt})
            if receipt["dispatch"]:
                a = ACTIONS.index(receipt["requested_action"])
                b = self.true_b()
                dyn = self.cfg["dynamics"]
                self.v = [dyn["alpha"] * self.v[j] + b[a][j] for j in range(2)]
                self.p = [self.p[j] + dyn["dt"] * self.v[j] for j in range(2)]
                self.tick += 1
                self.samples.append(self.sample())
                cached = self.cache[receipt["request_id"]]
                cached["execution_status"] = EXECUTED
                cached["executed_action"] = receipt["requested_action"]
                self.sequence += 1
                self.gtick += 1
                self.observation_id = f"o{self.gtick}"
                event["receipt"] = dict(cached)
                event["executed_transition_source_tick"] = self.tick - 1
                event["observed_sensor"] = copy.deepcopy(self.samples[max(0, self.tick - self.profile["delay"])])
        self.events.append(event)
        return event

    def next_episode(self) -> dict[str, Any]:
        if self.stopped or self.tick != self.cfg["steps_per_episode"]:
            raise ValueError("Only an unstopped completed episode can advance")
        if self.episode + 1 >= self.cfg["episodes"]:
            raise ValueError("No further episode in this protocol")
        event = {"actor_label_operator_reported": self.actor, "episode": self.episode,
                 "source_dispatch_tick": self.gtick, "event": "operator_episode_reset",
                 "final_sensor_samples": copy.deepcopy(self.samples[-3:]), "operator_intervention": True}
        self.episode += 1
        self.tick, self.p, self.v = 0, [0.0, 0.0], [0.0, 0.0]
        self.samples = [self.sample()]
        self.observation_id = f"o{self.gtick}-episode{self.episode}"
        self.events.append(event)
        return event
