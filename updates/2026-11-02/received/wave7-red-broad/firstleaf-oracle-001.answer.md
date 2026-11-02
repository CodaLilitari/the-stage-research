# First Leaf oracle baseline — firstleaf-oracle-001

**Status.** Everything below is static work: I wrote and desk-checked the code but did **not** execute anything, read any file beyond the verbatim bundle, or run first_leaf.py/relay.py. Numerical expectations stated in §6 are predictions for Red to check in the sandbox, not results. This is private computational research on models only.

**Credit (from the sources).** Simulator, gateway, relay and protocol (`first_leaf.py`, `interface.py`, `relay.py`, `protocol.json`): Lilitari, MIT, Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held. Founding work: Andrei with Red; research expansion: Grok Bot; companion review F2: Coda. Red reports that Coda ran the first part of this research run; I have not seen that work and do not characterise it. I could not find the phrase "Claude Fable 5.1" in the bundle, so I credit by the labels the sources actually use. New files below are mine for this task and carry the MIT licence and copyright line.

## 1. (a) The identification problem, from the public packet only

Every quantity here is readable from `packet.json` as `relay.py` writes it.

**Known constants.** Retention α = 0.75, step Δ = 0.1 (`known_dynamics`); noise bounds β_p = 0.01, β_v = 0.03 and delay d = 2 (`sensor_contract`); actions {k0,k1,k2,k3,coast,stop}; goal g_e per episode e (unit circle, but only the value is given).

**Hidden environment, as the agent must model it.** A regime index r (unknown, may change at unknown times: "actuator_mapping: unknown and may change"), effect vectors θ^(r) = (θ_0,…,θ_3) ∈ (ℝ²)⁴, θ_coast ≡ 0. Dynamics within an episode: v_{s+1} = α v_s + θ^(r)_{a_s}, p_{s+1} = p_s + Δ v_{s+1}. Sensor: p̃_s = p_s + η_s, ṽ_s = v_s + ε_s, ‖η_s‖_∞ ≤ β_p, ‖ε_s‖_∞ ≤ β_v.

**What a packet delivers at dispatch tick t of episode e** (t = number of committed transitions so far): one sample keyed (e, s) with s = max(0, t−2); the last 12 events, each either an *execution receipt* (status `verified_simulator_transition`, `episode`, `executed_transition_source_tick` = the tick u whose transition u→u+1 the committed action produced, `observed_sensor` = sample max(0,u−1)) or an `operator_episode_reset` carrying samples 78,79,80 of the previous episode. Receipts, not requests, define a_u. Hence the agent knows samples 0..max(0,t−2) and receipts 0..t−1; the evidence for action a_u becomes available at dispatch tick u+3.

**Evidence equation.** For each committed (e,u,a) with both samples (e,u),(e,u+1) known:

  y_{e,u} := ṽ_{u+1} − α ṽ_u = θ^(r)_a + w_{e,u}, w = ε_{u+1} − α ε_u, so ‖w‖_∞ ≤ β_w := (1+α)β_v = 0.0525.

Each (e,u) yields at most one equation; redelivered samples (same (episode, sample_tick)) add nothing — that is the "repeated samples are not new evidence" rule made precise. Transitions are never formed across episode boundaries (state resets; the reset event marks it). The position equation (p̃_{u+1}−p̃_u)/Δ = v_{u+1} + (η_{u+1}−η_u)/Δ has noise bound 0.2 in velocity units (std ≈ 0.082 under A1 vs 0.017 for ṽ), ≈22× less informative per equation; it is omitted (labelled choice).

**Problem.** Given the evidence set E_t, (i) segment it into regimes and estimate θ for the current regime; (ii) estimate the current state (p_t, v_t) from the latest sample and the committed actions since it; (iii) choose a_t ∈ {k0..k3, coast} to minimise Σ_t ‖p_{t+1} − g_e‖, which is exactly the scored quantity (`mean_distance`). Identifiability: θ_a is identified within a regime iff ≥1 equation with action a exists; with n equations the bounded-error feasible set is a box of per-coordinate width ≤ 2β_w, and the Gaussian-approximation posterior std is σ_w/√n with σ_w² = (1+α²)β_v²/3 = 4.6875·10⁻⁴ under A1. Consecutive equations with the same actuator have MA(1)-correlated noise (Cov = −αβ_v²/3).

