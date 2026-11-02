# First Leaf oracle baseline — firstleaf-oracle-001 (continuation)

**Status.** Static work only: nothing below was executed; I read no files beyond the verbatim bundle and the appended partial answer. Numbers in §6 are predictions for Red's sandbox, not results. Credit lines are unchanged from the partial answer (simulator/gateway/relay/protocol: Lilitari, MIT, Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held; founding work Andrei with Red; expansion Grok Bot; companion review F2 Coda; Red reports Coda ran the first part of this run — I have not seen that work).

**How this continuation fits.** The earlier instance's `oracle/first_leaf_oracle.py` was cut off inside `EvidenceLog.ingest_packet`, after the line `            self.add_sample(sensor)` and a dangling fragment `        for event`. The block `FILE: oracle/first_leaf_oracle.py.part2.txt` below is the exact remainder of that file. Assemble it mechanically with the splice script (it refuses to run twice):

```text
python oracle/splice_continuation.py oracle/first_leaf_oracle.py oracle/first_leaf_oracle.py.part2.txt
```

(or by hand: delete the dangling `        for event` line and append the part-2 text). No blocking defect was found in the delivered code; it is treated as fixed.

## 3. (c) Code — remaining files

FILE: oracle/splice_continuation.py
```python
#!/usr/bin/env python3
"""One-off build step: append the continuation block to the truncated first_leaf_oracle.py.

Usage: python oracle/splice_continuation.py <base.py> <continuation.txt>
Writes only to <base.py> (caller-supplied).  Refuses to run if the base file no
longer ends with the dangling '        for event' fragment (i.e. already spliced).
"""
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    base, cont = Path(sys.argv[1]), Path(sys.argv[2])
    text = base.read_text(encoding="utf-8")
    marker = "\n        for event"
    idx = text.rfind(marker)
    if idx < 0 or text[idx + 1:].strip() != "for event":
        raise SystemExit("Base file does not end with the truncated 'for event' line; already spliced?")
    base.write_text(text[:idx + 1] + cont.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"spliced {cont} into {base}")


if __name__ == "__main__":
    main()
```

