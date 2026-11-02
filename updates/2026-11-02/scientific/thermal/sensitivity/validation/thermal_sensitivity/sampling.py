"""Standard-library Morris elementary-effects screening and Saltelli/Jansen Sobol estimators
(thermal-sensitivity-001). Author: Claude (Anthropic); executed by Red.

Conventions: factors live on the unit cube and are mapped linearly onto declared study domains
(uniform measure as a description convention, not a belief distribution). Morris effects are per
unit of normalized factor range. Seeds are derived from strings through SHA-256 so results do not
depend on hash randomization. Evaluation functions receive a dict {factor name: value} and return
a dict {output name: float}.
"""
import hashlib
import math
import random


def derive_seed(*parts):
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng_for(*parts):
    return random.Random(derive_seed(*parts))


def mean(values):
    return math.fsum(values) / len(values) if values else 0.0


def sample_sd(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(math.fsum((v - m) ** 2 for v in values) / (len(values) - 1))


def latin_hypercube(n, k, rng):
    """n points in k dimensions; each column has exactly one point per stratum [i/n, (i+1)/n)."""
    columns = []
    for _ in range(k):
        perm = list(range(n))
        rng.shuffle(perm)
        columns.append([(perm[i] + rng.random()) / n for i in range(n)])
    return [[columns[j][i] for j in range(k)] for i in range(n)]


def design_digest(points):
    text = "\n".join(",".join(repr(float(v)) for v in pt) for pt in points)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scale(point, factors):
    """Map a unit-cube point onto factors = [(name, lo, hi), ...]."""
    return {name: lo + (hi - lo) * u for u, (name, lo, hi) in zip(point, factors)}


def _clamp(v):
    return min(1.0, max(0.0, v))


def morris_delta(p):
    return p / (2.0 * (p - 1))


def morris_trajectories(k, r, p, rng):
    """r trajectories on a p-level grid (p even). Each: {'points': [k+1 points], 'moves': [(i, step)]}."""
    if p < 2 or p % 2:
        raise ValueError("Morris level count p must be even and >= 2")
    delta = morris_delta(p)
    base_levels = [i / (p - 1) for i in range(p // 2)]
    trajectories = []
    for _ in range(r):
        base = [rng.choice(base_levels) for _ in range(k)]
        signs = [rng.choice((1, -1)) for _ in range(k)]
        x = [_clamp(base[i] if signs[i] > 0 else base[i] + delta) for i in range(k)]
        order = list(range(k))
        rng.shuffle(order)
        points, moves = [list(x)], []
        for i in order:
            x = list(x)
            x[i] = _clamp(x[i] + signs[i] * delta)
            points.append(x)
            moves.append((i, signs[i] * delta))
        trajectories.append({"points": points, "moves": moves})
    return trajectories


def morris_points(trajectories):
    return [pt for tr in trajectories for pt in tr["points"]]


def morris_effects(trajectories, values, output_names, k):
    """values: list of output dicts aligned with morris_points(trajectories)."""
    effects = {name: [[] for _ in range(k)] for name in output_names}
    index = 0
    for tr in trajectories:
        n = len(tr["points"])
        vals = values[index:index + n]
        index += n
        for j, (i, step) in enumerate(tr["moves"]):
            for name in output_names:
                effects[name][i].append((vals[j + 1][name] - vals[j][name]) / step)
    result = {}
    for name in output_names:
        result[name] = []
        for i in range(k):
            e = effects[name][i]
            result[name].append({"mu": mean(e), "mu_star": mean([abs(v) for v in e]),
                                 "sigma": sample_sd(e), "count": len(e)})
    return result


def sobol_points(k, n, rng):
    """Saltelli design: A (n), B (n), then AB_i (n each, column i of A replaced by B's)."""
    A = latin_hypercube(n, k, rng)
    B = latin_hypercube(n, k, rng)
    points = [list(x) for x in A] + [list(x) for x in B]
    for i in range(k):
        for row in range(n):
            x = list(A[row])
            x[i] = B[row][i]
            points.append(x)
    return points


def sobol_indices(k, n, values, output_names):
    """S_i (Saltelli 2010) and S_Ti (Jansen 1999) with pooled centring and pooled variance."""
    result = {}
    for name in output_names:
        fA = [values[r][name] for r in range(n)]
        fB = [values[n + r][name] for r in range(n)]
        m = mean(fA + fB)
        fA = [v - m for v in fA]
        fB = [v - m for v in fB]
        V = mean([v * v for v in fA + fB])
        S, ST = [], []
        for i in range(k):
            fAB = [values[(2 + i) * n + r][name] - m for r in range(n)]
            if V <= 0.0:
                S.append(None)
                ST.append(None)
                continue
            S.append(mean([fB[r] * (fAB[r] - fA[r]) for r in range(n)]) / V)
            ST.append(mean([(fA[r] - fAB[r]) ** 2 for r in range(n)]) / (2.0 * V))
        result[name] = {"S": S, "ST": ST, "variance": V, "mean": m}
    return result


def run_morris(factors, evaluate, seed_parts, r, p):
    k = len(factors)
    names = [f[0] for f in factors]
    trajectories = morris_trajectories(k, r, p, rng_for(*seed_parts, "morris"))
    points = morris_points(trajectories)
    values = [evaluate(scale(pt, factors)) for pt in points]
    outputs = sorted(values[0])
    effects = morris_effects(trajectories, values, outputs, k)
    ranking = {}
    for name in outputs:
        order = sorted(range(k), key=lambda i: (-effects[name][i]["mu_star"], i))
        total = math.fsum(effects[name][i]["mu_star"] for i in range(k))
        ranking[name] = [{"factor": names[i], "mu_star": effects[name][i]["mu_star"],
                          "share": (effects[name][i]["mu_star"] / total) if total > 0 else None}
                         for i in order]
    return {"r": r, "p": p, "delta": morris_delta(p), "evaluations": len(points),
            "design_sha256": design_digest(points), "factors": names,
            "effects": {name: dict(zip(names, effects[name])) for name in outputs},
            "ranking_by_mu_star": ranking}


def run_sobol(factors, evaluate, seed_parts, n):
    k = len(factors)
    names = [f[0] for f in factors]
    points = sobol_points(k, n, rng_for(*seed_parts, "sobol"))
    values = [evaluate(scale(pt, factors)) for pt in points]
    outputs = sorted(values[0])
    indices = sobol_indices(k, n, values, outputs)
    sanity = {}
    for name in outputs:
        S, ST = indices[name]["S"], indices[name]["ST"]
        if S[0] is None:
            sanity[name] = {"constant_output": True}
            continue
        sanity[name] = {"min_S": min(S), "sum_S": math.fsum(S),
                        "min_ST_minus_S": min(st - s for s, st in zip(S, ST))}
    return {"N": n, "evaluations": len(points), "design_sha256": design_digest(points),
            "factors": names, "indices": {name: {"S": dict(zip(names, indices[name]["S"])),
                                                 "ST": dict(zip(names, indices[name]["ST"])),
                                                 "variance": indices[name]["variance"],
                                                 "mean": indices[name]["mean"]}
                                          for name in outputs},
            "sanity": sanity}
