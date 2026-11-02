#!/usr/bin/env python3
# Coda review R1, 2026-11-01: separate repair of the preserved Fable original.
# Original SHA256: 9986a18f6f208cc1382fe4a7ffe1434584b96f4f1cb8da108d76970cb0114e0d
# Candidate 3 (Claude, Anthropic; static patch for Red / Richard Pemberton, run stage-red-20261102):
#   Gauss cross-check cancellation guard, h*A representability boundary, validator notes.  Not executed by author.
# Candidate 2 SHA256 (patch base): 160410e5cecb4e2408f3b13e42ae5213f12d43216d725859afbfa1e6e4b3a06a
"""
thermal_contract_t0.py
======================
Steady two-node, one-dimensional through-thickness reference model for the
shared synthetic reference contract T0-HYP-1 (The Stage; nonliving
synthetic-cover thermal baseline, supporting subsystem study).

STATUS OF THIS FILE
-------------------
Proposed reference code returned as text by a bounded technical contributor.
It was NOT executed by its author.  Nothing in it, or produced by it, has been
measured, observed or validated against hardware.  Material values are nominal
manufacturer references or explicitly assumed sensitivity domains held in the
configuration file; none is a specimen measurement.  Every number this program
can print is a conditional model result for a hypothetical linear network: not
the temperature of any physical object, not a safe-contact or component limit,
not evidence about tissue, tactile performance, barrier function or radiator
capacity.

NETWORK (outside ambient -> internal node)
------------------------------------------
 T_amb ~[R_conv]~[R_out_sil]-[R_c_out]-[R_film/2]-( S )-[R_film/2]-[R_c_in]-[R_in_sil]-( H )~[R_rej]~ T_res
                                                    ^                                     ^
                                                 P_sensor                               P_body
   R_SA  = R_film/2 + R_c_out + R_out_sil + R_conv   (S to ambient; R_conv = 1/(h A))
   R_HS  = R_in_sil + R_c_in + R_film/2              (H to S)
   R_rej                                             (H to rear reservoir; "blocked" -> G_rej = 0)

UNITS AND SIGNS
---------------
 area m2; thickness m; k W/(m K); areal contact resistance m2 K/W;
 total resistance K/W; conductance W/K; heat rate W; power density W/m2;
 temperature degC (only differences enter; no radiation, so no absolute scale).
 Q_HS    > 0 : heat flows from H toward S
 Q_front > 0 : heat leaves S toward ambient (same value through every element of R_SA)
 Q_rear  > 0 : heat leaves H toward the rear reservoir
 margin  = comparator - temperature   (positive: below the comparator)

Standard library only.  No network, no installation, no background work, no
access to any project checkout or prior report.  Reads one config path and
writes one output path, both supplied on the command line.

USAGE
-----
 python thermal_contract_t0.py run --config config.json --out results.json [--force]
 python thermal_contract_t0.py validate
 (with no subcommand, "run" is assumed)
"""

import argparse
import json
import math
import os
import sys

SCHEMA = "stage.thermal_contract.steady"
SCHEMA_VERSION = "T0-HYP-1.0"
BLOCKED = "blocked"
COMPARATOR_LABEL = "study_comparator_only"
SCENARIO_PLAN_ID = "deterministic_builtin_v1"
MAX_SETTINGS_PER_STACK = 60
CLAIM_STATUS = ("conditional_model_result; hypothetical reference T0-HYP-1; "
                "not a measurement, not a safety envelope, not validated")

RESULT_KEYS = ("T_H_C", "T_S_C", "T_outer_C", "Q_HS_W", "Q_front_W", "Q_rear_W",
               "reservoir_heat_demand_W", "q_front_W_m2", "q_inner_silicone_W_m2",
               "energy_residual_W", "energy_tolerance_W", "energy_check_pass",
               "margin_outer_K_study_comparator_only",
               "margin_internal_K_study_comparator_only")

STATUS_NOTES = {
    "solved": "unique steady solution (det > 0)",
    "solved_merged_node_R_HS_zero":
        "R_HS = 0: H and S merged into one node (documented limiting case, no division by zero)",
    "no_finite_steady_state_both_exits_absent_net_source_nonzero":
        "G_SA = 0 and G_rej = 0 with net source != 0: no steady state exists; no number is returned",
    "nonunique_constant_temperature_family_both_exits_absent":
        "G_SA = 0 and G_rej = 0 with zero sources: every T_H = T_S = const satisfies the balances",
    "nonunique_offset_family_both_exits_absent":
        "G_SA = 0 and G_rej = 0 with P_body = -P_sensor: T_H - T_S fixed, common level arbitrary",
    "nonunique_independent_constants_fully_disconnected":
        "all conductances zero and all sources zero: T_H and T_S independently arbitrary",
    "no_finite_steady_state_fully_disconnected_with_sources":
        "all conductances zero with nonzero per-node sources: global cancellation cannot satisfy either node",
    "no_finite_steady_state_H_isolated_with_source": "G_HS = 0 and G_rej = 0 with P_body != 0",
    "nonunique_T_H_H_isolated_zero_source": "G_HS = 0 and G_rej = 0 with P_body = 0: T_H arbitrary",
    "no_finite_steady_state_S_isolated_with_source": "G_HS = 0 and G_SA = 0 with P_sensor != 0",
    "nonunique_T_S_S_isolated_zero_source": "G_HS = 0 and G_SA = 0 with P_sensor = 0: T_S arbitrary",
}

DEFAULT_CMP = {"outer_surface_C": 40.0, "internal_node_C": 60.0}
DEFAULT_NUM = {"energy_abs_tol_W": 1e-10, "energy_rel_tol": 1e-10, "agreement_tol_K": 1e-9}

# Unit roundoff u = 2^-53 of IEEE-754 binary64 (sys.float_info.epsilon is 2^-52).
_UNIT_ROUNDOFF = sys.float_info.epsilon / 2.0
# Gauss cross-check guard (candidate 3): gauss_pivot_amplification() bounds the relative
# rounding error of the eliminated unknown by about 11 u * amplification for the thermal
# matrix; 16 is the next power of two and leaves room for the closed form's own ~6 u.
GAUSS_CHECK_ERROR_FACTOR = 16.0

# Acceptance rules tightened after the first T0-HYP-1.0 release.  The schema version string
# is deliberately unchanged (the output document echoes it and the frozen sample results must
# stay byte-identical); a configuration that validated under an earlier program version but
# violates a rule below is now rejected with a message naming the note.  Documentation only;
# never written to the output document.
VALIDATOR_NOTES = {
    "film_equal_across_stacks": (
        "candidate 2 (Coda): t_film_m must be equal across all stacks because the output "
        "document lists 'film thickness' under held_equal_across_stacks_per_condition; before "
        "that repair unequal films were accepted and the document's claim was unenforced (F3)."),
    "front_conductance_representable": (
        "candidate 3: for h_W_m2K > 0 (nominal, both assumed-range bounds and every resolved "
        "condition) h*A must be a finite positive float with a finite reciprocal.  h*A rounding "
        "to 0 (was ZeroDivisionError, F2a), to a subnormal whose reciprocal overflows (was a "
        "silent 'front path absent' solution echoing the positive h, CE-3) or to inf (would give "
        "R_conv = 0 exactly) is a configuration error.  h_W_m2K = 0 remains the documented "
        "absent-front-path limit."),
    "gauss_check_availability": (
        "candidate 3: checks.gauss_vs_closed_form_inverse is null (unavailable), never a "
        "spurious false, when the pivoted elimination raised (F1) or when its a-priori relative "
        "rounding bound GAUSS_CHECK_ERROR_FACTOR * u * amplification is >= "
        "numerics.agreement_tol_K, with amplification = (|d| + |f b|) / |d2| for the Schur "
        "complement d2 = d - f b (CE-1).  Otherwise the check is computed exactly as before."),
}


