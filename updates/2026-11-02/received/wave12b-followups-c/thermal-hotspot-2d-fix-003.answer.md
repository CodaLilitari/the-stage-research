# Deliverable: `thermal-hotspot-2d-fix-003` — diagnosis of the T_H "order 0.27", corrected convergence criterion, and reading of the executed study

Contributor note: written by Claude (via Red) on the wave-10 packet (Claude, via Red) that extends Coda's (Codex Lily) T0-HYP-1 contract; Coda's two-node reference and fixture numbers are hers. All executed numbers quoted below are Red's sandbox receipts (sha256 `ab66db0b…`, `afe808b6…`, `f00ce120…`). **Nothing in this packet has been executed by me**; every statement about what the new code will produce is a static expectation and is labelled as such. Model only — not empirical validation, not a safety or design statement.

---

## 1. Diagnosis: pre-asymptotic sequence, not round-off, not a coupling defect

Executed wave-10 sequence (H1, w = 5 mm, factor-2 refinement in z and y, uniform in-plane spacing dy = 5 / 2.5 / 1.25 mm):

| level | n | T_H (°C) | ΔT_H (K) | T_mid_centre (°C) | ΔT_mid (K) |
|---|---|---|---|---|---|
| r=1 | 101 | 33.843532 | | 32.821244 | |
| r=2 | 361 | 33.842843 | −6.890e-4 | 32.798093 | −2.315e-2 |
| r=4 | 1361 | 33.842272 | −5.713e-4 | 32.794176 | −3.917e-3 |

**(a) Not a round-off / solver-tolerance artefact.** The T_H differences are 0.69 mK and 0.57 mK. The direct solves have residual norms ~1e-13 W (receipts); with the smallest conductance eigenvalue of K ≳ 1e-4 W/K, the worst-case forward error is ≲ 1e-9 K, i.e. five orders of magnitude below the differences. The "T_H is dominated by the rear path" remark is true (4.42 of 5.1 W leave through R_rej; the patch moves T_H by only 1–11 mK in the study) but it makes T_H's *sensitivity* small, not its differences noisy. The 0.27 is a real, systematic number — just not an order of accuracy.

**(b) Not a defect at the lumped-node coupling.** The H coupling (A_j/(dz/2k) to every bottom cell) is exercised on every mesh by the two 1-D limits, both of which reproduce Coda's two-node numbers to 1e-9 (T_H, S, surface, front, rear; w = 0 and full-patch, open and blocked — tests passed). In 2-D the same per-column conductances are used; the lateral conductances are independently checked by the modal decay-length fit (fit/modal = 1.022 / 1.015 / 1.011 for H1/H2/H3). There is no mechanism by which the coupling could be exact in 1-D and inconsistent in 2-D.

**(c) The real cause: the sequence never resolved the lateral decay length.** T_H is set by the total front heat flow, whose only 2-D ingredient is the lateral exchange across the two patch edges, which lives on the unfaulted decay length ℓ_U = 0.682 mm (H1, executed modal value). The three levels have dy/ℓ_U = 7.3, 3.7, 1.8 — coarser than the structure at every level, so Richardson's premise (asymptotic error expansion) does not hold. This can be made quantitative with a closed-form *discrete fin*: for the cell-centred scheme a lateral mode decays per cell by λ with λ + 1/λ = 2 + (dy/ℓ)², and the series resistance between the two far fields is R_disc = dy·[1 + λ_U/(1−λ_U) + λ_F/(1−λ_F)] versus R_cont = ℓ_U + ℓ_F (ℓ_F = 1.616 mm inside the patch). The captured fraction of the resolved exchange is f = R_cont/R_disc:

| dy (mm) | 5 | 2.5 | 1.25 | 0.3125 | 0.156 | 0.078 |
|---|---|---|---|---|---|---|
| f | 0.413 | 0.663 | 0.865 | 0.988 | 0.997 | 0.9992 |

