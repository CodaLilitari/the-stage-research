#!/usr/bin/env python3
"""Public-packet oracle baseline agent for First Leaf (STAGE FL1-R, relay protocol).

The Stage task firstleaf-oracle-001.  Python standard library only; deterministic;
performs no I/O.

Credit and licence
------------------
The First Leaf simulator, gateway, relay and protocol (src/first_leaf.py,
src/interface.py, src/relay.py, inputs/protocol.json) are Lilitari's work in The
Stage package, MIT License, Copyright (c) 2026 Richard Pemberton and contributors,
to the extent of rights held (full text in oracle/LICENSE).  The package's
attribution record names founding work by Andrei with Red, research expansion by
Grok Bot and the companion review F2 by Coda; Red reports that Coda ran the first
part of this research run.  This module is new work for the oracle-baseline task
and imports nothing from the package.

Boundary
--------
At run time the agent sees only the public observation packet
(stage.observation.v1 as written by relay.py): known_dynamics, sensor_contract,
one delayed noisy sample keyed by (episode, sample_tick), the last twelve events
(execution receipts and operator episode resets), the goal and the request
template.  It never reads private_state.json, fixtures, the body schedule or
simulator code, and it emits exactly one stage.action.v1 object per turn (or None
when the packet says the episode is complete or the session is stopped, in which
case the operator must act).
"""
from __future__ import annotations

import json
import math
import random
from collections import deque
from typing import Any

ACTUATORS = ("k0", "k1", "k2", "k3")
COAST = "coast"
PLANNABLE = ACTUATORS + (COAST,)            # indices 0..3 actuators, 4 coast
COAST_INDEX = PLANNABLE.index(COAST)
ACTION_INDEX = {name: i for i, name in enumerate(PLANNABLE)}
EXECUTED = "verified_simulator_transition"  # receipt status that commits a transition

