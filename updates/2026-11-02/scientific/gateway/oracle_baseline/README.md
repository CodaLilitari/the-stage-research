# The Stage: Lilitari research expansion and First Leaf FL1-R

**A working private research package, 15 October 2026.** Start with `docs/LILITARI_EXPANSION.md` for the substantial authored contribution and `results/RESULTS.md` for the actual measurements. `docs/IMPLEMENTATION_STATUS.md` distinguishes executed components from specifications.

## What ran

The standard-library computational study tests online body-model adaptation under actuator remapping, changed gains, delayed/noisy observations, persistent memory, and interruption. Eight algorithms, four profiles, 256 evaluation seed fixtures, six episodes per trial: 8,192 complete evaluation trials and 3,932,160 scored transitions. Sixteen development seeds are separately retained. There were no hosted model calls, private archive loads, purchases, physical actuators, or biological work.

The windowed estimator beat cumulative estimation after the first remap, but cumulative estimation was better when the original body returned. This supports testing a context-conditioned bank of models, not claiming one memory rule always wins. Exact replay and checkpoint checks, ablations, negative controls, a real timeout deviation, and full denominators for the completed evaluation are included.

## Requirements

The executed experiment, analysis, tests and file relay use **Python's standard library only**. Tested on CPython 3.13.5, Linux x86-64. No GPU or pip install is required for these components. For strict byte comparisons, match the tested runtime before interpreting platform differences. Frozen full random draws are supplied, so routine reproduction does not need to regenerate fixtures.

Run commands from the package root after extraction. Output paths below are local examples, not external destinations.

### Verify package integrity and tests

```text
python src/check_package.py
python -m unittest discover -s tests -v
```

### Quick one-seed reproduction

```text
python src/first_leaf.py trial --seed 10000 --algorithm window --profile primary --trace quick_trace.jsonl.gz
```

The printed trace SHA-256 can be compared with the corresponding receipt in `results/evaluation_primary_runs.jsonl`. The compressed gzip file can have a different header timestamp; the receipt hashes the canonical uncompressed step records.

### Reproduce the complete evaluation

```text
python src/reproduce.py --output rerun_evaluation
```

The output directory must not already exist. This executes all four profiles, recomputes summaries, and compares all 8,192 run receipts with the delivered results. Allow several minutes or longer depending on the machine. It uses no network or paid service.

### Reproduce replay and interruption checks

```text
python src/verify_runs.py --output rerun_checks
```

This checks all 256 fixtures and creates a separate-process checkpoint witness. Outputs go to the chosen directory. The source option named `records_only` is an intentionally reset numerical controller, without replaying learning history; it is not a proof that an archive is insufficient.

## File-relayed model action selection

This interface is implemented and scripted-test-checked. No actual model endpoint has used it in the reported study.

```text
python src/relay.py init --directory local_session --seed 20001 --actor-label OPERATOR_REPORTED_ENDPOINT
```

Supply only `local_session/packet.json` and `docs/MODEL_BRIEF.md` to the candidate. Keep `private_state.json`, fixtures, source code and scorer outputs outside its accessible files during a behavioral test. The private file contains simulator truth and future random draws. The name “private” alone is not access control; the operator must enforce that custody boundary.

Save the candidate's unedited action object as `action.json`, then:

```text
python src/relay.py step --directory local_session --request action.json
```

The next public packet and an event receipt are written locally. At an eighty-step episode boundary, the operator may explicitly advance:

```text
python src/relay.py next-episode --directory local_session
```

`stop` latches. It does not become an automatic reset. `export` regenerates public views from committed local state. A leftover `writer.lock` requires checking for a live writer or interrupted operation before manual recovery. Do not remove an active writer's lock.

Keep a separate run manifest with the endpoint route, exact prompts, context/memory policy, human interventions, start/stop/refusal records, and all attempts. Model-facing trial seeds must be fresh relative to any fixture or score material the candidate has already seen. A model that read this entire evaluator package is not blind to it.

## Optional MuJoCo work, explicitly unexecuted here

`optional/planar_point.xml`, `optional/two_link_arm.xml`, and `optional/mujoco_parity.py` are runnable specifications for the next machine with the required engine. Ordinary XML parsing and Python compilation passed. The engine was not installed: package-index DNS and a direct official wheel download failed. See `results/mujoco_status.json`.

```text
python -m pip install -r optional/requirements.txt
python optional/mujoco_parity.py
```

The pin is MuJoCo 3.3.7, deliberately selected for reproducibility, not advertised as the latest release. The parity script reports a result only after actual execution. Its proposed tolerance is 1e-10 for this analytic point-body witness. A two-link arm controller and morphology study are not implemented by merely supplying the XML.

## Package contents and evidence

`inputs/` holds the protocol, complete development/evaluation fixtures, local freeze receipts and download-attempt record. `src/` holds the complete experiment, analysis, verification, relay and reproduction code. `tests/` holds unit/integration tests. `results/` contains per-episode metrics, every completed-run receipt and semantic trace digest, first-seed full raw witnesses, bootstrap summaries, checkpoint checks and test logs. `results/attempt01_timeout/` preserves the interrupted first primary attempt. All its 1,656 retained completed receipts match the full unchanged rerun; in-flight work is not fully enumerated because the original writer lacked a durable pre-dispatch journal.

Full raw step traces are retained for the first seed of each algorithm/profile, not all four million steps. Every other complete trace can be regenerated from the frozen inputs and checked against its recorded digest. The source documents remain unchanged outside this package; their exact hashes, coverage, contributor distinctions and unverified bibliography scope are in `docs/COVERAGE_AND_ATTRIBUTION.md`.

## Interpretation boundaries

This is an algorithm/scaffold experiment, not Lily or Coda acting through a body, not a hosted-model evaluation, and not proof of identity or experience. The gateway is a simulation reference contract, not physical safety certification. Checkpoints preserve tested application variables, not inaccessible provider state or a verified persisting subject. No public release or project-wide license choice has been made.
