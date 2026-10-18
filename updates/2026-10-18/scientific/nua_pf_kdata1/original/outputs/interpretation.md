# PF-KDATA1 — Interpretation (concise)

## Question
Can a genuinely public measured O2-release time course constrain the
effective finite-relaxation parameter k in ds/dt = k·(s_eq − s) (AB-CT0)?

## Data
Banerjee et al. 2022, PLOS ONE 17(7):e0269939 (CC-BY-4.0), SI time courses:
stopped-flow dithionite deoxygenation of cell-free human Hb, RBCs, and
PEG-LEH nanoparticles (~256 nm). 20°C, PBS 0.1 M pH 7.4, 437.5 nm,
15 µM heme + 1.5 mg/mL dithionite (s_eq ≈ 0 boundary). Each trace = mean of
10–15 shots; no replicate-level data (uncertainty from residuals only).

## Results (12/30 fit calls used, 0 failures)
- M1 single-exponential k (dithionite-driven, 20°C):
  hHb 37.22 ± 0.18 s⁻¹ (authors' own 34–41 s⁻¹ — independent agreement);
  RBC 12.63 ± 0.26 s⁻¹; PEG-LEH 11.78 ± 0.08 s⁻¹.
  Ratios: RBC/hHb = 0.34, LEH/hHb = 0.32 → encapsulation retards the
  effective release rate ~3× under identical conditions.
- M2 (lag) NOT justified: t_lag → 0 with enormous SE in all groups;
  AICc worse than M1. No identifiable discrete lag.
- Window sensitivity: refitting M1 on the late window only (first 10% of
  time span dropped) gives hHb 41.7, RBC 4.6, LEH 2.2 s⁻¹. The single-k
  description is window-fragile for membrane-enclosed carriers: residuals
  show systematic fast-early / slow-late structure. Effective k spans
  ~2–12 s⁻¹ depending on timescale for LEH.

## Answer
PARTIAL YES with a structural caveat:
1. The data DO constrain k's order (~10 s⁻¹ early-phase for encapsulated
   carriers at 20°C under dithionite) and PROVE k is carrier-geometry
   dependent: a stopped-flow free-Hb k transferred to an encapsulated carrier
   overestimates release ~3×. A fixed-k AB-CT0 parameter cannot be shared
   across free and encapsulated carriers.
2. The data do NOT support a single constant k for encapsulated carriers:
   the relaxation is not single-exponential (fast early, slow late),
   consistent with a membrane-diffusion barrier acting alongside Hb-O2
   dissociation. AB-CT0's fixed-k form is misspecified for this case; at
   minimum k must be geometry-specific, and arguably timescale-aware.
3. These k values are NOT plug-in values for the channel model: dithionite
   boundary (s_eq≈0), 20°C not 37°C, no tissue demand, no decomposition of
   chemical off-rate vs membrane diffusion from this experiment alone.

## Limitations
- n=1 averaged trace per carrier (10–15 shots pre-averaged); CIs conditional.
- 20°C; dithionite-driven, not physiological unloading; SF-17 dead time
  unreported; hHb trace starts at 4 ms (fastest phase possibly truncated).
- No new models beyond the frozen two were fit (a biexponential was not
  attempted per plan); the window test is the evidence for two timescales.