DEFAULT_PARAMS: dict[str, Any] = {
    "prior_var": 1.0,          # Gaussian prior variance per coordinate of each actuator effect
    "hard_test": True,         # bounded-error (set-membership) change detector, exact under contract
    "hard_test_slack": 1.0,    # multiplies the contract bound; 1.0 = exact contract
    "soft_test": True,         # windowed GLR mean-shift detector (heuristic)
    "soft_window": 4,
    "soft_threshold": 23.0,    # chi-square(2) upper tail about 1e-5
    "max_regimes": 8,
    "min_evidence": 1,         # equations needed before an actuator may be planned with
    "controller": "rollout",   # "rollout" (lookahead + kp tail) or "kp" (first_leaf-style one step)
    "horizon": 3,              # lookahead depth in executed steps, including the chosen one
    "tail": 6,                 # rollout tail length under the kp base policy
    "kp": 2.0,                 # base-policy gain, same as protocol.json controller.kp
    "max_desired_speed": 0.8,  # same as protocol.json controller.max_desired_speed
    "explore_margin": 0.02,    # near-tie band (summed distance) for the information tie-break
    "memory": "full",          # "full" keeps all packets' evidence; "packet_only" rebuilds per packet
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def step_state(p: list[float], v: list[float], effect: list[float], alpha: float, dt: float):
    v2 = [alpha * v[0] + effect[0], alpha * v[1] + effect[1]]
    p2 = [p[0] + dt * v2[0], p[1] + dt * v2[1]]
    return p2, v2


class ActionPosterior:
    """Conjugate Gaussian posterior for one actuator's 2-D effect plus bounded-error bookkeeping.

    Model (assumption A1): y = theta + w, w ~ N(0, noise_var I) approximating the bounded
    transition noise eps_{t+1} - alpha * eps_t; prior theta ~ N(0, prior_var I).
    """

    def __init__(self, noise_var: float, prior_var: float, window: int):
        self.noise_var = float(noise_var)
        self.prior_var = float(prior_var)
        self.window = int(window)
        self.n = 0
        self.sum = [0.0, 0.0]
        self.lo = [math.inf, math.inf]
        self.hi = [-math.inf, -math.inf]
        self.recent: deque[list[float]] = deque()

    def precision(self) -> float:
        return 1.0 / self.prior_var + self.n / self.noise_var

    def mean(self) -> list[float]:
        prec = self.precision()
        return [self.sum[0] / self.noise_var / prec, self.sum[1] / self.noise_var / prec]

    def var(self) -> float:
        return 1.0 / self.precision()

    def predictive_var(self) -> float:
        return self.var() + self.noise_var

    def info_gain(self) -> float:
        """Expected information gain (nats, both coordinates) of one more equation."""
        return math.log(1.0 + self.var() / self.noise_var)

    def box_consistent(self, y: list[float], half_width: float) -> bool:
        """Exact set-membership test: feasible box stays non-empty after adding y."""
        if self.n == 0:
            return True
        tol = 1e-9
        for j in range(2):
            if max(self.hi[j], y[j]) - min(self.lo[j], y[j]) > 2.0 * half_width + tol:
                return False
        return True

    def shift_statistic(self, y: list[float]) -> float:
        """GLR mean-shift statistic: last (window-1) equations plus y versus the earlier ones."""
        w = self.window
        if w < 2 or self.n < 2 * w - 1:
            return 0.0
        n_rec = len(self.recent) + 1
        n_old = self.n - len(self.recent)
        if n_old < 1:
            return 0.0
        rec_sum = [sum(s[j] for s in self.recent) + y[j] for j in range(2)]
        rec_mean = [rec_sum[j] / n_rec for j in range(2)]
        old_mean = [(self.sum[j] - (rec_sum[j] - y[j])) / n_old for j in range(2)]
        d2 = (rec_mean[0] - old_mean[0]) ** 2 + (rec_mean[1] - old_mean[1]) ** 2
        return d2 / (self.noise_var * (1.0 / n_rec + 1.0 / n_old))

    def mahalanobis2(self, y: list[float]) -> float:
        pv = self.predictive_var()
        m = self.mean()
        return ((y[0] - m[0]) ** 2 + (y[1] - m[1]) ** 2) / pv

    def log_predictive(self, y: list[float]) -> float:
        pv = self.predictive_var()
        return -0.5 * self.mahalanobis2(y) - math.log(2.0 * math.pi * pv)

    def update(self, y: list[float]) -> None:
        self.n += 1
        for j in range(2):
            self.sum[j] += y[j]
            self.lo[j] = min(self.lo[j], y[j])
            self.hi[j] = max(self.hi[j], y[j])
        self.recent.append([float(y[0]), float(y[1])])
        keep = max(0, self.window - 1)
        while len(self.recent) > keep:
            self.recent.popleft()


class Regime:
    """Four actuator posteriors sharing one body hypothesis."""

    def __init__(self, noise_var: float, prior_var: float, window: int, created: tuple[int, int]):
        self.actions = [ActionPosterior(noise_var, prior_var, window) for _ in range(4)]
        self.created = tuple(created)
        self.last_used = tuple(created)

    def vectors(self) -> list[list[float]]:
        return [a.mean() for a in self.actions] + [[0.0, 0.0]]

    def counts(self) -> list[int]:
        return [a.n for a in self.actions]


class RegimeBank:
    """Bank of body regimes with hard (bounded-error) and soft (GLR) change detection.

    Switching rule (heuristic; see docs/ORACLE_BASELINE.md):
      * an equation compatible with the active regime updates it;
      * otherwise, among other regimes that have evidence for the triggering actuator
        and are compatible with the equation, the one with the highest Gaussian
        predictive log-likelihood is revisited;
      * if none exists, a fresh regime is created (least recently used one evicted
        when the bank is full).
    """

    def __init__(self, params: dict[str, Any], noise_var: float, half_width: float):
        self.params = params
        self.noise_var = float(noise_var)
        self.half_width = float(half_width)
        self.regimes: list[Regime] = [self._new_regime((0, 0))]
        self.active = 0
        self.switches: list[dict[str, Any]] = []
        self.contract_violations = 0
        self.observations = 0

    def _new_regime(self, when: tuple[int, int]) -> Regime:
        return Regime(self.noise_var, self.params["prior_var"], self.params["soft_window"], when)

    def hard_enabled(self) -> bool:
        return bool(self.params["hard_test"]) and self.contract_violations == 0

    def compatible(self, post: ActionPosterior, y: list[float]) -> bool:
        if post.n == 0:
            return True
        if self.hard_enabled():
            return post.box_consistent(y, self.half_width)
        return post.mahalanobis2(y) <= self.params["soft_threshold"]

    def observe(self, action: int, y: list[float], when: tuple[int, int]) -> dict[str, Any] | None:
        self.observations += 1
        if action == COAST_INDEX:
            # Known zero effect: audits the sensor contract instead of fitting anything.
            if max(abs(y[0]), abs(y[1])) > self.half_width + 1e-9:
                self.contract_violations += 1
            return None
        regime = self.regimes[self.active]
        post = regime.actions[action]
        hard_ok = self.compatible(post, y)
        soft_stat = post.shift_statistic(y) if self.params["soft_test"] else 0.0
        soft_ok = soft_stat <= self.params["soft_threshold"]
        if hard_ok and soft_ok:
            post.update(y)
            regime.last_used = tuple(when)
            return None
        trigger = "hard" if not hard_ok else "soft"
        candidates = [k for k, r in enumerate(self.regimes)
                      if k != self.active and r.actions[action].n >= 1
                      and self.compatible(r.actions[action], y)]
        if candidates:
            target = max(candidates, key=lambda k: (self.regimes[k].actions[action].log_predictive(y),
                                                    self.regimes[k].last_used, k))
            kind = "revisit"
        else:
            if len(self.regimes) >= int(self.params["max_regimes"]):
                victim = min((k for k in range(len(self.regimes)) if k != self.active),
                             key=lambda k: (self.regimes[k].last_used, k))
                del self.regimes[victim]
                if victim < self.active:
                    self.active -= 1
            self.regimes.append(self._new_regime(tuple(when)))
            target = len(self.regimes) - 1
            kind = "new"
        event = {"when": [int(when[0]), int(when[1])], "action": PLANNABLE[action], "from": self.active,
                 "to": target, "kind": kind, "trigger": trigger, "soft_statistic": soft_stat,
                 "y": [float(y[0]), float(y[1])]}
        self.active = target
        self.regimes[target].actions[action].update(y)
        self.regimes[target].last_used = tuple(when)
        self.switches.append(event)
        return event


class EvidenceLog:
    """Deduplicated public evidence.

    samples: (episode, sample_tick) -> (p, v); actions: (episode, source_tick) -> action
    index from execution receipts only; learned: transitions already turned into equations.
    """

    def __init__(self) -> None:
        self.samples: dict[tuple[int, int], tuple[list[float], list[float]]] = {}
        self.actions: dict[tuple[int, int], int] = {}
        self.learned: set[tuple[int, int]] = set()
        self.duplicate_samples = 0
        self.duplicate_receipts = 0
        self.conflicting_receipts = 0
        self.ignored_events = 0

    def add_sample(self, sample: dict[str, Any]) -> bool:
        key = (int(sample["episode"]), int(sample["sample_tick"]))
        if key in self.samples:
            self.duplicate_samples += 1
            return False
        p = [float(sample["p"][0]), float(sample["p"][1])]
        v = [float(sample["v"][0]), float(sample["v"][1])]
        if not all(math.isfinite(x) for x in p + v):
            raise ValueError("Non-finite sample")
        self.samples[key] = (p, v)
        return True

    def add_action(self, episode: int, tick: int, action: int) -> bool:
        key = (int(episode), int(tick))
        if key in self.actions:
            if self.actions[key] != action:
                self.conflicting_receipts += 1
            else:
                self.duplicate_receipts += 1
            return False
        self.actions[key] = int(action)
        return True

    def ingest_packet(self, packet: dict[str, Any]) -> None:
        sensor = packet.get("sensor")
        if isinstance(sensor, dict):
            self.add_sample(sensor)
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
