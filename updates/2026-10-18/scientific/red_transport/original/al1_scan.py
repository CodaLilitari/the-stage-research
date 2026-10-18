#!/usr/bin/env python3
"""al1_scan.py - AL1: can a fixed total perfusate flow be redistributed among heterogeneous
tissue modules (or the modules re-arranged) to raise the worst-region free oxygen, and when do
allocation or carrier capacity stop helping?

The Stage, research/cowork_local. Author: Red (Claude, Anthropic) via Claude Cowork, 2026-10-15.
Computational investigation only: no tissue, clinical or viability validation.

Usage (any working directory; use -B so no bytecode is written anywhere):
  python -B research/cowork_local/al1_scan.py --freeze      writes al1_config.json, al1_inputs.csv, al1_freeze.json
  python -B research/cowork_local/al1_scan.py --run         verifies the freeze, runs, writes al1_results.csv, al1_summary.json
  python -B research/cowork_local/al1_scan.py --smoke DIR   pipeline smoke test on a small grid that is NOT the frozen scan
Nothing is ever overwritten: an existing output aborts the step (make a new version instead).
"""
import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import stage_transport as st  # noqa: E402

CONFIG = {
    "name": "AL1 heterogeneous-demand flow allocation and topology screen",
    "version": 1,
    "author": "Red (Claude, Anthropic) via Claude Cowork; configured model id claude-opus-5-5 (the serving model may differ)",
    "status": "computational investigation only; not a tissue, clinical or viability validation",
    "question": ("With the same total perfusate flow, can redistributing it among heterogeneous tissue modules, "
                 "or re-arranging the modules, raise the worst-region free O2; and when do allocation or carrier "
                 "capacity stop helping?"),
    "model_class": ("Per module, the PF0 constitutive model: steady 1-D one-sided slab, Michaelis-Menten uptake, finite "
                    "wall transfer, no-flux back face, cross-sectionally well-mixed plug-flow lumen, hypothetical linear "
                    "lumen capacity C_total = beta*C_free. Solved in the continuum limit (stage_transport.py: RK4 "
                    "shooting plus the exact separable lumen integral), not on PF0's 24 x 32 grid."),
    "reference_parameters": {
        "q_ref_mol_m3_s": 0.02, "Km_mol_m3": 0.028, "D_tissue_m2_s": 2e-9, "C_in_free_mol_m3": 0.2,
        "reference_line_mol_m3": 0.05, "W_m": 1e-3, "L_m": 1e-3,
        "provenance": ("PF0 values (Bonart et al. 2026 illustrative liver-like case). NOT skin measurements. Km is held "
                       "fixed when demand is scaled. 0.05 mol/m3 is PF0's arbitrary pass line and is used only as a "
                       "reference line, not a survival criterion."),
    },
    "patch": {
        "baseline_modules": 3, "baseline_depth_m": 1e-4, "baseline_demand_multiplier": 0.25,
        "hotspot_modules": 1, "hotspot_demand_ratio_r": [1, 2, 4], "hotspot_depth_m": [1e-4, 2e-4, 3e-4, 4e-4],
        "meaning": ("q_module = multiplier * q_ref. Hotspot multiplier = r * 0.25 (0.25, 0.5 or 1.0). Hypothetical "
                    "heterogeneity spanning 0.25-1x the PF0 reference demand; not calibrated to any tissue."),
    },
    "geometries": {
        "base": "every module = one channel face (W x L) plus a one-sided slab of its depth; 4 channels",
        "two_sided_hotspot": ("hotspot volume supplied from both faces, i.e. two one-sided modules of half depth, each with "
                              "its own channel; baseline modules unchanged; 5 channels"),
    },
    "transfer_conditions": [
        {"label": "P0.05_wall", "P_wall_m_s": 5e-5, "lumen_film": False},
        {"label": "P0.2_wall", "P_wall_m_s": 2e-4, "lumen_film": False},
        {"label": "P0.2_wall+film_h100", "P_wall_m_s": 2e-4, "lumen_film": True,
         "slit_height_m": 1e-4, "Sherwood_dh": 4.86, "D_fluid_m2_s": 2e-9},
    ],
    "film_note": ("k_L = Sh*D_fluid/d_h, d_h = 2h for a wide slit, Sh = 4.86 (fully developed laminar flow, one "
                  "transferring wall, other wall insulated, constant-concentration value); P_eff = 1/(1/P_wall + 1/k_L). "
                  "Fully developed Sh is the conservative (lowest) value; entrance effects raise k_L. Neither PF0 nor "
                  "Bonart et al. 2026 include this lumen-side series resistance."),
    "total_flows_uL_min": [1, 2, 4, 8, 16, 32, 64],
    "capacity_multipliers_beta": [1, 4, 16, 64, 256],
    "arrangements": {
        "parallel_uniform": "fresh inlet to every module; equal flow shares",
        "parallel_demand_prop": "fresh inlet; flow share proportional to nominal zero-order uptake q_i*H_i",
        "parallel_maxmin": "fresh inlet; shares maximise the minimum module oxygen (equalising optimum)",
        "series_limited_first": "all flow through the modules in sequence, ordered by decreasing fixed-lumen drop C_in - ceiling_i",
        "series_limited_last": "reverse of series_limited_first",
        "series_best": "best distinct ordering (exhaustive)",
        "series_worst": "worst distinct ordering (exhaustive)",
    },
    "hydraulics": {
        "channel_height_m": 1e-4, "viscosity_Pa_s": 7e-4,
        "resistance": "R = 12 mu L / (W h^3 (1 - 0.630 h/W)) per module channel; identical channels; interconnects neglected",
        "pressure_rules": "uniform parallel dp = R Q/N; allocated parallel (inline restrictors) dp = R max_i Q_i; series dp = N R Q; power = dp Q",
        "capacity_note": "PF0's capacity law changes neither flow nor viscosity, so the pump terms ignore beta (this favours the carrier)",
        "absolute_values_note": "absolute dp and power depend on the assumed h and mu; the ratios between arrangements do not",
    },
    "numerics": {
        "rk4_steps": 1000, "s_grid_points": 2001, "s_low_relative": 1e-14, "maxmin_bisection_iterations": 100, "equal_power_fixed_point_tolerance": 1e-12,
        "refinement_rk4_steps": 2000, "refinement_s_grid_points": 4001,
        "refinement_subset": "base geometry, P0.05_wall, r in {1,4}, hotspot depth in {100,400} um",
        "random_allocations_per_config": 200, "random_seed": 20261015,
    },
    "analytic_test_patches": {
        "zero_order": {"Km_mol_m3": 2e-7, "s_low_relative": 1e-3, "P_wall_m_s": 2e-4,
                       "modules_depth_m_multiplier": [[5e-5, 1.0], [1e-4, 0.25], [1e-4, 0.5], [1.5e-4, 0.25]],
                       "qbeta_uL_min": [8, 16, 32, 64]},
        "first_order": {"C_in_over_Km": 1e-9,
                        "modules_depth_m_multiplier_P": [[5e-5, 1.0, 5e-5], [1e-4, 0.25, 2e-4], [2e-4, 0.5, 5e-5], [1.5e-4, 0.25, 5e-6]],
                        "qbeta_uL_min": [1, 4, 16, 64]},
    },
    "predeclared_checks": {
        "C1_identical_modules_series_equals_uniform": "|series - uniform parallel| <= 1e-9*C_in for patches whose modules are all identical",
        "C2_zero_order_closed_forms": "max-min tau and series minimum match the zero-order closed forms to 1e-5 relative; series >= max-min",
        "C3_first_order_closed_forms": "max-min tau and series minimum match the first-order closed forms to 1e-5 relative; series >= max-min",
        "C4_maxmin_equalisation": "module minima at the max-min split agree to 1e-8 relative; shares sum to the total to 1e-12 relative",
        "C5_random_allocations_never_beat_maxmin": "200 random splits per (patch, flow) at beta=1 never exceed tau by more than 1e-9 relative",
        "C6_monotone_in_flow_and_beta": "every arrangement's worst minimum is non-decreasing in total flow and in beta (1e-12 absolute)",
        "C7_bounded_by_ceiling": "no arrangement exceeds the patch's minimum ceiling (infinite-flow limit) by more than 1e-12",
        "C8_refinement": "doubling RK4 steps and table points changes worst minima by <= 1e-7*C_in on the refinement subset",
    },
    "predeclared_expectations": {
        "E1": "parallel_maxmin >= parallel_uniform and >= parallel_demand_prop in every configuration (optimality; failure = defect)",
        "E2": "where the patch's minimum ceiling < 0.05, no arrangement at any beta <= 256 reaches 0.05",
        "E3": ("heterogeneous patches: median relative gain of max-min over uniform exceeds 1% where the uniform worst module "
               "is flow-limited (worst < 0.9 x minimum ceiling) and is below 1% where it is near its ceiling (>= 0.9)"),
        "E4": ("series_limited_first >= parallel_maxmin at equal total flow in every configuration (proven here only for the "
               "zero-order and first-order limits; open for Michaelis-Menten kinetics)"),
        "E5": "series_limited_first equals series_best in every configuration (Jackson-rule ordering; proven only in the two limits)",
        "E6": ("where the base geometry's minimum ceiling < 0.05: two-sided hotspot at beta=1 beats the base geometry at beta=256 "
               "(both max-min, same total flow) in every configuration"),
        "E7": "secondary, equal hydraulic power at beta=1: parallel_maxmin >= series_limited_first in most configurations",
    },
    "counterexample_config": {"geometry": "base", "hotspot_demand_ratio_r": 4, "hotspot_depth_m": 2e-4,
                              "transfer": "P0.05_wall", "total_flow_uL_min": 8},
    "figure_panels": {
        "A": {"geometry": "base", "hotspot_demand_ratio_r": 4, "hotspot_depth_m": 1e-4, "transfer": "P0.05_wall", "beta": 1, "x": "total flow"},
        "B": {"geometry": "base vs two_sided_hotspot", "hotspot_demand_ratio_r": 4, "hotspot_depth_m": 2e-4, "transfer": "P0.05_wall",
              "total_flow_uL_min": 8, "x": "beta"},
    },
    "pre_freeze_disclosure": ("Before this freeze the solver was unit-tested on synthetic patches (zero-order, first-order and "
                              "identical-module limits) and the infinite-flow ceilings of candidate modules were computed to "
                              "confirm that the grid spans flow-limited and transverse-limited regimes. No allocation or "
                              "topology outcome on this grid was computed before the freeze."),
    "scope_limits": [
        "Liver-like PF0 reference parameters and hypothetical demand multipliers; not skin or any measured tissue.",
        "Steady state; no axial diffusion in tissue; no lateral coupling between modules; cross-sectionally well-mixed lumen except the optional film term.",
        "Capacity beta is PF0's hypothetical instantaneous linear equilibrium; no carrier chemistry, viscosity, release kinetics or toxicity.",
        "Oxygen only: no glucose, CO2, lactate, pH, heat, immune, sterility, shear or mechanical-deformation model.",
        "Series arrangements pass each module's effluent to the next; waste accumulation and failure propagation are not modelled.",
        "Hydraulic numbers assume identical slit channels and ignore interconnects; absolute values are illustrative only.",
    ],
}

