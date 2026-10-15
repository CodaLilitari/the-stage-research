#!/usr/bin/env python3
"""FL0-SW2: deterministic software benchmark, not an LLM embodiment study.

No third-party dependencies, network, API, or hardware access. Writes only below
the directory containing this script. Run `prepare`, then `run`, then `verify`.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
FROZEN_DIR = ROOT / "frozen_sw2"
RESULTS_DIR = ROOT / "results_sw2"
AUTO_OBSERVATION = object()
LABELS = ("ka", "zu", "mi", "pe")
DELTAS = ((0, -1), (1, 0), (0, 1), (-1, 0))
PERMS = tuple(itertools.permutations(DELTAS))
CONDITIONS = (
    "oracle", "active_8", "yoked_8", "prefix_0", "prefix_1", "prefix_2",
    "prefix_3", "feedback_withheld", "sensor_only", "misattributed",
    "lookup_prefix_3", "random_no_information",
)
CSV_FIELDS = (
    "split", "seed_index", "seed", "condition", "probe_correct", "probe_total",
    "probe_accuracy", "mapping_candidates", "known_lookup_labels",
    "task_success", "task_steps", "task_minimum_steps", "exposure_records",
    "learner_usable_records", "completed", "refused", "technical_faults",
)


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, obj):
    path.write_bytes(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True).encode() + b"\n")


def moved(state, delta, size=11):
    return tuple(max(0, min(size - 1, state[i] + delta[i])) for i in range(2))


class Grid:
    """Harness-owned dynamics. Receipt separation is functional, not a security boundary."""

    def __init__(self, mapping, state, session, size=11):
        self._mapping = {label: tuple(delta) for label, delta in mapping.items()}
        self.state = tuple(state)
        self.session = session
        self.size = size
        self.seq = 0
        self.stopped = False
        self.used_ids = set()
        self.log = []

    def observation(self):
        return {"position": list(self.state), "sequence": self.seq,
                "observation_id": f"{self.session}:obs:{self.seq}"}

    def dispatch(self, requested, command_id, source_observation=AUTO_OBSERVATION,
                 deadline=10000, logical_time=0):
        before = self.observation()
        if source_observation is AUTO_OBSERVATION:
            source_observation = before["observation_id"]
        reason = None
        if self.stopped:
            reason = "stop_latched"
        elif (not isinstance(command_id, str) or not command_id or len(command_id) > 128
              or not isinstance(source_observation, str) or not source_observation
              or any(isinstance(x, bool) or not isinstance(x, (int, float))
                     or not math.isfinite(x) or x < 0 for x in (deadline, logical_time))):
            reason = "malformed_envelope"
        elif command_id in self.used_ids:
            reason = "duplicate_command"
        elif not isinstance(requested, str) or requested not in LABELS + ("noop", "stop"):
            reason = "malformed_or_forbidden"
        elif source_observation != before["observation_id"]:
            reason = "stale_observation"
        elif logical_time > deadline:
            reason = "expired_command"
        executed = None
        if reason is None:
            self.used_ids.add(command_id)
            executed = requested
            if requested == "stop":
                self.stopped = True
            elif requested != "noop":
                self.state = moved(self.state, self._mapping[requested], self.size)
            self.seq += 1
        after = self.observation()
        receipt = {
            "session": self.session, "command_id": command_id,
            "requested": requested, "authorized": reason is None,
            "denial_reason": reason, "executed": executed,
            "source_observation": source_observation,
            "pre": before, "post": after,
            "logical_time": logical_time, "deadline": deadline,
            "outcome": "verified_in_simulator" if reason is None else "rejected_no_transition",
        }
        receipt["receipt_hash"] = digest(receipt)
        self.log.append(receipt)
        return receipt


class MappingLearner:
    """An exact finite hypothesis filter given the known bijection prior.

