#!/usr/bin/env python3
"""
THE STAGE — Human Oxygen Carrier Equilibrium, Identifiability & Kinetic Reversal Suite
STATUS: UNEXECUTED (Provided for local execution by Coda & Richard Pemberton)
Dependencies: numpy, pandas, scipy
Input: oxygen_carriers_primary_data.csv (must be in the same directory)
Outputs:
  1. stage_carrier_ranking_comparison.csv (Equilibrium vs. Coupled Kinetic-Degradation Rankings)
  2. stage_hill_identifiability_audit.csv (Held-out pressure regime & Fisher Information check)
"""

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

# ---------------------------------------------------------------------------
# 1. Core Biophysical Models
# ---------------------------------------------------------------------------
def hill_saturation(pO2: np.ndarray, p50: float, n: float) -> np.ndarray:
    """Fractional O2 saturation S(P) via the Hill equation."""
    p = np.asarray(pO2, dtype=float)
    return (p ** n) / (p ** n + p50 ** n)


def hill_jacobian(pO2: np.ndarray, p50: float, n: float) -> np.ndarray:
    """Analytical Jacobian [dS/dP50, dS/dn] for Fisher Information Matrix identifiability."""
    p = np.asarray(pO2, dtype=float)
    s = hill_saturation(p, p50, n)
    w = s * (1.0 - s)
    dS_dp50 = - (n / p50) * w
    # Avoid log(0) if pO2 == 0
    with np.errstate(divide="ignore", invalid="ignore"):
        log_ratio = np.where(p > 0, np.log(p / p50), 0.0)
    dS_dn = w * log_ratio
    return np.column_stack([dS_dp50, dS_dn])