FILE: oracle/first_leaf_oracle.py.part2.txt
```python
        for event in packet.get("recent_events", []) or []:
            if not isinstance(event, dict):
                self.ignored_events += 1
                continue
            kind = event.get("event")
            if kind == "action_receipt":
                receipt = event.get("receipt")
                # Only a verified simulator transition with its source tick commits an action.
                # Rejected, duplicate (no source tick) and non-dispatched receipts commit nothing.
                if (isinstance(receipt, dict)
                        and receipt.get("execution_status") == EXECUTED
                        and receipt.get("executed_action") in ACTION_INDEX
                        and "executed_transition_source_tick" in event
                        and "episode" in event):
                    self.add_action(int(event["episode"]), int(event["executed_transition_source_tick"]),
                                    ACTION_INDEX[receipt["executed_action"]])
                    observed = event.get("observed_sensor")
                    if isinstance(observed, dict):
                        self.add_sample(observed)
                else:
                    self.ignored_events += 1
            elif kind == "operator_episode_reset":
                for item in event.get("final_sensor_samples", []) or []:
                    if isinstance(item, dict):
                        self.add_sample(item)
            else:
                self.ignored_events += 1

    def new_equations(self, alpha: float) -> list[tuple[int, int, int, list[float]]]:
        """Transitions with a committed action and both end samples, not yet converted; chronological.

        y_{e,u} = v~_{u+1} - alpha * v~_u is attributed to the action committed at source tick u
        of episode e (never to the most recent receipt, never across an episode reset).
        """
        out: list[tuple[int, int, int, list[float]]] = []
        for (episode, tick), action in self.actions.items():
            if (episode, tick) in self.learned:
                continue
            first = self.samples.get((episode, tick))
            second = self.samples.get((episode, tick + 1))
            if first is None or second is None:
                continue
            y = [second[1][j] - alpha * first[1][j] for j in range(2)]
            out.append((episode, tick, action, y))
        out.sort(key=lambda item: (item[0], item[1]))
        for episode, tick, _, _ in out:
            self.learned.add((episode, tick))
        return out

    def committed_unlearned(self, episode: int) -> list[int]:
        """Per-action counts of committed transitions of `episode` whose evidence has not arrived yet."""
        counts = [0] * len(PLANNABLE)
        for (ep, tick), action in self.actions.items():
            if ep == episode and (ep, tick) not in self.learned:
                counts[action] += 1
        return counts

    def episode_tick(self, episode: int) -> int:
        """Number of committed transitions seen for `episode` (largest source tick + 1)."""
        ticks = [tick for (ep, tick) in self.actions if ep == episode]
        return max(ticks) + 1 if ticks else 0

    def latest_sample_tick(self, episode: int, limit: int) -> int | None:
        ticks = [tick for (ep, tick) in self.samples if ep == episode and tick <= limit]
        return max(ticks) if ticks else None

    def summary(self) -> dict[str, Any]:
        return {"samples": len(self.samples), "receipts": len(self.actions), "equations": len(self.learned),
                "duplicate_samples": self.duplicate_samples, "duplicate_receipts": self.duplicate_receipts,
                "conflicting_receipts": self.conflicting_receipts, "ignored_events": self.ignored_events}


def kp_action(p: list[float], v: list[float], goal: list[float], vectors: list[list[float]],
              allowed: list[int], alpha: float, kp: float, max_speed: float) -> int:
    """first_leaf.py's proportional-velocity base policy restricted to `allowed` actions (ties: lowest index)."""
    desired = [kp * (goal[0] - p[0]), kp * (goal[1] - p[1])]
    norm = math.hypot(desired[0], desired[1])
    if norm > max_speed:
        desired = [desired[0] * max_speed / norm, desired[1] * max_speed / norm]
    best_key, best_action = None, allowed[0]
    for a in allowed:
        cost = ((alpha * v[0] + vectors[a][0] - desired[0]) ** 2
                + (alpha * v[1] + vectors[a][1] - desired[1]) ** 2)
        key = (cost, a)
        if best_key is None or key < best_key:
            best_key, best_action = key, a
    return best_action


def rollout_costs(p: list[float], v: list[float], goal: list[float], vectors: list[list[float]],
                  allowed: list[int], alpha: float, dt: float, horizon: int, tail: int,
                  kp: float, max_speed: float) -> dict[int, float]:
    """Best summed distance over `horizon` exhaustive steps plus a `tail` under kp_action, per first action."""
    best: dict[int, float] = {}
    stack: list[tuple[int, list[float], list[float], float, int | None]] = [(0, p, v, 0.0, None)]
    while stack:
        depth, pp, vv, acc, first = stack.pop()
        if depth == horizon:
            total = acc
            for _ in range(tail):
                a = kp_action(pp, vv, goal, vectors, allowed, alpha, kp, max_speed)
                pp, vv = step_state(pp, vv, vectors[a], alpha, dt)
                total += math.dist(pp, goal)
            key = first if first is not None else allowed[0]
            if key not in best or total < best[key]:
                best[key] = total
            continue
        for a in allowed:
            p2, v2 = step_state(pp, vv, vectors[a], alpha, dt)
            stack.append((depth + 1, p2, v2, acc + math.dist(p2, goal), a if first is None else first))
    return best


def validate_request(request: Any, packet: dict[str, Any]) -> None:
    """Protocol check used by tests/harness: exactly the template keys, fresh id, permitted action."""
    template = packet["request_template"]
    if not isinstance(request, dict) or set(request) != set(template):
        raise ValueError("Request keys must equal the packet's request_template keys")
    for key, value in template.items():
        if key not in ("request_id", "action") and request[key] != value:
            raise ValueError(f"Request field {key} must be copied from the template")
    rid = request["request_id"]
    if not isinstance(rid, str) or not 1 <= len(rid) <= 128 or rid == template["request_id"]:
        raise ValueError("request_id must be a fresh short identifier")
    if request["action"] not in packet.get("actions", PLANNABLE):
        raise ValueError("Action not permitted by the packet")


class OracleAgent:
    """Public-packet oracle baseline: evidence log -> regime bank -> IG probing / rollout control.

    act(packet) returns exactly one stage.action.v1 object (template fields copied, fresh
    request_id, chosen action) or None when the packet reports a stopped session or a
    complete episode (the operator must then stop or advance).
    """

    def __init__(self, params: dict[str, Any] | None = None, name: str = "public_oracle",
                 id_prefix: str = "orc"):
        self.params = dict(DEFAULT_PARAMS)
        if params:
            unknown = set(params) - set(DEFAULT_PARAMS)
            if unknown:
                raise ValueError(f"Unknown parameters: {sorted(unknown)}")
            self.params.update(params)
        self.name = name
        self.id_prefix = id_prefix
        self.log = EvidenceLog()
        self.bank: RegimeBank | None = None
        self.alpha = 0.75
        self.dt = 0.1
        self.delay = 0
        self.noise_var = 0.0
        self.half_width = 0.0
        self.counter = 0
        self.decisions = 0
        self.probes = 0
        self.missing_receipts = 0
        self.last_prediction: list[float] | None = None
        self.last_estimate: list[float] | None = None
        self.last_decision: dict[str, Any] | None = None

    # -- configuration from the packet's public constants -------------------------------
    def _configure(self, packet: dict[str, Any]) -> None:
        dynamics = packet["known_dynamics"]
        contract = packet["sensor_contract"]
        self.alpha = float(dynamics["velocity_retention"])
        self.dt = float(dynamics["dt"])
        beta_v = float(contract["velocity_noise_bound"])
        self.delay = int(contract.get("delay_ticks", 0))
        # A1: transition noise w = eps_{u+1} - alpha * eps_u of two independent bounded-uniform draws.
        self.noise_var = (1.0 + self.alpha ** 2) * beta_v ** 2 / 3.0
        # Exact contract bound on |w| per coordinate (times an optional slack factor).
        self.half_width = (1.0 + self.alpha) * beta_v * float(self.params["hard_test_slack"])
        self.bank = self._new_bank()

    def _new_bank(self) -> RegimeBank:
        return RegimeBank(self.params, self.noise_var, self.half_width)

    # -- evidence ------------------------------------------------------------------------
    def ingest(self, packet: dict[str, Any]) -> None:
        if not isinstance(packet, dict) or packet.get("schema") != "stage.observation.v1":
            raise ValueError("Expected a stage.observation.v1 packet")
        for key in ("sensor", "episode", "goal", "request_template", "known_dynamics", "sensor_contract"):
            if key not in packet:
                raise ValueError(f"Packet lacks {key}")
        if self.bank is None:
            self._configure(packet)
        if self.params["memory"] == "packet_only":
            # Context-limited condition: rebuild everything from this packet's twelve events.
            self.log = EvidenceLog()
            self.bank = self._new_bank()
        self.log.ingest_packet(packet)
        for episode, tick, action, y in self.log.new_equations(self.alpha):
            self.bank.observe(action, y, (episode, tick))

    def vectors(self) -> list[list[float]]:
        if self.bank is None:
            return [[0.0, 0.0] for _ in PLANNABLE]
        return self.bank.regimes[self.bank.active].vectors()

    def counts(self) -> list[int]:
        if self.bank is None:
            return [0, 0, 0, 0]
        return self.bank.regimes[self.bank.active].counts()

    # -- state ---------------------------------------------------------------------------
    def current_tick(self, packet: dict[str, Any]) -> int:
        """Within-episode dispatch tick: exact from the sample tick once t > delay, else from receipts."""
        episode = int(packet["episode"])
        sample_tick = int(packet["sensor"]["sample_tick"])
        from_sensor = sample_tick + self.delay if sample_tick > 0 else 0
        return max(from_sensor, self.log.episode_tick(episode))

    def estimate_state(self, packet: dict[str, Any], episode: int, tick: int) -> tuple[list[float], list[float]]:
        """Latest sample of this episode propagated through committed actions with posterior means.

        Assumption: actuators without evidence in the active regime contribute their prior mean (0);
        a transition with no receipt (should not happen if every packet was seen) is treated as coast
        and counted in missing_receipts.
        """
        anchor = self.log.latest_sample_tick(episode, tick)
        if anchor is None:
            raise ValueError("No sample for the current episode")
        p0, v0 = self.log.samples[(episode, anchor)]
        p, v = list(p0), list(v0)
        vecs = self.vectors()
        for u in range(anchor, tick):
            a = self.log.actions.get((episode, u))
            if a is None:
                self.missing_receipts += 1
                a = COAST_INDEX
            p, v = step_state(p, v, vecs[a], self.alpha, self.dt)
        return p, v

    # -- decision ------------------------------------------------------------------------
    def act(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        self.ingest(packet)
        if packet.get("stopped") or packet.get("episode_complete"):
            self.last_decision = {"action": None, "reason": "no_open_turn"}
            return None
        episode = int(packet["episode"])
        tick = self.current_tick(packet)
        goal = [float(packet["goal"][0]), float(packet["goal"][1])]
        p, v = self.estimate_state(packet, episode, tick)
        assert self.bank is not None
        regime = self.bank.regimes[self.bank.active]
        n = regime.counts()
        unlearned = self.log.committed_unlearned(episode)
        tried = [n[a] + unlearned[a] for a in range(4)]          # dispatched-but-unobserved counts as tried
        min_evidence = int(self.params["min_evidence"])
        vecs = regime.vectors()
        untried = [a for a in range(4) if tried[a] < min_evidence]
        costs: dict[int, float] | None = None
        if untried:
            # Information-gain greedy: highest expected gain, lowest index on ties (round-robin).
            action = max(untried, key=lambda a: (regime.actions[a].info_gain(), -a))
            reason = "probe"
            self.probes += 1
        else:
            allowed = [a for a in range(4) if n[a] >= min_evidence] + [COAST_INDEX]
            kp = float(self.params["kp"])
            speed = float(self.params["max_desired_speed"])
            if self.params["controller"] == "kp":
                action = kp_action(p, v, goal, vecs, allowed, self.alpha, kp, speed)
            else:
                costs = rollout_costs(p, v, goal, vecs, allowed, self.alpha, self.dt,
                                      max(1, int(self.params["horizon"])), max(0, int(self.params["tail"])),
                                      kp, speed)
                best = min(costs.values())
                band = [a for a in allowed if costs[a] <= best + float(self.params["explore_margin"])]
                action = min(band, key=lambda a: (tried[a] if a < 4 else 10 ** 9, a))
            reason = "control"
        predicted_v = [self.alpha * v[0] + vecs[action][0], self.alpha * v[1] + vecs[action][1]]
        self.last_prediction = predicted_v
        self.last_estimate = p
        self.counter += 1
        self.decisions += 1
        request = dict(packet["request_template"])
        request["request_id"] = f"{self.id_prefix}-{self.counter:06d}"
        request["action"] = PLANNABLE[action]
        self.last_decision = {"episode": episode, "tick": tick, "action": PLANNABLE[action], "reason": reason,
                              "estimated_p": p, "estimated_v": v, "tried": tried, "counts": n,
                              "regime": self.bank.active, "costs": costs}
        return request

    def summary(self) -> dict[str, Any]:
        bank = self.bank
        return {"name": self.name, "decisions": self.decisions, "probes": self.probes,
                "missing_receipts": self.missing_receipts, "evidence": self.log.summary(),
                "regimes": len(bank.regimes) if bank else 0, "active_regime": bank.active if bank else None,
                "switches": [dict(s) for s in bank.switches] if bank else [],
                "contract_violations": bank.contract_violations if bank else 0,
                "counts": self.counts(), "params": dict(self.params)}


class RandomAgent:
    """Random baseline: uniform over the five non-stop actions, no learning (seeded, deterministic)."""

    def __init__(self, seed: int = 0, name: str = "random"):
        self.rng = random.Random(seed)
        self.name = name
        self.counter = 0
        self.last_prediction: list[float] | None = None

    def act(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        if packet.get("stopped") or packet.get("episode_complete"):
            return None
        self.counter += 1
        request = dict(packet["request_template"])
        request["request_id"] = f"rnd-{self.counter:06d}"
        request["action"] = self.rng.choice(PLANNABLE)
        return request

    def vectors(self) -> list[list[float]]:
        return [[0.0, 0.0] for _ in PLANNABLE]

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "decisions": self.counter}


class ConstantAgent:
    """Always the same action (default coast): a do-nothing reference whose distance stays at the start value."""

    def __init__(self, action: str = COAST, name: str | None = None):
        if action not in PLANNABLE:
            raise ValueError("ConstantAgent action must be a non-stop action")
        self.action = action
        self.name = name or f"{action}_only"
        self.counter = 0
        self.last_prediction: list[float] | None = None

    def act(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        if packet.get("stopped") or packet.get("episode_complete"):
            return None
        self.counter += 1
        request = dict(packet["request_template"])
        request["request_id"] = f"cst-{self.counter:06d}"
        request["action"] = self.action
        return request

    def vectors(self) -> list[list[float]]:
        return [[0.0, 0.0] for _ in PLANNABLE]

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "decisions": self.counter}
```

