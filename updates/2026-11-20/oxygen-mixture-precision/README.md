# How accurately can two blood oxygen carriers be measured separately?

When red cells and free hemoglobin are present in the same fluid, one saturation reading is a weighted average of two contributions. Two different, independently known mixture fractions let us solve for both. The distance between those fractions determines how strongly measurement error is amplified. This gives the Stage’s artificial-blood milestone a testable measurement requirement.

## What the original investigators measured

Rosen, Sehgal, Gould, Sehgal and Moss compared a calculated composite oxygen saturation curve with their measured curve. Under their assumption that the carriers did not interact, the root mean square (RMS) difference was 0.9%. In a separate comparison of 16 direct and indirect oxygen concentration measurements from blood or plasma, the reported regression had slope 0.995, intercept 0.07 and correlation 0.995. The published abstract gives no individual pairs by sample type or pressure-by-mixture rows. The component accuracy and subgroup biases cannot be recovered from these summary numbers alone. [Rosen and colleagues, *Critical Care Medicine* (1986)](https://doi.org/10.1097/00003246-198602000-00016)

## What precision would the assay need?

We tested a synthetic example at four pressures. At each pressure, assume the observed saturation is the fraction-weighted average of the same two underlying component saturations. The fraction denotes the share of total hemoglobin attributable to free hemoglobin. Give **each** mixture a hypothetical RMS error limit of 0.9 saturation percentage points across its four observations. This error budget is an assumption for the example. The historical RMS discrepancy does not establish an instrument tolerance.

For two independently known mixture fractions symmetric around 50%, let *s* be their separation expressed as a fraction. The four-point RMS limit allows an error of 1.8 points at one pressure in each mixture. Inverting the two mixture equations multiplies this bound by at most 1/*s* for either component.

| Known free-hemoglobin fractions | Separation | Maximum single-pressure error in either inferred component |
| --- | --- | --- |
| 32% and 68% | 36 percentage points | 5.0 saturation points |
| 25% and 75% | 50 percentage points | 3.6 saturation points |
| 20% and 80% | 60 percentage points | 3.0 saturation points |
| Pure component references | 100 percentage points | 1.8 saturation points |

**Can the experiment tell which component’s saturation rose more?** In the synthetic 25% and 75% mixtures, the high-fraction sample’s endpoint increase was 6.5 saturation points smaller. That difference combines four readings. If each reading can differ from its recorded value by at most *e* points, the contrast can change by up to 4*e*. Its sign is fixed below **1.625 saturation points per reading**, provided the true fractions remain ordered. At 1.625 points two monotone component curves can tie. At 1.7 points the free component can rise 0.6 points more, reversing the ordering. If each fraction is uncertain by eight percentage points and each reading by 0.5 saturation points, the possible free-minus-cell increase spans **−25.0 to −6.818 points** in this example.

Run `python mixture_precision.py` with Python 3. The [standalone replay](mixture_precision.py) uses exact rational arithmetic to reproduce the separation bounds, the tie and the reversal. It prints feasible component curves for inspection. The example uses synthetic saturation values. Extending it to a real carrier calls for independently measured fractions and error estimates across the same pressures.

## A second check against measured oxygen in tissue

In a retrospective check of Radisic and colleagues’ externally bathed cardiac tissue constructs, **two depth readings ruled out all convex combinations of 13 previously frozen Stage profiles** for the fourth radial position. The chart reports a group mean from three constructs. A weighted comparison of the measured concentrations at 200 and 1300 µm left a **1.245 µmol/L gap** even after allowing ±4.356 µmol/L of chart-reading error at those two points and letting every profile vary its measured endpoints within that allowance. The result rejects that specific set of profiles for the observed group trace. It does not identify tissue uptake or bound concentrations in individual constructs. [Investigators’ Figure 4B](https://skoge.folk.ntnu.no/prost/proceedings/aiche-2005/non-topical/Non%20topical/papers/306e.pdf) · [Stage’s frozen profile forecasts and source replay](../oxygen-content-addendum/flow/)

The original investigators made the blood and tissue measurements. Richard Pemberton directs and funds The Stage. Lilitari contributes to project research design and interpretation. Coda coordinates the computations and verification.
