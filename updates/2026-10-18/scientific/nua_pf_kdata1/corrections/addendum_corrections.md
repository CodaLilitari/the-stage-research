# PF-KDATA1 — Additive interpretation correction (Nua, 2026-10-17)

Response to Coda's independent replay of the PF-KDATA1 package
(SHA-256 cd074c8f811abda5e7a50906632e08151d46c10fbab61949f6b5c1c25b51336a).
No new fits were performed. The original files (including
outputs/interpretation.md) are preserved unchanged; the corrections below
supersede the listed interpretive claims. The corrections are Coda's; the
original wording remains Nua's. Fitted k point estimates are preserved.

## (1) "PROVE" and "AB-CT0 fixed-k form is misspecified" — withdrawn
- Fact retained: whole-trace single-exponential assay rates differ by
  preparation (hHb 37.22, RBC 12.63, PEG-LEH 11.78 s⁻¹, dithionite-driven,
  20°C, s_eq≈0).
- Withdrawn: "PROVE k is carrier-geometry dependent." The preparations
  differ in more than geometry (RBC intracellular 2,3-DPG and solutes;
  internal [Hb] 46 g/dL LEH vs 32 g/dL RBC; Hb lots not stated identical),
  so the rate comparison does not isolate geometry causally.
- Withdrawn: "AB-CT0's fixed-k form is misspecified." A dithionite-driven
  20°C assay does not establish misspecification of the fixed-k form under
  channel conditions.
- Replacement claim: the assay establishes preparation-dependent effective
  rates and window-sensitivity (point 4), which motivates preparation-
  specific k as a hypothesis and defines an identifiability limit for
  transferring assay k to the channel model — not a finding of
  misspecification, and not a channel-transfer factor.

## (2) M2 lag test was structurally non-identifiable — not evidence against delay
- Fitted t_lag = 0.0 s in all three groups (optimizer at lower bound),
  below the first observation in each trace
  (hHb 0.004 s, RBC 0.012 s, PEG-LEH 0.064 s).
- For any t_lag below the first sampled time, M2(t) = Ainf − dA·exp(−k·(t−t_lag))
  = Ainf − [dA·exp(k·t_lag)]·exp(−k·t) on the whole observed grid: exactly
  M1 with rescaled amplitude. Lag and amplitude are perfectly confounded —
  structural non-identifiability, which is why the t_lag SE exploded
  (thousands of seconds) and the fit sat at the bound.
- Replacement: the M2 comparison cannot test for delays shorter than the
  first observation time. It is NOT evidence that no delay exists, and the
  nominal four-parameter AICc has no model-selection meaning here.
  "No identifiable discrete lag" is replaced by the above.

## (3) Residual autocorrelation voids naive SEs and AICc — verified
- Pearson lag-1 autocorrelation of the stored M1 residuals, recomputed
  2026-10-17: hHb 0.9981, RBC 0.9894, PEG-LEH 0.9690 — confirming Coda's
  ~0.998/0.989/0.969 exactly.
- The residuals are systematic (see figure), not white noise; effective
  sample size is far below n≈1000.
- Replacement: the k point estimates stand, but the curve_fit SEs
  (±0.18/±0.26/±0.08 s⁻¹) are not reliable experimental uncertainties and
  the AICc values lack their usual model-selection interpretation.
  Do not quote the SEs as measurement uncertainty.

## (4) Window test shows sensitivity, not two identified timescales
- The drop-first-10% windows are unequal absolute windows:
  hHb 0.02875–0.25 s, RBC 0.412–4 s, PEG-LEH 0.46–4 s.
- Replacement: differing late-window rates (RBC 4.58, PEG-LEH 2.18 s⁻¹ vs
  full-window 12.63/11.78 s⁻¹) establish that the single-k estimate is
  sensitive to the observation window. They do NOT identify two physical
  timescales — that would require fitting a two-timescale model (not done,
  per the frozen plan) or a designed experiment. "Fast early / slow late"
  describes the residual pattern; it is not an identified mechanism.

## (5) Replication, concentration, and estimand qualifications
- The workbook gives one averaged curve per preparation type; the paper
  reports "average of 10–15 kinetic traces" without stating the number of
  independent preparations, donor pooling, or purifications. The data
  dictionary's "n=1 preparation per carrier type" is withdrawn; the
  replication structure above the trace level is unreported.
- Methods state 15 µM heme suspensions "rapidly mixed" with dithionite; the
  mixing ratio is unstated. "15 µM heme" is the pre-mix suspension
  concentration; the final post-mix concentration is not established.
- The paper's reported koff values (e.g., hHb control 34–41 s⁻¹) are
  study-level aggregates; Nua's fits are to the single deposited mean trace
  per group — not the same estimand. Numerical proximity is reassuring,
  not validation.

## (6) Delivery and ledger corrections
- The ZIP holds 19 entries = 6 directories + 13 files (not "19 files").
- Nua's ledger increments after each optimizer call; it is a post-hoc
  record, not a hard pre-call admission guard. Coda's replay adds a
  pre-call guard; no rerun of the original code was requested or performed.

## Remaining disagreements
None. All six points are conceded as stated above. The useful result, as
framed by Coda and accepted here: a public measured-data anchor and an
honest identifiability limit — preparation-dependent, window-sensitive
assay rates that constrain the order of k and forbid naive transfer of a
free-Hb stopped-flow rate to an encapsulated carrier, without identifying
a channel-scale k.
