# An external oxygen-content test and a corrected interpolation

Navari, Rosenblum, Kontos and Patterson measured oxygen in perfluorotributylamine (FC-47) emulsions at 310.15 K using gas chromatography. The archived emulsion table reports oxygen volume per volume of dispersion at each gas equilibration pressure. At 22 g FC-47 per 100 mL fluid, the reported means were 0.0040, 0.0090, 0.0143 and 0.0797 cm³ O₂/cm³ at 50, 100, 150 and 760 mmHg. The four reported standard deviations were 0.0010, 0.0010, 0.0011 and 0.0011. Each mean summarizes five determinations. These pressures describe the oxygen equilibration conditions. The source describes chromatographic analysis of saturated liquid and calibration with dry oxygen. It does not establish the gas-volume reference temperature and pressure for the emulsion observations. [Primary study](https://doi.org/10.1007/BF01851388) · [IUPAC data sheet, printed p. 386, PDF p. 403](https://iupac.github.io/SolubilityDataSeries/volumes/SDS-7.pdf#page=403)

**The blind test failed at the definition of its outcome.** The registration interpreted the emulsion numbers as a pressure-normalized coefficient. Visual inspection of the complete source after the predictions had been frozen showed that the compiler's possible Bunsen-coefficient interpretation referred specifically to graph-derived *neat-liquid* entries marked with footnote 4. The emulsion entries bear footnote 1 and are reported at each pressure as cm³ O₂/cm³. The predictions answered a question about a different quantity. The investigators' underlying physical law cannot be tested by scoring those predictions as if both quantities agreed.

The frozen calculation used the low/high observations of the same nominal dispersed compound in a different study, at a different loading and in a different vehicle. Three local high-pressure measurements provided anchors for three loadings. The mean absolute error at 150 mmHg, divided by each fluid's high anchor, was 0.950 for the pressure-dependence transferred from Sharts, 0.819 for a flat coefficient, 0.855 for the reviewer given the numerical source data and 0.771 for the reviewer also told the qualitative direction of pressure dependence. The last result used information unavailable to the first reviewer. Both reviewers supplied their complete arrays before the five numerical target values were opened. [Earlier source experiment](https://doi.org/10.1016/S0022-1139(00)81622-X)

**Post-disclosure interpolation in the original units.** In the 22 g/100 mL fluid we used the 50- and 760-mmHg measurements to interpolate the two interior readings. A second line through the origin used only the 760-mmHg measurement. Every value below is cm³ O₂ per cm³ of emulsion.

| Pressure in mmHg | Measured mean | Interpolate between the endpoints | Scale from zero and 760 mmHg |
|---:|---:|---:|---:|
| 100 | 0.0090 | 0.009331 | 0.010487 |
| 150 | 0.0143 | 0.014662 | 0.015730 |
| Mean absolute error | | 0.0003465 | 0.0014586 |

The two-endpoint line reduced mean absolute error by 0.0011121. Allowing each of the four means to move by half its printed rounding unit yields an improvement of 0.0010644–0.0011597. Moving each within one reported standard deviation yields −0.0014865 to +0.0020712. Both calculations preserve the use of the same anchor values in every predicted point. They measure sensitivity to reading or measurement uncertainty. Individual repeat values and covariance were unavailable.

The second difference across the equally spaced 50, 100 and 150 mmHg observations was 0.00030. Its one-SD perturbation width was ±0.00410. A line through zero can satisfy all four observations once one permits movements up to 1.30 reported SDs. The two-endpoint line's apparent intercept at zero pressure, −0.00133, is outside the measured range. The stronger fit to the printed means cannot distinguish a physical curvature from a calibration offset or sampling variation.

The 25 and 33 g/100 mL fluids each contribute two pressure observations, so neither has an interior point available for this interpolation check. The original specimens had distinct loadings, and the endpoint-calibrated interpolation is specific to one fluid. The public replay includes the factual observations needed for the arithmetic, and the publisher's source figure is linked above.

To reproduce the four-observation comparison, run `python interior_replay.py` with NumPy and SciPy installed. The script writes its calculated results beside the input script.
