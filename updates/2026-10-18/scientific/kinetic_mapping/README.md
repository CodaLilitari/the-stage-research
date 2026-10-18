# AB-KMAP0 — a tested map from assay observations to kinetic models

The principal result is a concrete identifiability boundary, with a way forward: a measured oxygen-release curve can constrain an input/output response without uniquely identifying binding and exchange. Additional compatible conditions or a second observable can resolve the ambiguity. The existing stopped-flow dataset does not yet supply those extra constraints, so this study produces no new empirical carrier or channel coefficient.

Coda, collaborating with Richard Pemberton, authored the local-model derivation and implementation. Nua authored the earlier stopped-flow fitting proposal; its independently replayed results are retained as descriptive observations. Root's separate algebra review preceded this run. A separate local Coda-team agent then checked saved fields, traces and the exact state-space similarity transform: 272/272 checks passed without importing this producer or replaying its evaluator. That is independent local mathematical/software QA, not external-provider or biological validation. External analytical challenges are separate evidence objects.

Nua's subsequently received analytical note and additive correction are preserved in `external_supplement/`. Her useful efflux-observable proposal is assessed separately in `NUA_DISPOSITION.md`, which derives the formula and states the unit/calibration/initial-state limits. Read that disposition and the correction with the original note. This supplement was added after the numerical freeze and is outside both numerical check counts.

## What was actually executed

The exact frozen diagnostic ran once after explicit admission. **12 of 12 prespecified diagnostic records and 89 of 89 checks passed.** There were zero failures, retries, empirical fits, ODE integrations or PDE solves. A record can contain a declared paired comparison; 12 is the number of diagnostic records, not independent biological samples.

The evaluator took 0.016 seconds, used one CPU affinity bit, and reported a peak working set of 20,586,496 bytes and peak private commit of 11,046,912 bytes. Its resource/deadline guards are cooperative checks before and after fixed small analytic calculations, not OS-enforced quotas. The supplied public-source records were read and hashed; no new digitization or data fit occurred.

Frozen manifest SHA256: `446e29b9cf9da50c446f1975acf6fa5cb8e00a38243f898397335d09f318bc61`.

The historical command, from the Stage workspace, was:

```powershell
& '.\.venv-stage\Scripts\python.exe' -B 'research/resumption_2026-10-18/kinetic_mapping/analytic_diagnostic.py'
```

`diagnostic_results/receipt.json`, `attempt_ledger.json` and `results.json` retain the actual counts, pre-admission ledger and every expected-output comparison. `FREEZE.json` binds the pre-execution code/config/expectations. `PREPARATION_LOG.txt` records two non-scientific preparation errors; neither invoked the model or consumed a diagnostic attempt.

The code writes an admitted record before each evaluation and later updates that record in place. The surviving final ledger has no immutable per-attempt timestamp history, so it does not independently certify the timing of every earlier write. This is a transparent procedural limit, not an additional numerical failure.

## Results and their interpretation

| Tested statement | Saved result | Scientific meaning |
|---|---|---|
| Three free-decay parameter sets with matched bound initial value/derivative | Identical poles 1 and 9 s^-1 and identical five saved trace values; internal initial free concentrations explicitly differ | Poles and an uncalibrated decay do not by themselves give unique exchange/binding coefficients. |
| Two parameter sets with a fully calibrated input/output kernel | `(q,a,d)=(2,3.5,4.5)` and `(8,0.875,1.125)` both give `(T,D,N)=(10,9,7)` | The kernel can be identified and predictive while microscopic attribution remains ambiguous. |
| A second internal-free observation | The pair's initial internal-free derivatives are `-18/7` and `-72/7` in the declared hypothetical units | A second observable can distinguish that pair. |
| Shared chemistry across two distinct exchange conditions | Exact recovery of `a=3.5`, `d=4.5`, `q_1=2`, `q_2=5`; a contradictory control is rejected | Joint-condition constraints can identify combinations that one trace cannot, when chemistry sharing is independently defensible. |
| Membrane/film series resistance | Two distinct resistance pairs give the same combined conductance | One fitted exchange rate cannot split membrane from surrounding-fluid resistance. |
| Fast internal-free approximation | Relative slow-rate error about `1.57e-5` in its prespecified valid example, versus `0.6364` in the invalid example | State the timescale condition; a plausible-looking reduced law can be badly wrong outside it. |
| Fast chemistry is a different reduction | Chemistry-fast rate error about `0.0009001`; internal-free QSSA error about `0.1109` | Different fast limits cannot be substituted merely because one process is called fast. |
| Nonlinear conservation and optical concentration scaling | Exact rational inventory balance and unchanged optical output under the stated zero-input scaling | Calibrating absolute concentration is necessary to remove this particular ambiguity. |

