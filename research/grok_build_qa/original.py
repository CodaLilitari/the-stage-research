#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Toy screen: pump power versus oxygen transport.

Hypothetical engineering inequalities. Every entry in ASSUMPTIONS is an
assumed input. Nothing in this file is a measurement, a biological
constant, or a calibration to a device.

Run:
    python toy_perfusion_screen.py

Writes:
    toy_perfusion_out/sweep.csv
    toy_perfusion_out/screen.json
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path


# Unit definitions, not device data.
LBF_IN_NEWTONS = 4.4482216152605
INCH_IN_METRES = 0.0254
PSI_TO_PA = LBF_IN_NEWTONS / (INCH_IN_METRES ** 2)


def validate_efficiency(eta: float) -> float:
    if not math.isfinite(eta) or eta <= 0.0 or eta > 1.0:
        raise ValueError(
            "eta must lie in (0, 1]; eta > 1 puts hydraulic power above electrical input"
        )
    return float(eta)


def validate_nonnegative(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")
    return float(value)


def hydraulic_power(delta_p_pa: float, q_m3_s: float) -> float:
    """P_hyd = delta_p * Q. Pa * m^3/s = W."""
    return float(delta_p_pa) * float(q_m3_s)


def electrical_power(delta_p_pa: float, q_m3_s: float, eta: float) -> float:
    """P_elec = delta_p * Q / eta."""
    return hydraulic_power(delta_p_pa, q_m3_s) / validate_efficiency(eta)


def linear_delta_p(resistance_pa_s_per_m3: float, q_m3_s: float) -> float:
    resistance_pa_s_per_m3 = validate_nonnegative("resistance", resistance_pa_s_per_m3)
    q_m3_s = validate_nonnegative("flow", q_m3_s)
    return resistance_pa_s_per_m3 * q_m3_s


def carrier_capacity_mol_s(q_m3_s: float, c_in_mol_m3: float) -> float:
    """Single-pass upper bound Q * C_in."""
    q_m3_s = validate_nonnegative("flow", q_m3_s)
    c_in_mol_m3 = validate_nonnegative("c_in", c_in_mol_m3)
    return q_m3_s * c_in_mol_m3


def delivered_oxygen_mol_s(q_m3_s: float, c_in_mol_m3: float, c_out_mol_m3: float) -> float:
    """J = Q * (C_in - C_out) for one control volume. Report this once per volume."""
    q_m3_s = validate_nonnegative("flow", q_m3_s)
    c_in_mol_m3 = validate_nonnegative("c_in", c_in_mol_m3)
    c_out_mol_m3 = validate_nonnegative("c_out", c_out_mol_m3)
    if c_out_mol_m3 > c_in_mol_m3 + 1e-15:
        raise ValueError("c_out exceeds c_in")
    return q_m3_s * (c_in_mol_m3 - c_out_mol_m3)


def q_min_for_demand(demand_mol_s: float, alpha_max: float, c_in_mol_m3: float) -> float:
    """Smallest Q with alpha_max * Q * C_in >= demand. inf if that factor is 0 and demand > 0."""
    demand_mol_s = validate_nonnegative("demand", demand_mol_s)
    if not math.isfinite(alpha_max) or alpha_max <= 0.0 or alpha_max > 1.0:
        raise ValueError("alpha_max must lie in (0, 1]")
    c_in_mol_m3 = validate_nonnegative("c_in", c_in_mol_m3)
    if demand_mol_s == 0.0:
        return 0.0
    factor = alpha_max * c_in_mol_m3
    if factor == 0.0:
        return math.inf
    return demand_mol_s / factor


def q_max_for_power_linear(eta: float, p_elec_max_w: float, resistance: float) -> float:
    """P_elec = R Q^2 / eta <= P_elec_max. R == 0 yields inf."""
    eta = validate_efficiency(eta)
    p_elec_max_w = validate_nonnegative("p_elec_max", p_elec_max_w)
    resistance = validate_nonnegative("resistance", resistance)
    if resistance == 0.0:
        return math.inf
    return math.sqrt(eta * p_elec_max_w / resistance)


def q_max_for_power_fixed_dp(eta: float, p_elec_max_w: float, delta_p_pa: float) -> float:
    """P_elec = delta_p * Q / eta <= P_elec_max. delta_p == 0 yields inf."""
    eta = validate_efficiency(eta)
    p_elec_max_w = validate_nonnegative("p_elec_max", p_elec_max_w)
    delta_p_pa = validate_nonnegative("delta_p", delta_p_pa)
    if delta_p_pa == 0.0:
        return math.inf
    return eta * p_elec_max_w / delta_p_pa


def _interval_or_empty(q_lo: float, q_hi: float):
    if math.isinf(q_lo):
        return None
    if math.isinf(q_hi):
        return (q_lo, math.inf)
    if q_lo > q_hi and not math.isclose(q_lo, q_hi, rel_tol=1e-12, abs_tol=1e-15):
        return None
    if q_lo > q_hi:
        q_lo = q_hi
    return (q_lo, q_hi)


def feasible_interval_linear(demand, alpha_max, c_in, eta, p_elec_max, resistance):
    return _interval_or_empty(
        q_min_for_demand(demand, alpha_max, c_in),
        q_max_for_power_linear(eta, p_elec_max, resistance),
    )


def feasible_interval_fixed_dp(demand, alpha_max, c_in, eta, p_elec_max, delta_p):
    return _interval_or_empty(
        q_min_for_demand(demand, alpha_max, c_in),
        q_max_for_power_fixed_dp(eta, p_elec_max, delta_p),
    )


def gamma_linear(demand, alpha_max, c_in, eta, p_elec_max, resistance):
    """Nonempty global linear interval iff Gamma >= 1, for M > 0 and R > 0."""
    if demand < 0 or resistance < 0 or c_in < 0 or p_elec_max < 0:
        raise ValueError("gamma inputs must be nonnegative")
    validate_efficiency(eta)
    if not (0.0 < alpha_max <= 1.0):
        raise ValueError("alpha_max must lie in (0, 1]")
    if demand == 0.0:
        return math.inf
    if resistance == 0.0:
        return math.inf if alpha_max * c_in > 0.0 else 0.0
    if alpha_max * c_in == 0.0 or p_elec_max == 0.0:
        return 0.0
    return (alpha_max ** 2) * (c_in ** 2) * eta * p_elec_max / (demand ** 2 * resistance)


def global_supply_met(q, c_in, alpha_max, demand) -> bool:
    if demand == 0.0:
        return True
    return alpha_max * q * c_in >= demand


def branch_delivered(q, phi, c_in, alpha_max, ceiling_mol_s) -> float:
    if phi < 0.0:
        raise ValueError("flow fraction must be >= 0")
    if ceiling_mol_s < 0.0:
        raise ValueError("ceiling must be >= 0")
    return min(phi * q * alpha_max * c_in, ceiling_mol_s)


def local_supply_met(q, phis, c_in, alpha_max, ceilings, demands) -> bool:
    if len(phis) != len(ceilings) or len(phis) != len(demands):
        raise ValueError("branch arrays differ in length")
    if phis and abs(sum(phis) - 1.0) > 1e-12:
        raise ValueError("flow fractions must sum to 1")
    for phi, ceiling, demand in zip(phis, ceilings, demands):
        if branch_delivered(q, phi, c_in, alpha_max, ceiling) + 1e-15 < demand:
            return False
    return True


def model_survival_flag(global_ok, local_ok, power_ok) -> bool:
    """Boolean of the toy inequalities. Not a biological outcome."""
    return bool(global_ok and local_ok and power_ok)


def power_ok_linear(q, eta, p_elec_max, resistance) -> bool:
    delta_p = linear_delta_p(resistance, q)
    p_elec = electrical_power(delta_p, q, eta)
    return p_elec <= p_elec_max + 1e-12 * max(1.0, p_elec_max)


def series_path(q, c_in, requested_drops, ceilings):
    """Each segment inlet is the upstream outlet. Delivery is stored once."""
    q = validate_nonnegative("flow", q)
    c = validate_nonnegative("c_in", c_in)
    deliveries = []
    inlets = []
    for drop, ceiling in zip(requested_drops, ceilings):
        if drop < 0.0 or ceiling < 0.0:
            raise ValueError("drop and ceiling must be >= 0")
        inlets.append(c)
        if q == 0.0:
            taken = 0.0
        else:
            taken = min(drop, c, ceiling / q)
        deliveries.append(q * taken)
        c = c - taken
    delivered_once = sum(deliveries)
    return {
        "segment_inlet_mol_m3": inlets,
        "segment_delivery_mol_s": deliveries,
        "delivered_once_mol_s": delivered_once,
        "end_to_end_mol_s": q * (c_in - c),
        "carrier_capacity_mol_s": q * c_in,
        "path_outlet_mol_m3": c,
    }


ASSUMPTIONS = {
    "label": "hypothetical_round_values",
    "status": "assumed_not_measured",
    "resistance_Pa_s_per_m3": 1.0e8,
    "eta": 0.5,
    "p_elec_max_W": 10.0,
    "alpha_max": 1.0,
    "demand_mol_s": 2.0e-6,
    "branch_demands_mol_s": [1.0e-6, 1.0e-6],
    "c_in_reference_mol_m3": 1.0,
    "c_in_low_mol_m3": 1.0e-3,
    "c_in_high_mol_m3": 1.0e3,
    "equal_split": [0.5, 0.5],
    "ceilings_open_mol_s": [1.0e-2, 1.0e-2],
    "ceilings_blocking_mol_s": [1.0e-2, 5.0e-7],
    "stagnant_split": [1.0, 0.0],
    "fixed_delta_p_Pa": 1.0e5,
}


def _json_ready(value):
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
        return value
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def conditional_nameplate():
    """Conditional arithmetic on unverified nameplate text. Not an operating point."""
    q_if_actual_liquid = 40.0 * 1.0e-3 / 60.0
    delta_p = 100.0 * PSI_TO_PA
    p_hyd = hydraulic_power(delta_p, q_if_actual_liquid)
    p_elec_claim_w = 500.0
    return {
        "status": "conditional_unit_arithmetic_on_unverified_claims",
        "figures_are_measurements": False,
        "simultaneous_operating_point_known": False,
        "used_as_calibration": False,
        "slpm_note": (
            "SLPM is a gas-metrology unit. Reading 40 SLPM as 40 actual "
            "liquid L/min is an extra assumption."
        ),
        "hydraulic_power_uses": "actual volumetric flow, P_hyd = delta_p * Q_actual",
        "interpretation_actual_liquid_L_per_min": {
            "Q_m3_s": q_if_actual_liquid,
            "delta_p_Pa": delta_p,
            "P_hyd_W": p_hyd,
            "claimed_P_elec_W": p_elec_claim_w,
            "implied_eta_if_these_three_were_one_point": p_hyd / p_elec_claim_w,
        },
        "interpretation_gas_SLPM": {
            "Q_actual_m3_s": None,
            "P_hyd_W": None,
            "reason": (
                "Standard gas flow equals actual volume flow only at the "
                "meter standard state. delta_p * Q_standard is not hydraulic power."
            ),
        },
        "rating_product_note": (
            "Nameplate max pressure and nameplate max flow are separate ratings. "
            "On a falling pump curve their product exceeds delta_p * Q at a real point."
        ),
    }


def cornell_note():
    return {
        "item": "Cornell 2019 soft robotic fish",
        "relevance_to_this_screen": (
            "Electrochemical storage plus hydraulic actuation. "
            "It supplies no parameter for this perfusion screen."
        ),
    }


def run_checks(a):
    checks = []

    def record(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    record(
        "dimensions_power_and_molar_flow",
        hydraulic_power(1.0, 1.0) == 1.0
        and electrical_power(1.0, 1.0, 1.0) == 1.0
        and carrier_capacity_mol_s(2.0, 3.0) == 6.0
        and delivered_oxygen_mol_s(2.0, 3.0, 1.0) == 4.0,
        "Pa*m^3/s -> W and mol/m^3 * m^3/s -> mol/s",
    )

    rejected = []
    for bad in (0.0, -0.1, 1.01, 2.0, math.inf, math.nan):
        try:
            validate_efficiency(bad)
            rejected.append(bad)
        except ValueError:
            pass
    record("efficiency_rejects_outside_0_1", rejected == [], f"accepted invalid: {rejected}")
    record(
        "efficiency_one_equates_electrical_and_hydraulic",
        electrical_power(250.0, 0.004, 1.0) == hydraulic_power(250.0, 0.004),
        "eta=1 => P_elec = P_hyd",
    )
    p_hyd = hydraulic_power(200.0, 0.01)
    p_elec = electrical_power(200.0, 0.01, 0.25)
    record(
        "efficiency_loss_is_nonnegative",
        math.isclose(p_elec, p_hyd / 0.25) and p_elec >= p_hyd,
        "P_elec - P_hyd >= 0 for eta in (0, 1]",
    )

    record(
        "zero_demand_q_min_is_zero_even_if_capacity_zero",
        q_min_for_demand(0.0, 1.0, 0.0) == 0.0,
        "Q_min(M=0)=0",
    )
    record(
        "zero_demand_oxygen_met_at_zero_flow",
        global_supply_met(0.0, 0.0, 1.0, 0.0),
        "J=0 meets M=0",
    )
    record(
        "branch_demands_sum_to_module_demand",
        math.isclose(sum(a["branch_demands_mol_s"]), a["demand_mol_s"]),
        "M = sum m_i",
    )

    record(
        "zero_capacity_positive_demand_has_no_finite_flow",
        math.isinf(q_min_for_demand(1.0e-6, 1.0, 0.0)),
        "C_in=0 and M>0 => Q_min = inf",
    )
    record(
        "zero_capacity_global_fails_at_large_flow",
        not global_supply_met(1.0e3, 0.0, 1.0, 1.0e-9),
        "Q*C_in = 0 < M",
    )

    resistance = a["resistance_Pa_s_per_m3"]
    eta = a["eta"]
    record(
        "zero_flow_power_is_zero",
        hydraulic_power(linear_delta_p(resistance, 0.0), 0.0) == 0.0
        and electrical_power(0.0, 0.0, eta) == 0.0,
        "Q=0 => P_hyd = P_elec = 0",
    )
    record(
        "zero_flow_meets_demand_only_when_demand_is_zero",
        (not global_supply_met(0.0, a["c_in_reference_mol_m3"], 1.0, a["demand_mol_s"]))
        and global_supply_met(0.0, a["c_in_reference_mol_m3"], 1.0, 0.0),
        "delivered oxygen rate is 0 at Q=0",
    )
    record(
        "zero_flow_separates_power_from_survival",
        electrical_power(0.0, 0.0, 1.0) == 0.0
        and model_survival_flag(global_supply_met(0.0, 1.0, 1.0, 1.0e-6), False, True) is False,
        "P_elec=0 can coexist with survival flag False",
    )

    qs = [0.0, 1.0e-6, 1.0e-5, 2.0e-5, 1.0e-4]
    powers = [electrical_power(linear_delta_p(resistance, q), q, eta) for q in qs]
    record(
        "monotonic_pump_cost_fixed_resistance",
        all(powers[i] < powers[i + 1] for i in range(len(powers) - 1)),
        f"P_elec sequence {powers}",
    )
    q = 1.0e-5
    p1 = electrical_power(linear_delta_p(resistance, q), q, eta)
    p2 = electrical_power(linear_delta_p(resistance, 2.0 * q), 2.0 * q, eta)
    record(
        "quadratic_scaling_fixed_resistance",
        math.isclose(p2 / p1, 4.0, rel_tol=1e-12),
        "P(2Q)/P(Q) = 4 because P = R Q^2 / eta",
    )
    record(
        "analytic_derivative_positive",
        (2.0 * resistance * q / eta) > 0.0,
        "dP_elec/dQ = 2 R Q / eta",
    )
    fixed_powers = [electrical_power(1.0e5, flow, eta) for flow in (0.0, 1.0e-5, 2.0e-5)]
    record(
        "monotonic_pump_cost_fixed_delta_p",
        fixed_powers[0] < fixed_powers[1] < fixed_powers[2]
        and math.isclose(fixed_powers[1] * 2.0, fixed_powers[2], rel_tol=1e-12),
        "at fixed delta_p > 0, P scales linearly with Q",
    )

    record(
        "necessary_global_condition_catches_shortfall",
        not global_supply_met(1.0e-6, 1.0, 1.0, 1.1e-6),
        "Q*C_in < M => not met",
    )
    record(
        "carrier_upper_bound",
        delivered_oxygen_mol_s(0.2, 5.0, 0.0) <= carrier_capacity_mol_s(0.2, 5.0),
        "J <= Q*C_in when C_out >= 0",
    )

    interval = feasible_interval_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"],
        eta, a["p_elec_max_W"], resistance,
    )
    q_lo, q_hi = interval
    mid = 0.5 * (q_lo + q_hi)
    record("reference_interval_nonempty", q_lo <= q_hi, f"[{q_lo}, {q_hi}]")
    record(
        "q_min_meets_demand_exactly",
        math.isclose(a["alpha_max"] * a["c_in_reference_mol_m3"] * q_lo, a["demand_mol_s"], rel_tol=1e-12),
        "alpha*C*Q_min = M",
    )
    p_at_hi = electrical_power(linear_delta_p(resistance, q_hi), q_hi, eta)
    record(
        "q_max_meets_power_exactly",
        math.isclose(p_at_hi, a["p_elec_max_W"], rel_tol=1e-12),
        f"P_elec(Q_max)={p_at_hi}",
    )
    record(
        "interior_point_meets_global_power_and_oxygen",
        global_supply_met(mid, a["c_in_reference_mol_m3"], a["alpha_max"], a["demand_mol_s"])
        and power_ok_linear(mid, eta, a["p_elec_max_W"], resistance),
        "midpoint of the closed-form interval",
    )
    below = q_lo * (1.0 - 1.0e-6)
    record(
        "just_below_q_min_fails_oxygen",
        not global_supply_met(below, a["c_in_reference_mol_m3"], a["alpha_max"], a["demand_mol_s"]),
        f"Q={below}",
    )
    above = q_hi * (1.0 + 1.0e-6)
    record(
        "just_above_q_max_fails_power",
        not power_ok_linear(above, eta, a["p_elec_max_W"], resistance),
        f"Q={above}",
    )

    low = feasible_interval_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_low_mol_m3"], eta, a["p_elec_max_W"], resistance
    )
    high = feasible_interval_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_high_mol_m3"], eta, a["p_elec_max_W"], resistance
    )
    g_low = gamma_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_low_mol_m3"], eta, a["p_elec_max_W"], resistance
    )
    g_ref = gamma_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"], eta, a["p_elec_max_W"], resistance
    )
    record("low_carrier_gamma_below_one", g_low < 1.0 and low is None, f"Gamma={g_low}")
    record("reference_carrier_gamma_above_one", g_ref >= 1.0 and interval is not None, f"Gamma={g_ref}")
    record("higher_carrier_can_open_global_interval", high is not None, "global power limit only")

    blocked = []
    for c_value in (a["c_in_low_mol_m3"], a["c_in_reference_mol_m3"], a["c_in_high_mol_m3"], 1.0e9):
        for q_value in (0.0, q_hi, 1.0e3):
            blocked.append(
                local_supply_met(
                    q_value, a["equal_split"], c_value, a["alpha_max"],
                    a["ceilings_blocking_mol_s"], a["branch_demands_mol_s"],
                )
            )
    record(
        "more_carrier_does_not_clear_local_ceiling",
        not any(blocked),
        "branch 2 demand 1e-6 > ceiling 5e-7 at every tested Q and C_in",
    )
    record(
        "global_budget_can_pass_while_local_fails",
        global_supply_met(mid, a["c_in_reference_mol_m3"], a["alpha_max"], a["demand_mol_s"])
        and not local_supply_met(
            mid, a["equal_split"], a["c_in_reference_mol_m3"], a["alpha_max"],
            a["ceilings_blocking_mol_s"], a["branch_demands_mol_s"],
        ),
        "interval midpoint, blocking ceiling",
    )
    record(
        "stagnant_branch_stays_unsupplied",
        not local_supply_met(
            q_hi, a["stagnant_split"], a["c_in_high_mol_m3"], a["alpha_max"],
            a["ceilings_open_mol_s"], a["branch_demands_mol_s"],
        ),
        "phi_2 = 0 => delivery_2 = 0 for any finite C_in",
    )
    record(
        "open_ceilings_pass_inside_interval",
        local_supply_met(
            mid, a["equal_split"], a["c_in_reference_mol_m3"], a["alpha_max"],
            a["ceilings_open_mol_s"], a["branch_demands_mol_s"],
        ),
        "equal split, ceilings above branch demand",
    )

    path = series_path(0.01, 1.0, [0.2, 0.3, 0.1], [1.0, 1.0, 1.0])
    record(
        "series_sum_equals_end_to_end",
        math.isclose(path["delivered_once_mol_s"], path["end_to_end_mol_s"], rel_tol=1e-12)
        and math.isclose(path["delivered_once_mol_s"], 0.006, rel_tol=1e-12),
        "drops 0.2+0.3+0.1 at Q=0.01",
    )
    double_counted = path["delivered_once_mol_s"] + path["end_to_end_mol_s"]
    record(
        "double_count_would_exceed_carrier",
        double_counted > path["carrier_capacity_mol_s"]
        and path["delivered_once_mol_s"] <= path["carrier_capacity_mol_s"] + 1e-15,
        "the screen keeps a single delivered total",
    )
    depleted = series_path(0.02, 1.0, [0.8, 0.8], [10.0, 10.0])
    record(
        "downstream_inlet_is_upstream_outlet",
        math.isclose(depleted["segment_inlet_mol_m3"][1], 0.2, rel_tol=1e-12)
        and math.isclose(depleted["delivered_once_mol_s"], 0.02, rel_tol=1e-12),
        "second inlet is 0.2; total delivery equals Q*C_in",
    )
    capped = series_path(0.05, 1.0, [1.0, 1.0], [1.0e-4, 10.0])
    record(
        "segment_ceiling_limits_extraction_before_downstream",
        math.isclose(capped["segment_delivery_mol_s"][0], 1.0e-4, rel_tol=1e-12)
        and math.isclose(capped["segment_inlet_mol_m3"][1], 0.998, rel_tol=1e-12)
        and math.isclose(capped["delivered_once_mol_s"], capped["end_to_end_mol_s"], rel_tol=1e-12),
        "first segment stops at its ceiling",
    )
    stagnant_path = series_path(0.0, 1.0, [0.5, 0.5], [10.0, 10.0])
    record(
        "series_zero_flow_delivers_nothing",
        stagnant_path["delivered_once_mol_s"] == 0.0
        and math.isclose(stagnant_path["path_outlet_mol_m3"], 1.0),
        "no flow extraction term at Q=0",
    )

    fixed = feasible_interval_fixed_dp(
        a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"],
        eta, a["p_elec_max_W"], a["fixed_delta_p_Pa"],
    )
    record(
        "fixed_pressure_interval_matches_formula",
        fixed is not None
        and math.isclose(fixed[0], a["demand_mol_s"] / a["c_in_reference_mol_m3"], rel_tol=1e-12)
        and math.isclose(fixed[1], eta * a["p_elec_max_W"] / a["fixed_delta_p_Pa"], rel_tol=1e-12),
        f"interval={fixed}",
    )

    q_star = q_max_for_power_linear(eta, a["p_elec_max_W"], resistance)
    demand_star = a["alpha_max"] * a["c_in_reference_mol_m3"] * q_star
    singleton = feasible_interval_linear(
        demand_star, a["alpha_max"], a["c_in_reference_mol_m3"], eta, a["p_elec_max_W"], resistance
    )
    record(
        "singleton_interval_when_gamma_is_one",
        singleton is not None
        and math.isclose(singleton[0], singleton[1], rel_tol=1e-12)
        and math.isclose(
            gamma_linear(
                demand_star, a["alpha_max"], a["c_in_reference_mol_m3"],
                eta, a["p_elec_max_W"], resistance,
            ),
            1.0,
            rel_tol=1e-12,
        ),
        f"Q*={q_star}",
    )
    record(
        "zero_power_ceiling_only_allows_zero_flow",
        feasible_interval_linear(0.0, 1.0, 1.0, eta, 0.0, resistance) == (0.0, 0.0)
        and feasible_interval_linear(1.0e-9, 1.0, 1.0, eta, 0.0, resistance) is None,
        "P_elec_max = 0 => Q_max = 0",
    )

    plate = conditional_nameplate()
    record(
        "nameplate_not_used_as_calibration",
        plate["used_as_calibration"] is False
        and plate["figures_are_measurements"] is False
        and plate["simultaneous_operating_point_known"] is False
        and a["p_elec_max_W"] != 500.0
        and a["resistance_Pa_s_per_m3"] == 1.0e8,
        "toy R and P_elec_max stay on assumed values",
    )
    liquid = plate["interpretation_actual_liquid_L_per_min"]
    q_hand = 40.0 / 60.0 / 1000.0
    p_hand = 100.0 * PSI_TO_PA * q_hand
    record(
        "conditional_liquid_product_is_delta_p_times_Q",
        math.isclose(liquid["Q_m3_s"], q_hand, rel_tol=1e-12)
        and math.isclose(liquid["P_hyd_W"], p_hand, rel_tol=1e-12)
        and plate["interpretation_gas_SLPM"]["P_hyd_W"] is None,
        "liquid reading is delta_p * Q; gas SLPM reading stays undefined",
    )

    dp = linear_delta_p(resistance, mid)
    p_h = hydraulic_power(dp, mid)
    p_e = electrical_power(dp, mid, eta)
    carrier = carrier_capacity_mol_s(mid, a["c_in_reference_mol_m3"])
    delivered_available = a["alpha_max"] * carrier
    partial = delivered_oxygen_mol_s(mid, a["c_in_reference_mol_m3"], 0.25 * a["c_in_reference_mol_m3"])
    g_ok = global_supply_met(mid, a["c_in_reference_mol_m3"], a["alpha_max"], a["demand_mol_s"])
    l_ok = local_supply_met(
        mid, a["equal_split"], a["c_in_reference_mol_m3"], a["alpha_max"],
        a["ceilings_open_mol_s"], a["branch_demands_mol_s"],
    )
    record(
        "five_quantities_are_separately_defined",
        math.isclose(p_e, p_h / eta) and p_e > p_h > 0.0
        and math.isclose(delivered_available, carrier)
        and partial < carrier
        and math.isclose(partial, 0.75 * carrier, rel_tol=1e-12)
        and model_survival_flag(g_ok, l_ok, True) is True,
        "P_elec, P_hyd, carrier, partial delivery, survival flag",
    )
    record(
        "survival_flag_can_fail_at_unchanged_power",
        model_survival_flag(
            g_ok,
            local_supply_met(
                mid, a["equal_split"], a["c_in_reference_mol_m3"], a["alpha_max"],
                a["ceilings_blocking_mol_s"], a["branch_demands_mol_s"],
            ),
            True,
        ) is False,
        "local ceiling flips the flag without changing P_elec",
    )
    return checks


