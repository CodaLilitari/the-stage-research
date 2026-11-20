"""Predict the chamber's intermittent gas oxygen from separate step records (Qayyum et al.)."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

import numpy as np
from openpyxl import load_workbook

WORKBOOK_SHA256 = "f301464111d1feb33c1b28a192b8b9d868a352a6041d8f4b0da03eeccc152383"
POSITIONS = {"P1": (0, 20, 370.3), "P2": (5, 27, 371.3), "P3": (10, 34, 371.3)}
TIMES = np.arange(5, 216, 5)


def numeric(value):
    return isinstance(value, (int, float)) and np.isfinite(value)


def read_step(rows, column, trial):
    pairs = np.array([(r[column], r[column + trial]) for r in rows
                      if numeric(r[column]) and numeric(r[column + trial])])
    times, values = pairs.T
    assert times[0] == 0 and np.all(np.diff(times) > 0)
    return times, values - values[0]


def curve(lags, calibration):
    curves = [np.interp(lags, t, y, left=0.0, right=y[-1]) for t, y in calibration]
    return np.mean(curves, axis=0)


def waveform(rows, col, elapsed_offset):
    levels = {}
    for r in rows:
        if not numeric(r[col]) or not numeric(r[col + 1]):
            continue
        t = r[col]
        if t in levels:
            assert t > elapsed_offset + TIMES[-1]
        levels[t] = r[col + 1] * 100
    times = np.array(sorted(levels))
    return times, np.array([levels[t] for t in times])


def examine(source):
    assert hashlib.sha256(source.read_bytes()).hexdigest() == WORKBOOK_SHA256
    book = load_workbook(source, read_only=True, data_only=True)
    step = list(book["Gas Phase Oxygen (Step Change)"].values)[2:]
    measured = list(book["Gas Phase Oxygen (IH)"].values)[3:]
    book.close()
    local = {k: [read_step(step, POSITIONS[k][0], trial) for trial in (1, 2)] for k in ("P1", "P2")}
    local["P3"] = local["P1"] + local["P2"]
    out = {}
    for site, (gas_col, command_col, offset) in POSITIONS.items():
        trials = []
        for trial in (1, 2, 3):
            obs = {r[gas_col]:r[gas_col + trial] for r in measured
                   if numeric(r[gas_col]) and numeric(r[gas_col + trial])}
            actual = np.array([obs[t] for t in TIMES])
            anchor = obs[0]
            ti, u = waveform(measured, command_col + 2 * (trial - 1), offset)
            jumps = np.diff(u, prepend=0.0)
            start = curve(offset - ti, local[site])
            response = curve(TIMES[:, None] + offset - ti, local[site])
            modeled = anchor + (response - start) @ jumps / 21
            instant = u[np.searchsorted(ti, TIMES + offset, side="right") - 1]
            records = {"step_response": modeled, "hold_initial": np.full(len(TIMES), anchor),
                       "instantaneous_command": instant}
            trials.append({k: float(np.mean((p - actual) ** 2) ** .5) for k, p in records.items()})
        out[site] = {"trial_rmse": trials,
                     "mean_trial_rmse": {k: mean(r[k] for r in trials) for k in trials[0]}}
    return out


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("workbook", type=Path, help="Original Compiled_Data_PAPER_unformatted.xlsx from Dryad.")
    args = cli.parse_args()
    print(json.dumps(examine(args.workbook), indent=2))
