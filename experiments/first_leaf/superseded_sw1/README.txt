FIRST LEAF FL0-SW1

This is an actually executable, standard-library-only Python software benchmark
for The Stage. It is not an experiment on a language model, consciousness,
personal continuity, welfare, or physical embodiment.

What it tests
  - A deterministic symbolic sensor/action loop with requested, admitted,
    executed, and observed events separately recorded.
  - Mapping recovery from action/outcome evidence.
  - Exact equality of a deterministic active and replay mapping learner when
    their sufficient evidence is identical, despite different replay requests.
  - Exposure-count and information ablations, a deliberately incorrect
    request-as-execution learner, and oracle/random controls.
  - Nontrivial prescribed prediction probes and a later live free-action task.
  - Functional command rejection, stop, provenance, and replay invariants.

What it does not test
  - Any LLM, subjective embodiment, consent, personal memory or identity.
  - Noisy vision, microphone input, network timing, adversarial isolation,
    real hardware stopping, or tissue.
  - Arbitrary learning algorithms: the main learner has an explicit prior that
    opaque labels bijectively map to four cardinal directions.

The post-exposure predictor is deliberately frozen during primary evaluation
and the secondary control task. Observed test feedback is logged, not learned.
This isolates information acquired during exposure; it is a declared software
adaptation of the FL0 companion, not a claim to have run an LLM protocol.

Run once, in order:
  python first_leaf.py prepare
  python first_leaf.py run
  python first_leaf.py verify

Verified local interpreter for this task:
<LOCAL_PYTHON>

Prepare freezes code/configuration/evaluator-key hashes and records the local
clock before execution. No independent timestamp authority is used. Run refuses
to overwrite prior results. Verify checks the manifest and recomputes everything
in memory, comparing exact results, CSV, action traces and fault checks.

16 development seeds and 64 disjoint test seeds are fixed workload budgets.
There is no tuning between these splits in this run. Seeds range over at most
24 mappings and are not distinct human or model subjects. Report seed-level
summaries; do not treat repeated actions as independent subjects.

Artifacts
  frozen/config.json              Fixed scientific and implementation choices.
  frozen/evaluator_key.json       Harness-only ground truth by API convention.
  frozen/freeze_receipt.json      Hashes and local before-run clock.
  results/report.txt             Human-readable actual results and limitations.
  results/results.json           Condition summaries and paired checks.
  results/per_seed.csv           One row per seed and condition.
  results/traces.jsonl           Full exposure, learning state, probes and actions.
  results/fault_checks.json      Executed negative/fault checks and evidence.
  results/execution_receipt.json Runtime, timestamps, exact output hashes.
  results/verification_receipt.json Exact deterministic recomputation result.
  manifest-sha256.txt            SHA-256 for every retained file except itself.

All artifact writes stay beneath this folder. The script uses no APIs, network,
external messages, package installs, Git operations, or publication facilities.
The evaluator key is not cryptographically or process-isolated from the learner;
the harness follows a narrow function interface. Do not represent it as a secure
agent sandbox.
