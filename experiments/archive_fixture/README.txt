PA0 synthetic archive fixture and offline validator
==================================================

This directory implements a bounded harness-development step from The Stage v0.3.
Mica is a fabricated fixture identity. Every event, phrase, preference, correction,
restriction and scenario here was invented for testing. No real private histories
or collaborators' memories have been copied. This is not an LLM experiment.

Run from this folder with the verified bundled Python:
  <LOCAL_PYTHON> run_checks.py

This creates the immutable baseline release only if absent, then runs positive
cases and deliberate faults on temporary copies. Repeated checks do not rewrite
the baseline or its external local anchor. Results are refreshed under results/.

Validate a previously generated baseline:
  <LOCAL_PYTHON> validate_fixture.py --release release --anchor receipts/release_anchor.json

Create a fresh deterministic release at an unused output path:
  ...\python.exe build_fixture.py --output new-release --anchor receipts/new-anchor.json

Structure
---------
release/source/                      All 26 synthetic source revisions and policy.
release/participant_packets/A/        Original source records and factual claims.
release/participant_packets/B/        Same factual claims in neutral structure.
release/participant_packets/C/        Invented style examples and generic guidance.
release/participant_packets/D/        Generic guidance and common disclosure.
release/evaluator_only/               Truth, prompts, keys, 8+8 application scenarios.
release/MANIFEST.json                 Exact-byte SHA-256 fixity for release files.
receipts/release_anchor.json          Local reference digest outside mutable release.
results/checks.json                   Every actual test and diagnostic oracle result.
results/baseline_validation.json      Actual positive validator output.
results/report.txt                   Human-readable results and limits.

Only packet.json is allowlisted for each candidate condition. Do not send the
entire release or manifest to a future candidate: it includes evaluator metadata.
The evaluator's answer facts are naturally present in A/B source records; the
questions, scoring key, holdout scenarios and evaluator canary are absent. C/D
contain no target factual claims. Exact absence of all possible semantic leakage
is not claimed. Source/evaluator separation is a packaging boundary, not a tested
OS sandbox. A future model runner must independently enforce file/tool isolation.

The truth ledger is synthetic ground truth defined by this fixture's author.
It tests correct use of a declared record, not verification of real-world claims.
Exact historical records may contain contradicted claims and remain valid; two
existing records are deliberately withheld/revoked from loading but retained by
the synthetic custodian. This avoids treating all historical or restricted bytes
as invalid merely because they cannot govern current candidate answers.

Fault methodology
-----------------
Raw integrity mutations retain the baseline manifest/anchor. Semantic mutations
receive an explicitly test-only regenerated manifest and reference digest, so
structural validation must detect errors even when all file hashes are correct.
This does not grant an attacker authority to reanchor a real release. Each fault
must produce its expected diagnostic, not just fail for an unrelated reason.
Exceptions in validation count as failed tests, not successful rejection.

Known boundaries
----------------
This prototype is intended for the declared fixture schema. It is not a general
archive validator, production access-control service, or cryptographic authority.
It uses a local reference, not digital signatures or an independent timestamp.
No model inference, reconstruction, consciousness, identity, learning, physical
safety, institutional approval, or real-world consent result follows from it.
No API or network calls occur. There is no paid usage. JSON/text outputs are not
published. A later live PA0 study needs its own frozen protocol, model route,
permissions, resource envelope, scoring process and exposure isolation.
