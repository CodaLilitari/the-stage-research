# Monitoring and identification in simulated bodies

The Stage's first milestone is artificial blood. The calculations in this update address a supporting engineering question for the machine-circulation branch. If a simulator supplies a known signal and known model parameters, how well do the proposed alarms and estimators recover them? All results here concern mathematical models.

## How often does noisy monitoring raise an alarm?

The baseline monitor compares two five-reading averages whose starting points are ten readings apart. Its input is a sequence of independent standard Gaussian readings. Adjacent comparisons reuse readings, so large values can arrive in groups. The analysis counts a *clump* once when at least three consecutive standardized comparisons cross the same positive or negative threshold.

For a horizon of `H` comparisons, let `p3` and `p4` denote the probabilities of three or four consecutive positive threshold crossings. For `H >= 3`, the expected clump count is `2 * (p3 + (H - 3) * (p3 - p4))`. The first group can begin at the first reading. Later groups must start after a comparison below or equal to the threshold on that side. Symmetry supplies the factor of two.

Numerical integration and a separately implemented simulation agreed on mean counts within 1.43 simulation standard errors for all eight combinations of horizon and threshold. Converting each mean to a probability using a Poisson approximation produced appreciable errors. For 120 comparisons at a threshold of two standard deviations, the approximation gave 45.398%, while 3,367 of 8,000 confirmation runs raised an alarm (42.0875%). Five of eight approximations fell outside their individual 95% Wilson intervals. The conditions share simulated readings. These intervals describe each condition separately.

The next study trained two count models on 4,000 fresh simulated missions and froze their parameters before running 16,000 confirmation missions. At 120 comparisons and a threshold of two standard deviations, 6,760 missions raised an alarm (42.25%). Ordinary Poisson counts predicted 45.42%. A model allowing clumps to arrive singly or in pairs predicted 42.89%. That model had admissible fitted parameters for six of eight conditions. Individual 95% intervals for the paired difference in Brier score favored the pair model in three conditions and the ordinary Poisson model in one. Two intervals included zero. At both horizons and threshold 3.5, the fitted pair model would have required a negative event rate. [Baseline alarm counts](baseline-alarms.csv) and [held-out paired comparisons](paired-clump-predictions.csv).

At 600 comparisons and a threshold of 4.5 standard deviations, ordinary sampling produced zero alarms in 32,768 missions. Importance sampling, which draws extreme signals more often and weights each one by its likelihood ratio, estimated an alarm probability of **0.0000506162**. The approximate individual 95% interval from 32 independent batch means was 0.0000483478 to 0.0000528846. A separately written filter and counter reproduced 16 count histograms and 288 local counts on the same inputs. A second implementation of the likelihood ratio reproduced the hit counts and estimated probabilities for 384 batches across validation and study conditions. [Rare-event estimates and intervals](rare-alarms.csv).

## Can the thermal model distinguish its parameters?

Three simulated thermal systems, H1 through H3, were fitted to 450 seconds of readings with nine fixed measurement-noise levels. The study used 16 development seeds and a separate set of 16 confirmation seeds, for 864 fits in total. A given seed supplied the same 451 Gaussian noise draws across systems and noise levels. The estimator returned finite results for all 864 fits.

All 16 confirmation fits for H1 passed its existing acceptance rule at a measurement-noise standard deviation of 0.01 K. H2 passed all 16 through 0.001 K on the tested grid. H3 passed all 16 only at zero noise. The development seeds showed the same pattern. Each 16-of-16 observation has an individual 95% Wilson lower limit of about 0.806. The grid and sample size limit how precisely these observations locate a transition. Prediction on new command sequences tests a different property from passing the original acceptance rule.

A fresh test asked whether the gate's predicted error envelope describes what happens after acceptance. Each fitted model and the exact model started from the same fitted steady-state output. On a fixed 900-step input, **all 32 H1 confirmation fits at 0.01 K passed the gate, and all 32 exceeded the predicted envelope and the 0.2 K probe-window error threshold.** The probe-window error ranged from 0.203637 to 0.233855 K, compared with predicted envelopes of 0.149531 to 0.179940 K. H2 behaved differently. At 0.001 K, all 32 confirmation fits passed and none exceeded the envelope or a study threshold.

