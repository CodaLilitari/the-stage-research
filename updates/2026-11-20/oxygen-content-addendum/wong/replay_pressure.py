"""Replay the two group-mean pressure forecasts from Wong et al., J Gen Physiol (1977)."""
import json

# Figure 1. Starting content/pressure and terminal content come from printed group means.
# Terminal pressure was digitized from the graph; the reading half-width is 3.65 mmHg.
# Units are mL oxygen/dL finished fluid for content and mmHg for pressure.
PASSIVE = {
    "FC80": (8.03, 711.6, 7.53, 701.4056233835676),
    "Krebs": (2.23, 690.0, 1.43, 403.20008696572063),
}

# Figure 4, four preparations. Terminal tissue-loaded means and standard errors.
LOADED = {
    "FC80": {"content": 4.97, "content_se": .56, "pressure": 477.5, "pressure_se": 29.5},
    "Krebs": {"content": .40, "content_se": .06, "pressure": 153.8, "pressure_se": 26.4},
}


def main():
    results = {}
    for name, (initial_content, initial_pressure, final_content, final_pressure) in PASSIVE.items():
        fraction = final_content / initial_content
        forecast = initial_pressure * fraction
        error = abs(forecast - final_pressure)
        constant_error = abs(initial_pressure - final_pressure)
        threshold = .05 * initial_pressure
        gain = constant_error - error
        loaded_forecast = initial_pressure * LOADED[name]["content"] / initial_content
        results[name] = {
            "passive_content_fraction_retained": fraction,
            "passive_predicted_pressure_mmHg": forecast,
            "passive_observed_pressure_mmHg": final_pressure,
            "passive_error_mmHg": error,
            "constant_pressure_error_mmHg": constant_error,
            "gain_over_constant_mmHg": gain,
            "accuracy_allowance_mmHg": threshold,
            "passes_accuracy_test": error <= threshold,
            "passes_improvement_test": gain >= 15,
            "matches_both_registered_tests": error <= threshold and gain >= 15,
            "tissue_loaded_means_and_SE": LOADED[name],
            "retrospective_tissue_loaded_prediction_mmHg": loaded_forecast,
            "retrospective_tissue_loaded_error_mmHg": abs(LOADED[name]["pressure"] - loaded_forecast),
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
