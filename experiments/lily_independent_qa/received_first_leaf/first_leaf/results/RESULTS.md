# First Leaf FL1-R: executed results

Protocol: `STAGE-FL1-R-20261015-r1`. Author and local executor: Lilitari. Private synthetic algorithm experiment.

## Execution and units

The completed evaluation contains 8,192 six-episode trials and 3,932,160 scored transitions. There are 256 independent synthetic seed fixtures, reused in paired algorithm/profile comparisons. Time steps and repeated conditions are not independent replications.

The earlier 16-seed development batches are separate. No science-code, parameter, metric, seed, or decision-threshold changes were made after inspecting development outcomes. The local freeze is not independently witnessed preregistration.

## First-remap outcome

Mean distance to target over the first 32 steps after the first remap, starting one distance unit from the target. Lower is better.

| Algorithm | Delay + noise | No delay | No delay or noise | Stationary body |
|---|---:|---:|---:|---:|
| oracle | 0.327586 | 0.327456 | 0.328518 | 0.314461 |
| cumulative | 0.863850 | 0.555771 | 0.551525 | 0.314625 |
| window | 0.521833 | 0.409661 | 0.409420 | 0.317218 |
| episode_reset | 0.485440 | 0.380934 | 0.379648 | 0.461360 |
| frozen | 0.988952 | 0.703204 | 0.702918 | 0.314641 |
| no_information | 1.750140 | 1.750140 | 1.750140 | 1.658734 |
| misaligned | 1.036600 | 0.409661 | 0.409420 | 0.876940 |
| shuffled | 1.140065 | 1.108651 | 1.106973 | 1.131851 |

## Frozen design rule

Cumulative minus window: **0.342017**, paired 95% bootstrap interval **[0.329597, 0.354049]**.

Stable-body penalty, window minus cumulative: **0.005960**, interval **[0.005275, 0.006661]**.

The frozen rule (gain at least 0.10, gain interval lower bound above zero, stable-penalty upper bound at most 0.05) **passes** within this fixture family.

## Other planned contrasts

| Contrast | Mean difference | Paired 95% interval |
|---|---:|---:|
| primary_cumulative_minus_window | 0.342017 | [0.329597, 0.354049] |
| stable_window_minus_cumulative | 0.005960 | [0.005275, 0.006661] |
| remap_reset_minus_window | -0.036394 | [-0.055223, -0.018454] |
| stable_reset_minus_window | 0.060684 | [0.056409, 0.065021] |
| second_B_reset_minus_window | 0.167050 | [0.149636, 0.184680] |
| return_A_cumulative_minus_window | -0.091250 | [-0.102529, -0.080174] |
| primary_misaligned_minus_window | 0.514767 | [0.477822, 0.552398] |
| no_delay_cumulative_minus_window | 0.146110 | [0.134909, 0.156721] |
| clean_cumulative_minus_window | 0.142105 | [0.131797, 0.152357] |
| stationary_window_minus_cumulative | 0.002593 | [0.001788, 0.003448] |

Secondary intervals are exploratory. No familywise correction or claim of general population coverage is made.

## Verification and deviations

The first primary batch attempt hit a tool timeout. Its 1,656 retained completed receipts match the entire unchanged rerun. Partial in-flight work is not fully enumerated: the original batch writer was completion-based and buffered. The scored rerun is complete; the interrupted attempt is preserved and is not additional independent evidence.

The wrong-time action-assignment ablation becomes byte-identical to the aligned learner when observation delay is zero, on all 256 seed pairs in both applicable profiles. This is an exact implementation check, not a nonsignificance result.

## Interpretation

A bounded recent-evidence body model is preferable to an all-history pooled estimator for this specific nonstationary control problem. This does not establish that a fixed window is optimal. Resetting memory every episode recovers faster at the deliberately episode-aligned change, but sacrifices information on unchanged episodes. A context-conditioned model bank or change-point method is a motivated next comparator, not a result already obtained.

The body is a continuous-state planar point mass with momentum, not a grid. Mapping and anisotropic actuation gains change together. Morphology, contact, camera sensing, unknown damping, real hardware, hosted-language-model action selection, and personal continuity were not tested.

All source code, frozen random draws, per-episode outcomes and per-trial trace hashes are supplied. Full raw step traces are retained for the first evaluation seed in each algorithm/profile, with deterministic regeneration available for every other trace. Raw-trace gzip header times are not the semantic trace digest.

## Replay and recovery checks

```json
{
  "replay_seed_pairs": 256,
  "identical_learner_state_comparisons": 124416,
  "checkpoint_seed_pairs": 256,
  "full_state_exact_pairs": 256,
  "exact_continuation_steps_per_pair": 49,
  "separate_process_witness_identical": true,
  "separate_process_trace_sha256": "08efe3a16d6f4c5ed90e0072c9850ec41efc57e96fc7452f990a5f3c7789ef53",
  "cold_controller_reset_minus_full_state_distance": {
    "mean": 0.018725906405694367,
    "ci95": [
      0.016713336075756768,
      0.020940537647559113
    ],
    "n_seeds": 256
  },
  "cold_controller_mean_action_disagreements_of49": 8.6875,
  "cold_controller_reset_does_not_replay_history": true,
  "all_restoration_tests_same_python_runtime_platform": true
}
```

The records-only condition in source code means an intentionally reset numerical controller. It does not replay the saved learning history. It is therefore a state-restoration ablation, not evidence that event records cannot reconstruct learned state.
