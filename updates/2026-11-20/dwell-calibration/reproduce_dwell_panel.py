"""Calibrate probe-window error bounds for four square-wave missions in The Stage.

From the public repository root, run python -B path/to/reproduce_dwell_panel.py.
An alternate path to the frozen source can be supplied with --reference.
Outputs are dwell-missions.csv and dwell-summary.json next to this script by default.
Requires Python, NumPy and SciPy. Inputs and outputs are synthetic.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import sys
import warnings

for variable in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS",
                 "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"
sys.dont_write_bytecode = True

import numpy as np
import scipy
from scipy.stats import beta, binom


SOURCE_SHA256 = "a648a6a8069a1e67447db935bb7a6e90fa179e2e0e085bb591587500254a93d1"
PUBLIC_SOURCE = Path("updates/2026-11-20/reproduce_b2_gate.py")
DWELLS = (5, 15, 30, 60)
STACKS = (("H1", 0.0005, 0.01), ("H2", 0.001, 0.001))
SPLITS = (("calibration", 201121, 86), ("holdout", 201122, 300))
COVERAGE = 0.95
ALPHA = 0.05


def frozen_source(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Published reproduction source differs from the frozen SHA-256")
    spec = importlib.util.spec_from_file_location("published_b2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mission_seeds():
    """One independent seeded stream per split and stack; four dwells share a seed."""
    seen = set()
    blocks = {}
    for split, root, size in SPLITS:
        for stack_index, (stack, _, _) in enumerate(STACKS):
            rng = random.Random((root << 8) | stack_index)
            seeds = [rng.getrandbits(128) for _ in range(size)]
            if len(set(seeds)) != size or seen.intersection(seeds):
                raise ValueError("Duplicate mission seed")
            seen.update(seeds)
            blocks[stack, split] = seeds
    return blocks


def tolerance_rank(n, alpha):
    # For a continuous population, P[F(X_(r)) >= p] = P[Bin(n,p) <= r-1].
    for rank in range(1, n + 1):
        if binom.cdf(rank - 1, n, COVERAGE) >= 1 - alpha:
            return rank
    raise ValueError("Sample too small for the requested tolerance statement")


def failure_rate(flags):
    n = len(flags)
    k = int(np.count_nonzero(flags))
    lo = float(beta.ppf(ALPHA / 2, k, n - k + 1)) if k else 0.0
    hi = float(beta.ppf(1 - ALPHA / 2, k + 1, n - k)) if k < n else 1.0
    return {"failures": k, "n": n, "rate": k / n, "exact_95pct_CI": [lo, hi]}


def mission(source, seed, noise, calibration, clean, exact, fixed_test, waves):
    # The public trial refits deterministically on the same 451 Gaussian draws
    # on each call. These repeated calculations represent ONE fitted model.
    def evaluate(commands):
        result = source.trial(seed, noise, calibration, clean, exact, commands)
        if not np.all(np.isfinite([result["probe_error_K"], result["probe_envelope_K"]])):
            raise ValueError("Nonfinite probe statistic or envelope")
        return result

    with warnings.catch_warnings(), np.errstate(over="raise", divide="raise", invalid="raise"):
        warnings.simplefilter("error", RuntimeWarning)
        fixed_gate = evaluate(fixed_test)["accepted"]
        trials = [evaluate(waves[d]) for d in DWELLS]
    errors = [trial["probe_error_K"] for trial in trials]
    gates = [trial["accepted"] for trial in trials]
    return fixed_gate, errors, gates


def summarize(phase_rows):
    cal = phase_rows["calibration"]
    hold = phase_rows["holdout"]
    names = [f"d{d}_error_K" for d in DWELLS]
    fit_errors = np.array([[row[name] for name in names] for row in cal])
    test_errors = np.array([[row[name] for name in names] for row in hold])
    n = len(cal)
    rank_joint = tolerance_rank(n, ALPHA)
    rank_each = tolerance_rank(n, ALPHA / len(DWELLS))
    common_bound = float(np.sort(fit_errors.max(axis=1))[rank_joint - 1])
    dwell_bounds = np.sort(fit_errors, axis=0)[rank_each - 1]
    gate_counts = {}
    for phase, rows in phase_rows.items():
        gate_counts[phase] = {
            "missions": len(rows),
            "published_fixed_gate_rejections": sum(not row["fixed_gate"] for row in rows),
            "square_wave_gate_rejections_by_dwell": {
                str(d): sum(not row[f"d{d}_gate"] for row in rows) for d in DWELLS},
        }
    return {
        "gate_counts": gate_counts,
        "mission_maximum": {
            "rank_ascending_one_based": rank_joint, "threshold_K": common_bound,
            "confidence_lower_bound": float(binom.cdf(rank_joint - 1, n, COVERAGE)),
            "holdout_exceedance": failure_rate(test_errors.max(axis=1) > common_bound),
        },
        "four_marginal_bounds": {
            "rank_ascending_one_based": rank_each,
            "simultaneous_confidence_lower_bound":
                float(1 - len(DWELLS) * binom.sf(rank_each - 1, n, COVERAGE)),
            "by_dwell_s": {
                str(d): {"threshold_K": float(dwell_bounds[j]),
                         "holdout_exceedance": failure_rate(test_errors[:, j] > dwell_bounds[j])}
                for j, d in enumerate(DWELLS)},
            "holdout_exceedance_of_any_dwell_specific_bound":
                failure_rate(np.any(test_errors > dwell_bounds, axis=1)),
        },
        "fixed_0p2_K_comparison": {
            "holdout_missions_exceeding_0p2_K_at_any_dwell": failure_rate(test_errors.max(axis=1) > 0.2)
        },
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=PUBLIC_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    source = frozen_source(args.reference)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibration_step = np.arange(450)
    calibration = np.where((calibration_step >= 60) & ((calibration_step - 60) % 150 < 60), 2., 5.)
    step = np.arange(900)
    fixed_test = np.where((step >= 2) & ((step - 2) % 150 < 60), 2., 5.)
    waves = {d: np.where((step // d) % 2 == 0, 2., 5.) for d in DWELLS}
    if any(np.sum(np.diff(waves[d]) != 0) != 899 // d for d in DWELLS):
        raise AssertionError("Square-wave switch count mismatch")
    blocks = mission_seeds()
    all_rows = []
    invalid = []
    stacks = {}
    for stack, thickness, noise in STACKS:
        clean, exact = source.panel(thickness, calibration)
        if np.max(np.abs(source.forecast(exact, calibration, clean[:2]) - clean)) >= 1e-8:
            raise ArithmeticError("Panel recursion control failed")
        phase_rows = {}
        for split, _, size in SPLITS:
            rows = []
            for seed in blocks[stack, split]:
                row = {"stack": stack, "split": split, "seed": str(seed)}
                try:
                    fixed_gate, errors, gates = mission(
                        source, seed, noise, calibration, clean, exact, fixed_test, waves)
                except (ArithmeticError, ValueError, np.linalg.LinAlgError, RuntimeWarning) as error:
                    invalid.append(dict(row, reason=f"{type(error).__name__}: {error}"))
                    continue
                row.update(valid=True, fixed_gate=fixed_gate, maximum_error_K=max(errors))
                for d, error, gate in zip(DWELLS, errors, gates):
                    row[f"d{d}_error_K"] = error
                    row[f"d{d}_gate"] = gate
                rows.append(row)
            phase_rows[split] = rows
            all_rows.extend(rows)
            if len(rows) > size:
                raise AssertionError("Unexpected mission count")
        if not invalid:
            stacks[stack] = {"thickness_m": thickness, "sigma_K": noise, **summarize(phase_rows)}
    if invalid:
        write_json(args.output_dir / "invalid-missions.json", invalid)
        raise ValueError(f"{len(invalid)} invalid missions; no new bounds or summary issued")
    with (args.output_dir / "dwell-missions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=all_rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    write_json(args.output_dir / "dwell-summary.json", {
        "scope": "Synthetic, per stack, unconditional on gate acceptance",
        "source_sha256": SOURCE_SHA256,
        "design": {"dt_s": 1, "square_wave_transitions": 900, "dwells_s": DWELLS,
                   "starting_power_W": 2, "alternating_power_W": 5,
                   "window_readings": 5, "window_start_lag_steps": 61,
                   "paired_anchor": "Each model starts at the same two copies of the fitted 5 W steady output.",
                   "seed_method": "Python random.Random((root << 8) | stack_index), getrandbits(128); H1=0, H2=1",
                   "splits": [{"name": s, "root": root, "n_per_stack": n} for s, root, n in SPLITS],
                   "failure": "strict exceedance", "invalid_missions": 0,
                   "holdout_CI": "individual two-sided 95% Clopper-Pearson conditional on fixed thresholds"},
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "stacks": stacks})


if __name__ == "__main__":
    main()
