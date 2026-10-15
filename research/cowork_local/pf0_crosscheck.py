#!/usr/bin/env python3
"""pf0_crosscheck.py - independent continuum re-analysis of the frozen PF0 run and the
flow-versus-diffusion dimensionless groups.

The Stage, research/cowork_local. Author: Red (Claude, Anthropic) via Claude Cowork, 2026-10-15.
Reads research/artificial_blood/{freeze.json, cases.csv, results.json, monotonicity_diagnostic.json,
MANIFEST.sha256} READ-ONLY and writes only new files next to this script (never overwrites).
Computational verification only; PF0's liver-like constants are NOT treated as skin values.

Usage:  python -B research/cowork_local/pf0_crosscheck.py
"""
import csv
import hashlib
import io
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

PF0 = HERE.parent / "artificial_blood"
OUT = {"cases": "pf0_crosscheck_cases.csv", "wall": "pf0_wall_optimum.csv", "film": "lumen_film_groups.csv",
       "summary": "pf0_crosscheck_summary.json"}
NUM = {"rk4_steps": 1000, "s_grid_points": 2001, "refine_rk4_steps": 2000, "refine_s_grid_points": 4001,
       "wall_scan_points": 13, "wall_scan_P_min_m_s": 1e-6, "wall_scan_P_max_m_s": 1e-2,
       "wall_scan_rk4_steps": 400, "wall_scan_s_grid_points": 801,
       "refine_subset": "depths 50 and 400 um x P 0.005 and 0.2 mm/s",
       "qbeta_set_uL_min": [0.5, 2, 8, 32, 128, 512]}
FILM = {"D_fluid_m2_s": [2e-9, 3e-9], "slit_heights_m": [2.5e-5, 5e-5, 1e-4, 2e-4],
        "slit_Sh_dh": {"one wall, constant concentration": 4.86, "one wall, constant flux": 5.385},
        "tube_diameters_m": [1e-4], "tube_Sh_d": {"constant concentration": 3.66, "constant flux": 4.36},
        "P_wall_m_s": [5e-6, 5e-5, 1e-4, 2e-4], "slit_viscosity_Pa_s": 7e-4}


def kk(h, p):
    """Robust dictionary key for (depth [m], wall coefficient [m/s])."""
    return (int(round(h * 1e9)), int(round(p * 1e12)))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, text):
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        handle.write(text)


