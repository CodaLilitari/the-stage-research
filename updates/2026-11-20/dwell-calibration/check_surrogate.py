"""Reproduce synthetic lognormal tolerance-bound checks; emit CSV to stdout.

Run python -B check_surrogate.py > surrogate-check.csv using NumPy and SciPy.
The two correlations share the same contiguous pseudorandom normal draws.
The outer unit of replication is one fresh calibration sample of 100 missions.
"""
import csv
import math
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri, roots_hermitenorm
from scipy.stats import binom, binomtest


N = 100
REPEATS = 4096
DWELLS = 4
RANK = 99
P = 0.95
SEED = 201122
CORRELATIONS = (0.0, 0.6)


def common_factor_cdf(z, rho, dimensions, order):
    if rho == 0:
        return ndtr(z) ** dimensions
    nodes, weights = roots_hermitenorm(order)
    conditional = ndtr((z - math.sqrt(rho) * nodes) / math.sqrt(1 - rho))
    return np.dot(weights, conditional ** dimensions) / math.sqrt(2 * math.pi)


def max_quantile(rho, order):
    if rho == 0:
        return ndtri(P ** (1 / DWELLS))
    return brentq(lambda z: common_factor_cdf(z, rho, DWELLS, order) - P,
                  0, 5, xtol=1e-14)


def all_dwells_coverage(rho):
    # Inclusion-exclusion over dwell failures. All N independent missions must
    # miss z on the same chosen subset for those sample maxima to miss z.
    z = ndtri(P)
    return sum((-1) ** k * math.comb(DWELLS, k) *
               common_factor_cdf(z, rho, k, 128) ** N for k in range(DWELLS + 1))


def main():
    thresholds = {rho: max_quantile(rho, 128) for rho in CORRELATIONS}
    for rho, threshold in thresholds.items():
        if abs(threshold - max_quantile(rho, 64)) > 1e-10:
            raise ArithmeticError("Quadrature orders disagree on the maximum quantile")
    marginal = ndtri(P)
    counts = {rho: np.zeros(DWELLS + 2, dtype=int) for rho in CORRELATIONS}
    rng = np.random.default_rng(SEED)
    for start in range(0, REPEATS, 64):
        normals = rng.standard_normal((min(64, REPEATS - start), N, DWELLS + 1))
        for rho in CORRELATIONS:
            z = np.sqrt(rho) * normals[:, :, :1] + np.sqrt(1 - rho) * normals[:, :, 1:]
            # The lognormal transform is strictly increasing. Compare on z scale.
            dwell_ok = z.max(axis=1) >= marginal
            counts[rho][:DWELLS] += dwell_ok.sum(axis=0)
            counts[rho][DWELLS] += dwell_ok.all(axis=1).sum()
            maxima = z.max(axis=2)
            bound = np.partition(maxima, RANK - 1, axis=1)[:, RANK - 1]
            counts[rho][-1] += np.count_nonzero(bound >= thresholds[rho])

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["rho", "method", "ascending_rank", "calibration_n", "replications",
                     "successes", "fraction", "individual_95pct_Wilson_low",
                     "individual_95pct_Wilson_high", "population_comparison_threshold",
                     "theoretical_calibration_success"])
    for rho in CORRELATIONS:
        joint_probability = all_dwells_coverage(rho)
        for index, successes in enumerate(counts[rho]):
            rank = RANK if index == DWELLS + 1 else N
            probability = 1 - P ** N
            threshold = 0.1 * math.exp(0.5 * marginal)
            if index < DWELLS:
                method = f"dwell_{index + 1}"
            elif index == DWELLS:
                method = "all_four_dwell_bounds"
                probability = joint_probability
            else:
                method = "one_bound_on_mission_maximum"
                probability = binom.cdf(RANK - 1, N, P)
                threshold = 0.1 * math.exp(0.5 * thresholds[rho])
            interval = binomtest(int(successes), REPEATS).proportion_ci(method="wilson")
            writer.writerow([rho, method, rank, N, REPEATS, successes, successes / REPEATS,
                             interval.low, interval.high, threshold, probability])


if __name__ == "__main__":
    main()
