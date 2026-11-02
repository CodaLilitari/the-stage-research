# Process notes — how the run was operated

## Mechanics
- **Requests.** Every request went through the Claude Message Batches API at batch pricing, with
  `thinking: adaptive`, `effort: max`, `max_tokens: 128000` and `service_tier: standard_only`. The request shape is
  the one Coda's admitted waves used.
- **Packets.** Each request was a self-contained text packet with four parts: a common header (working conditions,
  standard-library code conventions, a `FILE: <path>` convention for mechanical extraction, and an output-budget
  instruction); the task statement; the verbatim sources with SHA-256 hashes; and receipts of earlier executions.
  The statements and source hashes are in `provenance/requests/`.
- **Execution.** Models had no tools. Red extracted every returned file and ran it in an isolated Linux sandbox
  (Python 3.13, standard library only). Results went back to the next wave as receipts. No returned code was run
  on a personal computer.
- **Model choice and refusals.** Claude Fable 5.1 was the primary model. When it refused, the identical request was
  sent once to Claude Opus 5.5 with a one-line fallback note. If Opus also refused, the line was closed. Requests
  were never reworded to get past a refusal.
- **Budget control.** A local runner reserved worst-case cost before every submission (input bound plus the full
  128,000 output tokens) against a cap, and settled actual usage on collection. The API key was held encrypted by the
  operating system on the project director's computer and decrypted only into the runner's memory. It never passed
  through any model, packet or file in this update.

## Cost by batch (USD at batch pricing; identifiers removed)
| batch | requests | complete | refused | max_tokens | other | input tok | output tok | model | USD |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Coda waves 1-5 (carry-forward) | 12 | | | | | | | | 18.80 |
| wave6-engineering | 4 | 2 | 0 | 2 | 0 | 127,737 | 435,222 | fable-5-1 | 11.52 |
| wave7-red-broad | 14 | 2 | 0 | 12 | 0 | 298,394 | 1,775,790 | fable-5-1 | 45.89 |
| wave8-opus-fallback-a | 3 | 0 | 3 | 0 | 0 | 23,868 | 34,891 | opus-5-5 | 0.40 |
| wave9-followups-a | 5 | 4 | 1 | 0 | 0 | 165,233 | 353,527 | fable-5-1 | 9.66 |
| wave10-resends | 13 | 11 | 0 | 2 | 0 | 303,781 | 1,264,264 | fable-5-1, opus-5-5 | 31.15 |
| wave11-followups-b | 5 | 4 | 1 | 0 | 0 | 326,286 | 244,245 | fable-5-1 | 7.74 |
| wave12a-fallbacks | 3 | 1 | 1 | 1 | 0 | 129,922 | 243,372 | fable-5-1, opus-5-5 | 4.61 |
| wave12b-followups-c | 8 | 8 | 0 | 0 | 0 | 381,075 | 702,271 | fable-5-1 | 19.46 |
| **total settled** | | | | | | | | | **149.23** |

Wave 13 was in progress at publication and is not included.

## Lessons with numbers
- **Reasoning can consume the whole budget.** Before an explicit output-budget instruction, 12 of 14 maximum-effort
  requests in wave 7 spent all 128,000 output tokens on reasoning and returned partial or empty deliverables
  (USD 45.89 for two complete answers). After the instruction was added, wave 12b returned 8 of 8 complete answers
  for USD 19.46.
- **Partial answers are recoverable.** A continuation request ("deliver only what is missing") plus mechanical
  splicing recovered four truncated code deliverables: the finite-volume model, the radiation model, the oracle
  agent and the metamorphic suite. Splices are recorded in the provenance map.
- **Specifications must travel with every request.** The one cross-model disagreement (F2) came from a request
  that omitted a contract value. The receiving author labelled its assumption correctly, so the error was findable.
- **Layout errors imitate defects.** Three apparent failures disappeared when the code was run in its documented
  layout: missing frozen modules, the wrong test-module path, and a missing reduced-oracle tree. Each was re-run
  before being reported.
- **Run first, judge second.** All seven First Leaf simulator defects claimed in a static audit were confirmed by
  execution before any repair was accepted. Conversely, a reviewer's own new identity test failed twice when
  executed. Reviews are run, not only read.
