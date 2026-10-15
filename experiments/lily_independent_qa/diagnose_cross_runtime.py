"""Bounded altered-arithmetic diagnosis; never modifies the received source."""
import csv, gzip, inspect, json, math, sys, textwrap
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / 'received_first_leaf' / 'first_leaf'
sys.path.insert(0, str(SRC / 'src'))
import first_leaf as fl

cfg = fl.load_protocol()
with gzip.open(SRC / 'inputs/evaluation_fixtures.jsonl.gz', 'rt') as stream:
    fx = next(x for x in map(json.loads, stream) if x['seed'] == 10237)
with (SRC / 'results/evaluation_clean_episodes.csv').open(newline='') as stream:
    original = [r for r in csv.DictReader(stream) if r['seed'] == '10237' and r['algorithm'] == 'shuffled']
baseline, baseline_hash = fl.run_trial(cfg, fx, 'clean', 'shuffled')
source = textwrap.dedent(inspect.getsource(fl.Agent.choose))
needle = '(alpha * v[j] + b[a][j] - desired[j]) ** 2'
assert source.count(needle) == 1
source = source.replace(needle, 'square(alpha * v[j] + b[a][j] - desired[j])')
space = {'math': math, 'square': lambda value: value * value}
exec(compile(source, '<diagnostic multiplication only>', 'exec'), space)
fl.Agent.choose = space['choose']
modified, modified_hash = fl.run_trial(cfg, fx, 'clean', 'shuffled')
result = {'scope': 'Single clean shuffled trial, frozen seed10237; action-cost square changed from pow to multiplication only. Original source untouched.',
          'runtime': sys.version, 'original_rows': original, 'baseline_rows': baseline, 'modified_rows': modified,
          'baseline_trace_sha256': baseline_hash, 'modified_trace_sha256': modified_hash,
          'original_end_model_match_baseline': [a['end_model_sha256'] == b['end_model_sha256'] for a,b in zip(original,baseline)],
          'original_end_model_match_multiplication': [a['end_model_sha256'] == b['end_model_sha256'] for a,b in zip(original,modified)]}
(BASE / 'cross_runtime_arithmetic_diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if not k.endswith('_rows')},indent=2))
