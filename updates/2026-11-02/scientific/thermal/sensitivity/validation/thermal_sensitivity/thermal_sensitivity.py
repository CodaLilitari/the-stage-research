#!/usr/bin/env python3
"""thermal-sensitivity-001 driver: which T0-HYP-1 assumptions control the surface/internal ranking
reversal and the steady/transient temperatures. Author: Claude (Anthropic), coordinated by Red;
Coda's (Codex Lily, with Andrei) steady reference and two-node transient are read-only inputs.
Standard library only; deterministic; writes only to --output. Not physical validation.

Usage:
  python thermal_sensitivity.py --output sensitivity_results.json
  options: --seed --morris-r --sobol-n --transient-morris-r --transient-n --grid-stride
           --skip-transient --skip-grid   (any change from defaults is recorded as a deviation)
"""
import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import steady_closed_form as scf  # noqa: E402
import sampling as smp  # noqa: E402
import transient_wrapper as tw  # noqa: E402

TASK = "thermal-sensitivity-001"
DEFAULTS = {"seed": 20261101, "morris_r": 20, "morris_p": 4, "sobol_n": 2048,
            "transient_morris_r": 10, "transient_sobol_n": 64, "transient_dt": 1.0,
            "transient_horizon": 1800.0, "transient_P": 5, "grid_stride": 1,
            "skip_transient": False, "skip_grid": False}
P_LEVELS = (1, 5, 10)
MODES = ("common_bias", "independent_layers")
BASE_FACTORS = [("k_s", 0.18, 0.35), ("k_f", 0.12, 0.25), ("r_c", 0.0, 2.0e-3),
                ("h", 3.0, 15.0), ("R_rej", 1.0, 10.0)]
FACTOR_DOMAINS = {
    "common_bias": BASE_FACTORS + [("delta_all", -0.1, 0.1)],
    "independent_layers": BASE_FACTORS + [("delta_outer", -0.1, 0.1), ("delta_film", -0.1, 0.1),
                                          ("delta_inner", -0.1, 0.1)],
}
GRIDS = {
    "common_bias": [("k_s", ["0.18", "0.265", "0.35"]), ("k_f", ["0.12", "0.185", "0.25"]),
                    ("r_c", ["0", "0.001", "0.002"]),
                    ("h", ["3", "3.5", "4", "4.5", "5", "6", "8", "10", "12", "15"]),
                    ("R_rej", ["1", "1.1", "1.2", "1.3", "1.5", "2", "3", "5", "7", "10"]),
                    ("delta_all", ["-0.1", "0", "0.1"])],
    "independent_layers": [("k_s", ["0.18", "0.35"]), ("k_f", ["0.12", "0.25"]),
                           ("r_c", ["0", "0.002"]), ("h", ["3", "3.5", "4", "4.5", "5", "8", "15"]),
                           ("R_rej", ["1", "1.2", "1.5", "2", "5", "10"]),
                           ("delta_outer", ["-0.1", "0", "0.1"]), ("delta_film", ["-0.1", "0", "0.1"]),
                           ("delta_inner", ["-0.1", "0", "0.1"])],
}
P1_FLIPPED_CELLS = sorted(["3,1", "3,1.1", "3,1.2", "3,1.3", "3,1.5", "3.5,1", "3.5,1.1", "3.5,1.2",
                           "3.5,1.3", "4,1", "4,1.1", "4.5,1"])
