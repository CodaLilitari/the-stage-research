"""release_review_additions.py -- adversarial-review additions for the AB-LFR1
release-observability synthetic study (The Stage, task release-observability-003).

Evaluates predeclared predictions N1-N3 and sharpened re-checks S1-S3 against a
fresh run of release_study.run_study().  Standard library only; deterministic;
writes only to a caller-supplied --out path.  Synthetic model-on-model study:
no empirical, biological or hardware claims.

Credit: model formulas Lilitari (AB-LFR1); baseline study and modules Claude
(Anthropic, wave-9 author); cross-check values Muse Code; task text Coda;
execution Red.  Review additions: Claude (Anthropic, reviewer instance), for
Richard (Andrei) Pemberton.  Nothing here was executed by its author.

Usage: python release_review_additions.py [--out additions.json] [--reps 1000] [--max-n 16384]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import release_model as rm
import release_study as rs

N2_SEEDS = (20261111, 20261112, 20261113, 20261114, 20261115)


# ------------------------------------------------------------------ helpers
def mean_exp_on_grid(rate: float, T: float, n: int) -> float:
    """(1/n) * sum_{i=1}^{n} exp(-rate * i*T/n), closed-form geometric sum."""
    if n < 1:
        raise ValueError("n must be >= 1")
    x = rate * T / n
    num = math.exp(-x) * (-math.expm1(-rate * T))
    den = -math.expm1(-x)
    return num / den / n


def relative_finite_data(p: rm.Params, m: rm.Modes, grid: Sequence[float]) -> Tuple[List[float], List[float]]:
    """Finite-k observables in noise-weighted relative units: c/c0 and b/(gamma c0)."""
    xc, xb = [], []
    for t in grid:
        c, b = rm.finite_state(p, t, m)
        xc.append(c / p.c0)
        xb.append(b / (p.gamma * p.c0))
    return xc, xb


def profile_residual_rms(xc: Sequence[float], xb: Sequence[float], grid: Sequence[float],
                         r: float, gamma_known: bool) -> float:
    """RMS (over 2n components) of the best least-squares equilibrium fit at decay rate r.
    gamma_known: one shared amplitude a*(e_r, e_r); else separate amplitudes (a_c e_r, a_b e_r)."""
    er = [math.exp(-r * t) for t in grid]
    see = math.fsum(e * e for e in er)
    if gamma_known:
        a = math.fsum((u + v) * e for u, v, e in zip(xc, xb, er)) / (2.0 * see)
        res2 = math.fsum((u - a * e) ** 2 + (v - a * e) ** 2 for u, v, e in zip(xc, xb, er))
    else:
        ac = math.fsum(u * e for u, e in zip(xc, er)) / see
        ab = math.fsum(v * e for v, e in zip(xb, er)) / see
        res2 = math.fsum((u - ac * e) ** 2 + (v - ab * e) ** 2 for u, v, e in zip(xc, xb, er))
    return math.sqrt(max(res2, 0.0) / (2 * len(grid)))


def profile_minimum(xc: Sequence[float], xb: Sequence[float], grid: Sequence[float], r_centre: float,
                    gamma_known: bool, span: float = 4.0, coarse: int = 25, iters: int = 40) -> Tuple[float, float]:
    """Minimise profile_residual_rms over r in [r_centre/span, r_centre*span]:
    coarse log grid, then golden-section refinement in the bracketing interval.
    Returns (minimum residual RMS, argmin r)."""
    lo, hi = math.log(r_centre / span), math.log(r_centre * span)
    xs = [lo + (hi - lo) * i / (coarse - 1) for i in range(coarse)]
    vals = [profile_residual_rms(xc, xb, grid, math.exp(x), gamma_known) for x in xs]
    i = min(range(coarse), key=lambda j: vals[j])
    best_val, best_x = vals[i], xs[i]
    a, b = xs[max(i - 1, 0)], xs[min(i + 1, coarse - 1)]
    g = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - g * (b - a), a + g * (b - a)
    fc = profile_residual_rms(xc, xb, grid, math.exp(c), gamma_known)
    fd = profile_residual_rms(xc, xb, grid, math.exp(d), gamma_known)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = profile_residual_rms(xc, xb, grid, math.exp(c), gamma_known)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = profile_residual_rms(xc, xb, grid, math.exp(d), gamma_known)
    for x, v in ((c, fc), (d, fd)):
        if v < best_val:
            best_val, best_x = v, x
    return best_val, math.exp(best_x)


def filter_geometry(delta_b: Sequence[float]) -> Tuple[float, float]:
    """(||D delta||^2, ||D^T D delta||^2) for the first-difference operator D."""
    n = len(delta_b)
    if n < 2:
        raise ValueError("need n >= 2")
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    dtd = [(w[j - 1] if j >= 1 else 0.0) - (w[j] if j <= n - 2 else 0.0) for j in range(n)]
    return nw2, math.fsum(x * x for x in dtd)


def naive_filter_stats(delta_b: Sequence[float], sigma: float, reps: int, seed: int) -> Tuple[float, float, float]:
    """Naive matched filter w = D delta on first differences of iid N(0, sigma^2) samples.
    Returns (empirical total error, sample variance of the noise statistic, its mean)."""
    rng = random.Random(seed)
    n = len(delta_b)
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    thresh = 0.5 * nw2
    err = 0
    draws: List[float] = []
    for _ in range(reps):
        for hyp in (0, 1):
            e = [rng.gauss(0.0, sigma) for _ in range(n)]
            s = math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
            draws.append(s)
            stat = s + (nw2 if hyp == 1 else 0.0)
            if (hyp == 0 and stat > thresh) or (hyp == 1 and stat <= thresh):
                err += 1
    big_n = len(draws)
    mean = math.fsum(draws) / big_n
    var = math.fsum((s - mean) ** 2 for s in draws) / (big_n - 1)
    return err / (2 * reps), var, mean


# ------------------------------------------------------------------ N1
def evaluate_n1(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    n_mid = 64 if 64 in grid_sizes else n_max
    n_late = 1024 if 1024 in grid_sizes else n_max
    a_det: Dict[str, float] = {}
    b_det: Dict[str, dict] = {}
    c_det: Dict[str, dict] = {}
    a_ok = b_ok = c_ok = True
    for fname, fres in results["families"].items():
        prm = fres["params"]
        T = prm["T"]
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            tag = f"{fname}:{kstr}"
            p = rm.Params(prm["alpha"], k, prm["gamma"], prm["c0"])
            m = rm.modes(p)
            cell = kres["windows"]["full"][str(n_mid)]
            known_cb = cell["rms_known"]["cb"]
            gk = cell["rms_impostor_bound"]["cb_gamma_known"]
            gf = cell["rms_impostor_bound"]["cb_gamma_free"]
            ratio_k = gk / known_cb
            a_det[tag] = ratio_k
            a_ok = a_ok and 0.85 <= ratio_k <= 0.95
            x = m.r_f * T / n_mid
            if x >= 4.0:
                ratio_f = gf / known_cb
                b_det[tag] = {"x_first_sample_in_layer_widths": x, "ratio": ratio_f}
                b_ok = b_ok and ratio_f <= 1e-2
            # N1c: tightness of the author's bounds against a profile least-squares minimum
            grid = rs.time_grid(T, n_mid, 0.0)
            xc, xb = relative_finite_data(p, m, grid)
            prof, r_best = profile_minimum(xc, xb, grid, m.r_s, True)
            c_det[tag + ":gamma_known:full:n=%d" % n_mid] = {"profile_over_bound": prof / gk,
                                                             "r_best_over_r_s": r_best / m.r_s}
            c_ok = c_ok and 0.99 <= prof / gk <= 1.0 + 1e-9
            gk_late = kres["windows"]["late"][str(n_late)]["rms_impostor_bound"]["cb_gamma_known"]
            grid = rs.time_grid(T, n_late, rs.WINDOWS["late"])
            xc, xb = relative_finite_data(p, m, grid)
            prof, r_best = profile_minimum(xc, xb, grid, m.r_s, True)
            c_det[tag + ":gamma_known:late:n=%d" % n_late] = {"profile_over_bound": prof / gk_late,
                                                              "r_best_over_r_s": r_best / m.r_s}
            c_ok = c_ok and 0.99 <= prof / gk_late <= 1.0 + 1e-9
            gf_max = kres["windows"]["full"][str(n_max)]["rms_impostor_bound"]["cb_gamma_free"]
            if m.r_f * T >= 100.0 and gf_max >= 1e-6:
                grid = rs.time_grid(T, n_max, 0.0)
                xc, xb = relative_finite_data(p, m, grid)
                prof, r_best = profile_minimum(xc, xb, grid, m.r_s, False)
                c_det[tag + ":gamma_free:full:n=%d" % n_max] = {"profile_over_bound": prof / gf_max,
                                                                "r_best_over_r_s": r_best / m.r_s}
                c_ok = c_ok and 0.95 <= prof / gf_max <= 1.0 + 1e-9
    return [
        {"id": "N1a", "statement": "full window, n=%d, k>=10, both families: gamma-known joint impostor bound / "
                                   "known-parameter RMS_cb in [0.85, 0.95] (calibrated gamma costs ~10%%)" % n_mid,
         "passed": a_ok, "details": a_det},
        {"id": "N1b", "statement": "full window, n=%d, first sample >= 4 layer widths (x>=4): gamma-free joint "
                                   "impostor bound / known RMS_cb <= 1e-2 (layer-blind grids are non-identifiable "
                                   "with gamma free even in the full window)" % n_mid,
         "passed": b_ok, "details": b_det},
        {"id": "N1c", "statement": "profile least-squares minimum over the equilibrium rate / author's impostor "
                                   "bound in [0.99,1] (gamma known) and [0.95,1] (gamma free, resolved grids): "
                                   "the bounds are tight, so P1's '>=' is valid",
         "passed": c_ok, "details": c_det},
    ]


# ------------------------------------------------------------------ N2
def evaluate_n2(reps: int, seeds: Sequence[int] = N2_SEEDS) -> List[dict]:
    fam = rs.FAMILIES["A"]
    p = rm.Params(fam["alpha"], 100.0, fam["gamma"], fam["c0"])
    m = rm.modes(p)
    grid = rs.time_grid(fam["T"], 64, 0.0)
    delta = [rm.relative_differences(p, t, m)[1] for t in grid]
    nw2, ndtd2 = filter_geometry(delta)
    ndtd = math.sqrt(ndtd2)
    d_real_unit = nw2 / ndtd                  # realized index per unit sigma
    sigma = d_real_unit / 3.0                 # calibrate so that d_real = 3
    d_naive = math.sqrt(nw2) / (math.sqrt(2.0) * sigma)
    p_real, p_naive = rs.phi(-1.5), rs.phi(-d_naive / 2.0)
    var_pred_real = sigma * sigma * ndtd2
    var_ratio_naive_over_real = 2.0 * nw2 / ndtd2
    big_n = 2 * reps
    se_p = math.sqrt(p_real * (1.0 - p_real) / big_n)
    se_v = math.sqrt(2.0 / (big_n - 1))
    cells = []
    for seed in seeds:
        err, var, mean = naive_filter_stats(delta, sigma, reps, seed)
        vr = var / var_pred_real
        cells.append({"seed": seed, "empirical_error": err, "z_error": (err - p_real) / se_p,
                      "variance_ratio_to_realized_prediction": vr, "z_variance": (vr - 1.0) / se_v,
                      "mean_statistic_over_sigma": mean / sigma})
    prim = cells[0]
    a_ok = (abs(prim["empirical_error"] - p_real) <= 3.0 * se_p
            and abs(prim["empirical_error"] - p_naive) > 3.0 * se_p)
    b_ok = abs(prim["variance_ratio_to_realized_prediction"] - 1.0) <= 3.0 * se_v and var_ratio_naive_over_real >= 10.0
    c_ok = all(abs(cl["z_error"]) <= 3.5 and abs(cl["z_variance"]) <= 3.5 for cl in cells)
    common = {"cell": "A, k=100, n=64, full window, computed flux from b, naive filter",
              "sigma_relative": sigma, "index_realized": 3.0, "index_naive_reported": d_naive,
              "predicted_error_realized": p_real, "predicted_error_naive": p_naive,
              "tolerance_error": 3.0 * se_p, "tolerance_variance_ratio": 3.0 * se_v,
              "variance_ratio_naive_over_realized": var_ratio_naive_over_real}
    return [
        {"id": "N2a", "statement": "d_real=3 calibration: empirical error within 3 SE of Phi(-1.5) AND farther than "
                                   "3 SE from the naive prediction Phi(-d_naive/2)",
         "passed": a_ok, "details": dict(common, primary=prim)},
        {"id": "N2b", "statement": "sample variance of the naive statistic / sigma^2 ||D^T D delta||^2 within 3 SE of 1, "
                                   "and naive/realized variance ratio 2||D delta||^2/||D^T D delta||^2 >= 10",
         "passed": b_ok, "details": dict(common, primary=prim)},
        {"id": "N2c", "statement": "all %d seeds: |z_error| <= 3.5 and |z_variance| <= 3.5" % len(seeds),
         "passed": c_ok, "details": {"cells": cells}},
    ]


# ------------------------------------------------------------------ N3
def evaluate_n3(results: dict, grid_sizes: Sequence[int]) -> dict:
    det: Dict[str, object] = {}
    ok, checked = True, 0
    for fname, fres in results["families"].items():
        prm = fres["params"]
        T = prm["T"]
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            tag = f"{fname}:{kstr}"
            p = rm.Params(prm["alpha"], k, prm["gamma"], prm["c0"])
            m = rm.modes(p)
            kd = m.kappa_defect
            _, t_j = rm.blind_spot_times(p)
            if not (kd < 0.0 and t_j is not None and T < t_j):
                det[tag] = "skipped: sign predicate (kappa_defect<0 and T<T_J) not met"
                continue
            rows = {}
            for n in grid_sizes:
                rms2 = kres["windows"]["full"][str(n)]["rms_known"]["J"] ** 2
                f2 = (1.0 + kd) ** 2 * mean_exp_on_grid(2.0 * m.r_f, T, n)
                h = mean_exp_on_grid(m.r_f, T, n)
                upper = 2.0 * abs(kd) * (1.0 + kd) * h + kd * kd
                excess = rms2 - f2
                lo_ok = excess >= -1e-7 * f2
                hi_ok = excess <= upper + 1e-7 * f2
                rows[str(n)] = {"excess_over_F2": (excess / f2 if f2 > 0 else None),
                                "upper_over_F2": (upper / f2 if f2 > 0 else None),
                                "excess": excess, "upper": upper, "pass": lo_ok and hi_ok}
                ok = ok and lo_ok and hi_ok
                checked += 1
            det[tag] = rows
    return {"id": "N3", "statement": "k>=10, both families, all full-window grids: 0 <= RMS_J^2 - (1+kappa_d)^2 G(n) "
                                     "<= 2|kappa_d|(1+kappa_d) H(n) + kappa_d^2 with exact geometric sums G, H",
            "passed": ok and checked > 0, "details": det}


# ------------------------------------------------------------------ S1-S3
def evaluate_sharpened(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    preds: List[dict] = []
    # S1: coefficient of the late-window gamma-known residual
    ok, det = True, {}
    for fname, fres in results["families"].items():
        prm = fres["params"]
        a, g, T = prm["alpha"], prm["gamma"], prm["T"]
        r_eq = a / (1.0 + g)
        rms_eq_late = math.sqrt(math.exp(-r_eq * T) * mean_exp_on_grid(2.0 * r_eq, T * (1.0 - rs.WINDOWS["late"]), n_max))
        pred = (a / (2.0 * (1.0 + g))) * rms_eq_late
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            gk = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]["cb_gamma_known"]
            ratio = k * gk / pred
            det[f"{fname}:{kstr}"] = ratio
            ok = ok and 0.98 <= ratio <= 1.0 + 1e-9
    preds.append({"id": "S1", "statement": "late window: k * gamma-known bound / [alpha/(2(1+gamma)) * rms_late(e_eq)] in [0.98, 1]",
                  "passed": ok, "details": det})
    # S2: P4a as a convergence rate (deviation ratio between k=1e3 and k=1e4 ~ 0.1)
    ok, det = True, {}
    per_k = results["families"]["A"]["per_k"]
    k3, k4 = per_k.get("1000.0"), per_k.get("10000.0")
    if k3 and k4:
        for o in ("c", "b", "J"):
            r3 = k3["endpoint"]["ratio_exact_over_leading"][o]
            r4 = k4["endpoint"]["ratio_exact_over_leading"][o]
            if r3 is None or r4 is None or r3 == 1.0:
                ok, det[o] = False, None
                continue
            ratio = (r4 - 1.0) / (r3 - 1.0)
            det[o] = ratio
            ok = ok and 0.085 <= ratio <= 0.115
    else:
        ok = False
    preds.append({"id": "S2", "statement": "A, T=1: (exact/leading - 1) at k=1e4 divided by the same at k=1e3 in [0.085, 0.115] for c, b, J",
                  "passed": ok, "details": det})
    # S3: P4b as a 1/k^2 law with 5% window, both decades
    ok, det = True, {}
    for lo, hi in (("100.0", "1000.0"), ("1000.0", "10000.0")):
        kl, kh = per_k.get(lo), per_k.get(hi)
        if not (kl and kh):
            ok = False
            continue
        rc = abs(kh["blind_spots"]["dc_at_T_c"]) / abs(kl["blind_spots"]["dc_at_T_c"])
        rj = abs(kh["blind_spots"]["dJ_at_T_J"]) / abs(kl["blind_spots"]["dJ_at_T_J"])
        det[f"{lo}->{hi}"] = {"ratio_c": rc, "ratio_J": rj}
        ok = ok and 0.0095 <= rc <= 0.0105 and 0.0095 <= rj <= 0.0105
    preds.append({"id": "S3", "statement": "blind spots: |delta(10k)|/|delta(k)| in [0.0095, 0.0105] for c (T_c) and J (T_J), both decades",
                  "passed": ok, "details": det})
    return preds


def evaluate_additions(results: dict, grid_sizes: Sequence[int], reps: int) -> List[dict]:
    grid_sizes = sorted(set(int(n) for n in grid_sizes))
    preds: List[dict] = []
    preds.extend(evaluate_n1(results, grid_sizes))
    preds.extend(evaluate_n2(reps))
    preds.append(evaluate_n3(results, grid_sizes))
    preds.extend(evaluate_sharpened(results, grid_sizes))
    return preds


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write JSON (baseline predictions + additions) to this path")
    ap.add_argument("--reps", type=int, default=rs.MC_SPEC["reps"], help="MC replicates per hypothesis")
    ap.add_argument("--max-n", type=int, default=max(rs.GRID_SIZES), help="cap on grid sizes (quick runs)")
    args = ap.parse_args(argv)
    grids = [n for n in rs.GRID_SIZES if n <= args.max_n] or [1]
    results = rs.run_study(grids, args.reps)
    adds = evaluate_additions(results, grids, args.reps)
    w = sys.stdout.write
    w("=== Baseline predeclared predictions (release_study) ===\n")
    for pr in results["predictions"]:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
    w("\n=== Review additions (release-observability-003) ===\n")
    for pr in adds:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
        w(f"      details: {json.dumps(pr['details'], default=str)}\n")
    passed = sum(1 for pr in adds if pr["passed"])
    w(f"\n{passed}/{len(adds)} review additions passed.  Executed numbers supersede the reviewer's hand estimates.\n")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"baseline_predictions": results["predictions"], "review_additions": adds,
                       "grid_sizes": grids, "reps": args.reps, "n2_seeds": list(N2_SEEDS)},
                      fh, indent=1, sort_keys=True, default=str)
        w(f"\nwrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