Apparent order predicted from (f₂−f₁)/(f₃−f₂): **0.31**; executed: **0.27**. The implied total lateral effect on T_H is e₁/(f₂−f₁) = 2.75 mK and e₂/(f₃−f₂) = 2.83 mK (consistent to 3 %), so the fully resolved T_H ≈ 33.84227 − (1−0.865)·2.83 mK ≈ **33.8419 °C**: the finest wave-10 level is still ~0.4 mK high. The expansion R_disc = R_cont + (dy²/8)(1/ℓ_U + 1/ℓ_F) + O(dy⁴) shows the scheme *is* second-order once dy ≲ ℓ_U; the sequence simply stopped before that regime.

**(d) Why T_mid_centre "showed 2.56".** The centre value is the mean of the two cells sharing y = L/2. At r = 1 those cells *are* the patch-edge cells (dy = w), at r = 2 they are one cell from the edge, at r = 4 three cells; with per-cell decay λ_F = 0.09 / 0.24 / 0.47 the edge's lateral imprint on the centre scales ≈ 1 → 0.24 → 0.10 (continuum limit e^{−w/ℓ_F} ≈ 0.045). That geometric sequence gives an apparent order log₂(0.76/0.14) ≈ 2.4 and an amplitude of ≈ 30 mK per unit (23.2/0.76 ≈ 3.9/0.14 — consistent), so the 2.56 is a mesh coincidence too; the r = 4 centre value is still ≈ 1.7 mK warm. T_mid_min and T_surf_min are the same column, hence identical orders.

**(e) Consequence for the study: none of its conclusions depend on it.** The predeclared 0.10 K criterion is met with margin ≥ 25× (finest-pair changes 0.57 mK, 3.9 mK). On the steady-study mesh (dy_fine = 0.5 mm, dy/ℓ_U = 0.73) the discrete-fin error in T_H is ≈ 2.8 % of 2.8 mK ≈ 0.1 mK and the centre error ≈ 1 mK — far inside every hypothesis margin except HYP1's smallest case (w = 1 mm, ΔT_H = +0.98 mK), where the under-resolution biases T_H *upward*, i.e. toward satisfying the lower bound, and the Rayleigh monotonicity argument covers the body-power part independently.

## 2. The fix (minimal diff + non-vacuous tests)

Corrected criterion, replacing "order ≥ 1.0 on whatever sequence is handy":

