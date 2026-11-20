"""Recover measured markers from two source plots and refit both pooled Hill models."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.optimize import least_squares, linear_sum_assignment
from scipy.special import expit

from vector_points import CONDITIONS, COUNTS, observed_symbols


SOURCE_SHA256 = "89a1d84facbb7423baf49bbd4ef125a50eea3b7303e1acb72f155cfadd72d8c9"


def measured_points(document):
    if hashlib.sha256(document.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Supplement does not match the cited source-file hash")
    data = []
    with ZipFile(document) as archive:
        for i, (co2, count) in enumerate(zip(CONDITIONS, COUNTS)):
            panel = observed_symbols(archive.read(f"word/media/image{14+i}.emf"), True)
            combined = observed_symbols(archive.read(f"word/media/image{19+i}.emf"), False)
            if len(panel) != count or len(combined) != count:
                raise ValueError("Unexpected number of plotted observations")
            xy = np.array([p[1:] for p in panel])
            repeated = np.array([p[1:] for p in combined])
            distance = np.abs(xy[:, None, :] - repeated).max(axis=2)
            row, col = linear_sum_assignment(distance)
            if (distance[row, col] >= 0.00075).any() or not np.array_equal(
                np.round(xy[row], 1), np.round(repeated[col], 1)
            ):
                raise ValueError("Two source representations give different rounded values")
            data.extend((donor, co2, round(po2, 1), round(sat, 1)) for donor, po2, sat in panel)
    return data


def fitted_curve(training, log_transform):
    def predictor(parameters, po2, co2):
        ceiling, exponent, intercept, slope = parameters
        feature = np.log(co2 / 50.0) if log_transform else (co2 - 50.0) / 40.0
        return ceiling * expit(exponent * (np.log(po2) - intercept - slope * feature))

    co2, po2, sat = np.array([r[1:] for r in training], dtype=float).T
    fit = least_squares(
        lambda pars: predictor(pars, po2, co2) - sat,
        [98.0, 2.7, np.log(25.0), 0.3],
        bounds=([1.0, 0.05, -np.inf, -np.inf], [100.0, 20.0, np.inf, np.inf]),
        ftol=1e-11, xtol=1e-11, gtol=1e-11, max_nfev=300,
    )
    if not fit.success:
        raise ValueError(fit.message)
    return lambda po2, co2: predictor(fit.x, po2, co2)


def grouped_rmse(errors):
    return float(np.sqrt(np.mean([np.mean(np.square(values)) for values in errors])))


def benchmark(data):
    donors = sorted({r[0] for r in data})
    if len(donors) != 6:
        raise ValueError("Unexpected donor count")
    result = {}
    for mode in ["known", "unseen"]:
        scores = {}
        for log_transform in [False, True]:
            errors = defaultdict(list)
            for co2 in CONDITIONS:
                for omit in ([None] if mode == "known" else donors):
                    training = [r for r in data if r[1] != co2 and r[0] != omit]
                    held = [r for r in data if r[1] == co2 and (omit is None or r[0] == omit)]
                    predict = fitted_curve(training, log_transform)
                    for donor, pressure, po2, observed in held:
                        errors[(donor, pressure)].append(predict(po2, pressure) - observed)
            if len(errors) != 30 or sum(map(len, errors.values())) != 346:
                raise ValueError("Incorrect donor-by-condition scoring coverage")
            scores["log" if log_transform else "linear"] = {
                "equal_cell_rmse_points": grouped_rmse(errors.values()),
                "condition_rmse_points": {
                    str(c): grouped_rmse([v for (_, p), v in errors.items() if p == c])
                    for c in CONDITIONS
                },
            }
        result[mode] = scores
    expected = {"known": (3.747, 2.145), "unseen": (3.806, 2.224)}
    for mode, pair in expected.items():
        for model, value in zip(["linear", "log"], pair):
            if abs(result[mode][model]["equal_cell_rmse_points"] - value) > 0.00051:
                raise ValueError("Numerical result differs from the printed benchmark")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("supplement", type=Path)
    args = parser.parse_args()
    print(json.dumps(benchmark(measured_points(args.supplement)), indent=2, allow_nan=False))
