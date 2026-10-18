# PF-KDATA1 — Data dictionary (frozen before fitting)

Source: raw/banerjee2022_S1.xlsx, sheets 'O2 Offloading RBCs' /
'O2 Offloading Hbs' / 'O2 Offloading LEHs'. Extracted input:
inputs/o2_offloading_exp.csv (Exp rows only).

## Columns in the extracted CSV

| column | meaning | units | notes |
|---|---|---|---|
| group | carrier identity | — | hHb = cell-free human Hb; RBC = human red blood cells; PEG-LEH = liposome-encapsulated Hb nanoparticles (~256 nm) |
| t_s | time since rapid mixing | seconds | hHb: 0.004–0.25 s, dt=0.00025 s; RBC: 0.012–4 s, dt=0.004 s; PEG-LEH: 0.064–4 s, dt=0.004 s |
| absorbance_437nm | measured absorbance at 437.5 nm | AU (arbitrary units) | increases as Hb deoxygenates (deoxyHb absorbs more at 437.5 nm) |
| src_row | 1-based row index in the SI sheet (Exp rows) | — | provenance pointer, not analysis data |

## Columns present in SI but NOT used

- Fit ('Exp' vs 'Fit' flag): only 'Exp' rows extracted; authors' fitted curves
  are not data.
- Norm: authors' normalized progress (their endpoint choices; RBC Exp starts
  at −0.26, an artifact of their normalization). Not used; k is invariant
  under affine rescaling of the observable, so we fit raw absorbance.
- Value: the raw absorbance; renamed absorbance_437nm for clarity.

## Replication / identity notes

- Each (group) trace = mean of 10–15 stopped-flow shots (paper). No
  shot-level data available. n_points refers to time samples, not replicates.
- Biological replication: one preparation per group reported (RBCs from
  pooled expired donor units; hHb purified once; one PEG-LEH batch).
  Treat as n=1 preparation per carrier type.
- Instrument: Applied Photophysics SF-17 stopped-flow; dead time not stated
  in the paper (typical SF-17 ~1–2 ms); hHb trace starts at 4 ms — the
  fastest phase may be partially truncated (noted as a limitation).
- Temperature 20°C (NOT 37°C); pH 7.4 PBS 0.1 M; heme 15 µM; dithionite
  1.5 mg/mL. Dithionite both drives deoxygenation AND defines the boundary
  (s_eq≈0); it is not a passive observer.
