# First Leaf public-packet oracle baseline (task firstleaf-oracle-001)

Private computational research on models only; not a hosted-model evaluation, safety
certification, hardware recommendation or public release.  Simulator, gateway, relay and
protocol are Lilitari's work in The Stage package (MIT, Copyright (c) 2026 Richard
Pemberton and contributors, to the extent of rights held); founding work Andrei with Red,
research expansion Grok Bot, companion review Coda.  The oracle-baseline files
(`oracle/`, this document, `tests/test_oracle.py`) are new work for the task under the same
licence.  Everything here was written statically; results must come from execution.

## Files

| file | role |
|---|---|
| `oracle/first_leaf_oracle.py` | agent: deduplicated evidence log, per-regime Gaussian posteriors, bounded-error + GLR change detection, regime bank, IG probing, rollout controller; `RandomAgent`, `ConstantAgent` |
| `oracle/fl_local_sim.py` | stdlib test double of relay.py's packet/event schema (labelled replica; parity-tested) |
| `oracle/fl_harness.py` | operator harness: relay.py via subprocess or in-process in a temp dir, or the test double; truth read operator-side only |
| `oracle/fl_scoring.py` | metrics (mirrors `first_leaf.episode_metrics`), phases, paired bootstrap, normalised regret, report |
| `tests/test_oracle.py` | unit + integration tests; package-dependent tests skip without `src/` and `inputs/` |

## Running (from the package root)

