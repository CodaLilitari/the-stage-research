"""Replay The Stage's held-formulation oxygen-content comparison with Python 3."""
from math import sqrt
from statistics import mean

# Only the three held-condition inputs, outcomes and one aggregate training statistic.
# Sharts et al. https://doi.org/10.1016/S0022-1139(00)81622-X
# Data transcribed in https://doi.org/10.1063/1.4883876 pp. 90-92 (held table p.92).
# Units are mL oxygen per dL of the whole emulsion as reported.
ROWS = [
    # tag, degassed, SD, low-pressure, SD, high-pressure observation, SD
    ("S1", 0.1, .1, 1.3, .2, 5.0, .3),
    ("S2", 0.0, .0, 1.2, .2, 4.4, .2),
    ("S3", 0.8, .1, 1.8, .2, 4.3, .1),
]
PRESSURE_RATIO = 98.3 / 21.3
TRAIN_HIGH_MEDIAN = 4.7
PAID_FORECASTS = {
    "calibration": [4.858, 4.758, 5.166],
    "exchangeability": [4.65, 4.575, 4.825],
    "stress": [4.763636363636364, 4.663636363636364, 5.239393939393939],
    "partial identification": [4.75, 4.65, 5.25],
}


def mae_bounds(errors, widths):
    """Conservative deterministic perturbation bounds. Each width includes target error."""
    return (mean(max(0., abs(e) - d) for e, d in zip(errors, widths)),
            mean(abs(e) + d for e, d in zip(errors, widths)))


def main():
    pressure = [z + (low-z) * PRESSURE_RATIO for _,z,_,low,_,_,_ in ROWS]
    observed = [r[5] for r in ROWS]
    forecasts = {"offset-aware pressure": pressure, "training median": [TRAIN_HIGH_MEDIAN] * len(ROWS)}
    forecasts.update(PAID_FORECASTS)
    mae = {}
    worst = {}
    for name, pred in forecasts.items():
        errors = [p-y for p,y in zip(pred,observed)]
        mae[name] = mean(map(abs, errors))
        worst[name] = max(map(abs, errors))
        print(f"{name:24s}  MAE {mae[name]:.3f}  worst {worst[name]:.3f}  RMSE {sqrt(mean(e*e for e in errors)):.3f}")
    gain = mae["training median"] - mae["offset-aware pressure"]
    passed = mae["offset-aware pressure"] <= .50 and worst["offset-aware pressure"] <= 1.0 and gain >= .20
    print(f"Registered improvement {gain:+.3f} mL/dL; all three engineering gates passed: {passed}")
    perr = [p-y for p,y in zip(pressure,observed)]
    merr = [TRAIN_HIGH_MEDIAN-y for y in observed]
    print("Primary rounding sensitivity",mae_bounds(perr,[.05*2*PRESSURE_RATIO]*len(ROWS)))
    print("Median rounding sensitivity",mae_bounds(merr,[.10]*len(ROWS)))
    print("Primary one-SD sensitivity",mae_bounds(perr,[PRESSURE_RATIO*r[4]+(PRESSURE_RATIO-1)*r[2]+r[6] for r in ROWS]))


if __name__ == "__main__":
    main()
