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
