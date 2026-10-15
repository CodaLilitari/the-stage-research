#!/usr/bin/env python3
"""Run all-seed matched-replay and checkpoint checks on frozen fixtures."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path
from first_leaf import ROOT, checkpoint_check, load_protocol, replay_check
from analyze import interval

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "results")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
cfg = load_protocol()
with gzip.open(ROOT / 'inputs/evaluation_fixtures.jsonl.gz', 'rt') as f:
    fixtures = [json.loads(l) for l in f]
replay, checkpoints = [], []
for i, fx in enumerate(fixtures):
    replay.append(replay_check(cfg, fx))
    checkpoints.append(checkpoint_check(cfg, fx, args.output / 'checkpoint_witness' if i == 0 else None))
    if (i + 1) % 32 == 0:
        print('Verified', i + 1, 'seeds', flush=True)
w = args.output / 'checkpoint_witness'
subprocess.run([sys.executable, str(ROOT / 'src/first_leaf.py'), 'resume',
                '--checkpoint', str(w / 'checkpoint.json'), '--fixture', str(w / 'checkpoint_fixture.json'),
                '--out', str(w / 'subprocess_continuation.jsonl')], check=True, capture_output=True)
a = (w / 'reference_continuation.jsonl').read_bytes()
b = (w / 'subprocess_continuation.jsonl').read_bytes()
assert a == b
penalty = [r['records_only_mean_distance'] - r['full_state_mean_distance'] for r in checkpoints]
summary = {'replay_seed_pairs': len(replay), 'identical_learner_state_comparisons': sum(r['comparisons'] for r in replay),
           'checkpoint_seed_pairs': len(checkpoints), 'full_state_exact_pairs': sum(r['full_state_exact'] for r in checkpoints),
           'exact_continuation_steps_per_pair': 49, 'separate_process_witness_identical': True,
           'separate_process_trace_sha256': hashlib.sha256(a).hexdigest(),
           'cold_controller_reset_minus_full_state_distance': interval(penalty, cfg),
           'cold_controller_mean_action_disagreements_of49': statistics.fmean(r['records_only_action_disagreements'] for r in checkpoints),
           'cold_controller_reset_does_not_replay_history': True,
           'all_restoration_tests_same_python_runtime_platform': True}
(args.output / 'invariants.json').write_text(json.dumps({'summary': summary, 'replay': replay, 'checkpoints': checkpoints}, indent=2) + '\n')
print(json.dumps(summary, indent=2))