def csv_text(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def main():
    for name in OUT.values():
        if (HERE / name).exists():
            raise SystemExit("%s exists; preserved. Use a new version name." % name)
    started = now()
    t0 = time.perf_counter()

    # --- provenance of the read-only inputs
    manifest = {}
    for line in (PF0 / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.strip().split(None, 1)
            manifest[name.strip()] = digest
    inputs = {name: sha256(PF0 / name) for name in ["freeze.json", "cases.csv", "results.json",
                                                    "monotonicity_diagnostic.json", "pf0.py"]}
    manifest_ok = bool(all(manifest.get(k) == v for k, v in inputs.items()))

    cfg = json.loads((PF0 / "freeze.json").read_text(encoding="utf-8"))["config"]
    sp = cfg["source_parameters"]
    q, km, d, cin, thr = sp["qmax_mol_m3_s"], sp["Km_mol_m3"], sp["D_m2_s"], sp["free_inlet_mol_m3"], sp["threshold_mol_m3"]
    w, l = cfg["analyst_selected_geometry"]["wall_width_m"], cfg["analyst_selected_geometry"]["channel_length_m"]
    depths = cfg["analyst_selected_geometry"]["slab_depths_m"]
    perms = cfg["wall_permeabilities_m_s"]
    rows = list(csv.DictReader((PF0 / "cases.csv").open(encoding="utf-8")))
    H = np.array([float(r["depth_um"]) * 1e-6 for r in rows])
    F = np.array([float(r["flow_uL_min"]) for r in rows])
    P = np.array([float(r["wall_permeability_mm_s"]) * 1e-3 for r in rows])
    B = np.array([float(r["beta_hypothetical"]) for r in rows])
    pf_min = np.array([float(r["minimum_free_tissue_mol_m3"]) for r in rows])
    pf_out = np.array([float(r["outlet_free_mol_m3"]) for r in rows])
    pf_upt = np.array([float(r["uptake_mol_s"]) for r in rows])
    pf_pass = np.array([r["all_cells_above_threshold"] == "True" for r in rows])
    pf_local = np.array([r["necessary_local_bound_passes"] == "True" for r in rows])
    pf_supply = np.array([r["necessary_supply_bound_passes"] == "True" for r in rows])
    pf_zero = np.array([float(r["infinite_flow_zero_order_conservative_minimum"]) for r in rows])
    qb = F * B * st.UL_MIN

    # --- V1: independent vectorised re-implementation of PF0's discrete equations
    t1 = time.perf_counter()
    mimic = st.pf0_discrete_channel(H, F, P, B, q, km, d, w, l, cin)
    v1 = {"max_abs_minimum_difference_mol_m3": float(np.max(np.abs(mimic["minimum"] - pf_min))),
          "max_abs_outlet_difference_mol_m3": float(np.max(np.abs(mimic["outlet"] - pf_out))),
          "max_rel_uptake_difference": float(np.max(np.abs(mimic["uptake"] - pf_upt) / pf_upt)),
          "max_mass_balance_error": float(mimic["mass_balance"].max()), "seconds": time.perf_counter() - t1}
    v1["reproduces_pf0"] = bool(v1["max_abs_minimum_difference_mol_m3"] < 1e-9 and v1["max_abs_outlet_difference_mol_m3"] < 1e-9)

    # --- V2: continuum solution of the same 144 cases
    tabs = {kk(h, p): st.ModuleTable(h, q, km, d, p, w, l, cin, n_s=NUM["s_grid_points"], n_x=NUM["rk4_steps"])
            for h in depths for p in perms}
    c_min = np.empty(len(rows))
    c_out = np.empty(len(rows))
    ceil = np.empty(len(rows))
    for i in range(len(rows)):
        t = tabs[kk(H[i], P[i])]
        s_o, cb_o = t.outlet(qb[i])
        c_min[i], c_out[i], ceil[i] = s_o[0], cb_o[0], t.s_in
    c_upt = qb * (cin - c_out)
    c_pass = c_min >= thr
    flips = [{"depth_um": H[i] * 1e6, "flow_uL_min": F[i], "P_mm_s": P[i] * 1e3, "beta": B[i],
              "pf0_minimum": pf_min[i], "continuum_minimum": c_min[i]} for i in np.where(c_pass != pf_pass)[0]]
    v2 = {"max_abs_minimum_difference_over_inlet": float(np.max(np.abs(c_min - pf_min)) / cin),
          "max_rel_minimum_difference": float(np.max(np.abs(c_min - pf_min) / c_min)),
          "max_abs_outlet_difference_over_inlet": float(np.max(np.abs(c_out - pf_out)) / cin),
          "max_rel_uptake_difference": float(np.max(np.abs(c_upt - pf_upt) / c_upt)),
          "pf0_cases_above_threshold": int(pf_pass.sum()), "continuum_cases_above_threshold": int(c_pass.sum()),
          "classification_flips": flips,
          "continuum_above_threshold_by_beta": {str(b): int(np.sum(c_pass[B == b])) for b in sorted(set(B))},
          "pf0_minimum_exceeds_continuum_cases": int(np.sum(pf_min > c_min)),
          "sign_note": "PF0's cell-centre minimum and backward-Euler axial depletion both bias its minima upward"}

    # --- refinement of the continuum tables
    worst_ref = 0.0
    qv = np.array(NUM["qbeta_set_uL_min"], dtype=float) * st.UL_MIN
    for h in [depths[0], depths[-1]]:
        for p in [perms[0], perms[-1]]:
            t = tabs[kk(h, p)]
            tf = st.ModuleTable(h, q, km, d, p, w, l, cin, n_s=NUM["refine_s_grid_points"], n_x=NUM["refine_rk4_steps"])
            worst_ref = max(worst_ref, float(np.max(np.abs(tf.outlet(qv)[0] - t.outlet(qv)[0]) / cin)),
                            abs(tf.s_in - t.s_in) / cin)

    # --- V3: limiting cases
    mono = json.loads((PF0 / "monotonicity_diagnostic.json").read_text(encoding="utf-8"))
    fixed = []
    for r in mono["rows"]:
        t = tabs[kk(r["depth_um"] * 1e-6, r["P_mm_s"] * 1e-3)]
        fixed.append({"depth_um": r["depth_um"], "P_mm_s": r["P_mm_s"], "continuum_ceiling": t.s_in,
                      "pf0_96cell_fixed_lumen_minimum": r["fixed_lumen_minimum"],
                      "rel_difference": abs(t.s_in - r["fixed_lumen_minimum"]) / t.s_in,
                      "continuum_low_flow_minimum": float(t.outlet(0.5 * st.UL_MIN)[0][0]),
                      "pf0_refined_48x128_minimum": r["refined_coupled_minimum"]})
    top = (F * B) == (F * B).max()
    high_flow = {"max_qbeta_uL_min": float((F * B).max()),
                 "max_gap_ceiling_minus_pf0_minimum_over_inlet": float(np.max((ceil[top] - pf_min[top]) / cin)),
                 "min_gap_ceiling_minus_pf0_minimum_over_inlet": float(np.min((ceil[top] - pf_min[top]) / cin))}
    bounds = {"local_bound_fails_but_ceiling_passes": int(np.sum(~pf_local & (ceil >= thr))),
              "local_bound_passes_but_ceiling_fails": int(np.sum(pf_local & (ceil < thr))),
              "continuum_pass_without_both_necessary_bounds": int(np.sum(c_pass & ~(pf_local & pf_supply))),
              "zero_order_conservative_minimum_exceeds_ceiling": int(np.sum(pf_zero > ceil + 1e-15))}
    # first-order (dilute) analytic limit of the full coupled channel
    cin_d = km * 1e-9
    qv = np.array(NUM["qbeta_set_uL_min"], dtype=float) * st.UL_MIN
    dil = 0.0
    for h in depths:
        for p in perms:
            t = st.ModuleTable(h, q, km, d, p, w, l, cin_d, n_s=NUM["s_grid_points"], n_x=NUM["rk4_steps"])
            ana = st.linear_module_closed_form(h, q / km, d, p, w, l, cin_d, qv)[0]
            dil = max(dil, float(np.max(np.abs(t.outlet(qv)[0] - ana) / ana)))
    # zero-order analytic limit (Km -> 1e-6 Cin, fully penetrated slabs)
    zer = 0.0
    qz = np.array([8, 32, 128, 512], dtype=float) * st.UL_MIN
    for h in [5e-5, 1e-4]:
        for p in [5e-5, 2e-4]:
            t = st.ModuleTable(h, q, cin * 1e-6, d, p, w, l, cin, n_s=NUM["s_grid_points"], n_x=NUM["rk4_steps"], s_lo_rel=1e-3)
            ana = cin - q * h * w * l / qz - q * (h / p + h * h / (2 * d))
            zer = max(zer, float(np.max(np.abs(t.outlet(qz)[0] - ana) / ana)))
    # Q*beta degeneracy as recorded in PF0's own outputs
    key = {}
    for i in range(len(rows)):
        key.setdefault(kk(H[i], P[i]) + (round(F[i] * B[i], 9),), []).append(pf_min[i])
    degeneracy = max((max(v) - min(v) for v in key.values() if len(v) > 1), default=0.0)
    # Richardson estimate from PF0's own 32- and 128-segment values (first-order backward Euler)
    rich = []
    for r in mono["rows"]:
        h, p = r["depth_um"] * 1e-6, r["P_mm_s"] * 1e-3
        i = int(np.where(np.isclose(H, h) & np.isclose(P, p) & (F == 0.5) & (B == 1.0))[0][0])
        est = r["refined_coupled_minimum"] + (r["refined_coupled_minimum"] - pf_min[i]) / 3.0
        cont = float(tabs[kk(h, p)].outlet(0.5 * st.UL_MIN)[0][0])
        rich.append({"depth_um": r["depth_um"], "P_mm_s": r["P_mm_s"], "pf0_24x32": pf_min[i],
                     "pf0_48x128": r["refined_coupled_minimum"], "richardson_estimate": est, "continuum": cont,
                     "richardson_rel_gap": abs(est - cont) / cont})
    # wall-permeability monotonicity groups in the continuum solution
    groups = {}
    for i in range(len(rows)):
        groups.setdefault((round(H[i] * 1e6, 6), F[i], B[i]), []).append((P[i], c_min[i]))
    cont_nonmono = []
    for g, vals in groups.items():
        vals.sort()
        if any(b[1] < a[1] - 1e-12 for a, b in zip(vals, vals[1:])):
            cont_nonmono.append({"depth_um": g[0], "flow_uL_min": g[1], "beta": g[2],
                                 "minima_by_P_mm_s": {"%g" % (v[0] * 1e3): v[1] for v in vals}})
    pf0_failures = json.loads((PF0 / "results.json").read_text(encoding="utf-8"))["monotonic_failures"]

    # --- dimensionless groups for every PF0 case
    k1 = q / km
    out_rows = []
    for i in range(len(rows)):
        h, p = H[i], P[i]
        phi = h * np.sqrt(k1 / d)
        a = np.sqrt(d * k1) * np.tanh(phi)
        k_lin = 1.0 / (1.0 / p + 1.0 / a)
        phi2 = q * h * h / (d * cin)
        bi = p * h / d
        da_c = q * w * h * l / (qb[i] * cin)
        sat = c_min[i] / ceil[i]
        regime = ("transverse-limited (ceiling below reference)" if ceil[i] < thr else
                  ("flow-saturated (>=0.9 of ceiling)" if sat >= 0.9 else "flow/extraction-limited"))
        out_rows.append({
            "depth_um": "%g" % (h * 1e6), "flow_uL_min": "%g" % F[i], "P_mm_s": "%g" % (p * 1e3), "beta": "%g" % B[i],
            "qbeta_uL_min": "%g" % (F[i] * B[i]),
            "kappa_Km_over_Cin": "%.6g" % (km / cin), "Phi2_qH2_over_DCin": "%.6g" % phi2,
            "zero_order_transverse_drop_over_Cin": "%.6g" % (phi2 / 2), "Biot_PH_over_D": "%.6g" % bi,
            "zero_order_wall_drop_over_Cin": "%.6g" % (phi2 / bi), "Da_conv_qV_over_QbetaCin": "%.6g" % da_c,
            "first_order_NTU": "%.6g" % (k_lin * w * l / qb[i]), "first_order_thiele_phi": "%.6g" % phi,
            "pf0_minimum_mol_m3": "%.10g" % pf_min[i], "pf0_mimic_minimum_mol_m3": "%.10g" % mimic["minimum"][i],
            "continuum_minimum_mol_m3": "%.10g" % c_min[i], "continuum_ceiling_mol_m3": "%.10g" % ceil[i],
            "pf0_outlet_mol_m3": "%.10g" % pf_out[i], "continuum_outlet_mol_m3": "%.10g" % c_out[i],
            "continuum_extraction_fraction": "%.6g" % (1 - c_out[i] / cin),
            "continuum_minimum_over_ceiling": "%.6g" % sat,
            "pf0_above_threshold": bool(pf_pass[i]), "continuum_above_threshold": bool(c_pass[i]), "regime": regime,
        })

    # --- wall-permeability optimum (where more wall transfer stops helping the worst region)
    p_grid = np.geomspace(NUM["wall_scan_P_min_m_s"], NUM["wall_scan_P_max_m_s"], NUM["wall_scan_points"])
    wall_rows = []
    for h in depths:
        curve = np.array([st.ModuleTable(h, q, km, d, p, w, l, cin, n_s=NUM["wall_scan_s_grid_points"],
                                         n_x=NUM["wall_scan_rk4_steps"]).outlet(qv)[0] for p in p_grid])  # (nP, nQ)
        for j, qbv in enumerate(NUM["qbeta_set_uL_min"]):
            s_curve = curve[:, j]
            k = int(np.argmax(s_curve))
            interior = 0 < k < len(p_grid) - 1
            if interior:
                x = np.log(p_grid[k - 1:k + 2])
                yv = s_curve[k - 1:k + 2]
                c2, c1, c0 = np.polyfit(x, yv, 2)
                xs = -c1 / (2 * c2)
                p_star, s_star = float(np.exp(xs)), float(c0 + c1 * xs + c2 * xs * xs)
            else:
                p_star, s_star = float(p_grid[k]), float(s_curve[k])
            phi = h * np.sqrt(k1 / d)
            a = np.sqrt(d * k1) * np.tanh(phi)
            s_res = w * l / (qbv * st.UL_MIN)
            p_lin = a / (a * s_res - 1.0) if a * s_res > 1.0 else float("inf")
            pf_vals = {"%g" % (p * 1e3): float(tabs[kk(h, p)].outlet(qbv * st.UL_MIN)[0][0]) for p in perms}
            wall_rows.append({
                "depth_um": "%g" % (h * 1e6), "qbeta_uL_min": "%g" % qbv,
                "interior_optimum_in_scan": interior,
                "P_star_mm_s": "%.6g" % (p_star * 1e3), "minimum_at_P_star_mol_m3": "%.8g" % s_star,
                "minimum_at_P_0.005_mol_m3": "%.8g" % pf_vals["0.005"], "minimum_at_P_0.05_mol_m3": "%.8g" % pf_vals["0.05"],
                "minimum_at_P_0.2_mol_m3": "%.8g" % pf_vals["0.2"],
                "minimum_at_P_10mm_s_mol_m3": "%.8g" % s_curve[-1],
                "first_order_prediction_P_star_mm_s": ("%.6g" % (p_lin * 1e3)) if np.isfinite(p_lin) else "inf (monotone)",
            })

    # --- lumen-side film resistance and channel-geometry groups
    film_rows = []
    for dfl in FILM["D_fluid_m2_s"]:
        for hgt in FILM["slit_heights_m"]:
            for lab, sh in FILM["slit_Sh_dh"].items():
                k_l = st.lumen_film_conductance(dfl, 2 * hgt, sh)
                for pw in FILM["P_wall_m_s"]:
                    film_rows.append({"geometry": "wide slit, one transferring wall", "size_um": "h=%g" % (hgt * 1e6),
                                      "d_h_um": "%g" % (2 * hgt * 1e6), "Sh_case": lab, "Sh": sh, "D_fluid_m2_s": dfl,
                                      "k_L_mm_s": "%.5g" % (k_l * 1e3), "P_wall_mm_s": "%g" % (pw * 1e3),
                                      "lumen_Biot_P_over_kL": "%.4g" % (pw / k_l),
                                      "P_eff_mm_s": "%.5g" % (1e3 / (1 / pw + 1 / k_l)), "P_eff_over_P_wall": "%.4g" % (1 / (1 + pw / k_l))})
        for dia in FILM["tube_diameters_m"]:
            for lab, sh in FILM["tube_Sh_d"].items():
                k_l = st.lumen_film_conductance(dfl, dia, sh)
                for pw in FILM["P_wall_m_s"]:
                    film_rows.append({"geometry": "circular tube", "size_um": "d=%g" % (dia * 1e6), "d_h_um": "%g" % (dia * 1e6),
                                      "Sh_case": lab, "Sh": sh, "D_fluid_m2_s": dfl, "k_L_mm_s": "%.5g" % (k_l * 1e3),
                                      "P_wall_mm_s": "%g" % (pw * 1e3), "lumen_Biot_P_over_kL": "%.4g" % (pw / k_l),
                                      "P_eff_mm_s": "%.5g" % (1e3 / (1 / pw + 1 / k_l)), "P_eff_over_P_wall": "%.4g" % (1 / (1 + pw / k_l))})
    r100 = st.slit_resistance(FILM["slit_viscosity_Pa_s"], l, w, 1e-4)
    channel = {"assumed_slit_height_m": 1e-4, "viscosity_Pa_s": FILM["slit_viscosity_Pa_s"],
               "graetz_Qh_over_WLD_at_PF0_flows_D2e-9": {"%g" % f: f * st.UL_MIN * 1e-4 / (w * l * 2e-9) for f in cfg["flows_uL_min"]},
               "pressure_drop_Pa_at_PF0_flows": {"%g" % f: r100 * f * st.UL_MIN for f in cfg["flows_uL_min"]},
               "resistance_Pa_s_m3": r100}

    checks = {
        "inputs_match_pf0_manifest": manifest_ok,
        "V1_mimic_reproduces_pf0_minima_and_outlets_1e-9": v1["reproduces_pf0"],
        "V2_continuum_close_to_pf0_within_1pct_of_inlet": v2["max_abs_minimum_difference_over_inlet"] < 0.01,
        "V2_no_threshold_classification_flips": len(flips) == 0,
        "continuum_refinement_below_1e-8_of_inlet": worst_ref < 1e-8,
        "fixed_lumen_ceiling_matches_pf0_96cell_within_0.5pct": max(f["rel_difference"] for f in fixed) < 5e-3,
        "dilute_first_order_closed_form_1e-6": dil < 1e-6,
        "zero_order_closed_form_1e-5": zer < 1e-5,
        "necessary_bounds_consistent": (bounds["local_bound_fails_but_ceiling_passes"] == 0 and
                                        bounds["continuum_pass_without_both_necessary_bounds"] == 0 and
                                        bounds["zero_order_conservative_minimum_exceeds_ceiling"] == 0),
        "pf0_outputs_depend_only_on_Qbeta_1e-12": degeneracy < 1e-12,
        "pf0_low_flow_wall_reversals_preserved_in_continuum": all(
            any(c["depth_um"] == f["group"][0] and c["flow_uL_min"] == f["group"][1] and c["beta"] == f["group"][2]
                for c in cont_nonmono) for f in pf0_failures),
    }
    checks = {k: bool(v) for k, v in checks.items()}
    summary = {
        "run_type": "PF0 continuum cross-check and dimensionless analysis (cowork_local, Red)",
        "started_at_utc": started, "finished_at_utc": now(), "elapsed_seconds": time.perf_counter() - t0,
        "inputs_read_only_sha256": inputs, "inputs_match_pf0_manifest": manifest_ok,
        "parameters_used": {"q": q, "Km": km, "D": d, "Cin": cin, "threshold_reference": thr, "W": w, "L": l,
                            "provenance": sp["provenance"]},
        "numerics": NUM, "film_inputs": FILM,
        "checks": checks, "check_pass_count": int(sum(checks.values())), "check_count": len(checks),
        "V1_pf0_discrete_mimic": v1, "V2_continuum_vs_pf0": v2, "continuum_refinement_max_change_over_inlet": worst_ref,
        "fixed_lumen_vs_pf0_diagnostic": fixed, "highest_qbeta_vs_ceiling": high_flow, "necessary_bound_consistency": bounds,
        "dilute_first_order_max_rel_error": dil, "zero_order_max_rel_error": zer,
        "pf0_qbeta_degeneracy_max_abs": degeneracy, "richardson_from_pf0_grids": rich,
        "continuum_wall_nonmonotone_groups": cont_nonmono, "pf0_reported_monotonic_failures": pf0_failures,
        "channel_geometry": channel,
        "python_version": platform.python_version(), "numpy_version": np.__version__, "platform": platform.platform(),
    }
    write_new(HERE / OUT["cases"], csv_text(out_rows))
    write_new(HERE / OUT["wall"], csv_text(wall_rows))
    write_new(HERE / OUT["film"], csv_text(film_rows))
    summary["outputs_sha256"] = {OUT[k]: sha256(HERE / OUT[k]) for k in ["cases", "wall", "film"]}
    write_new(HERE / OUT["summary"], json.dumps(summary, indent=2, sort_keys=True, default=float) + "\n")
    print(json.dumps({k: summary[k] for k in ["checks", "check_pass_count", "check_count", "elapsed_seconds"]}, indent=2))
    print(json.dumps({"V1": v1, "V2": {k: v2[k] for k in v2 if k != "classification_flips"},
                      "flips": len(flips), "refinement": worst_ref, "dilute": dil, "zero": zer,
                      "continuum_nonmonotone_groups": len(cont_nonmono)}, indent=2, default=float))


if __name__ == "__main__":
    main()
