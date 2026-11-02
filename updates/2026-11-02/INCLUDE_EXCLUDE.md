# Scope of this update

The file-level [MANIFEST.json](MANIFEST.json) and [LICENSE_MAP.csv](LICENSE_MAP.csv) define the exact included bytes.

**Included.** The update has six kinds of material:
- the executed working trees, meaning the code and tests exactly as Red ran them, including spliced and patched
  files;
- study outputs and test receipts;
- the returned model answers for every published line;
- the request statements, with the labels and SHA-256 hashes of the sources bundled into each request (not the
  sources themselves);
- unmodified copies of the collaborator files that the published code needs in order to run;
- this update's documents and reproduction check.

**Sanitization.** Changes are limited to:
- local and sandbox paths, replaced with neutral labels (`red-sandbox/`, `red-run/`, `coda-run-2026-11-01/`,
  `<home>`, `<archive>`);
- batch and request identifiers, which are redacted;
- the oracle README, where a correction notice was added.

Of the published files, 36 were changed by path or identifier sanitization. Original and export hashes are paired
in the provenance map. A hash that differs from a historical receipt is not evidence of a new execution. No result
was recomputed for publication. The only post-run changes to science are the one-line F2 correction in the layered
oracle and its rerun, both documented and both executed before this release.

**Excluded.**
- Raw API traffic (request and result files), batch and request identifiers, and the spend ledger with its account
  identifiers. A per-wave cost summary is in PROCESS_NOTES.md.
- Credentials, and the runner's key-handling material.
- Private conversations, and account or session records.
- Requests and partial answers of the closed lines. These were refused by Claude Fable 5.1 and by the Opus 5.5
  fallback, or never produced a complete answer: KMAP, finite-inventory, human-admit, tissue-ladder,
  shared-platform, mpb1a-robustness-audit and release-observability-002a. They were not reworded or retried.
- Coda's full 1 November run folder. It is hers to curate, and only the dependency copies named above are included.
- Nua's (Muse's) code, the corrected derivative of her AB-LFR1 check, and Red's reviews of her AB-LFR1 and
  AB-MPB1A work. These are pending her exact-export review, which is the project's convention for contributor
  material.
- Wave 13. It was still in progress when this update was prepared; its results belong to a later update.

**Historical wording.** The requests and several answers describe the work as private research and "not a public
release". That describes the run at the time it was done. Publication is the project director's later decision.
This folder does not assert that any contributor review of this export has been completed.
