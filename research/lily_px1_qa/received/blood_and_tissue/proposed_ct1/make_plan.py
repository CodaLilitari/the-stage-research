"""Generate hypothetical CT1 inputs, not tissue-solver results. Standard library only."""
from __future__ import annotations
import argparse
import itertools
import json
from pathlib import Path


def make_cases() -> list[dict]:
    profiles = [{"name": "dissolved", "kind": "dissolved", "kappa": 0.0}]
    for kappa in (4.0, 16.0):
        profiles.append({"name": f"linear_k{kappa:g}", "kind": "linear", "kappa": kappa})
        for ratio in (0.2, 0.5, 1.0):
            profiles.append({"name": f"hill_k{kappa:g}_p50_{ratio:g}", "kind": "hill",
                             "kappa": kappa, "p50_over_inlet": ratio, "hill_n": 2.7})
    result = []
    for index, (profile, mu, wall, spacing, mode) in enumerate(itertools.product(
        profiles, (1.0, 2.0, 4.0), (0.25, 1.0, 4.0), (0.8, 1.0, 1.2),
        ("pressure_and_power_limited", "fixed_flow_ablation"))):
        result.append({"case_id": f"CT1-{index+1:04d}", "status": "planned_not_executed",
                       "reference_manifest_sha256": None,
                       "carrier": profile, "viscosity_multiplier": mu,
                       "wall_transfer_multiplier": wall, "spacing_multiplier": spacing,
                       "hydraulic_mode": mode,
                       "parameter_status": "hypothetical_constitutive_screen_not_a_formulation"})
    if len(result) != 486 or len({r["case_id"] for r in result}) != 486:
        raise RuntimeError("Unexpected plan size or duplicate case IDs")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = make_cases()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        for row in cases:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": "input_plan_generated_no_tissue_solve", "cases": len(cases),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