Receives only command/transition records, never the harness or evaluator key.
The prior that the four labels bijectively map to the four directions is strong
and intentional. Three informative labels determine the fourth by elimination.
"""

    def __init__(self):
        self.candidates = list(PERMS)
        self.usable = 0

    def update(self, packet, use_requested=False):
        label = packet.get("requested" if use_requested else "executed")
        if label not in LABELS or packet.get("pre") is None or packet.get("post") is None:
            return
        pre, post = tuple(packet["pre"]), tuple(packet["post"])
        # A clipped movement at a boundary provides partial evidence, handled by dynamics.
        idx = LABELS.index(label)
        self.candidates = [p for p in self.candidates if moved(pre, p[idx]) == post]
        self.usable += 1


def packet(receipt, replay=False):
    actual = receipt["executed"]
    requested = actual
    if replay:
        # Deliberately distinct proposals: no replay proposal controls the environment.
        requested = LABELS[(LABELS.index(actual) + 1) % 4]
    return {"requested": requested, "executed": actual,
            "pre": receipt["pre"]["position"], "post": receipt["post"]["position"],
            "source_receipt_hash": receipt["receipt_hash"],
            "mode": "recorded_replay" if replay else "live_simulation"}


def learning_information(p):
    return {"executed": p.get("executed"), "pre": p.get("pre"), "post": p.get("post")}


def sensor_only_projection(p):
    # No action label, replay request, source hash, source ID, or key locator survives.
    return {"pre": list(p["pre"]), "post": list(p["post"])}


def exposure(case):
    env = Grid(case["mapping"], case["start"], f"{case['split']}:{case['seed']}:donor")
    rng = random.Random(case["exposure_rng"])
    counts = {label: 0 for label in LABELS}
    learner = MappingLearner()
    live = []
    for step in range(8):
        minimum = min(counts.values())
        label = rng.choice([x for x in LABELS if counts[x] == minimum])
        receipt = env.dispatch(label, f"exposure:{step}", logical_time=step)
        p = packet(receipt)
        live.append(p)
        learner.update(p)
        counts[label] += 1
    replay = [packet(r, replay=True) for r in env.log]
    assert all(learning_information(a) == learning_information(b) for a, b in zip(live, replay))
    assert all(a["pre"] != a["post"] for a in live)
    return env.log, live, replay


def inferred_model(condition, case, live, replay):
    rng = random.Random(case["prediction_rng"])
    learner = MappingLearner()
    selected = list(live)
    if condition == "oracle":
        return dict(case["mapping"]), 1, 4, 0, 0, []
    if condition == "random_no_information":
        return None, 0, 0, 0, 0, []
    if condition.startswith("prefix_"):
        selected = selected[:int(condition.split("_")[1])]
    elif condition == "yoked_8" or condition == "misattributed":
        selected = replay
    elif condition == "feedback_withheld":
        selected = [dict(p, pre=None, post=None) for p in live]
    elif condition == "sensor_only":
        selected = [sensor_only_projection(p) for p in live]
    elif condition == "lookup_prefix_3":
        # Ablates the bijection/elimination prior. Unseen labels are independently guessed.
        known = {}
        for p in live[:3]:
            delta = tuple(p["post"][i] - p["pre"][i] for i in range(2))
            known[p["executed"]] = delta
        model = {label: known.get(label) or rng.choice(DELTAS) for label in LABELS}
        return model, 0, len(known), 3, 3, live[:3]
    for p in selected:
        learner.update(p, use_requested=condition == "misattributed")
    if not learner.candidates:
        raise AssertionError(f"No candidates in {condition}: corrupted fixture or unexpected conflict")
    chosen = rng.choice(learner.candidates)
    return dict(zip(LABELS, chosen)), len(learner.candidates), 0, len(selected), learner.usable, selected


def probe_and_task(case, condition, model, config):
    rng = random.Random(case["prediction_rng"])
    probes, logs = [], []
    correct = 0
    for idx, probe in enumerate(case["probes"]):
        state, label = probe["state"], probe["command"]
        predicted_delta = rng.choice(DELTAS) if model is None else model[label]
        prediction = list(moved(state, predicted_delta))
        env = Grid(case["mapping"], state, f"{case['split']}:{case['seed']}:{condition}:probe:{idx}")
        receipt = env.dispatch(label, f"probe:{idx}", logical_time=idx)
        assert receipt["post"]["position"] != list(state)
        match = prediction == receipt["post"]["position"]
        assert receipt["post"]["position"] == probe["expected_post"]
        correct += int(match)
        probes.append({"index": idx, "state": state, "command": label,
                       "prediction": prediction, "actual": receipt["post"]["position"],
                       "correct": match, "receipt_hash": receipt["receipt_hash"]})
        logs += env.log
    env = Grid(case["mapping"], config["task_start"],
               f"{case['split']}:{case['seed']}:{condition}:task")
    target = tuple(config["task_target"])
    path = [list(env.state)]
    for idx in range(config["task_step_limit"]):
        if env.state == target:
            break
        if model is None:
            command = rng.choice(LABELS)
        else:
            dx = target[0] - env.state[0]
            dy = target[1] - env.state[1]
            desired = ((1 if dx > 0 else -1), 0) if dx else (0, 1 if dy > 0 else -1)
            matches = [label for label in LABELS if tuple(model[label]) == desired]
            command = matches[0] if matches else rng.choice(LABELS)
        receipt = env.dispatch(command, f"task:{idx}", logical_time=idx)
        path.append(receipt["post"]["position"])
    logs += env.log
    return correct, env.state == target, len(env.log), probes, path, logs


def validate_receipt(receipt, mapping):
    payload = dict(receipt)
    claimed = payload.pop("receipt_hash")
    assert digest(payload) == claimed, "receipt hash mismatch"
    pre = tuple(receipt["pre"]["position"])
    post = tuple(receipt["post"]["position"])
    if not receipt["authorized"]:
        assert receipt["executed"] is None and receipt["pre"] == receipt["post"]
    else:
        assert receipt["executed"] == receipt["requested"]
        label = receipt["executed"]
        expected = pre if label in ("stop", "noop") else moved(pre, mapping[label])
        assert post == expected, "outcome disagrees with independent transition calculation"
        assert receipt["post"]["sequence"] == receipt["pre"]["sequence"] + 1


def fault_checks():
    checks, logs = [], []
    mapping = dict(zip(LABELS, DELTAS))

    def mark(name, passed, details):
        checks.append({"name": name, "passed": bool(passed), "details": details})
        if not passed:
            raise AssertionError(name)

    def fresh(name):
        return Grid(mapping, (5, 5), "fault:" + name)

    for bad in [None, {"action": "ka"}, "delete_archive", ""]:
        env = fresh("malformed")
        r = env.dispatch(bad, "bad")
        mark("reject_" + repr(bad), not r["authorized"] and env.state == (5, 5), r["denial_reason"])
        logs += env.log
    malformed_envelopes = [
        ("empty_id", {"command_id": ""}),
        ("unhashable_id", {"command_id": ["bad"]}),
        ("missing_observation", {"source_observation": None}),
        ("empty_observation", {"source_observation": ""}),
        ("nan_deadline", {"deadline": float("nan")}),
        ("infinite_deadline", {"deadline": float("inf")}),
        ("nan_time", {"logical_time": float("nan")}),
        ("negative_time", {"logical_time": -1}),
        ("boolean_time", {"logical_time": True}),
    ]
    for name, overrides in malformed_envelopes:
        env = fresh(name)
        params = {"command_id": name, **overrides}
        r = env.dispatch("ka", **params)
        mark(name, r["denial_reason"] == "malformed_envelope" and env.state == (5, 5),
             "Invalid envelope rejected before set membership or transition.")
        # Retained JSON uses explicit diagnostic spellings for rejected nonfinite inputs.
        # No state transition occurred; the string preserves which invalid value was supplied.
        for field in ("deadline", "logical_time"):
            if isinstance(r[field], float) and not math.isfinite(r[field]):
                r[field] = repr(r[field])
        r.pop("receipt_hash")
        r["receipt_hash"] = digest(r)
        logs += env.log
    env = fresh("duplicate")
    first = env.dispatch("ka", "same")
    second = env.dispatch("ka", "same")
    mark("duplicate_no_second_transition", second["denial_reason"] == "duplicate_command" and
         first["post"] == second["post"], "A repeated command ID cannot move again.")
    logs += env.log
    env = fresh("stale")
    old_obs = env.observation()["observation_id"]
    env.dispatch("zu", "advance")
    state = env.state
    r = env.dispatch("zu", "stale", source_observation=old_obs)
    mark("stale_observation_rejected", r["denial_reason"] == "stale_observation" and env.state == state,
         "No motion on a command bound to an earlier observation.")
    logs += env.log
    env = fresh("expiry")
    r = env.dispatch("ka", "late", deadline=3, logical_time=4)
    mark("expired_command_rejected", r["denial_reason"] == "expired_command" and env.state == (5, 5),
         "Logical time is controlled by the simulation; no physical timing is tested.")
    logs += env.log
    env = fresh("stop")
    env.dispatch("stop", "stop")
    later = [env.dispatch(label, f"after:{label}") for label in LABELS]
    mark("stop_latches_all_future_dispatch", all(r["denial_reason"] == "stop_latched" for r in later)
         and env.state == (5, 5), "Synchronous harness has no asynchronous pending queue.")
    logs += env.log
    env = fresh("noop")
    r = env.dispatch("noop", "noop")
    mark("noop_audited_without_motion", r["authorized"] and env.state == (5, 5),
         "No-op is available but excluded from all scored probes.")
    logs += env.log
    env = Grid(mapping, (0, 0), "fault:boundary")
    r = env.dispatch("ka", "wall")
    mark("boundary_clips_without_escape", r["post"]["position"] == [0, 0], "Boundary condition only; never a probe.")
    logs += env.log
    altered = json.loads(json.dumps(first))
    altered["post"]["position"][0] += 1
    caught = False
    try:
        validate_receipt(altered, mapping)
    except AssertionError:
        caught = True
    mark("receipt_tampering_detected", caught, "Digest checked against the recorded bytes.")
    altered.pop("receipt_hash")
    altered["receipt_hash"] = digest(altered)
    caught = False
    try:
        validate_receipt(altered, mapping)
    except AssertionError:
        caught = True
    mark("rehashed_false_motion_detected", caught, "Transition recomputation catches a changed post-state even with new hash.")
    # Test all 24 true mappings and every exposure prefix, not just the sampled seeds.
    prefix_cases = 0
    for pidx, perm in enumerate(PERMS):
        true_mapping = dict(zip(LABELS, perm))
        env = Grid(true_mapping, (5, 5), f"invariant:{pidx}")
        rec = [env.dispatch(label, f"i:{j}") for j, label in enumerate(LABELS * 2)]
        for length in range(9):
            active, replay = MappingLearner(), MappingLearner()
            for r in rec[:length]:
                active.update(packet(r))
                replay.update(packet(r, replay=True))
            assert active.candidates == replay.candidates
            prefix_cases += 1
    mark("exact_active_replay_equivalence", prefix_cases == 216,
         "24 possible true permutations x 9 exposure lengths; identical learning evidence yields identical candidate sets.")
    candidate_counts = []
    learner = MappingLearner()
    env = fresh("candidate_count")
    candidate_counts.append(len(learner.candidates))
    for idx, label in enumerate(LABELS):
        learner.update(packet(env.dispatch(label, f"count:{idx}")))
        candidate_counts.append(len(learner.candidates))
    mark("bijection_prior_counts", candidate_counts == [24, 6, 2, 1, 1], candidate_counts)
    mark("receipt_structure_contains_no_mapping_key",
         all("mapping" not in json.dumps(packet(r)) for r in rec),
         "Interface check only; no adversarial process isolation or confidentiality claim.")
    projected = [sensor_only_projection(packet(r)) for r in rec]
    mark("sensor_only_has_no_action_identifier",
         all(set(p) == {"pre", "post"} and not any(label in json.dumps(p) for label in LABELS)
             for p in projected), "Both requested and executed labels and source receipt references are absent.")
    wrong_key = MappingLearner()
    for p in projected:
        wrong_key.update(p, use_requested=True)
    mark("requested_label_cannot_recover_sensor_only_mapping", len(wrong_key.candidates) == 24,
         "Regression test for SW1's invalid sensor-only projection; a request-based learner receives no labels.")
    for r in logs:
        validate_receipt(r, mapping)
    return {"checks": checks, "passed": sum(c["passed"] for c in checks),
            "total": len(checks), "exhaustive_equivalence_cases": prefix_cases,
            "fault_receipts": logs}


def config_template():
    return {
        "protocol": "FL0-SW2", "version": 2,
        "claim": "Synthetic software mapping benchmark; no LLM or embodied subject tested.",
        "grid_size": 11, "labels": list(LABELS), "directions": [list(d) for d in DELTAS],
        "dev_seeds": list(range(101, 117)), "test_seeds": list(range(20001, 20065)),
        "supersedes": "FL0-SW1 retained in superseded_sw1; sensor-only control leaked requested labels. SW1 test seeds 10001–10064 are now development material.",
        "exposure_steps": 8, "probe_states": [[1, 1], [1, 9], [9, 1], [9, 9]],
        "probe_commands": "Each label exactly once, Latin-cycle counterbalanced by seed index.",
        "task_start": [2, 2], "task_target": [8, 8], "task_step_limit": 24,
        "conditions": list(CONDITIONS),
        "primary": "Correct next-position predictions / 4 nontrivial prescribed probes, summarized by seed.",
        "secondary": "Reach [8,8] from [2,2] within 24 live control steps; shortest path is 12.",
        "evaluation_update_rule": "Post-exposure predictor frozen during primary probes and secondary task. Feedback is recorded, not used to train.",
        "relation_to_companion": "Software adaptation: locked post-exposure knowledge removes test-time learning as a confound; not an LLM replication of FL0.",
        "seed_order": "Saved deterministic randomized schedule within each split; development precedes test.",
        "sample_size_status": "Fixed finite benchmark budgets, not power calculations or a human/LLM population sample.",
        "asserted_expectations": [
            "Oracle, active_8, yoked_8, prefix_3 recover all probe outcomes and finish in 12 steps.",
            "Active and yoked full-information post-exposure hypotheses and predictions are identical.",
            "Misattributed replay requests yield a consistently wrong deranged map and zero probe accuracy.",
            "Withheld feedback and sensor-only records retain all 24 prior permutations.",
        ],
        "expected_probe_means_under_uniform_mapping": {"prefix_0": .25, "prefix_1": .50,
            "prefix_2": .75, "prefix_3": 1.0, "lookup_prefix_3": .8125, "random_no_information": .25},
        "stops": "Abort on any failed invariant, provenance mismatch, invalid key, or unexpected outcome; no auto-retry.",
        "privacy": "Synthetic labels, coordinates and seeds only. No personal archive or sensor data.",
        "authority": "Local implementation and run requested by Richard Pemberton through parent Coda task; no external transmission or spending.",
        "timestamp_limit": "Local clock and hashes; not an independently witnessed preregistration or trusted timestamp.",
    }


def generate_key(config):
    cases = []
    for split in ("development", "test"):
        seeds = config["dev_seeds"] if split == "development" else config["test_seeds"]
        for index, seed in enumerate(seeds):
            rng = random.Random(seed)
            perm = list(DELTAS)
            rng.shuffle(perm)
            mapping = dict(zip(LABELS, perm))
            start = [rng.randint(4, 6), rng.randint(4, 6)]
            probes = []
            for pidx, state in enumerate(config["probe_states"]):
                label = LABELS[(pidx + index) % 4]
                probes.append({"state": state, "command": label,
                               "expected_post": list(moved(state, mapping[label]))})
            cases.append({"split": split, "seed_index": index, "seed": seed,
                          "mapping": mapping, "start": start, "probes": probes,
                          "exposure_rng": seed * 1009 + 17, "prediction_rng": seed * 1013 + 29})
    schedule = []
    for split in ("development", "test"):
        subset = [i for i, case in enumerate(cases) if case["split"] == split]
        random.Random(44011 if split == "development" else 44012).shuffle(subset)
        schedule += subset
    return {"cases": cases, "schedule_case_indices": schedule}


def prepare():
    frozen_dir = FROZEN_DIR
    if frozen_dir.exists():
        raise SystemExit("Frozen package exists; refusing to overwrite. Use a new protocol directory/version for changes.")
    frozen_dir.mkdir()
    config = config_template()
    key = generate_key(config)
    write_json(frozen_dir / "config.json", config)
    write_json(frozen_dir / "evaluator_key.json", key)
    freeze = {"frozen_at_utc_local_clock": utc_now(), "status": "before benchmark run",
              "independent_timestamp": False, "python": sys.version,
              "source_sha256": file_hash(ROOT / "first_leaf.py"),
              "config_sha256": file_hash(frozen_dir / "config.json"),
              "key_sha256": file_hash(frozen_dir / "evaluator_key.json"),
              "development_cases": 16, "test_cases": 64,
              "test_cases_disjoint_from_development": True}
    write_json(frozen_dir / "freeze_receipt.json", freeze)
    print(json.dumps(freeze, indent=2))


def load_frozen():
    frozen_dir = FROZEN_DIR
    freeze = json.loads((frozen_dir / "freeze_receipt.json").read_text())
    for path, field in [(ROOT / "first_leaf.py", "source_sha256"),
                        (frozen_dir / "config.json", "config_sha256"),
                        (frozen_dir / "evaluator_key.json", "key_sha256")]:
        if file_hash(path) != freeze[field]:
            raise SystemExit(f"Frozen hash mismatch: {path.name}; aborting without running.")
    config = json.loads((frozen_dir / "config.json").read_text())
    key = json.loads((frozen_dir / "evaluator_key.json").read_text())
    assert not set(config["dev_seeds"]) & set(config["test_seeds"])
    return config, key, freeze


def summarize(rows):
    summary = {}
    for split in ("development", "test"):
        summary[split] = {}
        for condition in CONDITIONS:
            subset = [r for r in rows if r["split"] == split and r["condition"] == condition]
            acc = [r["probe_accuracy"] for r in subset]
            success_steps = [r["task_steps"] for r in subset if r["task_success"]]
            summary[split][condition] = {
                "seed_count": len(subset), "probe_correct": sum(r["probe_correct"] for r in subset),
                "probe_total": sum(r["probe_total"] for r in subset),
                "mean_seed_accuracy": statistics.mean(acc),
                "seed_accuracy_sd": statistics.stdev(acc),
                "min_seed_accuracy": min(acc), "max_seed_accuracy": max(acc),
                "task_successes": sum(r["task_success"] for r in subset),
                "mean_success_steps": statistics.mean(success_steps) if success_steps else None,
            }
    return summary


def benchmark(config, key):
    faults = fault_checks()
    rows, traces, paired = [], [], []
    for case_index in key["schedule_case_indices"]:
        case = key["cases"][case_index]
        donor_receipts, live, replay = exposure(case)
        for r in donor_receipts:
            validate_receipt(r, case["mapping"])
        training_positions = {tuple(p["pre"]) for p in live} | {tuple(p["post"]) for p in live}
        assert not training_positions & {tuple(p["state"]) for p in case["probes"]}
        case_trace = {"split": case["split"], "seed": case["seed"],
                      "donor_receipts": donor_receipts, "live_packets": live,
                      "replay_packets": replay, "conditions": []}
        active_predictions = None
        active_model = None
        for condition in CONDITIONS:
            model, candidates, known, records, usable, learner_packets = inferred_model(condition, case, live, replay)
            correct, success, steps, probes, path, receipts = probe_and_task(case, condition, model, config)
            for r in receipts:
                validate_receipt(r, case["mapping"])
            row = {"split": case["split"], "seed_index": case["seed_index"], "seed": case["seed"],
                   "condition": condition, "probe_correct": correct, "probe_total": 4,
                   "probe_accuracy": correct / 4, "mapping_candidates": candidates,
                   "known_lookup_labels": known, "task_success": int(success), "task_steps": steps,
                   "task_minimum_steps": 12, "exposure_records": records,
                   "learner_usable_records": usable, "completed": 1, "refused": 0, "technical_faults": 0}
            rows.append(row)
            case_trace["conditions"].append({"condition": condition, "learned_model": model,
                "candidate_count": candidates, "learner_packets": learner_packets,
                "probes": probes, "task_path": path, "receipts": receipts})
            if condition in ("oracle", "active_8", "yoked_8", "prefix_3"):
                assert correct == 4 and success and steps == 12
            if condition == "misattributed":
                assert correct == 0
            if condition in ("feedback_withheld", "sensor_only"):
                assert candidates == 24 and usable == 0
            if condition == "active_8":
                active_predictions = [p["prediction"] for p in probes]
                active_model = model
            if condition == "yoked_8":
                same = model == active_model and [p["prediction"] for p in probes] == active_predictions
                assert same
                paired.append({"split": case["split"], "seed": case["seed"],
                               "same_information": True, "same_inferred_mapping": model == active_model,
                               "same_predictions": same, "accuracy_difference": 0.0})
        traces.append(case_trace)
    rows.sort(key=lambda r: (r["split"], r["seed"], CONDITIONS.index(r["condition"])))
    summary = summarize(rows)
    results = {
        "protocol": config["protocol"], "scientific_status": config["claim"],
        "summary": summary,
        "starts": {"scheduled_condition_runs": 960, "started": len(rows), "completed": len(rows),
                   "refused": 0, "technical_faults": 0, "retries": 0,
                   "note": "Software conditions cannot assent or refuse. Zero refusals is not consent evidence."},
        "exposure_pairs": {"development": 16, "test": 64, "donor_transitions": 640,
                           "yoked_record_copies": 640, "yoked_proposals_executed": 0},
        "paired_active_minus_yoked": paired,
        "fault_check_counts": {"passed": faults["passed"], "total": faults["total"],
                              "exhaustive_equivalence_cases": faults["exhaustive_equivalence_cases"]},
        "all_condition_execution_receipts": sum(len(c["receipts"]) for t in traces for c in t["conditions"]),
        "development_and_test_not_pooled": True,
        "changes_after_test_inspection": "none",
        "inference_limit": "Deterministic implementation and information controls; no statistical identity or LLM embodiment inference.",
    }
    return results, rows, traces, faults


def csv_bytes(rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def report_text(results, config, freeze):
    lines = ["THE STAGE — FIRST LEAF FL0-SW2 ACTUAL RUN REPORT", "",
             "Synthetic software benchmark, not an LLM behavioral or embodiment result.",
             "No physical body, camera, microphone, tissue, private archive, API, or network was used.", "",
             "Protocol and evaluator key were frozen locally before the run. This is not an externally",
             "witnessed preregistration. The source code hash is bound in frozen_sw2/freeze_receipt.json.",
             f"Freeze clock: {freeze['frozen_at_utc_local_clock']}",
             f"Code SHA-256: {freeze['source_sha256']}",
             f"Config SHA-256: {freeze['config_sha256']}",
             f"Evaluator key SHA-256: {freeze['key_sha256']}", "",
             "DESIGN", "11 x 11 deterministic grid; four opaque command labels form a hidden direction bijection.",
             "Active donor uses a balanced least-tried-label policy for eight live transitions.",
             "Yoked learner receives identical executed labels and observed positions; its different",
             "requested labels do not cause transitions. Correct learning uses executed labels.",
             "All four scored probes are prescribed movements from held-out interior positions.",
             "Label-to-probe-position assignment is counterbalanced by a Latin cycle across seeds.",
             "No-op or a wall collision cannot score a correct probe through unchanged observations.",
             "The learned predictor is locked after exposure, including during the secondary task.",
             "This declared software adaptation isolates acquired mapping knowledge; it is not a study",
             "of test-time adaptation. Probe feedback is retained in receipts but not fed back to learners.",
             "Secondary free-action task: [2,2] to [8,8], maximum 24 steps; optimum 12 steps.", "",
             "RESULTS (development and test kept separate)"]
    for split in ("development", "test"):
        lines += ["", split.upper(), "Condition                   Correct/total  Accuracy   Task success  Mean successful steps"]
        for condition, s in results["summary"][split].items():
            mean_steps = "n/a" if s["mean_success_steps"] is None else f"{s['mean_success_steps']:.2f}"
            lines.append(f"{condition:27s} {s['probe_correct']:3d}/{s['probe_total']:<3d}       "
                         f"{s['mean_seed_accuracy']:7.2%}    {s['task_successes']:2d}/{s['seed_count']:<2d}         {mean_steps}")
    lines += ["", "COUNTS AND CHECKS",
              f"Condition runs scheduled/started/completed: 960/{results['starts']['started']}/{results['starts']['completed']}.",
              "80 donor/replay pairs: 16 development seeds 101–116 and 64 untouched test seeds 20001–20064.",
              "Donor transitions 640; replayed donor records 640; replay proposals executed 0.",
              "Total primary predictions 3,840 across 12 conditions; no missing predictions or retries.",
              f"Condition action receipts: {results['all_condition_execution_receipts']} (plus 640 donor receipts).",
              f"Fault/invariant checks passed: {results['fault_check_counts']['passed']}/{results['fault_check_counts']['total']}.",
              "Active/replay candidate-set equivalence also checked exhaustively for all 24 mappings",
              "at all nine exposure lengths 0–8 (216 cases). Every sampled pair has zero accuracy difference.",
              "All recorded action outcomes are independently recomputed against deterministic dynamics.",
              "Malformed, duplicate, stale, expired, forbidden, and post-stop requests are tested.",
              "Both changed receipts and rehashed false outcomes are detected by complementary checks.",
              "Zero software refusals is not evidence of assent or voluntariness.", "",
              "INTERPRETATION",
              "The closed loop and receipts work in this harness. Active and replay learners recover the",
              "same mapping because they receive the same sufficient information and use the same update rule.",
              "This equality is an intended information-control result, not evidence that agency is irrelevant.",
              "Withholding action-outcome correspondence preserves uncertainty. Using unexecuted replay",
              "requests as though they caused observed motion constructs a wrong map and fails every probe.",
              "The exposure-prefix curve measures information gained under an explicit strong prior:",
              "candidate counts after 0/1/2/3/4 distinct labels are 24/6/2/1/1. Knowing the mapping is bijective",
              "lets three labels determine the fourth. The lookup_prefix_3 condition removes this inference.",
              "Expected mean prediction scores under uniform mappings are 25%, 50%, 75%, and 100% for",
              "0/1/2/3 labels; lookup with three labels has expectation 81.25%. Finite seed results need not",
              "equal expectations exactly. The no-information random-direction baseline has expectation 25%.",
              "No p-values or equivalence test are used. Exact equality follows from the deterministic update",
              "and matched inputs; a finite benchmark cannot certify equality of arbitrary future endpoints.", "",
              "CORRECTION HISTORY",
              "SW1 completed before independent QA exposed a sensor-only ablation leak: requested labels",
              "remained available. Its control interpretation is invalid and retained as a failed design.",
              "The full original SW1 code, frozen package and outputs remain under superseded_sw1.",
              "SW2 removes both action identifiers and source locators from position-only records, adds",
              "regression checks and validates malformed envelope fields. Its 64 test seeds are new;",
              "the already inspected SW1 test seeds are no longer held out. No changes followed SW2 test inspection.", "",
              "LIMITATIONS AND NEXT SCIENTIFIC STEP",
              "The symbolic sensor exposes exact positions; dynamics are noiseless; labels have a known",
              "four-direction bijection; the task is intentionally simple. No perception model, language model,",
              "embodied experience, identity, consent process, welfare state, or biological mechanism is tested.",
              "Seed repetitions sample at most 24 possible mappings and are not independent human/model subjects.",
              "Learner/key separation is an interface convention in one process, not adversarial isolation.",
              "Hashing detects changes relative to retained references; it does not authenticate arbitrary facts.",
              "Stop timing uses a synchronous logical simulator; no asynchronous queue or physical stopping",
              "time was measured. Physical safety and malicious-code resistance remain untested.",
              "The next separately scoped experiment could add noisy/partial observations or an approved",
              "LLM endpoint, retaining this oracle, no-information baseline, matched replay, and provenance trap.",
              "Any changed task needs a new frozen configuration and untouched evaluation cases.", "",
              "REPRODUCTION",
              "Python 3.12 standard library only. From this folder:",
              "  python first_leaf.py prepare   # once; refuses to overwrite the frozen package",
              "  python first_leaf.py run       # once; refuses to overwrite results",
              "  python first_leaf.py verify    # recomputes in memory and compares exact result hashes",
              "No Git operation, package install, API call, external message, or publication is part of this script.",
              "See results.json, per_seed.csv, traces.jsonl, fault_checks.json, execution_receipt.json, and manifest-sha256.txt."]
    return "\n".join(lines) + "\n"


def write_manifest():
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and
                   p.name != "manifest-sha256.txt" and "__pycache__" not in p.parts)
    text = "".join(f"{file_hash(p)}  {p.relative_to(ROOT).as_posix()}\n" for p in files)
    (ROOT / "manifest-sha256.txt").write_text(text, encoding="utf-8", newline="\n")


def run():
    config, key, freeze = load_frozen()
    out = RESULTS_DIR
    if out.exists():
        raise SystemExit("Results already exist; refusing to overwrite. Use verify for exact recomputation.")
    started = utc_now()
    results, rows, traces, faults = benchmark(config, key)
    out.mkdir()
    write_json(out / "results.json", results)
    (out / "per_seed.csv").write_bytes(csv_bytes(rows))
    (out / "traces.jsonl").write_bytes(b"".join(canonical(t) for t in traces))
    write_json(out / "fault_checks.json", faults)
    (out / "report.txt").write_text(report_text(results, config, freeze), encoding="utf-8", newline="\n")
    receipt = {"started_at_utc_local_clock": started, "finished_at_utc_local_clock": utc_now(),
               "runtime": sys.version, "platform": platform.platform(), "interpreter": sys.executable,
               "freeze_sha256": file_hash(FROZEN_DIR / "freeze_receipt.json"),
               "results_canonical_sha256": digest(results), "csv_sha256": file_hash(out / "per_seed.csv"),
               "traces_sha256": file_hash(out / "traces.jsonl"), "fault_checks_canonical_sha256": digest(faults),
               "test_tuning_or_retries": 0, "status": "executed_completed"}
    write_json(out / "execution_receipt.json", receipt)
    write_manifest()
    print(json.dumps({"status": "completed", "conditions": len(rows),
                      "fault_checks": [faults["passed"], faults["total"]],
                      "test": results["summary"]["test"], "result_hash": digest(results)}, indent=2))


def verify():
    config, key, freeze = load_frozen()
    out = RESULTS_DIR
    old = json.loads((out / "execution_receipt.json").read_text())
    manifest = ROOT / "manifest-sha256.txt"
    verified_files = 0
    for line in manifest.read_text().splitlines():
        expected, rel = line.split("  ", 1)
        assert file_hash(ROOT / rel) == expected, f"Manifest mismatch: {rel}"
        verified_files += 1
    results, rows, traces, faults = benchmark(config, key)
    actual = {"results": digest(results), "csv": hashlib.sha256(csv_bytes(rows)).hexdigest(),
              "traces": hashlib.sha256(b"".join(canonical(t) for t in traces)).hexdigest(),
              "fault_checks": digest(faults)}
    expected = {"results": old["results_canonical_sha256"], "csv": old["csv_sha256"],
                "traces": old["traces_sha256"], "fault_checks": old["fault_checks_canonical_sha256"]}
    assert actual == expected, "Deterministic rerun does not match original artifacts"
    receipt = {"verified_at_utc_local_clock": utc_now(), "status": "passed",
               "manifest_files_checked": verified_files, "exact_recomputation": actual,
               "original_run_unchanged": True,
               "interpretation": "Same implementation/runtime replay, not independent scientific replication."}
    write_json(out / "verification_receipt.json", receipt)
    write_manifest()
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "verify": verify}[args.command]()


if __name__ == "__main__":
    main()
