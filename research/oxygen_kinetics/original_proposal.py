"""
Two-Compartment Finite-Kinetic Oxygen-Carrier Loading/Unloading Toy Model.

Research Context: 'The Stage' (Embodiment, Synthetic Circulation).
Collaborators: Coda & Richard Pemberton.
Reviewer: Independent mathematical review contribution.

DISCLAIMER: Phenomenological toy model only. Not a medical product model.
Constants and kinetic scaling are explicitly hypothetical.
Does not predict tissue survival or rank clinical products.
"""

import math
import json
import csv
import sys
from typing import Dict, Any, Tuple, List
import numpy as np


def hill_saturation(P: float, P50: float, n: float) -> float:
    """Equilibrium Hill saturation S(P) = P^n / (P^n + P50^n)."""
    if P <= 0.0:
        return 0.0
    if P50 <= 0.0:
        return 1.0
    pn = math.pow(P, n)
    p50n = math.pow(P50, n)
    return pn / (pn + p50n)


def exact_css_map(
    PL: float,
    PU: float,
    P50: float,
    n: float,
    kL: float,
    kU: float,
    tauL: float,
    tauU: float,
    B: float,
) -> Dict[str, float]:
    """
    Computes exact cyclic steady-state (CSS) fixed points and metrics.
    
    Returns dictionary with:
      - SL_star, SU_star: equilibrium limits
      - EL, EU: relaxation factors exp(-k*tau)
      - S_exit_L, S_exit_U: steady-state cyclic endpoints
      - delta_S_eq: equilibrium capacity difference
      - delta_S_cyc: actual delivered saturation per cycle
      - eta_kin: kinetic efficiency (delta_S_cyc / delta_S_eq)
      - q_cyc: delivered moles per unit volume per cycle
      - J_flux: time-averaged delivery rate (q_cyc / (tauL + tauU))
    """
    SL_star = hill_saturation(PL, P50, n)
    SU_star = hill_saturation(PU, P50, n)
    delta_S_eq = SL_star - SU_star

    EL = math.exp(-kL * tauL) if (kL * tauL) < 700 else 0.0
    EU = math.exp(-kU * tauU) if (kU * tauU) < 700 else 0.0

    denom = 1.0 - EL * EU
    if denom <= 1e-15:
        # Vanishing relaxation / zero contact limit
        S_exit_U = SU_star
        S_exit_L = SU_star
        delta_S_cyc = 0.0
        eta_kin = 0.0
    else:
        S_exit_U = ((1.0 - EU) * SU_star + EU * (1.0 - EL) * SL_star) / denom
        S_exit_L = ((1.0 - EL) * SL_star + EL * (1.0 - EU) * SU_star) / denom
        delta_S_cyc = S_exit_L - S_exit_U
        eta_kin = ((1.0 - EL) * (1.0 - EU)) / denom if delta_S_eq > 1e-12 else 0.0

    T_cyc = tauL + tauU
    q_cyc = B * delta_S_cyc
    J_flux = q_cyc / T_cyc if T_cyc > 0.0 else 0.0

    return {
        "SL_star": SL_star,
        "SU_star": SU_star,
        "delta_S_eq": delta_S_eq,
        "EL": EL,
        "EU": EU,
        "S_exit_L": S_exit_L,
        "S_exit_U": S_exit_U,
        "delta_S_cyc": delta_S_cyc,
        "eta_kin": eta_kin,
        "q_cyc": q_cyc,
        "J_flux": J_flux,
        "T_cyc": T_cyc,
    }


