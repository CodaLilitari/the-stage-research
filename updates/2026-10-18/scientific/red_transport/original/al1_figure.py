#!/usr/bin/env python3
"""al1_figure.py - the single summary figure for AL1, drawn only from the frozen run's
al1_results.csv and al1_summary.json. Refuses to overwrite al1_figure.png.

The Stage, research/cowork_local. Author: Red (Claude, Anthropic) via Claude Cowork, 2026-10-15.
Usage:  python -B research/cowork_local/al1_figure.py
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "al1_figure.png"

INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
# Fixed categorical order (validated palette slots 1-6); colour follows the arrangement in both panels.
STYLE = {
    "parallel_maxmin": ("#2a78d6", "o", "parallel, max-min split"),
    "series_limited_first": ("#eb6834", "s", "series, most-limited module first"),
    "parallel_uniform": ("#1baf7a", "^", "parallel, equal split"),
    "parallel_demand_prop": ("#eda100", "D", "parallel, demand-proportional split"),
    "series_limited_last": ("#e87ba4", "v", "series, most-limited module last"),
    "two_sided_maxmin": ("#008300", "P", "two-sided hotspot, max-min split"),
}


def main():
    if OUT.exists():
        sys.exit("al1_figure.png exists; preserved. Use a new version name.")
    rows = list(csv.DictReader((HERE / "al1_results.csv").open(encoding="utf-8")))
    summary = json.loads((HERE / "al1_summary.json").read_text(encoding="utf-8"))
    cfg = json.loads((HERE / "al1_config.json").read_text(encoding="utf-8"))
    ref = cfg["reference_parameters"]["reference_line_mol_m3"]

    def pick(geometry, r, depth_um, transfer, arrangement, beta=None, flow=None):
        out = []
        for x in rows:
            if (x["geometry"] == geometry and int(x["hotspot_demand_ratio_r"]) == r and float(x["hotspot_depth_um"]) == depth_um
                    and x["transfer"] == transfer and x["arrangement"] == arrangement
                    and (beta is None or int(x["beta"]) == beta) and (flow is None or float(x["total_flow_uL_min"]) == flow)):
                out.append(x)
        return out

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK})
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 6.4), facecolor=SURFACE)
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, lw=0.8, ls="-")
        ax.set_axisbelow(True)
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
        ax.set_xscale("log", base=2)
        ax.set_ylim(0, 0.14)

    # Panel A: flow-limited hotspot (100 um, 1x PF0 demand), beta = 1
    pa = cfg["figure_panels"]["A"]
    ax = axes[0]
    depth_a = pa["hotspot_depth_m"] * 1e6
    ceiling_a = None
    for arr in ["parallel_maxmin", "series_limited_first", "parallel_demand_prop", "parallel_uniform", "series_limited_last"]:
        sel = sorted(pick(pa["geometry"], pa["hotspot_demand_ratio_r"], depth_a, pa["transfer"], arr, beta=pa["beta"]),
                     key=lambda x: float(x["total_flow_uL_min"]))
        xs = [float(x["total_flow_uL_min"]) for x in sel]
        ys = [float(x["worst_min_mol_m3"]) for x in sel]
        ceiling_a = float(sel[0]["min_ceiling_mol_m3"])
        color, marker, label = STYLE[arr]
        ax.plot(xs, ys, color=color, lw=2, marker=marker, ms=7, mec=SURFACE, mew=1.5, label=label, zorder=3)
    ax.axhline(ceiling_a, color=MUTED, lw=1.2, ls=":", zorder=2)
    ax.text(1.05, ceiling_a + 0.003, "hotspot ceiling (infinite flow or capacity) %.3f" % ceiling_a, color=INK2, fontsize=8.5)
    ax.axhline(ref, color=INK2, lw=1.0, ls="--", zorder=2)
    ax.text(40, ref + 0.003, "PF0 reference line %.2f" % ref, color=INK2, fontsize=8.5, ha="right")
    ax.set_xticks([1, 2, 4, 8, 16, 32, 64])
    ax.set_xticklabels(["1", "2", "4", "8", "16", "32", "64"])
    ax.set_xlabel("Total perfusate flow shared by the 4 modules (microlitres/min)")
    ax.set_ylabel("Worst-region free O2 in the patch (mol/m3)")
    ax.set_title("A. Flow-limited hotspot (100 um, 4x baseline demand), beta = 1\n"
                 "The same total flow through 4 modules, distributed differently", fontsize=10.5, loc="left")

    # Panel B: transverse-limited hotspot (200 um), fixed total flow, vary hypothetical capacity
    pb = cfg["figure_panels"]["B"]
    ax = axes[1]
    depth_b = pb["hotspot_depth_m"] * 1e6
    flow_b = float(pb["total_flow_uL_min"])
    lines = [("base", "parallel_maxmin", "parallel_maxmin"), ("base", "series_limited_first", "series_limited_first"),
             ("base", "parallel_uniform", "parallel_uniform"), ("two_sided_hotspot", "parallel_maxmin", "two_sided_maxmin")]
    ceilings = {}
    for geometry, arr, key in lines:
        sel = sorted(pick(geometry, pb["hotspot_demand_ratio_r"], depth_b, pb["transfer"], arr, flow=flow_b),
                     key=lambda x: int(x["beta"]))
        xs = [int(x["beta"]) for x in sel]
        ys = [float(x["worst_min_mol_m3"]) for x in sel]
        ceilings[geometry] = float(sel[0]["min_ceiling_mol_m3"])
        color, marker, label = STYLE[key]
        big = key == "series_limited_first"
        ax.plot(xs, ys, color=color, lw=2, marker=marker, ms=9 if big else 7, mec=SURFACE, mew=1.5, label=label,
                zorder=3 if big else 4)
    ax.axhline(ceilings["base"], color=MUTED, lw=1.2, ls=":", zorder=2)
    ax.text(1.05, ceilings["base"] + 0.003, "one-sided hotspot ceiling %.4f" % ceilings["base"], color=INK2, fontsize=8.5)
    ax.axhline(ceilings["two_sided_hotspot"], color=MUTED, lw=1.2, ls=":", zorder=2)
    ax.text(1.05, ceilings["two_sided_hotspot"] + 0.003, "two-sided hotspot ceiling %.3f" % ceilings["two_sided_hotspot"],
            color=INK2, fontsize=8.5)
    ax.axhline(ref, color=INK2, lw=1.0, ls="--", zorder=2)
    ax.text(250, ref + 0.003, "PF0 reference line %.2f" % ref, color=INK2, fontsize=8.5, ha="right")
    sup = {int(x["beta"]): float(x["global_supply_ratio"])
           for x in pick("base", pb["hotspot_demand_ratio_r"], depth_b, pb["transfer"], "parallel_maxmin", flow=flow_b)}
    ax.text(1.05, 0.094, "Lower three lines: one-sided hotspot.\n"
            "At beta = 256, O2 supply above the reference line is %.0fx\n"
            "the patch's nominal demand, yet the worst region stays\n"
            "below the %.4f ceiling. Max-min parallel and\n"
            "most-limited-first series nearly coincide here." % (sup[256], ceilings["base"]),
            fontsize=8.5, color=INK, va="top")
    ax.set_xticks([1, 4, 16, 64, 256])
    ax.set_xticklabels(["1", "4", "16", "64", "256"])
    ax.set_xlabel("Hypothetical lumen capacity beta (C_total = beta x C_free)")
    ax.set_title("B. Transverse-limited hotspot (200 um, 4x demand), %g microlitres/min total\n"
                 "More carrier capacity saturates at the ceiling; halving the diffusion depth lifts it" % flow_b,
                 fontsize=10.5, loc="left")
    handles, labels = [], []
    for a in axes:
        for h_, l_ in zip(*a.get_legend_handles_labels()):
            if l_ not in labels:
                handles.append(h_)
                labels.append(l_)
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=9, frameon=False, labelcolor=INK,
               bbox_to_anchor=(0.5, 0.06))

    fig.suptitle("AL1: redistributing a fixed perfusate flow among heterogeneous tissue modules (computational screen)",
                 fontsize=12, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.012, "PF0 constitutive model, continuum solution. PF0's liver-like constants with hypothetical demand "
             "multipliers, not skin values. Wall 0.05 mm/s, no lumen film. Capacity law hypothetical (no viscosity or "
             "release kinetics).\nNot a tissue or clinical validation. Data: al1_results.csv (all 17,640 rows). "
             "Red (Claude, Anthropic) via Claude Cowork; checks %d/%d passed." % (summary["check_pass_count"], summary["check_count"]),
             fontsize=8, color=INK2)
    fig.tight_layout(rect=[0, 0.15, 1, 0.95])
    fig.savefig(OUT, dpi=170, facecolor=SURFACE)
    print("wrote", OUT.name)


if __name__ == "__main__":
    main()
