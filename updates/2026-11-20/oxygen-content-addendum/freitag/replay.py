"""Regenerate the minimal training summary and score the eight frozen forecasts from both papers."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
FILES = {
    "standl": "917ce2a3397fb5359ea2792902d3a0638f0814ef8a7e991839cfcca13b49df4e",
    "freitag": "22d0c8d1129b0cb7c5644e110b343d91b38e0aaae95b98198c0b260c73e7108c",
}


def layout(name, target):
    pdf = ROOT / (name + ".pdf")
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != FILES[name]:
        raise ValueError("Edition differs from the verified " + name + " paper.")
    tool = shutil.which("pdftotext")
    if tool:
        command = [tool, "-layout", "-enc", "UTF-8", str(pdf), str(target)]
    else:
        wsl = shutil.which("wsl.exe")
        if not wsl:
            raise RuntimeError("Install Poppler pdftotext locally or in WSL.")
        paths = [subprocess.check_output([wsl, "-e", "wslpath", "-a", p.as_posix()],text=True).strip()
                 for p in (pdf,target)]
        command = [wsl, "-e", "/usr/bin/pdftotext", "-layout", "-enc", "UTF-8", *paths]
    subprocess.run(command, timeout=120, check=True)


def training(text):
    lines = text.splitlines()
    def number(value):
        # Match the numerical serialization of the pre-score inputs for byte-level verification.
        numeric = float(value)
        return int(numeric) if numeric.is_integer() else numeric

    def rows(header):
        start = next(i for i,line in enumerate(lines) if line.startswith(header))
        records = [l for l in lines[start:] if re.match(r"\s*(?:Baseline|Time [1-4])\s",l)][:10]
        assert len(records) == 10
        return [[tuple(map(number,pair)) for pair in re.findall(r"([-\d.]+)\s*⫾\s*([\d.]+)",l)]
                for l in records]
    flow = rows("Table I. Hemodynamic")
    values = rows("Table III. Muscular")
    points = [[q[2],v[2],v[3]] for q,v in zip(flow,values)]
    return {"groups": {"H":points[:5], "R":points[5:]}}


if __name__ == "__main__":
    source_training = ROOT / "standl-layout.txt"
    layout("standl", source_training)
    layout("freitag", ROOT / "source-layout.txt")
    (ROOT/"standl-means.json").write_text(json.dumps(training(source_training.read_text(encoding="utf8"))),encoding="utf8")
    for script in ("inputs.py","freeze.py","score.py","compartments.py"):
        subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,check=True,timeout=45)
