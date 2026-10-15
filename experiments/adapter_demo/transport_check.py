"""Exercise the actual stdin/stdout boundary without exposing tools to a controller."""
import hashlib, json, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parent
def cmd(name, obs, **extra):
    return json.dumps(dict(command_id=name, observation_id=obs, deadline=1, **extra))
lines = [cmd("one", "obs-0", motor=.6), cmd("one", "obs-1", motor=.6),
         cmd("stale", "obs-0", motor=.6), "{broken", cmd("stop", "obs-1", stop=True),
         cmd("after-stop", "obs-2", motor=.1)]
run = subprocess.run([sys.executable, str(root / "adapter.py"), "serve"],
                     input="\n".join(lines) + "\n", text=True, capture_output=True, check=True)
out = [json.loads(line) for line in run.stdout.splitlines()]
assert len(out) == 7 and not run.stderr
assert [r["admitted"] for r in out[1:]] == [True, False, False, False, True, False]
assert [r["reason"] for r in out[2:5]] == ["duplicate_command", "stale_observation", "malformed_json_or_envelope"]
assert out[-1]["reason"] == "stop_latched" and out[-1]["observed"] == out[-2]["observed"]
assert all(set(r["observed"]) == {"position", "velocity", "logical_timestamp", "observation_id"} for r in out[1:])
(root / "transport_trace.jsonl").write_text(run.stdout, encoding="utf-8")
result = {"status": "passed", "transport": "actual subprocess stdin/stdout JSON-lines",
          "requests": 6, "initial_observations": 1, "receipts": 6, "admitted": 2, "rejected": 4}
(root / "transport_check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
files = sorted(p for p in root.iterdir() if p.is_file() and p.name != "manifest-sha256.txt")
(root / "manifest-sha256.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
print(json.dumps(result))