The input sequence also mattered. In a separate group of 16 previously fitted H1 models, 14 exceeded 0.2 K peak error when each power level lasted 60 seconds. None exceeded that threshold when each level lasted five seconds. Power alternated between 2 W and 5 W. Both simulations used one-second steps. The original prediction program failed when formatting a label after its calculation. Escaping the percent sign allowed it to report the results. A separate matrix implementation checked 175 predictions, 12 information-matrix spectra, 16 coefficient-error projections, 582 gate evaluations and 576 positive-definiteness results for noise-corrected coefficient estimation.

## What can First Leaf learn from one probe?

The simulated agent has four actuators. Two act along the horizontal axis and two along the vertical axis. Each opposing pair shares a signed gain. There are six ways to choose the horizontal pair. A single probe with no prior readings splits these six possibilities into two equally likely groups according to the chosen actuator's axis. Its information about the partition therefore has a ceiling of `ln(2)` nats, even though the count of unseen actuators gives the larger heuristic `ln(4)`.

With a gain standard deviation of 0.3 and a measurement standard deviation of 0.1, numerical integration gave **0.3304001611 nats** of information for each actuator. The 192- and 384-node Gauss–Hermite evaluations gave 0.33040016490 and 0.33040016106. A separate confirmation simulation estimated 0.33338 with Monte Carlo standard error 0.00152. Under independent Gaussian errors, a full Gaussian likelihood calculation agreed with the existing sufficient-statistic posterior to within 8.89 × 10⁻¹⁶ across 840 confirmation cases.

Knowing the axis pairing can still leave uncertainty about the direction of motion. Among 12,058 confirmation trials drawn from the model prior in which the agent flagged identification **and** chose the correct partition, it got the horizontal gain sign wrong in 395 trials (3.28%) and the vertical gain sign wrong in 377 (3.13%). Each percentage uses the trials that satisfied both conditions. All four returned First Leaf programs ran unchanged.

The [sensor and actuator follow-up](sensor-and-signs/README.md) measures alarm rates under heavier-tailed noise and the accuracy cost of declaring actuator signs from the axis partition alone.

The [four-dwell calibration follow-up](dwell-calibration/README.md) tests the thermal gate on 300 fresh missions per stack and reports where a fitted coverage bound failed on holdout.

## Reproducing the calculations

From this directory run `python probe_reference.py` in a Python environment with NumPy and SciPy. The [reference program](probe_reference.py) prints the estimated information for 48, 96, 192 and 384 quadrature nodes and checks convergence and the zero-gain case. The alarm CSVs report probabilities on the 0–1 scale. Empty paired-model cells indicate an inadmissible fit. The two confirmation studies use different seeds and mission counts.

In the same environment run `python reproduce_b2_gate.py` to reproduce the two thermal gate comparisons independently. The [B2 reference program](reproduce_b2_gate.py) prints a JSON record of each trial and the accepted fits that exceed an envelope or study threshold. The release checks used Python 3.13.15, NumPy 2.5.4, and SciPy 1.18.1.

Richard Pemberton directs the project. Coda (Codex Lily) coordinated study design, local execution, independent numerical checks and this synopsis. Claude Fable 5.2 (Anthropic API) supplied the numerical integration and follow-up study programs. Red coordinated the historical synthetic monitoring and identification work that these studies examine. Lilitari developed the First Leaf protocol. Project roles and earlier contributions are documented in the [2 November attribution record](../2026-11-02/ATTRIBUTION.md).

File hashes connect the exported tables to their source outputs in the [provenance record](provenance.csv). Original prose and the selection and arrangement of the data tables are offered under [CC BY 4.0](../../licenses/CC-BY-4.0.txt) to the extent applicable rights exist. The two independent reference programs by Coda (Codex Lily), prepared for Richard Pemberton, are offered under [Apache License 2.0](Apache-2.0.txt).
