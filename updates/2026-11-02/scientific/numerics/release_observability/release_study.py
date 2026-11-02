"""release_study.py -- predeclared synthetic measurement study: which observable,
time resolution and precision separate finite k from the algebraic-equilibrium
model (AB-LFR1 linear release model).  The Stage, task release-observability-002b
(computational half).  Claude (Anthropic), coordinated by Red for Richard
(Andrei) Pemberton.  Standard library only; deterministic; writes only to a
caller-supplied --out path.  Synthetic model only: no biology, no hardware
recommendation, no fit to real measurements.

Usage:  python release_study.py [--out results.json] [--reps 1000] [--max-n 16384]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from typing import Dict, List, Optional, Sequence

import release_model as rm

Z95 = 1.6448536269514722
D_STAR = 2.0 * Z95

FAMILIES: Dict[str, dict] = {
    "A": {"alpha": 1.0, "gamma": 4.0, "c0": 1.0, "T": 1.0,
          "ks": [1.0, 10.0, 100.0, 1000.0, 10000.0]},
    "B": {"alpha": 0.5, "gamma": 4.0, "c0": 0.2, "T": 3.0,
          "ks": [2.0, 20.0, 200.0]},
}
GRID_SIZES: List[int] = [1, 4, 16, 64, 256, 1024, 4096, 16384]
WINDOWS: Dict[str, float] = {"full": 0.0, "late": 0.5}
OBSERVABLES = ("c", "b", "cb", "J")
EPSILONS = (1e-2, 1e-3, 1e-4)
MC_SPEC = {"family": "A", "k": 100.0, "n": 64, "target_index": 3.0, "reps": 1000,
           "seeds": {"c": 20261101, "b": 20261102, "J": 20261103,
                     "computed_flux_from_b": 20261104}}


# ---------------------------------------------------------------- utilities
def phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def time_grid(T: float, n: int, start_frac: float = 0.0) -> List[float]:
    if n < 1:
        raise ValueError("n must be >= 1")
    t0 = start_frac * T
    return [t0 + (i + 1) * (T - t0) / n for i in range(n)]


def norm(xs: Sequence[float]) -> float:
    return math.sqrt(math.fsum(x * x for x in xs))


def rms(xs: Sequence[float]) -> float:
    return norm(xs) / math.sqrt(len(xs))


def computed_flux_indices(delta_b: Sequence[float]) -> Dict[str, float]:
    """Separation indices (per unit noise sigma) for a flux computed by first
    differences of the same b samples.  d_b: raw samples; d_comp: GLS-optimal use
    of the computed flux (= mean-removed delta); d_naive: index an analyst reports
    when treating difference noise as independent; d_real: actual deflection of
    that naive filter.  Theorem: d_real <= d_comp <= d_b."""
    n = len(delta_b)
    if n < 2:
        raise ValueError("need n >= 2")
    mean = math.fsum(delta_b) / n
    d_b = norm(delta_b)
    d_comp = norm([x - mean for x in delta_b])
    diff = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nd = norm(diff)
    d_naive = nd / math.sqrt(2.0)
    dtd = [(diff[j - 1] if j >= 1 else 0.0) - (diff[j] if j <= n - 2 else 0.0) for j in range(n)]
    ndtd = norm(dtd)
    d_real = (nd * nd / ndtd) if ndtd > 0.0 else 0.0
    return {"d_b": d_b, "d_comp": d_comp, "d_naive": d_naive, "d_real": d_real,
            "ratio_comp": d_comp / d_b if d_b > 0 else 0.0,
            "ratio_naive": d_naive / d_b if d_b > 0 else 0.0,
            "ratio_real": d_real / d_b if d_b > 0 else 0.0}


# ---------------------------------------------------------------- Monte Carlo
def mc_direct(delta: Sequence[float], sigma: float, reps: int, seed: int) -> float:
    """Empirical total error of the matched filter with midpoint threshold."""
    rng = random.Random(seed)
    nd2 = math.fsum(d * d for d in delta)
    thresh = 0.5 * nd2
    err = 0
    for _ in range(reps):
        s0 = math.fsum(d * rng.gauss(0.0, sigma) for d in delta)
        if s0 > thresh:
            err += 1
        s1 = nd2 + math.fsum(d * rng.gauss(0.0, sigma) for d in delta)
        if s1 <= thresh:
            err += 1
    return err / (2 * reps)


def mc_computed_flux(delta_b: Sequence[float], sigma: float, reps: int, seed: int) -> float:
    """Empirical total error of the naive matched filter applied to first differences."""
    rng = random.Random(seed)
    n = len(delta_b)
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    thresh = 0.5 * nw2
    err = 0
    for _ in range(reps):
        e = [rng.gauss(0.0, sigma) for _ in range(n)]
        s0 = math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
        if s0 > thresh:
            err += 1
        e = [rng.gauss(0.0, sigma) for _ in range(n)]
        s1 = nw2 + math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
        if s1 <= thresh:
            err += 1
    return err / (2 * reps)


# ---------------------------------------------------------------- analysis
def evaluate_arrays(p: rm.Params, m: rm.Modes, grid: Sequence[float]) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {k: [] for k in ("dc", "db", "dJ", "fc", "fb", "fJ", "rc", "rb")}
    for t in grid:
        dc, db, dJ = rm.relative_differences(p, t, m)
        fc, fb, fJ = rm.fast_mode_relative(p, t, m)
        rc, rb = rm.joint_gamma_known_impostor_relative(p, t, m)
        for key, val in zip(("dc", "db", "dJ", "fc", "fb", "fJ", "rc", "rb"),
                            (dc, db, dJ, fc, fb, fJ, rc, rb)):
            out[key].append(val)
    return out


def summarize_cell(arr: Dict[str, List[float]], n: int, window: str) -> dict:
    known = {"c": rms(arr["dc"]), "b": rms(arr["db"]),
             "cb": rms(arr["dc"] + arr["db"]), "J": rms(arr["dJ"])}
    bound = {"c": rms(arr["fc"]), "b": rms(arr["fb"]), "J": rms(arr["fJ"]),
             "cb_gamma_free": rms(arr["fc"] + arr["fb"]),
             "cb_gamma_known": rms(arr["rc"] + arr["rb"])}
    n_eff = {"c": n, "b": n, "cb": 2 * n, "J": n}
    eps_req = {o: math.sqrt(n_eff[o]) * known[o] / D_STAR for o in OBSERVABLES}
    disting = {str(eps): {o: (math.sqrt(n_eff[o]) * known[o] / eps >= D_STAR) for o in OBSERVABLES}
               for eps in EPSILONS}
    cell = {"n": n, "rms_known": known, "rms_impostor_bound": bound,
            "eps_required": eps_req, "distinguishable": disting}
    if window == "full" and n >= 2:
        cell["computed_flux_from_b"] = computed_flux_indices(arr["db"])
    return cell


def analyze_family(name: str, fam: dict, grid_sizes: Sequence[int]) -> dict:
    alpha, gamma, c0, T = fam["alpha"], fam["gamma"], fam["c0"], fam["T"]
    res = {"params": {k: v for k, v in fam.items() if k != "ks"}, "per_k": {}}
    for k in fam["ks"]:
        p = rm.Params(alpha, k, gamma, c0)
        m = rm.modes(p)
        kres = {"k": k, "r_f": m.r_f, "r_s": m.r_s, "r_eq": m.r_eq, "rate_shift": m.rate_shift,
                "boundary_layer_width": 1.0 / m.r_f, "n_res": math.ceil(T * m.r_f),
                "impostor_params": dict(zip(("c0", "gamma", "alpha"), rm.impostor_params(p, m))),
                "windows": {}}
        for wname, frac in WINDOWS.items():
            wres = {}
            for n in grid_sizes:
                arr = evaluate_arrays(p, m, time_grid(T, n, frac))
                wres[str(n)] = summarize_cell(arr, n, wname)
            kres["windows"][wname] = wres
        exact = rm.relative_differences(p, T, m)
        lead = rm.leading_order_endpoint(p, T)
        kres["endpoint"] = {"exact": dict(zip(("c", "b", "J"), exact)),
                            "leading_order": dict(zip(("c", "b", "J"), lead)),
                            "ratio_exact_over_leading": {
                                o: (e / l if l != 0.0 else None) for o, e, l in zip(("c", "b", "J"), exact, lead)}}
        t_c, t_j = rm.blind_spot_times(p)
        kres["blind_spots"] = {"T_c": t_c, "dc_at_T_c": rm.relative_differences(p, t_c, m)[0],
                               "T_J": t_j, "dJ_at_T_J": (rm.relative_differences(p, t_j, m)[2] if t_j else None)}
        res["per_k"][str(k)] = kres
    return res


def stiff_flux_diagnostic() -> dict:
    p = rm.Params(1.0, 1e12, 4.0, 1.0)
    t = 1e-3
    c, b = rm.finite_state(p, t)
    direct = p.k * (b - p.gamma * c)
    stable = rm.release_flux(p, t)
    return {"k": p.k, "t": t, "direct_k_times_b_minus_gamma_c_binary64": direct,
            "stable_alpha_gamma_c0_E12": stable, "abs_split": abs(direct - stable),
            "report_reference_values": {"stable": 0.7998400160, "direct_reported": 0.7989164885}}


def run_mc(reps: int) -> List[dict]:
    fam = FAMILIES[MC_SPEC["family"]]
    p = rm.Params(fam["alpha"], MC_SPEC["k"], fam["gamma"], fam["c0"])
    m = rm.modes(p)
    arr = evaluate_arrays(p, m, time_grid(fam["T"], MC_SPEC["n"], 0.0))
    target = MC_SPEC["target_index"]
    cells = []
    for obs, key in (("c", "dc"), ("b", "db"), ("J", "dJ")):
        delta = arr[key]
        sigma = norm(delta) / target
        p_pred = phi(-target / 2.0)
        p_emp = mc_direct(delta, sigma, reps, MC_SPEC["seeds"][obs])
        tol = 3.0 * math.sqrt(p_pred * (1.0 - p_pred) / (2.0 * reps))
        cells.append({"observable": obs, "sigma_relative": sigma, "index": target,
                      "predicted_error": p_pred, "empirical_error": p_emp,
                      "tolerance": tol, "within_tolerance": abs(p_emp - p_pred) <= tol})
    delta = arr["db"]
    sigma = norm(delta) / target
    ci = computed_flux_indices(delta)
    d_real, d_naive, d_comp = ci["d_real"] / sigma, ci["d_naive"] / sigma, ci["d_comp"] / sigma
    p_real, p_naive = phi(-d_real / 2.0), phi(-d_naive / 2.0)
    p_emp = mc_computed_flux(delta, sigma, reps, MC_SPEC["seeds"]["computed_flux_from_b"])
    tol = 3.0 * math.sqrt(p_real * (1.0 - p_real) / (2.0 * reps))
    cells.append({"observable": "computed_flux_from_b (naive filter)", "sigma_relative": sigma,
                  "index_b": target, "index_comp_gls": d_comp, "index_naive_reported": d_naive,
                  "index_realized": d_real, "predicted_error_realized": p_real,
                  "predicted_error_naive": p_naive, "empirical_error": p_emp, "tolerance": tol,
                  "within_tolerance": abs(p_emp - p_real) <= tol,
                  "naive_prediction_also_within_tolerance": abs(p_emp - p_naive) <= tol})
    return cells


def evaluate_predictions(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    n_lo = 4 if 4 in grid_sizes else min(grid_sizes)
    preds: List[dict] = []
    fam_a = results["families"]["A"]
    T_a = FAMILIES["A"]["T"]

    # P1 late-window structural non-identifiability
    ok, details = True, {}
    for kstr, kres in fam_a["per_k"].items():
        k = kres["k"]
        if k < 10.0:
            continue
        bnd = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]
        free_ok = all(bnd[o] <= 1e-6 for o in ("c", "b", "J", "cb_gamma_free"))
        known_ok = bnd["cb_gamma_known"] >= 0.05 / k
        details[kstr] = {"free_bounds": {o: bnd[o] for o in ("c", "b", "J", "cb_gamma_free")},
                         "cb_gamma_known": bnd["cb_gamma_known"], "pass": free_ok and known_ok}
        ok = ok and free_ok and known_ok
    preds.append({"id": "P1", "statement": "late window: nuisance-free impostor bounds <=1e-6; joint with gamma known >=0.05/k",
                  "passed": ok, "details": details})

    # P2 resolved independent flux dominates
    ok, details = True, {}
    for fname, fres in results["families"].items():
        for kstr, kres in fres["per_k"].items():
            if kres["n_res"] > n_max:
                continue
            kn = kres["windows"]["full"][str(n_max)]["rms_known"]
            ratio = kn["J"] / max(kn["c"], kn["b"])
            details[f"{fname}:{kstr}"] = ratio
            ok = ok and ratio >= 2.0
    preds.append({"id": "P2", "statement": "resolved grids: RMS_J >= 2*max(RMS_c, RMS_b)",
                  "passed": ok, "details": details})

    # P3 computed-flux chain
    ok, worst = True, 0.0
    for fres in results["families"].values():
        for kres in fres["per_k"].values():
            for cell in kres["windows"]["full"].values():
                ci = cell.get("computed_flux_from_b")
                if not ci:
                    continue
                v1 = ci["d_real"] - ci["d_comp"] * (1.0 + 1e-12)
                v2 = ci["d_comp"] - ci["d_b"] * (1.0 + 1e-12)
                worst = max(worst, v1, v2)
                ok = ok and v1 <= 0.0 and v2 <= 0.0
    preds.append({"id": "P3", "statement": "d_real <= d_comp <= d_b for every full-window cell",
                  "passed": ok, "details": {"worst_violation": worst}})

    # P4a leading-order endpoint at k=1000
    k1000 = fam_a["per_k"].get("1000.0")
    ok, details = True, {}
    if k1000:
        for o, r in k1000["endpoint"]["ratio_exact_over_leading"].items():
            details[o] = r
            ok = ok and (r is not None) and abs(r - 1.0) <= 0.05
    else:
        ok = False
    preds.append({"id": "P4a", "statement": "k=1000, T=1: exact/leading-order within 5% for c, b, J",
                  "passed": ok, "details": details})

    # P4b blind spots scale faster than 1/k
    ok, details = True, {}
    k100 = fam_a["per_k"].get("100.0")
    if k100 and k1000:
        rc = abs(k1000["blind_spots"]["dc_at_T_c"]) / abs(k100["blind_spots"]["dc_at_T_c"])
        rj = abs(k1000["blind_spots"]["dJ_at_T_J"]) / abs(k100["blind_spots"]["dJ_at_T_J"])
        details = {"ratio_c": rc, "ratio_J": rj}
        ok = rc <= 0.03 and rj <= 0.03
    else:
        ok = False
    preds.append({"id": "P4b", "statement": "endpoint blind spots: |delta(k=1000)|/|delta(k=100)| <= 0.03 for c at T=5, J at T=3.75",
                  "passed": ok, "details": details})

    # P5a/P5b/P5c resolution
    oka, okb, da, db_ = True, True, {}, {}
    ratios = []
    for kstr, kres in fam_a["per_k"].items():
        est = 1.0 / math.sqrt(2.0 * kres["r_f"] * T_a)
        rj_max = kres["windows"]["full"][str(n_max)]["rms_known"]["J"]
        if 4 * kres["n_res"] <= n_max:
            da[kstr] = rj_max / est
            oka = oka and 0.7 <= rj_max / est <= 1.3
        if kres["n_res"] > n_max:
            db_[kstr] = rj_max / est
            okb = okb and rj_max / est <= 0.5
        if kres["n_res"] <= n_max:
            ratios.append((kres["k"], rj_max / kres["windows"]["full"][str(n_lo)]["rms_known"]["J"]))
    ratios.sort()
    okc = all(ratios[i][1] <= ratios[i + 1][1] for i in range(len(ratios) - 1))
    preds.append({"id": "P5a", "statement": "4*n_res <= n_max: RMS_J(n_max) within [0.7,1.3] of (2 r_f T)^-1/2",
                  "passed": oka, "details": da})
    preds.append({"id": "P5b", "statement": "n_res > n_max: RMS_J(n_max) <= 0.5*(2 r_f T)^-1/2",
                  "passed": okb, "details": db_})
    preds.append({"id": "P5c", "statement": f"resolved k: RMS_J(n_max)/RMS_J({n_lo}) nondecreasing in k",
                  "passed": okc, "details": {str(k): r for k, r in ratios}})

    # P6 Monte Carlo
    mc = results["monte_carlo"]
    ok = all(cell["within_tolerance"] for cell in mc)
    preds.append({"id": "P6", "statement": "MC error rates match Phi(-d/2) (d_real for computed flux)",
                  "passed": ok, "details": {cell["observable"]: cell["within_tolerance"] for cell in mc}})
    return preds


def run_study(grid_sizes: Sequence[int] = GRID_SIZES, reps: int = MC_SPEC["reps"]) -> dict:
    grid_sizes = sorted(set(int(n) for n in grid_sizes))
    results = {"spec": {"families": FAMILIES, "grid_sizes": grid_sizes, "windows": WINDOWS,
                        "observables": list(OBSERVABLES), "epsilons": list(EPSILONS),
                        "D_star": D_STAR, "mc": dict(MC_SPEC, reps=reps),
                        "noise_model": "iid Gaussian; sigma_c=eps*c0, sigma_b=eps*gamma*c0, "
                                       "sigma_J=eps*alpha*gamma*c0/(1+gamma); fixed per sample"},
               "families": {name: analyze_family(name, fam, grid_sizes) for name, fam in FAMILIES.items()},
               "stiff_flux_diagnostic": stiff_flux_diagnostic(),
               "monte_carlo": run_mc(reps)}
    results["predictions"] = evaluate_predictions(results, grid_sizes)
    return results


# ---------------------------------------------------------------- reporting
def _f(x: Optional[float]) -> str:
    return "   n/a   " if x is None else f"{x:9.3e}"


def print_summary(results: dict, out=sys.stdout) -> None:
    w = out.write
    grid_sizes = results["spec"]["grid_sizes"]
    n_max = max(grid_sizes)
    w(f"release-observability-002b synthetic study  (D* = {D_STAR:.4f}; decision d >= D*)\n")
    for fname, fres in results["families"].items():
        prm = fres["params"]
        w(f"\n=== Family {fname}: alpha={prm['alpha']} gamma={prm['gamma']} c0={prm['c0']} T={prm['T']} ===\n")
        for obs in OBSERVABLES:
            w(f"\n-- RMS relative separation, all parameters known, full window, observable {obs} --\n")
            w(f"{'k':>8} " + " ".join(f"{'n=' + str(n):>9}" for n in grid_sizes) + "\n")
            for kstr, kres in fres["per_k"].items():
                row = [kres["windows"]["full"][str(n)]["rms_known"][obs] for n in grid_sizes]
                w(f"{kres['k']:8.0f} " + " ".join(_f(x) for x in row) + "\n")
        w(f"\n-- Late window [T/2,T], n={n_max}: impostor-bound RMS (nuisance parameters free) --\n")
        w(f"{'k':>8} {'c':>9} {'b':>9} {'J':>9} {'cb(g free)':>10} {'cb(g known)':>11} {'0.05/k':>9}\n")
        for kstr, kres in fres["per_k"].items():
            b = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]
            w(f"{kres['k']:8.0f} {_f(b['c'])} {_f(b['b'])} {_f(b['J'])} {_f(b['cb_gamma_free']):>10} "
              f"{_f(b['cb_gamma_known']):>11} {_f(0.05 / kres['k'])}\n")
        w(f"\n-- Required relative precision eps_req (full window, known params) at n=64 and n={n_max} --\n")
        w(f"{'k':>8} " + " ".join(f"{o + '@64':>9}" for o in OBSERVABLES)
          + " " + " ".join(f"{o + '@max':>9}" for o in OBSERVABLES) + "\n")
        for kstr, kres in fres["per_k"].items():
            e64 = kres["windows"]["full"].get("64", kres["windows"]["full"][str(n_max)])["eps_required"]
            emx = kres["windows"]["full"][str(n_max)]["eps_required"]
            w(f"{kres['k']:8.0f} " + " ".join(_f(e64[o]) for o in OBSERVABLES)
              + " " + " ".join(_f(emx[o]) for o in OBSERVABLES) + "\n")
        w("\n-- Time resolution of the independent release flux --\n")
        w(f"{'k':>8} {'r_f':>10} {'1/r_f':>9} {'n_res':>7} {'(2r_fT)^-1/2':>12} "
          + " ".join(f"{'J@' + str(n):>9}" for n in grid_sizes) + "\n")
        for kstr, kres in fres["per_k"].items():
            est = 1.0 / math.sqrt(2.0 * kres["r_f"] * prm["T"])
            row = [kres["windows"]["full"][str(n)]["rms_known"]["J"] for n in grid_sizes]
            w(f"{kres['k']:8.0f} {kres['r_f']:10.3e} {_f(1.0 / kres['r_f'])} {kres['n_res']:7d} {est:12.3e} "
              + " ".join(_f(x) for x in row) + "\n")
        w(f"\n-- Flux computed from the same b samples (full window): ratios to raw-b index --\n")
        w(f"{'k':>8} {'n':>6} {'comp/b':>9} {'naive/b':>9} {'real/b':>9}\n")
        for kstr, kres in fres["per_k"].items():
            for n in grid_sizes:
                ci = kres["windows"]["full"][str(n)].get("computed_flux_from_b")
                if ci and n in (64, n_max):
                    w(f"{kres['k']:8.0f} {n:6d} {_f(ci['ratio_comp'])} {_f(ci['ratio_naive'])} {_f(ci['ratio_real'])}\n")
        w("\n-- Endpoint t=T: exact relative difference / leading-order ratio; blind spots --\n")
        for kstr, kres in fres["per_k"].items():
            ep, bs = kres["endpoint"], kres["blind_spots"]
            w(f"k={kres['k']:.0f}: exact c={_f(ep['exact']['c'])} b={_f(ep['exact']['b'])} J={_f(ep['exact']['J'])}"
              f" | ratio c={_f(ep['ratio_exact_over_leading']['c'])} b={_f(ep['ratio_exact_over_leading']['b'])}"
              f" J={_f(ep['ratio_exact_over_leading']['J'])} | dc(T_c={bs['T_c']:.3g})={_f(bs['dc_at_T_c'])}"
              f" dJ(T_J={bs['T_J']})={_f(bs['dJ_at_T_J'])}\n")
    sd = results["stiff_flux_diagnostic"]
    w(f"\n=== Stiff-flux diagnostic (k=1e12, t=1e-3): direct={sd['direct_k_times_b_minus_gamma_c_binary64']:.10f}"
      f" stable={sd['stable_alpha_gamma_c0_E12']:.10f} |split|={sd['abs_split']:.3e}"
      f" (REPORT: stable 0.7998400160, direct 0.7989164885) ===\n")
    w("\n=== Monte Carlo (predeclared cells) ===\n")
    for cell in results["monte_carlo"]:
        w(json.dumps(cell) + "\n")
    w("\n=== Predeclared predictions ===\n")
    for pr in results["predictions"]:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
        w(f"      details: {json.dumps(pr['details'])}\n")
    passed = sum(1 for pr in results["predictions"] if pr["passed"])
    w(f"\n{passed}/{len(results['predictions'])} predeclared predictions passed. "
      f"Executed numbers supersede any expectation stated in the request text.\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write full JSON results to this path")
    ap.add_argument("--reps", type=int, default=MC_SPEC["reps"], help="MC replicates per hypothesis")
    ap.add_argument("--max-n", type=int, default=max(GRID_SIZES), help="cap on grid sizes (quick runs)")
    args = ap.parse_args(argv)
    grids = [n for n in GRID_SIZES if n <= args.max_n] or [1]
    results = run_study(grids, args.reps)
    print_summary(results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
