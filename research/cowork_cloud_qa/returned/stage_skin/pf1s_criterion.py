"""
PF1-S companion: the identified parameter group, its critical value, and a
measurable failure criterion for a first perfused skin module.

Runs after pf1s_skin.py and reuses its solver.

Three questions:
  1. What does this evidence actually identify? (Not q, h or D separately.)
  2. Where is the pass/fail boundary in that identified group?
  3. What measurement, with instruments that exist, would falsify the design?

Run:  python3 -I pf1s_criterion.py
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

import numpy as np

from pf1s_skin import (
    Case, solve_case, ALPHA_O2, C_AIR_EQUIL, C_LUMEN_IN, LX, THRESHOLD,
    P_SURF_LOWER_BOUND, Q_CELL_HDF, D_EPI_DEFAULT, H_EPI_DEFAULT, KM_DEFAULT,
)

ROOT = Path(__file__).resolve().parent

BASE = Case(
    q_epi=9.72e-3, q_derm=2e13 * Q_CELL_HDF, D_derm=2.0e-9, D_epi=D_EPI_DEFAULT,
    P_wall=5e-5, P_surf=P_SURF_LOWER_BOUND, H=1000e-6, h_epi=H_EPI_DEFAULT,
    Km=KM_DEFAULT,
)


def thiele_epi(c: Case) -> float:
    return c.q_epi * c.h_epi ** 2 / (c.D_epi * c.C_air)


def min_o2(c: Case) -> float:
    return solve_case(c)["min_free_O2_mol_m3"]


def critical_thiele(base: Case, vary: str = "q_epi") -> dict:
    """Bisect on epidermal demand to find where the minimum crosses THRESHOLD."""
    lo, hi = 1e-4, 1e2  # mol m^-3 s^-1
    if min_o2(replace(base, q_epi=lo)) < THRESHOLD:
        return {"error": "threshold already breached at the low end"}
    if min_o2(replace(base, q_epi=hi)) > THRESHOLD:
        return {"error": "threshold never breached at the high end"}
    for _ in range(60):
        mid = np.sqrt(lo * hi)
        if min_o2(replace(base, q_epi=mid)) >= THRESHOLD:
            lo = mid
        else:
            hi = mid
        if hi / lo < 1 + 1e-9:
            break
    qcrit = np.sqrt(lo * hi)
    return {
        "q_epi_critical_mol_m3_s": qcrit,
        "thiele_epi_critical": thiele_epi(replace(base, q_epi=qcrit)),
    }


def main():
    out = {}

    # ---- 1. what the evidence identifies, tested rather than asserted ------
    # Claim under test: the field depends only on phi2 = q h^2 / (D C), so
    # scaling q and D by a common factor should change nothing. That is exactly
    # true for a HOMOGENEOUS slab and must be checked, not assumed, for the
    # LAYERED geometry, where the layer conductance ratio enters as well.

    def scan(ref: Case, label: str):
        ref_min = min_o2(ref)
        cases = []
        for factor in [0.25, 0.5, 2.0, 4.0]:
            scaled = replace(ref, q_epi=ref.q_epi * factor, D_epi=ref.D_epi * factor,
                             **({"q_derm": ref.q_derm * factor,
                                 "D_derm": ref.D_derm * factor}
                                if label == "homogeneous_single_layer" else {}))
            cases.append({
                "factor": factor,
                "phi2_ref": thiele_epi(ref),
                "phi2_scaled": thiele_epi(scaled),
                "min_ref": ref_min,
                "min_scaled": min_o2(scaled),
                "relative_difference": abs(min_o2(scaled) - ref_min) / C_AIR_EQUIL,
            })
        return {"cases": cases,
                "max_relative_difference": max(c["relative_difference"] for c in cases)}

    # (a) homogeneous single layer, Dirichlet-like wall, sealed surface: the
    #     textbook case where the single-group reduction should hold exactly.
    homo = replace(BASE, h_epi=BASE.H, q_derm=BASE.q_epi, D_derm=BASE.D_epi,
                   P_wall=1e2, P_surf=0.0)
    res_homo = scan(homo, "homogeneous_single_layer")

    # (b) the actual layered construct with its finite wall and finite surface.
    res_layered = scan(replace(BASE, P_surf=P_SURF_LOWER_BOUND), "layered")

    out["identifiability_invariance"] = {
        "homogeneous_single_layer": res_homo,
        "layered_construct": res_layered,
        "statement": (
            "For a homogeneous slab the single-group reduction holds to solver "
            "tolerance: scaling demand and diffusivity together leaves the field "
            "unchanged, so q and D are not separately identifiable there. In the "
            "LAYERED construct the same scaling moves the minimum by up to "
            f"{100 * res_layered['max_relative_difference']:.0f}% of the inlet "
            "concentration, so phi2 alone does NOT close the problem. The layered "
            "geometry is governed by at least phi2_epi together with the layer "
            "conductance ratio D_epi/D_derm, the wall and surface Biot numbers, "
            "and the thickness ratios h_epi/H and Lx/H. The practical consequence "
            "is stronger, not weaker, than a single-group claim: an experiment "
            "that reports a skin 'qmax' without independently pinning epidermal "
            "thickness, epidermal diffusivity AND the dermal diffusivity it sits "
            "on has not identified a transportable parameter."
        ),
    }

    # ---- 2. critical value of the identified group ------------------------
    crit = {}
    for label, c in {
        "sealed_surface": replace(BASE, P_surf=0.0),
        "barrier_intact_stucker": replace(BASE, P_surf=P_SURF_LOWER_BOUND),
        "open_air_liquid_interface": replace(BASE, P_surf=1e-3),
    }.items():
        crit[label] = critical_thiele(c)
    out["critical_thiele"] = crit

    # literature readings placed against that boundary
    readings = {
        "textbook_resting_skin_bulk": 3.0e-3,
        "balu_as_read_by_collaborator_umol": 9.72e-3,
        "balu_recomputed_from_own_inputs": 1.0e-1,
        "balu_as_printed_mmol": 9.72,
    }
    out["literature_readings_vs_boundary"] = {
        k: {
            "q_epi_mol_m3_s": v,
            "phi2_epi": thiele_epi(replace(BASE, q_epi=v)),
        }
        for k, v in readings.items()
    }
    span = max(readings.values()) / min(readings.values())
    out["literature_span_factor"] = span

    # ---- 3. the measurable oxygen budget ----------------------------------
    # Wall flux per unit channel wall area, and the atmospheric share.
    budget = []
    for dem_label, q in readings.items():
        if dem_label == "balu_as_printed_mmol":
            continue
        for surf_label, Ps in {
            "sealed": 0.0,
            "barrier_intact_stucker": P_SURF_LOWER_BOUND,
            "open_air_liquid_interface": 1e-3,
        }.items():
            c = replace(BASE, q_epi=q, P_surf=Ps)
            r = solve_case(c)
            # per unit z-depth values; convert wall term to a flux per wall area
            wall_flux = (r["delivery_mol_s_per_m_depth"]
                         * (1.0 - (0.0 if np.isnan(r["surface_fraction_of_delivery"])
                                   else r["surface_fraction_of_delivery"]))) / c.H
            budget.append({
                "demand_case": dem_label,
                "surface_case": surf_label,
                "min_pO2_mmHg": r["min_pO2_mmHg"],
                "atmospheric_share_of_delivery": (
                    0.0 if np.isnan(r["surface_fraction_of_delivery"])
                    else r["surface_fraction_of_delivery"]
                ),
                "circuit_flux_per_wall_area_mol_m2_s": wall_flux,
                "total_consumption_mol_s_per_m_depth": r["consumption_mol_s_per_m_depth"],
            })
    out["oxygen_budget"] = budget

    # paired sealed/open contrast at each demand reading - the falsification test
    paired = []
    for dem_label, q in readings.items():
        if dem_label == "balu_as_printed_mmol":
            continue
        sealed = solve_case(replace(BASE, q_epi=q, P_surf=0.0))
        intact = solve_case(replace(BASE, q_epi=q, P_surf=P_SURF_LOWER_BOUND))
        openali = solve_case(replace(BASE, q_epi=q, P_surf=1e-3))
        paired.append({
            "demand_case": dem_label,
            "min_pO2_sealed_mmHg": sealed["min_pO2_mmHg"],
            "min_pO2_barrier_intact_mmHg": intact["min_pO2_mmHg"],
            "min_pO2_open_ali_mmHg": openali["min_pO2_mmHg"],
            "sealing_drop_from_intact_pct": 100 * (1 - sealed["min_pO2_mmHg"] / intact["min_pO2_mmHg"]),
            "sealing_drop_from_open_pct": 100 * (1 - sealed["min_pO2_mmHg"] / openali["min_pO2_mmHg"]),
            "circuit_share_sealed": 1.0,
            "circuit_share_intact": 1 - intact["surface_fraction_of_delivery"],
            "circuit_share_open": 1 - openali["surface_fraction_of_delivery"],
        })
    out["paired_seal_test"] = paired

    out["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    (ROOT / "pf1s_criterion.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )

    # ---- console ----------------------------------------------------------
    print("=" * 78)
    print("PF1-S CRITERION ANALYSIS")
    print("=" * 78)
    print()
    print("1. WHAT THE EVIDENCE IDENTIFIES")
    print("   " + out["identifiability_invariance"]["statement"].replace(". ", ".\n   "))
    print(f"   homogeneous slab, max relative difference under common scaling: "
          f"{out['identifiability_invariance']['homogeneous_single_layer']['max_relative_difference']:.3e}")
    print(f"   layered construct, same test:                                   "
          f"{out['identifiability_invariance']['layered_construct']['max_relative_difference']:.3e}")
    print()
    print("2. CRITICAL VALUE OF THE IDENTIFIED GROUP")
    for k, v in crit.items():
        if "error" in v:
            print(f"   {k:<28s} {v['error']}")
        else:
            print(f"   {k:<28s} q_epi_crit={v['q_epi_critical_mol_m3_s']:.4g} mol/m^3/s"
                  f"   phi2_crit={v['thiele_epi_critical']:.3f}")
    print()
    print("   Literature readings placed against that boundary:")
    for k, v in out["literature_readings_vs_boundary"].items():
        print(f"     {k:<38s} q={v['q_epi_mol_m3_s']:<9.4g} phi2={v['phi2_epi']:.4g}")
    print(f"   Span of the literature readings: {span:.0f}x")
    print()
    print("3. MEASURABLE OXYGEN BUDGET (Rhee geometry, H=1 mm, mid wall)")
    print(f"   {'demand':<38s} {'surface':<26s} {'minpO2':>8s} {'atm share':>10s} {'circuit flux':>14s}")
    for b in out["oxygen_budget"]:
        print(f"   {b['demand_case']:<38s} {b['surface_case']:<26s} "
              f"{b['min_pO2_mmHg']:8.2f} {100*b['atmospheric_share_of_delivery']:9.2f}% "
              f"{b['circuit_flux_per_wall_area_mol_m2_s']:14.3e}")
    print()
    print("4. PAIRED SEAL TEST - the falsification contrast")
    for p in out["paired_seal_test"]:
        print(f"   {p['demand_case']:<38s} sealed {p['min_pO2_sealed_mmHg']:7.2f}  "
              f"intact {p['min_pO2_barrier_intact_mmHg']:7.2f}  open {p['min_pO2_open_ali_mmHg']:7.2f}  "
              f"| circuit share intact {100*p['circuit_share_intact']:5.1f}%  open {100*p['circuit_share_open']:5.1f}%")
    print()


if __name__ == "__main__":
    main()