class ConfigError(ValueError):
    """Descriptive configuration error."""


def _close(a, b, tol=1e-9):
    """Combined absolute/relative closeness (K or W; a numerical criterion, not accuracy)."""
    return abs(a - b) <= tol * (1.0 + abs(a) + abs(b))


# ----------------------------------------------------------------------------
# 1. input validation
# ----------------------------------------------------------------------------

def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _finite(x):
    try:
        return _is_num(x) and math.isfinite(x)
    except OverflowError:
        return False


def _require(cond, msg):
    if not cond:
        raise ConfigError(msg)


def _require_range(name, rng, lo_ok=None):
    _require(isinstance(rng, list) and len(rng) == 2 and all(_finite(v) for v in rng),
             "%s must be a two-element list of finite numbers" % name)
    _require(rng[0] <= rng[1], "%s must be ordered low <= high" % name)
    if lo_ok is not None:
        _require(rng[0] >= lo_ok, "%s lower bound must be >= %r" % (name, lo_ok))


def parse_R_rej(value):
    """Rear rejection resistance: finite positive K/W, or the explicit blocked token.

    The blocked token is realised as R_rej = inf, hence G_rej = 1/inf = 0.0 exactly.
    It is never approximated by a large finite number.
    """
    if value == BLOCKED:
        return math.inf
    _require(_finite(value) and value > 0.0,
             "R_rej_K_W must be a finite positive number or the token %r (got %r)"
             % (BLOCKED, value))
    return float(value)


def validate_config(cfg):
    try:
        return _validate_config(cfg)
    except KeyError as exc:
        raise ConfigError("missing required field %s" % (exc,))


def _validate_config(cfg):
    _require(isinstance(cfg, dict), "top level must be a JSON object")
    _require(cfg["schema"] == SCHEMA, "schema must be %r" % SCHEMA)
    _require(cfg["schema_version"] == SCHEMA_VERSION,
             "schema_version must be %r" % SCHEMA_VERSION)
    _require(isinstance(cfg["study_id"], str) and cfg["study_id"] != "",
             "study_id must be a non-empty string")

    for section in ("geometry", "materials", "contacts", "thickness_perturbation",
                    "boundaries", "sources", "comparators", "numerics"):
        _require(isinstance(cfg[section], dict), "%s must be a JSON object" % section)

    g = cfg["geometry"]
    _require(_finite(g["area_m2"]) and g["area_m2"] > 0.0, "geometry.area_m2 must be finite and > 0")

    m = cfg["materials"]
    for key in ("silicone_ref", "polyimide_film_ref"):
        mat = m[key]
        _require(isinstance(mat, dict), "materials.%s must be a JSON object" % key)
        _require(_finite(mat["k_W_mK"]) and mat["k_W_mK"] > 0.0,
                 "materials.%s.k_W_mK must be finite and > 0" % key)
        _require_range("materials.%s.k_assumed_range_W_mK" % key,
                       mat["k_assumed_range_W_mK"], lo_ok=1e-9)
        _require(mat["k_assumed_range_W_mK"][0] <= mat["k_W_mK"] <= mat["k_assumed_range_W_mK"][1],
                 "materials.%s nominal k lies outside its assumed range" % key)
        _require(_finite(mat["density_kg_m3"]) and mat["density_kg_m3"] > 0.0,
                 "materials.%s.density_kg_m3 must be finite and > 0" % key)

    c = cfg["contacts"]
    _require(_finite(c["r_c_m2K_W"]) and c["r_c_m2K_W"] >= 0.0,
             "contacts.r_c_m2K_W must be finite and >= 0")
    _require_range("contacts.r_c_assumed_range_m2K_W", c["r_c_assumed_range_m2K_W"], lo_ok=0.0)

    stacks = cfg["stacks"]
    _require(isinstance(stacks, list) and len(stacks) >= 1, "stacks must be a non-empty list")
    _require(all(isinstance(s, dict) and isinstance(s.get("stack_id"), str) for s in stacks),
             "each stack must be a JSON object with a string stack_id")
    ids = [s["stack_id"] for s in stacks]
    _require(len(set(ids)) == len(ids), "stack_id values must be unique")
    for s in stacks:
        for key in ("t_outer_silicone_m", "t_film_m", "t_inner_silicone_m"):
            _require(_finite(s[key]) and s[key] >= 0.0,
                     "stack %r: %s must be finite and >= 0" % (s["stack_id"], key))
    _require(len({s["t_film_m"] for s in stacks}) == 1,
             "film thickness must be equal across stacks, as asserted by the study contract "
             "(validator note 'film_equal_across_stacks')")

    tp = cfg["thickness_perturbation"]
    _require(_finite(tp["fraction"]) and 0.0 <= tp["fraction"] < 1.0,
             "thickness_perturbation.fraction must lie in [0, 1)")

    b = cfg["boundaries"]
    for key in ("T_amb_C", "T_res_C"):
        _require(_finite(b[key]), "boundaries.%s must be finite" % key)
    _require(_finite(b["h_W_m2K"]) and b["h_W_m2K"] >= 0.0,
             "boundaries.h_W_m2K must be finite and >= 0 (0 = front path absent, limiting case only)")
    _require_range("boundaries.h_assumed_range_W_m2K", b["h_assumed_range_W_m2K"], lo_ok=0.0)
    for where, h in (("boundaries.h_W_m2K", b["h_W_m2K"]),
                     ("boundaries.h_assumed_range_W_m2K[0]", b["h_assumed_range_W_m2K"][0]),
                     ("boundaries.h_assumed_range_W_m2K[1]", b["h_assumed_range_W_m2K"][1])):
        front_convective_resistance_K_W(h, g["area_m2"], where)   # candidate 3: h*A representable
    parse_R_rej(b["R_rej_K_W"])
    _require_range("boundaries.R_rej_assumed_range_K_W", b["R_rej_assumed_range_K_W"], lo_ok=1e-12)
    _require(b["R_rej_blocked_token"] == BLOCKED,
             "boundaries.R_rej_blocked_token must be %r" % BLOCKED)

    src = cfg["sources"]
    for source in ("body", "sensor"):
        _require(isinstance(src[source], dict), "sources.%s must be a JSON object" % source)
    _require(src["body"]["node"] == "H", "sources.body.node must be 'H'")
    _require(src["sensor"]["node"] == "S", "sources.sensor.node must be 'S'")
    loads = src["body"]["P_W_list"]
    _require(isinstance(loads, list) and len(loads) == 3 and all(_finite(p) for p in loads),
             "sources.body.P_W_list must hold exactly three finite values (low, mid, high)")
    _require(loads[0] <= loads[1] <= loads[2], "sources.body.P_W_list must be ordered low <= mid <= high")
    _require(_finite(src["sensor"]["P_W"]), "sources.sensor.P_W must be finite")

    cmp_ = cfg["comparators"]
    _require(_finite(cmp_["outer_surface_C"]) and _finite(cmp_["internal_node_C"]),
             "comparator values must be finite")
    _require(cmp_["label"] == COMPARATOR_LABEL, "comparators.label must be %r" % COMPARATOR_LABEL)

    n = cfg["numerics"]
    for key in ("energy_abs_tol_W", "energy_rel_tol", "agreement_tol_K"):
        _require(_finite(n[key]) and n[key] > 0.0, "numerics.%s must be finite and > 0" % key)

    _require(cfg["scenario_plan"] == SCENARIO_PLAN_ID, "scenario_plan must be %r" % SCENARIO_PLAN_ID)
    return cfg


# ----------------------------------------------------------------------------
# 2. series resistance assembly
# ----------------------------------------------------------------------------

