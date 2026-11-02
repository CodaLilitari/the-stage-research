# AB-MPB1A prescribed-flow finite-site transport

**Executed on 2026-11-01: 18/18 frozen test methods passed; all 15 frozen synthetic study rows were retained and passed their inventory/positivity guards. Independent review of this exact coupled artifact is pending.** No pumping layer has been implemented.

The synthetic comparison changes its interpretation with the initial inventory constraint. Sites with the same initial dissolved oxygen have more total oxygen and higher wall concentrations at all sampled times. Sites at equal total oxygen have lower wall concentrations, consumption and net wall transfer at all sampled times. There is no reversal within either comparison over this sampled grid. These results do not identify a real oxygen carrier, predict tissue growth or establish human compatibility.

## Implemented model and quantities

The finite reservoir and 1..16 channel cells, with optional 0..16 mixed return cells, carry free oxygen, occupied sites and empty sites as distinct amounts. Equal prescribed flow advects all three species. Each occupied site holds one oxygen unit. Binding follows `kon*(free_amount/volume)*empty_amount - koff*occupied_amount`. Only dissolved oxygen crosses each channel/wall interface. A first-order wall sink enters a cumulative consumed-oxygen ledger. Return cells are mixed compartments, not a fixed transit delay.

Total oxygen is the sum of free, bound, wall and consumed amounts. Total sites are occupied plus empty amounts. The SSPRK2 integrator uses the sufficient global exit-rate bound in ACCEPTANCE.md, a 0.9 safety factor and a 200,000-step ceiling. It does not clip or renormalize states. Arbitrary callbacks in the separate integration entry are labeled `custom_not_admitted`; the standard `solve` entry fixes the physical operator.

The reported wall minimum is the minimum across wall compartments **at the named elapsed time**. It is not the trivial minimum over an initially empty wall's entire trajectory. Net wall transfer equals final wall amount plus consumed amount minus their initial sum. It is a net exchanged amount, not a gross one-way flux integral or an independently measured tissue-delivery quantity.

## Frozen design and complete primary results

Volumes are reservoir 2 mL, channel 1 mL and wall 0.5 mL, with no return tanks. The fixed parameters are Q = 0.4 mL/s, total exchange conductance G = 0.3 mL/s, kon = 0.5 mL/(micromole s), koff = 0.2/s and sink = 0.15/s. These are synthetic values. Primary channel count is three, each wall starts empty, and requested/actual timestep is 0.01 s.

- **No sites:** initial dissolved concentration 0.8 micromole/mL; total oxygen 2.4 micromoles.
- **Sites, same initial free:** site concentration 1 micromole/mL, dissolved concentration 0.8 and initial occupancy 2/3; total oxygen 4.4 micromoles. The extra 2 micromoles are initially bound oxygen.
- **Sites, equal initial oxygen:** site concentration 1, dissolved concentration 0.3403124237432849 and occupancy 0.45968757625671514; total oxygen 2.4 micromoles. This comparison starts with less dissolved oxygen than the no-site case.

Both site-bearing cases begin at local binding equilibrium. Their initial amount partitions are below (micromoles); wall and consumed amounts initially equal zero in every case. The same partitions apply to N = 3, 6 and 12 because total fluid volume is unchanged.

| Condition | Initial free oxygen | Initial bound oxygen | Initial total oxygen | Initial occupied sites | Initial empty sites | Initial total sites | Initial occupied fraction |
|---|---:|---:|---:|---:|---:|---:|---:|
| No sites | 2.4 | 0 | 2.4 | 0 | 0 | 0 | 0 (no sites present) |
| Sites, same initial free | 2.4 | 2.0 | 4.4 | 2.0 | 1.0 | 3.0 | 0.6666666666666666 |
| Sites, equal initial oxygen | 1.0209372712298547 | 1.3790627287701453 | 2.4 | 1.3790627287701453 | 1.6209372712298547 | 3.0 | 0.45968757625671514 |

