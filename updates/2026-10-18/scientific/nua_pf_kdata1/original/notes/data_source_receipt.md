# PF-KDATA1 — Data source receipt (frozen before fitting, 2026-10-17)

## Chosen source (candidate 1 of max 3 inspected)

- Paper: Banerjee U, Wolfe S, O'Boyle Q, Cuddington C, Palmer AF (2022).
  "Scalable production and complete biophysical characterization of
  poly(ethylene glycol) surface conjugated liposome encapsulated hemoglobin
  (PEG-LEH)." PLOS ONE 17(7): e0269939.
- DOI: https://doi.org/10.1371/journal.pone.0269939
- License: CC-BY-4.0 (open access; "permits unrestricted use, distribution,
  and reproduction in any medium, provided the original author and source
  are credited").
- Data Availability: "All relevant data are within the paper and its
  Supporting Information files."
- SI file used: https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0269939.s001&type=supplementary
  - Format: Microsoft Excel 2007+ (.xlsx), 785141 bytes as downloaded.
  - Acquired: 2026-10-17 by direct public HTTP download (curl).
  - Local copy: raw/banerjee2022_S1.xlsx
  - sha256: computed at extraction time, recorded in inputs/manifest.json
- Sheets used: 'O2 Offloading RBCs', 'O2 Offloading Hbs', 'O2 Offloading LEHs'
  (Exp-flagged rows only; authors' Fit rows excluded from fitting).

## Why this source (and why no source 2/3 was needed)

- It is the packet's preferred class: ENCAPSULATED hemoglobin oxygen carrier
  (PEG-LEH, ~256 nm vesicles) measured ALONGSIDE cell-free human Hb and RBCs
  under identical stopped-flow conditions — the exact comparison needed to
  test whether a microscopic off-rate transfers to an encapsulated carrier.
- Downloadable numeric time courses (not figure-only): ~985-998 points per
  group. No digitization required.
- Required metadata present: 20°C, PBS 0.1 M pH 7.4, 437.5 nm, 15 µM heme,
  1.5 mg/mL sodium dithionite, SF-17 stopped-flow, SX17MV software,
  average of 10–15 kinetic traces per group.
- Stopped here (1 of 3 allowed): the source satisfies every packet criterion.

## Method facts (from the paper, for the boundary-condition record)

- Dithionite-driven deoxygenation: external free O2 is chemically scavenged,
  so the imposed boundary is s_eq ≈ 0 (not a physiological tissue boundary).
- Authors' analysis: koff,O2 = slope of ln(absorbance) vs time (single
  exponential); reported hHb control 34–41 s⁻¹, PEG-LEH ~3-fold lower,
  RBC ~4-fold lower than hHb.
- Replication: each Exp trace is a MEAN of 10–15 kinetic traces. No
  per-replicate data in the SI. Uncertainty below comes from fit residuals
  only; no replicates invented (packet rule).
