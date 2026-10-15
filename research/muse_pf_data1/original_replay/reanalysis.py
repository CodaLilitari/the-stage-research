"""
PF-DATA1 reanalysis — Stuecker et al. 2002, Table 1 (PMC2290093).

FROZEN QUESTION (fixed before analysis):
  In the per-subject paired transcutaneous O2-flux data:
  (1) Is the occlusion-induced flux increase a fixed ABSOLUTE rate or
      PROPORTIONAL to resting flux? (tests whether the blood/channel
      supply behaves as a fixed baseline or a fixed fraction of demand)
  (2) Does flux scale LINEARLY with surface pO2 across the two measured
      boundary conditions per subject? (tests boundary-driven vs
      consumption-limited supply)
  (3) What per-subject thickness of the atmospherically-supplied skin
      layer follows from the measured fluxes, with propagated uncertainty?
      (empirical constraint for PF0 channel-spacing / demand constants)

Inputs: ../raw/stuecker2002_table1.csv (transcription of the published table).
Literature inputs (labeled, not measured here): skin VO2 range 1470-2110
ml O2 m^-3 min^-1 (Evans & Naylor, via the paper); stratum corneum 15 um.
"""
import hashlib, json
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = "../raw/stuecker2002_table1.csv"
OUT = "../outputs"

# ---------------- load + provenance ----------------
df = pd.read_csv(RAW)
raw_bytes = open(RAW, "rb").read()
sha = hashlib.sha256(raw_bytes).hexdigest()
assert len(df) == 20 and df.isna().sum().sum() == 0, "table must be 20 complete rows"

J_red  = df["flux_reduced_mlO2_min_m2"].to_numpy()   # ml O2 min^-1 m^-2
J_norm = df["flux_norm_mlO2_min_m2"].to_numpy()
P_red  = df["sspO2_reduced_Torr"].to_numpy()
P_norm = df["sspO2_norm_Torr"].to_numpy()
dJ     = df["occlusion_delta_mlO2_min_m2"].to_numpy()  # INCREASE, not total
age    = df["age_years"].to_numpy()

# ---------------- 0. transcription verification (analytic check) ----------------
# Reported column summaries (mean, sd) from the paper's Table 1 footer:
reported = {
    "P_red":  (101.4, 12.2), "J_red":  (0.334, 0.100),
    "P_norm": (163.0, 9.0),  "J_norm": (0.529, 0.265),
    "dJ":     (0.037, 0.013),
}
got = {"P_red": P_red, "J_red": J_red, "P_norm": P_norm, "J_norm": J_norm, "dJ": dJ}
# Reported column summaries are printed to limited precision (e.g. sd 9, 12.2),
# so tolerance must cover their rounding, not just transcription error.
TOL_MEAN, TOL_SD = 0.15, 0.5
checks = {}
for k, (m, s) in reported.items():
    v = got[k]
    checks[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)),
                 "mean_ok": bool(abs(v.mean() - m) < TOL_MEAN),
                 "sd_ok": bool(abs(v.std(ddof=1) - s) < TOL_SD)}
assert all(c["mean_ok"] and c["sd_ok"] for c in checks.values()), f"transcription mismatch: {checks}"

# Instrument-chain sanity check: flux = (K/d) * dP
K = 3.58e-7        # ml O2 min^-1 m^-1 Torr^-1, membrane conductivity (n=7)
d_mem = 55e-6      # m
P_mem = K / d_mem  # ml O2 m^-2 min^-1 Torr^-1
pred_J = P_mem * (P_norm.mean() - P_red.mean())  # not used as data; order check only
instrument_check = {"P_membrane": float(P_mem),
                    "typical_dP_Torr": float((P_norm - P_red).mean()),
                    "implied_flux_scale": float(P_mem * (P_norm - P_red).mean())}

# ---------------- 1. occlusion effect: paired test ----------------
t_stat, t_p = stats.ttest_1samp(dJ, 0.0)          # H0: no increase
w_stat, w_p = stats.wilcoxon(dJ)                  # rank-based robustness
rel = dJ / J_norm                                  # per-subject relative increase
young = age < 30
old = age > 70
ty, py = stats.ttest_ind(J_norm[young], J_norm[old])

# ---------------- 2. fixed-absolute vs proportional blood supply ----------------
r_pearson, r_p = stats.pearsonr(J_norm, dJ)
slope, intercept, rval, pval, stderr = stats.linregress(J_norm, dJ)
# through-origin (proportional) fit: dJ = b * J_norm
b_prop = float((J_norm @ dJ) / (J_norm @ J_norm))
resid_intercept = dJ - (slope * J_norm + intercept)
resid_prop = dJ - b_prop * J_norm
ss_int = float((resid_intercept ** 2).sum())
ss_prop = float((resid_prop ** 2).sum())
# sensitivity: drop anomalous volunteer 19 (J_norm < J_red)
m19 = df["volunteer"].to_numpy() != 19
slope_s, int_s, _, _, _ = stats.linregress(J_norm[m19], dJ[m19])
r_s, _ = stats.pearsonr(J_norm[m19], dJ[m19])