All nine primary rows follow; full precision and complete states are in run_001/numerical_receipt.json and comparison.csv. Concentration is micromoles/mL, amounts are micromoles. In every retained row the distal compartment is also the minimum wall compartment.

| Condition | Time (s) | Distal/minimum wall concentration | Consumed | Net wall transfer |
|---|---:|---:|---:|---:|
| No sites | 2 | 0.399149 | 0.040684 | 0.249305 |
| No sites | 10 | 0.462459 | 0.332798 | 0.571990 |
| No sites | 30 | 0.328213 | 0.939771 | 1.108979 |
| Sites, same initial free | 2 | 0.407282 | 0.041014 | 0.252753 |
| Sites, same initial free | 10 | 0.490747 | 0.343969 | 0.596428 |
| Sites, same initial free | 30 | 0.383084 | 1.013147 | 1.209532 |
| Sites, equal initial oxygen | 2 | 0.175650 | 0.017542 | 0.108534 |
| Sites, equal initial oxygen | 10 | 0.218782 | 0.150131 | 0.262302 |
| Sites, equal initial oxygen | 30 | 0.181702 | 0.456848 | 0.549747 |

Signed endpoint differences in absolute units, each site case minus the no-site case at the same N = 3 and elapsed time, are:

| Site comparison | Time (s) | Difference in distal/minimum concentration (micromoles/mL) | Difference in consumed amount (micromoles) | Difference in net wall transfer (micromoles) |
|---|---:|---:|---:|---:|
| Same initial free | 2 | +0.008133 | +0.000330 | +0.003447 |
| Same initial free | 10 | +0.028288 | +0.011171 | +0.024438 |
| Same initial free | 30 | +0.054871 | +0.073376 | +0.100554 |
| Equal initial oxygen | 2 | -0.223499 | -0.023142 | -0.140772 |
| Equal initial oxygen | 10 | -0.243677 | -0.182667 | -0.309688 |
| Equal initial oxygen | 30 | -0.146511 | -0.482923 | -0.559232 |

At 30 s the same-free site case has a 16.72% higher distal wall concentration and 7.81% more consumed oxygen than no sites, while carrying 83.33% more oxygen initially. That is not an equal-inventory benefit. At equal initial oxygen, the site case has a 44.64% lower distal concentration and 51.39% less consumed oxygen at 30 s. Equal total oxygen changes its initial free/bound partition and the immediately available dissolved supply; it does not isolate a universal effect of adding sites. These differences describe this finite-time parameter selection, not all binding affinities, times or carrier designs. The wall concentration rises between the sampled 2 and 10 s points and falls by 30 s; the study does not locate the actual peak.

## Compartment diagnostics

The six additional rows keep total geometry and all other parameters fixed at 30 s, changing only channel/wall compartment counts. They are retained as diagnostics; no continuum equation, boundary-value problem or spatial error order has been justified here.

| Condition | Channel cells | Distal/minimum wall concentration | Consumed | Net wall transfer |
|---|---:|---:|---:|---:|
| No sites | 6 | 0.326312 | 0.943466 | 1.113009 |
| Sites, same initial free | 6 | 0.381368 | 1.016596 | 1.213393 |
| Sites, equal initial oxygen | 6 | 0.180984 | 0.458228 | 0.551323 |
| No sites | 12 | 0.325353 | 0.945344 | 1.115051 |
| Sites, same initial free | 12 | 0.380487 | 1.018357 | 1.215362 |
| Sites, equal initial oxygen | 12 | 0.180611 | 0.458938 | 0.552132 |

The same qualitative comparisons persist at both diagnostic counts. Stable ranking across these three compartment counts does not establish spatial convergence or eliminate model-form uncertainty.

## Verification, provenance and execution bounds

FREEZE.json binds the specification, test source, original wrapper and identity stub before implementation and initial RED. RED ran 18 methods with 22 assertion-failure subcases and no errors; its test body took 0.016 s and its child wrapper measured 37.845062 s. The subsequent unchanged suite passed all 18 methods, with 0.419 s in the test body and 51.4351705 s in the wrapper, within its 60 s child deadline. The startup/wall-time difference has no established cause. A later requested pre-child termination recheck found the coordinator absent and GREEN log present; no process was terminated and no duplicate GREEN was run.

