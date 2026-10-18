# The Stage — research update, 18 October 2026

**Artificial blood is the first research milestone.** This additive update contains mathematical models, computational verification and a reanalysis of published oxygen-release traces. It does not describe manufactured artificial blood, clinical efficacy, a validated material, or maintained living tissue on a robot. Human oxygen therapeutics and circulation for engineered tissue remain separate applications.

This update leaves the [15 October snapshot](https://gitlab.com/codalilitari/the-stage-research/-/releases/snapshot-2026-10-15) unchanged. Richard Pemberton directs the project. Coda (Codex Lily) coordinates implementation, integration and independent checks within the project. Contributor names and concrete roles are in [ATTRIBUTION.md](ATTRIBUTION.md); attribution is not provider endorsement or a legal-ownership finding.

The main result is conditional: in one refined hypothetical AB-CT0 comparison under the same permitted pressure and fluid-power caps, instantaneous carrier equilibrium is slightly above dissolved fluid in distal tissue oxygen, while finite release falls below it. **Equal caps do not mean equal actual power.** The tiny equilibrium-versus-dissolved total-uptake difference remains numerically unresolved. Measured stopped-flow apparent rates do not yet supply a validated channel-scale relaxation rate.

| Contribution | What is provided | Critical qualification |
|---|---|---|
| [AB-CT0](scientific/ab_ct0/) | Source, 78 saved attempts, selected convergence and independent saved-field QA | Hypothetical Hill tissue transport; clamped inlet; selected contrasts only |
| [Red transport/AL1](scientific/red_transport/) | Original work, both correction versions, reproduction/independent QA | Failed E5/E6 retained; equal flow/power and comparison denominators matter |
| [Lilitari's AB-LFR1](scientific/lily_ab_lfr1/) | Linear verification instrument and original attempts | Final frozen suite is 1,612/1,613, with one deliberately retained failed expectation |
| [Nua's PF-KDATA1](scientific/nua_pf_kdata1/) | Published S1 workbook, extraction, original fits, correction and Coda replay | Averaged assay traces; window sensitivity and unidentifiable lag; no empirical Stage k |
| [Wren linear benchmark](scientific/wren_linear/) | Partial original and separate Coda local recovery | Coda supplied equations/eight cases; Wren implemented independently; lost cloud outputs remain lost |
| [AB-LA1](scientific/linear_adapter/) | Actual production-stepping verification: 47 positive attempts, four detected faults; separate saved-field QA | 49 calls completed and two expected exceptions; linear reduction, no material validation |
| [AB-KMAP0](scientific/kinetic_mapping/) | 12 analytic diagnostic records, 89 checks; separate 272-check saved-output review | Identifiability and controlled-reduction examples, no empirical fitted parameter |
| [Motion/perfusion context](context/motion_perfusion/) | Bounded primary-source findings | Adjacent prior art exists; no absence/priority claim and no new biological experiments |

Read the preserved October 17 [SESSION_RESEARCH_REPORT.txt](SESSION_RESEARCH_REPORT.txt), the [October 18 addition](OCT18_RESULTS.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md), [REPRODUCING.md](REPRODUCING.md) and [INCLUDE_EXCLUDE.md](INCLUDE_EXCLUDE.md). The visible numerical figure and CSV are in [figures](figures/). Historical source reports preserve their run-time wording; dated corrections and the synthesis state which claims remain accepted.

The root manifest identifies public bytes. Original scientific freeze hashes identify earlier bytes and are **historical evidence**, not fresh preregistration of privacy-edited copies. [Source/export mapping](provenance/source_export_map.json) identifies changes without disclosing private source locations. Use `python -B verify_release.py` for read-only integrity verification. Its success does not validate the science or authenticate authorship.

Code uses MIT and authored surrounding prose/figures/derived results use CC BY 4.0, to the extent the releaser holds applicable rights. Primary data and executable examples retain the file-specific terms in [LICENSE_MAP.csv](LICENSE_MAP.csv) and [SOURCE_RIGHTS.md](rights/SOURCE_RIGHTS.md). Private conversations, account records, authorization files, runtimes and model weights are excluded. Curation did not rerun a scientific study.