1. **Resolution precondition** (hard): at the coarsest level, max dy within 4 ℓ_U of a patch edge ≤ 0.5 ℓ_U. A sequence that fails it is *rejected*, not scored (the wave-10 sequence fails at 7.3).
2. **Noise floor** (explicit): differences below 1e-9 K are classified `below_noise` and the functional is declared converged on the absolute criterion instead of producing a meaningless order.
3. **Absolute criterion** (hard): finest-pair change ≤ 1 mK for T_H, T_mid_centre, T_surf_min (the study's 0.10 K criterion is kept and also reported).
4. **Order floor 1.0** (hard, predeclared, unchanged) for differences above the noise floor, with decreasing differences.
5. **Tightened floor 1.5** (separate test, labelled fix-003): the scheme is second-order by construction and by the discrete-fin expansion. This is the assertion that catches a first-order defect; a *mutation test* demonstrates it: shifting the fault boundary off the mesh faces by one cell (faulted area 2wD + 2 dy D, a first-order inconsistency of the kind a misaligned patch definition would produce) must give order ≈ 1 and fail the tightened floor.

Resolved sequence: graded `default_ymesh` with dy_fine = 0.3125 mm in the patch (dy/ℓ_U = 0.46), 6 mm fine margins, 5 mm coarse far field (exact in 1-D), z = (2r, 1, 2r), r = 1, 2, 4 (≈ 441 / 1585 / 5985 unknowns, banded direct solve; estimated ≈ 1 s per sequence in CPython — unmeasured).

Static expectations for Red to check (not claims): T_H ≈ 33.8419 at the finest level, finest-pair changes ≈ 7 µK (T_H) and tens of µK (T_mid_centre), both ≫ 1e-9 K; orders ≈ 2 (1.6–2.2 plausible); T_H monotonically decreasing with refinement; mutated sequence T_H order in 0.9–1.15. If the tightened test fails while the predeclared one passes, report the value — do not loosen the floor.

Files: a unified diff for `hotspot2d/study.py` and `tests/test_hotspot2d.py` (3 small hunks + removal of the old test method), one new module, one new test module, one notes addendum. `model.py` is untouched. If the patch does not apply mechanically (hunk line numbers are my count of the source; GNU `patch` tolerates offsets), the three edits are trivial to make by hand; the new module and tests run regardless, and `python -m hotspot2d.convergence --out <path>` produces the corrected refinement JSON standalone.

FILE: patches/fix003-refinement.diff
```diff
--- a/hotspot2d/study.py
+++ b/hotspot2d/study.py
@@ -17,6 +17,7 @@
 from typing import Dict, List
 
 from hotspot2d import model as M
+from hotspot2d import convergence as C
 
 PREDECLARED = {
     "extension": M.EXTENSION,
@@ -155,25 +156,13 @@
     return {"rows": out}
 
 
-def refinement_study() -> Dict[str, object]:
-    p = M.Params(stack="H1")
-    levels = []
-    for r in (1, 2, 4):
-        zm = M.build_zmesh(p, 2 * r, 1, 2 * r)
-        ym = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, 0.045, 0.055, 0.1], [9 * r, 2 * r, 9 * r]), 5e-3)
-        net = M.Network(p, zm, ym, True, True, p.P_body)
-        T, _ = M.solve_steady(net, "direct")
-        s = M.steady_summary(net, T)
-        levels.append({"refine": r, "n_unknowns": net.n, "T_H": s["T_H"], "T_mid_centre": s["T_mid_centre"],
-                       "T_mid_min": s["T_mid_min"], "T_surf_min": s["T_surf_min"]})
-    orders = {}
-    maxchange = {}
-    for key in ("T_H", "T_mid_centre", "T_mid_min", "T_surf_min"):
-        q = [lv[key] for lv in levels]
-        orders[key] = M.observed_order(q[0], q[1], q[2])
-        maxchange[key] = abs(q[1] - q[2])
-    return {"levels": levels, "observed_order": orders, "last_change_K": maxchange,
-            "criterion_0p10K_met_on_finest_pair": all(v <= 0.10 for v in maxchange.values())}
+def refinement_study() -> Dict[str, object]:
+    """fix-003: the wave-10 sequence (dy = 5/2.5/1.25 mm) never resolved the
+    unfaulted lateral decay length (0.68 mm for H1), so its T_H 'order' (0.27)
+    was pre-asymptotic. The scored sequence now satisfies dy <= ell_U/2 near
+    the patch edges at the coarsest level; the wave-10 sequence is kept as a
+    labelled diagnostic with a discrete-fin prediction of its apparent order."""
+    return C.refinement_study(M.Params(stack="H1"))
 
 
 def _hist(res: M.TransientResult, every: float = 10.0) -> Dict[str, List[float]]:
@@ -268,7 +257,8 @@
              "hypotheses": {k: v["all_pass"] for k, v in rep["steady"]["hypotheses"].items()},
              "spreading": [{k: r.get(k) for k in ("stack", "ell_modal_unfaulted_m", "fit_over_modal", "HYP5_pass")}
                            for r in rep["spreading"]["rows"]],
-             "refinement_orders": rep["refinement"]["observed_order"],
+             "refinement_orders_resolved": rep["refinement"]["resolved"]["observed_order"],
+             "refinement_precondition_met": rep["refinement"]["resolved"]["precondition_met"],
              "transient_rows": len(rep["transient"]["rows"]), "out": args.out}
     print(json.dumps(brief, indent=1, default=str))
     return 0
--- a/tests/test_hotspot2d.py
+++ b/tests/test_hotspot2d.py
@@ -126,28 +126,9 @@
             self.assertAlmostEqual(s["source_W"], 5.1, places=12)
             self.assertLess(abs(s["balance_W"]), 1e-9)
 
-    def test_mesh_refinement_observed_order(self):
-        """Factor-2 refinement in z and y; predeclared: order >= 1.0 for the
-        smooth functionals T_H and T_mid_centre, differences decreasing."""
-        p = M.Params(stack="H1")
-        q = {"T_H": [], "T_mid_centre": [], "T_mid_min": []}
-        for r in (1, 2, 4):
-            zm = M.build_zmesh(p, 2 * r, 1, 2 * r)
-            ym = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, 0.045, 0.055, 0.1], [9 * r, 2 * r, 9 * r]), 5e-3)
-            net = M.Network(p, zm, ym, True, True, 5.0)
-            T, _ = M.solve_steady(net, "direct")
-            s = M.steady_summary(net, T)
-            for k in q:
-                q[k].append(s[k])
-        for k in ("T_H", "T_mid_centre"):
-            e1, e2 = abs(q[k][0] - q[k][1]), abs(q[k][1] - q[k][2])
-            self.assertLess(e2, e1, msg=k)
-            order = M.observed_order(*q[k])
-            if order is not None:
-                self.assertGreaterEqual(order, 1.0, msg=f"{k}: observed order {order}")
-        # the patch is a cold spot over its centre in the open-rear case (model expectation)
-        ref = M.reference_1d_steady(p)
-        self.assertLess(q["T_mid_centre"][-1], ref["S"])
+    # test_mesh_refinement_observed_order (wave 10) was removed in fix-003: its
+    # sequence (dy = 5/2.5/1.25 mm) never resolved the lateral decay length, so
+    # the order it computed was pre-asymptotic. See tests/test_convergence_fix003.py.
 
 
 class TestTransient(unittest.TestCase):
```

FILE: hotspot2d/convergence.py
```python
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
```

FILE: tests/test_convergence_fix003.py
```python
"""fix-003: diagnosis of the wave-10 T_H 'order 0.27' and the corrected
mesh-convergence criterion. WAVE10_* fixtures are Red's executed numbers
(receipts afe808b6... / f00ce120..., Linux, CPython 3.13); everything else is
computed here. Model only."""
import math
import os
import sys
import unittest
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hotspot2d import model as M  # noqa: E402
from hotspot2d import convergence as C  # noqa: E402

WAVE10_T_H = (33.843532217632365, 33.842843219043225, 33.84227188231695)
WAVE10_T_MID_CENTRE = (32.821243935195, 32.79809332526317, 32.794176118033434)
WAVE10_ORDER_T_H = 0.27015975749952653
WAVE10_ORDER_T_MID_CENTRE = 2.5631528461192166
WAVE10_DY_M = (5e-3, 2.5e-3, 1.25e-3)


@lru_cache(maxsize=None)
def resolved_sequence(overhang_cells: int):
    return C.run_sequence(M.Params(stack="H1"), overhang_cells=overhang_cells)


class TestDiscreteFinModel(unittest.TestCase):
    def test_decay_factor_definition_and_limits(self):
        for x in (1e-3, 0.1, 0.5, 2.0, 10.0):
            lam = C.discrete_decay_factor(x)
            self.assertTrue(0.0 < lam < 1.0)
            self.assertAlmostEqual(lam + 1.0 / lam, 2.0 + x * x, places=9)
        self.assertAlmostEqual(C.discrete_decay_factor(1e-3), math.exp(-1e-3), delta=1e-6)
        self.assertAlmostEqual(C.discrete_decay_factor(10.0) * 102.0, 1.0, delta=0.02)

    def test_series_resistance_is_second_order_in_dy(self):
        for ell_u, ell_f in ((0.68e-3, 1.6e-3), (2.5e-3, 3.65e-3)):
            cont = ell_u + ell_f
            for dy in (1e-4, 5e-5):
                r = C.discrete_fin_series_resistance(dy, (ell_u, ell_f))
                second = dy * dy / 8.0 * (1.0 / ell_u + 1.0 / ell_f)
                self.assertGreater(r, cont)
                self.assertLess(abs(r - cont - second), 0.05 * second)
            self.assertAlmostEqual(C.exchange_fraction(1e-7, ell_u, ell_f), 1.0, delta=1e-6)


class TestWave10Diagnosis(unittest.TestCase):
    def test_wave10_sequence_violates_resolution_precondition_at_every_level(self):
        p = M.Params(stack="H1")
        ell_u = M.modal_spreading_length(p, p.r_c)
        for r in (1, 2, 4):
            zm, ym = C.wave10_level(p, r)
            self.assertGreater(C.edge_resolution(ym, ell_u), C.RESOLUTION_LIMIT, msg=f"refine {r}")

    def test_wave10_differences_are_far_above_the_noise_floor(self):
        rep = C.convergence_report(WAVE10_T_H)
        self.assertEqual(rep["status"], "order_defined")
        self.assertGreater(rep["e2_K"], 1e5 * C.NOISE_FLOOR_K)
        self.assertAlmostEqual(rep["order"], WAVE10_ORDER_T_H, places=9)
        self.assertAlmostEqual(C.convergence_report(WAVE10_T_MID_CENTRE)["order"], WAVE10_ORDER_T_MID_CENTRE, places=9)

    def test_discrete_fin_model_reproduces_executed_T_H_order(self):
        p = M.Params(stack="H1")
        ell_u = M.modal_spreading_length(p, p.r_c)
        ell_f = M.modal_spreading_length(p, p.r_fault)
        pred = C.predicted_pre_asymptotic_order(WAVE10_DY_M, ell_u, ell_f)
        self.assertLess(abs(pred - WAVE10_ORDER_T_H), 0.15, msg=f"predicted {pred}")
        f = [C.exchange_fraction(d, ell_u, ell_f) for d in WAVE10_DY_M]
        e1, e2 = abs(WAVE10_T_H[0] - WAVE10_T_H[1]), abs(WAVE10_T_H[1] - WAVE10_T_H[2])
        shift1, shift2 = e1 / (f[1] - f[0]), e2 / (f[2] - f[1])
        self.assertLess(abs(shift1 - shift2) / shift2, 0.10)   # one lateral effect explains both pairs
        self.assertTrue(2e-3 < shift2 < 4e-3, msg=f"implied lateral effect on T_H {shift2} K")

    def test_wave10_coarsest_level_is_reproduced(self):
        p = M.Params(stack="H1")
        zm, ym = C.wave10_level(p, 1)
        lv = C.solve_level(p, zm, ym)
        self.assertEqual(lv["n_unknowns"], 101)
        self.assertAlmostEqual(lv["T_H"], WAVE10_T_H[0], delta=1e-9)
        self.assertAlmostEqual(lv["T_mid_centre"], WAVE10_T_MID_CENTRE[0], delta=1e-9)


class TestResolvedRefinement(unittest.TestCase):
    """Corrected predeclared criterion: precondition, noise floor, absolute
    tolerance, order floor 1.0 (unchanged) on a resolved sequence."""

    def test_precondition_and_predeclared_criterion(self):
        seq = resolved_sequence(0)
        self.assertLessEqual(seq["precondition_dy_over_ell_coarsest"], C.RESOLUTION_LIMIT)
        for lv in seq["levels"]:
            self.assertAlmostEqual(lv["faulted_area_m2"], 2 * 5e-3 * M.PANEL_SIDE, places=12)
            self.assertLess(abs(lv["balance_W"]), 1e-9)
        for k in ("T_H", "T_mid_centre", "T_surf_min"):
            rep = seq["reports"][k]
            self.assertLessEqual(rep["e2_K"], C.ABS_TOL_FINEST_PAIR_K, msg=f"{k}: {rep}")
            self.assertNotEqual(rep["status"], "not_decreasing", msg=f"{k}: {rep}")
            if rep["status"] == "order_defined":
                self.assertGreaterEqual(rep["order"], C.ORDER_FLOOR_PREDECLARED, msg=f"{k}: {rep}")

    def test_resolved_values_confirm_the_diagnosis(self):
        seq = resolved_sequence(0)
        p = M.Params(stack="H1")
        ref = M.reference_1d_steady(p)
        th = [lv["T_H"] for lv in seq["levels"]]
        # more captured lateral exchange -> lower T_H, monotonically
        self.assertGreater(th[0], th[1])
        self.assertGreater(th[1], th[2])
        # resolved T_H lies below the under-resolved wave-10 finest value ...
        self.assertLess(th[-1], WAVE10_T_H[-1] - 1e-4)
        # ... and above the unfaulted reference (HYP1 lower bound)
        self.assertGreater(th[-1], ref["H"])
        # cool spot over the patch centre (open rear), as in the executed study
        self.assertLess(seq["levels"][-1]["T_mid_centre"], ref["S"])

    def test_tightened_second_order_floor_fix003(self):
        """Tightened in fix-003 (scheme is second order; discrete-fin expansion).
        If this fails while the predeclared test passes, report the value; do
        not loosen either floor."""
        seq = resolved_sequence(0)
        for k in ("T_H", "T_mid_centre"):
            rep = seq["reports"][k]
            if rep["status"] == "order_defined":
                self.assertGreaterEqual(rep["order"], C.ORDER_FLOOR_TIGHTENED, msg=f"{k}: {rep}")

    def test_criterion_rejects_a_first_order_edge_defect(self):
        """Non-vacuity check: a fault boundary one cell off the mesh faces is a
        first-order inconsistency; the tightened floor must reject it."""
        clean, defective = resolved_sequence(0), resolved_sequence(1)
        for a, b in zip(clean["levels"], defective["levels"]):
            self.assertGreater(b["faulted_area_m2"], a["faulted_area_m2"])
            self.assertGreater(b["T_H"], a["T_H"])     # more faulted area -> hotter H
        rep = defective["reports"]["T_H"]
        self.assertEqual(rep["status"], "order_defined", msg=str(rep))
        self.assertLess(rep["order"], C.ORDER_FLOOR_TIGHTENED, msg=str(rep))
        self.assertTrue(0.7 <= rep["order"] <= 1.3, msg=f"expected ~first order, got {rep}")


if __name__ == "__main__":
    unittest.main()
```

FILE: hotspot2d/NOTES_fix003.md
```markdown
# 2D-PATCH-EXT-1 — fix-003 addendum (to be read with NOTES.md §4 and §6)

Written by Claude (via Red) after Red's execution of the wave-10 packet
(receipts ab66db0b…, afe808b6…, f00ce120…). Model only; nothing here was
executed by the author.

## 8. Mesh-refinement test: what the 0.27 meant and the corrected criterion

- The wave-10 sequence (H1, w = 5 mm, dy = 5/2.5/1.25 mm) had dy/ell_U =
  7.3, 3.7, 1.8 (ell_U = 0.682 mm, modal). T_H depends on the lateral exchange
  across the patch edges, captured only to a fraction f(dy) = (ell_U+ell_F)/
  [dy(1 + sum lambda/(1-lambda))], lambda + 1/lambda = 2 + (dy/ell)^2:
  f = 0.41, 0.66, 0.86. Predicted apparent order 0.31; executed 0.27. Implied
  total lateral effect on T_H ≈ 2.8 mK; resolved T_H ≈ 33.8419 °C (finest
  wave-10 level ≈ 0.4 mK high). Not round-off (differences ~1e5 x the solver
  noise), not a coupling defect (1-D limits exact to 1e-9 on every mesh).
- T_mid_centre's apparent 2.56 is a mesh coincidence: at r = 1 the two centre
  cells are the patch-edge cells (dy = w); the edge imprint falls ~1 → 0.24 →
  0.10 (continuum 0.045), giving an apparent ≈ 2.4 and ≈ 1.7 mK residual error.
- Corrected criterion (hotspot2d/convergence.py, tests/test_convergence_fix003.py):
  precondition max dy <= ell_U/2 within 4 ell_U of the edges at the coarsest
  level (else the sequence is rejected, not scored); noise floor 1e-9 K; finest
  pair change <= 1 mK (hard) and <= 0.10 K (study criterion, kept); order >= 1.0
  (predeclared, unchanged); order >= 1.5 reported as a separate tightened test;
  a deliberately defective sequence (fault boundary one cell off the faces,
  first order) must fail the tightened floor.
- Effect on the executed study: none of its conclusions depend on the artefact;
  steady-mesh errors are ~0.1 mK (T_H) and ~1 mK (centre) by the same model.

## 9. HYP6 (blocked rear) — expectation corrected by the executed results

NOTES §6 expected the patch to barely change the front exit because 1/h >>
r_fault. That is true per unit area (the patch cuts the local front flux by
~13 %), but with the rear blocked the deficit over area fraction f must leave
through the unfaulted area: q_u/q_uniform = 1/[(1-f) + f R_u/R_f]. Predicted
surface excess (P/hA)(q_u/q_uniform - 1): H1 f = 0.1 → +0.86 K (criterion 0.5
K: fails, as executed), H3 f = 0.4 → +3.3 K (executed +2.98 K surface, +3.16 K
film; lateral spreading trims the peak). Uniform F2 bounds T_H (HYP1 passed
in all 35 cases) but not the local film/surface maxima, which occur beside
the patch over the unfaulted area. Section 6's "strongest justified claim"
must be narrowed accordingly (see the fix-003 answer, section 3).
```

## 3. What the executed study says (receipts; 31 of 35 steady rows and 2 of 6 transient rows were omitted from the receipt for size, so numbers below are from the visible rows plus the per-hypothesis pass/fail flags)

**Lumped-node temperature T_H — uniform F2 is an upper bound.** HYP1 passed in all 35 cases (3 stacks × open/blocked, planar + H2 axisymmetric, five widths): T_H(ref) ≤ T_H(w) ≤ T_H(uniform F2), non-decreasing in w. H1 open: +0.98 / +2.96 / +10.7 mK for w = 1 / 2 / 5 mm against +137 mK for uniform F2; H3 blocked, w = 20 mm: 99.91 °C between 96.56 (ref) and 106.46 (F2). Transient peaks agree (H1 w = 20 mm: 33.900 °C vs 34.017 uniform F2).

**Local temperature over the patch — a cool spot, never a hot spot (all 35 cases, HYP2).** Open rear, H1: film midplane at the centre −0.32 / −0.59 / −0.91 K (w = 1 / 2 / 5 mm) versus −0.87 K for uniform F2 (fractions 0.37, 0.67, 1.04); surface over the patch −0.28 / −0.55 / −0.89 K. For w ≥ 5 mm the local deficit slightly *exceeds* the uniform-F2 deficit because T_H rises less than in uniform F2; HYP2's bound S_F2 − [T_H(F2) − T_H(w)] (≈ −1.0 K for H1) holds. Blocked rear, H3, w = 20 mm: centre film −5.4 K, surface −5.1 K below the uniform values.

**Local maxima beside the patch — uniform F2 is NOT an envelope.** Open rear: the film/surface over the unfaulted area rise by +1 to +10 mK (H1, w ≤ 5 mm, steady) and by +67 / +66 mK (film / surface, H1, w = 20 mm, transient peak at ≈ 646 s) above the F0 peaks — small, but above both F0 and uniform F2 (which lowers the whole film by 0.87 K). Blocked rear: HYP6 **failed** for w ≥ 5 mm (H1 w = 5 mm fails; w = 1, 2 mm pass; H3 w = 20 mm: film max 95.86 vs 92.69 °C uniform, +3.16 K; surface max 91.73 vs 88.75, +2.98 K). The mechanism is the one §6 named as the "most important counterexample candidate": when the front is the only exit, the flux the patch rejects must pass through the unfaulted area, q_u/q_uniform = 1/[(1−f) + f·R_u/R_f] with R_u/R_f = 0.867 (H1) / 0.876 (H3); this closed form gives +0.86 K at f = 0.1 (H1) and +3.3 K at f = 0.4 (H3), matching the executed failures and magnitudes. The §6 "upper envelope" statement should be narrowed to T_H only; the hot spot is beside the patch, of order (P/hA)·f·(1 − R_u/R_f) for small f, and in this contract only matters when the rear is already blocked (T_H ≈ 100 °C). The 40 / 60 °C arbitrary comparators are not crossed in any open-rear case (transient, all stacks, both widths).

**Sensor detectability (open rear, fault at 600 s, 2-s samples; thresholds are arbitrary study comparators).** A film-midplane sensor over the patch centre sees ≥ 0.1 K at the first sample after the fault (602 s) for every visible case (H1 −0.142 K at w = 2 mm, −0.145 K at 20 mm; H2 −0.116 K; H3 −0.124 K), essentially simultaneously with the uniform-F2 1-D case (602 s), because the response is the fast local redistribution in the stack, not the slow T_H response; 0.5 K is reached at 618 / 612 s (H1, w = 2 / 20 mm) and 656 s (H3, 20 mm), and never for H2 at w = 2 mm (steady deficit below 0.5 K through lateral levelling; uniform F2 would reach it at 628 s). Steady, HYP4 passed: centre deviation ≥ 0.5 K for w ≥ 5 mm, < 0.5 K for w = 1 mm, all stacks. An edge sensor (panel edge, ≥ 30 mm away) never reaches 0.1 K in H1/H2 and only marginally in H3 at w = 20 mm (−0.1000 K at 1026 s, during cool-down after body-off); steady HYP3 passed (< 0.1 K for all w ≤ 20 mm, open rear). With the rear blocked, both sensors see the patch strongly (H3, w = 20 mm: edge +3.16 K, centre −5.38 K).

**Verification status of the executed packet.** 20 tests, 1 failure (the pre-asymptotic order test addressed here); steady balances |source − front − rear| ≤ 7e-13 W; transient energy residuals ≤ 4e-9 J over 4860 J injected; state continuity at 600 s exact; time refinement 2 → 1 s changes ≤ 0.026 K (criterion 0.05 K met); lateral decay lengths from the FV solution within 1.1–2.2 % of the two-layer modal prediction for all stacks (HYP5 passed; fin estimate within factor 2). Limits of §7 still apply (idealised isothermal H lump — no hot spot *in* H by construction, assumed h, no radiation, equal-area disc, no sweeps).

## 4. How to run (Red)

1. Apply `patches/fix003-refinement.diff` (or make the three edits by hand), add `hotspot2d/convergence.py`, `tests/test_convergence_fix003.py`, `hotspot2d/NOTES_fix003.md`.
2. `python -m unittest tests.test_hotspot2d tests.test_convergence_fix003` (expected: 19 + 9 tests; added runtime a few seconds, unmeasured).
3. `python -m hotspot2d.convergence --out <path>/fix003_refinement.json` for the corrected refinement record standalone (also produced inside `study.py` after the patch; the full study need not be re-run for this task).

Please return: the test receipt, the brief JSON, and in particular `resolved_T_H_levels`, `resolved_observed_order`, `resolved_last_change_K`, and `wave10_discrete_fin_model.extrapolated_minus_resolved_finest_K` (expected within a few tenths of a mK of zero; informational, not asserted).

## 5. Not implemented / open

- `NOTES.md` §6 text is not patched in place; the addendum file carries the corrected HYP6 reading and the narrowed "strongest claim".
- Resolved refinement is run for H1 only (smallest ℓ_U, the most demanding case); H2/H3 not run.
- The non-vacuity check covers one defect class (first-order edge misalignment); an inconsistent coupling with a mesh-independent error would be caught by the existing 1-D exactness tests, not by an order test — stated, not re-tested.
- Transient spatial refinement, axisymmetric refinement, F3/F4/F5 cases, property sweeps and all other §0 omissions remain omitted.
- No re-execution of the full study; whether to re-run it (≈ 13.5 s + a few seconds) is Red's call.