DECLARED_HASHES = {
    "thermal/thermal_reference.py": "7032eb2cdb7677c3f29401865d3f5f1f185c826d5f8395e5ec263ea15d642c56d",
    "thermal/reference_results.json": "e97cf35c8accb051096fdca20ec89a0a157015b863e94cb01020a8fdb5af3a56",
    "thermal_transient/rc_transient.py": "94ff435da55d2bccef769197d534e735e5813612a3275a829f703f05b5db6e0b",
}
# Coda's executed fault-suite peaks (validation/thermal_transient/REPORT.md): peak H (time), peak surface (time).
CODA_TRANSIENT_PEAKS = {
    ("H1", "intact_sensor_on"): (33.831193, 900, 33.554994, 900),
    ("H1", "rear_loss_sensor_on"): (61.143480, 900, 59.747155, 901),
    ("H2", "intact_sensor_on"): (33.861287, 900, 33.362444, 900),
    ("H2", "rear_loss_sensor_on"): (55.545063, 900, 53.153638, 904),
    ("H3", "intact_sensor_on"): (33.884652, 900, 32.963939, 900),
    ("H3", "rear_loss_sensor_on"): (50.169875, 900, 45.881263, 914),
}
LATE_PEAK_MARGIN_S = 300.0


def jsonable(o):
    if isinstance(o, Fraction):
        return str(o)
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, set):
        return sorted(jsonable(v) for v in o)
    return o


def accept(acceptance, ident, passed, detail):
    acceptance.append({"id": ident, "passed": bool(passed), "detail": detail})