## 2. (b) Estimator, change detection, decision rule

**Per-regime, per-actuator conjugate Gaussian posterior.** Prior N(0, τ²I), τ=1; after n equations with sum S: m = S/(n + σ_w²/τ²), s² = σ_w²/(n + σ_w²/τ²). *Claims:* (C1) Bayes-optimal under squared loss for the Gaussian model — standard. (C2) τ→∞ gives OLS = per-action sample mean (what `MeanModel` computes), unbiased for any zero-mean noise; BLUE only if noise were uncorrelated, so with the MA(1) correlation it is consistent but not exactly efficient (GLS omitted). (C3, exact under the contract) Set-membership: F_a = ∩_i [y_i − β_w, y_i + β_w]² always contains θ_a under stationarity, so a new y with per-coordinate range > 2β_w = 0.105 is *impossible* without a change: a zero-false-alarm detector. Detection is immediate for any coordinate shift > 0.105 (every FL1 remap shifts some coordinate by ≥ 0.21 — evaluator-side fact, not used by the agent). Coast equations (θ_coast = 0 known) audit the bound: a violation disables the hard test and falls back to the soft one.

**Soft detector (heuristic).** Windowed GLR on each actuator: recent w=4 equations vs earlier ones, D = ‖m_rec − m_old‖²/(σ_w²(1/n_rec + 1/n_old)) ~ χ²₂ under no change; fire if D > 23 (≈1e−5 nominal tail; bounded noise makes it conservative). Detects shifts ≥≈0.08 with delay ≤ 4; the pre-detection equations are not rolled back (limitation).

**Regime bank (heuristic, context-conditioned memory).** On detection: among other regimes that have evidence for the triggering actuator and are box-compatible with y, revisit the one with highest Gaussian predictive log-likelihood (MAP among compatible bank members); otherwise open a fresh regime. Compatible evidence always updates the active regime (sticky). This implements the README's "bank of models" idea; its correctness rests on the hard test, so a wrong revisit is undone by the next contradicting equation.

**Information gain ⇒ probing rule.** IG of one more equation for actuator a is log(1 + s_a²/σ_w²) nats: ≈7.7 (n=0), 0.69 (1), 0.41 (2). IG-greedy therefore probes untried actuators first, round-robin; actuators dispatched but not yet observed (delay) count as tried. The agent probes until every actuator of the active regime has ≥ `min_evidence`=1 equation, planning meanwhile only with actuators that have evidence (plus coast) — not with prior means.

**Controller: certainty-equivalent rollout.** State anchor = latest sample propagated through committed actions with posterior-mean effects; lookahead H=3 over evidenced actuators + coast, cost Σ‖p−g‖ over H steps plus a K=6-step tail under the base policy (first_leaf's proportional-velocity controller, kp=2, speed 0.8, used verbatim so `controller="kp"` reproduces the package's control law). *Claims:* rollout with an exact model is no worse than its base policy (policy-improvement property); with estimated models and change-points the whole adaptive policy is a heuristic — the Bayes-adaptive optimum (8 continuous unknowns, change-point process, 480-step horizon) is intractable. Near-ties (Δcost ≤ 0.02) break toward the least-sampled actuator (heuristic exploration bonus). Episode boundaries are *not* treated as change points (no public basis); the agent acts greedily under the current regime until contradicted, which also happens to yield the first post-change equation at dispatch tick 3.

## 3. (c) Code

Layout: `oracle/first_leaf_oracle.py` (agent; no package imports), `oracle/fl_local_sim.py` (stdlib test double of relay's packet schema), `oracle/fl_harness.py` (operator harness driving relay.py / first_leaf.py in a temp dir, scoring from operator-side truth), `oracle/fl_scoring.py`, `oracle/LICENSE`, `docs/ORACLE_BASELINE.md`, `tests/test_oracle.py`. Place `oracle/`, `docs/`, `tests/test_oracle.py` inside the package root (next to `src/`), or set `FL_PACKAGE_ROOT`.

FILE: oracle/LICENSE
```text
MIT License

Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights held

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
```

FILE: oracle/first_leaf_oracle.py
```python
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
        for event