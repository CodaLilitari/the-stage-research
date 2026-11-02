"""Run the predeclared matrix; write JSON only to --out. Deterministic, stdlib only."""
import argparse
import json
from pathlib import Path
import sys

from harness import scenario_matrix, run_scenario, summarize, build_report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Thermal supervisor scenario matrix (model study only)")
    ap.add_argument("--out", default=None, help="caller-supplied JSON output path (optional)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    runs = scenario_matrix()
    results = [run_scenario(s) for s in runs]
    report = build_report(results)
    if not args.quiet:
        for line in summarize(results):
            print(line)
        print(json.dumps(report["noise_false_alarm_bounds"], indent=1))
        for d in report["derived_configs"]:
            print(json.dumps(d, indent=1, sort_keys=True))
        for d in report["detectability"]:
            print(json.dumps(d, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if not args.quiet:
            print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