FILES = {"config": "al1_config.json", "inputs": "al1_inputs.csv", "freeze": "al1_freeze.json",
         "results": "al1_results.csv", "summary": "al1_summary.json"}

SMOKE_OVERRIDES = {"hotspot_demand_ratio_r": [3], "hotspot_depth_m": [1.5e-4], "total_flows_uL_min": [3, 10],
                   "capacity_multipliers_beta": [1, 3], "rk4_steps": 400, "s_grid_points": 801,
                   "refinement_rk4_steps": 800, "refinement_s_grid_points": 1601}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, text):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="") as handle:  # 'x' refuses to overwrite
        handle.write(text)


def p_eff(tc):
    if not tc["lumen_film"]:
        return tc["P_wall_m_s"]
    k_l = st.lumen_film_conductance(tc["D_fluid_m2_s"], 2.0 * tc["slit_height_m"], tc["Sherwood_dh"])
    return 1.0 / (1.0 / tc["P_wall_m_s"] + 1.0 / k_l)


def patch_modules(cfg, geometry, r, hh):
    pb = cfg["patch"]
    mods = [(pb["baseline_depth_m"], pb["baseline_demand_multiplier"], "B%d" % (i + 1)) for i in range(pb["baseline_modules"])]
    mu_h = r * pb["baseline_demand_multiplier"]
    if geometry == "base":
        return mods + [(hh, mu_h, "HS")]
    return mods + [(hh / 2.0, mu_h, "HSa"), (hh / 2.0, mu_h, "HSb")]


