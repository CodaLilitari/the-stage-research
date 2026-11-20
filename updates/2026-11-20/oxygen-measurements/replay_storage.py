"""Score the two empirical distribution baselines on the published day-42 wells."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from openpyxl import load_workbook
from scipy.stats import wasserstein_distance


def replay(workbook):
    expected = "e5d9003374f03ce1f77408932708219716ec9d1aef355c0d2c47f728c6a79677"
    if hashlib.sha256(workbook.read_bytes()).hexdigest() != expected:
        raise ValueError("Source workbook hash mismatch")
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        rows = list(book["Fig. 4"].values)
    finally:
        book.close()
    days = (0, 1, 7, 14, 28, 42)
    if tuple(rows[0][:6]) != tuple(f"Day {d}" for d in days):
        raise ValueError("Unexpected header")
    samples = [np.array([r[i] for r in rows[1:] if isinstance(r[i], (int, float))])
               for i in range(len(days))]
    if [len(s) for s in samples] != [72, 71, 60, 55, 75, 65]:
        raise ValueError("Unexpected number of wells")
    held = samples[-1]
    result = {}
    for name, training in (("hold_last", samples[-2:-1]), ("equal_day", samples[:-1])):
        values = np.concatenate(training)
        weights = np.concatenate([np.full(len(s), 1 / (len(training) * len(s))) for s in training])
        # For the empirical distribution F, CRPS(F,y) = E|X-y| - E|X-X'|/2.
        absolute_error = np.abs(values[:, None] - held).mean(axis=1) @ weights
        dispersion = weights @ np.abs(values[:, None] - values) @ weights
        result[name] = {
            "mean_CRPS_seconds": float(absolute_error - dispersion / 2),
            "W1_seconds": float(wasserstein_distance(values, held, u_weights=weights)),
        }
    for name, scores in {"hold_last": (0.200540, 0.237747), "equal_day": (0.171596, 0.168038)}.items():
        if not np.allclose(list(result[name].values()), scores, atol=0.00000051, rtol=0):
            raise ValueError("Score differs from the public rounding")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    print(json.dumps(replay(parser.parse_args().workbook), indent=2))
