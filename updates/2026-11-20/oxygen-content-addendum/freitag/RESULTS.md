# Transferring a limb venous oxygen prediction between two canine studies

A simple model trained on Standl et al. (2003) predicted the six post-baseline group-mean popliteal venous oxygen contents reported in Freitag et al. (2005) with a mean absolute error of 0.68 mL O₂/dL. The model reused the median training extraction fraction from the corresponding phase. Three observations are repeat occasions for the six controls and three are repeat occasions for the six treated animals. These are six group means from one other study with overlapping investigators. [Training study](https://pubmed.ncbi.nlm.nih.gov/12663989/) · [External study](https://doi.org/10.1007/BF03022050)

## What was predicted

The input was mean femoral arterial oxygen content from Table II and limb flow from Table IV. The output was mean measured popliteal venous oxygen content in Table IV. The papers measured blood oxygen content independently of the tissue oxygen-tension probe. Training errors are presented as SEM in the 2003 report; the 2005 target report gives SD. Means of products such as flow × content depend on paired covariance and cannot be recovered exactly by multiplying group means. Methods and Table IV refer to arterial popliteal flow, while the later appendix calls the flow venous.

The coordinator had seen Table IV before the exercise. The paid algorithm authors and their input-only runtime saw no external venous values. Local comparison formulas were fixed before any local reading of external V; during extraction the local reviewer saw the two baseline V means before freezing numerical forecasts. All eight conditional numerical forecasts were locked before the local reviewer read the six post-baseline outcomes. We present these six as the primary retrospective comparison and analyze the two baselines separately. Numerical input SHA-256 is b9b6fe8042abd790e6d12b5f88bd97f0e3e672823b33bc702e9e70ffd2afb68f; locked forecast SHA-256 is a5fc64ef7012eaf3fdb71ba9d89141b63796ab306a41914bfdbd4909dc585b30.

## Fixed external predictions

| Training rule | All six post-baseline RMSE | Control three | Treated three |
|---|---:|---:|---:|
| Phase-matched fractional extraction | 0.756 | 0.929 | 0.529 |
| Phase-matched content difference | 1.712 | 0.947 | 2.229 |
| Phase-matched fixed uptake | 1.015 | 0.837 | 1.167 |
| Phase-matched plug-flow law | 2.042 | 0.824 | 2.768 |
| Pooled fractional extraction | 1.280 | 0.863 | 1.591 |
| Pooled content difference | 2.810 | 3.064 | 2.530 |
| Pooled fixed uptake | 1.028 | 1.009 | 1.046 |
| Pooled plug-flow law | 5.122 | 7.163 | 1.073 |

All values are mL O₂/dL. At 20, 60 and 100 min, the phase-matched fraction model gave control predictions 16.12, 15.81, 15.88 against published 15.7, 14.8, 14.7. Treated predictions were 6.58, 4.92, 4.92 against 6.4, 5.6, 5.5. For the two carrier-exposure clocks the external arterial content was 10.4 mL/dL and flow 53–60 mL/min. The corresponding carrier training rows spanned 4.9–6.9 mL/dL and 100–114 mL/min. Performance in this particular external comparison therefore includes covariate extrapolation. Flow alone and a study-wide plug-flow law performed poorly in some phases. The small number of aggregate rows and inter-study differences do not support an intervention effect or a model ranking for humans.

## Internal measurement audit

The treated baseline prints A = 22.0, V = 13.1 and muscle A−V = 5.1 mL/dL. The reported independent content means differ by 8.9 mL/dL. The discrepancy from the printed difference is 3.8 mL/dL; every other occasion agrees within 0.1. We preserved all published values without silently substituting an inferred baseline. The two-baseline RMSE of the phase-matched fractional model was 3.34 mL/dL.

Rounding the concentrations to the printed 0.1 mL/dL and flow to 1 mL/min cannot account for the anomaly. Even allowing the full finite-sample covariance range implied by n=6, the published mean flow 43 (SD 27) and arterial content 22.0 (SD 2.2) imply mean delivery between 8.813 and 10.107 mL/min. The reported 7.2 mL/min falls outside. This establishes a discrepancy among summaries under the same-animal Fick interpretation; the underlying cause is unresolved.

The liver measurement has a different interface. Appendix assumptions combine one third arterial and two thirds portal venous content and use total hepatic flow estimated as 1.5 times measured portal flow. The appendix prints a pulmonary outflow label, while the methods describe inferior-caval sampling above the hepatic venous junction. Using the caval measurement reproduces the reported hepatic content difference within 0.10 mL/dL in seven rows; the pulmonary alternative misses by up to 2.17 mL/dL. For the treated baseline, the hepatic summaries imply A ≈18.4 mL/dL under the caval interpretation; the limb V + reported difference implies 18.2 mL/dL. These two values are diagnostic reconstructions. Neither is an independent arterial measurement or a replacement for the printed 22.0. The appendix also prints multiplication in its muscle extraction ratio where the systemic extraction ratio elsewhere uses division. This analysis used the directly measured limb V as its target.

## Reproducibility

The stand-alone public replay verifies and reads the original training and external paper PDFs. Only the external arterial and flow columns enter prediction. The raw external venous table is available to the scoring stage only. See SOURCE.md and replay.py. No original paper pages or animal-level records are distributed.
