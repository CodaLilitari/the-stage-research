# Calculation provenance (calc/o2_perfusion.py)

Chosen test: a fully specified published Fick/Krogh oxygen-diffusion calculation (Place, Domann, Case 2017, Free Radic Biol Med, doi:10.1016/j.freeradbiomed.2017.10.003, open text at PMC5699948, Fig. 5 legend and the "Dissolved oxygen" section). I extend it from a monolayer under medium to a slab or cylinder of tissue, then size convective perfusion and Hagen-Poiseuille channels for a finger module.

The Ren 2025 Dryad data (10.5061/dryad.xd2547drh, CC0) was my first choice. Its file downloads returned HTTP 401 through the API and 403 through the web stream, so it was not used. A copy of the Place 2017 text that I extracted is in ../src/place2017.txt.

| Input | Value | Label | Locator |
|---|---|---|---|
| Medium O2 at 37 C, PO2 141.4 mmHg | 0.181 mM | reported | Place 2017, text and Fig. 5 legend |
| O2 diffusivity, medium + 10 % FBS | 2.69e-5 cm2/s | reported | Place 2017, Fig. 5 legend |
| Physiologic pericellular target | 0.052 mM (~40 mmHg) | reported | Place 2017, Fig. 5B text |
| Cell OCR | 10 to 120 amol/cell/s | reported | Place 2017 (citing Wagner et al.) |
| Medium viscosity, supplemented DMEM, 37 C | 0.78 mPa s | reported | Bacabac et al. 2005, J Biomech, doi:10.1016/j.jbiomech.2004.03.020 (seen via the author's thesis ch. 2 and an index summary, not the journal PDF) |
| Blood O2 content | 201 mL/L = 8.97 mM | derived | Textbook Hufner 1.34 mL/g x 150 g/L, not checked against a specific page |
| Clone pump | 40 L/min, 100 psi, 500 W | company claim | press reports of company statements |
| Cell density | 1e7 to 1e8 cells/mL | ASSUMED | no MuMuTA measurement was accessible |
| Module tissue volume | 0.1 to 1 mL | ASSUMED | |
| Channel diameter | 100 to 500 um | ASSUMED | |
| Tissue-loop pressure budget | 2 to 10 kPa | ASSUMED | |
| O2 extraction per pass | 0.3 to 0.7 | ASSUMED | |

Model limits: zero-order O2 uptake (no Michaelis-Menten), no myoglobin, steady state, straight rigid circular channels, Newtonian fluid (blood is not Newtonian), ideal van 't Hoff osmolality. Rerun with `python3 o2_perfusion.py > output.txt`. The script needs only the Python 3 standard library.