def design(cfg):
    rows, cid = [], 0
    ref = cfg["reference_parameters"]
    for geometry in ["base", "two_sided_hotspot"]:
        for r in cfg["patch"]["hotspot_demand_ratio_r"]:
            for hh in cfg["patch"]["hotspot_depth_m"]:
                mods = patch_modules(cfg, geometry, r, hh)
                for tc in cfg["transfer_conditions"]:
                    for beta in cfg["capacity_multipliers_beta"]:
                        for flow in cfg["total_flows_uL_min"]:
                            cid += 1
                            rows.append({
                                "config_id": cid, "geometry": geometry, "hotspot_demand_ratio_r": r,
                                "hotspot_depth_um": round(hh * 1e6, 6), "transfer": tc["label"],
                                "P_wall_mm_s": tc["P_wall_m_s"] * 1e3, "lumen_film": tc["lumen_film"],
                                "P_eff_mm_s": p_eff(tc) * 1e3, "beta": beta, "total_flow_uL_min": flow,
                                "n_channels": len(mods),
                                "module_labels": ";".join(m[2] for m in mods),
                                "module_depths_um": ";".join("%g" % (m[0] * 1e6) for m in mods),
                                "module_demand_multipliers": ";".join("%g" % m[1] for m in mods),
                                "module_q_mol_m3_s": ";".join("%g" % (m[1] * ref["q_ref_mol_m3_s"]) for m in mods),
                            })
    return rows


def csv_text(rows):
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def smoke_config():
    cfg = json.loads(json.dumps(CONFIG))
    cfg["patch"]["hotspot_demand_ratio_r"] = SMOKE_OVERRIDES["hotspot_demand_ratio_r"]
    cfg["patch"]["hotspot_depth_m"] = SMOKE_OVERRIDES["hotspot_depth_m"]
    cfg["total_flows_uL_min"] = SMOKE_OVERRIDES["total_flows_uL_min"]
    cfg["capacity_multipliers_beta"] = SMOKE_OVERRIDES["capacity_multipliers_beta"]
    for key in ["rk4_steps", "s_grid_points", "refinement_rk4_steps", "refinement_s_grid_points"]:
        cfg["numerics"][key] = SMOKE_OVERRIDES[key]
    cfg["name"] += " [SMOKE TEST - not the frozen scan]"
    return cfg


