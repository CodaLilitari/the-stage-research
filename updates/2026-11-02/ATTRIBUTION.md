# Attribution — research update 2026-11-02

Collaboration credit describes who did which work. It is not a claim of human-equivalent authorship, legal
ownership, or provider endorsement. File-level credit is in [LICENSE_MAP.csv](LICENSE_MAP.csv), and the exact
source of each file is in [provenance/source_export_map.json](provenance/source_export_map.json).

- **Richard Pemberton**: project direction, funding of the API run (promotional credit allocation), and the
  decisions on scope and publication.
- **Coda (Codex Lily)**: ran waves 1–5 of the API run on 1 November and designed the T0-HYP-1 synthetic panel
  contract with its fault cases F0–F5. Also wrote the steady thermal reference and the two-node lumped transient
  (LUMP2), the gateway lifecycle design, and the SITE0, WEXACT0 and AB-MPB1A/B numerical kernels. Her files appear
  here only as unmodified copies needed to run the published audits (`coda_dependencies/`, `validation/` subfolders).
  Her own run folder is hers to curate and is not republished here.
- **Lilitari (Lily)**: author of the STAGE FL1-R First Leaf protocol, simulator, relay and original gateway. The
  integrated gateway in `scientific/gateway/` is a derivative of her code, with lifecycle work by Coda and Claude.
  Her original files keep her credit.
- **Claude Fable 5.1 (Anthropic)**, through the Claude API (batch, maximum effort): wrote the models, audits, tests
  and reviews returned in waves 6–12. Answers are preserved in `received/` and identified by request in
  `provenance/requests/`. Each answer was static reasoning until Red executed it.
- **Claude Opus 5.5 (Anthropic)**: used only as a refusal fallback. None of its outputs are in this update.
- **Red (Claude, Cowork)**: continued the run on 2 November. Red designed the requests (waves 6–12) and operated
  the batch runner. Red assembled and spliced returned files, executed every test and study in an isolated sandbox,
  and diagnosed failures, including the F2 specification-transfer error and harness-layout errors. Red wrote this
  update's documents and the reproduction check, and curated the release.
- **Nua (Muse)**: her independent AB-LFR1 and AB-MPB1A checks were reproduced and reviewed by Red during the run.
  Her code and the reviews of it are not included, pending her own exact-export review. See
  [INCLUDE_EXCLUDE.md](INCLUDE_EXCLUDE.md).

The word "independent" in this update means a separately written implementation or review within the project.
It never means independent laboratory validation.
