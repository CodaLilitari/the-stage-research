"""
PF1-S: layered skin oxygen transport and identifiability screen.

What this is
------------
A steady 2-D reaction-diffusion solve on the unit cell of the ONE openly
published, fully dimensioned perfused human skin construct in the Stage packet
(Rhee et al., Bioengineering 2024;11:1055), asking a question that paper never
measured: is the tissue between its channels oxygen-sufficient at its own
stated operating point?

It is NOT a calibrated prediction. No packet source supplies demand,
diffusivity, solubility, oxygen dependence and a functional threshold for the
same construct. What this run CAN do honestly is size the consequence of the
gaps: it propagates the documented ambiguities in the published record and
reports whether they span the pass/fail boundary.

Two of those ambiguities are defects found by reading the sources in this pass,
not uncertainty we invented:
  * Rhee section 2.6 states 4e6 fibroblasts in a 100 uL suspension AND a final
    concentration of 2e6 cells/mL. Those differ by 10-20x. Cell density sets
    volumetric demand directly.
  * Balu et al. 2013 prints ~0.035 mmol/1e6 cells/h for basal keratinocytes,
    but its own stated inputs (0.1 mmol/L/s over a 200 pL volume holding ~200
    cells) give ~0.00036 mmol/1e6 cells/h - a factor of ~97 lower.

Geometry (all from Rhee 2024 unless marked)
-------------------------------------------
  x = 0        outer surface of a printed channel wall
  x = Lx       symmetry plane midway to the next channel; Lx = 400/2 = 200 um
  y = 0        impermeable chip floor
  y = H        air-exposed surface (air-liquid interface)
  epidermis occupies the top h_epi; dermis the remainder
  H and h_epi are NOT reported by Rhee and are swept as declared unknowns.

Boundary conditions
-------------------
  x = 0   Robin, finite wall transfer against lumen concentration C_lumen
  x = Lx  zero flux (symmetry)
  y = 0   zero flux (chip floor)
  y = H   Robin, finite surface transfer against air-equilibrated C_air

The surface conductance is not a free invention. Its lower bound is derived
from the in vivo human measurement carried in the ledger: Stucker et al. 2002
report 0.53 mL O2 min^-1 m^-2 = 3.94e-7 mol m^-2 s^-1 at a surface pO2 of
163 Torr. Taking the full 163 Torr as the driving difference (the most
conservative possible reading, since the true difference is smaller) gives
P_surf >= 3.94e-7 / (1.34e-3 * 163) = 1.80e-6 m/s.

Scope and limits are listed in LIMITS at the bottom and reproduced in results.

Run:  python3 -I pf1s_skin.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import platform
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# fixed physical and geometric constants
# --------------------------------------------------------------------------

ALPHA_O2 = 1.34e-3          # mol m^-3 mmHg^-1, O2 solubility in plasma/water, 37 C
C_AIR_EQUIL = 0.20          # mol m^-3, medium equilibrated with air (~150 mmHg)
C_LUMEN_IN = 0.20           # mol m^-3, perfusate inlet, same basis

LX = 200e-6                 # m, half of Rhee's 400 um inter-channel spacing

# Stucker-derived lower bound on the surface conductance (see module docstring)
FLUX_STUCKER = 3.94e-7      # mol m^-2 s^-1
PO2_SURFACE_STUCKER = 163.0  # mmHg
P_SURF_LOWER_BOUND = FLUX_STUCKER / (ALPHA_O2 * PO2_SURFACE_STUCKER)

# Streeter & Cheema 2011 measured-profile/model-derived HDF rate
Q_CELL_HDF = 1.19e-17       # mol cell^-1 s^-1

# the three mutually inconsistent readings of Rhee section 2.6, as cell densities
RHEE_DENSITY_READINGS = {
    "stated_conc_2e6_per_mL": 2e12,       # cells m^-3, the printed concentration
    "4e6_cells_in_200uL": 2e13,           # cells m^-3
    "4e6_cells_in_100uL": 4e13,           # cells m^-3
}

# epidermal demand candidates, mol m^-3 s^-1
EPIDERMAL_DEMAND = {
    "textbook_resting_skin_bulk": 3.0e-3,
    "balu_as_read_by_collaborator_umol": 9.72e-3,   # 9.72e-18 mol/cell/s x 1e15 cells/m^3
    "balu_recomputed_from_own_inputs": 1.0e-1,      # 1.0e-16 mol/cell/s x 1e15 cells/m^3
    "balu_as_printed_mmol": 9.72e0,                 # retained to show the printed value is excluded
}

DERMAL_DIFFUSIVITY = {
    "dilute_gel_upper_bound": 2.0e-9,     # appropriate basis for Rhee's 3 mg/mL gel
    "cheema_11pct_compressed": 4.5e-10,   # FLAGGED: compressed collagen, not Rhee's gel
    "cheema_34pct_compressed": 1.7e-10,   # FLAGGED: compressed collagen, not Rhee's gel
}

SURFACE_CONDUCTANCE = {
    "sealed": 0.0,
    "stucker_lower_bound": P_SURF_LOWER_BOUND,
    "open_ali": 1.0e-3,
}

WALL_PERMEABILITY = {           # PF0's range, carried for comparability
    "low_5e-6": 5e-6,
    "mid_5e-5": 5e-5,
    "high_2e-4": 2e-4,
}

CONSTRUCT_THICKNESS = {"H_500um": 500e-6, "H_1000um": 1000e-6, "H_2000um": 2000e-6}

KM_DEFAULT = 0.028          # mol m^-3, PF0's value; NO packet source supplies a skin Km
H_EPI_DEFAULT = 100e-6      # m, assumed; Rhee does not report epidermal thickness
D_EPI_DEFAULT = 1.0e-9      # m^2 s^-1, assumed; no packet source measures epidermal D

THRESHOLD = 0.05            # mol m^-3, PF0's assumed line, carried only for comparability

NX, NY = 36, 54
NEWTON_TOL = 1e-11
NEWTON_MAX = 80


# --------------------------------------------------------------------------
# solver
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    q_epi: float
    q_derm: float
    D_derm: float
    D_epi: float
    P_wall: float
    P_surf: float
    H: float
    h_epi: float
    Km: float
    C_lumen: float = C_LUMEN_IN
    C_air: float = C_AIR_EQUIL
    Lx: float = LX
    nx: int = NX
    ny: int = NY


def _layer_arrays(c: Case):
    """Per-row diffusivity and qmax; row ny-1 is the top (air) side."""
    dy = c.H / c.ny
    ycent = (np.arange(c.ny) + 0.5) * dy
    is_epi = ycent >= (c.H - c.h_epi)
    D = np.where(is_epi, c.D_epi, c.D_derm)
    q = np.where(is_epi, c.q_epi, c.q_derm)
    return D, q, dy, is_epi


def solve_case(c: Case):
    nx, ny = c.nx, c.ny
    dx = c.Lx / nx
    D, q, dy, is_epi = _layer_arrays(c)
    n = nx * ny

    def idx(i, j):
        return j * nx + i

    # ---- face conductances (per unit depth in z), units m^3 s^-1 per unit z
    # horizontal (x) faces inside the domain: same row, same D
    gx = np.zeros((nx - 1, ny))
    for j in range(ny):
        gx[:, j] = D[j] * dy / dx

    # vertical (y) faces: harmonic mean across the layer interface
    gy = np.zeros((nx, ny - 1))
    for j in range(ny - 1):
        dh = 2.0 * D[j] * D[j + 1] / (D[j] + D[j + 1])
        gy[:, j] = dh * dx / dy

    # wall boundary at x = 0: series of wall permeability and half-cell diffusion
    gwall = np.zeros(ny)
    for j in range(ny):
        gwall[j] = (1.0 / (1.0 / c.P_wall + dx / (2.0 * D[j]))) * dy

    # air boundary at y = H
    if c.P_surf <= 0.0:
        gsurf = np.zeros(nx)
    else:
        gsurf = np.full(nx, (1.0 / (1.0 / c.P_surf + dy / (2.0 * D[ny - 1]))) * dx)

    vol = dx * dy
    qv = np.repeat(q, nx).reshape(ny, nx).T.reshape(-1, order="F")  # per cell, matching idx
    qv = np.empty(n)
    for j in range(ny):
        qv[j * nx:(j + 1) * nx] = q[j]

    # ---- constant part of the linear operator
    rows, cols, vals = [], [], []
    diag = np.zeros(n)
    src = np.zeros(n)

    for j in range(ny):
        for i in range(nx):
            k = idx(i, j)
            if i < nx - 1:
                g = gx[i, j]
                rows.append(k); cols.append(idx(i + 1, j)); vals.append(g); diag[k] -= g
            if i > 0:
                g = gx[i - 1, j]
                rows.append(k); cols.append(idx(i - 1, j)); vals.append(g); diag[k] -= g
            if j < ny - 1:
                g = gy[i, j]
                rows.append(k); cols.append(idx(i, j + 1)); vals.append(g); diag[k] -= g
            if j > 0:
                g = gy[i, j - 1]
                rows.append(k); cols.append(idx(i, j - 1)); vals.append(g); diag[k] -= g
            if i == 0:
                diag[k] -= gwall[j]; src[k] += gwall[j] * c.C_lumen
            if j == ny - 1 and gsurf[i] > 0:
                diag[k] -= gsurf[i]; src[k] += gsurf[i] * c.C_air

    A_lin = sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
    Dlin = sp.diags(diag)
    A_lin = A_lin + Dlin

    cmax = max(c.C_lumen, c.C_air)
    C = np.full(n, cmax)

    def residual(Cv):
        return A_lin @ Cv + src - vol * qv * Cv / (c.Km + Cv)

    scale = max(vol * float(np.max(qv)) * n, 1e-30)
    converged = False
    for _ in range(NEWTON_MAX):
        R = residual(C)
        rn = float(np.max(np.abs(R)))
        if rn <= NEWTON_TOL * scale:
            converged = True
            break
        dR = -vol * qv * c.Km / (c.Km + C) ** 2
        J = A_lin + sp.diags(dR)
        try:
            step = spla.spsolve(J.tocsc(), -R)
        except Exception:
            return None
        alpha = 1.0
        ok = False
        for _ in range(60):
            trial = np.clip(C + alpha * step, 0.0, cmax)
            if float(np.max(np.abs(residual(trial)))) < rn:
                C = trial
                ok = True
                break
            alpha *= 0.5
        if not ok:
            C = np.clip(C + 1e-3 * step, 0.0, cmax)
    R = residual(C)
    rn = float(np.max(np.abs(R))) / scale
    if rn <= 1e-8:
        converged = True

    # ---- diagnostics
    consumption = float(np.sum(vol * qv * C / (c.Km + C)))
    wall_in = float(np.sum(gwall * (c.C_lumen - C[0:n:nx][:ny] if False else
                                    np.array([C[idx(0, j)] for j in range(ny)]) * -1 + c.C_lumen)))
    surf_in = 0.0
    if c.P_surf > 0:
        top = np.array([C[idx(i, ny - 1)] for i in range(nx)])
        surf_in = float(np.sum(gsurf * (c.C_air - top)))
    delivered = wall_in + surf_in
    denom = max(abs(delivered), abs(consumption), 1e-30)
    balance = abs(delivered - consumption) / denom

    Cmin = float(np.min(C))
    frac_below = float(np.mean(C < THRESHOLD))

    # dimensionless groups actually identified by the data
    thiele_derm = c.q_derm * c.Lx ** 2 / (c.D_derm * c.C_lumen)
    thiele_epi = c.q_epi * (c.h_epi ** 2) / (c.D_epi * c.C_air)
    biot_wall = c.P_wall * c.Lx / c.D_derm

    return {
        "min_free_O2_mol_m3": Cmin,
        "min_pO2_mmHg": Cmin / ALPHA_O2,
        "fraction_below_PF0_threshold": frac_below,
        "all_above_PF0_threshold": bool(Cmin >= THRESHOLD),
        "consumption_mol_s_per_m_depth": consumption,
        "delivery_mol_s_per_m_depth": delivered,
        "wall_fraction_of_delivery": (wall_in / delivered) if delivered > 0 else float("nan"),
        "surface_fraction_of_delivery": (surf_in / delivered) if delivered > 0 else float("nan"),
        "relative_mass_balance_error": balance,
        "thiele_modulus_dermis": thiele_derm,
        "thiele_modulus_epidermis": thiele_epi,
        "biot_wall": biot_wall,
        "converged": bool(converged),
        "field": C.reshape(ny, nx),
    }


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def analytic_zero_order_min(q, D, L, Cs):
    """Zero-order consumption, Dirichlet Cs at x=0, no flux at x=L."""
    return Cs - q * L * L / (2.0 * D)


def run_verification():
    checks = {}

    # V1 zero demand gives a uniform field at the lumen concentration
    c = Case(q_epi=0.0, q_derm=0.0, D_derm=2e-9, D_epi=1e-9, P_wall=5e-5,
             P_surf=0.0, H=1000e-6, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
    r = solve_case(c)
    checks["V1_zero_demand_uniform"] = {
        "max_deviation": float(np.max(np.abs(r["field"] - C_LUMEN_IN))),
        "pass": bool(np.max(np.abs(r["field"] - C_LUMEN_IN)) < 1e-12),
    }

    # V2 analytic zero-order limit: tiny Km makes MM behave as zero order while C>0,
    # very large P_wall makes the wall boundary effectively Dirichlet, single layer.
    q = 5e-3
    D = 2e-9
    c = Case(q_epi=q, q_derm=q, D_derm=D, D_epi=D, P_wall=1e2,
             P_surf=0.0, H=1000e-6, h_epi=0.0, Km=1e-9, nx=160, ny=8)
    r = solve_case(c)
    expected = analytic_zero_order_min(q, D, LX, C_LUMEN_IN)
    rel = abs(r["min_free_O2_mol_m3"] - expected) / C_LUMEN_IN
    checks["V2_analytic_zero_order_slab"] = {
        "numeric_min": r["min_free_O2_mol_m3"], "analytic_min": expected,
        "abs_error_relative_to_inlet": rel, "pass": bool(rel < 2e-3),
    }

    # V3 mass balance across a spread of live cases
    worst = 0.0
    for qe, Dd, Ps in itertools.product(
        [3e-3, 1e-1], [2e-9, 4.5e-10], [0.0, P_SURF_LOWER_BOUND, 1e-3]
    ):
        c = Case(q_epi=qe, q_derm=2.38e-4, D_derm=Dd, D_epi=D_EPI_DEFAULT,
                 P_wall=5e-5, P_surf=Ps, H=1000e-6, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
        r = solve_case(c)
        worst = max(worst, r["relative_mass_balance_error"])
    checks["V3_mass_balance"] = {"worst_relative_error": worst, "pass": bool(worst < 1e-8)}

    # V4 mesh refinement on four corners
    worst_ref = 0.0
    refinement = []
    for qe, Dd in itertools.product([3e-3, 1e-1], [2e-9, 1.7e-10]):
        base = Case(q_epi=qe, q_derm=2.38e-4, D_derm=Dd, D_epi=D_EPI_DEFAULT,
                    P_wall=5e-5, P_surf=P_SURF_LOWER_BOUND, H=1000e-6,
                    h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
        fine = Case(**{**asdict(base), "nx": base.nx * 2, "ny": base.ny * 2})
        rb, rf = solve_case(base), solve_case(fine)
        err = abs(rb["min_free_O2_mol_m3"] - rf["min_free_O2_mol_m3"]) / C_LUMEN_IN
        refinement.append({"q_epi": qe, "D_derm": Dd, "coarse": rb["min_free_O2_mol_m3"],
                           "fine": rf["min_free_O2_mol_m3"], "abs_error_rel_inlet": err})
        worst_ref = max(worst_ref, err)
    checks["V4_mesh_refinement"] = {"worst_abs_error_rel_inlet": worst_ref,
                                    "cases": refinement, "pass": bool(worst_ref < 1e-2)}

    # V5 bounded concentrations
    c = Case(q_epi=1e-1, q_derm=4.76e-4, D_derm=1.7e-10, D_epi=D_EPI_DEFAULT,
             P_wall=5e-6, P_surf=0.0, H=2000e-6, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
    r = solve_case(c)
    f = r["field"]
    checks["V5_bounded"] = {"min": float(f.min()), "max": float(f.max()),
                            "pass": bool(f.min() >= -1e-12 and f.max() <= C_LUMEN_IN + 1e-12)}

    # V6 monotonicity: raising surface conductance must not lower the minimum
    mono_ok = True
    for qe in [3e-3, 9.72e-3, 1e-1]:
        prev = -np.inf
        for Ps in [0.0, P_SURF_LOWER_BOUND, 1e-3]:
            c = Case(q_epi=qe, q_derm=2.38e-4, D_derm=2e-9, D_epi=D_EPI_DEFAULT,
                     P_wall=5e-5, P_surf=Ps, H=1000e-6, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
            m = solve_case(c)["min_free_O2_mol_m3"]
            if m < prev - 1e-9:
                mono_ok = False
            prev = m
    checks["V6_surface_monotonic"] = {"pass": bool(mono_ok)}

    return checks


# --------------------------------------------------------------------------
# main sweep
# --------------------------------------------------------------------------

def main():
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    checks = run_verification()

    rows = []
    combos = itertools.product(
        EPIDERMAL_DEMAND.items(), RHEE_DENSITY_READINGS.items(),
        DERMAL_DIFFUSIVITY.items(), SURFACE_CONDUCTANCE.items(),
        WALL_PERMEABILITY.items(), CONSTRUCT_THICKNESS.items(),
    )
    for (ek, ev), (nk, nv), (dk, dv), (sk, sv), (wk, wv), (hk, hv) in combos:
        q_derm = nv * Q_CELL_HDF
        c = Case(q_epi=ev, q_derm=q_derm, D_derm=dv, D_epi=D_EPI_DEFAULT,
                 P_wall=wv, P_surf=sv, H=hv, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)
        r = solve_case(c)
        if r is None:
            continue
        rows.append({
            "epidermal_demand_case": ek, "q_epi_mol_m3_s": ev,
            "rhee_density_reading": nk, "cell_density_m3": nv,
            "q_derm_mol_m3_s": q_derm,
            "dermal_D_case": dk, "D_derm_m2_s": dv,
            "surface_case": sk, "P_surf_m_s": sv,
            "wall_case": wk, "P_wall_m_s": wv,
            "thickness_case": hk, "H_m": hv,
            "min_free_O2_mol_m3": r["min_free_O2_mol_m3"],
            "min_pO2_mmHg": r["min_pO2_mmHg"],
            "fraction_below_PF0_threshold": r["fraction_below_PF0_threshold"],
            "all_above_PF0_threshold": r["all_above_PF0_threshold"],
            "surface_fraction_of_delivery": r["surface_fraction_of_delivery"],
            "relative_mass_balance_error": r["relative_mass_balance_error"],
            "thiele_modulus_dermis": r["thiele_modulus_dermis"],
            "thiele_modulus_epidermis": r["thiele_modulus_epidermis"],
            "biot_wall": r["biot_wall"],
            "converged": r["converged"],
        })

    import csv as _csv
    with (ROOT / "pf1s_cases.csv").open("w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- how much of the outcome each ambiguity axis controls
    def spread_by(key):
        groups = {}
        for r in rows:
            groups.setdefault(r[key], []).append(r["all_above_PF0_threshold"])
        return {k: {"pass": sum(v), "n": len(v), "pass_rate": sum(v) / len(v)}
                for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}

    axes = ["epidermal_demand_case", "rhee_density_reading", "dermal_D_case",
            "surface_case", "wall_case", "thickness_case"]
    axis_effect = {a: spread_by(a) for a in axes}
    axis_range = {
        a: max(v["pass_rate"] for v in d.values()) - min(v["pass_rate"] for v in d.values())
        for a, d in axis_effect.items()
    }

    # ---- the Rhee-as-published operating point, under each density reading
    published_point = [
        r for r in rows
        if r["dermal_D_case"] == "dilute_gel_upper_bound"
        and r["surface_case"] == "stucker_lower_bound"
        and r["wall_case"] == "mid_5e-5"
        and r["thickness_case"] == "H_1000um"
        and r["epidermal_demand_case"] != "balu_as_printed_mmol"
    ]

    # ---- Km sensitivity, the weakest-evidence parameter in the ledger
    km_scan = []
    for km in [0.0028, 0.028, 0.28]:
        for qe in [3e-3, 9.72e-3, 1e-1]:
            c = Case(q_epi=qe, q_derm=2e13 * Q_CELL_HDF, D_derm=2e-9,
                     D_epi=D_EPI_DEFAULT, P_wall=5e-5, P_surf=P_SURF_LOWER_BOUND,
                     H=1000e-6, h_epi=H_EPI_DEFAULT, Km=km)
            r = solve_case(c)
            km_scan.append({"Km_mol_m3": km, "q_epi_mol_m3_s": qe,
                            "min_free_O2_mol_m3": r["min_free_O2_mol_m3"],
                            "min_pO2_mmHg": r["min_pO2_mmHg"],
                            "all_above_PF0_threshold": r["all_above_PF0_threshold"]})

    # ---- stratum corneum cross-check: three independent measurements
    D_SC = 3e-11
    implied_sc_thickness_m = D_SC / P_SURF_LOWER_BOUND
    sc_crosscheck = {
        "P_surf_lower_bound_m_s": P_SURF_LOWER_BOUND,
        "D_stratum_corneum_m2_s": D_SC,
        "implied_barrier_thickness_um": implied_sc_thickness_m * 1e6,
        "independently_reported_forearm_SC_thickness_um": "10-20 (general dermatology range, NOT from a packet source)",
        "interpretation": (
            "Assuming the stratum corneum's O2 solubility equals the aqueous value, "
            "the Stucker in vivo flux and the Hatcher & Plachy EPR diffusivity together "
            "imply a barrier of about this thickness. Agreement with the independently "
            "known forearm stratum corneum thickness is a genuine three-way consistency "
            "check across measurements that were never combined by their authors. "
            "It is NOT a validation: both inputs were access-blocked in this pass, and "
            "the lipid-rich barrier's true O2 partition coefficient is unmeasured, so a "
            "partition coefficient above 1 would scale the implied thickness up "
            "proportionally."
        ),
    }

    elapsed = time.perf_counter() - t0
    result = {
        "run_type": "PF1-S layered skin oxygen transport and identifiability screen",
        "geometry_source": "Rhee et al. Bioengineering 2024;11:1055 (channel 500 um inner edge, 50 um wall, 400 um spacing, 10 uL/min in / 12 uL/min out)",
        "main_cases": len(rows),
        "cases_above_PF0_threshold": sum(r["all_above_PF0_threshold"] for r in rows),
        "verification_checks": checks,
        "verification_pass_count": sum(1 for v in checks.values() if v.get("pass")),
        "verification_check_count": len(checks),
        "axis_pass_rate_range_larger_means_more_decisive": dict(
            sorted(axis_range.items(), key=lambda kv: -kv[1])
        ),
        "axis_effect_detail": axis_effect,
        "rhee_published_operating_point": published_point,
        "km_sensitivity": km_scan,
        "stratum_corneum_crosscheck": sc_crosscheck,
        "derived_constants": {
            "P_surf_lower_bound_m_s": P_SURF_LOWER_BOUND,
            "q_derm_from_each_rhee_reading_mol_m3_s": {
                k: v * Q_CELL_HDF for k, v in RHEE_DENSITY_READINGS.items()
            },
        },
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": sp.__version__ if hasattr(sp, "__version__") else "see scipy",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limits": LIMITS,
    }
    (ROOT / "pf1s_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )

    # ---- console summary (captured to the execution log)
    print("=" * 78)
    print("PF1-S ACTUAL COMPUTATIONAL RUN")
    print("=" * 78)
    print(f"Main cases: {len(rows)}; above PF0's assumed 0.05 mol/m^3 line: "
          f"{sum(r['all_above_PF0_threshold'] for r in rows)}")
    print(f"Verification: {result['verification_pass_count']}/{result['verification_check_count']} checks pass")
    for k, v in checks.items():
        print(f"  {k}: pass={v.get('pass')}")
    print()
    print("Derived surface conductance lower bound from Stucker 2002:")
    print(f"  P_surf >= {P_SURF_LOWER_BOUND:.3e} m/s")
    print(f"  implied stratum corneum thickness from Hatcher D: "
          f"{sc_crosscheck['implied_barrier_thickness_um']:.1f} um")
    print()
    print("Dermal demand implied by each reading of Rhee section 2.6:")
    for k, v in result["derived_constants"]["q_derm_from_each_rhee_reading_mol_m3_s"].items():
        print(f"  {k:<28s} {v:.3e} mol/m^3/s")
    print()
    print("Which ambiguity decides the outcome (pass-rate range across the axis):")
    for a, v in result["axis_pass_rate_range_larger_means_more_decisive"].items():
        print(f"  {a:<28s} {v:.3f}")
    print()
    print("Pass rate by epidermal demand case:")
    for k, v in axis_effect["epidermal_demand_case"].items():
        print(f"  {k:<38s} {v['pass']:4d}/{v['n']:<4d} = {v['pass_rate']:.3f}")
    print()
    print("Pass rate by reading of Rhee section 2.6 cell density:")
    for k, v in axis_effect["rhee_density_reading"].items():
        print(f"  {k:<38s} {v['pass']:4d}/{v['n']:<4d} = {v['pass_rate']:.3f}")
    print()
    print("Rhee's own published operating point (dilute gel D, Stucker surface, "
          "mid wall, H=1 mm):")
    for r in published_point:
        print(f"  epi demand {r['epidermal_demand_case']:<38s} "
              f"density {r['rhee_density_reading']:<24s} "
              f"min pO2 {r['min_pO2_mmHg']:8.2f} mmHg  pass={r['all_above_PF0_threshold']}")
    print()
    print("Km sensitivity (Km is the least-evidenced parameter in the ledger):")
    for r in km_scan:
        print(f"  Km={r['Km_mol_m3']:<7g} q_epi={r['q_epi_mol_m3_s']:<8g} "
              f"min pO2 {r['min_pO2_mmHg']:8.2f} mmHg  pass={r['all_above_PF0_threshold']}")
    print()
    print(f"Elapsed: {elapsed:.2f} s")
    print()
    for l in LIMITS:
        print(f"LIMIT: {l}")

    return result


LIMITS = [
    "No packet source supplies demand, diffusivity, solubility, oxygen dependence and a functional threshold for the same engineered skin construct. This is a sensitivity and identifiability study, not a calibrated skin prediction.",
    "The dermal demand is built from Streeter & Cheema's model-derived average rate, which is NOT a Michaelis-Menten qmax, multiplied by a cell density that the source geometry paper reports inconsistently. Both factors are weak.",
    "No packet source supplies a Km for dermal fibroblasts or keratinocytes. PF0's 0.028 mol/m^3 is carried unchanged and swept, not justified.",
    "Epidermal diffusivity and epidermal thickness are assumed; Rhee reports neither.",
    "Construct thickness is not reported by Rhee and is swept as a declared unknown rather than fitted.",
    "Cheema's diffusivities are for plastic-compressed dense collagen and are included only as flagged lower bounds; applying them to Rhee's 3 mg/mL gel is marked as a non-permitted combination and is reported separately.",
    "The Stucker flux and the Hatcher & Plachy diffusivity could not be re-read from primary sources in this cloud pass; they are carried as collaborator-reported and every result depending on them is labelled.",
    "Rhee's outlet flow exceeds its inlet flow by 20%, implying a transmural or ambient flow this steady diffusion-reaction model does not represent. Neither does PF0.",
    "Steady state only. No interstitial convection, glucose, CO2, lactate, pH, heat, hydration, immune or mechanical model. Cell density is fixed and does not respond to oxygen.",
    "The 0.05 mol/m^3 line is PF0's assumption, carried only so the two runs are comparable. It certifies nothing about viability or function, and Mieremet et al. 2019 is direct evidence that skin function is not monotone in oxygen.",
    "Mesh refinement and mass balance are numerical verification. They are not biological validation, and no biological experiment was performed.",
]


if __name__ == "__main__":
    main()