def sweep_rows(a):
    eta = a["eta"]
    resistance = a["resistance_Pa_s_per_m3"]
    p_max = a["p_elec_max_W"]
    alpha = a["alpha_max"]
    demand = a["demand_mol_s"]
    q_hi_ref = q_max_for_power_linear(eta, p_max, resistance)
    q_values = [0.0] + [1.1 * q_hi_ref * k / 20.0 for k in range(1, 21)]
    scenarios = [
        ("open_local_reference_C", a["c_in_reference_mol_m3"], a["equal_split"], a["ceilings_open_mol_s"]),
        ("blocking_ceiling_reference_C", a["c_in_reference_mol_m3"], a["equal_split"], a["ceilings_blocking_mol_s"]),
        ("low_C_open_local", a["c_in_low_mol_m3"], a["equal_split"], a["ceilings_open_mol_s"]),
        ("high_C_blocking_ceiling", a["c_in_high_mol_m3"], a["equal_split"], a["ceilings_blocking_mol_s"]),
        ("stagnant_branch_high_C", a["c_in_high_mol_m3"], a["stagnant_split"], a["ceilings_open_mol_s"]),
    ]
    rows = []
    for name, c_in, phis, ceilings in scenarios:
        interval = feasible_interval_linear(demand, alpha, c_in, eta, p_max, resistance)
        gval = gamma_linear(demand, alpha, c_in, eta, p_max, resistance)
        q_lo = None if interval is None else interval[0]
        q_hi = None if interval is None else interval[1]
        for q in q_values:
            dp = linear_delta_p(resistance, q)
            carrier = carrier_capacity_mol_s(q, c_in)
            delivered = alpha * carrier
            g_ok = global_supply_met(q, c_in, alpha, demand)
            l_ok = local_supply_met(q, phis, c_in, alpha, ceilings, a["branch_demands_mol_s"])
            pow_ok = power_ok_linear(q, eta, p_max, resistance)
            in_interval = False
            if interval is not None:
                hi = interval[1]
                in_interval = (q >= interval[0] - 1e-15) and (math.isinf(hi) or q <= hi + 1e-15)
            rows.append({
                "scenario": name,
                "parameter_status": "assumed",
                "Q_m3_s": q,
                "C_in_mol_m3": c_in,
                "delta_p_Pa": dp,
                "P_hyd_W": hydraulic_power(dp, q),
                "eta": eta,
                "P_elec_W": electrical_power(dp, q, eta),
                "carrier_capacity_mol_s": carrier,
                "delivered_available_mol_s": delivered,
                "demand_mol_s": demand,
                "Gamma_global_linear": gval,
                "Q_min_m3_s": q_lo,
                "Q_max_m3_s": q_hi,
                "in_closed_form_global_interval": in_interval,
                "global_supply_met": g_ok,
                "local_supply_met": l_ok,
                "power_met": pow_ok,
                "model_survival_flag": model_survival_flag(g_ok, l_ok, pow_ok),
            })
    return rows