def layer_resistance_K_W(thickness_m, k_W_mK, area_m2):
    """Plane-wall conduction resistance t / (k A).  Requires t >= 0, k > 0, A > 0."""
    if not (thickness_m >= 0.0 and k_W_mK > 0.0 and area_m2 > 0.0):
        raise ValueError("layer_resistance: need thickness >= 0, k > 0, area > 0 (got t=%r k=%r A=%r)"
                         % (thickness_m, k_W_mK, area_m2))
    return thickness_m / (k_W_mK * area_m2)


def conductance_W_K(R_K_W):
    """1/R with both limits explicit: R = inf -> 0.0 (path absent); R = 0 -> inf (node merge)."""
    if math.isnan(R_K_W) or R_K_W < 0.0:
        raise ValueError("thermal resistance must be >= 0 (got %r); negative resistance is unphysical"
                         % (R_K_W,))
    if R_K_W == 0.0:
        return math.inf
    return 1.0 / R_K_W          # 1.0 / inf == 0.0 exactly in IEEE arithmetic


def front_convective_resistance_K_W(h_W_m2K, area_m2, where="h_W_m2K"):
    """R_conv = 1/(h A) in K/W with the documented limit h = 0 -> inf (front path absent).

    Configuration boundary (candidate 3): any positive h must give a finite positive R_conv.
    Otherwise the program would silently reinterpret its input: h*A rounded to 0.0 raised
    ZeroDivisionError (F2a); a subnormal h*A gave R_conv = inf and the case was solved as
    "front path absent" while echoing the positive h (CE-3); an overflowed h*A would give
    R_conv = 0.0 exactly.  All three raise ConfigError here, so library callers and the
    command line meet the same boundary.  For h > 0 the arithmetic is exactly the former
    1.0 / (h * A); negative h is rejected by the validator (and here, as unrepresentable).
    """
    h = float(h_W_m2K)
    A = float(area_m2)
    if h == 0.0:
        return math.inf
    hA = h * A
    R_conv = (1.0 / hA) if hA != 0.0 else math.inf
    if not (hA > 0.0 and math.isfinite(hA) and math.isfinite(R_conv)):
        raise ConfigError(
            "%s = %r with area_m2 = %r gives h*A = %r, which has no finite positive R_conv = "
            "1/(h*A) in binary64; use exactly 0 for an absent front path "
            "(validator note 'front_conductance_representable')" % (where, h_W_m2K, area_m2, hA))
    return R_conv


def assemble_resistances(stack, p):
    """Total resistances (K/W) for one stack under resolved case parameters p."""
    A = p["area_m2"]
    t_out = stack["t_outer_silicone_m"] * p["t_scale_outer"]
    t_in = stack["t_inner_silicone_m"] * p["t_scale_inner"]
    t_f = stack["t_film_m"] * p["t_scale_film"]
    R_out = layer_resistance_K_W(t_out, p["k_sil"], A)
    R_in = layer_resistance_K_W(t_in, p["k_sil"], A)
    R_film = layer_resistance_K_W(t_f, p["k_film"], A)
    R_c_out = p["r_c_outer"] / A
    R_c_in = p["r_c_inner"] / A
    R_conv = front_convective_resistance_K_W(p["h"], A)   # same arithmetic; rejects unrepresentable h*A
    R_rej = p["R_rej"]                          # float K/W or math.inf (blocked)
    R_HS = R_in + 0.5 * R_film + R_c_in         # internal: H -> S
    R_SA = 0.5 * R_film + R_c_out + R_out + R_conv   # internal conduction + environmental R_conv
    return {
        "t_outer_silicone_m": t_out, "t_inner_silicone_m": t_in, "t_film_m": t_f,
        "R_outer_silicone_K_W": R_out, "R_inner_silicone_K_W": R_in, "R_film_K_W": R_film,
        "R_layers_conduction_subtotal_K_W": R_out + R_in + R_film,
        "R_contact_outer_K_W": R_c_out, "R_contact_inner_K_W": R_c_in,
        "R_conv_K_W": R_conv, "R_rej_K_W": R_rej,
        "R_HS_K_W": R_HS, "R_SA_K_W": R_SA,
    }


# ----------------------------------------------------------------------------
# 3. the 2x2 steady solution
# ----------------------------------------------------------------------------

def solve_2x2_gauss(a, b, c, d, r1, r2):
    """Gaussian elimination with partial pivoting for [[a, b], [c, d]] x = [r1, r2]."""
    if abs(c) > abs(a):
        a, b, r1, c, d, r2 = c, d, r2, a, b, r1
    if a == 0.0:
        raise ZeroDivisionError("singular 2x2 system")
    f = c / a
    d2 = d - f * b
    r2b = r2 - f * r1
    if d2 == 0.0:
        raise ZeroDivisionError("singular 2x2 system")
    x2 = r2b / d2
    x1 = (r1 - b * x2) / a
    return x1, x2


def gauss_pivot_amplification(a, b, c, d):
    """Cancellation amplification of the single elimination step of solve_2x2_gauss.

    After the same pivot choice the Schur complement is d2 = d - f b with f = c / a.  With
    unit roundoff u, forming d2 from exact a, b, c, d commits at most about u |d2| + u (|d| +
    3 |f b|) of absolute error (one rounding each in a, f, f b and the subtraction, with the
    error of d's own formation counted in |d|), so the relative error of d2 and of the
    eliminated unknown is at most about 3 u * amp + O(u), where
        amp = (|d| + |f b|) / |d2|   (>= 1).
    For the thermal matrix (a = G_HS + G_rej, b = c = -G_HS, d = G_HS + G_SA) the pivot never
    swaps and d2 = G_SA + G_HS G_rej / (G_HS + G_rej) = det / a is formed as the difference of
    two numbers close to G_HS whenever G_SA and G_rej are both small against G_HS: the exits
    are then 'lost' in elimination although det > 0 exactly (CE-1).  Returns inf when the
    computed d2 is 0.0 (the F1 case, where solve_2x2_gauss raises).  Diagnostic only: it
    never enters any returned temperature or flux.
    """
    if abs(c) > abs(a):
        a, b, c, d = c, d, a, b
    fb = (c / a) * b
    d2 = d - fb
    if d2 == 0.0:
        return math.inf
    return (abs(d) + abs(fb)) / abs(d2)


def classify_singular(G_HS, G_SA, G_rej, P_body, P_sensor):
    """det = 0: say which node lost its path to every boundary and whether a family exists."""
    P_total = P_body + P_sensor
    if G_SA == 0.0 and G_rej == 0.0:
        if P_total != 0.0:
            status = "no_finite_steady_state_both_exits_absent_net_source_nonzero"
        elif G_HS == 0.0:
            status = ("no_finite_steady_state_fully_disconnected_with_sources"
                      if P_body != 0.0 or P_sensor != 0.0
                      else "nonunique_independent_constants_fully_disconnected")
        elif math.isinf(G_HS) or P_body == 0.0:
            status = "nonunique_constant_temperature_family_both_exits_absent"
        else:
            status = "nonunique_offset_family_both_exits_absent"
    elif G_HS == 0.0 and G_rej == 0.0:
        status = ("no_finite_steady_state_H_isolated_with_source" if P_body != 0.0
                  else "nonunique_T_H_H_isolated_zero_source")
    elif G_HS == 0.0 and G_SA == 0.0:
        status = ("no_finite_steady_state_S_isolated_with_source" if P_sensor != 0.0
                  else "nonunique_T_S_S_isolated_zero_source")
    else:
        status = "singular_unclassified"
    return {"status": status, "T_H": None, "T_S": None,
            "T_H_gauss": None, "T_S_gauss": None, "det_W2_K2": 0.0}


