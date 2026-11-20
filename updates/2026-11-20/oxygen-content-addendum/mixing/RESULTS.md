# Reading oxygen release in a stirred chamber

Kakiuchi and Borden studied oxygenated buffer and a 50 vol% oxygen-microbubble dispersion in a chamber with an oxygen electrode at its base. The article describes a 50 µL aliquot added to 2.00 mL liquid. This retrospective analysis digitizes published group summaries. The authors report 3–4 runs in Figure 8 and 5 in Figure 9. Individual paired time records, original sample-normalization code and calibration logs were unavailable. [Original paper, Figures 8 and 9](https://pmc.ncbi.nlm.nih.gov/articles/PMC12039959/)

## What the two concentration scales can mean

Figure 8B reports the chamber increment in nmol/mL. Figure 8C labels the 200-second endpoint in mg/L. One nmol of O₂ is 32 ng. Converting a chamber increment to mg/L of the original aliquot gives a factor of 1.280 using the nominal chamber volume or 1.312 using the combined volume. Reading both ordinate labels on the same volume basis gives 0.032. Simply relabeling them gives 1.

| Material and stirring speed | Late chamber mean, nmol/mL | 200-s bar, mg/L | Implied factor | Bar minus prediction at 1.280 / 1.312, mg/L |
|---|---:|---:|---:|---:|
| Oxygenated buffer, 294 rpm | 43.25 | 55.89 | 1.292 | +0.53 / −0.86 |
| Dispersion, 294 rpm | 65.85 | 77.95 | 1.184 | −6.34 / −8.44 |
| Dispersion, 445 rpm | 116.92 | 149.43 | 1.278 | −0.22 / −3.96 |
| Dispersion, 748 rpm | 246.15 | 321.67 | 1.307 | +6.61 / −1.27 |

Late means average graphical readings at 195–198 s to avoid the source line cap. The two other stirred-buffer curves sit behind the red curve in 8A. Their separate means and SD bands cannot be read reliably. A few colored edges survive and are flagged in the extraction; the figure 8C buffer bars are 57.41 and 55.13 mg/L at 445 and 748 rpm. Reading individual dot centers separately recovers the six bar means within 0.77 mg/L. The residual for the slow dispersion is larger than the two volume conventions’ difference. The late 8B bands have approximate half-widths of 20.8, 11.7 and 8.0 nmol/mL. Band width describes the plotted group spread and cannot supply a paired difference between panels.

At 50 vol% nominal gas and the authors’ 4 °C density of 1.41 kg/m³, the model gas inventory is 705 mg per litre of initial dispersion, or 35.25 µg in this aliquot. Allowing 55 mg/L in the remaining half-volume of liquid gives a conditional total of 732.5 mg/L (36.625 µg). Figure 8C’s highest mean corresponds to 16.08 µg on the aliquot basis. The chamber calculation from 8B gives about 16.15 µg with a 2.05 mL volume. This agreement supports a change of volume basis. The measured increment is ~44% of that conditional inventory; temperature, gas-volume definition, true pressure and dissolved-liquid baseline affect that comparison. It does not establish the fraction released by individual bubbles or absolute usable oxygen delivery in blood.

## Same-run normalization is a testable assumption

If each run has endpoint T and fractional-in-time R, the raw mean increment D equals mean(TR). Its deviation from mean(T)mean(R) cannot exceed (n−1)/n × sample-SD(T) × sample-SD(R). We used the published ratio’s percentage as R×100 and T = source bar / scale. The displayed counts compare this necessary condition at 5, 10, 30 and 60 seconds. The second count allows ±1 native unit on each graphical mean and SD as a sensitivity calculation.

| Scale | Pass at central read / pass with ±1 | Testable / total |
|---|---:|---:|
| 0.032 | 0 / 0 | 19 / 24 |
| 1.000 | 1 / 2 | 19 / 24 |
| 1.280 | 4 / 15 | 19 / 24 |
| 1.312 | 4 / 15 | 19 / 24 |

For the 11 testable dispersion-only comparisons, necessary scale intervals overlap at approximately 1.281–1.333 under the ±1 assumption. All 11 admit 1.312, and 10 admit 1.280. Including buffer removes the common interval; four early buffer comparisons fail at 1.312. Marker overlap and unreported processing limit attribution. Exact plotting behavior and matched-run pairing would be needed to reconcile every ratio or establish that two panels use the same n. An algebraic bound passing is necessary for that interpretation and does not establish the underlying replicate values.

## Predicting the intermediate speed

We withheld 445-rpm dispersion ordinates from the prediction calculation and used the 294- and 748-rpm curves. The figures were already public and inspected before registration. Target and forecast files stay separate. Errors below use 39 clocks, 5–195 s, which belong to one published group curve.

| Fixed rule | RMSE (nmol/mL) | Error in time to 50% (s) | Error in time to 90% (s) |
|---|---:|---:|---:|
| Use nearest speed (294 rpm) | 53.43 | +0.49 | +76.68 |
| Linear in rpm, raw readings | 8.27 | −0.83 | +8.51 |
| Linear in rpm, endpoint and fractional curve separately | 4.75 | −0.14 | +54.25 |
| Linear in log-rpm, raw readings | 28.54 | −1.08 | −18.84 |
| Linear in rpm, buffer shape and dispersion endpoint | 24.03 | early, first 5-s interval | −51.80 |

In the target trace, the measured late endpoint is 116.92 nmol/mL. First crossings of 50% and 90% of that late endpoint are estimated at 11.50 s and 65.70 s. The lowest RMSE and best 90%-time prediction belong to different fixed rules. Linear and quadratic-in-scaled-rpm endpoint laws agree at both observed training speeds and disagree by 40.02 nmol/mL at 445 rpm. One held speed limits any claim about transfer to other settings. Across the dispersion panels, B and D readings at 10, 30 and 60 s agree within 1.64 nmol/mL. At 5 s the discrepancy reaches 22.31 nmol/mL for the steepest native trace. Overlapping symbols, their finite width and the clock origin make early slopes and buffer crossing times sensitive to graphical reconstruction.

## A second check using dilution

Figure 9A gives graphical means of ~55.9, 205.6, 338.1 and 426.5 mg/L at 0, 25, 50 and 60 vol%. Regressing those four means gives y = 5.997x + 54.15, close to the authors’ y = 6.0x + 53.6. The largest residual to the authors’ line is 15.46 mg/L. Leaving one concentration out gives errors up to 29.07 mg/L; endpoint discrepancies are largest at 50% and 60%. With five repeats per group, these bars are summaries and supply no new independent between-study test of that source line.

The measured group-mean percentage in 9B first crosses 50% between 5 and 10 s at every level. Linear interpolation gives 6.00, 6.96, 8.10 and 8.49 s. Figure 9C gives mean per-run T50 of 5.33, 6.40, 7.51 and 8.40 s. The difference is only 0.08–0.67 s, but a crossing of the mean need not equal the mean of individual crossings. A synthetic transfer counterexample also reproduces every sampled composite output to 6×10⁻¹⁷ while changing the equipment component’s mean lag from 1.7 to 0.4 samples by moving a shared nonnegative filter into the unknown material and reference processes. The chamber curves measure the composite response; separating intrinsic release, motion of the liquid and electrode delay requires independent information.

## Replay

Read the original figure files from the links in SOURCE.md. Place them as figure8.jpg and figure9.jpg alongside the supplied Python programs. In a Python environment with NumPy, SciPy and Pillow, run `python replay.py`. The replay verifies both original file hashes, extracts native pixels, computes the fixed comparisons and reconstructs the tables. CSV/JSON rows missing a graphical component retain empty or null fields. The shareable archive omits the source images and specimen-level data.
