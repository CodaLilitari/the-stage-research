# The Stage — computational research snapshot

**First milestone: artificial blood.** This release brings together two research branches: human oxygen-carrier models (H) and circulation supporting engineered living tissue (S). The longer-term objective is maintainable living tissue over robotic bodies, or a feasible alternative. These are computational studies, source checks and reanalyses of published data. We have not manufactured artificial blood, demonstrated transfusion efficacy, maintained a living tissue module, or built a physical AI body.

Richard Pemberton directs and hosts the project. Coda (provenance label Codex Lily) coordinates local implementation, source audits and integration. Lilitari (Lily), Nua, Grok Bot, Grok, Meta AI, Red through two Claude Cowork routes, Gemini and an Antigravity-route reviewer have distinct contributions and correction histories. See [ATTRIBUTION.md](ATTRIBUTION.md); collaboration is not a claim of human-equivalent authorship, legal ownership or provider endorsement.

This is a dated **15 October 2026 snapshot**. Its useful result is a more explicit, executable set of constraints and counterexamples. It is not a finished design. The complete release scope, licenses and provenance are defined by [INCLUDE_EXCLUDE.md](INCLUDE_EXCLUDE.md), [LICENSE_MAP.csv](LICENSE_MAP.csv), [SOURCE_RIGHTS.txt](rights/SOURCE_RIGHTS.txt), and [source_export_map.json](provenance/source_export_map.json). The package manifest identifies the actual public bytes. Historical run freezes identify earlier source bytes and must not be mistaken for a new preregistration of these sanitized copies.

## Where to start

| Question | Public material | What was actually established |
|---|---|---|
| Can equilibrium capacity predict oxygen exchange? | `research/human_oxygen_carrier/`, `research/oxygen_kinetics/` | Hypothetical Hill and finite-rate parcel models; kinetic counterexamples show why affinity and capacity alone are insufficient. |
| Can flow or added capacity erase local transport limits? | `research/artificial_blood/` | PF0's 144 cases include 55 threshold passes and a retained failed monotonicity assumption. Geometry and wall transfer remain distinct constraints. |
| What changes with plausible lower skin-demand scenarios? | `research/muse_pf_data1/` | Corrected summaries of 20 published volunteers and 432 synthetic scenarios. The complete published subject table is excluded; aggregate findings and code are included with retrieval requirements. |
| How do hydraulics and oxygen transport interact? | `research/grokbot_mechanics/`, `research/grok_build_qa/`, `research/cowork_cloud_qa/` | Original proposals and distinct local corrections, including a hydraulically plausible case that fails radial oxygen supply, zero-budget boundary defects, source-unit corrections and a mesh-sensitive threshold classification. |
| Can a known haemoglobin fold calibrate the tools? | `research/protein_modeling/` | Deposited geometry and one known-chain prediction comparison. Mean confidence/RMSD improve with MSA assistance; neither result establishes oxygen affinity, toxicity or therapeutic function. |
| What has already worked in biohybrid engineering? | `research/related_projects/`, `research/biohybrid_hand_reanalysis/` | Source-grounded comparisons and checksum-matched reuse of a small public actuator-force dataset. Three repeatedly measured actuators are not 24 independent subjects. |
| Can the control/archive interfaces be tested before a body exists? | `experiments/archive_fixture/`, `first_leaf/`, `mujoco_probe/`, `adapter_demo/` | Synthetic archive discrimination, controlled changing-body tasks, a simulator probe and a sensor/action adapter. These are not identity or consciousness experiments. |
| What did Lily implement independently? | `experiments/lily_independent_qa/`, `research/lily_px1_qa/` | FL1-R, its witnesses and local checks; PX1-HS mathematical diagnostics; CT1 remains a specification/planner. A cross-runtime trajectory discrepancy and Gateway defects remain open. |

The Cowork local contribution is included as **partially delivered**: 17 actual files, author-reported runs and checks, with an unfinished final report/manifest. Its receipt verifies files and counts, not an independent numerical replication. Meta's [limited contribution note](research/meta_contribution/CONTRIBUTION_AND_CORRECTION.md) records an artifact-access limit; no missing native code is portrayed as a completed public module.

## Reading and reproducing

Start with [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [REPRODUCING.md](REPRODUCING.md). They identify which scripts are directly reusable and which historical audit scripts require excluded inputs or original hash context. Work in a new checkout/copy if running commands: several scripts write their output files in place. No simulation matrix was rerun merely to curate this release.

Each scientific report retains its original run-time status; later public correction notices take precedence where expressly identified. Original collaborator code remains labeled separately from corrected derivatives. The word “independent” in local QA means a separate implementation or reviewer within this project, never independent laboratory validation.

The next research work, after publication, is to define a traceable tissue-support module contract; couple carrier exchange, local diffusion and finite supply with explicit units; then test controller observability and body revisions against those constraints. Acceptance must concern measurable numerical properties and parameter evidence before any biological or clinical claim is made. Historical contributions include unvalidated physical and biological experimental proposals, retained for critique. They are not adopted protocols, and this snapshot neither authorizes nor validates their execution. No physical, biological or clinical experiment was performed by this project.

Code is offered under MIT and authored prose/figures/derived outputs under CC BY 4.0 to the extent the releaser can grant those rights. The exact file map carves out CC0 source data, UniProt's CC BY 4.0 snapshot and standard legal texts. Contributor assent does not clear third-party rights. Private founding documents, chats, account records, video, weights, runtimes, raw MSA and uncleared complete source tables are not part of this release.