def integrate_numerical_cycles(
    PL: float,
    PU: float,
    P50: float,
    n: float,
    kL: float,
    kU: float,
    tauL: float,
    tauU: float,
    B: float,
    S_init: float = 0.0,
    n_cycles: int = 40,
    steps_per_phase: int = 100,
) -> Dict[str, Any]:
    """
    Independent numerical time-integration of alternating contact phases
    using explicit 4th-order Runge-Kutta (RK4).
    """
    SL_star = hill_saturation(PL, P50, n)
    SU_star = hill_saturation(PU, P50, n)

    S = S_init
    dt_L = tauL / steps_per_phase
    dt_U = tauU / steps_per_phase

    cycle_history = []

    for c in range(n_cycles):
        S_entry_L = S
        # Loading phase ODE: dS/dt = -kL * (S - SL_star)
        for _ in range(steps_per_phase):
            k1 = -kL * (S - SL_star)
            k2 = -kL * (S + 0.5 * dt_L * k1 - SL_star)
            k3 = -kL * (S + 0.5 * dt_L * k2 - SL_star)
            k4 = -kL * (S + dt_L * k3 - SL_star)
            S += (dt_L / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        S_exit_L = S

        S_entry_U = S
        # Unloading phase ODE: dS/dt = -kU * (S - SU_star)
        for _ in range(steps_per_phase):
            k1 = -kU * (S - SU_star)
            k2 = -kU * (S + 0.5 * dt_U * k1 - SU_star)
            k3 = -kU * (S + 0.5 * dt_U * k2 - SU_star)
            k4 = -kU * (S + dt_U * k3 - SU_star)
            S += (dt_U / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        S_exit_U = S

        cycle_history.append({
            "cycle": c,
            "S_entry_L": S_entry_L,
            "S_exit_L": S_exit_L,
            "S_entry_U": S_entry_U,
            "S_exit_U": S_exit_U,
            "delta_S_load": S_exit_L - S_entry_L,
            "delta_S_unload": S_entry_U - S_exit_U,
        })

    last = cycle_history[-1]
    return {
        "final_S_exit_L": last["S_exit_L"],
        "final_S_exit_U": last["S_exit_U"],
        "final_delta_S_load": last["delta_S_load"],
        "final_delta_S_unload": last["delta_S_unload"],
        "cycle_convergence_err": abs(last["S_exit_U"] - cycle_history[-2]["S_exit_U"]),
        "history": cycle_history,
    }


def run_verification_suite() -> Dict[str, bool]:
    """
    Executes six mandatory consistency checks and verifies analytic vs numeric agreement.
    Failures are explicitly surfaced without silent fallbacks.
    """
    checks = {}

    # Standard baseline parameters
    PL, PU, P50, n = 100.0, 20.0, 30.0, 2.0
    kL, kU = 2.0, 2.0
    tauL, tauU = 1.5, 1.5
    B = 5.0

    # 1. No-Capacity Check (B = 0)
    res_no_cap = exact_css_map(PL, PU, P50, n, kL, kU, tauL, tauU, B=0.0)
    checks["no_capacity"] = (res_no_cap["q_cyc"] == 0.0 and res_no_cap["J_flux"] == 0.0)

    # 2. No-Gradient Check (PL == PU)
    res_no_grad = exact_css_map(50.0, 50.0, P50, n, kL, kU, tauL, tauU, B)
    checks["no_gradient"] = (
        abs(res_no_grad["delta_S_eq"]) < 1e-14
        and abs(res_no_grad["delta_S_cyc"]) < 1e-14
        and abs(res_no_grad["q_cyc"]) < 1e-14
    )

    # 3. Vanishing-Contact Check (tauL -> 0 or tauU -> 0)
    res_vanish = exact_css_map(PL, PU, P50, n, kL, kU, tauL=1e-9, tauU=1.5, B=B)
    checks["vanishing_contact"] = (res_vanish["delta_S_cyc"] < 1e-7 and res_vanish["eta_kin"] < 1e-7)

    # 4. Fast-Equilibration Check (tau -> inf or k -> inf)
    res_fast = exact_css_map(PL, PU, P50, n, kL=100.0, kU=100.0, tauL=10.0, tauU=10.0, B=B)
    checks["fast_equilibration"] = (abs(res_fast["eta_kin"] - 1.0) < 1e-6)

    # 5. Equal-Rate Symmetry Check
    # When kL=kU=k and tauL=tauU=tau, eta_kin must equal tanh(k*tau/2)
    k_sym, tau_sym = 1.8, 1.2
    res_sym = exact_css_map(PL, PU, P50, n, k_sym, k_sym, tau_sym, tau_sym, B)
    expected_eta = math.tanh(0.5 * k_sym * tau_sym)
    checks["equal_rate_tanh_symmetry"] = (abs(res_sym["eta_kin"] - expected_eta) < 1e-12)

    # 6. Mass-Balance & Analytic vs Numerical Match
    num_res = integrate_numerical_cycles(PL, PU, P50, n, kL, kU, tauL, tauU, B, n_cycles=50)
    exact_res = exact_css_map(PL, PU, P50, n, kL, kU, tauL, tauU, B)

    # Mass balance in steady state: delta_S_load == delta_S_unload
    mass_balance_err = abs(num_res["final_delta_S_load"] - num_res["final_delta_S_unload"])
    match_exit_L = abs(num_res["final_S_exit_L"] - exact_res["S_exit_L"])
    match_exit_U = abs(num_res["final_S_exit_U"] - exact_res["S_exit_U"])

    checks["cycle_mass_balance_closed"] = (mass_balance_err < 1e-5)
    checks["numerical_vs_analytic_match"] = (match_exit_L < 1e-5 and match_exit_U < 1e-5)

    return checks


def run_bounded_sweep(csv_filename: str = "sweep_results.csv") -> Dict[str, Any]:
    """
    Conducts parameter sweeps across P50:
      Case A: Constant relaxation rate (Affinity-independent).
      Case B: Affinity-dependent unbinding rate kU(P50) = kU0 * (P50 / Pref)^1.0.
    Identifies optimal P50 for each case and writes bounded CSV output.
    """
    PL, PU = 100.0, 10.0
    n = 2.0
    B = 5.0
    tauL, tauU = 0.8, 0.8
    kL = 2.5
    kU_base = 2.5
    P50_eq_opt = math.sqrt(PL * PU)  # sqrt(1000) ~= 31.622776

    P50_values = np.linspace(5.0, 80.0, 76).tolist()
    sweep_rows = []

    max_delivery_A = -1.0
    best_P50_A = None
    max_delivery_B = -1.0
    best_P50_B = None

    for p50 in P50_values:
        # Case A: Constant kinetics
        res_A = exact_css_map(PL, PU, p50, n, kL, kU_base, tauL, tauU, B)
        # Case B: Hypothetical affinity-dependent unbinding rate
        # Carrier with higher P50 releases O2 faster:
        kU_B = kU_base * (p50 / P50_eq_opt)
        res_B = exact_css_map(PL, PU, p50, n, kL, kU_B, tauL, tauU, B)

        if res_A["q_cyc"] > max_delivery_A:
            max_delivery_A = res_A["q_cyc"]
            best_P50_A = p50

        if res_B["q_cyc"] > max_delivery_B:
            max_delivery_B = res_B["q_cyc"]
            best_P50_B = p50

        sweep_rows.append({
            "P50": round(p50, 3),
            "delta_S_eq": round(res_A["delta_S_eq"], 6),
            "q_cyc_CaseA_const_k": round(res_A["q_cyc"], 6),
            "eta_kin_CaseA": round(res_A["eta_kin"], 6),
            "kU_CaseB": round(kU_B, 6),
            "q_cyc_CaseB_aff_k": round(res_B["q_cyc"], 6),
            "eta_kin_CaseB": round(res_B["eta_kin"], 6),
        })

    # Write bounded CSV
    with open(csv_filename, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_rows)

    summary = {
        "fixed_endpoints": {"PL": PL, "PU": PU, "Hill_n": n, "B_capacity": B},
        "times": {"tauL": tauL, "tauU": tauU},
        "theoretical_equilibrium_P50_opt": P50_eq_opt,
        "caseA_constant_kinetics": {
            "best_P50": best_P50_A,
            "max_q_cyc": max_delivery_A,
            "preserves_equilibrium_optimum": bool(abs(best_P50_A - P50_eq_opt) < 1.0),
        },
        "caseB_affinity_dependent_kinetics": {
            "best_P50": best_P50_B,
            "max_q_cyc": max_delivery_B,
            "optimum_shifted": bool(best_P50_B > P50_eq_opt + 2.0),
            "shift_description": (
                f"Peak shifted from {P50_eq_opt:.2f} to {best_P50_B:.2f} "
                "because finite off-rates penalize high-affinity carriers."
            ),
        },
    }

    return summary


def main():
    print("=================================================================")
    print("  Two-Compartment Finite-Kinetic Oxygen-Carrier Model")
    print("  Collaborators: Coda & Richard Pemberton | Research Program: The Stage")
    print("=================================================================\n")

    print("[1] Running Verification Suite...")
    checks = run_verification_suite()
    all_passed = True
    for name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  - Check '{name}': {status}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nERROR: Verification check failure detected!")
        sys.exit(1)
    print("\nAll verification checks passed successfully.")

    print("\n[2] Executing Bounded Sweep & Counterexample Analysis...")
    summary = run_bounded_sweep("finite_kinetic_sweep.csv")
    print("\nSweep and Counterexample Summary (JSON format):")
    print(json.dumps(summary, indent=2))
    print("\nSweep written to 'finite_kinetic_sweep.csv'.")


if __name__ == "__main__":
    main()
