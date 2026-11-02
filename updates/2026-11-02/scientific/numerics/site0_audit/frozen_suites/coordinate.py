# SPDX-License-Identifier: Apache-2.0
# Provenance: Coda (Codex Lily), native agent stage_budget_runner.
"""One bounded child for this standalone suite or its numerical receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('label',choices=('initial_red','green','numerical'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    scratch=root/'tmp'
    scratch.mkdir(exist_ok=True)
    receipts=root/'receipts'
    receipts.mkdir(exist_ok=True)
    env=os.environ.copy()
    env.update(TEMP=str(scratch),TMP=str(scratch),PYTHONDONTWRITEBYTECODE='1',
               PYTHONIOENCODING='utf-8')
    command=[sys.executable,'-B']
    if args.label=='numerical': command+=['run_receipts.py']
    else: command+=['-m','unittest','discover','-s','.','-p','test_*.py','-v']
    start=time.perf_counter()
    with (receipts/(args.label+'.txt')).open('x',encoding='utf-8') as log:
        completed=subprocess.run(command,cwd=root,env=env,stdout=log,
                                 stderr=subprocess.STDOUT,timeout=60,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    record={'command':command,'cwd':str(root),'hard_timeout_seconds':60,
            'wall_seconds':time.perf_counter()-start,'returncode':completed.returncode,
            'python_version':sys.version,'temporary_directory':str(scratch),
            'site0_sha256':hashlib.sha256((root/'site0.py').read_bytes()).hexdigest()}
    (receipts/(args.label+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))
    return completed.returncode


if __name__=='__main__':
    raise SystemExit(main())
