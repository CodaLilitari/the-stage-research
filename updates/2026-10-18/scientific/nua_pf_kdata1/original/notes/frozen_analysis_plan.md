# PF-KDATA1 — Frozen analysis plan (written BEFORE any fit, 2026-10-17)

## Question
Can a genuinely public measured O2-release time course constrain the
effective finite-relaxation parameter k in ds/dt = k·(s_eq − s) as used in
the AB-CT0 channel model — and specifically, is k carrier-geometry dependent
(free vs encapsulated Hb), or does the stopped-flow free-Hb rate transfer?

## Competing models (at most two)
- M1 (single exponential): A(t) = Ainf − dA·exp(−k·t).
  This is the exact solution of ds/dt = −k·s (s_eq = 0 under dithionite).
- M2 (exponential with lag): A(t) = A0 for t < t_lag;
  A(t) = Ainf − dA·exp(−k·(t − t_lag)) for t ≥ t_lag, with
  A0 = Ainf − dA (continuity). Captures mixing/dead-time or a fast initial
  phase; justified only if residuals demand it (RBC Exp starts below the
  authors' fit, hinting at early-time mismatch).

Parameters per group: (Ainf, dA, k) for M1; (Ainf, dA, k, t_lag) for M2.
Fit per group independently (hHb, RBC, PEG-LEH): 3×2 = 6 planned fits.

## Declared residual / uncertainty checks
1. Residual-vs-time plots for each fit (structure vs white noise).
2. Parameter CIs from curve_fit covariance (conditional on model and on the
   averaged trace; NOT a replicate-based interval — stated as such).
3. Descriptive model comparison: residual SS and AICc (no causal claim).
4. Window sensitivity: refit M1 on (a) full window, (b) first 10% of time
   dropped, (c) last 20% dropped — 3 groups × 2 extra windows = 6 checks.
   If k moves substantially, the single-k description is window-dependent.
5. Cross-group k ratios (k_RBC/k_hHb, k_LEH/k_hHb): the transferable finding
   for the channel model — does encapsulation retard the effective rate?

## Pre-declared interpretation rules
- k̂ is a DITHIONITE-DRIVEN effective deoxygenation rate at 20°C with
  s_eq≈0. It is not the channel-scale k at 37°C with finite boundary O2.
  A tight statistical CI does not make it the AB-CT0 parameter.
- What the data CAN constrain: the ORDER of k, and whether effective k is
  geometry-dependent (the membrane-barrier factor). If k_LEH ≈ k_hHb/3,
  then plugging a stopped-flow free-Hb k into a channel model for an
  encapsulated carrier overestimates release ~3× — a concrete, useful
  constraint on HOW k must be specified, not its value.
- What it CANNOT identify: decomposition into chemical off-rate vs membrane
  diffusion vs dithionite kinetics (single experiment, no separation);
  temperature extrapolation to 37°C; behavior under finite tissue O2 demand.
- Negative result is acceptable: if M1/M2 cannot be distinguished or k is
  window-fragile, report that the dataset does not identify a stable k.

## Budget
≤30 fit/validation calls total (each curve_fit invocation = 1 call).
Planned: 6 (models) + 6 (window sensitivity) = 12. Ledger:
notes/fit_ledger.json, counter frozen at 0 before fitting, incremented per
call, failures recorded with reason.