FILE: oracle/fl_local_sim.py
```python
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
```

FILE: oracle/fl_scoring.py
```python
#!/usr/bin/env python3
"""Metrics and scoring protocol for comparing agents against the public-packet oracle and random baselines.

Standard library only.  episode_metrics mirrors first_leaf.episode_metrics (Lilitari, MIT,
Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held) so that
rows from the package's own algorithms and from relay-driven agents are directly comparable.
Inference follows protocol.json: unit = seed, paired across agents, paired nonparametric
percentile bootstrap, 5000 resamples, bootstrap seed 20261015.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Iterable

METRIC_KEYS = ["mean_distance", "early32_distance", "velocity_mse", "body_model_error",
               "final_distance", "final_within_0_15", "recovery_tick", "executed_steps"]
HIGHER_IS_BETTER = {"final_within_0_15"}
ALL_EPISODES = [0, 1, 2, 3, 4, 5]
PHASES: dict[str, dict[str, Any]] = {
    "all": {"episodes": ALL_EPISODES, "metric": "mean_distance"},
    "first_episode": {"episodes": [0], "metric": "mean_distance"},
    "stable": {"episodes": [1, 2], "metric": "mean_distance"},
    "remap_early32": {"episodes": [3], "metric": "early32_distance"},   # protocol.json primary metric
    "remap_full": {"episodes": [3, 4], "metric": "mean_distance"},
    "return_early32": {"episodes": [5], "metric": "early32_distance"},
    "final_within_0_15": {"episodes": ALL_EPISODES, "metric": "final_within_0_15"},
    "body_model_error": {"episodes": ALL_EPISODES, "metric": "body_model_error"},
}
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20261015


def episode_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    if not n:
        raise ValueError("No executed records")
    has_bme = all(r.get("body_model_error") is not None for r in records)
    has_vmse = all(r.get("velocity_mse") is not None for r in records)
    stable, recovery = 0, None
    if has_bme:
        for r in records:
            stable = stable + 1 if r["body_model_error"] <= 0.08 else 0
            if stable >= 8 and recovery is None:
                recovery = r["tick"] + 1
    return {"mean_distance": sum(r["distance"] for r in records) / n,
            "early32_distance": sum(r["distance"] for r in records[:32]) / min(32, n),
            "velocity_mse": sum(r["velocity_mse"] for r in records) / n if has_vmse else None,
            "body_model_error": sum(r["body_model_error"] for r in records) / n if has_bme else None,
            "final_distance": records[-1]["distance"],
            "final_within_0_15": int(records[-1]["distance"] <= 0.15),
            "recovery_tick": recovery, "executed_steps": n}


def per_seed(rows: list[dict[str, Any]], agent: str, metric: str, episodes: Iterable[int]) -> dict[int, float]:
    """Per-seed mean of `metric` over the listed episodes; seeds missing any listed episode are skipped."""
    wanted = list(episodes)
    table: dict[int, dict[int, float]] = {}
    for r in rows:
        if r.get("agent") == agent and r.get("episode") in wanted and r.get(metric) is not None:
            table.setdefault(int(r["seed"]), {})[int(r["episode"])] = float(r[metric])
    return {seed: sum(v[e] for e in wanted) / len(wanted)
            for seed, v in sorted(table.items()) if all(e in v for e in wanted)}


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("empty")
    pos = q * (len(sorted_values) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def bootstrap_mean(values: Iterable[float | None], resamples: int = BOOTSTRAP_RESAMPLES,
                   seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    mean = sum(vals) / n
    if n == 1:
        return {"n": 1, "mean": mean, "lo": mean, "hi": mean}
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(vals, k=n)) / n for _ in range(resamples))
    return {"n": n, "mean": mean, "lo": _percentile(means, 0.025), "hi": _percentile(means, 0.975)}


def paired_contrast(rows, a: str, b: str, metric: str, episodes, resamples=BOOTSTRAP_RESAMPLES,
                    seed=BOOTSTRAP_SEED) -> dict[str, Any]:
    """Paired (same seed) bootstrap of agent a minus agent b."""
    va, vb = per_seed(rows, a, metric, episodes), per_seed(rows, b, metric, episodes)
    common = sorted(set(va) & set(vb))
    out = bootstrap_mean([va[s] - vb[s] for s in common], resamples, seed)
    out.update({"metric": metric, "episodes": list(episodes), "a": a, "b": b, "seeds": common})
    return out


def normalised_scores(rows, candidate: str, oracle: str, random_name: str, metric: str, episodes,
                      resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED) -> dict[str, Any]:
    """Per-seed regret normalisation: 1 = oracle level, 0 = random level, < 0 worse than random."""
    vc = per_seed(rows, candidate, metric, episodes)
    vo = per_seed(rows, oracle, metric, episodes)
    vr = per_seed(rows, random_name, metric, episodes)
    scores, excluded = [], []
    for s in sorted(set(vc) & set(vo) & set(vr)):
        den = vr[s] - vo[s]
        if metric in HIGHER_IS_BETTER:
            den = vo[s] - vr[s]
        if abs(den) < 1e-9:
            excluded.append(s)
            continue
        num = (vr[s] - vc[s]) if metric not in HIGHER_IS_BETTER else (vc[s] - vr[s])
        scores.append(num / den)
    out = bootstrap_mean(scores, resamples, seed)
    out.update({"metric": metric, "episodes": list(episodes), "excluded_seeds_zero_denominator": excluded})
    return out


def report(rows: list[dict[str, Any]], oracle: str = "public_oracle", random_name: str = "random",
           resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    agents = sorted({r["agent"] for r in rows})
    out: dict[str, Any] = {"agents": {}, "contrasts": {}, "normalised": {},
                           "inference": {"unit": "independent seed, paired across agents",
                                         "interval": "paired nonparametric percentile bootstrap, 95%",
                                         "resamples": resamples, "bootstrap_seed": seed}}
    for agent in agents:
        out["agents"][agent] = {phase: bootstrap_mean(per_seed(rows, agent, spec["metric"],
                                                               spec["episodes"]).values(), resamples, seed)
                                for phase, spec in PHASES.items()}
    for agent in agents:
        for ref in (oracle, random_name):
            if ref in agents and agent != ref:
                out["contrasts"][f"{agent} - {ref}"] = {
                    phase: paired_contrast(rows, agent, ref, spec["metric"], spec["episodes"], resamples, seed)
                    for phase, spec in PHASES.items()}
    if oracle in agents and random_name in agents:
        for agent in agents:
            if agent not in (oracle, random_name):
                out["normalised"][agent] = {
                    phase: normalised_scores(rows, agent, oracle, random_name, spec["metric"],
                                             spec["episodes"], resamples, seed)
                    for phase, spec in PHASES.items()}
    return out


def load_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data["rows"] if isinstance(data, dict) else data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True, help="harness output JSON ({'rows': [...]}) or JSONL")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--oracle", default="public_oracle")
    ap.add_argument("--random", default="random")
    args = ap.parse_args()
    rep = report(load_rows(args.rows), args.oracle, args.random)
    args.out.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print(json.dumps({a: {p: v["mean"] for p, v in t.items()} for a, t in rep["agents"].items()}, indent=2))


if __name__ == "__main__":
    main()
```