def check_input_hashes(deviations):
    out = {}
    for rel, declared in DECLARED_HASHES.items():
        path = HERE.parent / rel
        entry = {"path": str(path), "declared_sha256": declared, "found": path.is_file()}
        if path.is_file():
            entry["observed_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["match"] = entry["observed_sha256"] == declared
            if not entry["match"]:
                deviations.append("hash mismatch for " + rel)
        else:
            deviations.append("input file not found: " + rel)
        out[rel] = entry
    return out


def params_from_named(stack, mode, named, P, exact_arithmetic):
    deltas = {k: v for k, v in named.items() if k.startswith("delta_")}
    r = named.get("R_rej")
    return scf.make_params(stack, mode, deltas, exact_arithmetic, k_s=named["k_s"], k_f=named["k_f"],
                           r_c=named["r_c"], h=named["h"], r=r, P=P)


def steady_outputs(named, P, mode):
    out = {}
    for stack in scf.STACKS:
        s = scf.steady(params_from_named(stack, mode, named, P, False))
        out["T_surface_" + stack] = s["T_surface"]
        out["T_H_" + stack] = s["T_H"]
    out["gap_surface_H1_H3"] = out["T_surface_H1"] - out["T_surface_H3"]
    out["gap_H_H1_H3"] = out["T_H_H1"] - out["T_H_H3"]
    return out


def reference_section(acceptance):
    rows = scf.reference_rows_check()
    accept(acceptance, "AC1", all(r["passed"] for r in rows),
           "closed form vs Coda's 12 reference rows (exact front flux, |dT| <= 1e-9 K)")
    return rows


def nominal_tables(acceptance):
    closed, partial_rows = [], []
    all_equal = True
    for stack in scf.STACKS:
        for P in P_LEVELS:
            for blocked in (False, True):
                p = scf.make_params(stack, P=P, r=None if blocked else scf.NOMINAL_EXOGENOUS["r"])
                s = scf.steady(p)
                closed.append({"stack": stack, "P": P, "rear_blocked": blocked,
                               **{k: {"exact": str(s[k]), "float": float(s[k])}
                                  for k in ("a", "b", "c", "F", "B", "T_surface", "T_S", "T_H")},
                               "margin_surface_40C_study_comparator_only": 40.0 - float(s["T_surface"]),
                               "margin_internal_60C_study_comparator_only": 60.0 - float(s["T_H"])})
                for x in scf.FACTOR_NAMES:
                    if blocked and x == "r":
                        continue
                    hand = scf.partials(p, x)
                    dual = scf.partials_by_dual(p, x)
                    equal = all(hand[k] == dual[k] for k in scf.OUTPUT_KEYS)
                    all_equal = all_equal and equal
                    partial_rows.append({"stack": stack, "P": P, "rear_blocked": blocked, "factor": x,
                                         "dual_equal": equal,
                                         **{"d" + k: {"exact": str(hand[k]), "float": float(hand[k])}
                                            for k in scf.OUTPUT_KEYS}})
    accept(acceptance, "AC2", all_equal, "hand partials == exact dual-number partials for 18 nominal cases")
    return closed, partial_rows


def analytic_condition():
    out = {"statement": "T_surface(X)-T_surface(Y) = c (F_X-F_Y); T_H(X)-T_H(Y) = -R_rej (F_X-F_Y); "
                        "symmetric discriminant (a_Y-a_X)[R_rej(2P+J) - J/(hA) + 2(T_res-T_amb)]",
           "per_P": {}}
    for P in P_LEVELS:
        kap = scf.kappa(P)
        brackets = {}
        for stack in scf.STACKS:
            s = scf.steady(scf.make_params(stack, P=P))
            brackets[stack] = str(scf.symmetric_bracket(s))
        out["per_P"][str(P)] = {
            "kappa_K_per_W_times_W_per_m2K": {"exact": str(kap), "float": float(kap)},
            "flip_condition": "R_rej < kappa/h (equal reservoirs)",
            "h_upper_bound_for_any_flip_in_domain": float(kap),
            "uniform_measure_flip_fraction_h3_15_R1_10": scf.uniform_flip_fraction(kap),
            "symmetric_bracket_at_nominal": brackets}
    return out


def method_self_checks(acceptance):
    lin = [("x1", 0.0, 1.0), ("x2", 0.0, 1.0), ("x3", 0.0, 1.0)]
    coeff = (2.0, -3.0, 0.5)
    morris = smp.run_morris(lin, lambda v: {"f": 1.0 + coeff[0] * v["x1"] + coeff[1] * v["x2"]
                                             + coeff[2] * v["x3"]}, ("selfcheck", "linear"), 8, 4)
    eff = morris["effects"]["f"]
    morris_ok = all(abs(eff[n]["mu"] - c) <= 1e-9 and eff[n]["sigma"] <= 1e-9
                    for n, c in zip(("x1", "x2", "x3"), coeff))
    sobol = smp.run_sobol(lin, lambda v: {"f": v["x1"] + 2.0 * v["x2"] * v["x3"]}, ("selfcheck", "sobol"), 4096)
    S, ST = sobol["indices"]["f"]["S"], sobol["indices"]["f"]["ST"]
    exact_S, exact_ST = (0.3, 0.3, 0.3), (0.3, 0.4, 0.4)
    sobol_ok = all(abs(S[n] - e) <= 0.05 for n, e in zip(("x1", "x2", "x3"), exact_S)) and \
        all(abs(ST[n] - e) <= 0.05 for n, e in zip(("x1", "x2", "x3"), exact_ST))
    accept(acceptance, "AC5", morris_ok and sobol_ok, "Morris linear exactness and Sobol test function N=4096")
    return {"morris_linear": {"coefficients": coeff, "effects": eff, "passed": morris_ok},
            "sobol_x1_plus_2x2x3": {"S": S, "ST": ST, "exact_S": exact_S, "exact_ST": exact_ST,
                                    "passed": sobol_ok}}


def classify_grid(mode, P, blocked=False, stride=1):
    """Exact classification of every (stride-th) grid point, brute force and analytic, all pairs."""
    grid = [(k, v) for k, v in GRIDS[mode] if not (blocked and k == "R_rej")]
    keys = [k for k, _ in grid]
    counts = Counter()
    cell_classes = {}
    checked = agree = pair_identical = 0
    for n, combo in enumerate(itertools.product(*[v for _, v in grid])):
        if n % stride:
            continue
        literal = dict(zip(keys, combo))
        named = {k: Fraction(v) for k, v in literal.items()}
        if blocked:
            named["R_rej"] = None
        states = {s: scf.steady(params_from_named(s, mode, named, Fraction(P), True)) for s in scf.STACKS}
        bf = {pair: scf.brute_force_class(states[pair[0]], states[pair[1]]) for pair in scf.PAIRS}
        an = {pair: scf.analytic_class(states[pair[0]], states[pair[1]]) for pair in scf.PAIRS}
        checked += 1
        agree += all(bf[pair] == an[pair] for pair in scf.PAIRS)
        pair_identical += len(set(bf.values())) == 1
        cls = bf[("H1", "H3")]
        counts[cls] += 1
        cell = literal["h"] + "," + (literal["R_rej"] if not blocked else "blocked")
        cell_classes.setdefault(cell, set()).add(cls)
    flipped_cells = sorted(c for c, s in cell_classes.items() if "flipped" in s)
    mixed_cells = sorted(c for c, s in cell_classes.items() if len(s) > 1)
    return {"mode": mode, "P": P, "rear_blocked": blocked, "stride": stride, "checked": checked,
            "counts_H1_vs_H3": dict(sorted(counts.items())), "flipped_cells_h_R": flipped_cells,
            "cells_with_mixed_classes": mixed_cells, "analytic_agreement": agree,
            "pair_pattern_identical": pair_identical,
            "cell_classes": {c: sorted(s) for c, s in sorted(cell_classes.items())}}


def grid_section(cfg, acceptance):
    stride = cfg["grid_stride"]
    results = []
    for mode in MODES:
        for P in P_LEVELS:
            results.append(classify_grid(mode, P, False, stride))
            results.append(classify_grid(mode, P, True, stride))
    finite = [g for g in results if not g["rear_blocked"]]
    blocked = [g for g in results if g["rear_blocked"]]
    total = sum(g["checked"] for g in results)
    accept(acceptance, "AC3", sum(g["counts_H1_vs_H3"].get("same_direction", 0) for g in results) == 0,
           "no same-direction ranking at any checked grid point (%d points)" % total)
    accept(acceptance, "AC4", all(g["analytic_agreement"] == g["checked"] for g in results),
           "analytic class equals brute-force class at every checked point, all three pairs")
    accept(acceptance, "AC4b", all(g["pair_pattern_identical"] == g["checked"] for g in results),
           "pairs (H1,H2),(H2,H3),(H1,H3) share the class at every checked point")
    common = [g for g in finite if g["mode"] == "common_bias"]
    p1_other = all(g["counts_H1_vs_H3"].get("flipped", 0) == 0 for g in common if g["P"] != 1)
    g1 = [g for g in common if g["P"] == 1][0]
    p1_cells = g1["flipped_cells_h_R"] == P1_FLIPPED_CELLS
    p1_constant = all(g1["cell_classes"][c] == ["flipped"] for c in g1["flipped_cells_h_R"])
    ties = sum(g["counts_H1_vs_H3"].get(k, 0) for g in finite for k in ("tie", "tie_surface", "tie_interior"))
    indep = [g for g in finite if g["mode"] == "independent_layers"]
    p3 = all(g["counts_H1_vs_H3"].get("flipped", 0) == 0 for g in indep if g["P"] != 1) and all(
        float(c.split(",")[0]) <= 5 and float(c.split(",")[1]) <= 1.5
        for g in indep if g["P"] == 1 for c in g["flipped_cells_h_R"])
    p4 = all(g["counts_H1_vs_H3"] == {"tie_surface": g["checked"]} for g in blocked)
    predictions = {
        "P1": {"passed": p1_other and p1_cells and p1_constant,
               "flipped_only_at_P1": p1_other, "cells_equal_predicted": p1_cells,
               "class_constant_in_flipped_cells": p1_constant, "observed_cells": g1["flipped_cells_h_R"],
               "predicted_cells": P1_FLIPPED_CELLS},
        "P2": {"passed": ties == 0, "ties_at_finite_R_rej": ties},
        "P3": {"passed": p3, "flipped_cells_P1": [g["flipped_cells_h_R"] for g in indep if g["P"] == 1][0]},
        "P4": {"passed": p4},
        "evaluated_on_full_grid": stride == 1,
    }
    return {"grids": results, "predictions": predictions,
            "note": "grid counts over-resolve the low-h/low-R_rej corner by design; they are not domain fractions"}


def screen(factors, evaluate, seed_parts, morris_r, morris_p, sobol_n):
    return {"morris": smp.run_morris(factors, evaluate, seed_parts, morris_r, morris_p),
            "sobol": smp.run_sobol(factors, evaluate, seed_parts, sobol_n)}


def sobol_sanity_ok(sobol, min_s, max_sum, min_gap):
    for name, s in sobol["sanity"].items():
        if s.get("constant_output"):
            continue
        if s["min_S"] < min_s or s["sum_S"] > max_sum or s["min_ST_minus_S"] < min_gap:
            return False
    return True


def steady_section(cfg, acceptance):
    out = {}
    sanity_ok = True
    for mode in MODES:
        for P in P_LEVELS:
            label = (cfg["seed"], "steady", mode, "P%d" % P)
            res = screen(FACTOR_DOMAINS[mode], lambda v, P=P, mode=mode: steady_outputs(v, P, mode),
                         label, cfg["morris_r"], cfg["morris_p"], cfg["sobol_n"])
            sanity_ok = sanity_ok and sobol_sanity_ok(res["sobol"], -0.05, 1.10, -0.05)
            out["%s|P%d" % (mode, P)] = res
    accept(acceptance, "AC10-steady", sanity_ok, "steady Sobol sanity bounds (min S>=-0.05, sum S<=1.10, ST>=S-0.05)")
    again = screen(FACTOR_DOMAINS["common_bias"], lambda v: steady_outputs(v, 5, "common_bias"),
                   (cfg["seed"], "steady", "common_bias", "P5"), cfg["morris_r"], cfg["morris_p"], cfg["sobol_n"])
    first = out["common_bias|P5"]
    repro = (again["morris"]["design_sha256"] == first["morris"]["design_sha256"]
             and again["sobol"]["design_sha256"] == first["sobol"]["design_sha256"]
             and json.dumps(jsonable(again), sort_keys=True) == json.dumps(jsonable(first), sort_keys=True))
    accept(acceptance, "AC6", repro, "regenerated steady common_bias P5 designs and indices identical")
    return out


def transient_section(cfg, acceptance, deviations):
    try:
        rc, rc_file = tw.load_rc_transient()
    except (FileNotFoundError, ImportError, AttributeError) as exc:
        deviations.append("transient section not run: " + str(exc))
        for ident in ("AC7", "AC8", "AC9", "AC10-transient"):
            accept(acceptance, ident, False, "not evaluated: rc_transient unavailable")
        return {"available": False, "error": str(exc)}
    horizon, dt = cfg["transient_horizon"], cfg["transient_dt"]
    audit = {"runs": 0, "energy_failures": 0, "late_peaks": 0, "late_peak_margin_s": LATE_PEAK_MARGIN_S}

    def audited(params, segments):
        res = tw.run_case(rc, params, segments, dt)
        audit["runs"] += 1
        audit["energy_failures"] += 0 if res["energy_ok"] else 1
        if max(res["t_peak_H"], res["t_peak_surface"]) > horizon - LATE_PEAK_MARGIN_S:
            audit["late_peaks"] += 1
        return res

    nominal = {}
    ac7 = True
    fields = ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv")
    for stack in scf.STACKS:
        ref = rc.nominal(stack)
        mine = tw.lump_parameters(rc, scf.make_params(stack, exact_arithmetic=False))
        dev = max(abs(getattr(mine, f) - getattr(ref, f)) / max(1.0, abs(getattr(ref, f))) for f in fields)
        ac7 = ac7 and dev <= 1e-12
        entry = {"parameter_max_relative_deviation_vs_rc_nominal": dev, "cases": {}}
        for case in ("intact_sensor_on", "rear_loss_sensor_on"):
            res = audited(mine, tw.scenario_segments(case, 5.0, horizon=horizon))
            cH, tH, cS, tS = CODA_TRANSIENT_PEAKS[(stack, case)]
            cmp_ = {"dpeak_H": abs(res["peak_H"] - cH), "dt_peak_H": abs(res["t_peak_H"] - tH),
                    "dpeak_surface": abs(res["peak_surface"] - cS), "dt_peak_surface": abs(res["t_peak_surface"] - tS)}
            ok = cmp_["dpeak_H"] <= 1e-5 and cmp_["dpeak_surface"] <= 1e-5 and \
                cmp_["dt_peak_H"] <= 1.0 and cmp_["dt_peak_surface"] <= 1.0
            ac7 = ac7 and ok
            entry["cases"][case] = {"result": res, "vs_coda_table": cmp_, "passed": ok}
        for P in P_LEVELS:
            res = audited(mine, tw.scenario_segments("rear_blocked_from_start", float(P), horizon=horizon))
            entry["cases"]["rear_blocked_from_start|P%d" % P] = {"result": res}
        nominal[stack] = entry
    accept(acceptance, "AC7", ac7, "wrapper reproduces rc_transient.nominal (1e-12) and Coda's six tabulated peaks (1e-5 K, 1 s)")

    P = cfg["transient_P"]

    def transient_outputs(named, mode):
        out = {}
        for stack in scf.STACKS:
            params = tw.lump_parameters(rc, params_from_named(stack, mode, named, P, False))
            res = audited(params, tw.scenario_segments("rear_loss_sensor_on", float(P), horizon=horizon))
            out["peak_H_" + stack] = res["peak_H"]
            out["peak_surface_" + stack] = res["peak_surface"]
        out["gap_peak_H_H1_H3"] = out["peak_H_H1"] - out["peak_H_H3"]
        out["gap_peak_surface_H1_H3"] = out["peak_surface_H1"] - out["peak_surface_H3"]
        return out

    screening = {}
    sanity_ok = True
    for mode in MODES:
        res = screen(FACTOR_DOMAINS[mode], lambda v, mode=mode: transient_outputs(v, mode),
                     (cfg["seed"], "transient", mode, "P%d" % P),
                     cfg["transient_morris_r"], cfg["morris_p"], cfg["transient_sobol_n"])
        sanity_ok = sanity_ok and sobol_sanity_ok(res["sobol"], -0.15, 1.30, -0.25)
        screening["%s|P%d|rear_loss_sensor_on" % (mode, P)] = res
    accept(acceptance, "AC8", audit["energy_failures"] == 0, "every transient run passes rc_transient's energy audit")
    accept(acceptance, "AC9", audit["late_peaks"] == 0, "every peak at least %.0f s before the horizon" % LATE_PEAK_MARGIN_S)
    accept(acceptance, "AC10-transient", sanity_ok, "transient Sobol sanity bounds (min S>=-0.15, sum S<=1.30, ST>=S-0.25)")
    return {"available": True, "rc_transient_file": str(rc_file), "model": "T0-LUMP2-1 (Coda), called",
            "dt_s": dt, "horizon_s": horizon, "audit": audit, "nominal": nominal, "screening": screening}


def run(config=None):
    cfg = dict(DEFAULTS)
    cfg.update(config or {})
    t0 = time.perf_counter()
    deviations, acceptance = [], []
    for k in DEFAULTS:
        if cfg[k] != DEFAULTS[k]:
            deviations.append("config %s=%r differs from predeclared default %r" % (k, cfg[k], DEFAULTS[k]))
    result = {"task": TASK, "status": "computed_synthetic_sensitivity_study", "physical_validation": False,
              "study_comparator_only": {"surface_C": 40, "internal_C": 60},
              "config": cfg, "sampling_convention": "uniform measure on declared study domains; not a belief distribution; no confidence intervals",
              "credits": "Coda (Codex Lily) with Andrei: steady reference and T0-LUMP2-1 transient (read-only inputs). "
                         "Claude (Anthropic): this analysis. Red: coordination and execution."}
    result["input_hashes"] = check_input_hashes(deviations)
    result["reference_check"] = reference_section(acceptance)
    result["closed_form_nominal"], result["partials_nominal"] = nominal_tables(acceptance)
    result["analytic_condition"] = analytic_condition()
    result["method_self_checks"] = method_self_checks(acceptance)
    if cfg["skip_grid"]:
        deviations.append("grid classification skipped")
    else:
        result["grid_classification"] = grid_section(cfg, acceptance)
    result["steady_screening"] = steady_section(cfg, acceptance)
    if cfg["skip_transient"]:
        deviations.append("transient section skipped")
    else:
        result["transient"] = transient_section(cfg, acceptance, deviations)
    result["acceptance"] = acceptance
    result["deviations"] = deviations
    result["claim_boundary"] = ("Synthetic two-node steady and lumped transient models with fixed nominal properties "
                                "and assumed convection; no spatial mesh, delamination, radiation, controller, contact "
                                "safety, biological viability or deployment claim; PF0 6/7 history unchanged.")
    result["timing_s"] = time.perf_counter() - t0
    return result


def summary(result):
    out = {"acceptance": {a["id"]: a["passed"] for a in result["acceptance"]},
           "deviations": result["deviations"], "timing_s": result.get("timing_s")}
    if "grid_classification" in result:
        out["predictions"] = {k: v["passed"] for k, v in result["grid_classification"]["predictions"].items()
                              if isinstance(v, dict)}
        out["flipped_counts"] = {"%s|P%d|%s" % (g["mode"], g["P"], "blocked" if g["rear_blocked"] else "finite"):
                                 g["counts_H1_vs_H3"].get("flipped", 0) for g in result["grid_classification"]["grids"]}
    key = "common_bias|P5"
    if key in result["steady_screening"]:
        out["steady_top_factor_by_mu_star"] = {
            name: rank[0]["factor"] for name, rank in result["steady_screening"][key]["morris"]["ranking_by_mu_star"].items()}
    tr = result.get("transient", {})
    if tr.get("available"):
        k2 = "common_bias|P%d|rear_loss_sensor_on" % result["config"]["transient_P"]
        out["transient_top_factor_by_mu_star"] = {
            name: rank[0]["factor"] for name, rank in tr["screening"][k2]["morris"]["ranking_by_mu_star"].items()}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default=None, help="JSON output path (only file written)")
    ap.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    ap.add_argument("--morris-r", type=int, default=DEFAULTS["morris_r"])
    ap.add_argument("--sobol-n", type=int, default=DEFAULTS["sobol_n"])
    ap.add_argument("--transient-morris-r", type=int, default=DEFAULTS["transient_morris_r"])
    ap.add_argument("--transient-n", type=int, default=DEFAULTS["transient_sobol_n"])
    ap.add_argument("--grid-stride", type=int, default=DEFAULTS["grid_stride"])
    ap.add_argument("--skip-transient", action="store_true")
    ap.add_argument("--skip-grid", action="store_true")
    args = ap.parse_args(argv)
    cfg = {"seed": args.seed, "morris_r": args.morris_r, "sobol_n": args.sobol_n,
           "transient_morris_r": args.transient_morris_r, "transient_sobol_n": args.transient_n,
           "grid_stride": args.grid_stride, "skip_transient": args.skip_transient, "skip_grid": args.skip_grid}
    result = run(cfg)
    if args.output:
        path = Path(args.output)
        if path.exists():
            raise SystemExit("Refusing to overwrite existing output " + str(path))
        path.write_text(json.dumps(jsonable(result), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(jsonable(summary(result)), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
