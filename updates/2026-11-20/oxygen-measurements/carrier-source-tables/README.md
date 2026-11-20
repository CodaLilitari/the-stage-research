# Existing oxygen carriers | reproducible source-table check

These calculations measure what can be learned about two existing kinds of noncellular oxygen carrier. The equipment, media, fluid composition and observation units differ between studies.

| Evidence | Observed or reconstructed result | Limits |
|---|---|---|
| Hemopure versus packed red cells in separate discarded human livers | Mean saturation extraction was 28.22% vs 19.56%, an 8.66-percentage-point difference across five organs per group. An organ-level two-sided label test counted 46/252, or 30/140 under donation-type strata. | Nonrandomized ex vivo series. Recovering mL O₂/min requires paired content and flow in all inlets and the outlet. |
| Measured dissolved oxygen in completed PFC emulsions | At 310.2 K in room air, values across six conditions were 0.93–1.00 µmol/mL. Whole-interface holdout RMSE was 0.0100 µmol/mL for the mean of other interfaces with the same PFC, 0.0296 for the pooled mean and 0.0647 for the published component expectation. | Fixed composition per material and one gas condition. The actual oxygen partial pressure and humidity are unknown. |
| Neat perfluorohexane across two Dias publications | A prespecified temperature secant reproduced none of nine external native volume coefficients within 2%; mean absolute relative error 7.62%. A subsequent check of standardized solute mole fraction reproduced six of nine within 2%; mean absolute relative error 1.28%. | Retrospective publications share authors. Six temperature blocks underlie nine rows. The newest series ends at 306.65 K so a 310.2 K estimate requires extrapolation. |

For a separate one-temperature anchor, the original Wesseler study as compiled by Young reports 8.6 mL oxygen/100 mL neat perfluorodecalin in air at 298.15 K. The Dias interpolation predicts 8.5445 under dry 1-atm air and 8.2775 under fully water-saturated air. The compiler assumed barometric pressure of 1 atm; no measured humidity is reported. [Air measurements, printed p. 527](https://srdata.nist.gov/solubility/IUPAC/SDS-10/SDS-10.pdf#page=572) · [Pure oxygen measurements, printed p. 336](https://srdata.nist.gov/solubility/IUPAC/SDS-7/SDS-7.pdf#page=353) · [Original Wesseler et al. article](https://doi.org/10.1016/S0022-1139(00)82152-1)

## Reproduce the three main rows

Install Python 3.9+ and Poppler's `pdftotext`. Windows can use Poppler in WSL Ubuntu. From this directory, choose cache and output paths outside your repository. The example uses a Unix temporary directory; Windows users can substitute a path under their local temporary directory.

```sh
python replay.py --fetch --source-dir /tmp/stage-paper-cache --output /tmp/stage-oxygen-results.json
```

The command downloads verified editions of the five primary source files, extracts the relevant original tables, and writes aggregate results. To run offline, place the same editions in the cache with the filenames in `sources.json`, then omit `--fetch`. `expected-aggregates.json` records results checked against the separate research implementation. The public package contains original analysis code, source metadata and derived aggregate results. The published articles, tables, pictures and publisher text can be accessed through their sources.

The content accounting calculation adopts Matton's explicitly carrier-specific constants, 1.39 versus 1.26 mL oxygen/g hemoglobin, and 0.0225 mL/dL/kPa for dissolved oxygen. The source ranges for fractional oxyhemoglobin yield conditional baseline-content envelopes of 6.59–7.55 mL/dL for Hemopure and 10.50–14.33 mL/dL for packed cells. These combine marginal extrema; the median plug-ins do not recover observed joint medians. The pure-PFC illustrative pressure conversion uses L·pO₂/(R·T) in mol/m³, numerically equal to µmol/mL. It assumes ideal gas behavior, proportionality to oxygen partial pressure and a specified dry or humid headspace.

The original capacity measurements and group comparisons are attributable to their experimental authors. The Stage contribution is the unit-preserving reconstruction and numerical cross-check. [Laing et al.](https://doi.org/10.1097/TP.0000000000001821) · [Matton et al.](https://doi.org/10.1002/lt.25005) · [Freire et al.](https://doi.org/10.1016/j.fluid.2005.01.008) · [Dias et al. 2004](https://doi.org/10.1016/j.fluid.2004.06.037) · [Dias, Bonifácio et al. 2003](https://doi.org/10.1039/B207512C)