FILE: oracle/fl_harness.py
```python
#!/usr/bin/env python3
"""Operator harness for the First Leaf public-packet oracle baseline.

Drives the package's relay.py end-to-end in a temporary directory (``subprocess``: the
real operator path, ``python src/relay.py init|step|next-episode``; ``inproc``: the same
relay functions imported without process spawns) or the standard-library test double
(``local``).  The agent receives only the public packet (packet.json contents); truth
for scoring is read operator-side from private_state.json / the simulator and never
passed to the agent.  Optionally runs the package's own in-process algorithms on the
same fixtures (same seeds => paired).  Writes only the caller-supplied --out path plus
the relay session's temporary directory.

The relay/simulator are Lilitari's (MIT, Copyright (c) 2026 Richard Pemberton and
contributors, to the extent of rights held).  This harness is new work for the task.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import fl_local_sim  # noqa: E402
import fl_scoring  # noqa: E402
from first_leaf_oracle import EXECUTED, ConstantAgent, OracleAgent, RandomAgent, canonical  # noqa: E402

STEPS = 80
ACTOR_LABEL = "scripted_public_packet_agent_not_hosted_model"
RESERVED_SEEDS = [(100, 115), (10000, 10255)]   # development/evaluation fixture ranges in protocol.json


def package_root(explicit: Path | None = None) -> Path:
    root = Path(explicit) if explicit else Path(os.environ.get("FL_PACKAGE_ROOT", HERE.parent))
    if not (root / "src" / "relay.py").exists():
        raise FileNotFoundError(f"No src/relay.py under {root}; pass --package-root or set FL_PACKAGE_ROOT")
    return root.resolve()


def import_package(root: Path):
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return importlib.import_module("relay"), importlib.import_module("first_leaf")


class LocalDriver:
    mode = "local"

    def __init__(self, seed: int, cfg: dict[str, Any] | None = None):
        self.sim = fl_local_sim.LocalRelay(seed, cfg)

    def packet(self) -> dict[str, Any]:
        return self.sim.packet()

    def step(self, raw: bytes) -> dict[str, Any]:
        return self.sim.step(raw)

    def next_episode(self) -> dict[str, Any]:
        return self.sim.next_episode()

    def truth(self) -> dict[str, Any]:
        s = self.sim
        return {"episode": s.episode, "tick": s.tick, "p": s.p[:], "v": s.v[:], "goal": s.goal(),
                "true_b": s.true_b()}

    def close(self) -> None:
        pass


class InprocRelayDriver:
    mode = "inproc"

    def __init__(self, seed: int, root: Path):
        self.root = root
        self.relay, self.first_leaf = import_package(root)
        self.tmp = tempfile.TemporaryDirectory(prefix="fl_relay_")
        self.dir = Path(self.tmp.name) / "session"
        self._init(seed)

    def _init(self, seed: int) -> None:
        self.relay.init(self.dir, seed, ACTOR_LABEL)

    def packet(self) -> dict[str, Any]:
        return json.loads((self.dir / "packet.json").read_text())

    def step(self, raw: bytes) -> dict[str, Any]:
        return self.relay.transact(self.dir, raw)

    def next_episode(self) -> dict[str, Any]:
        return self.relay.transact(self.dir, advance=True)

    def truth(self) -> dict[str, Any]:
        # Operator-side only: private_state.json never reaches the agent.
        s = json.loads((self.dir / "private_state.json").read_bytes())
        ep = s["episode"]
        return {"episode": ep, "tick": s["tick"], "p": s["p"], "v": s["v"], "goal": s["fixture"]["goals"][ep],
                "true_b": self.first_leaf.body_vectors(s["cfg"], s["fixture"], ep, s["cfg"]["profiles"]["primary"])}

    def close(self) -> None:
        self.tmp.cleanup()


class SubprocessRelayDriver(InprocRelayDriver):
    mode = "subprocess"

    def _run(self, *args: str) -> dict[str, Any]:
        cmd = [sys.executable, str(self.root / "src" / "relay.py"), *args]
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return json.loads(proc.stdout)

    def _init(self, seed: int) -> None:
        self._run("init", "--directory", str(self.dir), "--seed", str(seed), "--actor-label", ACTOR_LABEL)

    def step(self, raw: bytes) -> dict[str, Any]:
        action = self.dir / "action.json"
        action.write_bytes(raw)
        return self._run("step", "--directory", str(self.dir), "--request", str(action))

    def next_episode(self) -> dict[str, Any]:
        return self._run("next-episode", "--directory", str(self.dir))


def make_driver(mode: str, seed: int, root: Path | None, local_cfg: dict[str, Any] | None = None):
    if mode == "local":
        return LocalDriver(seed, local_cfg)
    if root is None:
        raise ValueError("relay modes need the package root")
    if mode == "inproc":
        return InprocRelayDriver(seed, root)
    if mode == "subprocess":
        return SubprocessRelayDriver(seed, root)
    raise ValueError(f"Unknown mode {mode}")


def make_agent(name: str, seed: int, params: dict[str, Any] | None = None):
    params = dict(params or {})
    if name == "public_oracle":
        return OracleAgent(params)
    if name == "public_oracle_kp":
        return OracleAgent({**params, "controller": "kp"}, name=name)
    if name == "public_oracle_packet_only":
        return OracleAgent({**params, "memory": "packet_only"}, name=name)
    if name == "random":
        return RandomAgent(seed)
    if name == "coast_only":
        return ConstantAgent("coast")
    raise ValueError(f"Unknown agent {name}")


def run_trial(driver, agent, episodes: int, steps_per_episode: int = STEPS,
              max_rejections: int = 3) -> dict[str, Any]:
    """Drive one session; the agent sees packets only.  Scores executed transitions from truth."""
    records: list[dict[str, Any]] = []
    rejections = 0
    for ep in range(episodes):
        executed = 0
        while executed < steps_per_episode:
            packet = driver.packet()
            if packet.get("stopped"):
                raise RuntimeError("Session stopped")
            if packet.get("episode_complete"):
                raise RuntimeError("Episode complete before the expected step count")
            request = agent.act(packet)
            if request is None:
                raise RuntimeError("Agent returned no request on an open turn")
            event = driver.step(canonical(request))
            receipt = event.get("receipt") if isinstance(event, dict) else None
            if not isinstance(receipt, dict) or receipt.get("execution_status") != EXECUTED:
                rejections += 1
                if rejections > max_rejections:
                    raise RuntimeError(f"Too many rejected requests; last event: {event}")
                continue
            truth = driver.truth()
            record = {"episode": truth["episode"], "tick": executed, "executed": receipt["executed_action"],
                      "distance": math.dist(truth["p"], truth["goal"])}
            est = agent.vectors() if hasattr(agent, "vectors") else None
            if est is not None:
                record["body_model_error"] = sum(math.dist(est[i], truth["true_b"][i]) for i in range(4)) / 4
            pred = getattr(agent, "last_prediction", None)
            if pred is not None:
                record["velocity_mse"] = sum((pred[j] - truth["v"][j]) ** 2 for j in range(2)) / 2
            records.append(record)
            executed += 1
        if ep + 1 < episodes:
            driver.next_episode()
    return {"records": records, "rejections": rejections}


def episode_rows(agent_name: str, seed: int, mode: str, result: dict[str, Any],
                 summary: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    by_ep: dict[int, list[dict[str, Any]]] = {}
    for r in result["records"]:
        by_ep.setdefault(int(r["episode"]), []).append(r)
    switches = (summary or {}).get("switches", [])
    rows = []
    for ep in sorted(by_ep):
        rows.append({"agent": agent_name, "seed": seed, "mode": mode, "episode": ep,
                     **fl_scoring.episode_metrics(by_ep[ep]),
                     "regime_switches": sum(1 for s in switches if s["when"][0] == ep),
                     "rejections": result["rejections"]})
    return rows


def run(agent_names: list[str], seeds: list[int], mode: str, root: Path | None, episodes: int,
        params: dict[str, Any] | None = None, local_cfg: dict[str, Any] | None = None,
        steps: int = STEPS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, summaries = [], []
    for seed in seeds:
        for name in agent_names:
            agent = make_agent(name, seed, params)
            driver = make_driver(mode, seed, root, local_cfg)
            try:
                result = run_trial(driver, agent, episodes, steps)
            finally:
                driver.close()
            summary = agent.summary() if hasattr(agent, "summary") else {}
            rows.extend(episode_rows(agent.name, seed, mode, result, summary))
            summaries.append({"agent": agent.name, "seed": seed, "summary": summary})
    return rows, summaries


def run_package_algorithms(root: Path, seeds: list[int], algorithms: list[str]) -> list[dict[str, Any]]:
    """Package's own in-process algorithms on the same fixtures (primary profile). 'oracle' there
    is the true-body controller with the fixed probe schedule and is labelled fl_oracle_truebody."""
    _, first_leaf = import_package(root)
    cfg = first_leaf.load_protocol()
    rows = []
    for seed in seeds:
        fx = first_leaf.fixture(seed, cfg)
        for algo in algorithms:
            trial_rows, _ = first_leaf.run_trial(cfg, fx, "primary", algo)
            label = "fl_oracle_truebody" if algo == "oracle" else f"fl_{algo}"
            for r in trial_rows:
                rows.append({"agent": label, "seed": seed, "mode": "package_inprocess", "episode": r["episode"],
                             **{k: r.get(k) for k in fl_scoring.METRIC_KEYS},
                             "regime_switches": None, "rejections": 0})
    return rows


def reserved(seeds: list[int]) -> list[int]:
    return [s for s in seeds if any(lo <= s <= hi for lo, hi in RESERVED_SEEDS)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="output JSON path (only file written)")
    ap.add_argument("--mode", choices=["local", "inproc", "subprocess"], default="local")
    ap.add_argument("--seed-first", type=int, default=20001)
    ap.add_argument("--seed-count", type=int, default=4)
    ap.add_argument("--agents", nargs="+", default=["public_oracle", "random"])
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--package-root", type=Path, default=None)
    ap.add_argument("--package-algorithms", nargs="*", default=[],
                    help="e.g. oracle cumulative window (run in-process on the same fixtures)")
    ap.add_argument("--params", default="{}", help="JSON overrides for OracleAgent parameters")
    args = ap.parse_args()
    seeds = list(range(args.seed_first, args.seed_first + args.seed_count))
    if reserved(seeds):
        print(f"warning: seeds {reserved(seeds)} lie in the frozen development/evaluation fixture ranges; "
              "model-facing trials must use fresh seeds", file=sys.stderr)
    params = json.loads(args.params)
    root = package_root(args.package_root) if (args.mode != "local" or args.package_algorithms) else None
    rows, summaries = run(args.agents, seeds, args.mode, root, args.episodes, params)
    if args.package_algorithms:
        rows += run_package_algorithms(root, seeds, args.package_algorithms)
    rep = fl_scoring.report(rows)
    payload = {"task": "firstleaf-oracle-001", "mode": args.mode, "seeds": seeds, "episodes": args.episodes,
               "params": params, "python": sys.version, "rows": rows, "agent_summaries": summaries,
               "report": rep}
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({a: {p: v["mean"] for p, v in t.items()} for a, t in rep["agents"].items()}, indent=2))


if __name__ == "__main__":
    main()
```

