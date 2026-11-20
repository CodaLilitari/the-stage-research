"""Reproduce the frozen static-to-external-flow analysis from the cited original PDF."""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
if len(sys.argv)!=2:
    raise SystemExit('Usage: python replay.py 306e.pdf')
steps=[
    ['prepare.py',str(Path(sys.argv[1]).resolve())],
    ['read_b.py'],
    ['score_b.py','0423744ec22898c5e8ef0c16c2718202a624bd61a70770042971c72cec970949'],
    ['rank_score.py'],['equal_trace.py'],['overlap_witness.py']
]
for name,*args in steps:
    subprocess.run([sys.executable,str(root/name),*args],check=True)
