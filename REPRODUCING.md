# Reproduction boundaries

This release includes actual saved outputs and original scientific source. No scientific matrix was executed while curating public copies. Public-copy checks parse code, inspect required inputs, check hashes and review claims; they do not certify a new runtime. Several scripts overwrite outputs or refuse existing output directories. Use a disposable copy, keep the release immutable and retain new outputs under a new run identity.

Use an appropriate Python environment. Standard-library tasks include PA0, FL0 and the core FL1-R benchmark. Scientific analysis uses the imports declared in each script: commonly NumPy, SciPy, pandas, Matplotlib and Biopython. MuJoCo is an optional separate dependency; the fresh parity receipt specifies 3.16.0. The snapshot contains no runtimes, weights or libraries. Version files and original receipts are evidence of the original environment, not a universal installation lock across operating systems.

## Compact entry points

Commands below are relative to the public package root and are provided for a separate working copy. They were read against the supplied code, not re-executed during release curation.

| Task | Entry point | Boundary |
|---|---|---|
| HC0 saved numerical replay | `python research/human_oxygen_carrier/hc0.py verify` | Recomputes the declared equilibrium matrix, writes a new verification receipt. Original scientific code is unchanged. |
| PF0 run | `python research/artificial_blood/pf0.py` | Uses included freeze; rewrites outputs in its directory. Inspect the retained monotonicity failure. |
| OK0 corrected run | `python research/oxygen_kinetics/kinetics.py` | Original corrected code/hash preserved; rewrites declared numerical outputs. |
| MECH1 | `python research/grokbot_mechanics/coupled_screen.py` | Uses included original freeze and assumptions; rewrites screen files. |
| Nua synthetic sensitivity | `python research/muse_pf_data1/corrected/pf0_sensitivity.py` | Uses copied PF0 source and scenario freeze. No individual source rows required. |
| Nua subject-level correction | `python research/muse_pf_data1/corrected/analysis.py` | **Not self-contained:** omitted Table 1 CSV required; see that directory's public release note. |
| PA0 validator | `python experiments/archive_fixture/validate_fixture.py --release experiments/archive_fixture/release --anchor experiments/archive_fixture/receipts/release_anchor.json` | No LLM call. Included fixture/anchor are completed public examples. |
| BH0 | `python research/biohybrid_hand_reanalysis/analyze.py --help` | The script provides `--freeze` and `--out`; without `--freeze` it analyzes the included checksum-matched data. Choose a new output directory. The acquisition helper is unnecessary for these supplied files. |
| Structural analysis | `python research/protein_modeling/analyze_hemoglobin.py` | Deposited CIFs, entry JSONs and download receipt are included; requires NumPy/Biopython. |
| FOLD1 evaluation | `python research/protein_modeling/evaluate_fold.py` | Evaluates the supplied predicted coordinates, not a new GPU fold. Includes UniProt sequence metadata. |
| Cowork corrected numeric audit | `python research/cowork_cloud_qa/audit_numeric.py` | Original solver, original replay CSV and corrected cases are included; performs numerical work and writes outputs. |
| Lily witness review | `python experiments/lily_independent_qa/independent_witness_check.py` | Reads supplied delivered witness artifacts. Scope and historical tolerances are recorded in its receipt. |

## Source-dependent or historically bound scripts

`research/gemini_qa/audit.py` has an explicit public source-pointer adaptation to its included `original/` folder. It still requires omitted primary-source HTML/figure inputs for the full source audit. It is retained as historical audit code, not advertised as a self-contained source-reproduction command. The original model and its local outputs are present separately.

`research/cowork_cloud_qa/summarize.py` is historical archive/figure assembly code. It reads excluded primary HTML/text and copies source snapshots. Inclusion of the code does not grant those sources' redistribution rights or authorize broad fetching. Use saved public reports rather than treating this helper as the default reproducibility entry point.

`research/protein_modeling/hb_fold2/evaluate_fold2.py` performs coordinate evaluation and then checks all entries in the original 49-artifact FOLD1 manifest. The lean release intentionally excludes some original operational artifacts and raw MSA. That complete historical-manifest assertion cannot pass in this subset. The coordinate outputs, comparison table, current export hashes and independent 21-check receipt are provided; do not remove the assertion silently and claim the original full integrity check ran. Recreating a fold also requires separately licensed tools, chosen weights and an independently obtained alignment. Weight licenses must be checked for the actual download; this release provides no weights.

FL0's public human-credit correction changes source/config hashes. Original `freeze_receipt.json` is retained as historical evidence and deliberately not relabeled as an export freeze. For a new run, copy only `first_leaf.py` into a fresh directory, then execute `python first_leaf.py prepare` followed by `python first_leaf.py run`. This creates new local bindings for the exported source. It is a new replay, not a recreation of the original pre-run timestamp. Do not run original `verify` against omitted long traces or original hashes and interpret rejection as a scientific failure. SW1 remains an invalid-control history, not the current benchmark.

OK0's *original proposal* and some original collaborators' code have public-credit metadata edits. Their saved original execution hashes identify the preserved historical originals; the public provenance map identifies export bytes. This distinction also applies to any nested historical manifest. The current top-level manifest is the release-integrity authority. No newly generated export binding is represented as a preregistration.

Cowork local cross-check code references the original PF0 `MANIFEST.sha256`, not included as an operational source manifest in this reduced archive. Its returned results and author checks are retained, but a self-contained replay has not been established here. The unfinished state and pending numerical review remain explicit.

## Source-data acquisition

BH0's two exact CSVs are included under CC0 with repository hashes. PDB 2DN1/2DN2 archive coordinates/sequences/selected metadata are CC0. UniProt P69905 is a dated unchanged CC BY 4.0 JSON snapshot. See the source notices for citations and retrieval URLs.

For Stücker Table 1, use the cited primary source and its terms for your use; the public note gives the omitted file's hash and schema expectations. A locally reconstructed CSV with different formatting will not share its hash even if numeric cells match, so record both numeric verification and byte provenance. Do not infer source redistribution permission from the fact that a historical script can parse a table.

Released synthetic fixtures and evaluator keys are transparent completed evidence. New evaluations need newly separated holdouts and a distinct run record. This release supplies no credentialed API harness or authorized physical-actuator loop. Historical wet-lab and operating proposals are included for critique only, not as validated or authorized procedures.