# ---------------- 3. flux vs surface pO2 (per-subject, two boundary points) ----------------
dP = P_norm - P_red
dJp = J_norm - J_red
slope_p = dJp / dP                      # per-subject dJ/dP
intercept_p = J_red - slope_p * P_red   # extrapolated J at P=0
ti, pi = stats.ttest_1samp(intercept_p, 0.0)  # is the intercept distinguishable from 0?
ratio_J = J_red / J_norm
ratio_P = P_red / P_norm

# ---------------- 4. atmospherically-supplied layer thickness, with uncertainty ----------------
# T = J_norm / VO2  (+ 15 um non-consuming stratum corneum), per paper eq. (5)
rng = np.random.default_rng(20261015)
VO2_lo, VO2_hi = 1470.0, 2110.0       # ml O2 m^-3 min^-1, literature (Evans & Naylor via paper)
N_MC = 200_000
VO2 = rng.uniform(VO2_lo, VO2_hi, N_MC)
J_pop = rng.choice(J_norm, N_MC)       # resample subjects (biological variability)
T_pop = J_pop / VO2 * 1e6 + 15.0       # um  (ml/m^2/min / ml/m^3/min = m -> *1e6 = um)
T_med = float(np.median(T_pop)); T_lo, T_hi = (float(x) for x in np.percentile(T_pop, [2.5, 97.5]))
# per-subject posterior medians
T_sub = []
for j in J_norm:
    Ts = j / VO2 * 1e6 + 15.0
    T_sub.append((float(np.median(Ts)), float(np.percentile(Ts, 2.5)), float(np.percentile(Ts, 97.5))))
T_sub = np.array(T_sub)

# ---------------- 5. PF0 comparison: demand constant + penetration depth ----------------
# ml O2 -> mol: molar volume 24.465 L/mol at 25 C, 1 atm
ML_PER_MOL = 24465.0
q_skin = np.array([VO2_lo, VO2_hi]) / 60.0 / ML_PER_MOL   # mol m^-3 s^-1
q_pf0 = 0.02                                             # mol m^-3 s^-1, PF0 illustrative (liver-like)
D, Cfree = 2e-9, 0.2                                     # m^2/s, mol/m^3 (PF0 values)
L = lambda q: np.sqrt(2 * D * Cfree / q)                 # zero-order penetration depth, m
pen_skin = L(q_skin.mean()) * 1e6                        # um
pen_pf0 = L(q_pf0) * 1e6
demand_ratio = q_pf0 / q_skin.mean()

# ---------------- outputs ----------------
derived = pd.DataFrame({
    "volunteer": df["volunteer"], "age_years": age,
    "flux_norm": J_norm, "occlusion_delta": dJ,
    "rel_occlusion_increase_pct": 100 * rel,
    "pO2_slope_ml_per_m2_min_Torr": slope_p,
    "pO2_intercept": intercept_p,
    "layer_thickness_med_um": T_sub[:, 0],
    "layer_thickness_lo_um": T_sub[:, 1],
    "layer_thickness_hi_um": T_sub[:, 2],
})
derived.to_csv(f"{OUT}/per_subject_derived.csv", index=False)

