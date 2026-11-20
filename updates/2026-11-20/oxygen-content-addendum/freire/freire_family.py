"""Lilitari's retrospective test of transferring a one-pressure correction between carrier families."""
import csv
from collections import defaultdict
from itertools import permutations
import json
from pathlib import Path
from statistics import mean


def evaluate(training, target):
    # The measurements report oxygen in micromoles per mL of finished fluid.
    offset = mean(value - estimate for value, spread, estimate in training)
    low = mean(value - spread - estimate for value, spread, estimate in training)
    high = mean(value + spread - estimate for value, spread, estimate in training)
    assert high < 0
    predictions = [estimate + offset for value, spread, estimate in target]
    observed = [value for value, spread, estimate in target]
    errors = {}
    for name, shift in (("component", 0.0), ("cross_family", offset)):
        residuals = [abs(estimate + shift - value) for value, spread, estimate in target]
        errors[name] = {"mae": mean(residuals), "largest": max(residuals)}

    # For negative corrections the gain is nonincreasing in each measured residual.
    # On either target boundary it is piecewise linear in the learned correction.
    gains = []
    for side in (-1, 1):
        residuals = [value + side * spread - estimate for value, spread, estimate in target]
        knots = [low, high] + [r for r in residuals if low < r < high]
        for correction in knots:
            gains.append(mean(abs(r) - abs(r - correction) for r in residuals))
    return {
        "train_mean_discrepancy": offset,
        "train_one_spread_range": [low, high],
        "predictions": predictions,
        "observations": observed,
        "errors": errors,
        "mae_improvement_minmax_when_each_measurement_moves_one_reported_spread": [min(gains), max(gains)],
    }


def main():
    groups = defaultdict(list)
    with Path(__file__).with_name("measurements.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            groups[row["pfc"]].append(tuple(float(row[k]) for k in (
                "oxygen_umol_per_mL", "spread_umol_per_mL", "component_model_umol_per_mL")))
    assert sorted(len(group) for group in groups.values()) == [3, 3]
    directions = {source + " to " + target: evaluate(groups[source], groups[target])
                  for source, target in permutations(sorted(groups), 2)}
    print(json.dumps({"directions": directions}, indent=2))


if __name__ == "__main__":
    main()