def write_outputs(checks, rows, plate):
    out_dir = Path("toy_perfusion_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "sweep.csv"
    json_path = out_dir / "screen.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: value if isinstance(value, bool) else _json_ready(value)
                    for key, value in row.items()
                }
            )
    a = ASSUMPTIONS
    interval = feasible_interval_linear(
        a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"],
        a["eta"], a["p_elec_max_W"], a["resistance_Pa_s_per_m3"],
    )
    payload = {
        "screen": "toy_pump_power_vs_oxygen_transport",
        "execution_note": "computed_* fields are filled by running this script",
        "biological_realism_claimed": False,
        "clinical_or_wetlab_design": False,
        "units": {
            "flow": "m^3/s",
            "pressure": "Pa",
            "resistance": "Pa*s/m^3",
            "power": "W",
            "oxygen_content": "mol/m^3 total oxygen per liquid volume, declared",
            "oxygen_rate": "mol/s",
            "efficiency": "1",
        },
        "identities": {
            "P_hyd_W": "delta_p_Pa * Q_m3_s",
            "P_elec_W": "P_hyd_W / eta",
            "delta_p_linear_Pa": "R * Q",
            "carrier_capacity_mol_s": "Q * C_in",
            "delivered_available_mol_s": "alpha_max * Q * C_in",
            "global_necessary_condition": "Q * C_in >= M, and alpha_max * Q * C_in >= M",
            "Gamma": "(alpha_max^2 * C_in^2 * eta * P_elec_max) / (M^2 * R)",
            "model_survival_flag": "global_supply_met AND local_supply_met AND power_met",
        },
        "assumptions": a,
        "computed_reference_interval_linear_m3_s": None if interval is None else list(interval),
        "computed_reference_gamma": gamma_linear(
            a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"],
            a["eta"], a["p_elec_max_W"], a["resistance_Pa_s_per_m3"],
        ),
        "computed_q_max_m3_s": q_max_for_power_linear(
            a["eta"], a["p_elec_max_W"], a["resistance_Pa_s_per_m3"]
        ),
        "computed_q_min_reference_m3_s": q_min_for_demand(
            a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"]
        ),
        "nameplate_conditional": plate,
        "cornell_2019_soft_fish": cornell_note(),
        "checks": checks,
        "limitations": [
            "Steady incompressible flow, constant eta, linear resistance or fixed delta_p.",
            "Oxygen balance is one pass of total content C. A recycle loop needs an explicit oxygenator balance before another pass is credited.",
            "Segment deliveries and the end-to-end drop are the same oxygen and are stored once.",
            "Local ceilings and flow fractions are independent assumed numbers.",
            "The survival flag is the inequality boolean only.",
            "Nameplate 500 W, 40 SLPM and 100 psi are unverified claims, not a simultaneous point, and do not set R, eta, or demand.",
            "Heat from pump losses is not coupled into the module.",
            "No solubility, binding curve, metabolism data set, culture method, or clinical target is used.",
        ],
    }
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(payload), handle, indent=2)
        handle.write("\n")
    return csv_path, json_path


def main():
    checks = run_checks(ASSUMPTIONS)
    rows = sweep_rows(ASSUMPTIONS)
    plate = conditional_nameplate()
    csv_path, json_path = write_outputs(checks, rows, plate)
    a = ASSUMPTIONS
    q_lo = q_min_for_demand(a["demand_mol_s"], a["alpha_max"], a["c_in_reference_mol_m3"])
    q_hi = q_max_for_power_linear(a["eta"], a["p_elec_max_W"], a["resistance_Pa_s_per_m3"])
    liquid = plate["interpretation_actual_liquid_L_per_min"]
    print("toy perfusion screen: analytic checks passed")
    print(f"assumed linear-R reference interval Q in [{q_lo:.6e}, {q_hi:.6e}] m^3/s")
    print(f"rows={len(rows)} csv={csv_path} json={json_path}")
    print(
        "conditional nameplate product if 40 SLPM means 40 actual liquid L/min: "
        f"P_hyd={liquid['P_hyd_W']:.6f} W; unverified claim product, not a measured point"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"analytic check failed: {exc}", file=sys.stderr)
        sys.exit(1)
