# The Stage — research update, 2 November 2026

**Thermal skin-panel models and the First Leaf embodiment gateway.** This additive update publishes the executed
results of a two-day research run (1–2 November 2026). The run used Claude API batch requests funded by a
promotional credit allocation. It contains computational models of a **nonliving** layered skin panel, gateway
software tests, and numerical audits of earlier kernels. It describes no physical prototype, no material testing,
no biological or clinical work, and no validation against measurement. Agreement between models is agreement
between models.

This update leaves the [15 October snapshot](../../README.md) and the [18 October update](../2026-10-18/README.md)
unchanged. Richard Pemberton directs the project. Coda (Codex Lily) designed the contracts and ran the first part of
the run (waves 1–5, 1 November). Red (Claude, Cowork) continued it (waves 6–12, 2 November). Red designed the requests,
assembled and executed every returned file in an isolated sandbox, diagnosed failures, and curated this update.
Claude Fable 5.1 wrote the returned models, audits and tests. Contributor roles are in [ATTRIBUTION.md](ATTRIBUTION.md).

## Main result

Four separately written implementations of Coda's synthetic panel contract T0-HYP-1 now agree. The contract has
silicone, then a film carrying a sensor sheet, then silicone again, plus a heater node. They agree on every quantity
at least two of them compute, within tolerances declared before comparison from each model's own error estimates.
The four are Coda's two-node lumped transient, a 1-D finite-volume fault model, a semi-analytic layered eigen-oracle,
and a radiation extension at emissivity zero. The cross-check passes 480 + 60 + 441 + 2,124 checks across tiers T1–T4.
The first run failed 66 checks, all in fault case F2. The cause was a specification-transfer error, not numerics:
Red's request to the oracle's author omitted the contract's F2 value, and the author used a labelled assumption.
The cross-check found an error that each model's own test suite could not see. See
[NVERSION_F2_RESOLUTION.md](scientific/thermal/nversion/NVERSION_F2_RESOLUTION.md).

| Contribution | What is provided | Critical qualification |
|---|---|---|
| [1-D finite-volume fault model](scientific/thermal/fv1d/) | F0–F5 fault suite, energy-balance checks, 28 tests | Synthetic 1-D panel; no lateral conduction or real sensor dynamics |
| [Layered eigen-oracle](scientific/thermal/layered_oracle/) | Semi-analytic reference with interlaced root bracketing, 21 tests | F2 default corrected by Red; results before and after the fix are both kept |
| [Radiation extension](scientific/thermal/radiation/), [closed-form peaks](scientific/thermal/peak_exact/), [sensitivity](scientific/thermal/sensitivity/) | Emissivity sweep; exact two-node peak times for all 9 executed scenarios; predeclared one-at-a-time sensitivity | Rear rejection resistance dominates; interactions not yet analysed (global analysis in progress) |
| [2-D localized delamination](scientific/thermal/hotspot2d/) | Patch-delamination model, study results, 19 tests | Observed refinement order is about 1, not the claimed 2: open |
| [Supervisory protection design](scientific/thermal/supervisor/) | Threshold/model-residual supervisor, full scenario matrix, 30 tests | 40/60 °C are arbitrary study comparators, not safety limits |
| [Candidate 3 review](scientific/thermal/candidate3_review/), [metamorphic suite](scientific/thermal/metamorphic/) | Repaired steady contract module; 68-test metamorphic/contract suite | One open test-expectation failure; the informational tier of non-promised relations records 14 failures and 1 error |
| [N-version cross-check](scientific/thermal/nversion/) | Script, predeclared tolerances, outputs before and after the F2 fix | Model-vs-model only |
| [Integrated gateway](scientific/gateway/integrated/) | Lifecycle relay and interface built on Lilitari's First Leaf; 128 tests incl. a trace-replay conformance module | 4 documented non-conformances remain as expected failures |
| [Model checker](scientific/gateway/model_checker/), [simulator audit](scientific/gateway/first_leaf_sim_audit/) | Explicit-state checker (8/8 seeded bugs caught; 4 design gaps with traces); 7 simulator defects confirmed | Checker covers the design model, not every code path |
| [First Leaf oracle baseline](scientific/gateway/oracle_baseline/) | Public-packet oracle agent, harness, scoring | Harness seeds 20001+ only; not FL1-R's frozen development or evaluation seeds |
| [Numerical kernel audits](scientific/numerics/) | SITE0 domain and mutant-blindness audit; WEXACT0 audit; AB-MPB1B pump audit; release-observability study | Numerical analysis of synthetic kernels; no physiological claim |

Read [RESULTS.md](RESULTS.md) for the executed numbers, [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for what remains open,
[REPRODUCING.md](REPRODUCING.md) to re-run the checks, [PROCESS_NOTES.md](PROCESS_NOTES.md) for how the run was
operated, and [INCLUDE_EXCLUDE.md](INCLUDE_EXCLUDE.md) for scope. Returned model answers are preserved under
[received/](received/), with path sanitization only. The request statements are under
[provenance/requests/](provenance/requests/). [source_export_map.json](provenance/source_export_map.json) records
the source and sanitization of every file.

Every check listed in [REPRODUCTION_RECEIPT.txt](REPRODUCTION_RECEIPT.txt) was re-run from this published layout
before release, and each reproduced its recorded outcome. Use `python -B verify_release.py` for read-only integrity
verification of this folder. Its success does not validate the science or authenticate authorship.

Code uses MIT, and authored prose and derived results use CC BY 4.0, to the extent the releaser holds the
applicable rights. Copies of collaborator files keep their credit in [LICENSE_MAP.csv](LICENSE_MAP.csv). Private
conversations, account and session records, credentials and raw API traffic are excluded.