FILE: tests/test_oracle.py
```python
"""Unit and integration tests for the First Leaf public-packet oracle baseline (task firstleaf-oracle-001).

Place next to the package's tests/; package-dependent tests skip when src/ or inputs/ are absent.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "oracle"))
sys.path.insert(0, str(ROOT / "src"))

import first_leaf_oracle as flo  # noqa: E402
import fl_harness as hz  # noqa: E402
import fl_local_sim as sim  # noqa: E402
import fl_scoring as sc  # noqa: E402

try:
    import first_leaf  # noqa: E402
    import relay  # noqa: E402,F401
    CFG = first_leaf.load_protocol()
    PACKAGE = True
except Exception:  # package or its inputs not present
    PACKAGE = False


def receipt_event(episode, tick, action, observed):
    return {"event": "action_receipt", "episode": episode, "source_dispatch_tick": tick,
            "receipt": {"execution_status": flo.EXECUTED, "executed_action": action,
                        "requested_action": action, "dispatch": True},
            "executed_transition_source_tick": tick, "observed_sensor": observed}


def sample(episode, tick, v, p=(0.0, 0.0)):
    return {"episode": episode, "sample_tick": tick, "p": list(p), "v": list(v)}


class EvidenceTests(unittest.TestCase):
    def test_duplicate_samples_and_receipts_are_single_evidence(self):
        log = flo.EvidenceLog()
        s0, s1 = sample(0, 0, [0.0, 0.0]), sample(0, 1, [0.3, 0.0])
        ev = receipt_event(0, 0, "k2", s0)
        log.ingest_packet({"sensor": s1, "recent_events": [ev, ev]})
        log.ingest_packet({"sensor": s1, "recent_events": [ev]})
        self.assertEqual(len(log.samples), 2)
        self.assertEqual(log.actions, {(0, 0): 2})
        self.assertEqual(log.duplicate_samples, 4)
        eqs = log.new_equations(0.75)
        self.assertEqual(len(eqs), 1)
        e, u, a, y = eqs[0]
        self.assertEqual((e, u, a), (0, 0, 2))
        self.assertAlmostEqual(y[0], 0.3)
        self.assertEqual(log.new_equations(0.75), [])  # no repeated learning credit

    def test_equation_pairs_source_tick_not_latest_receipt(self):
        log = flo.EvidenceLog()
        s0, s1, s2 = sample(0, 0, [0.0, 0.0]), sample(0, 1, [0.3, 0.0]), sample(0, 2, [0.225, 0.3])
        log.ingest_packet({"sensor": s2, "recent_events": [receipt_event(0, 0, "k0", s0),
                                                           receipt_event(0, 1, "k1", s1)]})
        eqs = log.new_equations(0.75)
        self.assertEqual([(e, u, a) for e, u, a, _ in eqs], [(0, 0, 0), (0, 1, 1)])
        self.assertAlmostEqual(eqs[0][3][0], 0.3)      # k0 -> +x
        self.assertAlmostEqual(eqs[1][3][0], 0.0)      # k1 -> +y (0.225 - 0.75*0.3 = 0)
        self.assertAlmostEqual(eqs[1][3][1], 0.3)

    def test_rejected_and_duplicate_receipts_commit_nothing(self):
        log = flo.EvidenceLog()
        dup = {"event": "action_receipt", "episode": 0, "receipt": {"execution_status": flo.EXECUTED,
               "executed_action": "k0", "duplicate": True}}
        rej = {"event": "rejected_invalid_request", "episode": 0, "reason": "x", "executed": False}
        log.ingest_packet({"sensor": sample(0, 0, [0, 0]), "recent_events": [dup, rej]})
        self.assertEqual(log.actions, {})
        self.assertEqual(log.ignored_events, 2)

    def test_episode_reset_samples_complete_previous_episode(self):
        log = flo.EvidenceLog()
        log.ingest_packet({"sensor": sample(0, 78, [0, 0]),
                           "recent_events": [receipt_event(0, 77, "k3", sample(0, 76, [0, 0])),
                                             receipt_event(0, 78, "k3", sample(0, 77, [0, 0])),
                                             receipt_event(0, 79, "k3", sample(0, 78, [0, 0]))]})
        self.assertEqual(len(log.new_equations(0.75)), 1)   # only (0,77) has both samples
        log.ingest_packet({"sensor": sample(1, 0, [0, 0]),
                           "recent_events": [{"event": "operator_episode_reset", "episode": 0,
                                              "final_sensor_samples": [sample(0, 78, [0, 0]),
                                                                       sample(0, 79, [0, -0.3]),
                                                                       sample(0, 80, [0, -0.525])]}]})
        eqs = log.new_equations(0.75)
        self.assertEqual([(e, u) for e, u, _, _ in eqs], [(0, 78), (0, 79)])
        self.assertAlmostEqual(eqs[1][3][1], -0.3)


class DetectionTests(unittest.TestCase):
    def bank(self, **over):
        params = dict(flo.DEFAULT_PARAMS)
        params.update(over)
        return flo.RegimeBank(params, 0.00046875, 0.0525)

    def test_noise_within_contract_is_absorbed(self):
        b = self.bank()
        for i in range(40):
            b.observe(0, [0.3 + 0.05 * (-1) ** i, 0.0], (0, i))
        self.assertEqual(len(b.regimes), 1)
        self.assertEqual(b.switches, [])
        self.assertAlmostEqual(b.regimes[0].actions[0].mean()[0], 0.3, places=3)

    def test_hard_shift_opens_regime_and_return_revisits(self):
        b = self.bank()
        for i in range(10):
            b.observe(0, [0.3, 0.0], (0, i))
        ev = b.observe(0, [0.0, 0.39], (3, 0))
        self.assertEqual((ev["kind"], ev["trigger"], b.active), ("new", "hard", 1))
        for i in range(1, 5):
            b.observe(0, [0.0, 0.39], (3, i))
        ev = b.observe(0, [0.3, 0.0], (5, 0))
        self.assertEqual((ev["kind"], b.active), ("revisit", 0))
        self.assertEqual(b.regimes[0].actions[0].n, 11)
        self.assertEqual(b.regimes[1].actions[0].n, 5)

    def test_soft_detector_catches_sub_contract_shift(self):
        b = self.bank()
        for i in range(20):
            b.observe(0, [0.3, 0.0], (0, i))
        for i in range(4):
            b.observe(0, [0.39, 0.0], (1, i))   # 0.09 shift: inside the 0.105 hard bound
        self.assertEqual(len(b.switches), 1)
        self.assertEqual(b.switches[0]["trigger"], "soft")

    def test_coast_audits_the_contract(self):
        b = self.bank()
        b.observe(4, [0.02, -0.05], (0, 0))
        self.assertEqual(b.contract_violations, 0)
        b.observe(4, [0.1, 0.0], (0, 1))
        self.assertEqual(b.contract_violations, 1)
        self.assertFalse(b.hard_enabled())

    def test_information_gain_prefers_unobserved_actuator(self):
        post = flo.ActionPosterior(0.00046875, 1.0, 4)
        g0 = post.info_gain()
        post.update([0.3, 0.0])
        self.assertGreater(g0, 7.0)
        self.assertLess(post.info_gain(), 1.0)


class AgentProtocolTests(unittest.TestCase):
    def test_one_valid_request_per_packet(self):
        s, agent, ids = sim.LocalRelay(7), flo.OracleAgent(), set()
        for _ in range(20):
            pk = s.packet()
            req = agent.act(pk)
            flo.validate_request(req, pk)
            self.assertNotIn(req["request_id"], ids)
            ids.add(req["request_id"])
            ev = s.step(flo.canonical(req))
            self.assertEqual(ev["receipt"]["execution_status"], flo.EXECUTED)
        self.assertEqual(s.tick, 20)

    def test_probe_order_then_control(self):
        s, agent, actions = sim.LocalRelay(11), flo.OracleAgent(), []
        for _ in range(6):
            req = agent.act(s.packet())
            actions.append(req["action"])
            s.step(flo.canonical(req))
        self.assertEqual(actions[:4], ["k0", "k1", "k2", "k3"])
        self.assertEqual(agent.last_decision["reason"], "control")

    def test_no_request_when_episode_complete_or_stopped(self):
        s, agent = sim.LocalRelay(3), flo.OracleAgent()
        pk = s.packet()
        self.assertIsNone(agent.act({**pk, "episode_complete": True}))
        self.assertIsNone(agent.act({**pk, "stopped": True}))
        self.assertIsNotNone(agent.act(pk))

    def test_random_and_constant_agents_follow_protocol(self):
        s = sim.LocalRelay(5)
        for agent in (flo.RandomAgent(1), flo.ConstantAgent("coast")):
            pk = s.packet()
            req = agent.act(pk)
            flo.validate_request(req, pk)
            self.assertEqual(s.step(flo.canonical(req))["receipt"]["execution_status"], flo.EXECUTED)

    def test_packet_only_memory_still_acts(self):
        s, agent = sim.LocalRelay(9), flo.OracleAgent({"memory": "packet_only"})
        for _ in range(30):
            req = agent.act(s.packet())
            self.assertEqual(s.step(flo.canonical(req))["receipt"]["execution_status"], flo.EXECUTED)


class IdentificationTests(unittest.TestCase):
    def test_clean_stationary_identifies_body(self):
        driver = hz.LocalDriver(21, {"profile": {"noise": False, "change": False}})
        agent = flo.OracleAgent()
        result = hz.run_trial(driver, agent, episodes=1)
        true_b = driver.sim.true_b()
        for i in range(4):
            self.assertLess(abs(agent.vectors()[i][0] - true_b[i][0]), 1e-3)
            self.assertLess(abs(agent.vectors()[i][1] - true_b[i][1]), 1e-3)
        self.assertLess(result["records"][-1]["body_model_error"], 1e-3)
        self.assertEqual(agent.summary()["switches"], [])

    def test_noisy_identification_within_contract(self):
        driver = hz.LocalDriver(22)
        agent = flo.OracleAgent()
        hz.run_trial(driver, agent, episodes=1)
        true_b = driver.sim.true_b()
        for i in range(4):
            self.assertLess(max(abs(agent.vectors()[i][j] - true_b[i][j]) for j in range(2)), 0.03)
        self.assertEqual(agent.summary()["contract_violations"], 0)


class EndToEndLocalTests(unittest.TestCase):
    def test_remap_detected_and_original_body_revisited(self):
        driver, agent = hz.LocalDriver(31), flo.OracleAgent()
        hz.run_trial(driver, agent, episodes=6)
        summary = agent.summary()
        self.assertEqual(summary["contract_violations"], 0)
        self.assertEqual(summary["missing_receipts"], 0)
        switches = summary["switches"]
        self.assertTrue(any(s["when"][0] == 3 and s["when"][1] <= 3 and s["kind"] == "new"
                            and s["trigger"] == "hard" for s in switches))
        self.assertTrue(any(s["when"][0] == 5 and s["when"][1] <= 3 and s["kind"] == "revisit"
                            and s["to"] == 0 for s in switches))
        self.assertFalse(any(s["when"][0] in (0, 1, 2, 4) for s in switches))

    def test_oracle_beats_random_and_coast(self):
        rows, _ = hz.run(["public_oracle", "random", "coast_only"], [1, 2], "local", None, 6)
        rep = sc.report(rows)
        oracle = rep["agents"]["public_oracle"]["all"]["mean"]
        rnd = rep["agents"]["random"]["all"]["mean"]
        self.assertAlmostEqual(rep["agents"]["coast_only"]["all"]["mean"], 1.0, places=9)
        self.assertLess(oracle, rnd - 0.2)
        self.assertLess(oracle, 0.6)
        self.assertGreater(rep["normalised"]["coast_only"]["all"]["mean"], -1.0)


class ScoringTests(unittest.TestCase):
    def test_bootstrap_deterministic_and_centred(self):
        vals = [0.1 * i for i in range(10)]
        a, b = sc.bootstrap_mean(vals, 500), sc.bootstrap_mean(vals, 500)
        self.assertEqual(a, b)
        self.assertLessEqual(a["lo"], a["mean"])
        self.assertLessEqual(a["mean"], a["hi"])
        self.assertEqual(sc.bootstrap_mean([])["n"], 0)

    def test_normalised_score_endpoints(self):
        rows = []
        for seed in range(3):
            for ep in range(6):
                base = {"seed": seed, "episode": ep, "mean_distance": 0.0, "early32_distance": 0.0,
                        "final_within_0_15": 1}
                rows.append({**base, "agent": "public_oracle", "mean_distance": 0.3})
                rows.append({**base, "agent": "random", "mean_distance": 1.0})
                rows.append({**base, "agent": "same_as_oracle", "mean_distance": 0.3})
                rows.append({**base, "agent": "same_as_random", "mean_distance": 1.0})
        rep = sc.report(rows, resamples=100)
        self.assertAlmostEqual(rep["normalised"]["same_as_oracle"]["all"]["mean"], 1.0)
        self.assertAlmostEqual(rep["normalised"]["same_as_random"]["all"]["mean"], 0.0)
        self.assertAlmostEqual(rep["contrasts"]["same_as_oracle - random"]["stable"]["mean"], -0.7)

    @unittest.skipUnless(PACKAGE, "package not importable")
    def test_episode_metrics_match_first_leaf(self):
        records = [{"tick": t, "distance": 1.0 - t / 100, "velocity_mse": 0.001,
                    "body_model_error": 0.2 if t < 20 else 0.05} for t in range(80)]
        self.assertEqual(sc.episode_metrics(records), first_leaf.episode_metrics(records))


@unittest.skipUnless(PACKAGE, "package not importable")
class PackageParityTests(unittest.TestCase):
    def test_fixture_and_body_replica_match_package(self):
        for seed in (103, 20001):
            fx_pkg, fx_loc = first_leaf.fixture(seed, CFG), sim.fixture(seed, sim.DEFAULT_CFG)
            self.assertEqual(first_leaf.canonical(fx_pkg), sim.canonical(fx_loc))
            for ep in range(6):
                self.assertEqual(first_leaf.body_vectors(CFG, fx_pkg, ep, CFG["profiles"]["primary"]),
                                 sim.body_vectors(sim.DEFAULT_CFG, fx_loc, ep, sim.DEFAULT_CFG["profile"]))

    def test_local_sim_matches_relay_inproc(self):
        local = hz.run_trial(hz.LocalDriver(20001), flo.OracleAgent(), episodes=2)
        driver = hz.InprocRelayDriver(20001, ROOT)
        try:
            remote = hz.run_trial(driver, flo.OracleAgent(), episodes=2)
        finally:
            driver.close()
        self.assertEqual(len(local["records"]), 160)
        for a, b in zip(local["records"], remote["records"]):
            self.assertEqual(a["executed"], b["executed"])
            self.assertAlmostEqual(a["distance"], b["distance"], places=12)

    def test_subprocess_relay_smoke(self):
        driver = hz.SubprocessRelayDriver(20002, ROOT)
        try:
            result = hz.run_trial(driver, flo.OracleAgent(), episodes=1, steps_per_episode=5)
            packet = driver.packet()
        finally:
            driver.close()
        self.assertEqual(len(result["records"]), 5)
        self.assertEqual(packet["sequence"], 5)
        self.assertEqual([r["executed"] for r in result["records"]][:4], ["k0", "k1", "k2", "k3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

FILE: docs/ORACLE_BASELINE.md
```markdown
# First Leaf public-packet oracle baseline (task firstleaf-oracle-001)

