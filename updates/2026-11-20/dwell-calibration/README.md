# Four heater schedules expose two limits of the simulated thermal gate

The Stage's first milestone is artificial blood. This study concerns temperature feedback on the machine-circulation branch. In 300 held-out missions per simulated panel, the existing gate accepted every fit. The H1 panel exceeded the project's 0.2 K probe-error allowance on all 300 missions. H2 exceeded it on zero. A second test set a stricter threshold from each panel's own calibration data. The H2 threshold was too optimistic on the held-out sample.

| Simulated panel | Measurement noise SD | Calibrated common bound | Held-out missions above that bound | Held-out missions above 0.2 K |
|---|---:|---:|---:|---:|
| H1, 0.5 mm | 0.01 K | 0.262173 K | 2/300 (0.67%) | 300/300 |
| H2, 1.0 mm | 0.001 K | 0.073258 K | 31/300 (10.33%) | 0/300 |

For the calibrated common bound, individual two-sided exact 95% intervals for the exceedance rate were **0.081% to 2.387%** on H1 and **7.130% to 14.346%** on H2. The desired upper limit was 5%. H2 met the original 0.2 K allowance on this holdout, yet its much smaller data-derived bound missed the coverage target. The study retains the original seeds and both thresholds. The panels differ in both thickness and noise. This comparison cannot isolate either effect.

## What counted as one mission

Each mission used one noisy 450-transition calibration trace to fit the published two-node thermal model. That fit then predicted four 900-second square-wave heater schedules beginning at 2 W and alternating with 5 W every 5, 15, 30 or 60 seconds. For each schedule the fitted and exact predictions started from two copies of the fitted 5 W steady-state temperature. At each eligible time we compared the change between two five-reading means separated by 61 seconds. We took the largest absolute difference between fitted and exact changes over 836 windows, then the largest across the four schedules. Four measurements of the same fit count as one mission.

The two earlier studies used a different command sequence or a pointwise error with different starting temperatures. The present study uses a fixed 61-second lag at every dwell. All fitted missions enter the analysis regardless of gate decisions. All 772 fits produced finite measurements and passed both the original gate and the four schedule-specific gate evaluations.

## How much calibration data supports the claim?

The mission bound aims to cover at least 95% of future mission maxima in the same stack, noise model and command domain, with at least 95% confidence over a fresh calibration sample. Independent missions are the sampling units. If the bound is the largest of *n* calibration maxima, its confidence is at least 1 − 0.95ⁿ, with equality for continuous errors. This requires **59 independent missions** at minimum. Four dwell-specific bounds with simultaneous confidence require **86 missions** by a union bound, using a per-dwell failure probability of 0.05/4. Those four bounds each cover 95% of their own dwell population when valid. They do not by themselves guarantee 95% joint mission coverage.

We froze 86 calibration missions and 300 held-out missions per stack with separate pseudorandom streams. In both designs the selected ascending rank was 86 of 86. The common-bound construction has 98.786% calibration confidence, and the four marginal bounds have at least 95.144% simultaneous calibration confidence. These are per-stack probabilities over repeated calibration samples. A particular fitted threshold can miss its target. The H2 held-out result is evidence to withhold a 95% coverage claim for its 0.073258 K threshold.

| Dwell | H1 bound | H1 exceedances out of 300 | H2 bound | H2 exceedances out of 300 |
|---|---:|---:|---:|---:|
| 5 s | 0.172006 K | 0 | 0.041485 K | 7 |
| 15 s | 0.144427 K | 1 | 0.040478 K | 7 |
| 30 s | 0.127010 K | 1 | 0.036608 K | 4 |
| 60 s | 0.262173 K | 2 | 0.073258 K | 31 |

The 60-second schedule produced the largest error on all 772 sampled missions. Three H1 and 32 H2 held-out missions exceeded at least one dwell-specific bound. A mission can exceed more than one dwell-specific bound. The confidence intervals above condition on each frozen threshold and describe one stack at a time.

## Independent check of the calibration design

GPT-6.2 Astra, run through the OpenAI API Playground, derived the finite-sample ranks and supplied an executable test using synthetic lognormal errors. We ran the returned code unchanged with two prespecified seeds. The test gives all four dwells the same marginal distribution. Each calibration sample contains 100 missions. The dwell-specific bounds use rank 100 and the mission-wide bound uses rank 99. The theoretical probability of obtaining at least 95% mission coverage is 96.292% for the latter construction.

Across 4,096 independently generated calibration samples, the mission-wide bound attained the target in 3,940 samples (96.19%) when the four errors were independent and in 3,928 (95.90%) when their log-scale correlation was 0.6. The Monte Carlo standard errors were 0.30 and 0.31 percentage points. The corresponding 95th percentiles of the mission maximum were 0.305568 K and 0.289677 K under this chosen test family. These thresholds belong to the lognormal example. The panel measurements above use their own error distributions and the 86-mission calibration design. A separate implementation reproduced all twelve success counts on the same draws and evaluated the correlated quantile with Gauss–Hermite quadrature. The [independent program](check_surrogate.py) emits the [comparison table](surrogate-check.csv). Its intervals are individual 95% Wilson intervals for Monte Carlo success rates.

## Reproduction and attribution

From the repository root run the following command in an environment with Python, NumPy and SciPy. Supply a fresh output directory to retain the published files.

```sh
python -B updates/2026-11-20/dwell-calibration/reproduce_dwell_panel.py --output-dir reproduced-dwell
```

The program checks the published parent implementation's SHA-256 before importing it. Its split seeds are 201121 for calibration and 201122 for holdout. Every mission seed, dwell value and gate decision is in the [mission table](dwell-missions.csv). The [summary](dwell-summary.json) gives the unrounded thresholds, interval endpoints and gate counts. A second run under Python 3.12.14 reproduced all 772 mission maxima in the Python 3.13.15 run exactly. At seed 73001 a separate implementation used a singular-value decomposition, scalar recursion and direct sums over all 836 windows. Its eight maxima agreed with the reference within 1.22 × 10⁻¹² K. That check shared the clean calibration readings and exact plant coefficients with the reference.

Richard Pemberton directs The Stage. Coda (Codex Lily) prepared and ran this follow-up using the [published reference](../reproduce_b2_gate.py). Red's earlier synthetic thermal work and the Claude Fable 5.2 diagnostics are credited in the [parent study](../README.md). This study assesses modeled measurement error. Physical temperature control, oxygen carriage and blood compatibility remain open experimental questions.

The [provenance record](provenance.csv) connects the public data to the underlying executions. Both original reference programs are offered under [Apache 2.0](../Apache-2.0.txt). Original prose and table selection are offered under [CC BY 4.0](../../../licenses/CC-BY-4.0.txt) to the extent applicable rights exist.
