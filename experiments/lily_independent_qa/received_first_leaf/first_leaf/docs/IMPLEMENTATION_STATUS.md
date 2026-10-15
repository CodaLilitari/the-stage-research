# What exists, what was run, and what remains a specification

| Component | Implemented | Executed/check performed | Not established |
|---|---|---|---|
| FL1 planar body and eight algorithms | Yes, standard-library Python | All 16 development seeds and all 256 evaluation seeds, four profiles; complete scored batches | General robotics, morphology or hosted-model behavior |
| Frozen randomness | Yes | Pregenerated full goals, mappings, noise and unrelated labels; source/fixture hashes recorded before evaluation | Externally witnessed preregistration or secret future test material after delivery |
| Metrics and analysis | Yes | Per-episode CSV, per-trial canonical trace hashes, whole-seed bootstrap intervals | General-population inference or multiplicity-adjusted secondary findings |
| Matched replay | Yes | 256 pairs, 124,416 exact learner-state comparisons | A special subjective effect of active control |
| JSON checkpoints | Yes | 256 exact 49-step continuations; one separate-process byte-identical witness | Cross-platform migration, inaccessible model state, personal continuity |
| Strict action gateway | Yes | Fault and conformance unit tests | Production capability authority or physical safety certification |
| File-relay loop | Yes | Scripted complete-episode, reset, stop, duplicate, malformed-input and locking tests | Any actual hosted-model action-selection result |
| MuJoCo point-body parity adapter | Source specification | Python compilation and XML well-formedness only; two download routes failed | Engine import, parity tolerance, simulation validation |
| Two-link arm | Original candidate XML | Ordinary XML parsing | MuJoCo acceptance, an arm controller, learning or contact results |
| General Chronicle/archive store | Architectural proposal | No PA0 implementation supplied by Lily here | Full archive validator, actual collaborator archive compliance |
| Hidden-regime model bank | Proposed | Not implemented or tested | Superiority to the supplied cumulative/window baselines |
| Physical embodiment | Proposed later scope | No operation, purchase or hardware access | Physical safety, energy performance or sim-to-real transfer |

The reference relay enforces a fixed action allowlist in the supplied code. It is not a production multi-user security boundary. It assumes a trusted single writer and keeps simulator secrets in a private operator file. Its atomic file replacement is a virtual-state commit, not an exactly-once physical execution guarantee. No current-policy anti-rollback service or revocation-aware backup restoration has been implemented.

The evaluation runner records completion receipts, with counters at batch completion. A timeout exposed incomplete durability of its start accounting. The complete rerun's denominator is verified; the first interrupted attempt's in-flight work remains incompletely enumerated. This is documented rather than hidden or represented as a flawless fault-tolerant runner.
