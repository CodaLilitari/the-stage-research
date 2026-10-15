"""
PF1-S figure. Static PNG for the report (no hover/dark-mode layer applies).

Palette: validated categorical slots 1-3 from the reference instance
(#2a78d6 blue, #eb6834 orange, #1baf7a aqua) - all checks PASS on the light
surface under --pairs all; aqua carries a sub-3:1 contrast WARN, so the relief
rule applies and every series is directly labelled as well as legended.

Run:  python3 pf1s_figure.py
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pf1s_skin import Case, solve_case, ALPHA_O2, THRESHOLD, P_SURF_LOWER_BOUND, \
    Q_CELL_HDF, D_EPI_DEFAULT, H_EPI_DEFAULT, KM_DEFAULT

ROOT = Path(__file__).resolve().parent

SURFACE_1 = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = {"Sealed surface": "#2a78d6",
          "Barrier intact": "#eb6834",
          "Open air-liquid interface": "#1baf7a"}
CRITICAL = "#d03b3b"

BASE = Case(q_epi=9.72e-3, q_derm=2e13 * Q_CELL_HDF, D_derm=2.0e-9,
            D_epi=D_EPI_DEFAULT, P_wall=5e-5, P_surf=P_SURF_LOWER_BOUND,
            H=1000e-6, h_epi=H_EPI_DEFAULT, Km=KM_DEFAULT)

SURF_VALUES = {"Sealed surface": 0.0,
               "Barrier intact": P_SURF_LOWER_BOUND,
               "Open air-liquid interface": 1e-3}

READINGS = [
    (3.0e-3, "Textbook resting\nskin bulk"),
    (9.72e-3, "Balu read as\nmicromol"),
    (1.0e-1, "Balu recomputed from\nits own inputs"),
]

AXIS_DECISIVENESS = [
    ("Epidermal demand", 1.000),
    ("Channel wall transfer", 0.080),
    ("Surface condition", 0.056),
    ("Dermal diffusivity", 0.052),
    ("Rhee cell density", 0.003),
    ("Construct thickness", 0.003),
]


def main():
    qs = np.logspace(np.log10(1e-3), np.log10(3e-1), 34)
    curves = {}
    for label, ps in SURF_VALUES.items():
        ys = []
        for q in qs:
            r = solve_case(replace(BASE, q_epi=float(q), P_surf=ps))
            ys.append(r["min_pO2_mmHg"])
        curves[label] = np.array(ys)

    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(13.2, 5.4), gridspec_kw={"width_ratios": [1.45, 1.0]}
    )
    fig.patch.set_facecolor(SURFACE_1)

    # ---------------- panel A ----------------
    ax.set_facecolor(SURFACE_1)
    for label, ys in curves.items():
        ax.plot(qs, ys, lw=2.0, color=SERIES[label], label=label,
                solid_capstyle="round", zorder=3)

    ax.axhline(THRESHOLD / ALPHA_O2, color=CRITICAL, lw=1.6, ls=(0, (5, 3)),
               zorder=2)
    ax.text(1.05e-3, THRESHOLD / ALPHA_O2 + 2.5,
            "PF0 assumed line (37 mmHg) - classifies a model field, certifies nothing",
            color=CRITICAL, fontsize=8.2, va="bottom", ha="left")

    for q, name in READINGS:
        ax.axvline(q, color=MUTED, lw=1.0, ls=(0, (2, 3)), zorder=1)
        ax.text(q * 1.06, 157, name, rotation=0, fontsize=8.0, color=INK_2,
                va="top", ha="left")

    # Threshold crossings: separated in x, so they label cleanly and also carry
    # the quantitative result. Markers >= 8px. Relief for the sub-3:1 aqua is
    # provided by these labels plus the delivered pf1s_cases.csv table view.
    crossings = {"Sealed surface": 0.02342,
                 "Barrier intact": 0.02883,
                 "Open air-liquid interface": 0.08973}
    for label, qc in crossings.items():
        ax.plot([qc], [THRESHOLD / ALPHA_O2], "o", ms=8, color=SERIES[label],
                markeredgecolor=SURFACE_1, markeredgewidth=2.0, zorder=5)

    ax.text(0.28, 128,
            "Demand at which this geometry\nfirst breaches that line:\n"
            "   sealed                 0.023\n"
            "   barrier intact        0.029\n"
            "   open interface      0.090",
            fontsize=8.4, color=INK_2, va="top", ha="right", linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.5", facecolor=SURFACE_1,
                      edgecolor=GRID, linewidth=1.0))

    ax.set_xscale("log")
    ax.set_xlabel("Epidermal volumetric oxygen demand  (mol m$^{-3}$ s$^{-1}$)",
                  fontsize=9.6, color=INK_2)
    ax.set_ylabel("Minimum tissue pO$_2$ in the unit cell  (mmHg)",
                  fontsize=9.6, color=INK_2)
    ax.set_ylim(-4, 168)
    ax.set_xlim(1e-3, 3e-1)
    ax.grid(True, which="major", color=GRID, lw=0.8, zorder=0)
    ax.grid(True, which="minor", color=GRID, lw=0.4, alpha=0.6, zorder=0)
    for s in ax.spines.values():
        s.set_color(AXIS); s.set_linewidth(1.0)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8.8)
    ax.set_title("A   The literature span straddles the boundary",
                 fontsize=10.8, color=INK, loc="left", pad=10)
    leg = ax.legend(frameon=False, fontsize=8.6, loc="lower left",
                    bbox_to_anchor=(0.015, 0.02))
    for t in leg.get_texts():
        t.set_color(INK_2)

    # ---------------- panel B ----------------
    bx.set_facecolor(SURFACE_1)
    names = [n for n, _ in AXIS_DECISIVENESS][::-1]
    vals = [v for _, v in AXIS_DECISIVENESS][::-1]
    ypos = np.arange(len(names))
    bars = bx.barh(ypos, vals, height=0.56, color="#2a78d6", zorder=3)
    bars[-1].set_color(CRITICAL)
    for b in bars:
        b.set_linewidth(0)
    for y, v in zip(ypos, vals):
        bx.text(v + 0.018, y, f"{v:.3f}", va="center", ha="left",
                fontsize=8.8, color=INK_2)
    bx.set_yticks(ypos)
    bx.set_yticklabels(names, fontsize=9.0, color=INK_2)
    bx.set_xlim(0, 1.16)
    bx.set_xlabel("Range of pass-rate across that parameter's settings\n"
                  "(1.000 = that parameter alone decides the outcome)",
                  fontsize=9.4, color=INK_2)
    bx.grid(True, axis="x", color=GRID, lw=0.8, zorder=0)
    for s in bx.spines.values():
        s.set_color(AXIS); s.set_linewidth(1.0)
    bx.spines["top"].set_visible(False); bx.spines["right"].set_visible(False)
    bx.tick_params(colors=MUTED, labelsize=8.8)
    bx.set_title("B   One unresolved number decides it; the rest barely matter",
                 fontsize=10.8, color=INK, loc="left", pad=10)

    fig.suptitle(
        "PF1-S: oxygen sufficiency of the Rhee 2024 perfused skin geometry, "
        "972 cases over the documented literature ambiguities",
        fontsize=11.6, color=INK, x=0.012, ha="left", y=0.985,
    )
    fig.text(0.012, 0.028,
             "Sensitivity and identifiability screen, not a calibrated prediction. No source supplies demand, "
             "diffusivity, solubility, oxygen dependence and a functional threshold for the same construct.",
             fontsize=7.8, color=MUTED, ha="left")
    fig.text(0.012, 0.008,
             "Surface conductance lower bound derived from Stucker 2002. Stucker 2002 and Hatcher & Plachy 1993 "
             "could not be re-read from primary sources in this pass and are carried as collaborator-reported.",
             fontsize=7.8, color=MUTED, ha="left")

    fig.tight_layout(rect=[0.004, 0.065, 0.998, 0.945])
    fig.savefig(ROOT / "pf1s_figure.png", dpi=180, facecolor=SURFACE_1)
    plt.close(fig)
    print("wrote pf1s_figure.png")


if __name__ == "__main__":
    main()
