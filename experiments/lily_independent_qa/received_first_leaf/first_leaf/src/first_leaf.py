#!/usr/bin/env python3
"""STAGE FL1-R: inspectable online body-model adaptation, Python standard library.

This is an algorithm experiment, not a hosted-language-model or identity test.
All fixture randomness is generated before execution. The policy sees only a
public packet: delayed noisy samples, actual executed labels and the target.
Evaluator-only truth is retained in the simulator and used for scoring/oracle.
"""
from __future__ import annotations
import argparse
from collections import deque
import copy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def load_protocol() -> dict[str, Any]:
    return json.loads((ROOT / "inputs/protocol.json").read_text())

def fixture(seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    rng = random.Random(seed)
    mapping = list(range(4))
    rng.shuffle(mapping)
    goals = []
    noise = []
    shuffle = []
    for _ in range(cfg["episodes"]):
        theta = rng.uniform(-math.pi, math.pi)
        goals.append([math.cos(theta), math.sin(theta)])
        noise.append([[rng.uniform(-1, 1) for _ in range(4)]
                      for _ in range(cfg["steps_per_episode"] + 1)])
        shuffle.append([rng.randrange(4) for _ in range(cfg["steps_per_episode"])])
    return {"seed": seed, "mapping_A": mapping,
            "mapping_B": [(d + 1) % 4 for d in mapping],
            "goals": goals, "unit_noise": noise, "negative_labels": shuffle}

def write_fixtures(cfg: dict[str, Any], split: str) -> Path:
    spec = cfg[f"{split}_seeds"]
    path = ROOT / f"inputs/{split}_fixtures.jsonl.gz"
    # mtime=0 makes the compressed fixture itself reproducible.
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as out:
        for seed in range(spec["first"], spec["first"] + spec["count"]):
            out.write(canonical(fixture(seed, cfg)) + b"\n")
    return path

def body_vectors(cfg: dict[str, Any], fx: dict[str, Any], ep: int,
                 profile: dict[str, Any]) -> list[list[float]]:
    is_b = cfg["body_schedule"][ep] == "B" and profile["change"]
    mapping = fx["mapping_B"] if is_b else fx["mapping_A"]
    dynamics = cfg["dynamics"]
    gx = dynamics["gain_B_x"] if is_b else dynamics["gain_A"]
    gy = dynamics["gain_B_y"] if is_b else dynamics["gain_A"]
    dirs = [[gx, 0.0], [0.0, gy], [-gx, 0.0], [0.0, -gy]]
    return [dirs[i][:] for i in mapping] + [[0.0, 0.0]]

class MeanModel:
    """Cumulative or finite-window sufficient statistics; no learned weights."""
    def __init__(self, window: int | None = None):
        self.window = window
        self.n = [0] * 4
        self.sums = [[0.0, 0.0] for _ in range(4)]
        self.events: deque[tuple[int, list[float]]] = deque()

    def update(self, a: int, y: list[float]) -> None:
        if not 0 <= a <= 4 or not all(math.isfinite(v) for v in y):
            raise ValueError("Invalid learning observation")
        if a < 4:
            self.n[a] += 1
            for j in range(2):
                self.sums[a][j] += y[j]
        if self.window is not None:
            # Coast samples consume window time but their known zero effect is not fitted.
            self.events.append((a, y[:]))
            if len(self.events) > self.window:
                old_a, old_y = self.events.popleft()
                if old_a < 4:
                    self.n[old_a] -= 1
                    for j in range(2):
                        self.sums[old_a][j] -= old_y[j]
                    if self.n[old_a] == 0:
                        self.sums[old_a] = [0.0, 0.0]

    def vectors(self) -> list[list[float]]:
        return [[v / n for v in s] if n else [0.0, 0.0]
                for s, n in zip(self.sums, self.n)] + [[0.0, 0.0]]

    def state(self) -> dict[str, Any]:
        return {"window": self.window, "n": self.n[:], "sums": copy.deepcopy(self.sums),
                "events": [[a, y[:]] for a, y in self.events]}

    @classmethod
    def restore(cls, state: dict[str, Any]) -> MeanModel:
        obj = cls(state["window"])
        obj.n = state["n"][:]
        obj.sums = copy.deepcopy(state["sums"])
        obj.events = deque((a, y[:]) for a, y in state["events"])
        return obj

class Agent:
    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name, self.cfg = name, cfg
        window = cfg["window_length"] if name in {
            "window", "episode_reset", "misaligned", "shuffled"} else None
        self.model = MeanModel(window)
        self.ep = -1
        self.goal: list[float] = [0.0, 0.0]
        self.history: list[int] = []
        self.last: dict[str, Any] | None = None
        self.oracle_vectors: list[list[float]] | None = None
        self.updates = 0

    def start_episode(self, ep: int, goal: list[float]) -> None:
        self.ep, self.goal = ep, goal[:]
        self.history, self.last = [], None
        if self.name == "episode_reset":
            self.model = MeanModel(self.cfg["window_length"])

    def vectors(self) -> list[list[float]]:
        if self.name == "oracle":
            if self.oracle_vectors is None:
                raise RuntimeError("Oracle requires explicit evaluator-supplied body parameters")
            return self.oracle_vectors
        return self.model.vectors()

    def receive(self, obs: dict[str, Any], negative_label: int | None = None) -> None:
        if self.last and obs["tick"] <= self.last["tick"]:
            return  # Repeated already-seen frame; no repeated learning credit.
        if self.last:
            if obs["tick"] != self.last["tick"] + 1:
                raise ValueError("Nonadjacent samples require a different transition estimator")
            src = self.last["tick"]
            actual = self.history[src]
            label = self.history[-1] if self.name == "misaligned" else actual
            if self.name == "shuffled":
                if negative_label is None:
                    raise ValueError("The negative control needs its pre-generated unrelated label")
                label = negative_label
            alpha = self.cfg["dynamics"]["alpha"]
            y = [obs["v"][j] - alpha * self.last["v"][j] for j in range(2)]
            if self.name not in {"oracle", "no_information"} and not (
                    self.name == "frozen" and self.ep > 0):
                self.model.update(label, y)
                self.updates += 1
        self.last = copy.deepcopy(obs)

    def estimate_current(self, tick: int) -> tuple[list[float], list[float]]:
        if self.last is None:
            raise RuntimeError("Cannot choose an action without an observation")
        p, v = self.last["p"][:], self.last["v"][:]
        b = self.vectors()
        alpha, dt = self.cfg["dynamics"]["alpha"], self.cfg["dynamics"]["dt"]
        for s in range(self.last["tick"], tick):
            a = self.history[s]
            v = [alpha * v[j] + b[a][j] for j in range(2)]
            p = [p[j] + dt * v[j] for j in range(2)]
        return p, v

    def choose(self, tick: int) -> tuple[int, list[float], list[float]]:
        p, v = self.estimate_current(tick)
        b = self.vectors()
        alpha = self.cfg["dynamics"]["alpha"]
        nsteps = self.cfg["steps_per_episode"]
        global_tick = self.ep * nsteps + tick
        if global_tick < self.cfg["initial_probe_steps"]:
            action = global_tick % 4
        elif tick % self.cfg["periodic_probe_interval"] == 0:
            action = (global_tick // self.cfg["periodic_probe_interval"]) % 4
        else:
            desired = [self.cfg["controller"]["kp"] * (self.goal[j] - p[j]) for j in range(2)]
            norm = math.hypot(*desired)
            speed = self.cfg["controller"]["max_desired_speed"]
            if norm > speed:
                desired = [u * speed / norm for u in desired]
            action = min(range(5), key=lambda a: (
                sum((alpha * v[j] + b[a][j] - desired[j]) ** 2 for j in range(2)), a))
        predicted_v = [alpha * v[j] + b[action][j] for j in range(2)]
        return action, predicted_v, p

    def state(self) -> dict[str, Any]:
        return {"name": self.name, "ep": self.ep, "goal": self.goal[:],
                "history": self.history[:], "last": copy.deepcopy(self.last),
                "model": self.model.state(), "updates": self.updates,
                "oracle_vectors": copy.deepcopy(self.oracle_vectors)}

    @classmethod
    def restore(cls, state: dict[str, Any], cfg: dict[str, Any]) -> Agent:
        obj = cls(state["name"], cfg)
        obj.ep, obj.goal = state["ep"], state["goal"][:]
        obj.history, obj.last = state["history"][:], copy.deepcopy(state["last"])
        obj.model, obj.updates = MeanModel.restore(state["model"]), state["updates"]
        obj.oracle_vectors = copy.deepcopy(state["oracle_vectors"])
        return obj

class Episode:
    """Environment, delivery clock and agent. Truth never enters choose/receive."""
    def __init__(self, cfg: dict[str, Any], fx: dict[str, Any], profile_name: str,
                 ep: int, agent: Agent):
        self.cfg, self.fx, self.profile_name, self.ep = cfg, fx, profile_name, ep
        self.profile = cfg["profiles"][profile_name]
        self.agent = agent
        self.agent.start_episode(ep, fx["goals"][ep])
        self.true_b = body_vectors(cfg, fx, ep, self.profile)
        if agent.name == "oracle":
            agent.oracle_vectors = copy.deepcopy(self.true_b)
        self.p, self.v = [0.0, 0.0], [0.0, 0.0]
        self.tick = 0
        self.samples = [self.make_sample(0)]
        self.records: list[dict[str, Any]] = []

    def make_sample(self, tick: int) -> dict[str, Any]:
        n = self.fx["unit_noise"][self.ep][tick]
        cfg = self.cfg["observations"]
        scale = 1.0 if self.profile["noise"] else 0.0
        return {"tick": tick, "p": [self.p[j] + scale * cfg["position_noise_scale"] * n[j] for j in range(2)],
                "v": [self.v[j] + scale * cfg["velocity_noise_scale"] * n[j + 2] for j in range(2)]}

    def step(self) -> dict[str, Any]:
        if self.tick >= self.cfg["steps_per_episode"]:
            raise RuntimeError("Episode already complete")
        t = self.tick
        delivered = max(0, t - self.profile["delay"])
        source_transition = delivered - 1
        neg = self.fx["negative_labels"][self.ep][source_transition] if source_transition >= 0 else None
        obs = self.samples[delivered]
        self.agent.receive(obs, neg)
        b = copy.deepcopy(self.agent.vectors())
        a, pred_v, est_p = self.agent.choose(t)
        alpha, dt = self.cfg["dynamics"]["alpha"], self.cfg["dynamics"]["dt"]
        self.v = [alpha * self.v[j] + self.true_b[a][j] for j in range(2)]
        self.p = [self.p[j] + dt * self.v[j] for j in range(2)]
        self.agent.history.append(a)  # Execution receipt, not the prediction.
        self.tick += 1
        self.samples.append(self.make_sample(self.tick))
        distance = math.dist(self.p, self.fx["goals"][self.ep])
        model_error = sum(math.dist(b[i], self.true_b[i]) for i in range(4)) / 4
        record = {"ep": self.ep, "tick": t, "requested": a, "executed": a,
                  "sample_tick": delivered, "observation": obs,
                  "true_p": self.p[:], "true_v": self.v[:],
                  "estimated_p": est_p, "predicted_v": pred_v, "estimated_b": b,
                  "distance": distance, "velocity_mse": sum((pred_v[j] - self.v[j]) ** 2 for j in range(2)) / 2,
                  "body_model_error": model_error}
        self.records.append(record)
        return record

    def finish(self) -> None:
        # Environment transitions have stopped. Drain pending sensor packets before reset.
        last = self.agent.last["tick"] if self.agent.last else -1
        for s in range(last + 1, len(self.samples)):
            neg = self.fx["negative_labels"][self.ep][s - 1] if s else None
            self.agent.receive(self.samples[s], neg)

    def checkpoint(self) -> dict[str, Any]:
        return {"schema": "stage.fl1.checkpoint.v1", "protocol_digest": digest(self.cfg),
                "fixture_digest": digest(self.fx), "profile_name": self.profile_name,
                "ep": self.ep, "p": self.p[:], "v": self.v[:], "tick": self.tick,
                "samples": copy.deepcopy(self.samples), "agent": self.agent.state()}

    @classmethod
    def restore(cls, state: dict[str, Any], cfg: dict[str, Any], fx: dict[str, Any],
                records_only: bool = False) -> Episode:
        if state["protocol_digest"] != digest(cfg) or state["fixture_digest"] != digest(fx):
            raise ValueError("Checkpoint context mismatch")
        obj = cls.__new__(cls)
        obj.cfg, obj.fx = cfg, fx
        obj.profile_name, obj.ep = state["profile_name"], state["ep"]
        obj.profile = cfg["profiles"][obj.profile_name]
        obj.true_b = body_vectors(cfg, fx, obj.ep, obj.profile)
        obj.p, obj.v, obj.tick = state["p"][:], state["v"][:], state["tick"]
        obj.samples = copy.deepcopy(state["samples"])
        obj.agent = Agent.restore(state["agent"], cfg)
        if records_only:
            obj.agent.model = MeanModel(obj.agent.model.window)
            obj.agent.updates = 0
        obj.records = []
        return obj

def episode_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    if not n:
        raise ValueError("No executed records")
    stable, recovery = 0, None
    for r in records:
        stable = stable + 1 if r["body_model_error"] <= 0.08 else 0
        if stable >= 8 and recovery is None:
            recovery = r["tick"] + 1
    return {"mean_distance": sum(r["distance"] for r in records) / n,
            "early32_distance": sum(r["distance"] for r in records[:32]) / min(32, n),
            "velocity_mse": sum(r["velocity_mse"] for r in records) / n,
            "body_model_error": sum(r["body_model_error"] for r in records) / n,
            "final_distance": records[-1]["distance"],
            "final_within_0_15": int(records[-1]["distance"] <= 0.15),
            "recovery_tick": recovery, "executed_steps": n}

def run_trial(cfg: dict[str, Any], fx: dict[str, Any], profile: str, algorithm: str,
              trace_out: Any = None) -> tuple[list[dict[str, Any]], str]:
    agent = Agent(algorithm, cfg)
    allhash = hashlib.sha256()
    rows = []
    for ep in range(cfg["episodes"]):
        session = Episode(cfg, fx, profile, ep, agent)
        for _ in range(cfg["steps_per_episode"]):
            record = session.step()
            encoded = canonical(record) + b"\n"
            allhash.update(encoded)
            if trace_out:
                trace_out.write(encoded)
        session.finish()
        rows.append({"seed": fx["seed"], "profile": profile, "algorithm": algorithm,
                     "episode": ep, **episode_metrics(session.records),
                     "end_model_sha256": digest(agent.model.state())})
    return rows, allhash.hexdigest()

def run_batch(cfg: dict[str, Any], split: str, profile: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = cfg[f"{split}_seeds"]
    path = ROOT / f"inputs/{split}_fixtures.jsonl.gz"
    if not path.exists():
        raise FileNotFoundError("Freeze fixtures first: python src/first_leaf.py freeze-inputs")
    summary_path = out_dir / f"{split}_{profile}_episodes.csv"
    runs_path = out_dir / f"{split}_{profile}_runs.jsonl"
    failures, starts, completed = [], 0, 0
    with gzip.open(path, "rt") as inp, open(summary_path, "w", newline="") as summary, open(runs_path, "wb") as runs:
        writer = None
        for line in inp:
            fx = json.loads(line)
            for algorithm in cfg["algorithms"]:
                starts += 1
                trace = None
                try:
                    if fx["seed"] == spec["first"]:
                        trace_path = out_dir / f"{split}_{profile}_{algorithm}_witness.jsonl.gz"
                        trace = gzip.open(trace_path, "wb")
                    rows, sha = run_trial(cfg, fx, profile, algorithm, trace)
                    if writer is None:
                        writer = csv.DictWriter(summary, fieldnames=list(rows[0]))
                        writer.writeheader()
                    writer.writerows(rows)
                    runs.write(canonical({"seed": fx["seed"], "profile": profile, "algorithm": algorithm,
                        "status": "completed", "episodes": len(rows), "trace_sha256": sha}) + b"\n")
                    completed += 1
                except Exception as exc:
                    fault = {"seed": fx["seed"], "profile": profile, "algorithm": algorithm,
                             "status": "technical_failure", "error_type": type(exc).__name__, "error": str(exc)}
                    failures.append(fault)
                    runs.write(canonical(fault) + b"\n")
                finally:
                    if trace:
                        trace.close()
            if (fx["seed"] - spec["first"] + 1) % 32 == 0:
                print(f"{split}/{profile}: {fx['seed'] - spec['first'] + 1} seeds", flush=True)
    status = {"split": split, "profile": profile, "scheduled_runs": spec["count"] * len(cfg["algorithms"]),
              "started": starts, "completed": completed, "failures": failures,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "protocol_sha256": hashlib.sha256((ROOT / "inputs/protocol.json").read_bytes()).hexdigest(),
              "fixture_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "python": sys.version}
    (out_dir / f"{split}_{profile}_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    if failures or starts != status["scheduled_runs"]:
        raise RuntimeError("Incomplete batch; inspect status and all-starts ledger")

def replay_check(cfg: dict[str, Any], fx: dict[str, Any]) -> dict[str, Any]:
    donor = Agent("window", cfg)
    replay = Agent("window", cfg)
    comparisons = 0
    for ep in range(cfg["episodes"]):
        session = Episode(cfg, fx, "primary", ep, donor)
        replay.start_episode(ep, fx["goals"][ep])
        for _ in range(cfg["steps_per_episode"]):
            r = session.step()
            replay.receive(r["observation"])
            if canonical(replay.model.state()) != canonical(donor.model.state()):
                raise AssertionError("Aligned donor/replay learner states differ")
            comparisons += 1
            replay.history.append(r["executed"])
        session.finish()
        last = replay.last["tick"] if replay.last else -1
        for s in range(last + 1, len(session.samples)):
            replay.receive(session.samples[s])
        assert canonical(replay.model.state()) == canonical(donor.model.state())
        comparisons += 1
    return {"seed": fx["seed"], "comparisons": comparisons, "identical": True}

def checkpoint_check(cfg: dict[str, Any], fx: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    agent = Agent("window", cfg)
    for ep in range(4):
        session = Episode(cfg, fx, "primary", ep, agent)
        for _ in range(cfg["steps_per_episode"]):
            session.step()
        session.finish()
    session = Episode(cfg, fx, "primary", 4, agent)
    for _ in range(31):
        session.step()
    state = json.loads(canonical(session.checkpoint()))
    restored = Episode.restore(state, cfg, fx)
    reset = Episode.restore(state, cfg, fx, records_only=True)
    reference, reconstructed, reset_records = [], [], []
    while session.tick < cfg["steps_per_episode"]:
        reference.append(session.step())
        reconstructed.append(restored.step())
        reset_records.append(reset.step())
    exact = canonical(reference) == canonical(reconstructed)
    if not exact:
        raise AssertionError("Full JSON restore is not an exact continuation")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "checkpoint.json").write_bytes(canonical(state) + b"\n")
        (out_dir / "checkpoint_fixture.json").write_bytes(canonical(fx) + b"\n")
        (out_dir / "reference_continuation.jsonl").write_bytes(b"".join(canonical(r) + b"\n" for r in reference))
    return {"seed": fx["seed"], "full_state_exact": exact, "continuation_steps": len(reference),
            "full_state_mean_distance": sum(r["distance"] for r in reference) / len(reference),
            "records_only_mean_distance": sum(r["distance"] for r in reset_records) / len(reset_records),
            "records_only_action_disagreements": sum(a["executed"] != b["executed"] for a, b in zip(reference, reset_records)),
            "reference_sha256": hashlib.sha256(b"".join(canonical(r) + b"\n" for r in reference)).hexdigest()}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("freeze-inputs")
    batch = subs.add_parser("run")
    batch.add_argument("--split", choices=["development", "evaluation"], required=True)
    batch.add_argument("--profile", choices=["primary", "no_delay", "clean", "stationary"], required=True)
    batch.add_argument("--out", type=Path, default=ROOT / "results")
    one = subs.add_parser("trial")
    one.add_argument("--seed", type=int, required=True)
    one.add_argument("--algorithm", required=True)
    one.add_argument("--profile", default="primary")
    one.add_argument("--trace", type=Path, required=True)
    resume = subs.add_parser("resume")
    resume.add_argument("--checkpoint", type=Path, required=True)
    resume.add_argument("--fixture", type=Path, required=True)
    resume.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cfg = load_protocol()
    if args.command == "freeze-inputs":
        for split in ["development", "evaluation"]:
            p = write_fixtures(cfg, split)
            print(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
    elif args.command == "run":
        run_batch(cfg, args.split, args.profile, args.out)
    elif args.command == "trial":
        if args.algorithm not in cfg["algorithms"]:
            parser.error("Unknown algorithm")
        with gzip.open(args.trace, "wb") as out:
            rows, sha = run_trial(cfg, fixture(args.seed, cfg), args.profile, args.algorithm, out)
        print(json.dumps({"episodes": rows, "trace_sha256": sha}, indent=2))
    else:
        state, fx = json.loads(args.checkpoint.read_text()), json.loads(args.fixture.read_text())
        ep = Episode.restore(state, cfg, fx)
        with open(args.out, "wb") as out:
            while ep.tick < cfg["steps_per_episode"]:
                out.write(canonical(ep.step()) + b"\n")
        print(hashlib.sha256(args.out.read_bytes()).hexdigest())

if __name__ == "__main__":
    main()
