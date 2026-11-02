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
