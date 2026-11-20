# Does an oxygen-depth profile transfer when the external medium flows?

Radisic and colleagues measured oxygen through engineered cardiac tissue. We used their stagnant profile to forecast their externally flowed condition, allowing each flow position its two measured surface concentrations. **The transferred shape improved on a straight line between the surfaces. It still systematically overestimated oxygen at the clearest identifiable radial position.** These are forecasts against measured group means under a second condition. The authors used four stagnant constructs and three externally flowed constructs, with four radial positions in each of the latter. [Authors’ Figure 4](https://skoge.folk.ntnu.no/prost/proceedings/aiche-2005/non-topical/Non%20topical/papers/306e.pdf) · [Related journal article](https://doi.org/10.1002/bit.20722)

## A trace that can be identified directly

Figure 4B contains four flow-marker shapes and a fifth stagnant comparison. Several flow markers and their error bars overlap. The cross for radial position 4 could be tracked at both surfaces and 13 of the 17 interior depths. We omitted the cross at 700, 800, 900 and 1000 µm from this position-specific score because its identity was ambiguous. The two anchors read **208.8 and 177.7 µmol/L** over 1800 µm.

| Forecast, evaluated between the two measured anchors | RMSE, µmol/L |
|---|---:|
| Unchanged stagnant profile | 85.52 |
| Straight line between flow anchors | 34.54 |
| Registered transfer of the stagnant profile’s deviation from its straight line | 22.50 |
| First-order uptake model fitted to the stagnant profile | 13.38 |
| Separately fitted first-order model from the external numerical program | 13.25 |
| Locally frozen smooth two-surface depletion profile | 9.04 |

The primary transfer overestimated these 13 oxygen values by a mean of **20.94 µmol/L**. The shape correction captured part of the interior oxygen deficit. The lower errors of the other models are comparisons on the same published profile. They do not establish a unique uptake law.

## All four radial positions

At each depth we recorded the four flow-marker centers ordered from highest to lowest concentration. Some nearly coincident marks occupy a common concentration band. We allowed alternative assignments of ranks to positions across depths and both surfaces. This avoids tracing a line across an overlap by eye.

The registered error was the **average of the four position-specific RMSEs**, with a five-µmol/L improvement required over both the boundary line and the unchanged stagnant curve. At the central readings, the transfer gains **at least 5.029 µmol/L over the straight line and 47.38 over the unchanged profile** for every assignment in this calculation. The first bound clears the five-unit threshold by only 0.029. Each individual curve was allowed to take any value between the lowest and highest flow rank at every interior depth; the per-position limits were then combined over all ways to pair the two sets of surface anchors.

**The five-unit gain over the straight line depends on chart resolution.** Our sensitivity calculation allowed ±4 native pixels at each flow rank (±4.98 µmol/L), and ±1.5 pixels (±2.94 µmol/L) at each stagnant reading. In the relaxed set of rank assignments and readings, a constructed case with a gain of **3.38 µmol/L** respects all the explicitly recognized crosses. It is an alternative allowed by that calculation, not a reconstruction of the actual tissue. The mean-over-positions error gain against unchanged stagnant oxygen remains at least **26.18 µmol/L** under these allowances. Pointwise sampling errors and covariance across positions would require additional information. The reading allowances concern the graphic alone.

Pooling squared errors yields a separate result that survives these allowances. The straight line’s pooled MSE exceeds the transfer MSE by **724.65 (µmol/L)²** at the central readings, independent of how the interior ranks are assigned. With the chart-reading bands, the excess remains at least **315.94 (µmol/L)²**, equivalent to a conservative lower bound of **3.19 µmol/L on the pooled RMSE gain**. Pooling squared errors gives more influence to positions with larger errors than the registered average of four RMSEs.

## Why the pooled result survives an overlap

At each depth, every position receives the same model correction d, the stagnant concentration minus its boundary line. If r is the measured flow concentration minus its boundary line, the pointwise squared-error improvement is 2rd−d². Averaging across positions therefore requires only the **mean** of their concentrations and surface values. Any reassignment of interior ranks leaves that quantity unchanged. The exact reading-box minimum follows by checking the four shared endpoints and the allowed extremes at each interior depth. The separate equal-position proof uses the reverse triangle inequality, vertex checks and supporting hyperplanes for Euclidean norms.

## Reproduction

The broad study findings, stagnant profile and bottom-panel horizontal-axis labels were already known. The interior pixels and surface values of Figure 4B were first examined after all local, external and explicitly labeled compatibility forecasts were frozen. Four original external programs passed their self-tests and observed-input runs. A fifth passed its self-test, then encountered a removed NumPy function name when analyzing the stagnant profile. Replacing `np.trapz` with `np.trapezoid` yielded a working, separately labeled numerical forecast before the reveal. The digest of the complete original pre-reveal record is `a2ea7208ce8ac5723d151922fae90d1242eb73f8fdd7ff1242d6647306d72e5c`.

This public snapshot contains the numerical conditional forecasts and their design rows copied from that locked record. Internal execution logs are omitted. The public coefficients file has SHA-256 0423744ec22898c5e8ef0c16c2718202a624bd61a70770042971c72cec970949.

Download the cited original PDF. In a private working copy of this supplement, run `python replay.py 306e.pdf`. Python, NumPy 2, SciPy, Pillow and Poppler are required. On Windows, Poppler can also be installed in the default WSL distribution. The replay verifies the PDF and forecast digests, checks the stagnant error-cap readings, and uses the recorded native flow-marker positions for scoring. The source authors’ figure remains the reference for inspecting our rank assignments and the four omitted crosses. The script saves result JSONs in the working copy. No original figure is included.
