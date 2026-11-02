"""Read-only public payload verifier. Standard library; no network or science.
The root MANIFEST.sha256 is an integrity anchor, not a signature/authentication.
Only root .git administration and Python bytecode caches are ignored.
"""
from pathlib import Path,PurePosixPath,PureWindowsPath
import hashlib,json,re
def verify(root):
    root=Path(root).resolve();errors=[];expected={};folded=set()
    try:
        raw=(root/'MANIFEST.json').read_bytes()
        anchor=(root/'MANIFEST.sha256').read_text(encoding='utf-8').strip().split()
        if len(anchor)!=2 or anchor[1]!='MANIFEST.json' or hashlib.sha256(raw).hexdigest()!=anchor[0]:
            errors.append('Manifest anchor mismatch')
        manifest=json.loads(raw)
        rows=manifest['files']
        if not isinstance(rows,list):raise ValueError('files must be a list')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return {'passed':False,'checked_files':0,'errors':['Unreadable manifest: '+str(exc)]}
    for row in rows:
        try:
            if not isinstance(row,dict):raise ValueError('entry must be an object')
            name=row['path'];size=row['bytes'];digest=row['sha256']
            if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.endswith('/'):
                raise ValueError('invalid path text')
            p=PurePosixPath(name)
            if p.is_absolute() or PureWindowsPath(name).is_absolute() or '..' in p.parts or '.' in name.split('/') or '' in name.split('/'):
                raise ValueError('unsafe path')
            if p.parts[0]=='.git' or name in ('MANIFEST.json','MANIFEST.sha256'):
                raise ValueError('reserved path')
            if name.casefold() in folded:raise ValueError('duplicate/case-colliding path')
            if type(size)!=int or size<0 or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
                raise ValueError('invalid byte/hash metadata')
            folded.add(name.casefold());expected[name]=row
            target=root.joinpath(*p.parts)
            if any(parent.is_symlink() for parent in [target,*list(target.parents)[:len(p.parts)-1]]):
                raise ValueError('symlink payload forbidden')
            if not target.resolve().is_relative_to(root):raise ValueError('path outside root')
            data=target.read_bytes()
            if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:errors.append('Hash/size mismatch: '+name)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append('Invalid/missing entry: '+str(row.get('path','?') if isinstance(row,dict) else '?')+': '+str(exc))
    actual=set()
    for p in root.rglob('*'):
        rel=p.relative_to(root)
        if rel.parts[0]=='.git' or '__pycache__' in rel.parts:continue
        if p.is_symlink():errors.append('Symlink present: '+rel.as_posix())
        if p.is_file() and rel.as_posix() not in ('MANIFEST.json','MANIFEST.sha256'):actual.add(rel.as_posix())
    errors.extend('Unmanifested file: '+n for n in sorted(actual-set(expected)))
    return dict(passed=not errors,checked_files=len(expected),errors=errors)
if __name__=='__main__':
    result=verify(Path(__file__).resolve().parent)
    print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
