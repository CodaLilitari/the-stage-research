"""Predeclared study for thermal-hotspot-2d-001 (section (d) of the task).

Everything is a model result at the modeled scale. The 0.1 K / 0.5 K
detection comparators and the 40/60 C contract comparators are arbitrary
study comparators (study_comparator_only), not instrument specifications or
safety limits. Writes one JSON file to --out; no other file writes.

Expected runtime is not measured by the author; CPython estimate: minutes.
Use --quick for a reduced grid.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, List

from hotspot2d import model as M
from hotspot2d import convergence as C

PREDECLARED = {
    "extension": M.EXTENSION,
    "contract": M.CONTRACT,
    "patch_half_widths_m": [1e-3, 2e-3, 5e-3, 10e-3, 20e-3],
    "stacks": ["H1", "H2", "H3"],
    "rear_states": ["open_R2", "blocked"],
    "geometries": {"planar": "all stacks", "axisymmetric": "H2 open rear only"},
    "body_power_W": 5.0, "sensor_power_W": 0.1,
    "detection_thresholds_K": [0.1, 0.5],
    "steady_mesh": {"n_outer": 3, "n_film": 1, "n_inner": 3, "dy_fine_m": 0.5e-3,
                    "dy_coarse_m": 5e-3, "margin_m": 8e-3},
    "transient_mesh": {"n_outer": 2, "n_film": 1, "n_inner": 2, "dy_fine_m": 0.5e-3,
                       "dy_coarse_m": 5e-3, "margin_m": 6e-3},
    "transient_dt_s": 2.0, "transient_refinement_dt_s": 1.0,
    "transient_cases": "F0 (no fault) and patch fault at 600 s for w in {2 mm, 20 mm}, "
                       "planar, open rear, body 5 W on [0,900) s, sensor 0.1 W throughout, "
                       "horizon 3600 s; plus 1-D uniform F2 (n_y=1) for comparison",
    "criteria": {
        "time_refinement_max_dT_K": 0.05,
        "mesh_refinement_max_dT_K": 0.10,
        "energy_residual_J_tolerance": 1e-6,
        "spreading_length_modal_rel_tol": 0.25,
        "spreading_length_fin_vs_modal_factor": 2.0,
    },
    "hypotheses": {
        "HYP1": "T_H(ref) <= T_H(w) <= T_H(uniform F2), non-decreasing in w (same rear state).",
        "HYP2": "Film midplane over the patch centre is <= unfaulted value (a cool spot, not a hot spot) "
                "and >= T_mid(uniform F2) - [T_H(uniform F2) - T_H(w)].",
        "HYP3": "Open rear: |T_mid_edge(w) - T_mid_edge(ref)| < 0.1 K for all w <= 20 mm.",
        "HYP4": "Open rear: |T_mid_centre(w) - T_mid_centre(ref)| >= 0.5 K for w >= 5 mm and < 0.5 K for w = 1 mm.",
        "HYP5": "Fitted lateral decay length within 25 % of the two-layer modal value; fin estimate within factor 2.",
        "HYP6": "Blocked rear: max film and max surface temperature with a patch do not exceed the uniform-F2 "
                "blocked values by more than 0.5 K (convection-dominated front path).",
    },
}


def _summ(p, zm, ym, faulted, rear_open):
    net = M.Network(p, zm, ym, faulted, rear_open, p.P_body)
    T, info = M.solve_steady(net, "direct")
    s = M.steady_summary(net, T)
    s["solver"] = info
    return net, T, s


def steady_study(quick: bool) -> Dict[str, object]:
    pm = PREDECLARED["steady_mesh"]
    ws = PREDECLARED["patch_half_widths_m"] if not quick else [2e-3, 20e-3]
    rows = []
    hyp = {k: [] for k in ("HYP1", "HYP2", "HYP3", "HYP4", "HYP6")}
    for stack in PREDECLARED["stacks"]:
        p = M.Params(stack=stack)
        zm = M.build_zmesh(p, pm["n_outer"], pm["n_film"], pm["n_inner"])
        geoms = ["planar", "axisymmetric"] if stack == "H2" else ["planar"]
        for geom in geoms:
            for rear in PREDECLARED["rear_states"]:
                if geom == "axisymmetric" and rear != "open_R2":
                    continue
                rear_open = rear == "open_R2"
                ref = M.reference_1d_steady(p, rear_open=rear_open)
                f2 = M.reference_1d_steady(p, r_inner=p.r_fault, rear_open=rear_open)
                prev_TH = ref["H"]
                for w in ws:
                    ym = M.default_ymesh(geom, w, pm["dy_fine_m"], pm["dy_coarse_m"], pm["margin_m"])
                    net, T, s = _summ(p, zm, ym, True, rear_open)
                    dTc = s["T_mid_centre"] - ref["S"]
                    dTe = s["T_mid_edge"] - ref["S"]
                    dF2 = f2["S"] - ref["S"]
                    row = {"stack": stack, "geometry": geom, "rear": rear, "w_m": w,
                           "n_unknowns": net.n, **s,
                           "ref_1d_unfaulted": {"H": ref["H"], "S": ref["S"], "surface": ref["surface"],
                                                "front": ref["front"], "rear": ref["rear"]},
                           "ref_1d_uniform_F2": {"H": f2["H"], "S": f2["S"], "surface": f2["surface"],
                                                 "front": f2["front"], "rear": f2["rear"]},
                           "delta_T_mid_centre_vs_ref_K": dTc,
                           "delta_T_mid_edge_vs_ref_K": dTe,
                           "delta_T_H_vs_ref_K": s["T_H"] - ref["H"],
                           "centre_deficit_fraction_of_uniform": (dTc / dF2) if abs(dF2) > 1e-12 else None,
                           "detect_centre": {str(th): abs(dTc) >= th for th in PREDECLARED["detection_thresholds_K"]},
                           "detect_edge": {str(th): abs(dTe) >= th for th in PREDECLARED["detection_thresholds_K"]},
                           "comparators_study_comparator_only": {
                               "surface_max_minus_40C": s["T_surf_max"] - 40.0,
                               "H_minus_60C": s["T_H"] - 60.0}}
                    tol = 1e-9
                    hyp["HYP1"].append({"case": (stack, geom, rear, w),
                                        "pass": ref["H"] - tol <= s["T_H"] <= f2["H"] + tol and s["T_H"] >= prev_TH - tol})
                    prev_TH = s["T_H"]
                    hyp["HYP2"].append({"case": (stack, geom, rear, w),
                                        "pass": s["T_mid_centre"] <= ref["S"] + tol and
                                        s["T_mid_centre"] >= f2["S"] - (f2["H"] - s["T_H"]) - tol})
                    if rear_open:
                        hyp["HYP3"].append({"case": (stack, geom, rear, w), "pass": abs(dTe) < 0.1})
                        if w >= 5e-3 - 1e-12:
                            hyp["HYP4"].append({"case": (stack, geom, rear, w), "pass": abs(dTc) >= 0.5})
                        if abs(w - 1e-3) < 1e-12:
                            hyp["HYP4"].append({"case": (stack, geom, rear, w), "pass": abs(dTc) < 0.5})
                    else:
                        hyp["HYP6"].append({"case": (stack, geom, rear, w),
                                            "pass": s["T_mid_max"] <= f2["S"] + 0.5 and
                                            s["T_surf_max"] <= f2["surface"] + 0.5})
                    rows.append(row)
    return {"rows": rows, "hypotheses": {k: {"all_pass": all(r["pass"] for r in v), "cases": v}
                                        for k, v in hyp.items()}}


def spreading_study(quick: bool) -> Dict[str, object]:
    out = []
    for stack in PREDECLARED["stacks"]:
        p = M.Params(stack=stack)
        ell_modal = M.modal_spreading_length(p, p.r_c)
        ell_modal_noconv = M.modal_spreading_length(p, p.r_c, include_convection=False)
        ell_fin = M.fin_spreading_length(p, p.r_c)
        ell_modal_f = M.modal_spreading_length(p, p.r_fault)
        ell_fin_f = M.fin_spreading_length(p, p.r_fault)
        rec = {"stack": stack, "ell_modal_unfaulted_m": ell_modal,
               "ell_modal_unfaulted_no_convection_m": ell_modal_noconv,
               "ell_fin_unfaulted_m": ell_fin, "ell_modal_faulted_m": ell_modal_f,
               "ell_fin_faulted_m": ell_fin_f,
               "fin_within_factor2_of_modal": 0.5 <= ell_fin / ell_modal <= 2.0}
        if not (quick and stack != "H3"):
            # fine mesh so that dy <= ell/4 near the patch edge
            dy = min(0.25e-3, ell_modal / 5)
            nz = 4
            zm = M.build_zmesh(p, nz, 1, nz)
            ym = M.default_ymesh("planar", 10e-3, dy, 2.5e-3, max(8 * ell_modal, 8e-3))
            net = M.Network(p, zm, ym, True, True, p.P_body)
            T, _ = M.solve_steady(net, "direct")
            fit = M.fit_decay_length(ym, net.film_midplane(T), ell_modal)
            rec["numerical_fit"] = fit
            rec["n_unknowns"] = net.n
            if fit is not None:
                rec["fit_over_modal"] = fit["ell_fit_m"] / ell_modal
                rec["HYP5_pass"] = abs(rec["fit_over_modal"] - 1.0) <= 0.25 and rec["fin_within_factor2_of_modal"]
        out.append(rec)
    return {"rows": out}


def refinement_study() -> Dict[str, object]:
    """fix-003: the wave-10 sequence (dy = 5/2.5/1.25 mm) never resolved the
    unfaulted lateral decay length (0.68 mm for H1), so its T_H 'order' (0.27)
    was pre-asymptotic. The scored sequence now satisfies dy <= ell_U/2 near
    the patch edges at the coarsest level; the wave-10 sequence is kept as a
    labelled diagnostic with a discrete-fin prediction of its apparent order."""
    return C.refinement_study(M.Params(stack="H1"))


def _hist(res: M.TransientResult, every: float = 10.0) -> Dict[str, List[float]]:
    keep = [k for k, t in enumerate(res.t) if abs(t / every - round(t / every)) < 1e-9]
    return {f: [getattr(res, f)[k] for k in keep]
            for f in ("t", "T_H", "T_mid_centre", "T_mid_edge", "T_mid_min", "T_mid_max", "T_surf_min", "T_surf_max")}


def _peaks(res: M.TransientResult) -> Dict[str, object]:
    out = {}
    for f in ("T_H", "T_mid_centre", "T_mid_max", "T_surf_max"):
        v = getattr(res, f)
        k = max(range(len(v)), key=lambda i: v[i])
        out[f] = {"peak_C": v[k], "t_peak_s": res.t[k]}
    for name, series, thr in (("surface_40C", res.T_surf_max, 40.0), ("H_60C", res.T_H, 60.0)):
        cross = next((res.t[i] for i, x in enumerate(series) if x >= thr), None)
        out[name + "_study_comparator_only"] = cross if cross is not None else "not_crossed_in_horizon"
    return out


def _detect(res_fault: M.TransientResult, res_base: M.TransientResult, field: str, thr: float):
    for t, a, b in zip(res_fault.t, getattr(res_fault, field), getattr(res_base, field)):
        if t >= 600.0 - 1e-9 and abs(a - b) >= thr:
            return {"t_first_sample_s": t, "deviation_K": a - b}
    return "not_crossed_in_horizon"


def transient_study(quick: bool) -> Dict[str, object]:
    pm = PREDECLARED["transient_mesh"]
    dt = PREDECLARED["transient_dt_s"]
    stacks = PREDECLARED["stacks"] if not quick else ["H1"]
    ws = [2e-3, 20e-3]
    out = []
    for stack in stacks:
        p = M.Params(stack=stack)
        zm = M.build_zmesh(p, pm["n_outer"], pm["n_film"], pm["n_inner"])
        sched_f0 = M.event_schedule(fault_time=None)
        sched_f2 = M.event_schedule(fault_time=600.0)
        # 1-D uniform F2 with the same code (single in-plane cell)
        ym1 = M.ymesh_from_faces("planar", [0.0, M.PANEL_SIDE], M.PANEL_SIDE / 2)
        res_1d_f0 = M.simulate(p, zm, ym1, sched_f0, dt)
        res_1d_f2 = M.simulate(p, zm, ym1, sched_f2, dt)
        for w in ws:
            ym = M.default_ymesh("planar", w, pm["dy_fine_m"], pm["dy_coarse_m"], pm["margin_m"])
            base = M.simulate(p, zm, ym, sched_f0, dt)
            fault = M.simulate(p, zm, ym, sched_f2, dt)
            rec = {"stack": stack, "w_m": w, "dt_s": dt, "n_unknowns": len(base.final_state),
                   "F0_audit": base.audit, "patch_audit": fault.audit,
                   "F0_peaks": _peaks(base), "patch_peaks": _peaks(fault),
                   "uniform_F2_1d_peaks": _peaks(res_1d_f2),
                   "detect_centre": {str(th): _detect(fault, base, "T_mid_centre", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "detect_edge": {str(th): _detect(fault, base, "T_mid_edge", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "detect_centre_uniform_F2_1d": {str(th): _detect(res_1d_f2, res_1d_f0, "T_mid_centre", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "state_continuity_at_600s": [b for b in fault.segment_boundaries if abs(b["t"] - 600.0) < 1e-9],
                   "history_every_10s": {"F0": _hist(base), "patch": _hist(fault), "uniform_F2_1d": _hist(res_1d_f2)}}
            if stack == "H1" and abs(w - 20e-3) < 1e-12:
                fine = M.simulate(p, zm, ym, sched_f2, PREDECLARED["transient_refinement_dt_s"])
                diffs = []
                for k, t in enumerate(fault.t):
                    diffs.append(abs(fault.T_mid_centre[k] - fine.value_at("T_mid_centre", t)))
                diffs_H = [abs(fault.T_H[k] - fine.value_at("T_H", fault.t[k])) for k in range(len(fault.t))]
                rec["time_refinement"] = {"dt_coarse_s": dt, "dt_fine_s": PREDECLARED["transient_refinement_dt_s"],
                                          "max_dT_mid_centre_K": max(diffs), "max_dT_H_K": max(diffs_H),
                                          "criterion_0p05K_met": max(diffs) <= 0.05 and max(diffs_H) <= 0.05}
            out.append(rec)
    return {"rows": out}


def run(out_path: str, quick: bool = False) -> Dict[str, object]:
    report = {"contract": M.CONTRACT, "extension": M.EXTENSION,
              "status": "model_only_not_validated_not_a_safety_or_design_claim",
              "predeclared": PREDECLARED,
              "spreading": spreading_study(quick),
              "steady": steady_study(quick),
              "refinement": refinement_study(),
              "transient": transient_study(quick),
              "omitted": ["F3/F4 controller cases", "F5 double block", "cp/C_H/k sweeps",
                          "outer-interface patch", "patch at panel edge", "radiation", "human contact",
                          "strain dependence", "transient spatial refinement", "real geometry"]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="output JSON path (only file written)")
    ap.add_argument("--quick", action="store_true", help="reduced grid")
    args = ap.parse_args(argv)
    rep = run(args.out, args.quick)
    brief = {"steady_rows": len(rep["steady"]["rows"]),
             "hypotheses": {k: v["all_pass"] for k, v in rep["steady"]["hypotheses"].items()},
             "spreading": [{k: r.get(k) for k in ("stack", "ell_modal_unfaulted_m", "fit_over_modal", "HYP5_pass")}
                           for r in rep["spreading"]["rows"]],
             "refinement_orders_resolved": rep["refinement"]["resolved"]["observed_order"],
             "refinement_precondition_met": rep["refinement"]["resolved"]["precondition_met"],
             "transient_rows": len(rep["transient"]["rows"]), "out": args.out}
    print(json.dumps(brief, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