# ----------------------------------------------------------------------------- analytic tests
def analytic_tests(cfg):
    ref = cfg["reference_parameters"]
    q_ref, km, d, w, l, cin = (ref["q_ref_mol_m3_s"], ref["Km_mol_m3"], ref["D_tissue_m2_s"], ref["W_m"], ref["L_m"],
                               ref["C_in_free_mol_m3"])
    out = {}
    # zero-order limit
    z = cfg["analytic_test_patches"]["zero_order"]
    mods = z["modules_depth_m_multiplier"]
    tabs = [st.ModuleTable(h, mu * q_ref, z["Km_mol_m3"], d, z["P_wall_m_s"], w, l, cin,
                           s_lo_rel=z["s_low_relative"]) for h, mu in mods]
    qb = np.array(z["qbeta_uL_min"], dtype=float) * st.UL_MIN
    tau, _ = st.parallel_maxmin(tabs, qb)
    u0 = np.array([mu * q_ref * w * l * h for h, mu in mods])
    dl = np.array([mu * q_ref * (h / z["P_wall_m_s"] + h * h / (2 * d)) for h, mu in mods])

    def tau_zero(v):
        lo, hi = -1.0, cin - dl.max()
        for _ in range(300):
            m = 0.5 * (lo + hi)
            if (u0 / (cin - dl - m)).sum() > v:
                hi = m
            else:
                lo = m
        return lo
    tau_a = np.array([tau_zero(v) for v in qb])
    order = list(np.argsort(-dl, kind="stable"))
    ser = st.series_chain([tabs[i] for i in order], qb)[0].min(axis=0)
    ser_a = np.array([cin - np.max(np.cumsum(u0[order]) / v + dl[order]) for v in qb])
    out["zero_order"] = {"maxmin_max_rel_error": float(np.max(np.abs(tau - tau_a) / tau_a)),
                         "series_max_rel_error": float(np.max(np.abs(ser - ser_a) / ser_a)),
                         "series_ge_maxmin": bool(np.all(ser >= tau * (1 - 1e-12))),
                         "tau_numeric": tau.tolist(), "tau_closed_form": tau_a.tolist(),
                         "series_numeric": ser.tolist(), "series_closed_form": ser_a.tolist()}
    # first-order limit
    f = cfg["analytic_test_patches"]["first_order"]
    cin1 = km * f["C_in_over_Km"]
    mods = f["modules_depth_m_multiplier_P"]
    tabs = [st.ModuleTable(h, mu * q_ref, km, d, p, w, l, cin1) for h, mu, p in mods]
    qb = np.array(f["qbeta_uL_min"], dtype=float) * st.UL_MIN
    tau, _ = st.parallel_maxmin(tabs, qb)
    ks, aa = [], []
    for h, mu, p in mods:
        _, _, k, a, phi = st.linear_module_closed_form(h, mu * q_ref / km, d, p, w, l, cin1, 1.0)
        ks.append(k)
        aa.append((1 + a / p) * np.cosh(phi))
    ks, aa = np.array(ks), np.array(aa)

    def tau_first(v):
        lo, hi = np.log(cin1 / aa.min()) - 800.0, np.log(cin1 / aa.max())
        for _ in range(400):
            m = 0.5 * (lo + hi)
            if (ks * w * l / (np.log(cin1 / aa) - m)).sum() > v:
                hi = m
            else:
                lo = m
        return np.exp(lo)
    tau_a = np.array([tau_first(v) for v in qb])
    order = list(np.argsort(-aa, kind="stable"))
    ser = st.series_chain([tabs[i] for i in order], qb)[0].min(axis=0)
    ser_a = np.array([(cin1 * np.exp(-np.cumsum(ks[order]) * w * l / v) / aa[order]).min() for v in qb])
    out["first_order"] = {"maxmin_max_rel_error": float(np.max(np.abs(tau - tau_a) / tau_a)),
                          "series_max_rel_error": float(np.max(np.abs(ser - ser_a) / ser_a)),
                          "series_ge_maxmin": bool(np.all(ser >= tau * (1 - 1e-12))),
                          "series_over_maxmin": (ser / tau).tolist()}
    return out