Private computational research on models only; not a hosted-model evaluation, safety
certification, hardware recommendation or public release.  Simulator, gateway, relay and
protocol are Lilitari's work in The Stage package (MIT, Copyright (c) 2026 Richard
Pemberton and contributors, to the extent of rights held); founding work Andrei with Red,
research expansion Grok Bot, companion review Coda.  The oracle-baseline files
(`oracle/`, this document, `tests/test_oracle.py`) are new work for the task under the same
licence.  Everything here was written statically; results must come from execution.

## Files

| file | role |
|---|---|
| `oracle/first_leaf_oracle.py` | agent: deduplicated evidence log, per-regime Gaussian posteriors, bounded-error + GLR change detection, regime bank, IG probing, rollout controller; `RandomAgent`, `ConstantAgent` |
| `oracle/fl_local_sim.py` | stdlib test double of relay.py's packet/event schema (labelled replica; parity-tested) |
| `oracle/fl_harness.py` | operator harness: relay.py via subprocess or in-process in a temp dir, or the test double; truth read operator-side only |
| `oracle/fl_scoring.py` | metrics (mirrors `first_leaf.episode_metrics`), phases, paired bootstrap, normalised regret, report |
| `tests/test_oracle.py` | unit + integration tests; package-dependent tests skip without `src/` and `inputs/` |