The tests cover hash-pinned SITE0 revision 1 and WEXACT0 reductions; independent circulation, pure release and wall-consumption exponentials; oxygen and site inventories; uniform site concentration; zero-site behavior; temporal refinement; automatic timestep restriction; scale/layout invariance; invalid/workload rejection; and four wrong-model witnesses. The witnesses distinguish conserved-but-wrong reservoir volume, omitted empty-site advection, incorrect elapsed-time scaling and oxygen created by clipping. The temporal-refinement test covers its declared case and does not supply a numerical error estimate for every study row.

STUDY_FREEZE.json separately binds the exact model, recorder, schema and acceptance before the comparison. The coordinator explicitly authorized a **180 s deadline covering the entire Python study child**, including startup, in response to the unresolved delays. This is a documented execution-envelope change from the earlier 60 s child statement; no frozen scientific parameter, test or assertion was changed. The direct Python `-B study.py` launch used F-only TEMP/TMP and disabled bytecode, with asynchronous stdout/stderr draining. The original coordinate.py remains unchanged as historical evidence. Its study command was not used for this run. Reusing run_001 is deliberately rejected; preserve it.

The single study child exited 0 without timeout. Its whole-Python wall time was **1.0654987 s**; internal study wall time was 0.803 s and CPU time was 0.609375 s. All 15 rows passed the frozen guards. Largest recorded oxygen residual was **1.9984014443252818e-14 micromoles**, largest site residual **1.4654943925052066e-14 micromoles**, and the lowest recorded state was zero. No negative state or clipping was reported. These residuals are inventory checks, not solution error estimates.

The separately executed audit_saved_results.ps1 re-read all 15 saved states without running the solver. It reconstructed terminal inventories, uniform site concentrations, wall concentrations, consumed/net-transfer endpoints, elapsed times, timestep bounds, fixed configurations, initial inventories and every compact CSV scalar; all checks passed. It also re-hashed both freezes, the executed kernel and both pinned oracles. SAVED_RESULTS_AUDIT.json records this static audit separately from numerical execution and independent review.

Kernel SHA-256: `d05cdd81f64464091148570d2f8c78f668e4960ffb10ae137f1ee6ad2f63c172`.

SITE0 revision 1 SHA-256: `6daa39ac3c98b93f6e8d7c8a2222e4c23ba175874c402d14c8415f1bb6126076`.

WEXACT0 SHA-256: `824340b4e29758e3592c024b912f2f5986a0a3a27fe8857622d6d57bb876afce`.

The earlier report/work-state/licensing checkpoint is preserved under checkpoints/pre_study. MANIFEST.json binds the current artifact files, excluding itself and temporary directories. Reduced-oracle admissions are recorded separately in the coordinator's SITE0/WEXACT0 review files. They do not admit this coupled implementation automatically.

## Scope, licensing and next gate

There is no viscosity, pressure, power or achievable-flow model here. Wall sink consumption is a synthetic bookkeeping law, not a validated respiration or growth law. No cell number, biomass, death, maturation, immune interaction, clotting, toxicity, carrier degradation or clearance dynamics are represented. The separate dated scope-transfer note does not alter this freeze. No empirical fit, biological experiment, material recommendation, human-use conclusion or tissue-growth result is claimed.

Richard Pemberton directs and resources the project. Coda (Codex Lily) supplies the recorded implementation, execution, verification and coordination roles. Lilitari (Lily) supplied the adopted staged design and licensing framework. See ATTRIBUTION.md, NOTICE, LICENSES.md and LICENSE_MAP.csv. Eligible new software uses Apache-2.0; prose/curated results use CC BY 4.0 to the extent applicable rights exist. Full unchanged license texts are included. Attribution does not assert AI copyright ownership. The artifact remains local and unpublished.

**Next gate:** coordinator independent numerical review of this exact source, frozen cases and saved results before considering AB-MPB1B pumping constraints.