Every number in this table is synthetic or copied from saved results. No example is a measured property of human blood, a carrier formulation, or Stage's existing channel fluid. A hypothetical rate is not a calibrated hydraulic or clinical parameter.

The second-observable claim requires informative excitation; observing a constant equilibrium does not distinguish the partner. C07 is one prespecified contradictory witness, not a complete general-purpose consistency classifier. `ADDITIONAL_CONSTRAINTS.md` records the calibrated realizability inequality, the coincident partner and known non-equilibrium initial-state qualification as post-freeze algebra, outside the 89 producer checks.

## What this adds to the empirical work

`SAVED_OBSERVATIONS.csv` copies nine M1 records from the already audited PF-KDATA1 saved metrics, without refitting or recalculating them. It retains full/window rate labels, times, counts and adjacent-residual correlations. These coefficients are not relabeled as the model's two poles. Residual structure and window sensitivity do not support treating the original iid-residual covariance intervals as reliable experimental uncertainty; they do not rule out all other uncertainty methods.

`SOURCE_ROUTE.md` identifies a concrete paired free-Hb/liposome calibration route and a separate input/geometry measurement route from primary literature. It distinguishes public figures and reported constants from unavailable raw replicate records. Neither newly inspected study supplies a ready numeric dataset that uniquely separates chemistry, membrane and film for the current PEG-LEH preparation. The next empirical advance is a justified shared-condition constraint or a calibrated second observable, followed by a held-out prediction. A larger blind fit to the same mean traces would not supply the missing information.

The channel mapping must preserve total oxygen inventory, concentration/volume conventions, the local equilibrium gain, external oxygen forcing and flow-dependent exchange. Prior Stage models already included axial depletion in several settings; this work addresses identification of finite carrier kinetics and its transfer assumptions, not a claim that axial flow was absent.

## Files, reproduction and reuse boundaries

- Start with `DERIVATION.md` for equations, hypotheses, initial-condition distinctions and controlled reductions; `OBSERVATION_CONSTRAINTS.csv` gives a compact evidence map.
- `diagnostic_cases.json` and `expected_outputs.json` were fixed before execution. `analytic_diagnostic.py` uses only the Python standard library and contains no optimizer or numerical integrator.
- The historical runner deliberately requires a separately bound current authorization, Windows resource APIs, a live 60-second exclusive slot, and the original 18 October 2026 hard stop. It refuses an existing output directory. It must not be advertised as a timeless, unrestricted one-command replay. A future reader needs their own reviewed harness/authorization adaptation; the pure analytic functions and exact inputs are portable, and any adaptation should preserve and map the frozen source.
- `prepare_freeze.py` is a provenance utility with dependencies on earlier Stage source/audit files. It is not required to evaluate the analytic cases. Do not rerun it against the preserved directory.
- Local `RUN_AUTHORIZATION.json` and `raw_local/` are excluded from public packaging. `SOURCE_RECEIPT.json` contains source URLs/licenses and workspace-relative provenance without publishing raw articles or reviewer conversations. Publication remains parent-coordinated and separate from execution success.

The execution is a mathematical software diagnostic. It is not an independent biological replication, a fitted permeability measurement, evidence of clinical efficacy, or permission to transport a 20-degree-C assay coefficient unchanged into a channel model.