## Running (from the package root)

```text
python oracle/splice_continuation.py oracle/first_leaf_oracle.py oracle/first_leaf_oracle.py.part2.txt
python -m unittest tests.test_oracle -v
python oracle/fl_harness.py --mode local --seed-first 20001 --seed-count 8 --out local_runs.json
python oracle/fl_harness.py --mode inproc --seed-first 20001 --seed-count 8 \
    --agents public_oracle public_oracle_packet_only random coast_only \
    --package-algorithms oracle cumulative window --out relay_runs.json
python oracle/fl_harness.py --mode subprocess --seed-first 20001 --seed-count 1 --out subprocess_run.json
python oracle/fl_scoring.py --rows relay_runs.json --out report.json
```

`inproc` and `subprocess` both execute relay.py's own `init/transact` code; `subprocess`
is the literal operator path (`python src/relay.py step ...`, roughly 480 process spawns per
trial).  The harness reads `private_state.json` only to score; the agent object receives the
packet dict alone.

## Scoring protocol (deliverable d)

**Unit and pairing.** The experimental unit is a seed.  All agents on a seed share the same
fixture (goals, noise draws, mapping), so contrasts are paired.  Model-facing seeds must be
fresh: outside 100–115 and 10000–10255 (the frozen development/evaluation ranges) and unseen
by the candidate in any form.  Default: 20001 onward.

**Episodes and steps.** Six episodes of 80 executed transitions (`body_schedule` A,A,A,B,B,A
under the primary profile).  Only executed transitions are scored; a rejected request does
not advance the simulator.

**Metrics** (per episode, then phase means; lower is better unless noted):
`mean_distance` (the headline task metric: mean true distance to target over the 80 executed
steps), `early32_distance` (first 32 steps), `final_distance`, `final_within_0_15` (higher is
better), `velocity_mse` and `body_model_error` (only for agents exposing a prediction/model;
not comparable across agents that do not), `recovery_tick`.  Phases: `all`, `first_episode`,
`stable` (episodes 1–2), `remap_early32` (episode 3 first 32 steps — the package's primary
metric), `remap_full` (3–4), `return_early32` (episode 5 first 32).

