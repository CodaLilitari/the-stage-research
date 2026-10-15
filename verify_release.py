"""Verify this public snapshot's file membership, sizes and SHA-256 hashes.

Standard library only. No network, scientific run, or file writes.
Historical nested manifests are data, not substitutes for the root manifest.
Only root .git administrative metadata is excluded for ordinary Git clones;
nested .git paths remain subject to the public payload inventory.
"""
from pathlib import Path
import hashlib
import json

def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    expected = {}
    errors = []
    for row in manifest['files']:
        name = row['path']
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or name in expected:
            errors.append('Unsafe or duplicate manifest path: ' + name)
            continue
        expected[name] = row
        target = root / name
        if not target.is_file():
            errors.append('Missing file: ' + name)
            continue
        data = target.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            errors.append('Hash/size mismatch: ' + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts
              and p.relative_to(root).parts[0] != '.git'
              and p.relative_to(root).as_posix() not in {'MANIFEST.json', 'MANIFEST.sha256'}}
    errors.extend('Unmanifested file: ' + name for name in sorted(actual - set(expected)))
    print(json.dumps({'checked_files': len(expected), 'passed': not errors, 'errors': errors}, indent=2))
    raise SystemExit(bool(errors))

if __name__ == '__main__':
    main()
