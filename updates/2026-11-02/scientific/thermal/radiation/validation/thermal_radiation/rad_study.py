"""RAD-STUDY-1: predeclared small study of the outer-face radiation extension (T0-RAD-1 steady,
T0-LUMP2-RAD-1 transient).  Standard library only; deterministic; writes only to the caller-
supplied output path.  Usage: python rad_study.py OUTPUT_JSON [--overwrite]
Criteria C1-C6 and the output schema are fixed in ANALYSIS.md section 8 before execution.
Computational modelling only; no physical validation or safety claim."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thermal_radiation as tr  # noqa: E402
import reference_fixture as fx  # noqa: E402

STACKS = ("H1", "H2", "H3")
POWERS = (1, 5, 10)
H_VALUES = (3.0, 8.0, 15.0)
EPS_VALUES = (0.0, 0.1, 0.5, 0.9)
TRANSIENT_EPS = (0.0, 0.5, 0.9)
TRANSIENT_H = 8.0
DT_S = 1.0
EQUILIBRIUM_HORIZON_S, EQUILIBRIUM_DT_S = 10000.0, 10.0

# Predeclared numerical thresholds (ANALYSIS.md section 8); never relaxed after execution.
TOL = dict(balance_W=1e-9, reference_K=1e-9, reference_W=1e-9, newton_iterations=60,
           bracket_slack_K=1e-6, linearization_identity_K=1e-8, bound_B3_slack_K=1e-9,
           blocked_flux_W=1e-9, equilibrium_K=1e-8, ordering_K=1e-9, report_K=1e-5)

T_AMB_C = T_SUR_C = T_RES_C = 25.0
T25 = tr.kelvin(25.0)


def steady_row(stack, P, h, eps, blocked, eps0_surface_K):
    out = tr.nominal_steady(stack, P, h=h, eps=eps, blocked_rear=blocked)
    row = {k: out[k] for k in ("stack", "body_power_W", "sensor_power_W", "h_W_m2K", "eps", "rear_blocked",
                               "R_rej_K_W", "status", "T_H_K", "T_S_K", "T_O_K", "T_H_C", "T_S_C", "T_O_C",
                               "q_front_W", "q_conv_W", "q_rad_W", "q_rear_W", "balance_W", "node_balance_H_W",
                               "residual_front_K", "margin_surface_40C_K", "margin_internal_60C_K",
                               "comparator_label", "K_W_K", "M", "D_W")}
    row["newton"] = {k: out["newton"][k] for k in ("iterations", "bisections", "residual_W", "bracket_lo_K", "bracket_hi_K")}
    row["reservoir_heat_demand_W"] = out["q_rear_W"]
    row["linearization"] = None
    if eps > 0.0:
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs(stack, h=h, eps=eps, blocked_rear=blocked)
        Tw = front.T_sur_K
        variants = {"a_priori_eps0_mean": 0.5*(eps0_surface_K + Tw),
                    "exact_mean": 0.5*(out["T_O_K"] + Tw),
                    "cold_side": Tw}
        row["linearization"] = {}
        for name, T_m in variants.items():
            an = tr.linearization_error_analysis(R_HS, R_SO, R_rej, front, float(P), out["sensor_power_W"], T_res, T_m, exact_row=out)
            row["linearization"][name] = {k: an[k] for k in ("T_m_K", "h_r_W_m2K", "T_O_lin_K", "T_H_lin_K", "error_O_K",
                                                             "error_H_K", "predicted_error_O_K", "identity_B2_residual_K",
                                                             "identity_H_residual_K", "bound_B3_K", "bound_B3_holds",
                                                             "T_m_at_or_below_true_mean", "mean_cubic_law_K")}
    return row


def steady_grid():
    rows, blocked_rows = [], []
    for stack in STACKS:
        for h in H_VALUES:
            for P in POWERS:
                base = tr.nominal_steady(stack, P, h=h, eps=0.0)
                for eps in EPS_VALUES:
                    rows.append(steady_row(stack, P, h, eps, False, base["T_O_K"]))
            base_b = tr.nominal_steady(stack, 5, h=h, eps=0.0, blocked_rear=True)
            for eps in EPS_VALUES:
                blocked_rows.append(steady_row(stack, 5, h, eps, True, base_b["T_O_K"]))
    return rows, blocked_rows


def summarize_run(stack, eps, case, run):
    trace = run["trace"]

    def state(row):
        return dict(time_s=row["time"], H_C=tr.celsius(row["H_K"]), S_C=tr.celsius(row["S_K"]), O_C=tr.celsius(row["O_K"]),
                    front_W=row["front_W"], conv_W=row["conv_W"], rad_W=row["rad_W"], rear_W=row["rear_W"])

    peaks = {}
    for key, label in (("H_K", "peak_H"), ("S_K", "peak_S"), ("O_K", "peak_surface")):
        best = tr.trace_peak(trace, key)
        peaks[label] = dict(C=tr.celsius(best[key]), time_s=best["time"])
    samples = [state(r) for r in trace if abs(r["time"] - round(r["time"]/60.0)*60.0) < 1e-9]
    return dict(stack=stack, eps=eps, h_W_m2K=TRANSIENT_H, case=case, dt_s=DT_S, horizon_s=trace[-1]["time"],
                segments=fx.fault_segments(loss=(case == "rear_loss")), peaks=peaks,
                checkpoints={"600": state(tr.trace_at(trace, 600.0)), "900": state(tr.trace_at(trace, 900.0))},
                final=state(trace[-1]), samples_60s=samples,
                margin_surface_40C_K=40.0 - peaks["peak_surface"]["C"], margin_internal_60C_K=60.0 - peaks["peak_H"]["C"],
                comparator_label="study_comparator_only",
                energy=dict(injected_J=run["injected_J"], exported_front_J=run["exported_front_J"],
                            exported_rear_J=run["exported_rear_J"], stored_change_J=run["final_stored_energy_change_J"],
                            max_residual_abs_J=run["max_energy_residual_abs_J"], tolerance_J=run["energy_tolerance_J"],
                            within_tolerance=run["max_energy_residual_abs_J"] <= run["energy_tolerance_J"]),
                newton=dict(max_iterations=run["max_newton_iterations"], total_iterations=run["total_newton_iterations"]),
                events=run["events"], steps=run["steps"])


def transient_study():
    runs, summaries = {}, []
    for stack in STACKS:
        for eps in TRANSIENT_EPS:
            params = tr.nominal_transient(stack, h=TRANSIENT_H, eps=eps)
            for case in ("intact", "rear_loss"):
                run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=(case == "rear_loss")), DT_S)
                runs[(stack, eps, case)] = run
                summaries.append(summarize_run(stack, eps, case, run))
    equilibria = []
    for stack in STACKS:
        for eps in TRANSIENT_EPS:
            run = tr.simulate(tr.nominal_transient(stack, h=TRANSIENT_H, eps=eps), (T25, T25),
                              [dict(duration=EQUILIBRIUM_HORIZON_S, p=5.0, j=0.1)], EQUILIBRIUM_DT_S)
            steady = tr.nominal_steady(stack, 5, h=TRANSIENT_H, eps=eps)
            final = run["trace"][-1]
            equilibria.append(dict(stack=stack, eps=eps, dH_K=final["H_K"] - steady["T_H_K"], dS_K=final["S_K"] - steady["T_S_K"],
                                   dO_K=final["O_K"] - steady["T_O_K"], max_energy_residual_abs_J=run["max_energy_residual_abs_J"],
                                   energy_tolerance_J=run["energy_tolerance_J"]))
    return runs, summaries, equilibria


def evaluate_criteria(rows, blocked_rows, runs, summaries, equilibria):
    allrows = rows + blocked_rows
    c = {}
    c1 = dict(status_unique=all(r["status"] == "unique" for r in allrows),
              max_abs_balance_W=max(abs(r["balance_W"]) for r in allrows),
              max_abs_node_balance_H_W=max(abs(r["node_balance_H_W"]) for r in allrows),
              max_abs_residual_front_K=max(abs(r["residual_front_K"]) for r in allrows),
              max_newton_iterations=max(r["newton"]["iterations"] for r in allrows),
              all_in_bracket=all(r["newton"]["bracket_lo_K"] - TOL["bracket_slack_K"] <= r["T_O_K"] <= r["newton"]["bracket_hi_K"] + TOL["bracket_slack_K"] for r in allrows))
    c1["pass"] = (c1["status_unique"] and c1["max_abs_balance_W"] <= TOL["balance_W"] and c1["max_abs_node_balance_H_W"] <= TOL["balance_W"]
                  and c1["max_abs_residual_front_K"] <= TOL["balance_W"] and c1["max_newton_iterations"] <= TOL["newton_iterations"] and c1["all_in_bracket"])
    c["C1_balance_convergence"] = c1

    by_key = {(r["stack"], r["body_power_W"], r["h_W_m2K"], r["eps"], r["rear_blocked"]): r for r in allrows}
    worst_K = worst_W = 0.0
    for ref in fx.STEADY_ROWS:
        r = by_key[(ref["stack"], float(ref["body_power"]), 8.0, 0.0, ref["rear_blocked"])]
        worst_K = max(worst_K, abs(r["T_H_C"] - ref["H"]), abs(r["T_S_C"] - ref["S"]), abs(r["T_O_C"] - ref["surface"]))
        worst_W = max(worst_W, abs(r["q_front_W"] - ref["front"]), abs(r["q_rear_W"] - ref["rear"]))
    c["C2_reference_reproduction"] = dict(max_abs_temperature_difference_K=worst_K, max_abs_flux_difference_W=worst_W,
                                          pass_=None, **{"pass": worst_K <= TOL["reference_K"] and worst_W <= TOL["reference_W"]})
    del c["C2_reference_reproduction"]["pass_"]

    mono_eps = mono_h = True
    for stack in STACKS:
        for P in POWERS:
            for h in H_VALUES:
                seq = [by_key[(stack, float(P), h, e, False)] for e in EPS_VALUES]
                for a, b in zip(seq, seq[1:]):
                    mono_eps &= b["T_O_K"] < a["T_O_K"] and b["T_S_K"] < a["T_S_K"] and b["T_H_K"] < a["T_H_K"] and b["q_front_W"] > a["q_front_W"] and b["q_rear_W"] < a["q_rear_W"]
            for e in EPS_VALUES:
                seq = [by_key[(stack, float(P), h, e, False)] for h in H_VALUES]
                for a, b in zip(seq, seq[1:]):
                    mono_h &= b["T_O_K"] < a["T_O_K"] and b["T_H_K"] < a["T_H_K"] and b["q_front_W"] > a["q_front_W"]
    c["C3_monotonicity"] = dict(strict_in_eps=mono_eps, strict_in_h=mono_h, **{"pass": mono_eps and mono_h})

    lin_rows = [r for r in allrows if r["linearization"]]
    ident = max(abs(v["identity_B2_residual_K"]) for r in lin_rows for v in r["linearization"].values())
    ident_H = max(abs(v["identity_H_residual_K"]) for r in lin_rows for v in r["linearization"].values())
    b3 = all(v["bound_B3_holds"] for r in lin_rows for v in r["linearization"].values())
    hot_side = all(r["linearization"][k]["error_O_K"] >= -TOL["bound_B3_slack_K"] for r in lin_rows for k in ("exact_mean", "cold_side"))
    cubic = max(abs(r["linearization"]["exact_mean"]["error_O_K"] - r["linearization"]["exact_mean"]["mean_cubic_law_K"]) for r in lin_rows)
    max_err = {k: max(abs(r["linearization"][k]["error_O_K"]) for r in lin_rows) for k in ("a_priori_eps0_mean", "exact_mean", "cold_side")}
    c["C4_linearization"] = dict(max_identity_B2_residual_K=ident, max_identity_H_residual_K=ident_H, bound_B3_holds_everywhere=b3,
                                 mean_and_cold_coefficients_overpredict=hot_side, max_cubic_law_residual_K=cubic,
                                 max_abs_surface_error_K_by_variant=max_err,
                                 **{"pass": ident <= TOL["linearization_identity_K"] and ident_H <= TOL["linearization_identity_K"] and b3 and hot_side and cubic <= TOL["linearization_identity_K"]})

    blocked_flux = max(abs(r["q_front_W"] - (r["body_power_W"] + r["sensor_power_W"])) for r in blocked_rows)
    blocked_rear_zero = all(r["q_rear_W"] == 0.0 for r in blocked_rows)
    hotter = all(r["T_O_K"] > by_key[(r["stack"], 5.0, r["h_W_m2K"], r["eps"], False)]["T_O_K"] for r in blocked_rows)
    c["C5_blocked_rear"] = dict(max_abs_front_minus_total_source_W=blocked_flux, rear_flux_exactly_zero=blocked_rear_zero,
                                blocked_surface_hotter_than_open=hotter,
                                **{"pass": blocked_flux <= TOL["blocked_flux_W"] and blocked_rear_zero and hotter})

    energy_ok = all(s["energy"]["within_tolerance"] for s in summaries)
    order_eps = loss_warm = True
    for stack in STACKS:
        for case in ("intact", "rear_loss"):
            seq = [runs[(stack, e, case)]["trace"] for e in TRANSIENT_EPS]
            for cooler, warmer in zip(seq[1:], seq[:-1]):
                order_eps &= len(cooler) == len(warmer) and all(a["H_K"] <= b["H_K"] + TOL["ordering_K"] and a["S_K"] <= b["S_K"] + TOL["ordering_K"] and a["O_K"] <= b["O_K"] + TOL["ordering_K"] for a, b in zip(cooler, warmer))
        for e in TRANSIENT_EPS:
            loss, intact = runs[(stack, e, "rear_loss")]["trace"], runs[(stack, e, "intact")]["trace"]
            loss_warm &= all(a["H_K"] >= b["H_K"] - TOL["ordering_K"] and a["S_K"] >= b["S_K"] - TOL["ordering_K"] for a, b in zip(loss, intact))
    eq_worst = max(max(abs(e["dH_K"]), abs(e["dS_K"]), abs(e["dO_K"])) for e in equilibria)
    report_worst = 0.0
    for (stack, case), ref in fx.TRANSIENT_REPORT.items():
        trace = runs[(stack, 0.0, case)]["trace"]
        pk = tr.trace_peak(trace, "H_K")
        report_worst = max(report_worst, abs(tr.celsius(pk["H_K"]) - ref["peak_H_C"]), abs(tr.celsius(tr.trace_peak(trace, "O_K")["O_K"]) - ref["peak_surface_C"]),
                           abs(tr.celsius(trace[-1]["H_K"]) - ref["H_3600_C"]), 0.0 if pk["time"] == ref["peak_H_time_s"] else math.inf)
    c["C6_transient"] = dict(energy_within_tolerance_all_runs=energy_ok, pointwise_eps_ordering=order_eps, rear_loss_at_least_as_warm=loss_warm,
                             max_abs_equilibrium_gap_K=eq_worst, max_abs_difference_vs_coda_report_K=report_worst,
                             coda_report_dt_assumed_s=fx.TRANSIENT_REPORT_DT_ASSUMED_S,
                             max_newton_iterations=max(s["newton"]["max_iterations"] for s in summaries),
                             **{"pass": energy_ok and order_eps and loss_warm and eq_worst <= TOL["equilibrium_K"] and report_worst <= TOL["report_K"]})
    c["all_pass"] = all(c[k]["pass"] for k in c if k != "all_pass")
    return c


SCHEMA = {
    "steady_rows[]": ["stack", "body_power_W", "sensor_power_W", "h_W_m2K", "eps", "rear_blocked", "R_rej_K_W", "status",
                      "T_H_K/T_S_K/T_O_K and _C", "q_front_W (=q_conv_W+q_rad_W, outward)", "q_rear_W = reservoir_heat_demand_W (signed, H->reservoir)",
                      "balance_W", "node_balance_H_W", "residual_front_K", "newton{iterations,bisections,residual_W,bracket_lo_K,bracket_hi_K}",
                      "margin_surface_40C_K, margin_internal_60C_K (comparator_label=study_comparator_only)",
                      "linearization{a_priori_eps0_mean|exact_mean|cold_side}{T_m_K,h_r_W_m2K,T_O_lin_K,T_H_lin_K,error_O_K,error_H_K,predicted_error_O_K,identity_B2_residual_K,identity_H_residual_K,bound_B3_K,bound_B3_holds,T_m_at_or_below_true_mean,mean_cubic_law_K} or null at eps=0"],
    "transient_runs[]": ["stack", "eps", "h_W_m2K", "case intact|rear_loss", "dt_s", "horizon_s", "segments", "peaks{peak_H,peak_S,peak_surface}{C,time_s}",
                         "checkpoints{600,900}", "final", "samples_60s[]", "margins (study_comparator_only)", "energy{...,within_tolerance}", "newton", "events", "steps"],
    "equilibrium_checks[]": ["stack", "eps", "dH_K", "dS_K", "dO_K", "max_energy_residual_abs_J", "energy_tolerance_J"],
    "criteria_results": "C1..C6 with pass flags and the measured quantities; all_pass",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="output JSON path (only file written)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() and not args.overwrite:
        raise SystemExit("Refusing to overwrite existing results; pass --overwrite")
    rows, blocked_rows = steady_grid()
    runs, summaries, equilibria = transient_study()
    criteria = evaluate_criteria(rows, blocked_rows, runs, summaries, equilibria)
    here = Path(__file__).resolve().parent
    record = dict(
        study_id="RAD-STUDY-1", contract="T0-HYP-1 (unchanged) + labelled extension T0-RAD-1 / T0-LUMP2-RAD-1",
        status="executed_synthetic_study", physical_validation=False, safety_certification=False,
        provenance="Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton; references by Coda (Codex Lily)",
        assumptions=["emissivity eps is an assumed study parameter, not a material property",
                     "convection h is an assumed coefficient, not measured or derived from airflow",
                     "radiative surroundings at T_amb = 25 C; unit view factor; grey diffuse surface; no sky/enclosure model",
                     "outer surface massless and isothermal (quasi-steady), as in T0-LUMP2-1",
                     "C_H = 20 J/K and C_S from T0-LUMP2-1 are hypothetical storage values",
                     "Coda REPORT cross-check assumes its scenario dt = 1 s (not stated in the source)",
                     "rear reservoir is an ideal boundary; its heat demand is reported, its realization is unmodeled",
                     "40 C / 60 C are arbitrary study comparators (study_comparator_only), not limits"],
        constants=dict(sigma_W_m2K4=tr.SIGMA_W_M2K4, area_m2=tr.AREA_M2, T_amb_C=T_AMB_C, T_sur_C=T_SUR_C, T_res_C=T_RES_C,
                       R_rej_K_W=tr.NOMINAL_R_REJ_K_W, P_sensor_W=tr.NOMINAL_SENSOR_POWER_W, C_H_J_K=tr.NOMINAL_C_H_J_K,
                       C_S_J_K={s: tr.nominal_panel_capacity(s) for s in STACKS},
                       R_HS_K_W={s: float(tr.exact_stack_resistances(s)["R_HS"]) for s in STACKS}),
        design=dict(stacks=STACKS, body_power_W=POWERS, h_W_m2K=H_VALUES, eps=EPS_VALUES, blocked_rear_power_W=5,
                    transient_eps=TRANSIENT_EPS, transient_h_W_m2K=TRANSIENT_H, dt_s=DT_S, schedule="5 W to 900 s then 0; 0.1 W sensor throughout; rear loss at 600 s in loss cases",
                    equilibrium_check=dict(horizon_s=EQUILIBRIUM_HORIZON_S, dt_s=EQUILIBRIUM_DT_S), tolerances=TOL),
        steady_rows=rows, blocked_rear_rows=blocked_rows, transient_runs=summaries, equilibrium_checks=equilibria,
        criteria_results=criteria, schema=SCHEMA,
        source_sha256={"thermal_radiation.py": hashlib.sha256((here/"thermal_radiation.py").read_bytes()).hexdigest(),
                       "rad_study.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "reference_fixture.py": hashlib.sha256((here/"reference_fixture.py").read_bytes()).hexdigest()})
    output.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), steady_rows=len(rows), blocked_rows=len(blocked_rows), transient_runs=len(summaries),
                          criteria={k: (v["pass"] if isinstance(v, dict) else v) for k, v in criteria.items()}), indent=1))
    print("stack eps   T_O_C        T_H_C        q_front_W    q_rear_W   (P=5 W, h=8)")
    for r in rows:
        if r["body_power_W"] == 5.0 and r["h_W_m2K"] == 8.0 and r["eps"] in (0.0, 0.5, 0.9):
            print(f'{r["stack"]}   {r["eps"]:.1f} {r["T_O_C"]:12.6f} {r["T_H_C"]:12.6f} {r["q_front_W"]:12.6f} {r["q_rear_W"]:10.6f}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
