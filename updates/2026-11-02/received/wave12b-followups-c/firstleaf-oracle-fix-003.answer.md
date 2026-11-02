# firstleaf-oracle-fix-003 — deliverable (static; nothing here was executed by me)

Contributors: oracle module, local double, scoring and harness — Claude (Anthropic) earlier waves, assembled by Red (splice); integrated relay — Lilitari (original), Coda (Codex Lily) and Claude (lifecycle, audit D1–D6), coordinated by Red for Richard (Andrei) Pemberton; execution receipts — Red. This revision (Claude, this request): test fix, harness/scoring changes, new tests, interpretation. Private computational research on models only.

## 1. Failing test vs. deduplication code — the **test is wrong**; code unchanged

Static trace of `EvidenceLog.ingest_packet` on the test's two packets (`ev` carries `observed_sensor = s0`, packet sensor is `s1`):

| presentation | key | result |
|---|---|---|
| packet 1 sensor `s1` | (0,1) | new |
| packet 1 event 1 → `s0` | (0,0) | new (first time (0,0) is ever seen) |
| packet 1 event 2 → `s0` | (0,0) | duplicate 1 |
| packet 2 sensor `s1` | (0,1) | duplicate 2 |
| packet 2 event → `s0` | (0,0) | duplicate 3 |

Five presentations of two distinct keys → 3 duplicates. The test's 4 double-counts the first `s0`. The executed receipt (`3 != 4`) agrees with the trace. The counter semantics are also exactly confirmed by the 8-seed summaries: with 480 agent-visible packets, 12-event windows, 5 reset events (3 samples each, visible in 12 packets apiece), the sample presentations are 480 + (5682 − 60 + 180) = 6282 for 483 distinct keys → **5799** duplicates, and 5622 receipt appearances for 479 distinct receipts → **5143**, both matching the receipt verbatim. The key assertions (2 samples, `{(0,0): 2}`, one equation, no repeated credit) hold; the dedup is correct and "duplicates are single evidence" is what the harness measured.

Minimal fix (contained in the full test file below):

```
-        self.assertEqual(log.duplicate_samples, 4)
+        # Five presentations (s1, s0, s0 | s1, s0) of two distinct keys: three duplicates.
+        self.assertEqual(log.duplicate_samples, 3)
+        self.assertEqual(log.duplicate_receipts, 2)
+        self.assertEqual(log.conflicting_receipts, 0)
```

## 2. What the metrics establish, and the fair comparison protocol

**What the oracle is.** A scripted agent that sees exactly what a candidate sees (packet.json: delayed noisy sample, last 12 events, published dynamics and noise bounds) and never the body schedule or private state. Its numbers are therefore a *demonstrated, achievable public-packet level*, not an information-theoretic optimum, and not the package's true-body `fl_oracle_truebody`.