def solve_two_node(G_HS, G_SA, G_rej, P_body, P_sensor, T_amb, T_res):
    """
    Node balances (W):
      H:  P_body            = G_HS (T_H - T_S) + G_rej (T_H - T_res)
      S:  P_sensor + G_HS (T_H - T_S) = G_SA (T_S - T_amb)
    Matrix form  M [T_H, T_S]^T = [P_body + G_rej T_res, P_sensor + G_SA T_amb]^T
      M     = [[G_HS + G_rej, -G_HS], [-G_HS, G_HS + G_SA]]
      det M = G_HS G_SA + G_HS G_rej + G_rej G_SA   (W^2/K^2)
    Unique solution iff det > 0, i.e. at most one conductance is zero (every node reaches
    a boundary).  Closed-form inverse and pivoted elimination are both returned so a
    caller can confirm agreement.  Blocked exits are exact zeros, never large numbers.
    'gauss_amplification' (candidate 3) is the pivot-cancellation factor of that elimination
    (see gauss_pivot_amplification); semantic_checks uses it to report the cross-check as
    unavailable when its a-priori rounding bound reaches the agreement tolerance.
    """
    for name, G in (("G_HS", G_HS), ("G_SA", G_SA), ("G_rej", G_rej)):
        if math.isnan(G) or G < 0.0:
            raise ValueError("%s must be >= 0, got %r" % (name, G))
    for name, v in (("P_body", P_body), ("P_sensor", P_sensor), ("T_amb", T_amb), ("T_res", T_res)):
        if not math.isfinite(v):
            raise ValueError("%s must be finite, got %r" % (name, v))
    if math.isinf(G_SA):
        raise ValueError("R_SA = 0 (the entire front resistance is zero) is outside the study domain; "
                         "documented limit T_S = T_amb is deliberately not implemented")
    if math.isinf(G_rej):
        raise ValueError("R_rej = 0 is outside the study domain; the ideal H = T_res "
                         "pinning limit is deliberately not implemented")
    if math.isinf(G_HS):                     # R_HS = 0 -> merge H and S
        G_exit = G_rej + G_SA
        if G_exit == 0.0:
            return classify_singular(G_HS, G_SA, G_rej, P_body, P_sensor)
        T = (P_body + P_sensor + G_rej * T_res + G_SA * T_amb) / G_exit
        return {"status": "solved_merged_node_R_HS_zero", "T_H": T, "T_S": T,
                "T_H_gauss": T, "T_S_gauss": T, "det_W2_K2": None}
    det = G_HS * G_SA + G_HS * G_rej + G_rej * G_SA
    if det <= 0.0:
        return classify_singular(G_HS, G_SA, G_rej, P_body, P_sensor)
    a = G_HS + G_rej
    b = -G_HS
    c = -G_HS
    d = G_HS + G_SA
    r1 = P_body + G_rej * T_res
    r2 = P_sensor + G_SA * T_amb
    T_H = (d * r1 - b * r2) / det            # = ((G_HS+G_SA) r1 + G_HS r2) / det
    T_S = (-c * r1 + a * r2) / det           # = (G_HS r1 + (G_HS+G_rej) r2) / det
    try:
        T_H_g, T_S_g = solve_2x2_gauss(a, b, c, d, r1, r2)
        amp = gauss_pivot_amplification(a, b, c, d)
    except ZeroDivisionError:
        # det > 0 above, but floating-point elimination can lose a tiny exit.
        # Keep the closed-form result and explicitly mark the check unavailable.
        T_H_g = T_S_g = None
        amp = math.inf
    return {"status": "solved", "T_H": T_H, "T_S": T_S,
            "T_H_gauss": T_H_g, "T_S_gauss": T_S_g, "det_W2_K2": det,
            "gauss_amplification": amp}


# ----------------------------------------------------------------------------
# 4. flux / temperature reconstruction and semantic checks
# ----------------------------------------------------------------------------

def reconstruct(sol, R, p, comparators, numerics):
    """Signed heat rates, outer-surface temperature, energy residual, comparator margins.

    Q_front crosses every element between S and ambient (series, no source between), so
    T_outer = T_amb + Q_front * R_conv.  If the front path is absent (h = 0) the front flux
    is identically zero and the front layers are isothermal at T_S, so T_outer = T_S.
    """
    T_H, T_S = sol["T_H"], sol["T_S"]
    G_HS = conductance_W_K(R["R_HS_K_W"])
    G_SA = conductance_W_K(R["R_SA_K_W"])
    G_rej = conductance_W_K(R["R_rej_K_W"])
    Q_rear = G_rej * (T_H - p["T_res"])          # exactly 0.0 when blocked
    Q_front = G_SA * (T_S - p["T_amb"])          # exactly 0.0 when front absent
    if math.isinf(G_HS):
        Q_HS = p["P_body"] - Q_rear              # merged node: from the H balance
    else:
        Q_HS = G_HS * (T_H - T_S)
    if G_SA == 0.0:
        T_outer = T_S
    else:
        T_outer = p["T_amb"] + Q_front * R["R_conv_K_W"]
    P_total = p["P_body"] + p["P_sensor"]
    residual = P_total - Q_front - Q_rear
    scale = abs(p["P_body"]) + abs(p["P_sensor"]) + abs(Q_front) + abs(Q_rear)
    tol = numerics["energy_abs_tol_W"] + numerics["energy_rel_tol"] * scale
    A = p["area_m2"]
    return {
        "T_H_C": T_H, "T_S_C": T_S, "T_outer_C": T_outer,
        "Q_HS_W": Q_HS, "Q_front_W": Q_front, "Q_rear_W": Q_rear,
        "reservoir_heat_demand_W": Q_rear,
        "q_front_W_m2": Q_front / A, "q_inner_silicone_W_m2": Q_HS / A,
        "energy_residual_W": residual, "energy_tolerance_W": tol,
        "energy_check_pass": bool(abs(residual) <= tol),
        "margin_outer_K_study_comparator_only": comparators["outer_surface_C"] - T_outer,
        "margin_internal_K_study_comparator_only": comparators["internal_node_C"] - T_H,
    }


def semantic_checks(res, sol, R, p, tol):
    """Independent consistency checks.  A small residual alone cannot prove the right network."""
    checks = {}
    checks["all_outputs_finite"] = all(
        math.isfinite(res[k]) for k in RESULT_KEYS if isinstance(res[k], float))
    checks["energy_balance_within_tolerance"] = res["energy_check_pass"]
    checks["sensor_flux_discontinuity_equals_P_sensor"] = _close(
        res["Q_front_W"] - res["Q_HS_W"], p["P_sensor"], tol)
    amp = sol.get("gauss_amplification")          # None when no elimination was performed
    if sol["T_H_gauss"] is None:
        checks["gauss_vs_closed_form_inverse"] = None          # elimination raised (F1)
    elif amp is not None and GAUSS_CHECK_ERROR_FACTOR * _UNIT_ROUNDOFF * amp >= tol:
        # Cancellation guard (candidate 3): the elimination's a-priori rounding bound reaches
        # the agreement tolerance, so a disagreement could not be charged to the closed form.
        checks["gauss_vs_closed_form_inverse"] = None          # unavailable, not False (CE-1)
    else:
        checks["gauss_vs_closed_form_inverse"] = (_close(sol["T_H_gauss"], sol["T_H"], tol)
                                                  and _close(sol["T_S_gauss"], sol["T_S"], tol))
    R_HS, R_SA, R_rej = R["R_HS_K_W"], R["R_SA_K_W"], R["R_rej_K_W"]
    if all(math.isfinite(x) and x > 0.0 for x in (R_HS, R_SA, R_rej)):
        R_sum = R_HS + R_SA + R_rej
        Q_front_cf = (R_rej * p["P_body"] + (R_rej + R_HS) * p["P_sensor"]
                      + (p["T_res"] - p["T_amb"])) / R_sum
        checks["resistance_divider_closed_form"] = _close(Q_front_cf, res["Q_front_W"], tol)
    else:
        checks["resistance_divider_closed_form"] = None      # not applicable
    if math.isfinite(R_rej):
        hA = 0.0 if math.isinf(R["R_conv_K_W"]) else 1.0 / R["R_conv_K_W"]
        T_H_line = p["T_res"] + R_rej * (p["P_body"] + p["P_sensor"]
                                         - hA * (res["T_outer_C"] - p["T_amb"]))
        checks["pareto_line_identity_T_H_vs_T_outer"] = _close(T_H_line, res["T_H_C"], tol)
    else:
        checks["pareto_line_identity_T_H_vs_T_outer"] = None
    return checks