def evaluate_carrier_performance(
    df: pd.DataFrame,
    p_load: float = 80.0,
    p_unload: float = 20.0,
    tau_cap_s: float = 0.15,
    t_mission_h: float = 12.0,
    alpha_no_vaso: float = 0.012,
    n_mc: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Compares static HC0 equilibrium O2 delivery against a coupled
    Equilibrium-Kinetic-Degradation (EKD) model with Monte Carlo uncertainty propagation.

    Parameters:
      - p_load, p_unload (mmHg): Arterial loading and tissue unloading partial pressures
      - tau_cap_s (s): Capillary / microchannel transit residence time
      - t_mission_h (h): Cumulative circulation time at 37 C without enzymatic rejuvenation
      - alpha_no_vaso: Empirical arteriolar radius sensitivity to k_ox_NO (r/r0 = 1 / (1 + alpha * k_ox_NO))
    """
    rng = np.random.default_rng(seed)
    HUFNER_ML_O2_PER_G_HB = 1.34  # mL O2 per g functional Hb

    # Empirical thermal autoxidation rate k_auto (h^-1) at 37 C when enzymatic reduction is absent:
    # Intact RBCs have active NADH-cytochrome b5 reductase (net k_auto ~ 0.0005 h^-1).
    # Cell-free / unreduced encapsulated Hb scales with P50 (Wyman redox coupling).
    records = []

    for _, row in df.dropna(subset=["P50_mmHg_mean", "hill_n_mean", "Hb_susp_gdL_mean"]).iterrows():
        sid = row["sample_id"]
        c_class = row["carrier_class"]

        p50_mu = float(row["P50_mmHg_mean"])
        p50_sd = float(row["P50_mmHg_sd"]) if pd.notna(row["P50_mmHg_sd"]) else 0.0
        n_mu = float(row["hill_n_mean"])
        n_sd = float(row["hill_n_sd"]) if pd.notna(row["hill_n_sd"]) else 0.0
        hb_mu = float(row["Hb_susp_gdL_mean"])
        hb_sd = float(row["Hb_susp_gdL_sd"]) if pd.notna(row["Hb_susp_gdL_sd"]) else 0.0

        k_off_mu = float(row["k_off_O2_s1_mean"]) if pd.notna(row["k_off_O2_s1_mean"]) else 15.0
        k_off_sd = float(row["k_off_O2_s1_sd"]) if pd.notna(row["k_off_O2_s1_sd"]) else 0.0

        k_no_mu = float(row["k_ox_NO_uM1s1_mean"]) if pd.notna(row["k_ox_NO_uM1s1_mean"]) else 1.0
        k_no_sd = float(row["k_ox_NO_uM1s1_sd"]) if pd.notna(row["k_ox_NO_uM1s1_sd"]) else 0.0

        met0_pct = float(row["metHb_initial_pct_mean"]) if pd.notna(row["metHb_initial_pct_mean"]) else 1.0

        # Assign net 37 C autoxidation rate k_auto (h^-1)
        if c_class == "Native_Erythrocyte":
            k_auto_h1 = 0.0005  # Active intracellular metHb reductase
        elif "Encapsulated" in c_class:
            k_auto_h1 = 0.018 * (p50_mu / 25.0) ** 0.5  # Moderated by co-encapsulated reductants/vesicle
        else:
            k_auto_h1 = 0.035 * (p50_mu / 25.0) ** 0.6  # Acellular Hb in plasma

        # Monte Carlo sampling (clipped to physical bounds)
        p50_s = np.clip(rng.normal(p50_mu, p50_sd, n_mc), 0.2, 150.0)
        n_s = np.clip(rng.normal(n_mu, n_sd, n_mc), 1.0, 4.5)
        hb_s = np.clip(rng.normal(hb_mu, hb_sd, n_mc), 1.0, 50.0)
        k_off_s = np.clip(rng.normal(k_off_mu, k_off_sd, n_mc), 0.5, 200.0)
        k_no_s = np.clip(rng.normal(k_no_mu, k_no_sd, n_mc), 0.01, 150.0)

        # 1. Static HC0 Equilibrium Extraction
        s_load = hill_saturation(p_load, p50_s, n_s)
        s_unload = hill_saturation(p_unload, p50_s, n_s)
        delta_s_eq = s_load - s_unload

        # Volumetric equilibrium O2 delivered per dL suspension (mL O2 / dL)
        c_max = hb_s * HUFNER_ML_O2_PER_G_HB
        do2_eq_mLdL = c_max * delta_s_eq

        # 2. Non-Equilibrium Corrections:
        # (a) Capillary transit residence-time factor (Damkohler unloading efficiency)
        f_kin_unload = 1.0 - np.exp(-k_off_s * tau_cap_s)

        # (b) Pre-capillary arteriolar O2 dumping penalty (if k_off > 15 s^-1 in acellular plasma)
        f_art_retention = np.where(
            "Acellular" in c_class,
            np.exp(-0.008 * np.maximum(k_off_s - 12.0, 0.0)),
            1.0,
        )

        # (c) Hagen-Poiseuille vasoconstriction flow factor Q/Q0 = (r/r0)^4 from NO scavenging
        r_ratio = 1.0 / (1.0 + alpha_no_vaso * k_no_s)
        q_flow_factor = r_ratio ** 4

        # (d) Active ferrous heme survival at t_mission_h
        f_redox_active = (1.0 - met0_pct / 100.0) * np.exp(-k_auto_h1 * t_mission_h)

        # Net coupled O2 delivery index (mL O2 / dL effective perfusion equivalent)
        do2_ekd_mLdL = (
            do2_eq_mLdL
            * f_kin_unload
            * f_art_retention
            * q_flow_factor
            * f_redox_active
        )

        records.append({
            "sample_id": sid,
            "carrier_class": c_class,
            "P50_mmHg": p50_mu,
            "hill_n": n_mu,
            "delta_S_eq_mean": np.mean(delta_s_eq),
            "delta_S_eq_sd": np.std(delta_s_eq),
            "DO2_HC0_eq_mLdL_mean": np.mean(do2_eq_mLdL),
            "DO2_HC0_eq_mLdL_sd": np.std(do2_eq_mLdL),
            "f_kin_unload_mean": np.mean(f_kin_unload),
            "Q_Poiseuille_factor_mean": np.mean(q_flow_factor),
            "f_redox_12h": f_redox_active,
            "DO2_EKD_net_mLdL_mean": np.mean(do2_ekd_mLdL),
            "DO2_EKD_net_mLdL_sd": np.std(do2_ekd_mLdL),
        })

    out_df = pd.DataFrame(records)
    # Normalize to fixed [Hb] = 12 g/dL as well so intrinsic carrier properties can be ranked
    out_df["HC0_Rank_Intrinsic_dS"] = out_df["delta_S_eq_mean"].rank(ascending=False).astype(int)
    out_df["EKD_Rank_Net_Delivery"] = out_df["DO2_EKD_net_mLdL_mean"].rank(ascending=False).astype(int)
    out_df["Rank_Reversed"] = out_df["HC0_Rank_Intrinsic_dS"] != out_df["EKD_Rank_Net_Delivery"]
    return out_df.sort_values("EKD_Rank_Net_Delivery")


# ---------------------------------------------------------------------------
# 2. Held-Out Pressure Regime & Identifiability Check
# ---------------------------------------------------------------------------
def run_identifiability_and_heldout_check(
    p50_true: float = 17.60,
    n_true: float = 1.92,
    noise_sd: float = 0.008,
    seed: int = 101,
) -> pd.DataFrame:
    """
    Tests parameter identifiability (Fisher Information Matrix condition number)
    and held-out regime prediction error when fitting Hill parameters across:
      - Regime A (Full OEC: 2 to 140 mmHg)
      - Regime B (Physiological window only: 20 to 100 mmHg, holding out <20 mmHg hypoxic foot)
      - Regime C (Venous/Hypoxic only: 2 to 35 mmHg, holding out >35 mmHg arterial shoulder)
    """
    rng = np.random.default_rng(seed)
    p_full = np.array([2, 4, 6, 8, 10, 12, 15, 18, 20, 25, 30, 40, 50, 60, 80, 100, 120, 140], dtype=float)
    s_clean = hill_saturation(p_full, p50_true, n_true)
    s_obs = np.clip(s_clean + rng.normal(0.0, noise_sd, size=p_full.size), 1e-4, 0.9999)

    regimes = {
        "Full_OEC_2_140mmHg": (p_full >= 2.0),
        "Restricted_Physiol_20_100mmHg_HoldOut_HypoxicFoot": (p_full >= 20.0) & (p_full <= 100.0),
        "Restricted_Hypoxic_2_35mmHg_HoldOut_Arterial": (p_full <= 35.0),
    }

    rows = []
    for name, mask in regimes.items():
        p_train, s_train = p_full[mask], s_obs[mask]
        p_test, s_test = p_full[~mask], s_clean[~mask]

        popt, pcov = curve_fit(
            hill_saturation,
            p_train,
            s_train,
            p0=[25.0, 2.0],
            bounds=([0.1, 0.5], [150.0, 5.0]),
        )
        p50_hat, n_hat = popt
        se = np.sqrt(np.diag(pcov))

        # Fisher Information Matrix J^T J condition number on training grid
        J = hill_jacobian(p_train, p50_hat, n_hat)
        fim = J.T @ J
        cond_num = float(np.linalg.cond(fim))

        rmse_train = float(np.sqrt(np.mean((hill_saturation(p_train, p50_hat, n_hat) - s_train) ** 2)))
        rmse_holdout = (
            float(np.sqrt(np.mean((hill_saturation(p_test, p50_hat, n_hat) - s_test) ** 2)))
            if p_test.size > 0
            else np.nan
        )

        rows.append({
            "regime": name,
            "n_train_pts": int(p_train.size),
            "n_holdout_pts": int(p_test.size),
            "P50_true": p50_true,
            "P50_fit": p50_hat,
            "P50_SE": se[0],
            "n_true": n_true,
            "n_fit": n_hat,
            "n_SE": se[1],
            "FIM_condition_number": cond_num,
            "RMSE_train": rmse_train,
            "RMSE_holdout": rmse_holdout,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df_raw = pd.read_csv("oxygen_carriers_primary_data.csv")

    # 1. Run HC0 vs. EKD coupled evaluation at Pload=80, Punload=20 mmHg
    df_rank = evaluate_carrier_performance(df_raw, p_load=80.0, p_unload=20.0)
    df_rank.to_csv("stage_carrier_ranking_comparison.csv", index=False)
    print("=== Carrier Ranking Comparison (HC0 Equilibrium vs. EKD Coupled) ===")
    print(df_rank[[
        "sample_id", "P50_mmHg", "hill_n", "delta_S_eq_mean",
        "Q_Poiseuille_factor_mean", "f_redox_12h",
        "DO2_HC0_eq_mLdL_mean", "DO2_EKD_net_mLdL_mean",
        "HC0_Rank_Intrinsic_dS", "EKD_Rank_Net_Delivery", "Rank_Reversed"
    ]].to_string(index=False))

    # 2. Run Identifiability & Held-Out Pressure Regime Audit on PEG-LEH_256nm parameters
    df_ident = run_identifiability_and_heldout_check(p50_true=17.60, n_true=1.92)
    df_ident.to_csv("stage_hill_identifiability_audit.csv", index=False)
    print("\n=== Hill Parameter Identifiability & Held-Out Regime Audit ===")
    print(df_ident.to_string(index=False))
