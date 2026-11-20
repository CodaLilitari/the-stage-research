# Predicting the oxygen content of a finished carrier liquid

The Stage tested whether one low-pressure oxygen-content measurement and a degassed background could predict the same fluid's measured content at a much higher oxygen partial pressure. The three held archival emulsions contained 1-bromoperfluorohexane, 1-bromoperfluoroheptane and 1-bromoperfluorododecane, respectively. Eight other fluids at the same nominal loading provided an unconditional high-pressure comparison. Sharts and colleagues measured oxygen content directly with a Lex oxygen-content analyzer. The source reports means and standard deviations for triplicates. [Original study](https://doi.org/10.1016/S0022-1139(00)81622-X) · [IUPAC–NIST compilation, printed pp. 90–92](https://doi.org/10.1063/1.4883876)

At **310.2 K**, the compiler assigns nominal oxygen partial pressures of **21.3 and 98.3 kPa** to the air and oxygen-rich equilibration gases. These values come from the gas conditions. The paper did not provide independently measured liquid-phase tensions for these rows. The original units are mL oxygen per 100 mL finished dispersion. The compiler interpreted the reported units as consistent with an Ostwald-type convention; the gas-volume reference temperature and pressure are insufficiently documented for an absolute molar conversion.

| Held material | Observed at 21.3 kPa | Forecast at 98.3 kPa | Observed at 98.3 kPa |
|---|---:|---:|---:|
| S1 | 1.3 ± 0.2 | 5.64 | 5.0 ± 0.3 |
| S2 | 1.2 ± 0.2 | 5.54 | 4.4 ± 0.2 |
| S3 | 1.8 ± 0.2 | 5.42 | 4.3 ± 0.1 |

The offset-aware linear extrapolation used each fluid's background reading, then multiplied its excess oxygen at the lower pressure by 98.3/21.3. Its mean absolute error was **0.964 mL/dL**, compared with **0.333** for predicting 4.7 mL/dL for all three fluids. Its largest miss was **1.138**. It failed the three prespecified conditions: an average error at most 0.50, maximum error at most 1.00 and an improvement of at least 0.20 over the training median. Four independent, source-masked computational forecasts also returned; their errors ranged from 0.350 to 0.483 mL/dL. None improved upon the median on these three outcomes.

Allowing each mean to vary by half a printed decimal yields non-overlapping MAE ranges for the pressure forecast (0.502–1.425) and median (0.233–0.433). Allowing inputs and outcomes to move by one full reported standard deviation instead gives a much broader pressure-model sensitivity range of 0.005–2.328. These are deterministic sensitivity bounds. Three technical readings per endpoint and three held materials do not establish a population-level effect. The result rejects this forecast at the specified accuracy, while the physical mechanism behind the discrepancies remains unresolved.

The analyst saw the development rows and both vehicle values while locating the study. The three held outcomes were saved without display. Locally locked baselines and the isolated reviewers' numerical outputs existed before the held high-pressure column was opened. The exercise tested retrospective predictions against the original laboratory's measurements.

Run `python pressure_replay.py` from this directory. The replay uses only Python's standard library, includes the limited factual inputs needed for this calculation and reproduces the registered criteria, exploratory forecast scores, and uncertainty calculation.
