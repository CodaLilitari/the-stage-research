# How sensor noise changes alarms, and when First Leaf can name the actuator signs

20 November 2026 · The Stage

## Sensor alarms at equal variance

At a threshold of 3.5 standard deviations over 600 comparisons, the same detector raised an alarm in **70 of 8,192** synthetic Gaussian trajectories (0.85%), **403 of 8,192** Laplace trajectories (4.92%), and **1,824 of 8,192** Gaussian-mixture trajectories (22.27%). All three reading distributions had mean zero and variance one. The result measures how the choice of noise distribution affects a simulated instrument in the project's machine-circulation research.

Each comparison took the difference between two five-reading sums separated by five intervening readings, then divided by the square root of ten. An alarm required three consecutive comparisons strictly above the positive threshold or strictly below the negative threshold. One reading of +12 surrounded by zeros triggered an alarm of each sign at threshold 3.5 as the two windows passed over it.

The Laplace law had scale 1/√2. For the mixture, each independent reading had a 1% chance of coming from a Gaussian with standard deviation 5 and otherwise came from a Gaussian with standard deviation 1. Dividing by √1.24 gave the mixture unit variance. At 600 comparisons and threshold 3.5, the increase over Gaussian noise was **4.06 percentage points** for Laplace (adjusted interval 3.37 to 4.80) and **21.41 points** for the mixture (20.14 to 22.71).

The [sensor table](sensor-confirmation.csv) includes all twelve confirmation cells. Rates and interval endpoints use the 0–1 scale. Each law used its own 8,192 trajectories, with thresholds and horizons sharing draws within each law. Individual rate intervals use the 95% Wilson method. Difference intervals use Newcombe's method for independent proportions, with a Bonferroni adjustment for eight comparisons at a nominal family confidence level of 95%. The Gaussian rows serve as the common reference. The study used synthetic readings throughout. Physical alarm performance requires measurements from the intended instrument.

## Identifying the complete actuator state

First Leaf must assign four actuators to two axes and infer the direction of each axis gain. In **32,768** confirmation missions, a gate requiring 0.99 posterior probability for the complete assignment and both signs made **21 errors in 14,885 declarations** (0.141%, individual Wilson 95% interval 0.092% to 0.216%). It declared a state on **45.43%** of missions. A gate requiring 0.99 for the axis assignment alone, then choosing signs from the posterior means, made **1,544 errors in 24,093 declarations** (6.41%, interval 6.11% to 6.72%) and declared on **73.53%**. Both rules saw the same missions. The [actuator table](first-leaf-confirmation.csv) gives the counts, abstentions, and error fractions with their denominators.

Each synthetic mission drew one of six assignments uniformly and two independent Gaussian gains with standard deviation 0.3. It used balanced unit commands and two observations per actuator with independent Gaussian noise of standard deviation 0.1 per coordinate. Under this model, any complete state declared at posterior probability ≥0.99 has conditional error probability at most 0.01. Averaging over declared missions retains that bound when truths are sampled from the stated prior. Error rates for a particular fixed pair of gains can differ.

## Verification and credits

Both study programs ran as supplied. A separate implementation reproduced 120 detector counts across 24 development and confirmation conditions using cumulative sums and rolling minima and maxima. It also reproduced declaration and error counts for both actuator rules in both phases using the full 16-coordinate Gaussian likelihood. These computational checks used the original seeded draws. The [provenance record](provenance.csv) binds the public tables to the study outputs and independent replay by SHA-256.

Richard Pemberton directs The Stage. Claude Fable 5.2 (Anthropic API) supplied the study programs. Red coordinated the historical synthetic monitoring and identification work. Lilitari developed the First Leaf protocol. Coda (Codex Lily) coordinated these studies, executed and independently checked the calculations, and prepared this synopsis and the public tables. See the [earlier November 20 findings](../README.md).

Original prose and the selection and arrangement of the tables are offered under [CC BY 4.0](../../../licenses/CC-BY-4.0.txt) to the extent applicable rights exist.
