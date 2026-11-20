# Reproducing the assay comparison

The investigators published Figure 1 and Table 2 in the primary article. Download the institutional version of record into a new scratch directory as `paper.pdf`. It includes a repository cover sheet. The expected SHA-256 is `0b373848cfe9ffef84bce62cdc89f828cc85a65d13faa1733501c89744b4cf9f`. [Source PDF](https://pure.eur.nl/ws/files/98553324/Int_J_Lab_Hematology_-_2023_-_Bronkhorst_van_der_Helm.pdf) · [Article and license details](https://doi.org/10.1111/ijlh.14146)

Put the five Python files in that directory. Use Poppler and Python with NumPy, SciPy and Pillow. Run these commands from the scratch directory.

```sh
pdftocairo -svg -f 5 -l 5 paper.pdf plot.svg
pdftoppm -png -f 5 -l 5 -singlefile -scale-to 960 paper.pdf preview
python extract.py
python crosscheck.py
python score.py
python cross_validate.py
python quantization.py
```

`extract.py` writes the calibrated marker positions and axis diagnostics. `crosscheck.py` verifies all 124 markers against independently rasterized Figure 1 and all 14 means against the visually verified Table 2. `score.py` calculates error ranges by enumerating admissible assignments within each series and calculates the cross-assay signal contrasts by bipartite matching. `cross_validate.py` holds out one analyzer at a time and fits a two-parameter linear program to the others. Its secondary minimizations choose the smallest scale compatible with the optimum and then the midpoint of the optimal intercept interval.

`quantization.py` checks how closely the two sets of assay readings follow a regular grid and calculates the departures from proportionality that exceed a declared rounding model.

The public packet contains newly written code and a report. The researcher obtains the publication and produces derivatives locally under its license. The calculated numerical contrasts summarize this publication. No laboratory sample, independently collected donor, or newly tested instrument is represented by a code replay.
