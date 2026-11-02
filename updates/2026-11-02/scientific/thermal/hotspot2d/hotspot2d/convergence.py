"""Mesh-convergence helpers for 2D-PATCH-EXT-1 (task thermal-hotspot-2d-fix-003).

Why this module exists (Red's executed wave-10 receipt, H1, w = 5 mm, factor-2
refinement in z and y with in-plane spacing dy = 5, 2.5, 1.25 mm): the T_H
sequence 33.843532 / 33.842843 / 33.842272 C has differences 0.689 mK and
0.571 mK and an 'observed order' of 0.270.  Those differences are ~1e5 times
the solver noise floor, so this is not round-off; the sequence is
pre-asymptotic: dy never resolved the unfaulted lateral decay length
ell_U = 0.682 mm (dy/ell_U = 7.3, 3.7, 1.8).  T_H depends on the lateral
exchange across the patch edges, which a cell-centred scheme captures only to
the fraction f(dy) given by the discrete-fin model below (0.41, 0.66, 0.86 at
the three levels); that predicts an apparent order of 0.31 (executed 0.27) and
a total lateral effect on T_H of ~2.8 mK.  The lumped-node coupling is not at
fault: both 1-D limits reproduce Coda's two-node reference to 1e-9 on every
mesh (existing tests).

Provided here: (i) a resolution precondition that must hold before an order is
scored, (ii) the discrete-fin model that reproduces the pre-asymptotic
behaviour, (iii) a sequence classifier with an explicit noise floor so that
round-off-limited differences are never scored as an order, (iv) a resolved
refinement sequence (dy <= ell_U/2 near the patch edges at the coarsest level)
and (v) a deliberately defective variant (fault boundary one cell off the mesh
faces) used by the tests to show the criterion is not vacuous.
Standard library only; model only; nothing here was executed by the author.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from hotspot2d import model as M

# Worst-case forward-error bound of the direct solve: executed residual norms
# ~1e-13 W divided by the smallest eigenvalue of K (>~ 1e-4 W/K for n <= 6000).
NOISE_FLOOR_K = 1e-9
# Coarsest-level max(dy)/ell_U within 4 ell_U of a patch edge; discrete-fin
# relative error (dy^2/8)(1/ell_U + 1/ell_F)/(ell_U + ell_F) is ~1 % at 0.5.
RESOLUTION_LIMIT = 0.5
ORDER_FLOOR_PREDECLARED = 1.0   # wave-10 predeclared floor, unchanged
ORDER_FLOOR_TIGHTENED = 1.5     # fix-003: scheme is second order; reported separately
ABS_TOL_FINEST_PAIR_K = 1e-3    # finest-pair change declared mesh-converged for the study
KEYS = ("T_H", "T_mid_centre", "T_mid_min", "T_surf_min")
REFINES = (1, 2, 4)

RESOLVED = {"w": 5e-3, "dy_fine": 0.3125e-3, "dy_coarse": 5e-3, "margin": 6e-3, "nz_base": 2}
WAVE10 = {"w": 5e-3, "breaks": (0.0, 0.045, 0.055, 0.1), "counts": (9, 2, 9), "nz_base": 2}


# --------------------------------------------------------------------------
# discrete fin (closed-form model of the FV lateral exchange)
# --------------------------------------------------------------------------
def discrete_decay_factor(x: float) -> float:
    """Per-cell decay factor of the cell-centred discrete fin
    theta_{j+1} - 2 theta_j + theta_{j-1} = x^2 theta_j, x = dy/ell:
    lambda + 1/lambda = 2 + x^2, i.e. lambda = exp(-2 asinh(x/2)) in (0, 1)."""
    if not x > 0.0:
        raise ValueError("x = dy/ell must be positive")
    return math.exp(-2.0 * math.asinh(0.5 * x))


def discrete_fin_series_resistance(dy: float, ells: Sequence[float]) -> float:
    """Lateral series resistance (units of 1/kappa) between the far fields of
    semi-infinite discrete fins joined at a mesh face:
    R = dy * (1 + sum_i lambda_i / (1 - lambda_i)).
    Continuum limit sum(ells); expansion R = sum(ells) + dy^2/8 * sum(1/ell_i)
    + O(dy^4): the scheme is second order once dy <~ ell."""
    if dy <= 0.0:
        raise ValueError("dy must be positive")
    total = 1.0
    for ell in ells:
        lam = discrete_decay_factor(dy / ell)
        total += lam / (1.0 - lam)
    return dy * total


def exchange_fraction(dy: float, ell_u: float, ell_f: float) -> float:
    """Fraction of the resolved lateral exchange captured at spacing dy
    (semi-infinite fins on both sides; valid for patch half-width w >> ell_f)."""
    return (ell_u + ell_f) / discrete_fin_series_resistance(dy, (ell_u, ell_f))


def predicted_pre_asymptotic_order(dys: Sequence[float], ell_u: float, ell_f: float,
                                   ratio: float = 2.0) -> float:
    """Apparent Richardson order of a functional proportional to the captured
    exchange, for three spacings refined by `ratio`."""
    if len(dys) != 3:
        raise ValueError("need three spacings")
    f = [exchange_fraction(d, ell_u, ell_f) for d in dys]
    e1, e2 = abs(f[1] - f[0]), abs(f[2] - f[1])
    if e1 <= 0.0 or e2 <= 0.0:
        raise ArithmeticError("degenerate exchange-fraction sequence")
    return math.log(e1 / e2) / math.log(ratio)


# --------------------------------------------------------------------------
# precondition and sequence classification
# --------------------------------------------------------------------------
def edge_resolution(ym: M.YMesh, ell: float, span: float = 4.0) -> float:
    """max cell width among cells whose centre lies within span*ell of a patch
    edge, divided by ell. Must be <= RESOLUTION_LIMIT at the coarsest level
    before an observed order is scored."""
    if ell <= 0.0:
        raise ValueError("ell must be positive")
    c = ym.centre_position
    edges = [c + ym.w] if ym.geometry == "axisymmetric" else [c - ym.w, c + ym.w]
    widths = [ym.widths[j] for j in range(ym.n)
              if any(abs(ym.centres[j] - e) <= span * ell for e in edges)]
    if not widths:
        raise ValueError("no cell centre within span*ell of a patch edge")
    return max(widths) / ell


def convergence_report(values: Sequence[float], ratio: float = 2.0,
                       floor: float = NOISE_FLOOR_K) -> Dict[str, object]:
    """Classify three successive refinement values.
    status: 'below_noise' (e2 < floor: converged to solver noise, no order),
            'not_decreasing' (e2 >= e1 or e1 < floor <= e2),
            'order_defined' (order = log(e1/e2)/log(ratio))."""
    vals = [float(v) for v in values]
    if len(vals) != 3:
        raise ValueError("need exactly three refinement levels")
    e1, e2 = abs(vals[0] - vals[1]), abs(vals[1] - vals[2])
    rep: Dict[str, object] = {"values": vals, "e1_K": e1, "e2_K": e2, "order": None,
                              "noise_floor_K": floor, "ratio": ratio}
    if e2 < floor:
        rep["status"] = "below_noise"
    elif e1 < floor or e2 >= e1:
        rep["status"] = "not_decreasing"
    else:
        rep["order"] = math.log(e1 / e2) / math.log(ratio)
        rep["status"] = "order_defined"
    return rep


def score(report: Dict[str, object], order_floor: float) -> str:
    if report["status"] == "below_noise":
        return "pass_converged_below_noise"
    if report["status"] == "not_decreasing":
        return "FAIL_not_decreasing"
    return "pass" if float(report["order"]) >= order_floor else "FAIL_order_below_floor"


# --------------------------------------------------------------------------
# refinement levels
# --------------------------------------------------------------------------
def resolved_level(p: M.Params, refine: int, w: float = RESOLVED["w"],
                   dy_fine: float = RESOLVED["dy_fine"], dy_coarse: float = RESOLVED["dy_coarse"],
                   margin: float = RESOLVED["margin"], nz_base: int = RESOLVED["nz_base"],
                   refine_z: bool = True, overhang_cells: int = 0) -> Tuple[M.ZMesh, M.YMesh]:
    """Graded planar mesh: dy_fine inside the patch and within `margin` of its
    edges, dy_coarse in the (1-D exact) far field; nested under `refine`.
    overhang_cells > 0 builds the deliberately defective variant: the fault is
    applied to that many cells beyond the geometric patch edge on each side
    (faulted area 2wD + 2*overhang*dy*D), a first-order inconsistency."""
    if refine < 1:
        raise ValueError("refine must be >= 1")
    nz = nz_base * refine if refine_z else nz_base
    zm = M.build_zmesh(p, nz, 1, nz)
    ym = M.default_ymesh("planar", w, dy_fine, dy_coarse, margin, refine=refine)
    if overhang_cells:
        c = ym.centre_position
        outside = [j for j in range(ym.n) if ym.centres[j] > c + w]
        width_out = ym.widths[outside[0]]
        ym = M.ymesh_from_faces("planar", ym.faces, w + (overhang_cells + 0.25) * width_out)
    return zm, ym


def wave10_level(p: M.Params, refine: int) -> Tuple[M.ZMesh, M.YMesh]:
    """The wave-10 sequence (uniform dy = 5 mm / refine): kept for diagnosis."""
    nz = WAVE10["nz_base"] * refine
    zm = M.build_zmesh(p, nz, 1, nz)
    counts = [c * refine for c in WAVE10["counts"]]
    ym = M.ymesh_from_faces("planar", M.faces_from_segments(list(WAVE10["breaks"]), counts), WAVE10["w"])
    return zm, ym


def solve_level(p: M.Params, zm: M.ZMesh, ym: M.YMesh) -> Dict[str, object]:
    net = M.Network(p, zm, ym, True, True, p.P_body)
    T, info = M.solve_steady(net, "direct")
    s = M.steady_summary(net, T)
    out: Dict[str, object] = {k: s[k] for k in KEYS}
    out.update({"n_unknowns": net.n, "n_y": ym.n, "n_z": zm.n, "dz_silicone_m": zm.dz[0],
                "faulted_area_m2": ym.patch_area, "front_W": s["front_W"], "rear_W": s["rear_W"],
                "balance_W": s["balance_W"], "residual_norm": info["residual_norm"]})
    return out


def run_sequence(p: M.Params, refines: Sequence[int] = REFINES, ell_u: Optional[float] = None,
                 **level_kwargs) -> Dict[str, object]:
    """Solve the resolved sequence and classify every functional in KEYS."""
    if len(refines) != 3 or refines[1] * refines[1] != refines[0] * refines[2]:
        raise ValueError("need three levels with a constant refinement ratio")
    if ell_u is None:
        ell_u = M.modal_spreading_length(p, p.r_c)
    levels: List[Dict[str, object]] = []
    for r in refines:
        zm, ym = resolved_level(p, r, **level_kwargs)
        lv = solve_level(p, zm, ym)
        lv["refine"] = r
        lv["edge_resolution_dy_over_ell"] = edge_resolution(ym, ell_u)
        lv["dy_patch_m"] = max(ym.widths[j] for j in range(ym.n) if ym.in_patch[j])
        levels.append(lv)
    ratio = refines[1] / refines[0]
    reports = {k: convergence_report([lv[k] for lv in levels], ratio=ratio) for k in KEYS}
    coarse_res = float(levels[0]["edge_resolution_dy_over_ell"])
    return {"levels": levels, "reports": reports,
            "observed_order": {k: reports[k]["order"] for k in KEYS},
            "status": {k: reports[k]["status"] for k in KEYS},
            "last_change_K": {k: reports[k]["e2_K"] for k in KEYS},
            "ell_unfaulted_modal_m": ell_u,
            "precondition_dy_over_ell_coarsest": coarse_res,
            "precondition_met": coarse_res <= RESOLUTION_LIMIT}


# --------------------------------------------------------------------------
# study-level record
# --------------------------------------------------------------------------
def refinement_study(p: Optional[M.Params] = None, include_wave10: bool = True) -> Dict[str, object]:
    p = M.Params(stack="H1") if p is None else p
    ell_u = M.modal_spreading_length(p, p.r_c)
    ell_f = M.modal_spreading_length(p, p.r_fault)
    resolved = run_sequence(p, ell_u=ell_u)
    resolved["scores_predeclared_floor_1p0"] = {k: score(resolved["reports"][k], ORDER_FLOOR_PREDECLARED)
                                                for k in KEYS}
    resolved["scores_tightened_floor_1p5"] = {k: score(resolved["reports"][k], ORDER_FLOOR_TIGHTENED)
                                              for k in ("T_H", "T_mid_centre")}
    resolved["criterion_0p10K_met_on_finest_pair"] = all(float(v) <= 0.10 for v in resolved["last_change_K"].values())
    resolved["criterion_1mK_met_on_finest_pair"] = all(float(v) <= ABS_TOL_FINEST_PAIR_K
                                                       for v in resolved["last_change_K"].values())
    resolved["mesh"] = dict(RESOLVED)
    out: Dict[str, object] = {"resolved": resolved, "ell_unfaulted_modal_m": ell_u, "ell_faulted_modal_m": ell_f,
                              "resolution_limit_dy_over_ell": RESOLUTION_LIMIT, "noise_floor_K": NOISE_FLOOR_K,
                              "criterion_0p10K_met_on_finest_pair": resolved["criterion_0p10K_met_on_finest_pair"]}
    if include_wave10:
        levels: List[Dict[str, object]] = []
        for r in REFINES:
            zm, ym = wave10_level(p, r)
            lv = solve_level(p, zm, ym)
            lv["refine"] = r
            lv["edge_resolution_dy_over_ell"] = edge_resolution(ym, ell_u)
            levels.append(lv)
        reports = {k: convergence_report([lv[k] for lv in levels]) for k in KEYS}
        dys = [2.0 * WAVE10["w"] / (WAVE10["counts"][1] * r) for r in REFINES]
        fr = [exchange_fraction(d, ell_u, ell_f) for d in dys]
        fin: Dict[str, object] = {"dy_patch_m": dys, "exchange_fraction": fr,
                                  "predicted_order_T_H": predicted_pre_asymptotic_order(dys, ell_u, ell_f)}
        rep = reports["T_H"]
        if rep["status"] == "order_defined" and fr[2] > fr[1]:
            shift = float(rep["e2_K"]) / (fr[2] - fr[1])
            extrap = float(levels[-1]["T_H"]) - (1.0 - fr[2]) * shift
            fin["implied_total_lateral_effect_on_T_H_K"] = shift
            fin["extrapolated_resolved_T_H_C"] = extrap
            fin["resolved_sequence_finest_T_H_C"] = resolved["levels"][-1]["T_H"]
            fin["extrapolated_minus_resolved_finest_K"] = extrap - float(resolved["levels"][-1]["T_H"])
        out["wave10_pre_asymptotic"] = {
            "levels": levels, "reports": reports,
            "observed_order": {k: reports[k]["order"] for k in KEYS},
            "precondition_met": float(levels[0]["edge_resolution_dy_over_ell"]) <= RESOLUTION_LIMIT,
            "discrete_fin_model": fin,
            "note": "Diagnostic only. dy/ell_U = 7.3, 3.7, 1.8: not an asymptotic sequence, so the "
                    "'order' is not scored. Kept so that the wave-10 artefact stays on record."}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fix-003 mesh-convergence study (writes one JSON file)")
    ap.add_argument("--out", required=True, help="output JSON path (only file written)")
    ap.add_argument("--no-wave10", action="store_true", help="skip the wave-10 diagnostic sequence")
    args = ap.parse_args(argv)
    rep = refinement_study(include_wave10=not args.no_wave10)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=str)
    res = rep["resolved"]
    brief = {"resolved_precondition_met": res["precondition_met"],
             "resolved_dy_over_ell_coarsest": res["precondition_dy_over_ell_coarsest"],
             "resolved_observed_order": res["observed_order"],
             "resolved_status": res["status"],
             "resolved_last_change_K": res["last_change_K"],
             "resolved_T_H_levels": [lv["T_H"] for lv in res["levels"]],
             "scores_predeclared_floor_1p0": res["scores_predeclared_floor_1p0"],
             "scores_tightened_floor_1p5": res["scores_tightened_floor_1p5"],
             "out": args.out}
    if "wave10_pre_asymptotic" in rep:
        brief["wave10_observed_order"] = rep["wave10_pre_asymptotic"]["observed_order"]
        brief["wave10_discrete_fin_model"] = rep["wave10_pre_asymptotic"]["discrete_fin_model"]
    print(json.dumps(brief, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
