# SPDX-License-Identifier: Apache-2.0
# Coda (Codex Lily): immutable AB-MPB1A dependency loader, not a new solver.
from pathlib import Path
import hashlib, importlib.util, json, sys
ROOT=Path(__file__).resolve().parent
A_ROOT=ROOT.parent/'ab_mpb1a'
PINS={'model.py':'d05cdd81f64464091148570d2f8c78f668e4960ffb10ae137f1ee6ad2f63c172',
      'MANIFEST.json':'14416f7f4e4650da4e6ef3182953646ef3e02064ed37646f33c9be761e0741b4',
      'run_001/numerical_receipt.json':'859fd45ea16751d7722c3b2e85a241e5981a10906512c66cb05025b46dc1e90e'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def verify_a():
    for rel,want in PINS.items():
        if sha(A_ROOT/rel)!=want:raise RuntimeError('Admitted A pin changed: '+rel)
    entries=read(A_ROOT/'MANIFEST.json')['files']
    for item in entries:
        path=A_ROOT/item['path']
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise RuntimeError('A manifest member changed: '+item['path'])
    return len(entries)
verify_a()
spec=importlib.util.spec_from_file_location('_stage_admitted_mpb1a',A_ROOT/'model.py')
A=importlib.util.module_from_spec(spec);sys.modules[spec.name]=A;spec.loader.exec_module(A)
A_ROWS=tuple(row for row in read(A_ROOT/'run_001/numerical_receipt.json')['rows'] if row['channel_cells']==3)
if len(A_ROWS)!=9:raise RuntimeError('Expected nine admitted primary rows')
DESIGN=read(ROOT/'STUDY_DESIGN.json')
def initial(config,condition):
    model=A.build(config)
    values=A.uniform_state(model,condition['free_concentration'],condition['site_concentration'],condition['bound_fraction'])
    return model,values