# ----------------------------------------------------------------------------- main scan
def run_scan(cfg, outdir, smoke=False):
    started = now()
    t0 = time.perf_counter()
    ref = cfg["reference_parameters"]
    q_ref, km, d, w, l, cin, cref = (ref["q_ref_mol_m3_s"], ref["Km_mol_m3"], ref["D_tissue_m2_s"], ref["W_m"],
                                     ref["L_m"], ref["C_in_free_mol_m3"], ref["reference_line_mol_m3"])
    num = cfg["numerics"]
    hyd = cfg["hydraulics"]
    r_ch = st.slit_resistance(hyd["viscosity_Pa_s"], l, w, hyd["channel_height_m"])
    betas = np.array(cfg["capacity_multipliers_beta"], dtype=float)
    flows = np.array(cfg["total_flows_uL_min"], dtype=float)
    bb, ff = np.meshgrid(betas, flows, indexing="ij")
    beta_v, flow_v = bb.ravel(), ff.ravel()
    q_tot = flow_v * st.UL_MIN
    qbt = q_tot * beta_v
    i_beta1 = np.where(beta_v == 1.0)[0]

    cache = {}

    def table(h, mu, tc_label, p, nx, ns):
        key = (round(h * 1e12), round(mu * 1e9), tc_label, nx, ns)
        if key not in cache:
            cache[key] = st.ModuleTable(h, mu * q_ref, km, d, p, w, l, cin, n_s=ns, n_x=nx,
                                        s_lo_rel=num["s_low_relative"])
        return cache[key]

    rng = np.random.default_rng(num["random_seed"])
    rows = []
    checks = {k: True for k in cfg["predeclared_checks"]}
    detail = {"C1_max_dev": 0.0, "C4_max_spread": 0.0, "C4_max_sum_err": 0.0, "C5_max_excess": -np.inf,
              "C6_worst_violation": 0.0, "C7_worst_excess": -np.inf, "C8_max_change": 0.0,
              "eq_power_max_fixed_point_residual": 0.0}
    patch_store = {}

    for geometry in ["base", "two_sided_hotspot"]:
        for r in cfg["patch"]["hotspot_demand_ratio_r"]:
            for hh in cfg["patch"]["hotspot_depth_m"]:
                mods = patch_modules(cfg, geometry, r, hh)
                n = len(mods)
                keys = [(round(m[0] * 1e12), round(m[1] * 1e9)) for m in mods]
                identical = len(set(keys)) == 1
                for tc in cfg["transfer_conditions"]:
                    p = p_eff(tc)
                    tabs = [table(m[0], m[1], tc["label"], p, num["rk4_steps"], num["s_grid_points"]) for m in mods]
                    ceil = np.array([t.s_in for t in tabs])
                    min_ceil = ceil.min()
                    u0 = np.array([t.nominal_uptake for t in tabs])
                    supply_ratio = qbt * (cin - cref) / u0.sum()
                    drops = cin - ceil
                    first = sorted(range(n), key=lambda i: (-drops[i], i))
                    last = first[::-1]
                    res = {}
                    # parallel arrangements
                    f_uni = np.full(n, 1.0 / n)
                    res["parallel_uniform"] = (st.parallel_fixed(tabs, f_uni, qbt), np.repeat(f_uni[:, None], qbt.size, 1), None)
                    f_dp = u0 / u0.sum()
                    res["parallel_demand_prop"] = (st.parallel_fixed(tabs, f_dp, qbt), np.repeat(f_dp[:, None], qbt.size, 1), None)
                    tau, alloc = st.parallel_maxmin(tabs, qbt, iters=num["maxmin_bisection_iterations"])
                    m_mm = np.array([t.outlet(a)[0] for t, a in zip(tabs, alloc)])
                    res["parallel_maxmin"] = (m_mm, alloc / qbt, None)
                    spread = np.max((m_mm.max(0) - m_mm.min(0)) / m_mm.min(0))
                    sum_err = np.max(np.abs(alloc.sum(0) - qbt) / qbt)
                    detail["C4_max_spread"] = max(detail["C4_max_spread"], float(spread))
                    detail["C4_max_sum_err"] = max(detail["C4_max_sum_err"], float(sum_err))
                    # series arrangements (minima mapped back to module index order)
                    def chain(order):
                        mins_chain = st.series_chain([tabs[i] for i in order], qbt)[0]
                        mins = np.empty_like(mins_chain)
                        for pos, i in enumerate(order):
                            mins[i] = mins_chain[pos]
                        return mins
                    res["series_limited_first"] = (chain(first), None, first)
                    res["series_limited_last"] = (chain(last), None, last)
                    orders = st.distinct_orders(keys)
                    per = [(o, chain(list(o))) for o in orders]
                    worsts = np.array([m.min(0) for _, m in per])
                    ib, iw = worsts.argmax(0), worsts.argmin(0)
                    best_m = np.array([per[ib[j]][1][:, j] for j in range(qbt.size)]).T
                    worst_m = np.array([per[iw[j]][1][:, j] for j in range(qbt.size)]).T
                    res["series_best"] = (best_m, None, [per[ib[j]][0] for j in range(qbt.size)])
                    res["series_worst"] = (worst_m, None, [per[iw[j]][0] for j in range(qbt.size)])

                    # equal hydraulic power to uniform parallel at beta = 1 (secondary)
                    eq = {}
                    q_ref_flow = q_tot[i_beta1]
                    eq["parallel_uniform"] = res["parallel_uniform"][0][:, i_beta1].min(0)
                    f_dp_max = f_dp.max()
                    eq["parallel_demand_prop"] = st.parallel_fixed(tabs, f_dp, q_ref_flow / np.sqrt(n * f_dp_max)).min(0)
                    qm = q_ref_flow.copy()
                    fp_res = 0.0
                    for _ in range(60):
                        _, al = st.parallel_maxmin(tabs, qm, iters=num["maxmin_bisection_iterations"])
                        q_new = q_ref_flow / np.sqrt(n * (al / qm).max(0))
                        fp_res = float(np.max(np.abs(q_new / qm - 1.0)))
                        qm = q_new
                        if fp_res < num["equal_power_fixed_point_tolerance"]:
                            break
                    detail["eq_power_max_fixed_point_residual"] = max(detail["eq_power_max_fixed_point_residual"], fp_res)
                    eq["parallel_maxmin"] = st.parallel_maxmin(tabs, qm, iters=num["maxmin_bisection_iterations"])[0]
                    qs = q_ref_flow / n
                    eq["series_limited_first"] = st.series_chain([tabs[i] for i in first], qs)[0].min(0)
                    eq["series_limited_last"] = st.series_chain([tabs[i] for i in last], qs)[0].min(0)
                    eq_orders = np.array([st.series_chain([tabs[i] for i in o], qs)[0].min(0) for o in orders])
                    eq["series_best"] = eq_orders.max(0)
                    eq["series_worst"] = eq_orders.min(0)

                    # C1 identical modules
                    if identical:
                        dev = np.max(np.abs(res["series_limited_first"][0].min(0) - res["parallel_uniform"][0].min(0))) / cin
                        detail["C1_max_dev"] = max(detail["C1_max_dev"], float(dev))
                    # C5 random allocations at beta = 1
                    a_rand = rng.dirichlet(np.ones(n), size=num["random_allocations_per_config"])
                    qb1 = qbt[i_beta1]
                    worst_rand = np.full((a_rand.shape[0], qb1.size), np.inf)
                    for i, t in enumerate(tabs):
                        s_i = t.outlet((a_rand[:, i][:, None] * qb1[None, :]).ravel())[0].reshape(a_rand.shape[0], qb1.size)
                        worst_rand = np.minimum(worst_rand, s_i)
                    excess = np.max((worst_rand.max(0) - tau[i_beta1]) / tau[i_beta1])
                    detail["C5_max_excess"] = max(detail["C5_max_excess"], float(excess))

                    patch_store[(geometry, r, round(hh * 1e6, 6), tc["label"])] = {
                        "worst": {k: v[0].min(0) for k, v in res.items()}, "min_ceiling": min_ceil,
                        "ceilings": ceil.tolist(), "eq_power": eq, "tau": tau}

                    for j in range(qbt.size):
                        for arr, (mins, frac, order) in res.items():
                            col = mins[:, j]
                            worst = float(col.min())
                            wi = int(col.argmin())
                            if arr.startswith("parallel"):
                                qi = frac[:, j] * q_tot[j]
                                dp = r_ch * q_tot[j] / n if arr == "parallel_uniform" else r_ch * qi.max()
                                frac_s = ";".join("%.10g" % x for x in frac[:, j])
                                order_s = ""
                                rel_power = (dp * q_tot[j]) / (r_ch * q_tot[j] / n * q_tot[j])
                            else:
                                dp = n * r_ch * q_tot[j]
                                frac_s = "all flow"
                                o = order if isinstance(order, list) and not isinstance(order[0], tuple) else order[j]
                                order_s = ">".join(mods[i][2] for i in o)
                                rel_power = float(n * n)
                            eq_val = float(eq[arr][np.where(i_beta1 == j)[0][0]]) if j in i_beta1 else ""
                            rows.append({
                                "geometry": geometry, "hotspot_demand_ratio_r": r, "hotspot_depth_um": round(hh * 1e6, 6),
                                "transfer": tc["label"], "P_eff_mm_s": "%.10g" % (p * 1e3), "beta": int(beta_v[j]),
                                "total_flow_uL_min": "%g" % flow_v[j], "arrangement": arr,
                                "worst_min_mol_m3": "%.12g" % worst, "worst_module": mods[wi][2],
                                "min_ceiling_mol_m3": "%.12g" % min_ceil, "worst_over_ceiling": "%.10g" % (worst / min_ceil),
                                "reaches_reference_0p05": worst >= cref,
                                "module_minima_mol_m3": ";".join("%.10g" % x for x in col),
                                "module_ceilings_mol_m3": ";".join("%.10g" % x for x in ceil),
                                "flow_fractions": frac_s, "series_order": order_s,
                                "pressure_drop_Pa": "%.6g" % dp, "pump_power_W": "%.6g" % (dp * q_tot[j]),
                                "power_relative_to_uniform_parallel": "%.6g" % rel_power,
                                "global_supply_ratio": "%.6g" % supply_ratio[j],
                                "worst_at_equal_power_beta1_mol_m3": ("%.12g" % eq_val) if eq_val != "" else "",
                            })

                    # C6 monotonicity and C7 ceiling bound
                    for arr, (mins, _, _) in res.items():
                        wv = mins.min(0).reshape(betas.size, flows.size)
                        viol = max(float(np.max(-(np.diff(wv, axis=1)), initial=0.0)),
                                   float(np.max(-(np.diff(wv, axis=0)), initial=0.0)))
                        detail["C6_worst_violation"] = max(detail["C6_worst_violation"], viol)
                        detail["C7_worst_excess"] = max(detail["C7_worst_excess"], float(np.max(wv - min_ceil)))

    # C8 refinement subset
    for r in [1, 4]:
        for hh in [1e-4, 4e-4]:
            if r not in cfg["patch"]["hotspot_demand_ratio_r"] or hh not in cfg["patch"]["hotspot_depth_m"]:
                continue
            mods = patch_modules(cfg, "base", r, hh)
            tc = cfg["transfer_conditions"][0]
            p = p_eff(tc)
            fine = [table(m[0], m[1], tc["label"] + "_fine", p, num["refinement_rk4_steps"], num["refinement_s_grid_points"]) for m in mods]
            tau_f, _ = st.parallel_maxmin(fine, qbt, iters=num["maxmin_bisection_iterations"])
            drops = cin - np.array([t.s_in for t in fine])
            first = sorted(range(len(mods)), key=lambda i: (-drops[i], i))
            ser_f = st.series_chain([fine[i] for i in first], qbt)[0].min(0)
            uni_f = st.parallel_fixed(fine, np.full(len(mods), 1.0 / len(mods)), qbt).min(0)
            base = patch_store[("base", r, round(hh * 1e6, 6), tc["label"])]["worst"]
            change = max(np.max(np.abs(tau_f - base["parallel_maxmin"])), np.max(np.abs(ser_f - base["series_limited_first"])),
                         np.max(np.abs(uni_f - base["parallel_uniform"]))) / cin
            detail["C8_max_change"] = max(detail["C8_max_change"], float(change))

    analytic = analytic_tests(cfg)
    checks["C1_identical_modules_series_equals_uniform"] = detail["C1_max_dev"] <= 1e-9
    checks["C2_zero_order_closed_forms"] = (analytic["zero_order"]["maxmin_max_rel_error"] <= 1e-5 and
                                            analytic["zero_order"]["series_max_rel_error"] <= 1e-5 and
                                            analytic["zero_order"]["series_ge_maxmin"])
    checks["C3_first_order_closed_forms"] = (analytic["first_order"]["maxmin_max_rel_error"] <= 1e-5 and
                                             analytic["first_order"]["series_max_rel_error"] <= 1e-5 and
                                             analytic["first_order"]["series_ge_maxmin"])
    checks["C4_maxmin_equalisation"] = detail["C4_max_spread"] <= 1e-8 and detail["C4_max_sum_err"] <= 1e-12
    checks["C5_random_allocations_never_beat_maxmin"] = detail["C5_max_excess"] <= 1e-9
    checks["C6_monotone_in_flow_and_beta"] = detail["C6_worst_violation"] <= 1e-12
    checks["C7_bounded_by_ceiling"] = detail["C7_worst_excess"] <= 1e-12
    checks["C8_refinement"] = detail["C8_max_change"] <= 1e-7

    summary = summarise(cfg, patch_store, betas, flows, i_beta1)
    summary.update({
        "run_type": "AL1 scan" + (" [SMOKE]" if smoke else ""), "started_at_utc": started, "finished_at_utc": now(),
        "elapsed_seconds": time.perf_counter() - t0, "n_result_rows": len(rows),
        "n_module_tables": len(cache), "checks": checks, "check_pass_count": int(sum(checks.values())),
        "check_count": len(checks), "check_details": detail, "analytic_tests": analytic,
        "python_version": platform.python_version(), "numpy_version": np.__version__, "platform": platform.platform(),
        "hydraulic_resistance_per_channel_Pa_s_m3": r_ch,
    })
    write_new(Path(outdir) / FILES["results"], csv_text(rows))
    summary["results_sha256"] = sha256(Path(outdir) / FILES["results"])
    write_new(Path(outdir) / FILES["summary"], json.dumps(summary, indent=2, sort_keys=True, default=float) + "\n")
    return summary


