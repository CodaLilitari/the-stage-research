# Can a measured oxygen profile predict cell viability better than depth?

For three held-out depth intervals in a static engineered cardiac tissue study, depth alone predicted the measured live-cell fraction more closely in every interval. The oxygen-based model had a mean absolute error of **7.65 percentage points**, compared with **5.48** for depth and **12.58** for the calibration mean. Both depth and oxygen carried predictive information within this profile. The study does not resolve their independent contributions.

| Depth interval, µm | Measured live fraction, % | Oxygen forecast, % | Depth forecast, % |
|---|---:|---:|---:|
| 511–766 | 49.03 | 40.46 | 42.88 |
| 766–1021 | 39.35 | 29.41 | 32.59 |
| 1277–1532 | 15.48 | 11.05 | 11.96 |

The authors measured oxygen concentration along the tissue centerline and cell viability over depth intervals. The oxygen profile spanned four constructs. The viability figure reports three constructs, with only one contributing to the deepest calibration bin because the other samples lacked sufficient cells there. Neither the published summary nor its figures identify corresponding specimens across the two assays. We matched the depth intervals geometrically by averaging the oxygen profile over each interval. A directly measured viability bar, a measured total-cell-density bar and the authors’ derived live-cell-density product represent different quantities. Only the first supplied the outcome. [Authors’ conference paper, Figures 4A and 5B–C](https://skoge.folk.ntnu.no/prost/proceedings/aiche-2005/non-topical/Non%20topical/papers/306e.pdf) · [Related journal article](https://doi.org/10.1002/bit.20722)

## What was fixed before the reveal

We used four calibration bins and reserved the other three. The source and its broad qualitative findings were public. A preliminary chart-axis inspection had exposed the edges of the first two bars. Both went into calibration. The numerical reserved bar heights and their caps were kept out of the model inputs and inspected after the forecasts were fixed. This was a retrospective masked reanalysis of a single published profile.

The primary rule fitted an intercept and an oxygen coefficient to the calibration means. The depth comparator used the same number of fitted parameters. Every target lay between measured calibration depths. The registered success rule required oxygen to improve mean absolute error by at least two percentage points over both comparators and improve on depth in at least two of the three intervals. Oxygen improved on the mean by 4.93 percentage points. Depth improved on oxygen by 2.17.

Three independently commissioned programs produced forecasts before the reveal. One reproduced the primary calculation. A regularized oxygen-and-total-cell-density model yielded 5.59 percentage points of error, and a minimum-slope envelope midpoint yielded 6.75. An unconstrained one-predictor total-density fit yielded 14.41. All are comparisons on these same three observations. In a model that allows an arbitrary monotone relationship, the two central target bins can each range from about 14.5% to 60.4% given the calibration means and ±1 percentage point reading allowance. Values at those two depths must also remain jointly ordered.

## Spatial dependence and uncertainty

The seven depth bins come from contiguous tissue regions. The reported errors compare interpolated group means; the bins supply no independent replication for population inference. The oxygen values and the depths had a Pearson correlation of −0.9958. Either coordinate can reproduce an arbitrary monotone curve by an appropriate change of horizontal scale. A causal oxygen threshold cannot be identified from this comparison.

* At fixed oxygen readings, allowing ±1 percentage point in all seven observed viability bars gives an exact **2.08–2.25 percentage-point depth advantage**. The replay enumerates residual sign combinations and optimizes over the same seven unknown true bar heights for both fits.
* Adding the published pointwise standard errors to those reading bands allows a depth advantage of 2.46 or an oxygen advantage of 2.37. The deepest calibration bin has one observed construct and no published SE. That bin received only the chart-reading allowance in this sensitivity calculation. These limits are neither sampling confidence intervals nor simultaneous SE bands. Oxygen graph reading has its own allowance of approximately ±2.94 µmol/L.
* As a separate post-reveal check, we withheld each possible contiguous block of three interior bins. Depth led by 2.56 and 1.21 percentage points in the first two blocks. Oxygen led by 0.02 in the third. The three blocks overlap. Omitting the single-construct deepest calibration bin leaves the last target outside the calibration range. Depth remained closer in both targets still inside that range.

This comparison gives The Stage a concrete test for a proposed oxygen-to-viability model. On these measurements a depth-only rule is a stronger reference than a constant fraction. Distinguishing the biological effects would require observations that vary oxygen at comparable depth, and traceable links between the two measurements would support specimen-level comparisons.

## Reproduction

Download the conference PDF and run `python replay.py 306e.pdf`. The program checks the source SHA-256, uses Poppler to recover the original Figure 4 and 5 images in a temporary directory, and reads the Figure 5B bar heights separately from the upper error bars. It requires Python, NumPy 2 or later, SciPy, Pillow, and Poppler. On Windows the program also supports Poppler installed in the default WSL distribution.

The replay uses the original recorded Figure 4A cap positions, the training-only linear models, and the three frozen external forecast vectors. It reproduces both the main outcomes and spatial sensitivity calculations. Re-running it after the reveal reproduces the scores. The recorded pre-reveal forecast and disposition file has SHA-256 `665f0b0187abf1b9b1d19039ad7b80f532f99bcf4f90ec6171c0fed7a3baaac4`. Source figures remain with their authors.
