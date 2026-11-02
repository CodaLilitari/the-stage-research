#!/usr/bin/env python3
"""nversion_crosscheck.py -- predeclared N-version cross-check for the T0-HYP-1 panel models.

Task thermal-nversion-crosscheck-004 (The Stage; Red coordinating with Richard (Andrei) Pemberton).
Code written as text by Red's Claude contributor; results exist only when Red executes it.

Inputs (paths as CLI arguments; key structure taken from the compact copies in the task bundle):
  --fv      T0-FV1D-1 suite JSON                 (Claude, waves 7+10)
  --oracle  layered eigen-oracle results JSON     (Claude, wave 10; two structural tests still failing)
  --rad     RAD-STUDY-1 results JSON              (Claude; eps = 0 rows re-implement Coda's T0-LUMP2-1)
  --steady  Coda's rational steady reference JSON (validation/thermal/reference_results.json)
  --lump2   optional: Coda's study_results.json (schema not visible to the author: keys are listed,
            nothing is compared from it; the REPORT.md table embedded below is used instead)
  --out     optional output JSON path (the only file this script writes)

Standard library only. Deterministic. No network. Exit code 0 always (the report is the result).
Agreement between models of the same contract validates nothing physical.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

AREA_M2 = 0.01
T_AMB_C = 25.0
T_RES_C = 25.0
R_REJ_K_W = 2.0
NOMINAL_H = 8.0
NOMINAL_RC = 2.0e-4
CASE_TO_RAD = {"F0": "intact", "F1": "rear_loss"}
RAD_TO_CASE = {v: k for k, v in CASE_TO_RAD.items()}
VARS = ("surface", "sensor", "H", "front", "rear")
TEMP_VARS = ("surface", "sensor", "H")

# ------------------------------------------------------------------ predeclared tolerances (section b)
DECLARED: Dict[str, Any] = {
    "T1_steady_K": 1e-9,
    "T1_steady_W": 1e-9,
    "T2_lump2_reproduction_K": 2e-6,
    "T2_lump2_reproduction_time_s": 1e-9,
    "T2b_transcription_K": 1e-9,
    "T3_richardson_safety": 1.5,
    "T3_time_factor": 2.0,          # backward Euler, first order: e(dt) ~ 2 * D(dt, dt/2)
    "T3_space_factor": 4.0 / 3.0,   # cell-centred FV, second order: e(h) ~ (4/3) * D(h, h/2)
    "T3_oracle_floor_K": 1e-3,
    "T3_oracle_defect_multiplier": 20.0,
    "T3_fallback_time_pair_K": 0.05,
    "T3_fallback_mesh_pair_K": 0.1,
    "T3_energy_3600_J": 8.0,
    "T4_value_K": {"peak_H": 2.0, "peak_surface": 2.0, "peak_sensor": 2.0, "H_at_3600": 1.0, "trajectory": 2.0},
    "T4_peak_H_time_s": 1.0,
    "T4_peak_surface_time_floor_s": 1.5,
    "T4_peak_surface_time_factor": 1.0,   # times L_outer^2 / alpha_silicone
    "flux_excluded_at_event_times_s": [600.0, 900.0],
    "fv_steady_match_assumed_body_power_W": 5.0,
    "policy": "tolerances fixed in this file before any comparison; failures are reported, never loosened",
}
EVENT_TIMES = tuple(DECLARED["flux_excluded_at_event_times_s"])

# Coda's T0-LUMP2-1 table, transcribed from validation/thermal_transient/REPORT.md
# (sha256 86f9b6107dc2e62b9e497454924c3463230bc96ba9495ab0bdc2baa24d6b25a6). 6-decimal values.
# dt = 1 s is an assumption carried over from RAD criterion C6 (coda_report_dt_assumed_s).
CODA_REPORT_TABLE: Dict[Tuple[str, str], Dict[str, float]] = {
    ("H1", "F0"): dict(peak_H_C=33.831193, peak_H_time_s=900.0, peak_surface_C=33.554994, peak_surface_time_s=900.0, H_3600_C=25.170303),
    ("H1", "F1"): dict(peak_H_C=61.143480, peak_H_time_s=900.0, peak_surface_C=59.747155, peak_surface_time_s=901.0, H_3600_C=26.374204),
    ("H1", "F1_sensor_off"): dict(peak_H_C=60.446481, peak_H_time_s=900.0, peak_surface_C=59.055570, peak_surface_time_s=901.0, H_3600_C=25.104135),
    ("H2", "F0"): dict(peak_H_C=33.861287, peak_H_time_s=900.0, peak_surface_C=33.362444, peak_surface_time_s=900.0, H_3600_C=25.168602),
    ("H2", "F1"): dict(peak_H_C=55.545063, peak_H_time_s=900.0, peak_surface_C=53.153638, peak_surface_time_s=904.0, H_3600_C=26.798252),
    ("H2", "F1_sensor_off"): dict(peak_H_C=54.963957, peak_H_time_s=900.0, peak_surface_C=52.578375, peak_surface_time_s=904.0, H_3600_C=25.520601),
    ("H3", "F0"): dict(peak_H_C=33.884652, peak_H_time_s=900.0, peak_surface_C=32.963939, peak_surface_time_s=900.0, H_3600_C=25.165436),
    ("H3", "F1"): dict(peak_H_C=50.169875, peak_H_time_s=900.0, peak_surface_C=45.881263, peak_surface_time_s=914.0, H_3600_C=28.187988),
    ("H3", "F1_sensor_off"): dict(peak_H_C=49.704285, peak_H_time_s=900.0, peak_surface_C=45.421846, peak_surface_time_s=913.0, H_3600_C=26.934740),
}

INVENTORY = [
    "T1 steady: REF rows vs analytic; RAD eps=0 steady/blocked rows vs analytic (all h, P) and vs REF (h=8);",
    "   FV steady_match details (P=5 assumed) vs REF; FV long_time_target (sensor-only) vs analytic.",
    "T2 reproduction: RAD eps=0 transient peaks/H(3600) vs Coda LUMP2 table; FV-embedded lump2 rows vs the table.",
    "T3 same continuum model: FV samples/checkpoints vs oracle rows at common times (temps + fluxes,",
    "   fluxes skipped at 600/900 s); energy split at 3600 s; oracle row-maxima vs FV peaks (info only).",
    "T4 structure: Coda table and RAD eps=0 peaks/times/H(3600) vs FV; RAD eps=0 traces vs FV and vs oracle.",
    "Single-version (not cross-checkable): FV F3/F4T/F4F/F5 and perturbation runs; LUMP2 sensor-off rows;",
    "   RAD eps>0 rows; RAD blocked rows at h!=8 (analytic only); oracle 1 s / 10 s rows; oracle mode diagnostics.",
]


# ------------------------------------------------------------------ small helpers
def fnum(x: Any) -> Optional[float]:
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def tkey(t: Any) -> Optional[float]:
    f = fnum(t)
    return None if f is None else round(f, 6)


def dig(d: Any, *keys: Any) -> Optional[float]:
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list) and isinstance(k, int) and 0 <= k < len(cur):
            cur = cur[k]
        else:
            return None
    return fnum(cur)


def is_blocked(r_rej: Any) -> bool:
    if r_rej is None:
        return True
    if isinstance(r_rej, str):
        return r_rej.strip().lower() in ("inf", "infinity", "blocked", "none")
    f = fnum(r_rej)
    return f is None or math.isinf(f) or f <= 0.0


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ analytic steady (contract two-node reduction)
def analytic_steady(a: float, r_sa: float, r_conv: float, r_rej: Optional[float],
                    p_body: float, p_sensor: float, rear_blocked: bool) -> Dict[str, float]:
    """Exact steady state of the T0-HYP-1 network. a = R_HS; r_sa = R_SA (includes r_conv).
    Node H: (H-S)/a + (H-T_res)/R_rej = P_body ; node S: (H-S)/a + P_sensor = (S-T_amb)/R_SA."""
    if rear_blocked or r_rej is None or math.isinf(r_rej):
        y = (p_body + p_sensor) * r_sa
        x = y + p_body * a
        h_t, s_t, front, rear = T_AMB_C + x, T_AMB_C + y, y / r_sa, 0.0
    else:
        a11, a12, b1 = 1.0 / a + 1.0 / r_rej, -1.0 / a, p_body + T_RES_C / r_rej
        a21, a22, b2 = 1.0 / a, -(1.0 / a + 1.0 / r_sa), -p_sensor - T_AMB_C / r_sa
        det = -(1.0 / (a * r_sa) + 1.0 / (a * r_rej) + 1.0 / (r_rej * r_sa))  # = a11*a22 - a12*a21
        h_t = (b1 * a22 - a12 * b2) / det
        s_t = (a11 * b2 - a21 * b1) / det
        front, rear = (s_t - T_AMB_C) / r_sa, (h_t - T_RES_C) / r_rej
    return {"H": h_t, "S": s_t, "surface": T_AMB_C + front * r_conv, "front": front, "rear": rear}


# ------------------------------------------------------------------ indexers
def stack_network(steady: Dict) -> Dict[str, Dict[str, float]]:
    net: Dict[str, Dict[str, float]] = {}
    for row in steady.get("rows", []):
        s = row.get("stack")
        if s and s not in net and fnum(row.get("a")) is not None and fnum(row.get("b")) is not None:
            net[s] = {"a": fnum(row["a"]), "b": fnum(row["b"]),
                      "r_conv": fnum(row.get("convection_resistance")) or 1.0 / (NOMINAL_H * AREA_M2)}
    return net


def ref_rows(steady: Dict) -> Dict[Tuple[str, float, bool], Dict]:
    return {(r.get("stack"), fnum(r.get("body_power")), bool(r.get("rear_blocked"))): r for r in steady.get("rows", [])}


def fv_nominal(fv: Dict) -> Dict[Tuple[str, str], Dict]:
    out = {}
    for run in fv.get("runs", []):
        if run.get("perturbation") in ({}, None):
            out[(run.get("stack"), run.get("case"))] = run
    return out


def fv_refinement(fv: Dict) -> Tuple[Dict, Dict]:
    ver = fv.get("verification", {})
    dts: Dict[Tuple[str, str], Dict[str, Optional[float]]] = {}
    meshes: Dict[Tuple[str, str], Dict[str, float]] = {}
    for d in ver.get("time_refinement", {}).get("details", []):
        pair = d.get("pairs_K", {}).get("0.5_vs_0.25", {})
        dts[(d.get("stack"), d.get("case"))] = {"surface": fnum(pair.get("surface_actual_C")),
                                                "sensor": fnum(pair.get("sensor_actual_C")), "H": fnum(pair.get("H_C"))}
    for d in ver.get("mesh_refinement", {}).get("details", []):
        acc = meshes.setdefault((d.get("stack"), d.get("case")), {"surface": 0.0, "sensor": 0.0, "H": 0.0})
        md = d.get("max_difference_K", {})
        for var, src in (("surface", "surface_actual_C"), ("sensor", "sensor_actual_C"), ("H", "H_C")):
            v = fnum(md.get(src))
            if v is not None:
                acc[var] += abs(v)
    return dts, meshes


def oracle_cases(oracle: Dict) -> Dict[Tuple[str, str], Dict]:
    return {(c.get("stack"), c.get("scenario")): c for c in oracle.get("cases", [])}


def oracle_allowance(oracle: Dict) -> float:
    mx = 0.0
    for c in oracle.get("cases", []):
        for seg in c.get("segments", []):
            v = fnum(seg.get("projection_defect"))
            if v is not None:
                mx = max(mx, abs(v))
            for tv in (seg.get("tail_estimate_K_at_dt_1s") or {}).values():
                f = fnum(tv)
                if f is not None:
                    mx = max(mx, abs(f))
    return max(DECLARED["T3_oracle_floor_K"], DECLARED["T3_oracle_defect_multiplier"] * mx)


def rad_eps0(rad: Dict) -> Dict[Tuple[str, str], Dict]:
    out = {}
    for run in rad.get("transient_runs", []):
        if fnum(run.get("eps")) == 0.0 and fnum(run.get("h_W_m2K")) == NOMINAL_H:
            case = RAD_TO_CASE.get(run.get("case"))
            if case:
                out[(run.get("stack"), case)] = run
    return out


# ------------------------------------------------------------------ traces
FV_KEYS = {"surface": "surface_actual_C", "sensor": "sensor_actual_C", "H": "H_C", "front": "front_flux_W", "rear": "rear_flux_W"}
OR_KEYS = {"surface": "surface_C", "sensor": "sensor_C", "H": "H_C", "front": "front_W", "rear": "rear_W"}
RAD_KEYS = {"surface": "O_C", "sensor": "S_C", "H": "H_C", "front": "front_W", "rear": "rear_W"}


def build_trace(rows: List[Dict], keys: Dict[str, str], time_key: str) -> Dict[float, Dict[str, Optional[float]]]:
    out: Dict[float, Dict[str, Optional[float]]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        t = tkey(r.get(time_key))
        if t is None:
            continue
        out[t] = {k: fnum(r.get(src)) for k, src in keys.items()}
    return out


def fv_trace(run: Dict) -> Dict[float, Dict[str, Optional[float]]]:
    rows = list(run.get("samples_60s", [])) + list((run.get("checkpoints") or {}).values())
    return build_trace(rows, FV_KEYS, "time_s")


def oracle_trace(case: Dict) -> Dict[float, Dict[str, Optional[float]]]:
    return build_trace(case.get("rows", []), OR_KEYS, "t_s")


def rad_trace(run: Dict) -> Dict[float, Dict[str, Optional[float]]]:
    rows = list(run.get("samples_60s", [])) + list((run.get("checkpoints") or {}).values())
    if isinstance(run.get("final"), dict):
        rows.append(run["final"])
    return build_trace(rows, RAD_KEYS, "time_s")


# ------------------------------------------------------------------ tolerance builders
def t3_budget(stack: str, case: str, var: str, dts: Dict, meshes: Dict, allowance: float) -> Tuple[float, str]:
    cases = [case] if case in ("F1", "F2") else ["F1", "F2"]
    dvals = [dts[(stack, c)][var] for c in cases if (stack, c) in dts and dts[(stack, c)].get(var) is not None]
    xvals = [meshes[(stack, c)][var] for c in cases if (stack, c) in meshes]
    src = []
    if dvals:
        d_t, _ = max(dvals), src.append("dt:richardson")
    else:
        d_t, _ = DECLARED["T3_fallback_time_pair_K"], src.append("dt:fallback")
    if xvals:
        d_x, _ = max(xvals), src.append("dx:richardson")
    else:
        d_x, _ = DECLARED["T3_fallback_mesh_pair_K"], src.append("dx:fallback")
    tol = DECLARED["T3_richardson_safety"] * (DECLARED["T3_time_factor"] * d_t + DECLARED["T3_space_factor"] * d_x) + allowance
    return tol, ",".join(src) + f";Dt={d_t:.3g};Dx={d_x:.3g};orc={allowance:.3g}"


def fv_r_conv(run: Dict) -> float:
    r = dig(run, "parameters", "mesh", "front_convection_resistance_K_per_W")
    if r is None:
        h = dig(run, "parameters", "boundary_initial", "h") or NOMINAL_H
        a = dig(run, "parameters", "stack", "area") or AREA_M2
        r = 1.0 / (h * a)
    return r


def peak_surface_time_tol(run: Dict) -> Tuple[float, str]:
    k = dig(run, "parameters", "materials", "k_silicone")
    rho = dig(run, "parameters", "materials", "rho_silicone")
    cp = dig(run, "parameters", "materials", "cp_silicone")
    length = dig(run, "parameters", "stack", "t_silicone_outer")
    floor = DECLARED["T4_peak_surface_time_floor_s"]
    if None in (k, rho, cp, length) or k <= 0 or rho <= 0 or cp <= 0:
        return floor, "floor(parameters missing)"
    tau = length * length / (k / (rho * cp))
    return max(floor, DECLARED["T4_peak_surface_time_factor"] * tau), f"L_outer^2/alpha={tau:.2f}s"


def structural_scale_note(run: Dict) -> str:
    try:
        p = run["parameters"]
        st, mat, bi = p["stack"], p["materials"], p["boundary_initial"]
        area = fnum(st.get("area")) or AREA_M2
        r_cover = ((fnum(st["t_silicone_outer"]) + fnum(st["t_silicone_inner"])) / (fnum(mat["k_silicone"]) * area)
                   + fnum(st["t_film"]) / (fnum(mat["k_film"]) * area)
                   + (fnum(bi["r_c_outer"]) + fnum(bi["r_c_inner"])) / area)
        q = (dig(run, "peaks", "surface_actual", "value_C") - T_AMB_C) / fv_r_conv(run)
        return f"structural scale q_front_peak*R_cover={q * r_cover:.2f}K"
    except (KeyError, TypeError, ZeroDivisionError):
        return ""


# ------------------------------------------------------------------ ledger
class Ledger:
    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def add(self, tier: str, check: str, pair: str, stack: str, case: str, quantity: str, t_s: Optional[float],
            va: Optional[float], vb: Optional[float], tol: Optional[float], note: str = "", by_case: bool = True) -> None:
        diff = None if (va is None or vb is None) else abs(va - vb)
        passed = None if (diff is None or tol is None) else (diff <= tol)
        if (va is None or vb is None) and tol is not None:
            note = (note + ";" if note else "") + "missing value"
        group = (tier, check, pair, stack if by_case else "*", case if by_case else "*", quantity)
        self.records.append({"tier": tier, "check": check, "pair": pair, "stack": stack, "case": case, "quantity": quantity,
                             "t_s": t_s, "value_a": va, "value_b": vb, "abs_diff": diff, "tol": tol, "passed": passed,
                             "note": note, "group": group})


def compare_traces(L: Ledger, tier: str, check: str, pair: str, stack: str, case: str,
                   tr_a: Dict, tr_b: Dict, tol_fn) -> int:
    n = 0
    for t in sorted(set(tr_a) & set(tr_b)):
        for var in VARS:
            if var in ("front", "rear") and t in EVENT_TIMES:
                continue
            va, vb = tr_a[t].get(var), tr_b[t].get(var)
            if va is None or vb is None:
                continue
            tol, note = tol_fn(var)
            L.add(tier, check, pair, stack, case, var, t, va, vb, tol, note)
            n += 1
    return n


# ------------------------------------------------------------------ tiers
def q_tol(q: str) -> float:
    return DECLARED["T1_steady_W"] if q in ("front", "rear") else DECLARED["T1_steady_K"]


def compare_T1(L: Ledger, steady: Dict, rad: Dict, fv: Dict) -> None:
    net, refs = stack_network(steady), ref_rows(steady)
    for (stack, p, blocked), row in refs.items():
        n = net.get(stack)
        if n is None or p is None:
            continue
        an = analytic_steady(n["a"], n["b"], n["r_conv"], R_REJ_K_W, p, fnum(row.get("sensor_power")) or 0.1, blocked)
        for q in ("H", "S", "surface", "front", "rear"):
            L.add("T1", "reference_vs_analytic", "coda_reference|analytic", stack, f"P={p:g},blocked={blocked}", q, None,
                  fnum(row.get(q)), an[q], q_tol(q), by_case=False)
    rad_keys = (("H", "T_H_C"), ("S", "T_S_C"), ("surface", "T_O_C"), ("front", "q_front_W"), ("rear", "q_rear_W"))
    for row in list(rad.get("steady_rows", [])) + list(rad.get("blocked_rear_rows", [])):
        if fnum(row.get("eps")) != 0.0:
            continue
        stack, h, p = row.get("stack"), fnum(row.get("h_W_m2K")), fnum(row.get("body_power_W"))
        n = net.get(stack)
        if n is None or not h or p is None:
            continue
        blocked = bool(row.get("rear_blocked")) or is_blocked(row.get("R_rej_K_W"))
        r_conv = 1.0 / (h * AREA_M2)
        r_rej = None if blocked else (fnum(row.get("R_rej_K_W")) or R_REJ_K_W)
        an = analytic_steady(n["a"], n["b"] - n["r_conv"] + r_conv, r_conv, r_rej, p, fnum(row.get("sensor_power_W")) or 0.1, blocked)
        label = f"P={p:g},h={h:g},blocked={blocked}"
        ref = refs.get((stack, p, blocked)) if h == NOMINAL_H else None
        for q, key in rad_keys:
            L.add("T1", "rad_eps0_steady_vs_analytic", "rad_eps0|analytic", stack, label, q, None, fnum(row.get(key)), an[q], q_tol(q), by_case=False)
            if ref is not None:
                L.add("T1", "rad_eps0_steady_vs_reference", "rad_eps0|coda_reference", stack, label, q, None,
                      fnum(row.get(key)), fnum(ref.get(q)), q_tol(q), by_case=False)
    p_assumed = DECLARED["fv_steady_match_assumed_body_power_W"]
    for d in fv.get("verification", {}).get("steady_match", {}).get("details", []):
        if "rear_blocked" not in d or not isinstance(d.get("fv"), dict):
            continue
        ref = refs.get((d.get("stack"), p_assumed, bool(d["rear_blocked"])))
        if ref is None:
            continue
        for q, key in (("H", "H_C"), ("S", "sensor_C"), ("surface", "surface_C"), ("front", "front_W"), ("rear", "rear_W")):
            L.add("T1", "fv_steady_match_vs_reference", "fv_steady|coda_reference", d.get("stack"),
                  f"mesh={d.get('mesh')},blocked={bool(d['rear_blocked'])}", q, None, fnum(d["fv"].get(key)), fnum(ref.get(q)),
                  q_tol(q), f"P_body={p_assumed:g} assumed", by_case=False)
    for (stack, case), run in fv_nominal(fv).items():
        tgt, n = run.get("long_time_target_if_final_conditions_held"), net.get(stack)
        bf = run.get("parameters", {}).get("boundary_final", {})
        if not isinstance(tgt, dict) or n is None or tgt.get("status") not in (None, "unique"):
            continue
        h = fnum(bf.get("h"))
        if not h:
            continue  # F5: adiabatic front, no finite powered steady state
        rc_i, rc_o = fnum(bf.get("r_c_inner")) or NOMINAL_RC, fnum(bf.get("r_c_outer")) or NOMINAL_RC
        blocked = is_blocked(bf.get("r_rej"))
        r_conv = 1.0 / (h * (fnum(dig(run, "parameters", "stack", "area")) or AREA_M2))
        an = analytic_steady(n["a"] + (rc_i - NOMINAL_RC) / AREA_M2, n["b"] - n["r_conv"] + r_conv + (rc_o - NOMINAL_RC) / AREA_M2,
                             r_conv, None if blocked else (fnum(bf.get("r_rej")) or R_REJ_K_W),
                             dig(run, "final_state", "body_power_W") or 0.0, dig(run, "final_state", "sensor_power_W") or 0.1, blocked)
        for q, key in (("H", "H_C"), ("S", "sensor_C"), ("surface", "surface_C"), ("front", "front_W"), ("rear", "rear_W")):
            L.add("T1", "fv_long_time_target_vs_analytic", "fv_target|analytic", stack, case, q, None, fnum(tgt.get(key)), an[q], q_tol(q))


def compare_T2(L: Ledger, rad: Dict, fv: Dict) -> None:
    tk, tt = DECLARED["T2_lump2_reproduction_K"], DECLARED["T2_lump2_reproduction_time_s"]
    for (stack, case), run in rad_eps0(rad).items():
        fx = CODA_REPORT_TABLE.get((stack, case))
        if not fx:
            continue
        pr = "rad_eps0|coda_report"
        L.add("T2", "rad_eps0_reproduces_lump2", pr, stack, case, "peak_H_C", None, dig(run, "peaks", "peak_H", "C"), fx["peak_H_C"], tk)
        L.add("T2", "rad_eps0_reproduces_lump2", pr, stack, case, "peak_H_time_s", None, dig(run, "peaks", "peak_H", "time_s"), fx["peak_H_time_s"], tt)
        L.add("T2", "rad_eps0_reproduces_lump2", pr, stack, case, "peak_surface_C", None, dig(run, "peaks", "peak_surface", "C"), fx["peak_surface_C"], tk)
        L.add("T2", "rad_eps0_reproduces_lump2", pr, stack, case, "peak_surface_time_s", None, dig(run, "peaks", "peak_surface", "time_s"), fx["peak_surface_time_s"], tt)
        L.add("T2", "rad_eps0_reproduces_lump2", pr, stack, case, "H_at_3600_C", 3600.0, dig(run, "final", "H_C"), fx["H_3600_C"], tk)
    for row in fv.get("cross_check_against_lump2", {}).get("rows", []):
        fx, l2 = CODA_REPORT_TABLE.get((row.get("stack"), row.get("case"))), row.get("lump2") or {}
        if not fx:
            continue
        for key in ("peak_H_C", "peak_H_time_s", "peak_surface_C", "peak_surface_time_s", "H_3600_C"):
            L.add("T2", "fv_embedded_lump2_transcription", "fv_embedded|coda_report", row.get("stack"), row.get("case"), key, None,
                  fnum(l2.get(key)), fx[key], DECLARED["T2b_transcription_K"])


def compare_T3(L: Ledger, fv: Dict, oracle: Dict) -> None:
    runs, orc = fv_nominal(fv), oracle_cases(oracle)
    dts, meshes = fv_refinement(fv)
    allowance = oracle_allowance(oracle)
    for (stack, case), oc in sorted(orc.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        run = runs.get((stack, case))
        if run is None:
            continue
        budgets = {v: t3_budget(stack, case, v, dts, meshes, allowance) for v in TEMP_VARS}
        r_conv = fv_r_conv(run)

        def tol_fn(var: str, budgets=budgets, r_conv=r_conv) -> Tuple[float, str]:
            if var == "front":
                return budgets["surface"][0] / r_conv, "surface budget / R_conv"
            if var == "rear":
                return budgets["H"][0] / R_REJ_K_W, "H budget / R_rej"
            return budgets[var]

        compare_traces(L, "T3", "fv_vs_oracle_trajectory", "fv|oracle", stack, case, fv_trace(run), oracle_trace(oc), tol_fn)
        aud = [a for a in oc.get("energy_audits", []) if tkey(a.get("t_s")) == 3600.0]
        en = run.get("energy") or {}
        if aud and en:
            for q, fk, ok in (("stored_J", "stored_change_J", "stored_J"), ("front_export_J", "exported_front_to_ambient_J", "front_loss_J"),
                              ("rear_export_J", "exported_rear_to_reservoir_J", "rear_loss_J")):
                L.add("T3", "fv_vs_oracle_energy_3600", "fv|oracle", stack, case, q, 3600.0, fnum(en.get(fk)), fnum(aud[-1].get(ok)),
                      DECLARED["T3_energy_3600_J"], "right-endpoint quadrature bound")
        rows = [r for r in oc.get("rows", []) if fnum(r.get("surface_C")) is not None]
        if rows:
            rs, rh = max(rows, key=lambda r: fnum(r["surface_C"])), max(rows, key=lambda r: fnum(r.get("H_C")) or -1e9)
            L.add("T3", "oracle_rowmax_vs_fv_peak_INFO", "oracle_rowmax|fv", stack, case, "surface_peak_lower_bound_C", tkey(rs.get("t_s")),
                  fnum(rs["surface_C"]), dig(run, "peaks", "surface_actual", "value_C"), None, "info: sparse rows, not judged")
            L.add("T3", "oracle_rowmax_vs_fv_peak_INFO", "oracle_rowmax|fv", stack, case, "H_peak_lower_bound_C", tkey(rh.get("t_s")),
                  fnum(rh.get("H_C")), dig(run, "peaks", "H", "value_C"), None, "info: sparse rows, not judged")


def compare_T4(L: Ledger, fv: Dict, oracle: Dict, rad: Dict) -> None:
    runs, orc, r0 = fv_nominal(fv), oracle_cases(oracle), rad_eps0(rad)
    T4 = DECLARED["T4_value_K"]

    def t4_tol(var: str) -> Tuple[float, str]:
        if var == "front":
            return T4["trajectory"] / 12.5, "2K / R_conv"
        if var == "rear":
            return T4["trajectory"] / R_REJ_K_W, "2K / R_rej"
        return T4["trajectory"], "predeclared structural expectation"

    for (stack, case), run in sorted(runs.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        if case not in ("F0", "F1"):
            continue
        tol_ts, tnote = peak_surface_time_tol(run)
        scale = structural_scale_note(run)
        fx = CODA_REPORT_TABLE.get((stack, case))
        if fx:
            pr = "coda_report|fv"
            L.add("T4", "lump2_table_vs_fv_peaks", pr, stack, case, "peak_H_C", None, fx["peak_H_C"], dig(run, "peaks", "H", "value_C"), T4["peak_H"], scale)
            L.add("T4", "lump2_table_vs_fv_peaks", pr, stack, case, "peak_H_time_s", None, fx["peak_H_time_s"], dig(run, "peaks", "H", "time_s"), DECLARED["T4_peak_H_time_s"])
            L.add("T4", "lump2_table_vs_fv_peaks", pr, stack, case, "peak_surface_C", None, fx["peak_surface_C"], dig(run, "peaks", "surface_actual", "value_C"), T4["peak_surface"], scale)
            L.add("T4", "lump2_table_vs_fv_peaks", pr, stack, case, "peak_surface_time_s", None, fx["peak_surface_time_s"], dig(run, "peaks", "surface_actual", "time_s"), tol_ts, tnote)
            L.add("T4", "lump2_table_vs_fv_peaks", pr, stack, case, "H_at_3600_C", 3600.0, fx["H_3600_C"], dig(run, "final_state", "H_C"), T4["H_at_3600"])
        rr = r0.get((stack, case))
        if rr:
            pr = "rad_eps0|fv"
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_H_C", None, dig(rr, "peaks", "peak_H", "C"), dig(run, "peaks", "H", "value_C"), T4["peak_H"], scale)
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_H_time_s", None, dig(rr, "peaks", "peak_H", "time_s"), dig(run, "peaks", "H", "time_s"), DECLARED["T4_peak_H_time_s"])
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_sensor_C", None, dig(rr, "peaks", "peak_S", "C"), dig(run, "peaks", "sensor_actual", "value_C"), T4["peak_sensor"])
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_sensor_time_s", None, dig(rr, "peaks", "peak_S", "time_s"), dig(run, "peaks", "sensor_actual", "time_s"), tol_ts, tnote)
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_surface_C", None, dig(rr, "peaks", "peak_surface", "C"), dig(run, "peaks", "surface_actual", "value_C"), T4["peak_surface"], scale)
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "peak_surface_time_s", None, dig(rr, "peaks", "peak_surface", "time_s"), dig(run, "peaks", "surface_actual", "time_s"), tol_ts, tnote)
            L.add("T4", "rad_eps0_vs_fv_peaks", pr, stack, case, "H_at_3600_C", 3600.0, dig(rr, "final", "H_C"), dig(run, "final_state", "H_C"), T4["H_at_3600"])
            compare_traces(L, "T4", "rad_eps0_vs_fv_trajectory", pr, stack, case, rad_trace(rr), fv_trace(run), t4_tol)
            oc = orc.get((stack, case))
            if oc:
                compare_traces(L, "T4", "rad_eps0_vs_oracle_trajectory", "rad_eps0|oracle", stack, case, rad_trace(rr), oracle_trace(oc), t4_tol)


# ------------------------------------------------------------------ reporting
def summarize(records: List[Dict]) -> Tuple[List[Dict], Dict[str, Dict[str, int]], List[Dict]]:
    groups: Dict[Tuple, Dict[str, Any]] = {}
    for r in records:
        g = groups.setdefault(r["group"], {"tier": r["tier"], "check": r["check"], "pair": r["pair"], "stack": r["group"][3],
                                           "case": r["group"][4], "quantity": r["quantity"], "n": 0, "max_abs_diff": None,
                                           "t_at_max": None, "value_a_at_max": None, "value_b_at_max": None, "min_tol": None,
                                           "judged": 0, "failed": 0, "notes": set()})
        g["n"] += 1
        if r["note"]:
            g["notes"].add(r["note"])
        if r["abs_diff"] is not None and (g["max_abs_diff"] is None or r["abs_diff"] > g["max_abs_diff"]):
            g["max_abs_diff"], g["t_at_max"] = r["abs_diff"], r["t_s"]
            g["value_a_at_max"], g["value_b_at_max"] = r["value_a"], r["value_b"]
        if r["tol"] is not None and (g["min_tol"] is None or r["tol"] < g["min_tol"]):
            g["min_tol"] = r["tol"]
        if r["passed"] is not None:
            g["judged"] += 1
            g["failed"] += 0 if r["passed"] else 1
        if r["tol"] is not None and (r["value_a"] is None or r["value_b"] is None):
            g["failed"] += 1  # a judged quantity that could not be read counts as a failure of the check
            g["judged"] += 1
    out = []
    for g in groups.values():
        g["notes"] = sorted(g["notes"])[:3]
        g["result"] = "INFO" if g["judged"] == 0 else ("PASS" if g["failed"] == 0 else "FAIL")
        out.append(g)
    out.sort(key=lambda g: (g["tier"], g["check"], g["pair"], g["stack"], g["case"], g["quantity"]))
    tiers: Dict[str, Dict[str, int]] = {}
    for g in out:
        t = tiers.setdefault(g["tier"], {"groups": 0, "judged": 0, "failed": 0})
        t["groups"] += 1
        t["judged"] += g["judged"]
        t["failed"] += g["failed"]
    failures = [r for r in records if r["passed"] is False or (r["tol"] is not None and r["abs_diff"] is None)]
    return out, tiers, failures


def fmt(x: Optional[float], spec: str) -> str:
    return "-" if x is None else format(x, spec)


def render(groups: List[Dict], tiers: Dict, failures: List[Dict], allowance: float) -> str:
    lines = ["N-VERSION CROSS-CHECK T0-HYP-1 (thermal-nversion-crosscheck-004) -- model-vs-model only; validates nothing physical",
             "Declared tolerances (fixed before comparison):", json.dumps(DECLARED, indent=1, sort_keys=True),
             f"oracle allowance used in T3: {allowance:.3g} K", "Inventory (a):", *INVENTORY, "",
             f"{'tier':4} {'check':36} {'pair':28} {'stk':3} {'case':22} {'quantity':26} {'n':>4} {'t@max':>8} "
             f"{'a@max':>14} {'b@max':>14} {'max|diff|':>11} {'tol':>10} {'res':4}"]
    for g in groups:
        lines.append(f"{g['tier']:4} {g['check'][:36]:36} {g['pair'][:28]:28} {str(g['stack'])[:3]:3} {str(g['case'])[:22]:22} "
                     f"{g['quantity'][:26]:26} {g['n']:>4} {fmt(g['t_at_max'], '8.1f'):>8} {fmt(g['value_a_at_max'], '14.7f'):>14} "
                     f"{fmt(g['value_b_at_max'], '14.7f'):>14} {fmt(g['max_abs_diff'], '11.3e'):>11} {fmt(g['min_tol'], '10.3e'):>10} {g['result']:4}")
    lines.append("")
    lines.append("Notes per group (first three distinct):")
    for g in groups:
        if g["notes"]:
            lines.append(f"  {g['tier']} {g['check']} {g['stack']} {g['case']} {g['quantity']}: {' | '.join(g['notes'])}")
    lines.append("")
    lines.append("Tier summary:")
    for t, s in sorted(tiers.items()):
        lines.append(f"  {t}: groups={s['groups']} judged={s['judged']} failed={s['failed']} -> {'PASS' if s['failed'] == 0 else 'FAIL'}")
    lines.append(f"Failures ({len(failures)}; first 60 shown):")
    for r in failures[:60]:
        lines.append(f"  {r['tier']} {r['check']} {r['pair']} {r['stack']} {r['case']} {r['quantity']} t={r['t_s']} "
                     f"a={r['value_a']} b={r['value_b']} diff={r['abs_diff']} tol={r['tol']} {r['note']}")
    overall = "PASS" if all(s["failed"] == 0 for s in tiers.values()) and tiers else "FAIL"
    lines.append(f"OVERALL (judged tiers): {overall}")
    return "\n".join(lines)


def run_crosscheck(fv: Dict, oracle: Dict, rad: Dict, steady: Dict) -> Dict[str, Any]:
    L = Ledger()
    compare_T1(L, steady, rad, fv)
    compare_T2(L, rad, fv)
    compare_T3(L, fv, oracle)
    compare_T4(L, fv, oracle, rad)
    groups, tiers, failures = summarize(L.records)
    return {"records": L.records, "groups": groups, "tiers": tiers, "failures": failures, "oracle_allowance_K": oracle_allowance(oracle)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fv", required=True)
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--rad", required=True)
    ap.add_argument("--steady", required=True)
    ap.add_argument("--lump2", default=None, help="optional Coda study_results.json; keys listed only")
    ap.add_argument("--out", default=None, help="optional JSON output path (only file written)")
    args = ap.parse_args(argv)
    fv, oracle, rad, steady = load_json(args.fv), load_json(args.oracle), load_json(args.rad), load_json(args.steady)
    res = run_crosscheck(fv, oracle, rad, steady)
    print(render(res["groups"], res["tiers"], res["failures"], res["oracle_allowance_K"]))
    if args.lump2:
        l2 = load_json(args.lump2)
        keys = sorted(l2.keys()) if isinstance(l2, dict) else [f"<list len {len(l2)}>"]
        print(f"\n--lump2 file loaded; top-level keys: {keys}\nNo values compared from it (schema not available to the author);"
              " Coda's REPORT.md table is the LUMP2 source used above.")
    if args.out:
        payload = {"task": "thermal-nversion-crosscheck-004", "declared_tolerances": DECLARED,
                   "oracle_allowance_K": res["oracle_allowance_K"], "tiers": res["tiers"],
                   "groups": [{k: (list(v) if isinstance(v, (set, tuple)) else v) for k, v in g.items()} for g in res["groups"]],
                   "records": [{k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in res["records"]],
                   "failures": [{k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in res["failures"]],
                   "meaning": "agreement between models of one synthetic contract; not physical validation"}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
