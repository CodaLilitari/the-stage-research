"""Exact rational examples of two-component saturation measurement. Run with Python 3."""

import json
from fractions import Fraction


def blend(cell, free, free_fraction):
    return [(1 - free_fraction) * a + free_fraction * b for a, b in zip(cell, free)]


def components(low, high, low_fraction, high_fraction):
    difference = [(y - x) / (high_fraction - low_fraction) for x, y in zip(low, high)]
    cell = [x - low_fraction * d for x, d in zip(low, difference)]
    free = [x + (1 - low_fraction) * d for x, d in zip(low, difference)]
    for curve in (cell, free):
        assert all(0 <= value <= 1 for value in curve) and curve == sorted(curve)
    return cell, free


def main():
    low_fraction, high_fraction = Fraction(1, 4), Fraction(3, 4)
    cell = list(map(Fraction, [".12", ".41", ".76", ".96"]))
    free = list(map(Fraction, [".23", ".59", ".84", ".94"]))
    low = blend(cell, free, low_fraction)
    high = blend(cell, free, high_fraction)
    contrast = (high[-1] - high[0]) - (low[-1] - low[0])
    threshold = -contrast / 4
    assert contrast == Fraction("-.065") and threshold == Fraction(".01625")
    examples = []
    for error in [Fraction(".005"), threshold, Fraction(".017")]:
        adjusted_low, adjusted_high = low.copy(), high.copy()
        adjusted_low[0] += error
        adjusted_low[-1] -= error
        adjusted_high[0] -= error
        adjusted_high[-1] += error
        a, b = components(adjusted_low, adjusted_high, low_fraction, high_fraction)
        change_difference = (b[-1] - b[0]) - (a[-1] - a[0])
        assert change_difference == (contrast + 4 * error) / (high_fraction - low_fraction)
        examples.append({
            "per_readout_absolute_error_pp": float(error * 100),
            "component_change_contrast_pp": float(change_difference * 100),
            "cell": list(map(float, a)),
            "free": list(map(float, b)),
        })

    # Across four pressures the pointwise limit is sqrt(4) times the RMS limit.
    pointwise = 2 * Fraction(".9")
    bounds = {
        str(separation_pp): float(pointwise / Fraction(separation_pp, 100))
        for separation_pp in (36, 50, 60, 100)
    }
    print(json.dumps({
        "error_threshold_for_sign_pp": float(100 * threshold),
        "examples": examples,
        "max_pointwise_component_error_bound_for_four_point_RMS_0p9_and_symmetric_known_mix_pp": bounds,
    }, indent=2))


if __name__ == "__main__":
    main()