summary = {
  "provenance": {"doi": "10.1113/jphysiol.2001.013067", "pmcid": "PMC2290093",
                 "table": "Table 1", "n_volunteers": 20,
                 "acquired": "2026-10-15", "method": "transcription from open-access HTML table",
                 "sha256_raw_csv": sha},
  "transcription_checks": checks,
  "instrument_check": instrument_check,
  "occlusion_effect": {
    "delta_mean": float(dJ.mean()), "delta_sd": float(dJ.std(ddof=1)),
    "rel_increase_pct_mean": float(100*rel.mean()), "rel_increase_pct_sd": float(100*rel.std(ddof=1)),
    "ttest_t": float(t_stat), "ttest_p": float(t_p),
    "wilcoxon_p": float(w_p)},
  "age_groups": {"young_mean": float(J_norm[young].mean()), "young_sd": float(J_norm[young].std(ddof=1)),
                 "old_mean": float(J_norm[old].mean()), "old_sd": float(J_norm[old].std(ddof=1)),
                 "ttest_p": float(py)},
  "absolute_vs_proportional": {
    "pearson_r_delta_vs_flux": float(r_pearson), "pearson_p": float(r_p),
    "ols_slope": float(slope), "ols_intercept": float(intercept),
    "ols_intercept_se": float(stderr), "ols_p_slope": float(pval),
    "through_origin_slope": b_prop,
    "ss_resid_with_intercept": ss_int, "ss_resid_through_origin": ss_prop,
    "sensitivity_drop_v19": {"pearson_r": float(r_s), "ols_slope": float(slope_s),
                             "ols_intercept": float(int_s)}},
  "flux_vs_pO2": {
    "per_subject_slope_mean": float(slope_p.mean()), "per_subject_slope_sd": float(slope_p.std(ddof=1)),
    "per_subject_intercept_mean": float(intercept_p.mean()),
    "per_subject_intercept_sd": float(intercept_p.std(ddof=1)),
    "intercept_ttest_t": float(ti), "intercept_ttest_p": float(pi),
    "mean_flux_ratio": float(ratio_J.mean()), "mean_pO2_ratio": float(ratio_P.mean())},
  "layer_thickness_um": {"population_median": T_med, "ci95": [T_lo, T_hi],
                         "paper_range": [251, 360],
                         "per_subject_median_range": [float(T_sub[:,0].min()), float(T_sub[:,0].max())]},
  "pf0_comparison": {
    "skin_q_mol_m3_s_range": [float(q_skin[0]), float(q_skin[1])],
    "pf0_q_mol_m3_s": q_pf0,
    "demand_ratio_pf0_over_skin": float(demand_ratio),
    "penetration_depth_um": {"skin_q": float(pen_skin), "pf0_q": float(pen_pf0)}},
}
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)

# ---------------- figure ----------------
fig, ax = plt.subplots(2, 2, figsize=(11, 9))
fig.suptitle("PF-DATA1: Stuecker 2002 per-subject skin O2-flux reanalysis (n=20)", fontsize=12)

a = ax[0, 0]
for i in range(20):
    a.plot([P_red[i], P_norm[i]], [J_red[i], J_norm[i]], "o-", ms=3, lw=0.7,
           color="steelblue", alpha=0.6)
a.set_xlabel("skin-surface pO2 (Torr)"); a.set_ylabel("transcutaneous O2 flux (ml min$^{-1}$ m$^{-2}$)")
a.set_title("(a) flux vs surface pO2, paired per subject")
a.grid(alpha=0.3)

b = ax[0, 1]
b.scatter(J_norm, dJ, c=age, cmap="coolwarm", s=40, zorder=3)
xs = np.linspace(0, J_norm.max()*1.05, 50)
b.plot(xs, slope*xs + intercept, "k-", lw=1.5, label=f"OLS: dJ={slope:.3f}·J+{intercept:.3f}")
b.plot(xs, b_prop*xs, "k--", lw=1.2, label=f"proportional: dJ={b_prop:.3f}·J")
b.set_xlabel("resting flux J (ml min$^{-1}$ m$^{-2}$)")
b.set_ylabel("occlusion increase ΔJ (ml min$^{-1}$ m$^{-2}$)")
b.set_title(f"(b) occlusion ΔJ vs resting flux (r={r_pearson:.2f}, p={r_p:.3f})")
b.legend(fontsize=8); b.grid(alpha=0.3)

c = ax[1, 0]
c.hist(T_pop, bins=60, color="seagreen", alpha=0.7, density=True)
c.axvline(T_med, color="k", lw=1.5, label=f"median {T_med:.0f} µm")
c.axvspan(T_lo, T_hi, color="k", alpha=0.12, label="95% interval")
c.set_xlabel("atmospherically-supplied layer thickness (µm)")
c.set_ylabel("density"); c.set_title("(c) layer thickness, T=J/VO2+15µm (MC)")
c.legend(fontsize=8); c.grid(alpha=0.3)

d = ax[1, 1]
labels = ["skin (literature\nVO2 range)", "PF0 illustrative\n(liver-like qmax)"]
vals = [q_skin.mean(), q_pf0]
d.bar(labels, vals, color=["seagreen", "firebrick"], log=True)
d.set_ylabel("volumetric O2 demand (mol m$^{-3}$ s$^{-1}$, log)")
d.set_title(f"(d) demand constants: PF0 ≈ {demand_ratio:.0f}× skin")
for i, v in enumerate(vals):
    y = v / 3 if v > 0.01 else v * 1.6   # keep tall-bar label inside the bar
    d.text(i, y, f"{v:.4f}", ha="center", fontsize=9,
           color="white" if v > 0.01 else "black")
d.grid(alpha=0.3, axis="y")

fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(f"{OUT}/figure.png", dpi=150)
print(json.dumps({k: summary[k] for k in
      ["occlusion_effect","absolute_vs_proportional","flux_vs_pO2",
       "layer_thickness_um","pf0_comparison"]}, indent=1))
print("transcription checks:", all(c["mean_ok"] and c["sd_ok"] for c in checks.values()))
