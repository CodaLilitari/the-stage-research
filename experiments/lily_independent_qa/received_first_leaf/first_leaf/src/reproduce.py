#!/usr/bin/env python3
"""Re-run four frozen evaluation profiles without overwriting delivered results."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
from first_leaf import ROOT

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    p.error('Output must be a new directory; do not overwrite a previous run')
a.output.mkdir(parents=True)
comparisons = {}
for profile in ['primary', 'no_delay', 'clean', 'stationary']:
    subprocess.run([sys.executable, str(ROOT/'src/first_leaf.py'), 'run', '--split', 'evaluation',
                    '--profile', profile, '--out', str(a.output)], check=True)
    def receipts(path):
        return {(r['seed'],r['algorithm']): r for r in (json.loads(l) for l in path.read_text().splitlines())}
    original = receipts(ROOT/f'results/evaluation_{profile}_runs.jsonl')
    rerun = receipts(a.output/f'evaluation_{profile}_runs.jsonl')
    mismatches = [list(k) for k in original if original[k] != rerun.get(k)]
    comparisons[profile] = {'original_count': len(original), 'rerun_count': len(rerun), 'mismatches': mismatches}
subprocess.run([sys.executable, str(ROOT/'src/analyze.py'), '--results', str(a.output)], check=True)
(a.output/'comparison_with_delivered.json').write_text(json.dumps(comparisons,indent=2)+'\n')
print(json.dumps(comparisons,indent=2))
if any(x['mismatches'] for x in comparisons.values()):
    raise SystemExit('Rerun differs: inspect runtime and implementation before claiming reproduction')