def summarise(cfg, store, betas, flows, i_beta1):
    cref = cfg["reference_parameters"]["reference_line_mol_m3"]
    out = {}
    b1 = list(betas).index(1.0) if 1.0 in list(betas) else 0
    # E1, E4, E5 over all configurations
    e1 = e4 = e5 = True
    e4_counter, gains = [], {"flow_limited": [], "near_ceiling": []}
    e2_ok, e6_total, e6_ok, e6_pass_ref, e7_total, e7_ok = True, 0, 0, 0, 0, 0
    for (geometry, r, hh, tcl), rec in store.items():
        wv = rec["worst"]
        e1 &= bool(np.all(wv["parallel_maxmin"] >= wv["parallel_uniform"] - 1e-12) and
                   np.all(wv["parallel_maxmin"] >= wv["parallel_demand_prop"] - 1e-12))
        diff = wv["series_limited_first"] - wv["parallel_maxmin"]
        if np.any(diff < -1e-12):
            e4 = False
            for j in np.where(diff < -1e-12)[0]:
                e4_counter.append({"geometry": geometry, "r": r, "hotspot_depth_um": hh, "transfer": tcl,
                                   "beta": float(betas[j // flows.size]), "total_flow_uL_min": float(flows[j % flows.size]),
                                   "series_limited_first": float(wv["series_limited_first"][j]),
                                   "parallel_maxmin": float(wv["parallel_maxmin"][j])})
        e5 &= bool(np.all(np.abs(wv["series_limited_first"] - wv["series_best"]) <= 1e-12))
        if rec["min_ceiling"] < cref:
            e2_ok &= bool(all(np.all(v < cref) for v in wv.values()))
        heterogeneous = not ((geometry == "base" and r == 1 and hh == 100.0) or
                             (geometry == "two_sided_hotspot" and r == 1 and hh == 200.0))
        if heterogeneous:
            rel = (wv["parallel_maxmin"] - wv["parallel_uniform"]) / wv["parallel_uniform"]
            limited = wv["parallel_uniform"] < 0.9 * rec["min_ceiling"]
            gains["flow_limited"] += rel[limited].tolist()
            gains["near_ceiling"] += rel[~limited].tolist()
        eqp = rec["eq_power"]
        e7_total += eqp["parallel_maxmin"].size
        e7_ok += int(np.sum(eqp["parallel_maxmin"] >= eqp["series_limited_first"] - 1e-12))
        if geometry == "base" and rec["min_ceiling"] < cref:
            two = store[("two_sided_hotspot", r, hh, tcl)]["worst"]["parallel_maxmin"].reshape(betas.size, flows.size)
            base = wv["parallel_maxmin"].reshape(betas.size, flows.size)
            e6_total += flows.size
            e6_ok += int(np.sum(two[b1] > base[-1]))
            e6_pass_ref += int(np.sum(two[b1] >= cref))
    out["expectations"] = {
        "E1_maxmin_dominates_parallel_heuristics": e1,
        "E2_no_arrangement_or_beta_passes_when_ceiling_below_reference": e2_ok,
        "E3_median_rel_gain_flow_limited": float(np.median(gains["flow_limited"])) if gains["flow_limited"] else None,
        "E3_median_rel_gain_near_ceiling": float(np.median(gains["near_ceiling"])) if gains["near_ceiling"] else None,
        "E3_max_rel_gain": float(max(gains["flow_limited"] + gains["near_ceiling"])) if gains["flow_limited"] else None,
        "E3_n_flow_limited": len(gains["flow_limited"]), "E3_n_near_ceiling": len(gains["near_ceiling"]),
        "E3_holds": bool(gains["flow_limited"] and np.median(gains["flow_limited"]) > 0.01 and
                         (not gains["near_ceiling"] or np.median(gains["near_ceiling"]) < 0.01)),
        "E4_series_limited_first_ge_maxmin_everywhere": e4, "E4_counterexamples": e4_counter[:25],
        "E4_n_counterexamples": len(e4_counter),
        "E5_heuristic_order_is_best_everywhere": e5,
        "E6_configs": e6_total, "E6_two_sided_beta1_beats_base_beta256": e6_ok,
        "E6_two_sided_beta1_reaches_reference": e6_pass_ref, "E6_holds": e6_ok == e6_total,
        "E7_equal_power_maxmin_ge_series_first": e7_ok, "E7_total": e7_total,
    }
    # compact table at beta = 1 for every patch
    table = []
    for (geometry, r, hh, tcl), rec in store.items():
        wv = rec["worst"]
        for k, fl in enumerate(flows):
            j = b1 * flows.size + k
            table.append({"geometry": geometry, "r": r, "hotspot_depth_um": hh, "transfer": tcl, "total_flow_uL_min": float(fl),
                          **{a: float(v[j]) for a, v in wv.items()}, "min_ceiling": float(rec["min_ceiling"]),
                          **{"eq_power_" + a: float(v[k]) for a, v in rec["eq_power"].items()}})
    out["beta1_table"] = table
    # pre-declared counterexample to "more carrier capacity solves everything"
    ce = cfg["counterexample_config"]
    key = (ce["geometry"], ce["hotspot_demand_ratio_r"], round(ce["hotspot_depth_m"] * 1e6, 6), ce["transfer"])
    if key in store:
        k = list(flows).index(ce["total_flow_uL_min"])
        rec = store[key]
        two = store[("two_sided_hotspot",) + key[1:]]
        u_sum = None
        out["counterexample"] = {
            "config": ce, "min_ceiling_base": float(rec["min_ceiling"]), "ceilings_base": rec["ceilings"],
            "min_ceiling_two_sided": float(two["min_ceiling"]),
            "by_beta": [{"beta": float(b), "maxmin_base": float(rec["worst"]["parallel_maxmin"][ib * flows.size + k]),
                         "series_limited_first_base": float(rec["worst"]["series_limited_first"][ib * flows.size + k]),
                         "uniform_base": float(rec["worst"]["parallel_uniform"][ib * flows.size + k]),
                         "maxmin_two_sided": float(two["worst"]["parallel_maxmin"][ib * flows.size + k])}
                        for ib, b in enumerate(betas)],
        }
        del u_sum
    return out


# ----------------------------------------------------------------------------- CLI
def do_freeze():
    for name in ["config", "inputs", "freeze"]:
        if (HERE / FILES[name]).exists():
            raise SystemExit("%s already exists; create a new version instead of refreezing" % FILES[name])
    write_new(HERE / FILES["config"], json.dumps(CONFIG, indent=2, sort_keys=True) + "\n")
    write_new(HERE / FILES["inputs"], csv_text(design(CONFIG)))
    freeze = {"frozen_at_utc": now(), "status": "local pre-run freeze written by the author; not externally witnessed",
              "al1_scan_sha256": sha256(__file__), "stage_transport_sha256": sha256(HERE / "stage_transport.py"),
              "config_sha256": sha256(HERE / FILES["config"]), "inputs_sha256": sha256(HERE / FILES["inputs"]),
              "n_configurations": len(design(CONFIG)), "pre_freeze_disclosure": CONFIG["pre_freeze_disclosure"]}
    write_new(HERE / FILES["freeze"], json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    print(json.dumps(freeze, indent=2))


def do_run():
    freeze = json.loads((HERE / FILES["freeze"]).read_text(encoding="utf-8"))
    current = {"al1_scan_sha256": sha256(__file__), "stage_transport_sha256": sha256(HERE / "stage_transport.py"),
               "config_sha256": sha256(HERE / FILES["config"]), "inputs_sha256": sha256(HERE / FILES["inputs"])}
    mismatch = {k: (freeze[k], v) for k, v in current.items() if freeze[k] != v}
    if mismatch:
        raise SystemExit("Frozen code/config/inputs mismatch: %s" % mismatch)
    if json.loads((HERE / FILES["config"]).read_text(encoding="utf-8")) != json.loads(json.dumps(CONFIG)):
        raise SystemExit("CONFIG in code differs from frozen al1_config.json")
    if csv_text(design(CONFIG)) != (HERE / FILES["inputs"]).read_text(encoding="utf-8"):
        raise SystemExit("Design grid differs from frozen al1_inputs.csv")
    for name in ["results", "summary"]:
        if (HERE / FILES[name]).exists():
            raise SystemExit("%s already exists; this frozen run is preserved" % FILES[name])
    summary = run_scan(CONFIG, HERE)
    keys = ["run_type", "n_result_rows", "n_module_tables", "check_pass_count", "check_count", "checks", "expectations",
            "elapsed_seconds"]
    print(json.dumps({k: summary[k] for k in keys}, indent=2, default=float))


def do_smoke(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=False)
    cfg = smoke_config()
    summary = run_scan(cfg, outdir, smoke=True)
    print(json.dumps({k: summary[k] for k in ["run_type", "n_result_rows", "check_pass_count", "check_count", "checks",
                                               "elapsed_seconds"]}, indent=2, default=float))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--run", action="store_true")
    group.add_argument("--smoke", metavar="DIR")
    args = parser.parse_args()
    if args.freeze:
        do_freeze()
    elif args.run:
        do_run()
    else:
        do_smoke(args.smoke)