**Reading the 8-seed run (local; in-process identical — trajectory parity of the test double on these seeds/agents):**
- `all` 0.139 [0.135, 0.143] vs random 1.038 [0.971, 1.096]; coast-only sits at exactly 1.0 (goal on the unit circle, body at origin). Random ≈ coast: "beats random" is a weak bar; report coast as a third anchor.
- `stable` 0.104: body already identified → pure approach-and-hold under the kp tail's 0.8 speed cap (the achievable steady axis speed is 0.3/(1−0.75) = 1.2). This is the controller family's floor, not the task's: candidates *can* score above 1.0 on the normalised scale; never clip it.
- `first_episode` 0.159: cost of identifying from scratch (4 probes + 2-tick delay) ≈ 0.055 × 80 ≈ 4.4 distance·steps. `min_evidence = 1` suffices because the contract bound (0.0525 per coordinate after the α-difference) is tight relative to the gains 0.21–0.39; the yardstick thus assumes the published bound is used.
- `remap_early32` 0.483 [0.442, 0.529] (protocol.json's primary metric) vs random 0.963: the degradation is the mechanism, not a defect — equations for tick 0 need sample tick 1, which arrives at dispatch tick 3, so ticks 0–2 are taken under body A; the hard (set-membership) test then fires at tick 3 (`kind new, trigger hard` in both shown summaries, `when [3,0]`), three probes follow (ticks 3–5), their evidence arrives at 6–8, with partial-actuator control in between. Seed 20001: `recovery_tick` 16 in episode 3 vs 8 in stable episodes; the mechanism predicts 14–16. `remap_full` 0.156 shows episode 4 is back at stable level.
- `return_early32` 0.358: the revisit path (`kind revisit, to 0` at `[5,0]`) re-enables all four actuators from one equation; the remaining cost (~0.13 × 32 vs stable early32 ≈ 0.21–0.24 on seed 20001) is the three blind ticks plus settling.
- `final_within_0_15` 1.0 vs 0.0 and `body_model_error` 0.016 vs 0.300 (random's zero vectors give exactly 0.3 for both bodies) are at their anchors: the normalised score on the success metric is just the candidate's raw success rate; the oracle's residual 0.016 is dominated by the two learning phases (0.029 ep 0, 0.033 ep 3 on seed 20001; stable episodes ≈ 0.004–0.006 ≈ the posterior noise floor 0.0217/√75 per coordinate).
- Gap conditioning: for `mean_distance` the oracle–random gap is ≈ 0.90 with the oracle nearly constant across seeds (SD ≈ 0.006) → the per-seed normalisation is well conditioned. For `remap_early32` the gap is only ≈ 0.48 and random's per-seed SD is ≈ 0.23, so some seeds will have small denominators and per-seed normalised scores become heavy-tailed. Hence the pooled normalisation added below.

**Fair comparison protocol (implemented where it is code):**
1. *Episodes*: the full 6-episode session (A,A,A,B,B,A), 80 executed steps each = 480 steps per seed. The primary metric lives in episode 3 and the return test in episode 5; shorter runs cannot be scored on them. Candidates never receive the schedule.
2. *Seeds*: fresh seeds outside the frozen development/evaluation ranges (the integrated relay's D6 enforces this; harness `--allow-frozen-seed` is for non-model-facing runs only). Identical seeds for candidate, oracle, random and coast (same goals, noise draws, mappings → paired). Baselines must be re-run on the candidate's seeds (cheap: ~18 ms per in-process transaction); the 20001–20008 numbers are not reusable unless those are the seeds. Eight seeds suffice for the deterministic scripted baselines; for a model, whose per-seed variance is unknown, plan ≥ 16–24 (illustrative: detecting a 0.1 normalised difference ≈ 0.09 distance with a per-seed SD of 0.15 at 80 % power needs ≈ 22 paired seeds).
3. *Intervals*: paired per-seed differences (candidate − oracle, candidate − random) with the paired percentile bootstrap, 5000 resamples, seed 20261015 (as implemented); treat the raw contrasts as the inferential result, the normalised scores as descriptive, and prefer `normalised_pooled` for `remap_early32`. Report n, the per-seed table, and the sign count (seeds where the candidate beats random); with n = 8 the percentile CI is a guide only.
4. *Budgets and coverage*: rejections and duplicates do not advance the simulator; set a per-session non-executed budget (`--max-rejections`, 3 for scripted agents, e.g. 48 = 10 % for a model) and record outcomes by status. A `stop` latches the session; `per_seed` then drops that seed from every phase missing an episode — report coverage explicitly (coordinator decision whether a stop should instead be scored as failure).
5. *Channel*: the candidate goes through relay.py only (packet.json + MODEL_BRIEF.md). Its session directory is scored post hoc with `session_rows` (replays executed actions through the deterministic dynamics with the relay's operand order) and merged with baseline rows (`--merge-rows`). `body_model_error`/`velocity_mse` are unavailable post hoc (None → phases skipped) unless an estimate channel is defined.

## 3. Changes needed for the integrated relay (lifecycle API)

What differs and what it requires:

| Integrated relay behaviour | Harness/test change |
|---|---|
| `transact` raises `ExportAfterCommitError` (committed, views stale); CLI exits 3 with `{"committed": true, "export_failed": true, "event": …}` | inproc driver catches it, calls `regenerate_views`, continues with `exc.event`; subprocess driver drops `check=True`, handles exit 3 → runs `export`, returns the event. Never replays. Counts `export_recoveries`. |
| `init(…, allow_frozen_seed=False)` refuses frozen seeds (D6) | `--allow-frozen-seed` plumbed through both drivers; `reserved()` reads the embedded protocol's ranges when the package is importable; hard error in relay modes without the flag |
| packet carries `active_request` (`command_pending`) | `run_trial` refuses to let any agent act and fails loud |
| executed receipt has `dispatch: False` (consumed at `mark_dispatched`); status vocabulary renamed for non-executed states | none needed — oracle and harness key on `execution_status == "verified_simulator_transition"` only; new unit test documents this |
| events gain `request_bytes_sha256/len`, `error_type`, `executed`; new `operator_state_migration` event | none needed — oracle ignores unknown fields/kinds; `check_verified_event` fails loud if `executed_action` / `executed_transition_source_tick` / `observed_sensor` / `episode` ever disappear |
| state schema `stage.relay.private.v2` (same truth keys) | `truth()` checks the schema against `relay.STATE_SCHEMA` when present |
| relay lives in a different tree (`gw3`) | `FL_PACKAGE_ROOT` honoured by tests; `import_package` refuses a cached relay from another root; relay sha256 recorded in output |

Unchanged: `first_leaf_oracle.py` and `fl_local_sim.py` (the measured baseline stays byte-identical).

FILE: oracle/fl_harness.py
```python
#!/usr/bin/env python3
"""Operator harness for the First Leaf public-packet oracle baseline.

Drives the package's relay end-to-end in a temporary directory (``inproc``: relay functions
imported from <package-root>/src; ``subprocess``: the real operator path ``python src/relay.py
init|step|next-episode``) or the standard-library test double (``local``).  The agent receives
only the public packet (packet.json contents); truth for scoring is read operator-side from
private_state.json / the simulator and never passed to the agent.  Finished relay session
directories (e.g. a hosted model's) are scored post hoc with ``session_rows`` on the same row
schema, so they can be merged with the scripted baselines on the same seeds.  Writes only the
caller-supplied --out path plus the relay session's temporary directory.

Integrated relay (gateway lifecycle, GW-ASYNC0) support, task firstleaf-oracle-fix-003:
  * ``ExportAfterCommitError`` (in-process) / CLI exit code 3 (subprocess) mean the step IS
    committed but packet.json/events.jsonl are stale: the driver regenerates the views
    (``regenerate_views`` / ``export``) and continues with the committed event; never replays.
  * a packet carrying ``active_request`` (in-flight receipt restored from an operator edit) stops
    the trial: no agent may act; the operator resolves it with the Gateway API.
  * ``init`` refuses frozen development/evaluation seeds unless ``--allow-frozen-seed`` is passed.
  * the committed receipt of an executed step has ``dispatch`` False (authorization consumed at
    ``mark_dispatched``); harness and oracle key on ``execution_status`` only.
  * the imported relay must come from the requested package root (fail loud otherwise) and the
    relay file's sha256 is recorded in the output.

The relay/simulator/gateway are Lilitari's with lifecycle work by Coda (Codex Lily) and Claude
(Anthropic), MIT, Copyright (c) 2026 Richard Pemberton and contributors, to the extent of rights
held.  This harness is new work for the oracle-baseline tasks (Claude, coordinated by Red).
"""
from __future__ import annotations

import argparse
import hashlib
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
# Fallback only (local mode / package absent); with the package the embedded protocol is read (D5/D6).
RESERVED_SEEDS = [(100, 115), (10000, 10255)]
EXPORT_FAILED_EXIT = 3        # relay.py CLI: step committed, export views stale
VERIFIED_EVENT_KEYS = ("episode", "executed_transition_source_tick", "observed_sensor")


def package_root(explicit: Path | None = None) -> Path:
    root = Path(explicit) if explicit else Path(os.environ.get("FL_PACKAGE_ROOT", HERE.parent))
    if not (root / "src" / "relay.py").exists():
        raise FileNotFoundError(f"No src/relay.py under {root}; pass --package-root or set FL_PACKAGE_ROOT")
    return root.resolve()


def import_package(root: Path):
    """Import relay and first_leaf from root/src; refuse a module cached from another tree."""
    root = Path(root).resolve()
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    relay = importlib.import_module("relay")
    first_leaf = importlib.import_module("first_leaf")
    for mod in (relay, first_leaf):
        where = Path(getattr(mod, "__file__", "") or "").resolve()
        if root not in where.parents:
            raise RuntimeError(f"{mod.__name__} was imported from {where}, not from {root}; another package "
                               "copy is already on sys.path (use a fresh process or a consistent FL_PACKAGE_ROOT)")
    return relay, first_leaf


def relay_provenance(relay_module) -> dict[str, Any]:
    path = Path(relay_module.__file__).resolve()
    return {"relay_file": str(path), "relay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "lifecycle_api": hasattr(relay_module, "ExportAfterCommitError"),
            "state_schema": getattr(relay_module, "STATE_SCHEMA", None)}


class LocalDriver:
    mode = "local"

    def __init__(self, seed: int, cfg: dict[str, Any] | None = None):
        self.sim = fl_local_sim.LocalRelay(seed, cfg)
        self.export_recoveries = 0

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

    def __init__(self, seed: int, root: Path, allow_frozen_seed: bool = False):
        self.root = Path(root).resolve()
        self.relay, self.first_leaf = import_package(self.root)
        self.allow_frozen_seed = allow_frozen_seed
        self.export_recoveries = 0
        self.tmp = tempfile.TemporaryDirectory(prefix="fl_relay_")
        self.dir = Path(self.tmp.name) / "session"
        self._init(seed)

    def _init(self, seed: int) -> None:
        if self.allow_frozen_seed:
            self.relay.init(self.dir, seed, ACTOR_LABEL, True)      # lifecycle relay signature (D6)
        else:
            self.relay.init(self.dir, seed, ACTOR_LABEL)            # works for both relay generations

    def packet(self) -> dict[str, Any]:
        return json.loads((self.dir / "packet.json").read_text())

    def _transact(self, request_bytes: bytes | None = None, advance: bool = False) -> dict[str, Any]:
        export_error = getattr(self.relay, "ExportAfterCommitError", ())   # `except ()` catches nothing
        try:
            if advance:
                return self.relay.transact(self.dir, advance=True)
            return self.relay.transact(self.dir, request_bytes)
        except export_error as exc:
            # Committed, candidate-facing views stale: regenerate them; never replay the step.
            self.export_recoveries += 1
            self.relay.regenerate_views(self.dir)
            return exc.event

    def step(self, raw: bytes) -> dict[str, Any]:
        return self._transact(raw)

    def next_episode(self) -> dict[str, Any]:
        return self._transact(advance=True)

    def truth(self) -> dict[str, Any]:
        # Operator-side only: private_state.json never reaches the agent.
        s = json.loads((self.dir / "private_state.json").read_bytes())
        expected = getattr(self.relay, "STATE_SCHEMA", None)
        if expected is not None and s.get("schema") != expected:
            raise RuntimeError(f"private state schema {s.get('schema')!r} != relay's {expected!r}")
        ep = s["episode"]
        return {"episode": ep, "tick": s["tick"], "p": s["p"], "v": s["v"], "goal": s["fixture"]["goals"][ep],
                "true_b": self.first_leaf.body_vectors(s["cfg"], s["fixture"], ep, s["cfg"]["profiles"]["primary"])}

    def close(self) -> None:
        self.tmp.cleanup()


class SubprocessRelayDriver(InprocRelayDriver):
    mode = "subprocess"

    def _run(self, *args: str, allow_export_failure: bool = True) -> dict[str, Any]:
        cmd = [sys.executable, str(self.root / "src" / "relay.py"), *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        if proc.returncode == EXPORT_FAILED_EXIT and allow_export_failure:
            payload = json.loads(proc.stdout)
            if payload.get("committed") and payload.get("export_failed") and "event" in payload:
                self.export_recoveries += 1
                self._run("export", "--directory", str(self.dir), allow_export_failure=False)
                return payload["event"]
        raise RuntimeError(f"relay.py {args[0]} failed (exit {proc.returncode}): {proc.stderr.strip()}")

    def _init(self, seed: int) -> None:
        args = ["init", "--directory", str(self.dir), "--seed", str(seed), "--actor-label", ACTOR_LABEL]
        if self.allow_frozen_seed:
            args.append("--allow-frozen-seed")
        self._run(*args)

    def step(self, raw: bytes) -> dict[str, Any]:
        action = self.dir / "action.json"
        action.write_bytes(raw)
        return self._run("step", "--directory", str(self.dir), "--request", str(action))

    def next_episode(self) -> dict[str, Any]:
        return self._run("next-episode", "--directory", str(self.dir))


def make_driver(mode: str, seed: int, root: Path | None, local_cfg: dict[str, Any] | None = None,
                allow_frozen_seed: bool = False):
    if mode == "local":
        return LocalDriver(seed, local_cfg)
    if root is None:
        raise ValueError("relay modes need the package root")
    if mode == "inproc":
        return InprocRelayDriver(seed, root, allow_frozen_seed)
    if mode == "subprocess":
        return SubprocessRelayDriver(seed, root, allow_frozen_seed)
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


def check_verified_event(event: dict[str, Any]) -> dict[str, Any]:
    """Fields the harness and the oracle rely on in an executed event; fail loud if the relay's shape changed."""
    receipt = event.get("receipt")
    missing = [k for k in VERIFIED_EVENT_KEYS if k not in event]
    if not isinstance(receipt, dict) or receipt.get("executed_action") not in fl_local_sim.ACTIONS:
        missing.append("receipt.executed_action")
    if missing:
        raise RuntimeError(f"Executed event lacks {missing}; the relay event shape changed: {event}")
    return receipt


def run_trial(driver, agent, episodes: int, steps_per_episode: int = STEPS,
              max_rejections: int = 3) -> dict[str, Any]:
    """Drive one session; the agent sees packets only.  Scores executed transitions from truth."""
    records: list[dict[str, Any]] = []
    rejections = 0
    non_executed: dict[str, int] = {}
    for ep in range(episodes):
        executed = 0
        while executed < steps_per_episode:
            packet = driver.packet()
            if packet.get("stopped"):
                raise RuntimeError("Session stopped")
            if packet.get("active_request"):
                raise RuntimeError("Packet reports an in-flight receipt (command_pending); the operator must "
                                   f"resolve it with the Gateway API before any agent acts: {packet['active_request']}")
            if packet.get("episode_complete"):
                raise RuntimeError("Episode complete before the expected step count")
            request = agent.act(packet)
            if request is None:
                raise RuntimeError("Agent returned no request on an open turn")
            event = driver.step(canonical(request))
            receipt = event.get("receipt") if isinstance(event, dict) else None
            if isinstance(receipt, dict):
                status = str(receipt.get("execution_status"))
            else:
                status = str(event.get("event")) if isinstance(event, dict) else "no_event"
            if status != EXECUTED:
                rejections += 1
                non_executed[status] = non_executed.get(status, 0) + 1
                if rejections > max_rejections:
                    raise RuntimeError(f"Too many non-executed requests ({rejections}); last event: {event}")
                continue
            receipt = check_verified_event(event)
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
    return {"records": records, "rejections": rejections, "non_executed": non_executed,
            "export_recoveries": getattr(driver, "export_recoveries", 0)}


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


def session_rows(directory: Path, agent_name: str, mode: str = "relay_session") -> list[dict[str, Any]]:
    """Operator-side post-hoc scoring of a finished relay session directory (any agent, e.g. a hosted model).

    Replays the executed actions recorded in the committed private state's public_events through the
    deterministic dynamics with the relay's operand order (v = alpha*v + b; p = p + dt*v), so distance
    metrics match the live harness records; body_model_error / velocity_mse are None (no estimate channel).
    Reads private_state.json (operator material; the candidate never sees it).  `rejections` counts every
    request attempt that did not execute (rejections, duplicates, stop acknowledgements, known failures).
    Body vectors come from the fl_local_sim replica (parity with first_leaf.body_vectors is tested).
    """
    state = json.loads((Path(directory) / "private_state.json").read_bytes())
    cfg, fx = state["cfg"], state["fixture"]
    dyn, profile = cfg["dynamics"], cfg["profiles"]["primary"]
    seed = int(fx["seed"])
    by_ep: dict[int, list[dict[str, Any]]] = {}
    rejections = 0
    current_ep: int | None = None
    p = v = [0.0, 0.0]
    for event in state["public_events"]:
        if not isinstance(event, dict):
            continue
        kind = event.get("event")
        if kind == "rejected_invalid_request":
            rejections += 1
            continue
        if kind != "action_receipt":
            continue
        receipt = event.get("receipt") or {}
        if receipt.get("execution_status") != EXECUTED:
            rejections += 1
            continue
        ep = int(event["episode"])
        if ep != current_ep:
            current_ep, p, v = ep, [0.0, 0.0], [0.0, 0.0]
        b = fl_local_sim.body_vectors(cfg, fx, ep, profile)
        a = fl_local_sim.ACTIONS.index(receipt["executed_action"])
        v = [dyn["alpha"] * v[j] + b[a][j] for j in range(2)]
        p = [p[j] + dyn["dt"] * v[j] for j in range(2)]
        recs = by_ep.setdefault(ep, [])
        recs.append({"episode": ep, "tick": len(recs), "executed": receipt["executed_action"],
                     "distance": math.dist(p, fx["goals"][ep])})
    rows = []
    for ep in sorted(by_ep):
        rows.append({"agent": agent_name, "seed": seed, "mode": mode, "episode": ep,
                     **fl_scoring.episode_metrics(by_ep[ep]), "regime_switches": None, "rejections": rejections})
    return rows


def run(agent_names: list[str], seeds: list[int], mode: str, root: Path | None, episodes: int,
        params: dict[str, Any] | None = None, local_cfg: dict[str, Any] | None = None,
        steps: int = STEPS, allow_frozen_seed: bool = False,
        max_rejections: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, summaries = [], []
    for seed in seeds:
        for name in agent_names:
            agent = make_agent(name, seed, params)
            driver = make_driver(mode, seed, root, local_cfg, allow_frozen_seed)
            try:
                result = run_trial(driver, agent, episodes, steps, max_rejections)
            finally:
                driver.close()
            summary = agent.summary() if hasattr(agent, "summary") else {}
            rows.extend(episode_rows(agent.name, seed, mode, result, summary))
            summaries.append({"agent": agent.name, "seed": seed, "summary": summary,
                              "driver": {"mode": driver.mode, "export_recoveries": result["export_recoveries"],
                                         "non_executed": result["non_executed"]}})
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


def reserved(seeds: list[int], cfg: dict[str, Any] | None = None) -> list[int]:
    """Seeds inside the frozen development/evaluation fixture ranges (protocol when given, else fallback)."""
    ranges = list(RESERVED_SEEDS)
    if cfg is not None:
        ranges = []
        for split in ("development", "evaluation"):
            spec = cfg.get(f"{split}_seeds")
            if isinstance(spec, dict) and "first" in spec and "count" in spec:
                ranges.append((int(spec["first"]), int(spec["first"]) + int(spec["count"]) - 1))
    return [s for s in seeds if any(lo <= s <= hi for lo, hi in ranges)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="output JSON path (only file written)")
    ap.add_argument("--mode", choices=["local", "inproc", "subprocess"], default="local")
    ap.add_argument("--seed-first", type=int, default=20001)
    ap.add_argument("--seed-count", type=int, default=4)
    ap.add_argument("--agents", nargs="*", default=["public_oracle", "random"],
                    help="scripted agents to run live (give the flag with no values to skip the live run)")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--package-root", type=Path, default=None)
    ap.add_argument("--package-algorithms", nargs="*", default=[],
                    help="e.g. oracle cumulative window (run in-process on the same fixtures)")
    ap.add_argument("--params", default="{}", help="JSON overrides for OracleAgent parameters")
    ap.add_argument("--allow-frozen-seed", action="store_true",
                    help="relay modes: permit frozen development/evaluation seeds (never model-facing)")
    ap.add_argument("--max-rejections", type=int, default=3, help="non-executed request budget per session")
    ap.add_argument("--score-sessions", nargs="*", type=Path, default=[],
                    help="finished relay session directories (private_state.json) scored post hoc")
    ap.add_argument("--session-agent", default="candidate", help="agent label for --score-sessions rows")
    ap.add_argument("--merge-rows", type=Path, default=None,
                    help="earlier harness output whose rows are merged (e.g. baselines on the same seeds)")
    args = ap.parse_args()
    seeds = list(range(args.seed_first, args.seed_first + args.seed_count))
    root = package_root(args.package_root) if (args.mode != "local" or args.package_algorithms) else None
    provenance: dict[str, Any] = {"mode": args.mode}
    cfg = None
    if root is not None:
        relay, first_leaf = import_package(root)
        provenance.update(relay_provenance(relay))
        cfg = first_leaf.load_protocol()
    frozen = reserved(seeds, cfg) if args.agents else []
    if frozen:
        if args.mode != "local" and not args.allow_frozen_seed:
            ap.error(f"seeds {frozen} lie in the frozen development/evaluation fixture ranges; the relay refuses "
                     "them unless --allow-frozen-seed is passed (non-model-facing runs only)")
        print(f"warning: seeds {frozen} lie in the frozen development/evaluation fixture ranges; "
              "model-facing trials must use fresh seeds", file=sys.stderr)
    params = json.loads(args.params)
    rows, summaries = run(args.agents, seeds, args.mode, root, args.episodes, params,
                          allow_frozen_seed=args.allow_frozen_seed, max_rejections=args.max_rejections)
    if args.package_algorithms:
        rows += run_package_algorithms(root, seeds, args.package_algorithms)
    for directory in args.score_sessions:
        rows += session_rows(directory, args.session_agent)
    if args.merge_rows is not None:
        rows += fl_scoring.load_rows(args.merge_rows)
    rep = fl_scoring.report(rows)
    payload = {"task": "firstleaf-oracle-fix-003", "mode": args.mode, "seeds": seeds, "episodes": args.episodes,
               "params": params, "python": sys.version, "relay": provenance,
               "sessions": [str(d) for d in args.score_sessions],
               "merged_rows_from": str(args.merge_rows) if args.merge_rows else None,
               "rows": rows, "agent_summaries": summaries, "report": rep}
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({a: {p: v["mean"] for p, v in t.items()} for a, t in rep["agents"].items()}, indent=2))


if __name__ == "__main__":
    main()
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

Two regret normalisations are reported (1 = oracle level, 0 = random level, < 0 worse than random,
> 1 better than the oracle; never clipped): `normalised` (per-seed ratios, excludes seeds with a
zero denominator) and `normalised_pooled` (ratio of seed-mean gaps, bootstrapped over seeds), the
latter being the stable choice where the oracle-random gap is small, e.g. remap_early32.
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


def pooled_normalised(rows, candidate: str, oracle: str, random_name: str, metric: str, episodes,
                      resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED) -> dict[str, Any]:
    """Pooled regret normalisation: (mean_random - mean_candidate) / (mean_random - mean_oracle) over the
    common seeds (signs flipped for higher-is-better metrics).  `mean` is the point estimate on all common
    seeds; lo/hi resample seeds jointly for the three agents (paired).  Well defined when single seeds
    have random ~ oracle, which the per-seed version must exclude.  `degenerate_resamples` counts
    resamples whose pooled denominator vanished (dropped from the interval)."""
    vc = per_seed(rows, candidate, metric, episodes)
    vo = per_seed(rows, oracle, metric, episodes)
    vr = per_seed(rows, random_name, metric, episodes)
    common = sorted(set(vc) & set(vo) & set(vr))
    base = {"metric": metric, "episodes": list(episodes), "seeds": common}
    n = len(common)
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "degenerate_resamples": 0, **base}
    sign = -1.0 if metric in HIGHER_IS_BETTER else 1.0

    def score(seeds: list[int]) -> float | None:
        k = len(seeds)
        mc = sum(vc[s] for s in seeds) / k
        mo = sum(vo[s] for s in seeds) / k
        mr = sum(vr[s] for s in seeds) / k
        den = sign * (mr - mo)
        if abs(den) < 1e-9:
            return None
        return sign * (mr - mc) / den

    point = score(common)
    if n == 1 or point is None:
        return {"n": n, "mean": point, "lo": point, "hi": point, "degenerate_resamples": 0, **base}
    rng = random.Random(seed)
    draws, degenerate = [], 0
    for _ in range(resamples):
        value = score(rng.choices(common, k=n))
        if value is None:
            degenerate += 1
        else:
            draws.append(value)
    draws.sort()
    lo = _percentile(draws, 0.025) if draws else None
    hi = _percentile(draws, 0.975) if draws else None
    return {"n": n, "mean": point, "lo": lo, "hi": hi, "degenerate_resamples": degenerate, **base}


def report(rows: list[dict[str, Any]], oracle: str = "public_oracle", random_name: str = "random",
           resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    agents = sorted({r["agent"] for r in rows})
    out: dict[str, Any] = {"agents": {}, "contrasts": {}, "normalised": {}, "normalised_pooled": {},
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
                out["normalised_pooled"][agent] = {
                    phase: pooled_normalised(rows, agent, oracle, random_name, spec["metric"],
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

FILE: tests/test_oracle.py
```python
"""Unit and integration tests for the First Leaf public-packet oracle baseline (tasks firstleaf-oracle-001/-003).

Place next to the package's tests/; package-dependent tests skip when src/ or inputs/ are absent.
Set FL_PACKAGE_ROOT to run the relay-dependent tests against another package tree (e.g. the
integrated lifecycle relay); otherwise the tree containing this tests/ directory is used.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = Path(os.environ.get("FL_PACKAGE_ROOT", str(ROOT))).resolve()
sys.path.insert(0, str(ROOT / "oracle"))
sys.path.insert(0, str(PKG_ROOT / "src"))

import first_leaf_oracle as flo  # noqa: E402
import fl_harness as hz  # noqa: E402
import fl_local_sim as sim  # noqa: E402
import fl_scoring as sc  # noqa: E402

try:
    import first_leaf  # noqa: E402
    import relay  # noqa: E402
    CFG = first_leaf.load_protocol()
    PACKAGE = True
except Exception:  # package or its inputs not present
    PACKAGE = False
LIFECYCLE = PACKAGE and hasattr(relay, "ExportAfterCommitError")


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
        # Five presentations (s1, s0, s0 | s1, s0) of two distinct keys: three duplicates, not four
        # (the first s0 is the first time key (0, 0) is seen).  Receipt ev is presented three times.
        self.assertEqual(log.duplicate_samples, 3)
        self.assertEqual(log.duplicate_receipts, 2)
        self.assertEqual(log.conflicting_receipts, 0)
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

    def test_lifecycle_receipt_with_consumed_dispatch_is_committed(self):
        """Integrated relay: the committed receipt of an executed step has dispatch False (authorization
        consumed at mark_dispatched) and events carry D2 fields; evidence keys on execution_status only."""
        log = flo.EvidenceLog()
        ev = receipt_event(0, 0, "k1", sample(0, 0, [0, 0]))
        ev["receipt"]["dispatch"] = False
        ev.update({"executed": True, "request_bytes_sha256": "00" * 32, "request_bytes_len": 200})
        failure = {"event": "action_receipt", "episode": 0, "executed": False,
                   "receipt": {"execution_status": "known_failure_example", "requested_action": "k2",
                               "dispatch": False}}
        migration = {"event": "operator_state_migration", "episode": 0, "operator_intervention": True}
        log.ingest_packet({"sensor": sample(0, 1, [0, 0.3]), "recent_events": [ev, failure, migration]})
        self.assertEqual(log.actions, {(0, 0): 1})
        self.assertEqual(log.ignored_events, 2)
        self.assertEqual([(e, u, a) for e, u, a, _ in log.new_equations(0.75)], [(0, 0, 1)])

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


class HarnessGuardTests(unittest.TestCase):
    def test_harness_refuses_packet_with_in_flight_receipt(self):
        class Wrapped(hz.LocalDriver):
            def packet(self):
                pk = super().packet()
                pk["active_request"] = {"request_id": "x", "execution_status": "admitted_pending"}
                return pk
        with self.assertRaises(RuntimeError):
            hz.run_trial(Wrapped(1), flo.OracleAgent(), episodes=1, steps_per_episode=1)

    def test_verified_event_shape_is_checked(self):
        ev = receipt_event(0, 0, "k0", sample(0, 0, [0, 0]))
        self.assertIs(hz.check_verified_event(ev), ev["receipt"])
        broken = dict(ev, receipt={"execution_status": flo.EXECUTED})
        with self.assertRaises(RuntimeError):
            hz.check_verified_event(broken)

    def test_reserved_seeds_from_protocol_or_fallback(self):
        cfg = {"development_seeds": {"first": 500, "count": 3}, "evaluation_seeds": {"first": 900, "count": 1}}
        self.assertEqual(hz.reserved([499, 500, 502, 503, 900, 901], cfg), [500, 502, 900])
        self.assertEqual(hz.reserved([99, 100, 115, 116, 10000, 20001]), [100, 115, 10000])


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
        self.assertGreater(rep["normalised_pooled"]["coast_only"]["all"]["mean"], -1.0)


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
        self.assertAlmostEqual(rep["normalised_pooled"]["same_as_oracle"]["all"]["mean"], 1.0)
        self.assertAlmostEqual(rep["normalised_pooled"]["same_as_random"]["all"]["mean"], 0.0)
        self.assertAlmostEqual(rep["contrasts"]["same_as_oracle - random"]["stable"]["mean"], -0.7)

    def test_pooled_normalisation_survives_a_zero_denominator_seed(self):
        rows = []
        for seed in range(3):
            for ep in range(6):
                rnd = 0.3 if seed == 0 else 1.0          # seed 0: random equals the oracle
                rows.append({"seed": seed, "episode": ep, "agent": "public_oracle", "mean_distance": 0.3})
                rows.append({"seed": seed, "episode": ep, "agent": "random", "mean_distance": rnd})
                rows.append({"seed": seed, "episode": ep, "agent": "cand", "mean_distance": 0.65})
        rep = sc.report(rows, resamples=200)
        self.assertEqual(rep["normalised"]["cand"]["all"]["excluded_seeds_zero_denominator"], [0])
        pooled = rep["normalised_pooled"]["cand"]["all"]
        # means: random 2.3/3, oracle 0.3, candidate 0.65 -> (2.3/3 - 0.65) / (2.3/3 - 0.3) = 0.25
        self.assertEqual(pooled["n"], 3)
        self.assertAlmostEqual(pooled["mean"], 0.25)
        self.assertEqual(rep["normalised_pooled"]["cand"]["remap_early32"]["n"], 0)   # metric absent

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
        driver = hz.InprocRelayDriver(20001, PKG_ROOT)
        try:
            remote = hz.run_trial(driver, flo.OracleAgent(), episodes=2)
        finally:
            driver.close()
        self.assertEqual(len(local["records"]), 160)
        self.assertEqual(remote["export_recoveries"], 0)
        for a, b in zip(local["records"], remote["records"]):
            self.assertEqual(a["executed"], b["executed"])
            self.assertAlmostEqual(a["distance"], b["distance"], places=12)

    def test_session_rows_match_live_records(self):
        driver = hz.InprocRelayDriver(20003, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            result = hz.run_trial(driver, agent, episodes=2)
            live = hz.episode_rows("public_oracle", 20003, "inproc", result, agent.summary())
            post = hz.session_rows(driver.dir, "public_oracle")
        finally:
            driver.close()
        self.assertEqual(len(post), 2)
        for a, b in zip(live, post):
            for key in ("episode", "seed", "mean_distance", "early32_distance", "final_distance",
                        "final_within_0_15", "executed_steps", "rejections"):
                self.assertEqual(a[key], b[key], key)
            self.assertIsNone(b["body_model_error"])

    def test_subprocess_relay_smoke(self):
        driver = hz.SubprocessRelayDriver(20002, PKG_ROOT)
        try:
            result = hz.run_trial(driver, flo.OracleAgent(), episodes=1, steps_per_episode=5)
            packet = driver.packet()
        finally:
            driver.close()
        self.assertEqual(len(result["records"]), 5)
        self.assertEqual(packet["sequence"], 5)
        self.assertEqual([r["executed"] for r in result["records"]][:4], ["k0", "k1", "k2", "k3"])

    @unittest.skipUnless(LIFECYCLE, "lifecycle relay (ExportAfterCommitError) not importable")
    def test_export_failure_after_commit_is_recovered_without_replay(self):
        driver = hz.InprocRelayDriver(20004, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            original = driver.relay.export
            calls = {"n": 0}

            def failing_export(s, directory):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError("simulated export failure after commit")
                return original(s, directory)

            driver.relay.export = failing_export
            try:
                event = driver.step(flo.canonical(agent.act(driver.packet())))
            finally:
                driver.relay.export = original
            self.assertEqual(event["receipt"]["execution_status"], flo.EXECUTED)
            self.assertEqual(driver.export_recoveries, 1)
            self.assertEqual(calls["n"], 2)                      # failed once, regenerated once, no replay
            self.assertEqual(driver.packet()["sequence"], 1)
            self.assertEqual(driver.truth()["tick"], 1)
        finally:
            driver.close()

    @unittest.skipUnless(LIFECYCLE, "lifecycle relay not importable")
    def test_lifecycle_receipt_fields_as_seen_by_the_agent(self):
        driver = hz.InprocRelayDriver(20005, PKG_ROOT)
        try:
            agent = flo.OracleAgent()
            driver.step(flo.canonical(agent.act(driver.packet())))
            packet = driver.packet()
            agent.act(packet)
        finally:
            driver.close()
        self.assertIsNone(packet["active_request"])
        last = packet["recent_events"][-1]
        self.assertTrue(last["executed"])
        self.assertFalse(last["receipt"]["dispatch"])             # authorization consumed at mark_dispatched
        self.assertEqual(agent.log.summary()["receipts"], 1)      # ...and the oracle still commits the action
        self.assertEqual(agent.log.summary()["ignored_events"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

## Static predictions for Red to check (not results)

- `tests/test_oracle.py` against the w10 tree (old relay): 24 → 30 tests collected, 2 lifecycle tests skipped; the previously failing test passes (trace above); all others unchanged in behaviour.
- With `FL_PACKAGE_ROOT=<gw3 tree>`: 30 run, 0 skipped. Highest-risk predictions: (a) `test_local_sim_matches_relay_inproc` — I predict bitwise parity (same fixture draw order, same operand order in `candidate_transition`, no packet field the oracle reads changed), hence the 8-seed inproc study through gw3 should reproduce **exactly** the local numbers (`all` 0.13885562111071895, etc.); (b) `test_session_rows_match_live_records` relies on the replica `body_vectors` accepting the package `cfg` (keys `body_schedule`, `dynamics.gain_*`, `profiles.primary.change`) and on `fixture["seed"]` being present (both implied by the passing parity test); (c) the lifecycle `record_execution` receipt must carry `executed_action` — if it does not, `check_verified_event` raises a clear `RuntimeError` rather than letting the oracle silently learn nothing.
- Harness commands: `python oracle/fl_harness.py --mode inproc --package-root <gw3> --seed-first 20001 --seed-count 8 --out run.json`; model session scoring: `--agents --score-sessions <dir…> --session-agent candidate --merge-rows baselines.json`.

## Assumptions (labelled)
- A-REL1: gw3 is a complete tree (`src/first_leaf.py`, `src/interface.py`, `inputs/protocol.json`) and `interface.VERIFIED_SIMULATOR_TRANSITION == "verified_simulator_transition"` (consistent with the integration note's adapted assertions).
- A-REL2: protocol.json exposes `development_seeds` / `evaluation_seeds` as `{first, count}` (as `relay.frozen_seed_ranges` reads them); the literal fallback is used otherwise.
- A-STAT: the seed-count guidance in §2 is a power heuristic under an assumed candidate per-seed SD, not a measured quantity.

## Not implemented (explicit)
- No change to `first_leaf_oracle.py`: optional one-liner (`act` returning None when `packet.get("active_request")`) deferred so the measured baseline stays byte-identical; the harness guard covers it.
- No adapter that drives a hosted model (only post-hoc `session_rows` scoring of its session directory); no estimate channel for `body_model_error`/`velocity_mse` from a model.
- No scoring rule for stopped/incomplete sessions beyond the existing "seed dropped from phases missing an episode" (coordinator decision).
- Unified-diff form of the harness/scoring changes (full files supplied instead; the test fix hunk is shown in §1).