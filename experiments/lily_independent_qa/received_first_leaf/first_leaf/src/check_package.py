#!/usr/bin/env python3
"""Check supplied bytes against the local manifest; this does not authenticate truth or time."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'MANIFEST.json').read_text())
errors = []
for item in manifest['files']:
    path = (root/item['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        errors.append({'path':item['path'],'error':'missing or outside package'})
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item['sha256']:
        errors.append({'path':item['path'],'error':'digest mismatch'})
print(json.dumps({'checked':len(manifest['files']),'errors':errors,
                  'meaning':'Byte equality to this manifest only; no independent authenticity or timestamp guarantee'},indent=2))
if errors:
    raise SystemExit(1)
