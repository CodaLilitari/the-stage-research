# Reproducing the empirical benchmarks

The reference programs take one original source file as their only argument. They run offline, verify the source bytes, print aggregate JSON and leave their inputs untouched. The original investigators host the source data. The verification environment used Python with NumPy, SciPy, openpyxl and PyMuPDF. Run each command in this directory.

## Human-blood equilibrium

Download **Data Sheet 1** from Valsecchi and colleagues. The same 346 measured records appear twice, with and without separation by donor. The file SHA-256 is `89a1d84facbb7423baf49bbd4ef125a50eea3b7303e1acb72f155cfadd72d8c9`. [Original supplementary document](https://pmc-oa-opendata.s3.amazonaws.com/PMC12833093.1/Data_Sheet_1.docx) · [Article](https://doi.org/10.3389/fmed.2025.1708274)

```sh
python replay_equilibrium.py Data_Sheet_1.docx
```

The program reads the measured dark-green symbols in the five subfigures of S6, calibrates each axis against its tick marks, excludes the separate legend symbol and checks the coordinate pairing against the second rendering in S7. It rounds the recovered oxygen pressure and saturation to one decimal. Fitted curves in the paper are excluded.

For each nominal CO₂ setting, fit across all the other settings. The unseen-donor comparison also removes every observation of the target donor from training. Each model has four parameters. Its ceiling is in [1, 100] saturation percentage points and its Hill exponent in [0.05, 20]. The logarithm of P50 is affine in either `(CO₂ − 50) / 40` or `log(CO₂ / 50)`. Fit by ordinary least squares in saturation points. At scoring, calculate the mean squared error within each donor-by-condition cell, average those 30 means and take the square root. The program prints both primary models and their per-condition scores. This compact replay covers the ordinary pooled comparison. The earlier nested donor-shrinkage and missing-pairing analyses are described in the [report](README.md).

| RMSE, saturation percentage points | Linear | Log |
|---|---:|---:|
| Omit condition | 3.747070 | 2.144570 |
| Omit condition and donor | 3.805616 | 2.223677 |

The full study froze 11,072 forecast records from 16 model variants and two donor settings before scoring them. That forecast CSV had SHA-256 `bf5a2a6a47628beedee2c515a08fa1146e913537a213ae62272c2bfa122cd20d`. The compact replay reads the source directly and implements the two pooled models independently of that file.

## Cell-free and cell-loaded chamber recordings

Download **Compiled_Data_PAPER_unformatted.xlsx** from Qayyum, Cole, Oomen, Khayat and Grosberg’s Dryad record. The workbook SHA-256 is `f301464111d1feb33c1b28a192b8b9d868a352a6041d8f4b0da03eeccc152383`. [Dataset and measurement definitions](https://doi.org/10.5061/dryad.t1g1jwtg9) · [Original article](https://pmc.ncbi.nlm.nih.gov/articles/PMC13485341/)

```sh
python replay_chamber.py Compiled_Data_PAPER_unformatted.xlsx
```

Use the two liquid-phase intermittent-oxygen worksheets. Each held prediction starts with that run’s initial measurement. Then at each later time add the mean or median of the changes observed since time zero in the specified training runs. Compare the next 184 predictions with the recorded dissolved oxygen concentration from 5 to 920 seconds, inclusive. Calculate a separate RMSE in µM for each run. The loaded-run aggregate is the arithmetic mean of its two RMSE values.

| Held target | Training and prediction | Mean run RMSE, µM |
|---|---|---:|
| Empty run 3 | Initial value | 71.495093 |
| Empty run 3 | Mean change of empty runs 1–2 | 3.880692 |
| Loaded runs 5–6 | Mean change of empty runs 1–3 | 23.741913 |
| Loaded runs 5–6 | Mean change of loaded runs 1–4 | 10.744041 |
| Loaded runs 5–6 | Median change of loaded runs 1–4 | 10.842123 |

Full forecast locks, including the other fitted models, had SHA-256 `beebdd0aa2719b9c69340edb9436ceb6fc6dc478fa133a93dc29ab4729b9fe96` (empty) and `20012e99965bcb00917d734870d5e0c4eea0a1f33c264c60e63b2cced1c11904` (loaded). The pointwise median above also matches every primary-window value of the original forecasting program’s secondary median output. Its primary output used a residual-corrected command model.

## Earlier storage days and membrane transfer

For the storage-day comparison, use Chng and colleagues’ supplementary source data workbook. The program reads the six day columns in the `Fig. 4` worksheet, computes the two empirical distributions, and independently scores them against the 65 day-42 wells. It reproduces both mean CRPS and Wasserstein distance for equal-day weighting and the last-day baseline. [Original study and source data](https://doi.org/10.1038/s42003-021-01793-z)

```sh
python replay_storage.py 42003_2021_1793_MOESM3_ESM.xlsx
```

For the membrane comparison, use Menzel and colleagues’ supplementary Tables S1 and S2. For each S1 row, convert the outlet–inlet pressure rise to transfer rate using the authors’ dissolved oxygen solubility of 0.028 mL gas per mL medium per atmosphere. Average the three numbered membranes within each flow and surface. The program also extracts the corresponding reported S2 row for comparison. [Original supplementary PDF](https://pmc-oa-opendata.s3.amazonaws.com/PMC5587952.1/5258196.f1.pdf)

```sh
python replay_membrane.py 5258196.f1.pdf
```

## Direct carrier measurements, stored-blood P50 and instrument ambiguity

The [two-pressure replay](two-pressure/) calculates the registered native-unit forecasts for the three held Sharts emulsions and reports all decision criteria. The [carrier source-table replay](carrier-source-tables/) reads the cited Laing, Matton, Freire and Dias sources and reports the aggregate results and comparison limits. Each subdirectory includes its source citations and run command.

For the external P50 forecast, download the [Chen article PDF](https://pmc-oa-opendata.s3.amazonaws.com/PMC12488716.1/PMC12488716.1.pdf) and the [Kassa article XML](https://pmc-oa-opendata.s3.amazonaws.com/PMC11366621.1/PMC11366621.1.xml). The reference script reads the original embedded Figure 2 from the PDF with PyMuPDF and Pillow. It locates the conventional-storage control markers at days 3 and 42, calibrates their heights against the plotted ticks, and then reads the P50 row in Table 1 of the external article. The expected mean forecast is 22.604386 mmHg, and the external target mean is 22.1 mmHg.

```sh
python replay_stored_affinity.py PMC12488716.1.pdf PMC11366621.1.xml
python replay_two_reads.py
```

The second script takes no inputs. It bounds the contrast for two rectangular exposures ending at 0.08 and 0.28 s, each 0.020 s wide. Both measure the same synthetic intermediate signal with one shared trace gain in [0.98, 1.02], offset in [−0.01, 0.01] and clock shift of up to ±0.010 s. The fast time constant ranges from 0.128 to 0.192 s and the slow one from 0.2304 to 0.3456 s. Each reading may also have a separate bounded additive error of ±0.008. The noiseless intermediate state decays exponentially from one following a step to zero. Use a 55-significant-digit Decimal calculation and subdivide each continuous family into 4,096 intervals. An enclosed strictly positive gap certifies that all admissible fast and slow readings fall on the appropriate sides of the decision threshold.

## Credit and reuse

Coda (Codex Lily) prepared the replay code for The Stage under [Apache License 2.0](../Apache-2.0.txt). This report, guide and original arrangement of aggregate results are offered under [CC BY 4.0](../../../licenses/CC-BY-4.0.txt) to the extent the project can grant those rights. Reuse of the authors’ original measurement files follows the terms at each source. The named primary investigators performed the original experiments.