# ----------------------------------------------------------------------------
# 5. deterministic scenario plan and study runner
# ----------------------------------------------------------------------------

def resolve_parameters(cfg, cond):
    """Merge one shared-condition override dict with the configured nominal values."""
    b, m, c, s = cfg["boundaries"], cfg["materials"], cfg["contacts"], cfg["sources"]
    r_c_common = cond.get("r_c", c["r_c_m2K_W"])
    bias = float(cond.get("t_bias", 0.0))
    p = {
        "area_m2": float(cfg["geometry"]["area_m2"]),
        "k_sil": float(cond.get("k_sil", m["silicone_ref"]["k_W_mK"])),
        "k_film": float(cond.get("k_film", m["polyimide_film_ref"]["k_W_mK"])),
        "r_c_inner": float(cond.get("r_c_inner", r_c_common)),
        "r_c_outer": float(cond.get("r_c_outer", r_c_common)),
        "h": float(cond.get("h", b["h_W_m2K"])),
        "R_rej": parse_R_rej(cond.get("R_rej", b["R_rej_K_W"])),
        "T_amb": float(cond.get("T_amb", b["T_amb_C"])),      # offsets: not used by the plan
        "T_res": float(cond.get("T_res", b["T_res_C"])),
        "P_body": float(cond["P_body"]),
        "P_sensor": float(cond.get("P_sensor", s["sensor"]["P_W"])),
        "t_scale_inner": (1.0 + bias) * (1.0 + float(cond.get("t_dev_inner", 0.0))),
        "t_scale_outer": (1.0 + bias) * (1.0 + float(cond.get("t_dev_outer", 0.0))),
        "t_scale_film": 1.0,                                   # clarification C4
    }
    for key, val in p.items():
        if key != "R_rej" and not math.isfinite(val):
            raise ConfigError("condition %r: %s is not finite" % (cond.get("condition_id"), key))
    if p["k_sil"] <= 0.0 or p["k_film"] <= 0.0:
        raise ConfigError("condition %r: conductivities must be > 0" % cond.get("condition_id"))
    if p["r_c_inner"] < 0.0 or p["r_c_outer"] < 0.0 or p["h"] < 0.0:
        raise ConfigError("condition %r: r_c and h must be >= 0" % cond.get("condition_id"))
    if p["t_scale_inner"] <= 0.0 or p["t_scale_outer"] <= 0.0:
        raise ConfigError("condition %r: thickness scale must be > 0" % cond.get("condition_id"))
    front_convective_resistance_K_W(p["h"], p["area_m2"],           # candidate 3: h*A representable
                                    "condition %r: h" % cond.get("condition_id"))
    return p


def build_shared_conditions(cfg):
    """Deterministic plan: nominal, rear-blocked, one-at-a-time, load extremes, corners, layer deviations."""
    b, m, c, s = cfg["boundaries"], cfg["materials"], cfg["contacts"], cfg["sources"]
    loads = [float(x) for x in s["body"]["P_W_list"]]
    P_lo, P_mid, P_hi = loads
    k_sil_rng = m["silicone_ref"]["k_assumed_range_W_mK"]
    k_film_rng = m["polyimide_film_ref"]["k_assumed_range_W_mK"]
    rc_rng = c["r_c_assumed_range_m2K_W"]
    h_rng = b["h_assumed_range_W_m2K"]
    Rrej_rng = b["R_rej_assumed_range_K_W"]
    f = float(cfg["thickness_perturbation"]["fraction"])
    conds = []

    def ptag(P):
        return ("%g" % P).replace(".", "p")

    def add(cid, group, P_body, **over):
        d = {"condition_id": cid, "group": group, "P_body": P_body}
        d.update(over)
        conds.append(d)

    for P in loads:                                            # A: nominal
        add("A_nominal_P%s" % ptag(P), "A_nominal", P)
    for P in loads:                                            # B: rear blocked comparator
        add("B_rear_blocked_P%s" % ptag(P), "B_rear_blocked", P, R_rej=BLOCKED)
    for name, key, rng in (("k_sil", "k_sil", k_sil_rng), ("k_film", "k_film", k_film_rng),
                           ("r_c", "r_c", rc_rng), ("h", "h", h_rng), ("R_rej", "R_rej", Rrej_rng)):
        for tag, v in (("lo", rng[0]), ("hi", rng[1])):          # C: one-at-a-time at mid load
            add("C_%s_%s_P%s" % (name, tag, ptag(P_mid)), "C_one_at_a_time", P_mid, **{key: v})
    add("C_t_bias_minus_P%s" % ptag(P_mid), "C_one_at_a_time", P_mid, t_bias=-f)
    add("C_t_bias_plus_P%s" % ptag(P_mid), "C_one_at_a_time", P_mid, t_bias=+f)
    add("C_sensor_off_P%s" % ptag(P_mid), "C_one_at_a_time", P_mid, P_sensor=0.0)
    for P in (P_lo, P_hi):                                     # D: boundary OAT at load extremes
        for tag, v in (("lo", h_rng[0]), ("hi", h_rng[1])):
            add("D_h_%s_P%s" % (tag, ptag(P)), "D_boundary_at_load_extremes", P, h=v)
        for tag, v in (("lo", Rrej_rng[0]), ("hi", Rrej_rng[1])):
            add("D_R_rej_%s_P%s" % (tag, ptag(P)), "D_boundary_at_load_extremes", P, R_rej=v)
    E = "E_joint_adverse_corner"                               # E: prespecified joint corners
    add("E1_both_exits_weak_P%s" % ptag(P_hi), E, P_hi, h=h_rng[0], R_rej=Rrej_rng[1],
        k_sil=k_sil_rng[0], r_c=rc_rng[1], t_bias=+f)
    add("E2_rear_weak_front_strong_P%s" % ptag(P_hi), E, P_hi, h=h_rng[1], R_rej=Rrej_rng[1],
        k_sil=k_sil_rng[1], r_c=rc_rng[0])
    add("E3_rear_strong_front_weak_P%s" % ptag(P_hi), E, P_hi, h=h_rng[0], R_rej=Rrej_rng[0],
        k_sil=k_sil_rng[0], r_c=rc_rng[1])
    add("E4_blocked_adverse_P%s" % ptag(P_hi), E, P_hi, R_rej=BLOCKED, h=h_rng[0],
        k_sil=k_sil_rng[0], r_c=rc_rng[1], t_bias=+f)
    add("E5_blocked_favourable_P%s" % ptag(P_lo), E, P_lo, R_rej=BLOCKED, h=h_rng[1],
        k_sil=k_sil_rng[1], r_c=rc_rng[0], t_bias=-f)
    add("E6_max_layer_resistance_P%s" % ptag(P_mid), E, P_mid, k_sil=k_sil_rng[0],
        k_film=k_film_rng[0], r_c=rc_rng[1], t_bias=+f)
    add("E7_min_layer_resistance_P%s" % ptag(P_mid), E, P_mid, k_sil=k_sil_rng[1],
        k_film=k_film_rng[1], r_c=rc_rng[0], t_bias=-f)
    F = "F_independent_layer_deviation"                        # F: independent layer deviations
    add("F_inner_plus_outer_minus_P%s" % ptag(P_mid), F, P_mid, t_dev_inner=+f, t_dev_outer=-f)
    add("F_inner_minus_outer_plus_P%s" % ptag(P_mid), F, P_mid, t_dev_inner=-f, t_dev_outer=+f)

    if len(conds) > MAX_SETTINGS_PER_STACK:
        raise ConfigError("scenario plan has %d settings per stack; bound is %d"
                          % (len(conds), MAX_SETTINGS_PER_STACK))
    ids = [d["condition_id"] for d in conds]
    if len(set(ids)) != len(ids):
        raise ConfigError("duplicate condition_id in scenario plan")
    return conds