**Inference.** Paired nonparametric percentile bootstrap over seeds, 5000 resamples,
bootstrap seed 20261015 (protocol.json's inference block), 95% intervals; secondary
contrasts are exploratory (no familywise-error claim).  Reported for each candidate:
`candidate − public_oracle` and `candidate − random` per phase, and the normalised score
`(random − candidate) / (random − public_oracle)` per seed (1 = oracle level, 0 = random,
< 0 worse than random; seeds with a zero denominator are listed and excluded).  Expected
half-width ≈ 1.96·sd/√n of the per-seed differences; with sd ≈ 0.1 (prediction) 32 seeds
give ±0.035, 256 give ±0.012.  Choose n before running and record it.

**Fair comparison rules.**
1. Same packets, same brief (`docs/MODEL_BRIEF.md`), same seeds, same episode count.
2. One request per packet.  A rejected request is logged; the operator re-presents the
   *same* packet at most twice more; after three rejections the operator commits `coast` on
   the candidate's behalf and records the intervention (counted in `rejections`).  Duplicate
   IDs with identical content are no-ops; changed content needs a new ID (interface rule).
3. Memory condition declared and matched: a candidate that keeps its own notes is compared
   with `public_oracle` (full evidence); a candidate limited to the current packet is compared
   with `public_oracle_packet_only` (twelve-event rebuild).
4. No access to `private_state.json`, fixtures, source or scores; the operator enforces it.
5. Every attempt is reported (no selection by performance); a technical failure is an
   explicit row, not a silent omission; the run manifest records endpoint, prompts, context
   policy and interventions (README requirements).
6. The package's own `oracle` algorithm is the *true-body* controller with a fixed probe
   schedule; it is labelled `fl_oracle_truebody` and is an upper reference on model
   knowledge, not on control (its periodic probes cost tracking).  `random` and `coast_only`
   are lower references; `coast_only` has `mean_distance` exactly 1.0 by construction.

## What is a claim and what is a heuristic

Exact under the public contract: the bounded-error change test (zero false alarms if the
noise bounds hold; coast equations audit the bounds).  Optimal under stated assumptions:
the conjugate posterior (squared loss, Gaussian approximation A1); IG-greedy ordering of
untried actuators.  Heuristics: the GLR soft test and its threshold, the regime-bank
revisit rule, certainty-equivalent rollout with a kp tail, the near-tie exploration bonus,
treating episode boundaries as non-events.  The Bayes-adaptive optimum is intractable here.

## Limitations

No MA(1)-aware (GLS) estimator; position equations unused; pre-detection equations after a
soft trigger are not rolled back; the oracle is a baseline, not a proof of attainable
performance; nothing here was executed by its author.
```

## 4. (d) Metrics and scoring protocol

The full rule set is in `docs/ORACLE_BASELINE.md` (above) and implemented in `fl_scoring.py`. Summary of the design decisions and why:

- **Unit = seed, paired.** The fixture fixes goals, mapping and every noise draw per (episode, tick), independent of the trajectory, so two agents on one seed face identical disturbances; paired contrasts remove the large between-seed variance from goal direction (axis-aligned goals are much easier than diagonal ones for a 4-actuator body).
- **Headline metric = per-episode `mean_distance`**, because it is literally the objective the brief gives the candidate and what the controller minimises; `early32_distance` of episode 3 is kept because it is the package's preregistered primary metric and isolates adaptation speed. `body_model_error`/`velocity_mse` are reported only within agents that expose a model; a hosted model normally does not, so they do not enter the cross-agent score.
- **Normalised regret** `(random − candidate)/(random − oracle)` makes seeds with different difficulty commensurable and is bootstrapped over seeds (percentile, 5000, seed 20261015 — the package's own inference spec, so a candidate's report reads like the package's `RESULTS`).
- **Three references, not one:** `public_oracle` (what is attainable from the packet alone), `fl_oracle_truebody` (true body, fixed probes — a knowledge upper bound, labelled separately because its periodic probing is a control handicap), `random`/`coast_only` (floor; `coast_only` = 1.0 exactly is a built-in sanity check of the pipeline).
- **Fairness rules** (one request per packet; bounded retries with operator-committed coast after three rejections, logged; declared and matched memory condition via `public_oracle_packet_only`; fresh seeds; all attempts reported) follow the README/MODEL_BRIEF constraints and the protocol's "no exclusions by performance" rule.

## 5. (e) Tests

`tests/test_oracle.py` covers: deduplicated evidence (samples and receipts), source-tick attribution, non-committing events (rejected/duplicate receipts), episode-reset samples completing the previous episode; hard change detection with return revisit, soft detection of a sub-contract shift, coast contract audit, information-gain ordering; protocol conformance (exactly the template keys, fresh unique IDs, permitted actions, `None` on complete/stopped, probe order k0..k3 then control, packet-only memory); identification (clean stationary → body recovered to 1e-3, noisy → within 0.03, zero contract violations); end-to-end local behaviour (switch at episode 3 kind `new`/`hard`, revisit of regime 0 at episode 5, no switches elsewhere; oracle < random − 0.2 and < 0.6 mean distance; coast = 1.0); scoring (deterministic bootstrap, normalised endpoints 1/0, contrast value, `episode_metrics` equality with `first_leaf.episode_metrics`); package parity (fixture/body replica byte-equal to the package; local sim trajectory equal to relay in-process to 1e-12 over two episodes; subprocess relay smoke test of 5 steps).

## 6. Predictions for Red to check (not results)

1. Test suite: all pass; expected wall time ≈ 15–40 s (rollout agent ≈ 1–2 s per 6-episode trial). The two tolerance-based assertions most likely to need adjustment if my desk arithmetic is off: `assertLess(oracle, 0.6)` and the `- 0.2` margin in `test_oracle_beats_random`; the deterministic `to == 0` revisit assertion in `test_remap_detected_and_original_body_revisited`.
2. Primary relay sessions (`--mode inproc`, seeds 20001+): per trial exactly two regime switches — `(3, u≤2)` kind `new` trigger `hard`, `(5, u≤2)` kind `revisit` to regime 0 — `contract_violations` 0, `missing_receipts` 0, `rejections` 0; probes = 4 (episode 0) + ≤3 (episode 3) + 0 (episode 5).
3. Phase means (rough): `public_oracle` stable ≈ 0.30–0.40 (expected ≤ `fl_window`/`fl_cumulative`, which keep probing every 7th tick), remap_early32 ≈ 0.55–0.70 versus `fl_cumulative` ≈ 0.8–0.9 and `fl_window` ≈ 0.7–0.8, return_early32 close to stable level (bank revisit) and below `fl_window`; `random` all ≈ 1.0–1.3; `coast_only` = 1.0 exactly; `public_oracle_packet_only` slightly worse than `public_oracle` in episodes 0 and 3 (ten-equation rebuilds), similar elsewhere.
4. `velocity_mse` for `public_oracle` after episode 0 ≈ 1e-4–4e-4 (sample-noise floor propagated two ticks); `body_model_error` late-episode ≈ 0.005–0.01.
5. Parity test: exact action agreement and distances equal to ≥ 12 places between the local double and relay in-process.

If 2 fails with a soft `trigger` in episodes 0–2, the GLR threshold (23) is too low for the MA(1)-correlated noise; raise `soft_threshold` or `soft_window` and re-run — report the change as a deviation.

## 7. Left unimplemented (explicit)

GLS/MA(1)-aware estimator; fusion of the position equation; rollback of pre-detection equations after a soft trigger; Bayes-adaptive or POMDP-optimal exploration (the IG rule is greedy); the full 256-seed run and any numerical table (execution is Red's); run-manifest tooling for hosted candidates; anything MuJoCo-related.