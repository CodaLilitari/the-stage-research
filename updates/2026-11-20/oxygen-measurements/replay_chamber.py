"""Recalculate chamber-template results directly from Qayyum et al.'s workbook."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from openpyxl import load_workbook


SOURCE_SHA256 = "f301464111d1feb33c1b28a192b8b9d868a352a6041d8f4b0da03eeccc152383"


def recordings(sheet, count):
    """Extract t=0 and the 184 on-grid observations covered by every input run."""
    times = []
    readings = []
    for row in list(sheet.values)[3:]:
        if not isinstance(row[0], (int, float)) or not 0 <= row[0] <= 920:
            continue
        times.append(row[0])
        readings.append(row[1:count + 1])
    if times != list(range(0, 921, 5)):
        raise ValueError("Source observation times differ from the registered grid")
    values = np.asarray(readings, dtype=float)
    if values.shape != (185, count) or not np.isfinite(values).all():
        raise ValueError("Source has missing or nonnumeric observations")
    return values


def score(held, training, reduction=np.mean):
    # Compare predicted and observed changes. This anchors every test series
    # at its own observed t=0 without admitting later held oxygen values.
    template = reduction(training[1:, :] - training[0, :], axis=1)
    changes = held[1:, :] - held[0, :]
    by_run = np.sqrt(np.mean((template[:, None] - changes) ** 2, axis=0))
    return {"each_run_rmse_uM": by_run.tolist(), "mean_run_rmse_uM": float(by_run.mean())}


def replay(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Workbook does not match the cited source-file hash")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        empty = recordings(book["Liquid Phase (IH, No Cells)"], 3)
        loaded = recordings(book["Liquid Phase (IH, Cells)"], 6)
    finally:
        book.close()
    result = {
        "empty_held3_initial": score(empty[:, 2:], np.zeros((185, 1))),
        "empty_held3_empty_template": score(empty[:, 2:], empty[:, :2]),
        "loaded_held5_and_6_empty_template": score(loaded[:, 4:], empty),
        "loaded_held5_and_6_loaded_template": score(loaded[:, 4:], loaded[:, :4]),
        "loaded_held5_and_6_loaded_median": score(loaded[:, 4:], loaded[:, :4], np.median),
    }
    expected = [71.4950930, 3.8806917, 23.7419129, 10.7440411, 10.8421234]
    for metric, target in zip(result.values(), expected):
        if abs(metric["mean_run_rmse_uM"] - target) > 1e-6:
            raise ValueError("Reproduction departed from the registered primary-window score")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.workbook), indent=2, allow_nan=False))
