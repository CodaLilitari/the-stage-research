"""PF0: conservative oxygen transport screen, not a blood formulation."""
from pathlib import Path
import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
CONFIG = {
    "name": "PF0 planar perfused-tissue transport screen",
    "model": "steady one-sided planar slab at each axial station; finite-volume Michaelis-Menten reaction-diffusion, finite wall transfer, backward-Euler lumen depletion",
    "source_url": "https://www.nature.com/articles/s41598-026-53301-0",
    "source_parameters": {
        "cell_density_per_m3": 2e14, "maximum_consumption_mol_per_cell_s": 1e-16,
        "qmax_mol_m3_s": 0.02, "Km_mol_m3": 0.028, "D_m2_s": 2e-9,
        "free_inlet_mol_m3": 0.2, "threshold_mol_m3": 0.05,
        "provenance": "Bonart et al. 2026 illustrative liver-like high-demand case; not measured skin physiology.",
    },
    "analyst_selected_geometry": {"wall_width_m": 0.001, "channel_length_m": 0.001, "slab_depths_m": [0.00005, 0.0001, 0.0002, 0.0004]},
    "flows_uL_min": [0.5, 2.0, 8.0, 32.0],
    "wall_permeabilities_m_s": [0.000005, 0.00005, 0.0002],
    "wall_provenance": "0.05 and 0.2 mm/s span the paper's reference range; 0.005 mm/s is an analyst-selected low-transfer stress case.",
    "capacity_multipliers": [1.0, 4.0, 16.0],
    "capacity_law": "Hypothetical instantaneous equilibrium C_total=beta*C_free in lumen only. Same free inlet, diffusivity, consumption and wall law. No actual carrier, viscosity, affinity, kinetics or toxicity is modeled.",
    "numerics": {"tissue_cells": 24, "axial_segments": 32, "newton_relative_tolerance": 1e-10, "axial_root_absolute_tolerance": 1e-12},
    "predeclared_checks": {"mass_balance_relative_tolerance": 1e-6, "bounded_concentrations_tolerance": 1e-10, "refinement_absolute_tolerance_relative_to_inlet": 0.01, "monotonic_absolute_tolerance": 1e-9},
    "scope": "144 main cases; synthetic computational feasibility screening only; no human or tissue experiment, injectable product, clinical efficacy or whole-body viability claim.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tridiagonal(lower, diagonal, upper, rhs):
    d, b = list(diagonal), list(rhs)
    for i in range(1, len(d)):
        factor = lower[i] / d[i - 1]
        d[i] -= factor * upper[i - 1]
        b[i] -= factor * b[i - 1]
    out = [0.0] * len(d)
    out[-1] = b[-1] / d[-1]
    for i in range(len(d) - 2, -1, -1):
        out[i] = (b[i] - upper[i] * out[i + 1]) / d[i]
    return out


def slab(cbulk, depth, permeability, params, n):
    if cbulk <= 0:
        return {"c": [0.0] * n, "flux": 0.0, "uptake": 0.0, "residual": 0.0}
    D, km, qmax = params["D_m2_s"], params["Km_mol_m3"], params["qmax_mol_m3_s"]
    dx = depth / n
    g = D / dx
    wall = 1.0 / (1.0 / permeability + dx / (2 * D))
    c = [cbulk] * n

    def residual_and_jac(values):
        residual, lower, diagonal, upper = [], [], [], []
        for i, ci in enumerate(values):
            gl = wall if i == 0 else g
            gr = g if i < n - 1 else 0.0
            cl = cbulk if i == 0 else values[i - 1]
            cr = values[i + 1] if i < n - 1 else ci
            rate = qmax * ci / (km + ci)
            residual.append(gl * (cl - ci) + gr * (cr - ci) - dx * rate)
            lower.append(gl if i else 0.0)
            diagonal.append(-gl - gr - dx * qmax * km / (km + ci) ** 2)
            upper.append(gr)
        return residual, lower, diagonal, upper

    scale = max(qmax * depth, 1e-15)
    for iteration in range(50):
        residual, lower, diagonal, upper = residual_and_jac(c)
        norm = max(abs(v) for v in residual)
        if norm <= CONFIG["numerics"]["newton_relative_tolerance"] * scale:
            flux = wall * (cbulk - c[0])
            uptake = sum(qmax * ci / (km + ci) * dx for ci in c)
            return {"c": c, "flux": flux, "uptake": uptake, "residual": norm / scale}
        delta = tridiagonal(lower, diagonal, upper, [-v for v in residual])
        alpha = 1.0
        for backtrack in range(40):
            trial = [ci + alpha * di for ci, di in zip(c, delta)]
            if min(trial) >= 0.0 and max(trial) <= cbulk * (1 + 1e-12):
                new_norm = max(abs(v) for v in residual_and_jac(trial)[0])
                if new_norm < norm:
                    c = trial
                    break
            alpha *= 0.5
        else:
            raise RuntimeError("Slab Newton line search did not converge")
    raise RuntimeError("Slab solver exceeded iteration limit")


def simulate(depth, flow_uL_min, permeability, beta, *, tissue_cells=None, axial_segments=None, qmax=None):
    params = dict(CONFIG["source_parameters"])
    if qmax is not None:
        params["qmax_mol_m3_s"] = qmax
    nt = tissue_cells or CONFIG["numerics"]["tissue_cells"]
    nz = axial_segments or CONFIG["numerics"]["axial_segments"]
    width = CONFIG["analyst_selected_geometry"]["wall_width_m"]
    length = CONFIG["analyst_selected_geometry"]["channel_length_m"]
    dz = length / nz
    Q = flow_uL_min * 1e-9 / 60
    ci = params["free_inlet_mol_m3"]
    inlet = ci
    uptake = 0.0
    minimum = inlet
    hypoxic_cells = 0
    highest_residual = 0.0
    for _ in range(nz):
        previous = ci
        factor = width * dz / (Q * beta)
        lo, hi = 0.0, previous
        if params["qmax_mol_m3_s"] == 0:
            ci = previous
        else:
            for bisection in range(50):
                mid = (lo + hi) / 2
                profile = slab(mid, depth, permeability, params, nt)
                error = mid + factor * profile["flux"] - previous
                if error > 0:
                    hi = mid
                else:
                    lo = mid
                if hi - lo < CONFIG["numerics"]["axial_root_absolute_tolerance"]:
                    break
            ci = (lo + hi) / 2
        profile = slab(ci, depth, permeability, params, nt)
        minimum = min(minimum, min(profile["c"]))
        hypoxic_cells += sum(c < params["threshold_mol_m3"] for c in profile["c"])
        highest_residual = max(highest_residual, profile["residual"])
        uptake += width * dz * profile["uptake"]
    delivered = Q * beta * (inlet - ci)
    balance = abs(delivered - uptake) / max(abs(delivered), abs(uptake), 1e-20)
    qcrit = params["qmax_mol_m3_s"] * params["threshold_mol_m3"] / (params["Km_mol_m3"] + params["threshold_mol_m3"])
    local_drop_minimum = qcrit * (depth / permeability + depth * depth / (2 * params["D_m2_s"]))
    volume = depth * width * length
    return {
        "depth_um": depth * 1e6, "flow_uL_min": flow_uL_min, "wall_permeability_mm_s": permeability * 1e3, "beta_hypothetical": beta,
        "minimum_free_tissue_mol_m3": minimum, "outlet_free_mol_m3": ci,
        "fraction_below_threshold": hypoxic_cells / (nt * nz), "all_cells_above_threshold": minimum >= params["threshold_mol_m3"],
        "uptake_mol_s": uptake, "delivery_mol_s": delivered, "relative_mass_balance_error": balance, "maximum_relative_station_residual": highest_residual,
        "necessary_local_bound_passes": inlet - local_drop_minimum >= params["threshold_mol_m3"],
        "necessary_supply_bound_passes": Q * beta * (inlet - params["threshold_mol_m3"]) >= volume * qcrit,
        "infinite_flow_zero_order_conservative_minimum": inlet - params["qmax_mol_m3_s"] * (depth / permeability + depth * depth / (2 * params["D_m2_s"])),
    }


def main_run():
    freeze = json.loads((ROOT / "freeze.json").read_text())
    if freeze["code_sha256"] != sha(__file__) or freeze["config"] != CONFIG:
        raise RuntimeError("Frozen code/config mismatch; create a new version rather than refitting this run")
    if (ROOT / "results.json").exists():
        raise SystemExit("Results already exist; this frozen run is preserved")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    cases = list(itertools.product(CONFIG["analyst_selected_geometry"]["slab_depths_m"], CONFIG["flows_uL_min"], CONFIG["wall_permeabilities_m_s"], CONFIG["capacity_multipliers"]))
    rows = [simulate(*case) for case in cases]
    with (ROOT / "cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lookup = {(r["depth_um"], r["flow_uL_min"], r["wall_permeability_mm_s"], r["beta_hypothetical"]): r for r in rows}
    monotonic_failures = []
    for axis in [1, 2, 3]:
        groups = {}
        for key, row in lookup.items():
            group = tuple(v for i, v in enumerate(key) if i != axis)
            groups.setdefault(group, []).append((key[axis], row["minimum_free_tissue_mol_m3"]))
        for key, values in groups.items():
            values.sort()
            if any(b[1] < a[1] - 1e-9 for a, b in zip(values, values[1:])):
                monotonic_failures.append({"axis": axis, "group": key})
    zero = simulate(0.0001, 2, 0.00005, 1, qmax=0)
    # A consequence of this declared constitutive law: flow and beta enter only
    # as Q*beta. This checks implementation, not the existence of such a carrier.
    product_pairs = []
    for depth in CONFIG["analyst_selected_geometry"]["slab_depths_m"]:
        for permeability in CONFIG["wall_permeabilities_m_s"]:
            a = lookup[(depth * 1e6, 2.0, permeability * 1e3, 4.0)]
            b = lookup[(depth * 1e6, 8.0, permeability * 1e3, 1.0)]
            product_pairs.append(abs(a["minimum_free_tissue_mol_m3"] - b["minimum_free_tissue_mol_m3"]))
    # Eight prespecified corner cases: double both grids, retaining all inputs.
    refinement = []
    for case in itertools.product([0.00005, 0.0004], [0.5, 32.0], [0.000005], [1.0, 16.0]):
        fine = simulate(*case, tissue_cells=48, axial_segments=64)
        coarse = lookup[(case[0] * 1e6, case[1], case[2] * 1e3, case[3])]
        refinement.append({"case": case, "coarse_minimum": coarse["minimum_free_tissue_mol_m3"], "fine_minimum": fine["minimum_free_tissue_mol_m3"], "absolute_error_relative_to_inlet": abs(fine["minimum_free_tissue_mol_m3"] - coarse["minimum_free_tissue_mol_m3"]) / CONFIG["source_parameters"]["free_inlet_mol_m3"]})
    checked = CONFIG["predeclared_checks"]
    bound_false_passes = [r for r in rows if r["all_cells_above_threshold"] and not (r["necessary_local_bound_passes"] and r["necessary_supply_bound_passes"])]
    checks = {
        "all_mass_balances_pass": max(r["relative_mass_balance_error"] for r in rows) < checked["mass_balance_relative_tolerance"],
        "all_concentrations_bounded": all(-1e-10 <= r["minimum_free_tissue_mol_m3"] <= r["outlet_free_mol_m3"] <= 0.2 + 1e-10 for r in rows),
        "zero_demand_uniform": abs(zero["minimum_free_tissue_mol_m3"] - 0.2) < 1e-12 and abs(zero["uptake_mol_s"]) < 1e-20,
        "flow_wall_capacity_monotonic": not monotonic_failures,
        "flow_times_capacity_degeneracy": max(product_pairs) < 1e-12,
        "necessary_bounds_never_falsely_passed": not bound_false_passes,
        "eight_refinement_cases_within_declared_limit": max(r["absolute_error_relative_to_inlet"] for r in refinement) < checked["refinement_absolute_tolerance_relative_to_inlet"],
    }
    by_beta = {str(beta): sum(r["all_cells_above_threshold"] for r in rows if r["beta_hypothetical"] == beta) for beta in CONFIG["capacity_multipliers"]}
    result = {
        "run_type": "PF0 computational transport screen", "main_cases": len(rows), "main_cases_above_threshold": sum(r["all_cells_above_threshold"] for r in rows), "above_threshold_by_beta_out_of_48": by_beta,
        "checks": checks, "check_pass_count": sum(checks.values()), "check_count": len(checks),
        "maximum_relative_mass_balance_error": max(r["relative_mass_balance_error"] for r in rows),
        "maximum_refinement_error_relative_to_inlet": max(r["absolute_error_relative_to_inlet"] for r in refinement),
        "refinement": refinement, "monotonic_failures": monotonic_failures,
        "impossible_local_bound_main_cases": sum(not r["necessary_local_bound_passes"] for r in rows),
        "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.perf_counter() - t0,
        "code_sha256": sha(__file__), "freeze_sha256": sha(ROOT / "freeze.json"), "python_executable": sys.executable, "python_version": platform.python_version(),
        "limits": ["Liver-like illustrative demand is not measured skin demand.", "Planar one-wall geometry, steady state, no interstitial flow, fixed cell density and abundant other nutrients.", "Carrier multiplier is hypothetical instantaneous linear equilibrium; it does not change free oxygen, D, wall permeability, viscosity or pump power.", "Threshold classifies a model oxygen field; it does not certify survival or tissue function.", "No glucose, CO2, lactate, pH, heat, immune, sterility or mechanical-deformation model.", "Numerical mesh refinement and mass balance are verification, not biological validation or replication of the full 2026 network study."],
    }
    write_json(ROOT / "results.json", result)
    make_plot(rows)
    lines = ["PF0 ACTUAL COMPUTATIONAL RUN", "", f"Main cases: {len(rows)}; above the assumed oxygen threshold: {result['main_cases_above_threshold']}.", f"Passing cases by hypothetical capacity beta (48 each): {by_beta}", f"Checks: {sum(checks.values())}/{len(checks)}; {checks}", f"Maximum relative mass-balance error: {result['maximum_relative_mass_balance_error']:.6g}", f"Maximum eight-case refinement difference / inlet: {result['maximum_refinement_error_relative_to_inlet']:.6g}", f"Cases failing the local necessary bound regardless of flow/capacity: {result['impossible_local_bound_main_cases']}", f"Elapsed seconds: {result['elapsed_seconds']:.3f}", "", "The exact Q*beta equivalence is built into the assumed equilibrium capacity law. It is an implementation check, not evidence that a material with those properties exists. Increasing total carrier content cannot remove a transverse diffusion or wall-transfer limit while free inlet oxygen stays fixed.", "", "All inputs were frozen locally before this main run. No independent timestamp or biological experiment was used.", ""] + result["limits"]
    (ROOT / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(ROOT / "execution_receipt.json", {"started_at_utc": started, "finished_at_utc": result["finished_at_utc"], "code_sha256": result["code_sha256"], "freeze_sha256": result["freeze_sha256"], "outputs": {name: sha(ROOT / name) for name in ["cases.csv", "results.json", "report.txt", "oxygen_screen.png"]}})
    print(json.dumps({key: result[key] for key in ["main_cases", "main_cases_above_threshold", "above_threshold_by_beta_out_of_48", "checks", "maximum_relative_mass_balance_error", "maximum_refinement_error_relative_to_inlet", "impossible_local_bound_main_cases", "elapsed_seconds"]}, indent=2))


def make_plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3), sharey=True)
    for ax, beta in zip(axes, CONFIG["capacity_multipliers"]):
        for permeability in CONFIG["wall_permeabilities_m_s"]:
            selected = sorted([r for r in rows if r["beta_hypothetical"] == beta and r["flow_uL_min"] == 8 and r["wall_permeability_mm_s"] == permeability * 1e3], key=lambda r: r["depth_um"])
            ax.plot([r["depth_um"] for r in selected], [r["minimum_free_tissue_mol_m3"] for r in selected], "o-", label=f"P={permeability * 1e3:g} mm/s")
        ax.axhline(0.05, color="black", ls="--", lw=1, label="assumed threshold")
        ax.set_title(f"Hypothetical capacity beta = {beta:g}")
        ax.set_xlabel("One-sided tissue depth (micrometers)")
        ax.set_ylim(0, 0.21)
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Minimum free oxygen (mol/m^3)")
    axes[-1].legend(fontsize=8)
    fig.suptitle("PF0: capacity cannot erase local transport limits | flow 8 microliters/min")
    fig.text(0.5, 0.01, "Computational screen; liver-like demand; carrier law is hypothetical; no tissue viability certification.", ha="center", fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.94])
    fig.savefig(ROOT / "oxygen_screen.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        if (ROOT / "freeze.json").exists():
            raise SystemExit("Freeze already exists")
        write_json(ROOT / "freeze.json", {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "code_sha256": sha(__file__), "config": CONFIG, "status": "local pre-run freeze, not externally witnessed preregistration"})
        print("Frozen code and inputs before main run")
    else:
        main_run()