def run_case(cfg, stack, cond):
    p = resolve_parameters(cfg, cond)
    R = assemble_resistances(stack, p)
    sol = solve_two_node(conductance_W_K(R["R_HS_K_W"]), conductance_W_K(R["R_SA_K_W"]),
                         conductance_W_K(R["R_rej_K_W"]),
                         p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
    rho_sil = cfg["materials"]["silicone_ref"]["density_kg_m3"]
    rho_film = cfg["materials"]["polyimide_film_ref"]["density_kg_m3"]
    A = p["area_m2"]
    mass = A * ((R["t_outer_silicone_m"] + R["t_inner_silicone_m"]) * rho_sil
                + R["t_film_m"] * rho_film)
    blocked = math.isinf(R["R_rej_K_W"])
    case = {
        "case_id": "%s__%s" % (stack["stack_id"], cond["condition_id"]),
        "stack_id": stack["stack_id"],
        "condition_id": cond["condition_id"],
        "group": cond["group"],
        "overrides_vs_nominal": {k: v for k, v in cond.items() if k not in ("condition_id", "group")},
        "status": sol["status"],
        "status_note": STATUS_NOTES.get(sol["status"], ""),
        "claim_status": CLAIM_STATUS,
        "P_body_W": p["P_body"],
        "P_sensor_W": p["P_sensor"],
        "P_total_W": p["P_body"] + p["P_sensor"],
        "T_amb_C": p["T_amb"],
        "T_res_C": p["T_res"],
        "h_W_m2K": p["h"],
        "k_silicone_W_mK": p["k_sil"],
        "k_film_W_mK": p["k_film"],
        "r_c_inner_m2K_W": p["r_c_inner"],
        "r_c_outer_m2K_W": p["r_c_outer"],
        "rear_boundary_condition": ("blocked_G_rej_zero" if blocked
                                    else "finite_R_rej_to_ideal_isothermal_reservoir"),
        "R_rej_K_W": (BLOCKED if blocked else R["R_rej_K_W"]),
        "reservoir_is_idealization_with_unknown_realization": True,
        "modeled_total_thickness_m": R["t_outer_silicone_m"] + R["t_film_m"] + R["t_inner_silicone_m"],
        "modeled_mass_kg_nominal_density_not_weighed": mass,
        "det_W2_K2": sol["det_W2_K2"],
    }
    for key in ("R_outer_silicone_K_W", "R_inner_silicone_K_W", "R_film_K_W",
                "R_layers_conduction_subtotal_K_W", "R_contact_outer_K_W", "R_contact_inner_K_W",
                "R_conv_K_W", "R_HS_K_W", "R_SA_K_W"):
        case[key] = R[key]
    if sol["T_H"] is None:
        case.update({k: None for k in RESULT_KEYS})
        case["checks"] = {"solvable": False}
    else:
        res = reconstruct(sol, R, p, cfg["comparators"], cfg["numerics"])
        case.update(res)
        case["checks"] = semantic_checks(res, sol, R, p, cfg["numerics"]["agreement_tol_K"])
    return case


def summarize(cases):
    solved = [c for c in cases if c["status"].startswith("solved")]
    return {
        "n_cases": len(cases),
        "n_solved": len(solved),
        "n_not_solved": len(cases) - len(solved),
        "n_energy_pass": sum(1 for c in solved if c["energy_check_pass"]),
        "n_all_semantic_checks_pass": sum(
            1 for c in solved if all(v in (True, None) for v in c["checks"].values())),
        "n_outer_comparator_exceeded_study_comparator_only": sum(
            1 for c in solved if c["margin_outer_K_study_comparator_only"] < 0.0),
        "n_internal_comparator_exceeded_study_comparator_only": sum(
            1 for c in solved if c["margin_internal_K_study_comparator_only"] < 0.0),
        "note": ("bookkeeping counts only; a comparator crossing is a model event, "
                 "not an observed injury, limit or safety finding"),
    }


def _sanitize(obj):
    """Make the document strict-JSON: inf -> string token, nan -> null."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        if math.isnan(obj):
            return None
    return obj


def print_table(cases):
    print("%-36s %9s %9s %9s %9s %8s %8s %5s" % ("case_id", "T_outer_C", "T_H_C", "Q_front_W",
                                                  "Q_rear_W", "m_out_K", "m_H_K", "E_ok"))
    for c in cases:
        if not (c["group"].startswith("A_") or c["group"].startswith("B_")):
            continue
        if c["status"].startswith("solved"):
            print("%-36s %9.3f %9.3f %9.4f %9.4f %8.2f %8.2f %5s" % (
                c["case_id"], c["T_outer_C"], c["T_H_C"], c["Q_front_W"], c["Q_rear_W"],
                c["margin_outer_K_study_comparator_only"],
                c["margin_internal_K_study_comparator_only"], c["energy_check_pass"]))
        else:
            print("%-36s %s" % (c["case_id"], c["status"]))
    print("(display rounded; file holds full floats; margins are study comparators only)")


def run_study(config_path, out_path, force=False):
    if os.path.normcase(os.path.realpath(config_path)) == os.path.normcase(os.path.realpath(out_path)):
        raise OSError("output must not overwrite the input configuration, even with --force")
    if os.path.exists(out_path) and os.path.samefile(config_path, out_path):
        raise OSError("output aliases the input configuration; refusing overwrite")
    if os.path.exists(out_path) and not force:
        raise OSError("refusing to overwrite existing output %r (use --force)" % out_path)
    parent = os.path.dirname(os.path.abspath(out_path))
    if not os.path.isdir(parent):
        raise OSError("output directory does not exist: %r" % parent)
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    validate_config(cfg)
    conds = build_shared_conditions(cfg)
    cases = []
    for cond in conds:
        for stack in cfg["stacks"]:
            cases.append(run_case(cfg, stack, cond))
    doc = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "study_id": cfg["study_id"],
        "scenario_plan": SCENARIO_PLAN_ID,
        "claim_status": CLAIM_STATUS,
        "provenance_note": ("material k values are manufacturer nominal references (see config "
                            "source cards); ranges are assumed sensitivity domains, not "
                            "distributions; boundaries, loads and comparators are hypothetical "
                            "study choices; the rear reservoir is an idealization"),
        "held_equal_across_stacks_per_condition": [
            "area_m2", "k_silicone (common to both silicone layers)", "k_film",
            "r_c at both interfaces", "h", "T_amb", "T_res", "R_rej", "P_body", "P_sensor",
            "film thickness", "thickness perturbation fractions"],
        "differs_across_stacks": [
            "silicone thickness per side", "modeled_total_thickness_m",
            "modeled_mass_kg_nominal_density_not_weighed", "R_HS_K_W", "R_SA_K_W"],
        "omitted_effects_delimiting_scope": [
            "in-plane spreading", "curvature", "seams and bridges", "radiation",
            "contacting human body / effusivity / exposure duration", "H-to-inner-silicone "
            "attachment resistance", "metal traces, components, wiring", "temperature-dependent "
            "properties", "transients and thermal mass", "reservoir realization, energy, mass, "
            "environmental coupling and capacity cap", "ambient/sink offsets"],
        "interpretation_caveats": [
            "The linear constant-property model has no internal validity bound; outputs far "
            "above ambient (e.g. rear-blocked 5 W and 10 W settings) lie where omitted "
            "radiation and property changes may materially alter the result. The formal "
            "steady model rejects the full load; the physical credibility of those large "
            "temperature rises has not been established.",
            "Lower T_outer and lower T_H trade against each other on one line for fixed "
            "boundaries and loads (T_H = T_res + R_rej*(P_total - h*A*(T_outer - T_amb))); "
            "no stack is better in both.  No ranking is implied."],
        "n_conditions_per_stack": len(conds),
        "conditions": conds,
        "config_echo": cfg,
        "cases": cases,
        "summary": summarize(cases),
    }
    with open(out_path, "w" if force else "x", encoding="utf-8") as fh:
        json.dump(_sanitize(doc), fh, indent=1, allow_nan=False)
    print_table(cases)
    print(json.dumps(_sanitize(doc["summary"]), indent=1))
    print("wrote %s  --  %s" % (out_path, CLAIM_STATUS))
    return 0


# ----------------------------------------------------------------------------
# 6. analytic self-checks (validate mode; writes nothing)
# ----------------------------------------------------------------------------

def _ref_stack(t_sil_m=0.5e-3, t_film_m=0.05e-3):
    return {"stack_id": "ref", "t_outer_silicone_m": t_sil_m, "t_film_m": t_film_m,
            "t_inner_silicone_m": t_sil_m}


def _ref_params(**over):
    p = {"area_m2": 0.01, "k_sil": 0.27, "k_film": 0.20, "r_c_inner": 2.0e-4, "r_c_outer": 2.0e-4,
         "h": 8.0, "R_rej": 2.0, "T_amb": 25.0, "T_res": 25.0, "P_body": 5.0, "P_sensor": 0.10,
         "t_scale_inner": 1.0, "t_scale_outer": 1.0, "t_scale_film": 1.0}
    p.update(over)
    return p


def _solve(stack, p):
    R = assemble_resistances(stack, p)
    sol = solve_two_node(conductance_W_K(R["R_HS_K_W"]), conductance_W_K(R["R_SA_K_W"]),
                         conductance_W_K(R["R_rej_K_W"]),
                         p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
    res = reconstruct(sol, R, p, DEFAULT_CMP, DEFAULT_NUM) if sol["T_H"] is not None else None
    return R, sol, res


def v01_zero_sources_equal_connected_reservoirs():
    p = _ref_params(P_body=0.0, P_sensor=0.0)
    R, sol, res = _solve(_ref_stack(), p)
    ok = (sol["status"] == "solved" and _close(res["T_H_C"], 25.0) and _close(res["T_S_C"], 25.0)
          and _close(res["T_outer_C"], 25.0) and abs(res["Q_front_W"]) <= 1e-12
          and abs(res["Q_rear_W"]) <= 1e-12)
    return ok, "expect all temperatures 25 C and zero fluxes; got T_H=%r T_S=%r" % (
        res["T_H_C"], res["T_S_C"])


def v02_rear_disabled_single_series_branch():
    p = _ref_params(R_rej=math.inf)
    R, sol, res = _solve(_ref_stack(), p)
    P_total = p["P_body"] + p["P_sensor"]
    T_S_exp = p["T_amb"] + P_total * R["R_SA_K_W"]
    T_H_exp = T_S_exp + p["P_body"] * R["R_HS_K_W"]
    T_out_exp = p["T_amb"] + P_total * R["R_conv_K_W"]
    ok = (res["Q_rear_W"] == 0.0 and _close(res["Q_front_W"], P_total)
          and _close(res["T_S_C"], T_S_exp) and _close(res["T_H_C"], T_H_exp)
          and _close(res["T_outer_C"], T_out_exp))
    return ok, "series expectations T_S=%.6f T_H=%.6f T_outer=%.6f; got %.6f %.6f %.6f" % (
        T_S_exp, T_H_exp, T_out_exp, res["T_S_C"], res["T_H_C"], res["T_outer_C"])


def v03_no_sensor_parallel_split():
    p = _ref_params(P_sensor=0.0)
    R, sol, res = _solve(_ref_stack(), p)
    ratio_exp = R["R_rej_K_W"] / (R["R_HS_K_W"] + R["R_SA_K_W"])
    ratio = res["Q_front_W"] / res["Q_rear_W"]
    front_exp = p["P_body"] * R["R_rej_K_W"] / (R["R_HS_K_W"] + R["R_SA_K_W"] + R["R_rej_K_W"])
    ok = _close(ratio, ratio_exp) and _close(res["T_H_C"], res["T_S_C"] + front_exp * R["R_HS_K_W"])
    return ok, "Q_front/Q_rear expect %.9f got %.9f" % (ratio_exp, ratio)


def v04_symmetric_network():
    sol = solve_two_node(3.0, 0.5, 0.5, 1.0, 1.0, 20.0, 20.0)
    Q_front = 0.5 * (sol["T_S"] - 20.0)
    Q_rear = 0.5 * (sol["T_H"] - 20.0)
    ok = _close(sol["T_H"], sol["T_S"]) and _close(Q_front, Q_rear) and _close(Q_front + Q_rear, 2.0)
    return ok, "T_H=%.9f T_S=%.9f Q_front=%.9f Q_rear=%.9f" % (sol["T_H"], sol["T_S"], Q_front, Q_rear)


def v05_both_exits_blocked_detection():
    R1, sol1, res1 = _solve(_ref_stack(), _ref_params(h=0.0, R_rej=math.inf))
    R2, sol2, res2 = _solve(_ref_stack(), _ref_params(h=0.0, R_rej=math.inf, P_body=0.0, P_sensor=0.0))
    ok = (sol1["status"].startswith("no_finite_steady_state") and sol1["T_H"] is None
          and sol2["status"].startswith("nonunique_constant_temperature_family")
          and sol2["T_H"] is None)
    return ok, "positive power -> %s; zero power -> %s" % (sol1["status"], sol2["status"])


def v06_boundary_shift_invariance():
    Ra, sa, ra = _solve(_ref_stack(), _ref_params())
    Rb, sb, rb = _solve(_ref_stack(), _ref_params(T_amb=37.5, T_res=37.5))
    ok = (all(_close(rb[k] - ra[k], 12.5) for k in ("T_H_C", "T_S_C", "T_outer_C"))
          and all(_close(rb[k], ra[k]) for k in ("Q_HS_W", "Q_front_W", "Q_rear_W")))
    return ok, "shift 12.5 K: dT_H=%.9f dQ_front=%.3e" % (rb["T_H_C"] - ra["T_H_C"],
                                                          rb["Q_front_W"] - ra["Q_front_W"])


def v07_sensor_power_counted_once():
    p = _ref_params()
    R, sol, res = _solve(_ref_stack(), p)
    R0, sol0, res0 = _solve(_ref_stack(), _ref_params(P_sensor=0.0))
    total_once = res["Q_front_W"] + res["Q_rear_W"]
    ok = (_close(total_once, p["P_body"] + p["P_sensor"])
          and not _close(total_once, p["P_body"] + 2.0 * p["P_sensor"])
          and _close(res["Q_front_W"] - res["Q_HS_W"], p["P_sensor"])
          and _close((res["Q_front_W"] - res0["Q_front_W"]) + (res["Q_rear_W"] - res0["Q_rear_W"]),
                     p["P_sensor"]))
    return ok, "Q_front+Q_rear=%.9f (expect %.3f, not %.3f); Q_front-Q_HS=%.9f" % (
        total_once, p["P_body"] + p["P_sensor"], p["P_body"] + 2.0 * p["P_sensor"],
        res["Q_front_W"] - res["Q_HS_W"])


def v08_hand_derived_example_H1_5W():
    # Hand-derived (not executed) values for H1, P_body = 5 W, nominal boundaries, 4-5 s.f.
    hand = {"Q_front_W": 0.684400, "Q_rear_W": 4.415600, "T_H_C": 33.8312,
            "T_S_C": 33.7040, "T_outer_C": 33.5550}
    tolr = {"Q_front_W": 2e-5, "Q_rear_W": 2e-5, "T_H_C": 6e-4, "T_S_C": 6e-4, "T_outer_C": 6e-4}
    R, sol, res = _solve(_ref_stack(), _ref_params())
    diffs = {k: res[k] - hand[k] for k in hand}
    ok = all(abs(diffs[k]) <= tolr[k] for k in hand)
    return ok, "code minus hand: " + ", ".join("%s %+.2e" % (k, diffs[k]) for k in hand)


def v09_zero_internal_resistance_merged_node():
    stack = {"stack_id": "merge", "t_outer_silicone_m": 1.0e-3, "t_film_m": 0.0, "t_inner_silicone_m": 0.0}
    p = _ref_params(r_c_inner=0.0, r_c_outer=0.0)
    R, sol, res = _solve(stack, p)
    G_SA = conductance_W_K(R["R_SA_K_W"])
    G_rej = conductance_W_K(R["R_rej_K_W"])
    T_exp = (p["P_body"] + p["P_sensor"] + G_rej * p["T_res"] + G_SA * p["T_amb"]) / (G_rej + G_SA)
    ok = (sol["status"] == "solved_merged_node_R_HS_zero" and _close(res["T_H_C"], T_exp)
          and _close(res["T_S_C"], T_exp) and res["energy_check_pass"])
    return ok, "status=%s T=%.9f expect %.9f" % (sol["status"], res["T_H_C"], T_exp)


def v10_front_path_absent():
    p = _ref_params(h=0.0)
    R, sol, res = _solve(_ref_stack(), p)
    P_total = p["P_body"] + p["P_sensor"]
    T_H_exp = p["T_res"] + R["R_rej_K_W"] * P_total
    T_S_exp = T_H_exp + p["P_sensor"] * R["R_HS_K_W"]
    ok = (res["Q_front_W"] == 0.0 and _close(res["Q_rear_W"], P_total)
          and _close(res["T_H_C"], T_H_exp) and _close(res["T_S_C"], T_S_exp)
          and _close(res["T_outer_C"], res["T_S_C"]) and _close(res["Q_HS_W"], -p["P_sensor"]))
    return ok, "T_H=%.6f (exp %.6f) T_S=%.6f (exp %.6f) Q_HS=%.6f (exp %.3f, sign kept)" % (
        res["T_H_C"], T_H_exp, res["T_S_C"], T_S_exp, res["Q_HS_W"], -p["P_sensor"])


def v11_three_formulations_agree():
    p = _ref_params()
    R, sol, res = _solve(_ref_stack(), p)
    R_sum = R["R_HS_K_W"] + R["R_SA_K_W"] + R["R_rej_K_W"]
    Q_front_cf = (R["R_rej_K_W"] * p["P_body"] + (R["R_rej_K_W"] + R["R_HS_K_W"]) * p["P_sensor"]
                  + (p["T_res"] - p["T_amb"])) / R_sum
    ok = (_close(sol["T_H_gauss"], sol["T_H"]) and _close(sol["T_S_gauss"], sol["T_S"])
          and _close(Q_front_cf, res["Q_front_W"]))
    return ok, "inverse vs gauss dT_H=%.3e; divider vs inverse dQ_front=%.3e" % (
        sol["T_H_gauss"] - sol["T_H"], Q_front_cf - res["Q_front_W"])


def v12_thickness_monotonicity_and_exception():
    stacks = [_ref_stack(0.5e-3), _ref_stack(1.0e-3), _ref_stack(2.0e-3)]
    out = {}
    for P_body in (5.0, 0.0):
        rows = [_solve(s, _ref_params(P_body=P_body)) for s in stacks]
        Q = [r[2]["Q_front_W"] for r in rows]
        TH = [r[2]["T_H_C"] for r in rows]
        R0 = rows[0][0]
        predicate = 0.10 * (R0["R_conv_K_W"] - R0["R_rej_K_W"]) < 2.0 * R0["R_rej_K_W"] * P_body
        out[P_body] = (predicate, Q[0] > Q[1] > Q[2], TH[0] < TH[1] < TH[2])
    ok = all(out[5.0]) and not any(out[0.0])
    return ok, ("P_body=5: predicate %s, Q_front decreasing %s, T_H increasing %s | "
                "P_body=0 (sensor only): predicate %s, Q_front decreasing %s, T_H increasing %s "
                "(all three expected False)") % (out[5.0] + out[0.0])


def v13_rejects_unphysical_inputs():
    results = []
    for fn, args, exc in ((conductance_W_K, (-1.0,), ValueError),
                          (parse_R_rej, (0.0,), ConfigError),
                          (parse_R_rej, (-2.0,), ConfigError),
                          (layer_resistance_K_W, (-1e-3, 0.27, 0.01), ValueError)):
        try:
            fn(*args)
            results.append(False)
        except exc:
            results.append(True)
    results.append(math.isinf(parse_R_rej(BLOCKED)))
    return all(results), "rejections and blocked token: %r" % (results,)


def run_validation():
    tests = [v01_zero_sources_equal_connected_reservoirs, v02_rear_disabled_single_series_branch,
             v03_no_sensor_parallel_split, v04_symmetric_network, v05_both_exits_blocked_detection,
             v06_boundary_shift_invariance, v07_sensor_power_counted_once,
             v08_hand_derived_example_H1_5W, v09_zero_internal_resistance_merged_node,
             v10_front_path_absent, v11_three_formulations_agree,
             v12_thickness_monotonicity_and_exception, v13_rejects_unphysical_inputs]
    n_fail = 0
    for t in tests:
        try:
            ok, detail = t()
        except Exception as exc:                 # report; never hide
            ok, detail = False, "exception: %r" % (exc,)
        n_fail += 0 if ok else 1
        print("%-4s %-46s %s" % ("PASS" if ok else "FAIL", t.__name__, detail))
    print("validation: %d test(s), %d failed; analytic self-consistency only, no empirical content"
          % (len(tests), n_fail))
    return 0 if n_fail == 0 else 1


# ----------------------------------------------------------------------------
# 7. command line
# ----------------------------------------------------------------------------

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("run", "validate", "-h", "--help"):
        argv.insert(0, "run")                    # default mode: the small reference comparison
    ap = argparse.ArgumentParser(prog="thermal_contract_t0.py",
                                 description="T0-HYP-1 steady two-node reference model (model results only)")
    sub = ap.add_subparsers(dest="cmd")
    run_p = sub.add_parser("run", help="small reference comparison (default)")
    run_p.add_argument("--config", required=True, help="JSON configuration path (read only)")
    run_p.add_argument("--out", required=True, help="JSON results path (no overwrite without --force)")
    run_p.add_argument("--force", action="store_true", help="allow overwriting an existing output file")
    sub.add_parser("validate", help="run analytic self-checks; writes no files")
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 2
    try:
        if args.cmd == "validate":
            return run_validation()
        return run_study(args.config, args.out, args.force)
    except (ConfigError, ValueError, OSError, json.JSONDecodeError, ArithmeticError) as exc:
        sys.stderr.write("error: %s\n" % (exc,))
        return 1


if __name__ == "__main__":
    sys.exit(main())
