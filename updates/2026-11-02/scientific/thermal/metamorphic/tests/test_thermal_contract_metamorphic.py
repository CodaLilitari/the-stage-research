#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
test_thermal_contract_metamorphic.py
====================================
Independent metamorphic and property-based tests for thermal_contract.py, the steady
two-node through-thickness reference model of contract T0-HYP-1 (The Stage).

Authorship and status
---------------------
Written as text and NOT executed by its author (Red / Claude, made by Anthropic;
coordinated with Richard Pemberton).  Module under test: original implementation by
Claude Fable 5.1, three repairs by Coda (Codex Lily).  Exact rational reference:
validation/thermal/thermal_reference.py (Coda).  Every expected relation below is a
mathematical property of a hypothetical linear network model; nothing here measures,
validates or certifies any physical object.

Conventions
-----------
* Standard library only, deterministic (seeded random.Random), no network, no file writes.
* Case counts are bounded: THERMAL_TEST_CASES (default 300, max 3000) per property,
  THERMAL_TEST_CONFIGS (default 8, max 50) random configurations.
* Each test states its mathematical justification in a comment.
* Tolerances are combined absolute/relative:  |a-b| <= tol (1 + |a| + |b|), tol = 1e-9
  unless a limit test states otherwise.  They are numerical criteria, not accuracy claims.

Environment
-----------
  THERMAL_CONTRACT_PATH         path of the thermal_contract.py under test (required)
  THERMAL_REFERENCE_PATH        path of thermal_reference.py (optional; else the layout
                                <...>/thermal/thermal_reference.py is searched upward)
  THERMAL_TEST_SEED             integer seed (default 20261101)
  THERMAL_TEST_INFORMATIONAL=1  also run expectations the contract does not promise

Comments marked "EXPECTED-DIFF" name tests that, by static reading of REPAIR.diff, should
fail on the frozen original and pass on the repaired copy.  Those are predictions, not results.
"""

import copy
import importlib.util
import json
import math
import os
import random
import unittest
from fractions import Fraction as F

# ----------------------------------------------------------------------------
# module loading (no side effects beyond importing the two modules)
# ----------------------------------------------------------------------------


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot build an import spec for %r" % (path,))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONTRACT_PATH = os.environ.get("THERMAL_CONTRACT_PATH", "")
tc = None
LOAD_ERROR = ""
if CONTRACT_PATH and os.path.isfile(CONTRACT_PATH):
    try:
        tc = _load("thermal_contract_under_test", CONTRACT_PATH)
    except Exception as exc:                     # report, never hide
        LOAD_ERROR = "import of %r failed: %r" % (CONTRACT_PATH, exc)
else:
    LOAD_ERROR = "THERMAL_CONTRACT_PATH is unset or does not name a file"


def _find_reference():
    cand = os.environ.get("THERMAL_REFERENCE_PATH", "")
    if cand and os.path.isfile(cand):
        return cand
    if not CONTRACT_PATH:
        return ""
    base = os.path.dirname(os.path.abspath(CONTRACT_PATH))
    for _ in range(4):
        base = os.path.dirname(base)
        guess = os.path.join(base, "thermal", "thermal_reference.py")
        if os.path.isfile(guess):
            return guess
    return ""


REF_PATH = _find_reference()
ref = None
if REF_PATH:
    try:
        ref = _load("thermal_reference_exact", REF_PATH)
    except Exception:
        ref = None


def setUpModule():
    if tc is None:
        raise unittest.SkipTest(LOAD_ERROR)


# ----------------------------------------------------------------------------
# constants and helpers
# ----------------------------------------------------------------------------

SEED = int(os.environ.get("THERMAL_TEST_SEED", "20261101"))
N = max(10, min(int(os.environ.get("THERMAL_TEST_CASES", "300")), 3000))
N_CFG = max(2, min(int(os.environ.get("THERMAL_TEST_CONFIGS", "8")), 50))
TOL = 1e-9
INFORMATIONAL = os.environ.get("THERMAL_TEST_INFORMATIONAL", "0") not in ("", "0", "false", "no")

# Reduced copy of the required fields of the sample plan (values as in sample_plan.json);
# documentation-only fields are omitted because validate_config ignores unknown keys.
BASE_CFG = {
    "schema": "stage.thermal_contract.steady",
    "schema_version": "T0-HYP-1.0",
    "study_id": "T0-HYP-1_metamorphic_tests",
    "geometry": {"area_m2": 0.01},
    "materials": {
        "silicone_ref": {"k_W_mK": 0.27, "k_assumed_range_W_mK": [0.18, 0.35], "density_kg_m3": 1030},
        "polyimide_film_ref": {"k_W_mK": 0.2, "k_assumed_range_W_mK": [0.12, 0.25], "density_kg_m3": 1420},
    },
    "contacts": {"r_c_m2K_W": 0.0002, "r_c_assumed_range_m2K_W": [0.0, 0.002]},
    "stacks": [
        {"stack_id": "H1", "t_outer_silicone_m": 0.0005, "t_film_m": 0.00005, "t_inner_silicone_m": 0.0005},
        {"stack_id": "H2", "t_outer_silicone_m": 0.001, "t_film_m": 0.00005, "t_inner_silicone_m": 0.001},
        {"stack_id": "H3", "t_outer_silicone_m": 0.002, "t_film_m": 0.00005, "t_inner_silicone_m": 0.002},
    ],
    "thickness_perturbation": {"fraction": 0.1},
    "boundaries": {
        "T_amb_C": 25.0, "T_res_C": 25.0,
        "h_W_m2K": 8.0, "h_assumed_range_W_m2K": [3.0, 15.0],
        "R_rej_K_W": 2.0, "R_rej_assumed_range_K_W": [1.0, 10.0], "R_rej_blocked_token": "blocked",
    },
    "sources": {"body": {"node": "H", "P_W_list": [1.0, 5.0, 10.0]}, "sensor": {"node": "S", "P_W": 0.1}},
    "comparators": {"outer_surface_C": 40.0, "internal_node_C": 60.0, "label": "study_comparator_only"},
    "numerics": {"energy_abs_tol_W": 1e-10, "energy_rel_tol": 1e-10, "agreement_tol_K": 1e-9},
    "scenario_plan": "deterministic_builtin_v1",
}

SECTIONS = ("geometry", "materials", "contacts", "thickness_perturbation",
            "boundaries", "sources", "comparators", "numerics")

NUMERIC_LEAVES = [
    ("geometry", "area_m2"),
    ("materials", "silicone_ref", "k_W_mK"), ("materials", "silicone_ref", "density_kg_m3"),
    ("materials", "polyimide_film_ref", "k_W_mK"), ("materials", "polyimide_film_ref", "density_kg_m3"),
    ("contacts", "r_c_m2K_W"),
    ("stacks", 0, "t_outer_silicone_m"), ("stacks", 0, "t_film_m"), ("stacks", 1, "t_inner_silicone_m"),
    ("thickness_perturbation", "fraction"),
    ("boundaries", "T_amb_C"), ("boundaries", "T_res_C"), ("boundaries", "h_W_m2K"), ("boundaries", "R_rej_K_W"),
    ("sources", "sensor", "P_W"),
    ("comparators", "outer_surface_C"), ("comparators", "internal_node_C"),
    ("numerics", "energy_abs_tol_W"), ("numerics", "energy_rel_tol"), ("numerics", "agreement_tol_K"),
]
RANGE_LEAVES = [
    ("materials", "silicone_ref", "k_assumed_range_W_mK"),
    ("materials", "polyimide_film_ref", "k_assumed_range_W_mK"),
    ("contacts", "r_c_assumed_range_m2K_W"),
    ("boundaries", "h_assumed_range_W_m2K"),
    ("boundaries", "R_rej_assumed_range_K_W"),
]
STRING_LEAVES = [
    ("schema",), ("schema_version",), ("study_id",), ("stacks", 0, "stack_id"),
    ("boundaries", "R_rej_blocked_token"), ("sources", "body", "node"), ("sources", "sensor", "node"),
    ("comparators", "label"), ("scenario_plan",),
]
REQUIRED_PATHS = (
    [("schema",), ("schema_version",), ("study_id",), ("scenario_plan",), ("stacks",)]
    + [(s,) for s in SECTIONS]
    + NUMERIC_LEAVES + RANGE_LEAVES + STRING_LEAVES
    + [("materials", "silicone_ref"), ("materials", "polyimide_film_ref"),
       ("sources", "body"), ("sources", "sensor"), ("sources", "body", "P_W_list")]
)

BAD_NUMBERS = [None, "1.0", True, False, [], {}, float("nan"), math.inf, -math.inf, 10 ** 400, b"1"]
BAD_STRINGS = [None, 1, 1.5, True, [], {}, "", "unexpected"]
BAD_RANGES = [None, 5, "1,2", [1.0], [0.1, 0.2, 0.3], [0.2, 0.1], ["0.1", 0.2],
              [float("nan"), 0.2], [0.1, math.inf], [True, 0.2], {}]
BAD_LOADS = [None, "1,5,10", [], [1.0], [1.0, 5.0], [1.0, 5.0, 10.0, 20.0], [10.0, 5.0, 1.0],
             [1.0, "5", 10.0], [1.0, None, 10.0], [1.0, True, 10.0], [1.0, float("nan"), 10.0],
             [1.0, 5.0, math.inf], {}]


def close(a, b, tol=TOL):
    return abs(a - b) <= tol * (1.0 + abs(a) + abs(b))


def rnd_dec(rng, lo, hi, nd):
    """Uniform draw rounded to nd decimals.  repr() of the result is then a short decimal that
    round-trips, so Fraction(repr(x)) is an exact rational value of the float the code receives."""
    return round(rng.uniform(lo, hi), nd)


def rnd_log(rng, lo, hi, sig=6):
    """Log-uniform draw truncated to sig significant decimal digits (same exactness argument)."""
    return float("%.*g" % (sig, math.exp(rng.uniform(math.log(lo), math.log(hi)))))


def exact(x):
    """Exact rational value of a short-decimal float / int; +-inf is passed through unchanged."""
    if isinstance(x, bool):
        raise TypeError("bool is not a model number")
    if isinstance(x, int):
        return F(x)
    if isinstance(x, float):
        if math.isinf(x):
            return x
        return F(repr(x))
    return F(x)


def base_params(**over):
    p = {"area_m2": 0.01, "k_sil": 0.27, "k_film": 0.2, "r_c_inner": 2e-4, "r_c_outer": 2e-4,
         "h": 8.0, "R_rej": 2.0, "T_amb": 25.0, "T_res": 25.0, "P_body": 5.0, "P_sensor": 0.1,
         "t_scale_inner": 1.0, "t_scale_outer": 1.0, "t_scale_film": 1.0}
    p.update(over)
    return p


def rand_stack(rng, tag="S"):
    """Positive silicone thicknesses (R_HS > 0 unless a test zeroes them); film may be absent."""
    return {"stack_id": tag,
            "t_outer_silicone_m": rnd_dec(rng, 1e-5, 3e-3, 7),
            "t_film_m": rng.choice([0.0, rnd_dec(rng, 1e-5, 2e-4, 7)]),
            "t_inner_silicone_m": rnd_dec(rng, 1e-5, 3e-3, 7)}


def rand_params(rng, **fixed):
    """Moderate in-domain draw: conductance ratios stay within ~1e6, sources nonnegative."""
    p = base_params(
        area_m2=rnd_log(rng, 1e-3, 0.1),
        k_sil=rnd_dec(rng, 0.1, 1.0, 4),
        k_film=rnd_dec(rng, 0.1, 0.5, 4),
        r_c_inner=rnd_dec(rng, 0.0, 3e-3, 6),
        r_c_outer=rnd_dec(rng, 0.0, 3e-3, 6),
        h=rnd_dec(rng, 0.5, 50.0, 3),
        R_rej=rnd_dec(rng, 0.3, 30.0, 3),
        T_amb=rnd_dec(rng, -30.0, 60.0, 3),
        T_res=rnd_dec(rng, -30.0, 60.0, 3),
        P_body=rnd_dec(rng, 0.0, 20.0, 4),
        P_sensor=rnd_dec(rng, 0.0, 1.0, 4))
    p.update(fixed)
    return p


def solve_path(stack, p, cmp_=None, num=None):
    """Assemble -> solve -> reconstruct through the module's public functions."""
    R = tc.assemble_resistances(stack, p)
    sol = tc.solve_two_node(tc.conductance_W_K(R["R_HS_K_W"]), tc.conductance_W_K(R["R_SA_K_W"]),
                            tc.conductance_W_K(R["R_rej_K_W"]),
                            p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
    res = None
    if sol["T_H"] is not None:
        res = tc.reconstruct(sol, R, p, cmp_ or tc.DEFAULT_CMP, num or tc.DEFAULT_NUM)
    return R, sol, res


def cond(cid="T", P_body=5.0, **over):
    d = {"condition_id": cid, "group": "T_metamorphic", "P_body": P_body}
    d.update(over)
    return d


def set_path(cfg, path, value):
    node = cfg
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def del_path(cfg, path):
    node = cfg
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]


def run_all_cases(cfg):
    conds = tc.build_shared_conditions(cfg)
    return [tc.run_case(cfg, s, c) for c in conds for s in cfg["stacks"]]


def exact_network(A, k, kf, t_in, t_out, t_f, rc_in, rc_out, h, R_rej, P, J, T_amb, T_res):
    """Independent exact assembly in the reference's heat-flow variables (route of review.py's
    exact_case, generalised to split contacts, h = 0, arbitrary boundaries and area)."""
    half_film = t_f / (2 * kf * A)
    a = t_in / (k * A) + rc_in / A + half_film
    conv = math.inf if h == 0 else 1 / (h * A)
    b_solid = t_out / (k * A) + rc_out / A + half_film
    b = b_solid + conv
    sol = ref.steady(a, b, R_rej, P, J, T_amb, T_res, conv)
    sol.update({"a": a, "b": b, "conv": conv, "b_solid": b_solid, "P": P, "J": J})
    return sol


def exact_from_params(stack, p):
    e = exact
    A = e(p["area_m2"])
    t_in = e(stack["t_inner_silicone_m"]) * e(p["t_scale_inner"])
    t_out = e(stack["t_outer_silicone_m"]) * e(p["t_scale_outer"])
    t_f = e(stack["t_film_m"]) * e(p["t_scale_film"])
    rear = p["R_rej"] if (isinstance(p["R_rej"], float) and math.isinf(p["R_rej"])) else e(p["R_rej"])
    return exact_network(A, e(p["k_sil"]), e(p["k_film"]), t_in, t_out, t_f, e(p["r_c_inner"]),
                         e(p["r_c_outer"]), e(p["h"]), rear, e(p["P_body"]), e(p["P_sensor"]),
                         e(p["T_amb"]), e(p["T_res"]))


def exact_from_cfg_cond(cfg, stack, cnd):
    e = exact
    A = e(cfg["geometry"]["area_m2"])
    k = e(cnd.get("k_sil", cfg["materials"]["silicone_ref"]["k_W_mK"]))
    kf = e(cnd.get("k_film", cfg["materials"]["polyimide_film_ref"]["k_W_mK"]))
    bias = 1 + e(cnd.get("t_bias", 0))
    t_in = e(stack["t_inner_silicone_m"]) * bias * (1 + e(cnd.get("t_dev_inner", 0)))
    t_out = e(stack["t_outer_silicone_m"]) * bias * (1 + e(cnd.get("t_dev_outer", 0)))
    t_f = e(stack["t_film_m"])
    common = cnd.get("r_c", cfg["contacts"]["r_c_m2K_W"])
    rc_in = e(cnd.get("r_c_inner", common))
    rc_out = e(cnd.get("r_c_outer", common))
    h = e(cnd.get("h", cfg["boundaries"]["h_W_m2K"]))
    rear = cnd.get("R_rej", cfg["boundaries"]["R_rej_K_W"])
    rear = math.inf if rear == "blocked" else e(rear)
    P = e(cnd["P_body"])
    J = e(cnd.get("P_sensor", cfg["sources"]["sensor"]["P_W"]))
    T_amb = e(cnd.get("T_amb", cfg["boundaries"]["T_amb_C"]))
    T_res = e(cnd.get("T_res", cfg["boundaries"]["T_res_C"]))
    sol = exact_network(A, k, kf, t_in, t_out, t_f, rc_in, rc_out, h, rear, P, J, T_amb, T_res)
    sol.update({"t_in": t_in, "t_out": t_out, "t_f": t_f, "A": A})
    return sol


def rand_config(rng):
    """Random configuration that must satisfy every documented admission rule."""
    cfg = copy.deepcopy(BASE_CFG)
    cfg["study_id"] = "random_%d" % rng.randrange(10 ** 6)
    cfg["geometry"]["area_m2"] = rnd_log(rng, 1e-3, 0.1)
    for key, lo_rng, hi_rng in (("silicone_ref", (0.05, 0.2), (0.3, 1.0)),
                                ("polyimide_film_ref", (0.05, 0.15), (0.2, 0.6))):
        lo = rnd_dec(rng, lo_rng[0], lo_rng[1], 3)
        hi = rnd_dec(rng, hi_rng[0], hi_rng[1], 3)
        mat = cfg["materials"][key]
        mat["k_W_mK"] = rnd_dec(rng, lo, hi, 3)
        mat["k_assumed_range_W_mK"] = [lo, hi]
        mat["density_kg_m3"] = rnd_dec(rng, 800.0, 1600.0, 1)
    rc_hi = rnd_dec(rng, 1e-4, 5e-3, 5)
    cfg["contacts"] = {"r_c_m2K_W": rnd_dec(rng, 0.0, rc_hi, 5), "r_c_assumed_range_m2K_W": [0.0, rc_hi]}
    t_film = rnd_dec(rng, 1e-5, 1e-4, 6)
    cfg["stacks"] = [{"stack_id": "S%d" % i, "t_outer_silicone_m": rnd_dec(rng, 1e-4, 3e-3, 6),
                      "t_film_m": t_film, "t_inner_silicone_m": rnd_dec(rng, 1e-4, 3e-3, 6)}
                     for i in range(rng.randint(1, 4))]
    cfg["thickness_perturbation"] = {"fraction": rnd_dec(rng, 0.0, 0.5, 2)}
    h_lo, h_hi = rnd_dec(rng, 0.5, 5.0, 2), rnd_dec(rng, 10.0, 50.0, 2)
    R_lo, R_hi = rnd_dec(rng, 0.2, 2.0, 2), rnd_dec(rng, 5.0, 50.0, 2)
    cfg["boundaries"] = {"T_amb_C": rnd_dec(rng, -20.0, 40.0, 1), "T_res_C": rnd_dec(rng, -20.0, 40.0, 1),
                         "h_W_m2K": rnd_dec(rng, h_lo, h_hi, 2), "h_assumed_range_W_m2K": [h_lo, h_hi],
                         "R_rej_K_W": rnd_dec(rng, R_lo, R_hi, 2), "R_rej_assumed_range_K_W": [R_lo, R_hi],
                         "R_rej_blocked_token": "blocked"}
    while True:
        loads = sorted(rnd_dec(rng, 0.0, 30.0, 2) for _ in range(3))
        if len(set(loads)) == 3 and len({"%g" % x for x in loads}) == 3:
            break
    cfg["sources"] = {"body": {"node": "H", "P_W_list": loads},
                      "sensor": {"node": "S", "P_W": rnd_dec(rng, 0.0, 1.0, 3)}}
    return cfg


def my_sanitize(obj):
    if isinstance(obj, dict):
        return {k: my_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [my_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        if math.isnan(obj):
            return None
    return obj


def rand_json_like(rng, depth=0):
    r = rng.random()
    if depth < 3 and r < 0.3:
        return {"k%d" % i: rand_json_like(rng, depth + 1) for i in range(rng.randint(0, 4))}
    if depth < 3 and r < 0.5:
        return [rand_json_like(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return rng.choice([math.inf, -math.inf, math.nan, 0, 1, -7, 2.5, True, False, None, "txt", "inf"])


class _Base(unittest.TestCase):
    def assertClose(self, a, b, tol=TOL, msg=None):
        if not close(a, b, tol):
            self.fail("%r !~ %r (tol %g)%s" % (a, b, tol, "" if msg is None else ": %s" % (msg,)))

    def assertLE(self, a, b, tol=TOL, msg=None):
        """a <= b up to rounding (b + tol (1 + |a| + |b|))."""
        if not (a <= b + tol * (1.0 + abs(a) + abs(b))):
            self.fail("%r <= %r failed (tol %g)%s" % (a, b, tol, "" if msg is None else ": %s" % (msg,)))


# ----------------------------------------------------------------------------
# 1. solve_two_node on the abstract conductance network
# ----------------------------------------------------------------------------

class TestSolverAlgebra(_Base):

    def setUp(self):
        self.rng = random.Random(SEED + 1)

    def draw_G(self, lo=1e-3, hi=1e3):
        return rnd_log(self.rng, lo, hi), rnd_log(self.rng, lo, hi), rnd_log(self.rng, lo, hi)

    def draw_PT(self, nonneg=False):
        rng = self.rng
        Pb = rnd_dec(rng, 0.0 if nonneg else -20.0, 20.0, 4)
        Ps = rnd_dec(rng, 0.0 if nonneg else -2.0, 2.0, 4)
        return Pb, Ps, rnd_dec(rng, -40.0, 80.0, 3), rnd_dec(rng, -40.0, 80.0, 3)

    def test_node_balances_hold_for_random_draws(self):
        # Definition of the steady state: (T_H, T_S) must satisfy
        #   P_body = G_HS (T_H - T_S) + G_rej (T_H - T_res)      and
        #   P_sensor + G_HS (T_H - T_S) = G_SA (T_S - T_amb)
        # up to rounding scaled by the sizes of the terms (backward-error form).
        for _ in range(N):
            G_HS, G_SA, G_rej = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT()
            sol = tc.solve_two_node(G_HS, G_SA, G_rej, Pb, Ps, Ta, Tr)
            self.assertEqual(sol["status"], "solved")
            TH, TS = sol["T_H"], sol["T_S"]
            q_hs, q_rear, q_front = G_HS * (TH - TS), G_rej * (TH - Tr), G_SA * (TS - Ta)
            args = (G_HS, G_SA, G_rej, Pb, Ps, Ta, Tr)
            self.assertLessEqual(abs(Pb - q_hs - q_rear),
                                 TOL * (1.0 + abs(Pb) + abs(q_hs) + abs(q_rear)), args)
            self.assertLessEqual(abs(Ps + q_hs - q_front),
                                 TOL * (1.0 + abs(Ps) + abs(q_hs) + abs(q_front)), args)

    def test_superposition_in_sources_with_zero_boundaries(self):
        # With T_amb = T_res = 0 the right-hand side is linear in (P_body, P_sensor) and M is
        # fixed, so  T(a P1 + b P2) = a T(P1) + b T(P2)  for every scalar pair (a, b).
        for _ in range(N):
            G = self.draw_G()
            P1 = (rnd_dec(self.rng, -20, 20, 4), rnd_dec(self.rng, -2, 2, 4))
            P2 = (rnd_dec(self.rng, -20, 20, 4), rnd_dec(self.rng, -2, 2, 4))
            a, b = rnd_dec(self.rng, -3, 3, 3), rnd_dec(self.rng, -3, 3, 3)
            s1 = tc.solve_two_node(*G, P1[0], P1[1], 0.0, 0.0)
            s2 = tc.solve_two_node(*G, P2[0], P2[1], 0.0, 0.0)
            s12 = tc.solve_two_node(*G, a * P1[0] + b * P2[0], a * P1[1] + b * P2[1], 0.0, 0.0)
            for k in ("T_H", "T_S"):
                self.assertClose(s12[k], a * s1[k] + b * s2[k], msg=(G, P1, P2, a, b, k))

    def test_boundary_terms_superpose_and_act_as_convex_weights(self):
        # RHS = [P_body + G_rej T_res, P_sensor + G_SA T_amb] is affine in (T_amb, T_res), so
        #   T(P, Ta, Tr) = T(P, 0, 0) + T(0, Ta, Tr).
        # With zero sources M [1,1]^T = [G_rej, G_SA]^T, hence a uniform boundary c gives the
        # uniform field (c, c); and because M^-1 >= 0 entrywise with weight rows summing to one,
        # T(0, Ta, Tr) lies between min(Ta, Tr) and max(Ta, Tr).
        for _ in range(N):
            G = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT()
            full = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            src = tc.solve_two_node(*G, Pb, Ps, 0.0, 0.0)
            bnd = tc.solve_two_node(*G, 0.0, 0.0, Ta, Tr)
            uni = tc.solve_two_node(*G, 0.0, 0.0, Ta, Ta)
            lo, hi = min(Ta, Tr), max(Ta, Tr)
            for k in ("T_H", "T_S"):
                self.assertClose(full[k], src[k] + bnd[k], msg=(G, Pb, Ps, Ta, Tr, k))
                self.assertClose(uni[k], Ta, msg=(G, Ta, k))
                self.assertLE(lo, bnd[k], msg=(G, Ta, Tr, k))
                self.assertLE(bnd[k], hi, msg=(G, Ta, Tr, k))

    def test_common_boundary_shift_moves_temperatures_not_heat_rates(self):
        # Only differences enter (no radiation): adding D to both boundaries adds D to each node
        # temperature and leaves each heat rate unchanged (generalises built-in v06 to random D).
        for _ in range(N):
            G_HS, G_SA, G_rej = G = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT()
            D = rnd_dec(self.rng, -100.0, 100.0, 3)
            s0 = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            s1 = tc.solve_two_node(*G, Pb, Ps, Ta + D, Tr + D)
            self.assertClose(s1["T_H"] - s0["T_H"], D)
            self.assertClose(s1["T_S"] - s0["T_S"], D)
            self.assertClose(G_HS * (s1["T_H"] - s1["T_S"]), G_HS * (s0["T_H"] - s0["T_S"]))
            self.assertClose(G_rej * (s1["T_H"] - (Tr + D)), G_rej * (s0["T_H"] - Tr))
            self.assertClose(G_SA * (s1["T_S"] - (Ta + D)), G_SA * (s0["T_S"] - Ta))

    def test_joint_scaling_of_conductances_and_sources_preserves_temperatures(self):
        # (G, P) -> (lam G, lam P) with the same boundary temperatures multiplies both sides of
        # M T = P + G_b T_b by lam: identical solution.  Scaling conductances alone with zero
        # boundaries scales the temperature rises by 1/lam.
        for _ in range(N):
            G = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT()
            lam = self.rng.choice([0.001, 0.25, 0.5, 2.0, 7.0, 1000.0])
            Gl = (G[0] * lam, G[1] * lam, G[2] * lam)
            s0 = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            s1 = tc.solve_two_node(*Gl, Pb * lam, Ps * lam, Ta, Tr)
            z0 = tc.solve_two_node(*G, Pb, Ps, 0.0, 0.0)
            z1 = tc.solve_two_node(*Gl, Pb, Ps, 0.0, 0.0)
            for k in ("T_H", "T_S"):
                self.assertClose(s1[k], s0[k], msg=(G, lam, k))
                self.assertClose(z1[k] * lam, z0[k], msg=(G, lam, k))

    def test_H_S_role_swap_symmetry(self):
        # Relabelling H <-> S together with their exits, (G_rej, P_body, T_res) <-> (G_SA, P_sensor,
        # T_amb), maps the two-node network onto itself; therefore the solution components swap and
        # the determinant G_HS G_SA + G_HS G_rej + G_rej G_SA is unchanged.
        for _ in range(N):
            G_HS, G_SA, G_rej = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT()
            a = tc.solve_two_node(G_HS, G_SA, G_rej, Pb, Ps, Ta, Tr)
            b = tc.solve_two_node(G_HS, G_rej, G_SA, Ps, Pb, Tr, Ta)
            self.assertClose(a["T_H"], b["T_S"])
            self.assertClose(a["T_S"], b["T_H"])
            self.assertClose(a["det_W2_K2"], b["det_W2_K2"], 1e-12)

    def test_gauss_cross_check_present_and_consistent_for_bounded_ratios(self):
        # Both the closed-form inverse and pivoted elimination solve the same nonsingular 2x2 system.
        # With conductance ratios within 1e4 the elimination pivot cannot cancel to zero, so the
        # cross-check must be available (not None) and agree with the closed form.
        for _ in range(N):
            G = self.draw_G(1e-2, 1e2)
            Pb, Ps, Ta, Tr = self.draw_PT()
            sol = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            self.assertIsNotNone(sol["T_H_gauss"], (G, Pb, Ps, Ta, Tr))
            self.assertIsNotNone(sol["T_S_gauss"], (G, Pb, Ps, Ta, Tr))
            self.assertClose(sol["T_H_gauss"], sol["T_H"], msg=(G, Pb, Ps, Ta, Tr))
            self.assertClose(sol["T_S_gauss"], sol["T_S"], msg=(G, Pb, Ps, Ta, Tr))

    def test_det_matches_formula_and_single_zero_patterns_remain_solvable(self):
        # det M = G_HS G_SA + G_HS G_rej + G_rej G_SA > 0 iff at most one conductance is zero (each
        # node still reaches a boundary); the reported det must equal the formula.
        for _ in range(N):
            G = list(self.draw_G())
            z = self.rng.choice([None, 0, 1, 2])
            if z is not None:
                G[z] = 0.0
            Pb, Ps, Ta, Tr = self.draw_PT()
            sol = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            self.assertEqual(sol["status"], "solved", (G, Pb, Ps, Ta, Tr))
            det = G[0] * G[1] + G[0] * G[2] + G[2] * G[1]
            self.assertClose(sol["det_W2_K2"], det, 1e-12)
            self.assertGreater(sol["det_W2_K2"], 0.0)
            self.assertTrue(math.isfinite(sol["T_H"]) and math.isfinite(sol["T_S"]))

    def test_maximum_principle_for_signed_sources(self):
        # M^-1 = (1/det) [[G_HS+G_SA, G_HS], [G_HS, G_HS+G_rej]] >= 0 entrywise.  With P >= 0 every
        # node is at or above min(T_amb, T_res); with P <= 0 at or below max(T_amb, T_res).
        for _ in range(N):
            G = self.draw_G()
            Pb, Ps, Ta, Tr = self.draw_PT(nonneg=True)
            lo, hi = min(Ta, Tr), max(Ta, Tr)
            up = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            dn = tc.solve_two_node(*G, -Pb, -Ps, Ta, Tr)
            for k in ("T_H", "T_S"):
                self.assertLE(lo, up[k], msg=(G, Pb, Ps, Ta, Tr, k))
                self.assertLE(dn[k], hi, msg=(G, Pb, Ps, Ta, Tr, k))

    def test_temperatures_nonincreasing_in_each_exit_conductance(self):
        # Equal boundaries T0 and P >= 0:  T_H - T0 = [(G_HS+G_SA) P_b + G_HS P_s]/det,
        # T_S - T0 = [G_HS P_b + (G_HS+G_rej) P_s]/det.  d(T_H)/dG_rej <= 0 (numerator fixed, det
        # increasing); d(T_S)/dG_rej = (-G_HS^2 P_s - G_HS P_b (G_HS+G_SA))/det^2 <= 0; and
        # symmetrically in G_SA.  Strengthening either exit cannot warm either node.
        for _ in range(N):
            G_HS, G_SA, G_rej = self.draw_G()
            Pb, Ps = rnd_dec(self.rng, 0, 20, 4), rnd_dec(self.rng, 0, 2, 4)
            T0 = rnd_dec(self.rng, -40, 80, 3)
            f = self.rng.choice([1.5, 2.0, 5.0, 50.0])
            s0 = tc.solve_two_node(G_HS, G_SA, G_rej, Pb, Ps, T0, T0)
            s_rej = tc.solve_two_node(G_HS, G_SA, G_rej * f, Pb, Ps, T0, T0)
            s_sa = tc.solve_two_node(G_HS, G_SA * f, G_rej, Pb, Ps, T0, T0)
            for k in ("T_H", "T_S"):
                self.assertLE(s_rej[k], s0[k], msg=("G_rej", k))
                self.assertLE(s_sa[k], s0[k], msg=("G_SA", k))

    def test_internal_conductance_cools_the_sourced_node_and_warms_the_other(self):
        # Single source at H (P_s = 0, equal boundaries): d(T_H)/dG_HS = -G_SA^2 P_b/det^2 <= 0 and
        # d(T_S)/dG_HS = G_rej G_SA P_b/det^2 >= 0.  By the role symmetry the mirrored statement holds
        # for a single source at S.  (With both sources present no monotonicity is promised.)
        for _ in range(N):
            G_HS, G_SA, G_rej = self.draw_G()
            P = rnd_dec(self.rng, 0, 20, 4)
            T0 = rnd_dec(self.rng, -40, 80, 3)
            f = self.rng.choice([1.5, 2.0, 5.0, 50.0])
            a0 = tc.solve_two_node(G_HS, G_SA, G_rej, P, 0.0, T0, T0)
            a1 = tc.solve_two_node(G_HS * f, G_SA, G_rej, P, 0.0, T0, T0)
            self.assertLE(a1["T_H"], a0["T_H"])
            self.assertLE(a0["T_S"], a1["T_S"])
            b0 = tc.solve_two_node(G_HS, G_SA, G_rej, 0.0, P, T0, T0)
            b1 = tc.solve_two_node(G_HS * f, G_SA, G_rej, 0.0, P, T0, T0)
            self.assertLE(b1["T_S"], b0["T_S"])
            self.assertLE(b0["T_H"], b1["T_H"])

    def test_singular_patterns_classified_by_existence_of_a_steady_family(self):
        # det = 0 exactly iff at least two conductances are exactly zero.  A steady state then exists
        # iff every isolated component has zero net source:  {G_SA=G_rej=0, G_HS>0}: P_b + P_s = 0;
        # {G_HS=G_rej=0}: P_b = 0;  {G_HS=G_SA=0}: P_s = 0;  all zero: P_b = P_s = 0.
        # The status must start with 'nonunique' exactly when a family exists and with
        # 'no_finite_steady_state' otherwise, be a documented STATUS_NOTES key (never
        # 'singular_unclassified'), return no numbers, and not depend on the boundary temperatures.
        for _ in range(N):
            pos = [rnd_log(self.rng, 1e-2, 1e2) for _ in range(3)]
            zeros = self.rng.choice([(0, 1), (0, 2), (1, 2), (0, 1, 2)])
            G = [0.0 if i in zeros else pos[i] for i in range(3)]
            x, y = rnd_dec(self.rng, 0.5, 10, 3), rnd_dec(self.rng, 0.5, 10, 3)
            Pb = self.rng.choice([0.0, x, -x])
            Ps = self.rng.choice([0.0, y, -y, -Pb])
            Ta, Tr = rnd_dec(self.rng, -40, 80, 3), rnd_dec(self.rng, -40, 80, 3)
            G_HS, G_SA, G_rej = G
            if G_SA == 0.0 and G_rej == 0.0 and G_HS != 0.0:
                exists = (Pb + Ps == 0.0)
            elif G_HS == 0.0 and G_SA == 0.0 and G_rej == 0.0:
                exists = (Pb == 0.0 and Ps == 0.0)
            elif G_HS == 0.0 and G_rej == 0.0:
                exists = (Pb == 0.0)
            else:
                exists = (Ps == 0.0)
            sol = tc.solve_two_node(*G, Pb, Ps, Ta, Tr)
            sol2 = tc.solve_two_node(*G, Pb, Ps, Ta + 10.0, Tr - 5.0)
            info = (G, Pb, Ps, sol["status"])
            self.assertEqual(sol["status"], sol2["status"], info)
            self.assertNotEqual(sol["status"], "singular_unclassified", info)
            self.assertIn(sol["status"], tc.STATUS_NOTES, info)
            self.assertIsNone(sol["T_H"], info)
            self.assertIsNone(sol["T_S"], info)
            self.assertEqual(sol["det_W2_K2"], 0.0, info)
            if exists:
                self.assertTrue(sol["status"].startswith("nonunique"), info)
            else:
                self.assertTrue(sol["status"].startswith("no_finite_steady_state"), info)

    def test_tiny_but_positive_exit_never_crashes_the_unique_solution(self):
        # det = G_HS G_rej > 0 whenever G_SA = 0 and G_rej > 0, so the closed form exists for every
        # positive G_rej however small:  T_H = T_res + P_total/G_rej,  T_S = T_H + P_sensor/G_HS.
        # The Gauss cross-check may be unavailable (None); when present it must at least be finite.
        # Agreement under this conditioning is NOT promised (repair report) -> informational class.
        # EXPECTED-DIFF: the frozen original raises ZeroDivisionError here (repair 1).
        for _ in range(N // 3):
            G_HS = rnd_log(self.rng, 1e-2, 1e2)
            G_rej = rnd_log(self.rng, 1e-20, 1e-12)
            Pb, Ps = rnd_dec(self.rng, 0.1, 20, 3), rnd_dec(self.rng, 0.0, 2, 3)
            sol = tc.solve_two_node(G_HS, 0.0, G_rej, Pb, Ps, 25.0, 25.0)
            self.assertEqual(sol["status"], "solved", (G_HS, G_rej))
            self.assertClose(sol["T_H"], 25.0 + (Pb + Ps) / G_rej, msg=(G_HS, G_rej))
            self.assertClose(sol["T_S"], sol["T_H"] + Ps / G_HS, msg=(G_HS, G_rej))
            if sol["T_H_gauss"] is not None:
                self.assertTrue(math.isfinite(sol["T_H_gauss"]) and math.isfinite(sol["T_S_gauss"]),
                                (G_HS, G_rej))

    def test_invalid_solver_inputs_raise_value_error(self):
        # Documented rejections: negative or NaN conductance, non-finite source/boundary, and the two
        # deliberately unimplemented pinning limits R_SA = 0 and R_rej = 0 (infinite exit conductance).
        nan, inf = float("nan"), math.inf
        bad = [(-1.0, 1, 1, 1, 0, 25, 25), (1, -1e-9, 1, 1, 0, 25, 25), (1, 1, -2.0, 1, 0, 25, 25),
               (nan, 1, 1, 1, 0, 25, 25), (1, nan, 1, 1, 0, 25, 25), (1, 1, nan, 1, 0, 25, 25),
               (1, 1, 1, inf, 0, 25, 25), (1, 1, 1, 1, nan, 25, 25), (1, 1, 1, 1, 0, inf, 25),
               (1, 1, 1, 1, 0, 25, -inf), (1, inf, 1, 1, 0, 25, 25), (1, 1, inf, 1, 0, 25, 25)]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    tc.solve_two_node(*args)


# ----------------------------------------------------------------------------
# 2. assembled physical network (assemble_resistances -> solve -> reconstruct)
# ----------------------------------------------------------------------------

class TestAssembledNetwork(_Base):

    def setUp(self):
        self.rng = random.Random(SEED + 2)

    def draw(self, equal_boundaries=False, **fixed):
        stack = rand_stack(self.rng)
        p = rand_params(self.rng)
        if equal_boundaries:
            p["T_res"] = p["T_amb"]
        p.update(fixed)
        return stack, p

    def test_energy_balance_and_bookkeeping(self):
        # Summed node balances: Q_front + Q_rear = P_body + P_sensor (sensor power counted once);
        # S balance: Q_front - Q_HS = P_sensor; H balance: Q_HS + Q_rear = P_body.  The derived fields
        # (demand, flux densities, residual, margins) are pure bookkeeping of these rates.
        for _ in range(N):
            stack, p = self.draw()
            mode = self.rng.random()
            if mode < 0.15:
                p["h"] = 0.0
            elif mode < 0.30:
                p["R_rej"] = math.inf
            R, sol, res = solve_path(stack, p)
            self.assertEqual(sol["status"], "solved", (stack, p))
            Pt = p["P_body"] + p["P_sensor"]
            self.assertClose(res["Q_front_W"] + res["Q_rear_W"], Pt)
            self.assertClose(res["Q_front_W"] - res["Q_HS_W"], p["P_sensor"])
            self.assertClose(res["Q_HS_W"] + res["Q_rear_W"], p["P_body"])
            self.assertEqual(res["reservoir_heat_demand_W"], res["Q_rear_W"])
            self.assertClose(res["q_front_W_m2"] * p["area_m2"], res["Q_front_W"], 1e-12)
            self.assertClose(res["q_inner_silicone_W_m2"] * p["area_m2"], res["Q_HS_W"], 1e-12)
            self.assertClose(res["energy_residual_W"], Pt - res["Q_front_W"] - res["Q_rear_W"], 1e-12)
            self.assertTrue(res["energy_check_pass"], (stack, p, res["energy_residual_W"]))
            self.assertLessEqual(abs(res["energy_residual_W"]), res["energy_tolerance_W"])
            self.assertClose(res["margin_outer_K_study_comparator_only"],
                             tc.DEFAULT_CMP["outer_surface_C"] - res["T_outer_C"], 1e-12)
            self.assertClose(res["margin_internal_K_study_comparator_only"],
                             tc.DEFAULT_CMP["internal_node_C"] - res["T_H_C"], 1e-12)

    def test_sign_conventions_with_equal_boundaries_and_nonnegative_sources(self):
        # Discrete maximum principle: with P >= 0 and T_amb = T_res = T0 every node is at or above T0,
        # heat leaves through both exits (Q_front, Q_rear >= 0), the outer surface lies between the
        # ambient and the sensor node along the series front path, and Q_HS has the sign of T_H - T_S.
        for _ in range(N):
            stack, p = self.draw(equal_boundaries=True)
            R, sol, res = solve_path(stack, p)
            T0 = p["T_amb"]
            self.assertLE(T0, res["T_H_C"])
            self.assertLE(T0, res["T_S_C"])
            self.assertLE(0.0, res["Q_front_W"])
            self.assertLE(0.0, res["Q_rear_W"])
            self.assertLE(T0, res["T_outer_C"])
            self.assertLE(res["T_outer_C"], res["T_S_C"])
            self.assertLE(0.0, res["Q_HS_W"] * (res["T_H_C"] - res["T_S_C"]))

    def test_zero_sources_reversed_boundaries_form_a_series_divider(self):
        # With P = 0 the network is the single series path reservoir -> H -> S -> outer -> ambient:
        # Q_front = -Q_rear = Q_HS = (T_res - T_amb)/(R_HS + R_SA + R_rej) and the temperatures are
        # ordered monotonically along the path (heat drawn from the reservoir when T_res > T_amb).
        for _ in range(N):
            stack, p = self.draw(P_body=0.0, P_sensor=0.0)
            if p["T_res"] <= p["T_amb"]:
                p["T_res"] = p["T_amb"] + rnd_dec(self.rng, 1.0, 50.0, 2)
            R, sol, res = solve_path(stack, p)
            Q = (p["T_res"] - p["T_amb"]) / (R["R_HS_K_W"] + R["R_SA_K_W"] + R["R_rej_K_W"])
            self.assertClose(res["Q_front_W"], Q)
            self.assertClose(res["Q_rear_W"], -Q)
            self.assertClose(res["Q_HS_W"], Q)
            self.assertLE(res["T_H_C"], p["T_res"])
            self.assertLE(res["T_S_C"], res["T_H_C"])
            self.assertLE(res["T_outer_C"], res["T_S_C"])
            self.assertLE(p["T_amb"], res["T_outer_C"])

    def test_outer_surface_follows_the_series_front_path(self):
        # Q_front crosses every front element (no source between S and ambient), so
        # T_S - T_outer = Q_front (R_SA - R_conv) and T_outer - T_amb = Q_front R_conv.  With h = 0
        # the front flux is exactly zero, R_conv = R_SA = inf and T_outer = T_S.
        for _ in range(N):
            stack, p = self.draw()
            R, sol, res = solve_path(stack, p)
            self.assertClose(res["T_S_C"] - res["T_outer_C"], res["Q_front_W"] * (R["R_SA_K_W"] - R["R_conv_K_W"]))
            self.assertClose(res["T_outer_C"] - p["T_amb"], res["Q_front_W"] * R["R_conv_K_W"])
            R0, sol0, res0 = solve_path(stack, dict(p, h=0.0))
            self.assertEqual(res0["Q_front_W"], 0.0)
            self.assertEqual(res0["T_outer_C"], res0["T_S_C"])
            self.assertTrue(math.isinf(R0["R_conv_K_W"]) and math.isinf(R0["R_SA_K_W"]))
            self.assertClose(res0["Q_rear_W"], p["P_body"] + p["P_sensor"])

    def test_resistance_assembly_identities_and_homogeneity(self):
        # Plane wall R = t/(k A), contact R = r_c/A, convection R = 1/(h A): each is homogeneous of
        # degree -1 in A, layer terms of degree +1 in thickness and -1 in k; R_rej is not areal.
        # Branch totals are the documented sums with the film split in halves around S.
        for _ in range(N):
            stack, p = self.draw()
            R = tc.assemble_resistances(stack, p)
            A = p["area_m2"]
            self.assertClose(R["R_HS_K_W"], R["R_inner_silicone_K_W"] + 0.5 * R["R_film_K_W"]
                             + R["R_contact_inner_K_W"])
            self.assertClose(R["R_SA_K_W"], 0.5 * R["R_film_K_W"] + R["R_contact_outer_K_W"]
                             + R["R_outer_silicone_K_W"] + R["R_conv_K_W"])
            self.assertClose(R["R_layers_conduction_subtotal_K_W"],
                             R["R_outer_silicone_K_W"] + R["R_inner_silicone_K_W"] + R["R_film_K_W"])
            t_out = stack["t_outer_silicone_m"] * p["t_scale_outer"]
            t_in = stack["t_inner_silicone_m"] * p["t_scale_inner"]
            t_f = stack["t_film_m"] * p["t_scale_film"]
            self.assertClose(R["t_outer_silicone_m"], t_out, 1e-12)
            self.assertClose(R["t_inner_silicone_m"], t_in, 1e-12)
            self.assertClose(R["t_film_m"], t_f, 1e-12)
            self.assertClose(R["R_outer_silicone_K_W"], t_out / (p["k_sil"] * A))
            self.assertClose(R["R_inner_silicone_K_W"], t_in / (p["k_sil"] * A))
            self.assertClose(R["R_film_K_W"], t_f / (p["k_film"] * A))
            self.assertClose(R["R_contact_outer_K_W"], p["r_c_outer"] / A)
            self.assertClose(R["R_contact_inner_K_W"], p["r_c_inner"] / A)
            self.assertClose(R["R_conv_K_W"], 1.0 / (p["h"] * A))
            self.assertEqual(R["R_rej_K_W"], p["R_rej"])
            lam = self.rng.choice([0.5, 2.0, 10.0, 100.0])
            R_A = tc.assemble_resistances(stack, dict(p, area_m2=A * lam))
            for key in ("R_outer_silicone_K_W", "R_inner_silicone_K_W", "R_film_K_W",
                        "R_contact_outer_K_W", "R_contact_inner_K_W", "R_conv_K_W",
                        "R_HS_K_W", "R_SA_K_W", "R_layers_conduction_subtotal_K_W"):
                self.assertClose(R_A[key] * lam, R[key], msg=key)
            self.assertEqual(R_A["R_rej_K_W"], R["R_rej_K_W"])
            R_k = tc.assemble_resistances(stack, dict(p, k_sil=p["k_sil"] * lam))
            self.assertClose(R_k["R_outer_silicone_K_W"] * lam, R["R_outer_silicone_K_W"])
            self.assertClose(R_k["R_inner_silicone_K_W"] * lam, R["R_inner_silicone_K_W"])
            self.assertEqual(R_k["R_film_K_W"], R["R_film_K_W"])
            R_t = tc.assemble_resistances(stack, dict(p, t_scale_inner=p["t_scale_inner"] * lam))
            self.assertClose(R_t["R_inner_silicone_K_W"], lam * R["R_inner_silicone_K_W"])
            self.assertEqual(R_t["R_outer_silicone_K_W"], R["R_outer_silicone_K_W"])
            self.assertEqual(R_t["R_SA_K_W"], R["R_SA_K_W"])

    def test_areal_scaling_leaves_temperatures_and_flux_densities_unchanged(self):
        # Layer, contact and convection resistances are all areal (1/A); R_rej is a lumped K/W value.
        # Multiplying A by lam, dividing R_rej by lam and multiplying both sources by lam multiplies
        # every conductance and every source by lam, so by joint scaling the node temperatures are
        # unchanged, heat rates scale by lam and the flux densities Q/A are unchanged.
        for _ in range(N):
            stack, p = self.draw()
            lam = self.rng.choice([0.1, 0.5, 2.0, 10.0])
            p2 = dict(p, area_m2=p["area_m2"] * lam, R_rej=p["R_rej"] / lam,
                      P_body=p["P_body"] * lam, P_sensor=p["P_sensor"] * lam)
            _, _, r1 = solve_path(stack, p)
            _, _, r2 = solve_path(stack, p2)
            for k in ("T_H_C", "T_S_C", "T_outer_C", "q_front_W_m2", "q_inner_silicone_W_m2"):
                self.assertClose(r2[k], r1[k], msg=k)
            for k in ("Q_HS_W", "Q_front_W", "Q_rear_W"):
                self.assertClose(r2[k], lam * r1[k], msg=k)

    def test_blocked_rear_is_a_single_series_branch(self):
        # G_rej = 0 exactly: Q_rear = 0, Q_front = P_total, T_S = T_amb + P_total R_SA,
        # T_H = T_S + P_body R_HS, T_outer = T_amb + P_total R_conv (independent of the layers, hence
        # equal across stacks), det = G_HS G_SA, and the reservoir temperature is irrelevant.
        for _ in range(N):
            stack, p = self.draw(R_rej=math.inf)
            R, sol, res = solve_path(stack, p)
            Pt = p["P_body"] + p["P_sensor"]
            self.assertEqual(sol["status"], "solved")
            self.assertEqual(res["Q_rear_W"], 0.0)
            self.assertClose(res["Q_front_W"], Pt)
            self.assertClose(res["T_S_C"], p["T_amb"] + Pt * R["R_SA_K_W"])
            self.assertClose(res["T_H_C"], res["T_S_C"] + p["P_body"] * R["R_HS_K_W"])
            self.assertClose(res["T_outer_C"], p["T_amb"] + Pt * R["R_conv_K_W"])
            self.assertClose(sol["det_W2_K2"], tc.conductance_W_K(R["R_HS_K_W"])
                             * tc.conductance_W_K(R["R_SA_K_W"]), 1e-12)
            _, _, res2 = solve_path(stack, dict(p, T_res=p["T_res"] + rnd_dec(self.rng, -100.0, 100.0, 2)))
            for k in FIELDS6:
                self.assertEqual(res2[k], res[k], k)
            _, _, res_b = solve_path(rand_stack(self.rng, "B"), p)
            self.assertClose(res_b["T_outer_C"], res["T_outer_C"])

    def test_sensor_off_swap_of_inner_and_outer_layers(self):
        # With P_sensor = 0 the sensor node is passive, so only the total series resistance between H
        # and ambient matters:  Q_front = (R_rej P_body + (T_res - T_amb)) / (R_HS + R_SA + R_rej).
        # Swapping inner/outer silicone thicknesses together with the two contact resistances leaves
        # R_HS + R_SA, Q_front, Q_rear, Q_HS, T_H and T_outer unchanged (T_S moves).
        for _ in range(N):
            stack, p = self.draw(P_sensor=0.0)
            swapped = dict(stack, t_outer_silicone_m=stack["t_inner_silicone_m"],
                           t_inner_silicone_m=stack["t_outer_silicone_m"])
            p_sw = dict(p, r_c_inner=p["r_c_outer"], r_c_outer=p["r_c_inner"])
            R1, _, r1 = solve_path(stack, p)
            R2, _, r2 = solve_path(swapped, p_sw)
            self.assertClose(R1["R_HS_K_W"] + R1["R_SA_K_W"], R2["R_HS_K_W"] + R2["R_SA_K_W"])
            for k in ("T_H_C", "T_outer_C", "Q_front_W", "Q_rear_W", "Q_HS_W"):
                self.assertClose(r2[k], r1[k], msg=k)

    def test_contact_resistance_equals_silicone_thickness_and_vanishes_continuously(self):
        # A contact resistance r_c/A on either arm is indistinguishable from extra silicone of
        # thickness r_c k_sil on the same arm (t/(k A) = r_c/A); so (r_c, t) == (0, t + r_c k_sil).
        # Limit r_c -> 0: results converge to the r_c = 0 case (continuity of a linear system).
        for _ in range(N):
            stack, p = self.draw()
            ks = p["k_sil"]
            equiv = dict(stack, t_inner_silicone_m=stack["t_inner_silicone_m"] + p["r_c_inner"] * ks,
                         t_outer_silicone_m=stack["t_outer_silicone_m"] + p["r_c_outer"] * ks)
            p0 = dict(p, r_c_inner=0.0, r_c_outer=0.0)
            R1, _, r1 = solve_path(stack, p)
            R2, _, r2 = solve_path(equiv, p0)
            self.assertClose(R2["R_HS_K_W"], R1["R_HS_K_W"])
            self.assertClose(R2["R_SA_K_W"], R1["R_SA_K_W"])
            for k in FIELDS6:
                self.assertClose(r2[k], r1[k], msg=k)
            _, _, r3 = solve_path(stack, dict(p, r_c_inner=1e-16, r_c_outer=1e-16))
            _, _, r4 = solve_path(stack, p0)
            for k in FIELDS6:
                self.assertClose(r3[k], r4[k], msg=k)

    def test_vanishing_h_converges_to_the_front_absent_solution(self):
        # h = 0 (front path absent): Q_front = 0, Q_rear = P_total, T_H = T_res + R_rej P_total,
        # T_S = T_H + P_sensor R_HS (sensor heat flows inward: Q_HS = -P_sensor), T_outer = T_S.
        # For h -> 0+ the unique solution converges to this limit, and T_outer -> T_S.
        for _ in range(N):
            stack, p = self.draw()
            R0, s0, r0 = solve_path(stack, dict(p, h=0.0))
            Pt = p["P_body"] + p["P_sensor"]
            self.assertEqual(s0["status"], "solved")
            self.assertClose(r0["T_H_C"], p["T_res"] + R0["R_rej_K_W"] * Pt)
            self.assertClose(r0["T_S_C"], r0["T_H_C"] + p["P_sensor"] * R0["R_HS_K_W"])
            self.assertClose(r0["Q_HS_W"], -p["P_sensor"])
            _, s1, r1 = solve_path(stack, dict(p, h=1e-16))
            self.assertEqual(s1["status"], "solved")
            for k in ("T_H_C", "T_S_C", "Q_HS_W", "Q_front_W", "Q_rear_W"):
                self.assertClose(r1[k], r0[k], msg=k)
            self.assertClose(r1["T_outer_C"], r1["T_S_C"])

    def test_large_h_removes_only_the_convection_resistance(self):
        # h -> inf drives R_conv -> 0 and T_outer -> T_amb, but the solid/contact part of R_SA
        # remains, so T_S stays above T_amb and the solution equals the network with
        # R_SA = R_out + R_c_out + R_film/2.  (First report's clarification: R_SA = 0 is NOT reached.)
        for _ in range(N):
            stack, p = self.draw()
            R, sol, res = solve_path(stack, dict(p, h=1e30))
            b_solid = R["R_outer_silicone_K_W"] + R["R_contact_outer_K_W"] + 0.5 * R["R_film_K_W"]
            self.assertGreater(b_solid, 0.0)
            self.assertClose(R["R_SA_K_W"], b_solid)
            self.assertClose(res["T_outer_C"], p["T_amb"], 1e-12)
            ref_sol = tc.solve_two_node(tc.conductance_W_K(R["R_HS_K_W"]), 1.0 / b_solid,
                                        tc.conductance_W_K(R["R_rej_K_W"]),
                                        p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
            self.assertClose(res["T_H_C"], ref_sol["T_H"])
            self.assertClose(res["T_S_C"], ref_sol["T_S"])
            p_eq = dict(p, T_res=p["T_amb"])
            _, _, r_fin = solve_path(stack, p_eq)
            _, _, r_inf = solve_path(stack, dict(p_eq, h=1e30))
            self.assertLE(r_inf["T_S_C"], r_fin["T_S_C"])
            self.assertLE(p["T_amb"], r_inf["T_S_C"])

    def test_large_conductivity_removes_the_layer(self):
        # k -> inf makes t/(k A) -> 0: k_sil = 1e30 reproduces zero silicone thickness (contacts and
        # film kept) and k_film = 1e30 reproduces a zero-thickness film.  The film is kept positive in
        # the first case so that R_HS > 0 (no merged node).
        for _ in range(N):
            stack = rand_stack(self.rng)
            stack["t_film_m"] = rnd_dec(self.rng, 1e-5, 2e-4, 7)
            p = rand_params(self.rng)
            _, _, r1 = solve_path(stack, dict(p, k_sil=1e30))
            _, _, r2 = solve_path(dict(stack, t_outer_silicone_m=0.0, t_inner_silicone_m=0.0), p)
            _, _, r3 = solve_path(stack, dict(p, k_film=1e30))
            _, _, r4 = solve_path(dict(stack, t_film_m=0.0), p)
            for k in FIELDS6:
                self.assertClose(r1[k], r2[k], msg=("k_sil", k))
                self.assertClose(r3[k], r4[k], msg=("k_film", k))

    def test_merged_node_limit_and_continuity(self):
        # R_HS = 0 (no inner silicone, no film, no inner contact): H and S merge, G_exit = G_rej + G_SA,
        # T = (P_total + G_rej T_res + G_SA T_amb)/G_exit, det reported as None, divider check not
        # applicable.  For R_HS -> 0+ the two-node solution converges to the merged value.
        for _ in range(N):
            p = rand_params(self.rng, r_c_inner=0.0)
            merged = {"stack_id": "M", "t_outer_silicone_m": rnd_dec(self.rng, 1e-5, 3e-3, 7),
                      "t_film_m": 0.0, "t_inner_silicone_m": 0.0}
            R, sol, res = solve_path(merged, p)
            self.assertEqual(sol["status"], "solved_merged_node_R_HS_zero")
            self.assertEqual(R["R_HS_K_W"], 0.0)
            self.assertIsNone(sol["det_W2_K2"])
            G_SA = tc.conductance_W_K(R["R_SA_K_W"])
            G_rej = tc.conductance_W_K(R["R_rej_K_W"])
            Pt = p["P_body"] + p["P_sensor"]
            T = (Pt + G_rej * p["T_res"] + G_SA * p["T_amb"]) / (G_rej + G_SA)
            self.assertClose(res["T_H_C"], T)
            self.assertClose(res["T_S_C"], T)
            self.assertTrue(res["energy_check_pass"])
            self.assertClose(res["Q_front_W"] + res["Q_rear_W"], Pt)
            self.assertClose(res["Q_HS_W"], p["P_body"] - res["Q_rear_W"])
            checks = tc.semantic_checks(res, sol, R, p, tc.DEFAULT_NUM["agreement_tol_K"])
            self.assertIsNone(checks["resistance_divider_closed_form"])
            for key, val in checks.items():
                self.assertIn(val, (True, None), key)
            _, s2, r2 = solve_path(dict(merged, t_inner_silicone_m=1e-18), p)
            self.assertEqual(s2["status"], "solved")
            self.assertClose(r2["T_H_C"], T)
            self.assertClose(r2["T_S_C"], T)
            self.assertClose(r2["Q_front_W"], res["Q_front_W"])
            self.assertClose(r2["Q_rear_W"], res["Q_rear_W"])

    def test_monotone_in_h_with_front_absent_as_supremum(self):
        # Equal boundaries, P >= 0.  Raising h raises the exit conductance G_SA, so T_H and T_S cannot
        # rise; T_outer - T0 = (T_S - T0)/(1 + h A R_front_solid) falls too; from the divider
        # Q_front = [R_rej P_b + (R_rej + R_HS) P_s]/R_sum rises as R_SA falls and Q_rear falls.
        # h = 0 is the supremum of T_H, T_S, T_outer, Q_rear and the infimum of Q_front.
        for _ in range(N):
            stack, p = self.draw(equal_boundaries=True)
            f = self.rng.choice([1.5, 2.0, 5.0, 50.0])
            _, _, r0 = solve_path(stack, p)
            _, _, r1 = solve_path(stack, dict(p, h=p["h"] * f))
            _, _, rz = solve_path(stack, dict(p, h=0.0))
            for k in ("T_H_C", "T_S_C", "T_outer_C", "Q_rear_W"):
                self.assertLE(r1[k], r0[k], msg=k)
                self.assertLE(r0[k], rz[k], msg=k)
            self.assertLE(r0["Q_front_W"], r1["Q_front_W"])
            self.assertLE(rz["Q_front_W"], r0["Q_front_W"])

    def test_monotone_in_R_rej_with_blocked_rear_as_supremum(self):
        # Equal boundaries, P >= 0.  Raising R_rej lowers the exit conductance G_rej: T_H and T_S cannot
        # fall; dQ_front/dR_rej = (P_b (R_HS + R_SA) + P_s R_SA)/R_sum^2 >= 0, so Q_front and
        # T_outer = T0 + Q_front R_conv rise and Q_rear falls.  The blocked rear is the supremum.
        for _ in range(N):
            stack, p = self.draw(equal_boundaries=True)
            f = self.rng.choice([1.5, 2.0, 5.0, 50.0])
            _, _, r0 = solve_path(stack, p)
            _, _, r1 = solve_path(stack, dict(p, R_rej=p["R_rej"] * f))
            _, _, rb = solve_path(stack, dict(p, R_rej=math.inf))
            for k in ("T_H_C", "T_S_C", "T_outer_C", "Q_front_W"):
                self.assertLE(r0[k], r1[k], msg=k)
                self.assertLE(r1[k], rb[k], msg=k)
            self.assertLE(r1["Q_rear_W"], r0["Q_rear_W"])
            self.assertLE(rb["Q_rear_W"], r1["Q_rear_W"])

    def test_layer_thickness_sensitivities_match_exact_divider_finite_differences(self):
        # All branches finite and positive:
        #   Q_front = [R_rej P_b + (R_rej + R_HS) P_s + (T_res - T_amb)] / (R_HS + R_SA + R_rej).
        # Adding delta to R_HS (thicker inner silicone) changes Q_front by exactly
        #   delta [P_s R_SA - R_rej P_b - (T_res - T_amb)] / (R_sum (R_sum + delta)),
        # a sign that does not depend on delta (the inner layer can push heat either way).
        # Adding delta to R_SA (thicker outer silicone) changes Q_front by exactly
        #   -Q_front delta / (R_sum + delta)  (always toward the rear).
        # Temperatures follow from T_H = T_res + R_rej (P_t - Q_front), T_S = T_amb + Q_front R_SA,
        # T_outer = T_amb + Q_front R_conv.
        for _ in range(N):
            stack, p = self.draw()
            f = self.rng.choice([1.1, 1.5, 2.0, 4.0])
            R0, _, r0 = solve_path(stack, p)
            R_sum = R0["R_HS_K_W"] + R0["R_SA_K_W"] + R0["R_rej_K_W"]
            dTb = p["T_res"] - p["T_amb"]
            Ri, _, ri = solve_path(stack, dict(p, t_scale_inner=p["t_scale_inner"] * f))
            delta = Ri["R_HS_K_W"] - R0["R_HS_K_W"]
            self.assertGreater(delta, 0.0)
            dQ = delta * (p["P_sensor"] * R0["R_SA_K_W"] - R0["R_rej_K_W"] * p["P_body"] - dTb) \
                / (R_sum * (R_sum + delta))
            self.assertClose(ri["Q_front_W"] - r0["Q_front_W"], dQ)
            self.assertClose(ri["T_H_C"] - r0["T_H_C"], -R0["R_rej_K_W"] * dQ)
            self.assertClose(ri["T_S_C"] - r0["T_S_C"], dQ * R0["R_SA_K_W"])
            self.assertClose(ri["T_outer_C"] - r0["T_outer_C"], dQ * R0["R_conv_K_W"])
            Ro, _, ro = solve_path(stack, dict(p, t_scale_outer=p["t_scale_outer"] * f))
            delta_o = Ro["R_SA_K_W"] - R0["R_SA_K_W"]
            self.assertGreater(delta_o, 0.0)
            dQo = -r0["Q_front_W"] * delta_o / (R_sum + delta_o)
            self.assertClose(ro["Q_front_W"] - r0["Q_front_W"], dQo)
            self.assertClose(ro["T_H_C"] - r0["T_H_C"], -R0["R_rej_K_W"] * dQo)
            self.assertClose(ro["T_S_C"] - p["T_amb"], ro["Q_front_W"] * Ro["R_SA_K_W"])
            self.assertClose(ro["T_outer_C"] - r0["T_outer_C"], dQo * R0["R_conv_K_W"])

    def test_sensor_off_monotonicity_in_k_sil_and_contact_resistance(self):
        # Equal boundaries, P_s = 0: both finite-difference formulas above have the sign of
        # -R_rej P_b <= 0, so raising any series resistance between H and ambient (lower k_sil or
        # larger r_c at either interface) lowers Q_front and T_outer and raises T_H.
        # T_S is NOT monotone in these (not promised; see InformationalNotPromised).
        for _ in range(N):
            stack, p = self.draw(equal_boundaries=True, P_sensor=0.0)
            f = self.rng.choice([1.5, 2.0, 5.0])
            _, _, r0 = solve_path(stack, p)
            _, _, r_k = solve_path(stack, dict(p, k_sil=p["k_sil"] / f))
            _, _, r_c = solve_path(stack, dict(p, r_c_inner=p["r_c_inner"] * f + 1e-4,
                                               r_c_outer=p["r_c_outer"] * f + 1e-4))
            for r in (r_k, r_c):
                self.assertLE(r["Q_front_W"], r0["Q_front_W"])
                self.assertLE(r["T_outer_C"], r0["T_outer_C"])
                self.assertLE(r0["T_H_C"], r["T_H_C"])

    def test_results_are_affine_and_monotone_in_the_loads(self):
        # M^-1 >= 0 entrywise: temperatures are affine and nondecreasing in P_body and P_sensor.
        # With all branches finite: dQ_front/dP_b = R_rej/R_sum, dQ_front/dP_s = (R_rej + R_HS)/R_sum,
        # dQ_HS/dP_s = dQ_front/dP_s - 1 = -R_SA/R_sum, dT_H/dP_b = R_rej (R_HS + R_SA)/R_sum,
        # dT_S/dP_b = R_rej R_SA/R_sum.  Affinity: T(lam P1 + (1-lam) P2) = lam T(P1) + (1-lam) T(P2).
        for _ in range(N):
            stack, p = self.draw()
            R, _, r0 = solve_path(stack, p)
            R_sum = R["R_HS_K_W"] + R["R_SA_K_W"] + R["R_rej_K_W"]
            lo, hi = sorted((rnd_dec(self.rng, 0.0, 20.0, 4), rnd_dec(self.rng, 0.0, 20.0, 4)))
            if hi == lo:
                hi = lo + 1.0
            lam = rnd_dec(self.rng, 0.01, 0.99, 3)
            _, _, r_lo = solve_path(stack, dict(p, P_body=lo))
            _, _, r_hi = solve_path(stack, dict(p, P_body=hi))
            _, _, r_mid = solve_path(stack, dict(p, P_body=lam * lo + (1.0 - lam) * hi))
            for k in FIELDS6:
                self.assertClose(r_mid[k], lam * r_lo[k] + (1.0 - lam) * r_hi[k], msg=k)
                self.assertLE(r_lo[k], r_hi[k], msg=k)
            _, _, r_b = solve_path(stack, dict(p, P_body=p["P_body"] + 1.0))
            self.assertClose(r_b["Q_front_W"] - r0["Q_front_W"], R["R_rej_K_W"] / R_sum)
            self.assertClose(r_b["T_H_C"] - r0["T_H_C"],
                             R["R_rej_K_W"] * (R["R_HS_K_W"] + R["R_SA_K_W"]) / R_sum)
            self.assertClose(r_b["T_S_C"] - r0["T_S_C"], R["R_rej_K_W"] * R["R_SA_K_W"] / R_sum)
            _, _, r_s = solve_path(stack, dict(p, P_sensor=p["P_sensor"] + 1.0))
            self.assertClose(r_s["Q_front_W"] - r0["Q_front_W"], (R["R_rej_K_W"] + R["R_HS_K_W"]) / R_sum)
            self.assertClose(r_s["Q_HS_W"] - r0["Q_HS_W"], -R["R_SA_K_W"] / R_sum)
            self.assertLE(r0["T_H_C"], r_s["T_H_C"])
            self.assertLE(r0["T_S_C"], r_s["T_S_C"])

    def test_module_semantic_checks_hold_across_the_domain(self):
        # The module's own consistency checks are exact identities of the network; in the moderate
        # domain they must all be True, with None exactly where the module documents inapplicability:
        # divider needs all three branch resistances finite and positive (not for h = 0, blocked rear
        # or merged node), the Pareto line needs finite R_rej, the Gauss check needs a Gauss result.
        for _ in range(N):
            stack, p = self.draw()
            mode = self.rng.random()
            if mode < 0.15:
                p["h"] = 0.0
            elif mode < 0.30:
                p["R_rej"] = math.inf
            elif mode < 0.40:
                stack = dict(stack, t_inner_silicone_m=0.0, t_film_m=0.0)
                p["r_c_inner"] = 0.0
            R, sol, res = solve_path(stack, p)
            checks = tc.semantic_checks(res, sol, R, p, tc.DEFAULT_NUM["agreement_tol_K"])
            for key, val in checks.items():
                self.assertIn(val, (True, None), (key, stack, p))
            finite_pos = all(math.isfinite(x) and x > 0.0
                             for x in (R["R_HS_K_W"], R["R_SA_K_W"], R["R_rej_K_W"]))
            self.assertEqual(checks["resistance_divider_closed_form"] is None, not finite_pos)
            self.assertEqual(checks["pareto_line_identity_T_H_vs_T_outer"] is None,
                             math.isinf(R["R_rej_K_W"]))
            self.assertEqual(checks["gauss_vs_closed_form_inverse"] is None, sol["T_H_gauss"] is None)
            self.assertIs(checks["gauss_vs_closed_form_inverse"], True, (stack, p))
            self.assertIs(checks["all_outputs_finite"], True)
            self.assertIs(checks["energy_balance_within_tolerance"], True)


FIELDS6 = ("T_H_C", "T_S_C", "T_outer_C", "Q_HS_W", "Q_front_W", "Q_rear_W")

NUMERIC_CASE_KEYS = tuple(tc.RESULT_KEYS) + (
    "R_outer_silicone_K_W", "R_inner_silicone_K_W", "R_film_K_W", "R_layers_conduction_subtotal_K_W",
    "R_contact_outer_K_W", "R_contact_inner_K_W", "R_conv_K_W", "R_HS_K_W", "R_SA_K_W",
    "det_W2_K2", "modeled_total_thickness_m", "modeled_mass_kg_nominal_density_not_weighed",
    "P_body_W", "P_sensor_W", "P_total_W", "T_amb_C", "T_res_C", "h_W_m2K", "k_silicone_W_mK",
    "k_film_W_mK", "r_c_inner_m2K_W", "r_c_outer_m2K_W", "R_rej_K_W", "status") if tc is not None else ()

ALLOWED_OVERRIDES = ("k_sil", "k_film", "r_c", "h", "R_rej", "t_bias", "P_sensor",
                     "t_dev_inner", "t_dev_outer")

# expected_plan.json (frozen, Coda) for the sample-valued BASE_CFG; ints compare equal to floats.
EXPECTED_BASE_PLAN = [
    {"condition_id": "A_nominal_P1", "P_body": 1},
    {"condition_id": "A_nominal_P5", "P_body": 5},
    {"condition_id": "A_nominal_P10", "P_body": 10},
    {"condition_id": "B_rear_blocked_P1", "P_body": 1, "R_rej": "blocked"},
    {"condition_id": "B_rear_blocked_P5", "P_body": 5, "R_rej": "blocked"},
    {"condition_id": "B_rear_blocked_P10", "P_body": 10, "R_rej": "blocked"},
    {"condition_id": "C_k_sil_lo_P5", "P_body": 5, "k_sil": 0.18},
    {"condition_id": "C_k_sil_hi_P5", "P_body": 5, "k_sil": 0.35},
    {"condition_id": "C_k_film_lo_P5", "P_body": 5, "k_film": 0.12},
    {"condition_id": "C_k_film_hi_P5", "P_body": 5, "k_film": 0.25},
    {"condition_id": "C_r_c_lo_P5", "P_body": 5, "r_c": 0},
    {"condition_id": "C_r_c_hi_P5", "P_body": 5, "r_c": 0.002},
    {"condition_id": "C_h_lo_P5", "P_body": 5, "h": 3},
    {"condition_id": "C_h_hi_P5", "P_body": 5, "h": 15},
    {"condition_id": "C_R_rej_lo_P5", "P_body": 5, "R_rej": 1},
    {"condition_id": "C_R_rej_hi_P5", "P_body": 5, "R_rej": 10},
    {"condition_id": "C_t_bias_minus_P5", "P_body": 5, "t_bias": -0.1},
    {"condition_id": "C_t_bias_plus_P5", "P_body": 5, "t_bias": 0.1},
    {"condition_id": "C_sensor_off_P5", "P_body": 5, "P_sensor": 0},
    {"condition_id": "D_h_lo_P1", "P_body": 1, "h": 3},
    {"condition_id": "D_h_hi_P1", "P_body": 1, "h": 15},
    {"condition_id": "D_R_rej_lo_P1", "P_body": 1, "R_rej": 1},
    {"condition_id": "D_R_rej_hi_P1", "P_body": 1, "R_rej": 10},
    {"condition_id": "D_h_lo_P10", "P_body": 10, "h": 3},
    {"condition_id": "D_h_hi_P10", "P_body": 10, "h": 15},
    {"condition_id": "D_R_rej_lo_P10", "P_body": 10, "R_rej": 1},
    {"condition_id": "D_R_rej_hi_P10", "P_body": 10, "R_rej": 10},
    {"condition_id": "E1_both_exits_weak_P10", "P_body": 10, "h": 3, "R_rej": 10, "k_sil": 0.18,
     "r_c": 0.002, "t_bias": 0.1},
    {"condition_id": "E2_rear_weak_front_strong_P10", "P_body": 10, "h": 15, "R_rej": 10,
     "k_sil": 0.35, "r_c": 0},
    {"condition_id": "E3_rear_strong_front_weak_P10", "P_body": 10, "h": 3, "R_rej": 1,
     "k_sil": 0.18, "r_c": 0.002},
    {"condition_id": "E4_blocked_adverse_P10", "P_body": 10, "R_rej": "blocked", "h": 3,
     "k_sil": 0.18, "r_c": 0.002, "t_bias": 0.1},
    {"condition_id": "E5_blocked_favourable_P1", "P_body": 1, "R_rej": "blocked", "h": 15,
     "k_sil": 0.35, "r_c": 0, "t_bias": -0.1},
    {"condition_id": "E6_max_layer_resistance_P5", "P_body": 5, "k_sil": 0.18, "k_film": 0.12,
     "r_c": 0.002, "t_bias": 0.1},
    {"condition_id": "E7_min_layer_resistance_P5", "P_body": 5, "k_sil": 0.35, "k_film": 0.25,
     "r_c": 0, "t_bias": -0.1},
    {"condition_id": "F_inner_plus_outer_minus_P5", "P_body": 5, "t_dev_inner": 0.1, "t_dev_outer": -0.1},
    {"condition_id": "F_inner_minus_outer_plus_P5", "P_body": 5, "t_dev_inner": -0.1, "t_dev_outer": 0.1},
]
EXPECTED_GROUP_COUNTS = {"A_nominal": 3, "B_rear_blocked": 3, "C_one_at_a_time": 13,
                         "D_boundary_at_load_extremes": 8, "E_joint_adverse_corner": 7,
                         "F_independent_layer_deviation": 2}


def reversed_keys(obj):
    """Rebuild every dict with reversed insertion order (lists keep their order: it matters)."""
    if isinstance(obj, dict):
        return {k: reversed_keys(obj[k]) for k in reversed(list(obj))}
    if isinstance(obj, list):
        return [reversed_keys(v) for v in obj]
    return obj


def numeric_view(case, drop=()):
    return {k: case[k] for k in NUMERIC_CASE_KEYS if k not in drop}


def validation_outcome(cfg):
    """'rejected' (ConfigError), 'admitted', or 'escaped:<ExceptionName>'."""
    try:
        tc.validate_config(cfg)
    except tc.ConfigError:
        return "rejected"
    except Exception as exc:                     # noqa: BLE001 - report the exact leak
        return "escaped:%s" % type(exc).__name__
    return "admitted"


def assert_matches_exact(test, actual, ex, info):
    """Compare a module result dict (T_*_C, Q_*_W) with an exact-rational steady solution."""
    test.assertEqual(ex["status"], "unique", info)
    test.assertClose(actual["T_H_C"], float(ex["H"]), msg=("T_H", info))
    test.assertClose(actual["T_S_C"], float(ex["S"]), msg=("T_S", info))
    test.assertClose(actual["Q_front_W"], float(ex["front"]), msg=("Q_front", info))
    test.assertClose(actual["Q_rear_W"], float(ex["rear"]), msg=("Q_rear", info))
    test.assertClose(actual["Q_HS_W"], float(ex["front"] - ex["J"]), msg=("Q_HS", info))
    if ex["surface"] is None:
        test.assertEqual(actual["T_outer_C"], actual["T_S_C"], ("T_outer h=0", info))
    else:
        test.assertClose(actual["T_outer_C"], float(ex["surface"]), msg=("T_outer", info))


def assert_resistances_match_exact(test, Rvals, ex, info):
    test.assertClose(Rvals["R_HS_K_W"], float(ex["a"]), msg=("R_HS", info))
    if isinstance(ex["b"], float) and math.isinf(ex["b"]):
        test.assertTrue(math.isinf(Rvals["R_SA_K_W"]) and math.isinf(Rvals["R_conv_K_W"]), info)
    else:
        test.assertClose(Rvals["R_SA_K_W"], float(ex["b"]), msg=("R_SA", info))
        test.assertClose(Rvals["R_conv_K_W"], float(ex["conv"]), msg=("R_conv", info))


# ----------------------------------------------------------------------------
# 3. agreement with the independent exact rational reference (thermal_reference.steady)
# ----------------------------------------------------------------------------

class TestExactReference(_Base):

    def setUp(self):
        if ref is None:
            self.skipTest("thermal_reference.py not found (set THERMAL_REFERENCE_PATH)")
        self.rng = random.Random(SEED + 3)

    def test_random_assembled_cases_agree_with_exact_rational_reference(self):
        # The reference solves the same network in heat-flow variables with Fractions (no nodal
        # matrix, independent assembly route).  For nonnegative sources and R_SA > 0 both must agree
        # to rounding on every reported temperature and heat rate, including the h = 0, blocked-rear
        # and merged-node (R_HS = 0, i.e. a = 0 in the reference) limits.
        for i in range(N):
            stack, p = rand_stack(self.rng), rand_params(self.rng)
            mode = self.rng.random()
            expect = "solved"
            if mode < 0.15:
                p["h"] = 0.0
            elif mode < 0.30:
                p["R_rej"] = math.inf
            elif mode < 0.40:
                stack = dict(stack, t_inner_silicone_m=0.0, t_film_m=0.0)
                p["r_c_inner"] = 0.0
                expect = "solved_merged_node_R_HS_zero"
            R, sol, res = solve_path(stack, p)
            self.assertEqual(sol["status"], expect, (i, stack, p))
            ex = exact_from_params(stack, p)
            assert_matches_exact(self, res, ex, (i, stack, p))
            assert_resistances_match_exact(self, R, ex, (i, stack, p))

    def test_run_case_with_random_overrides_agrees_with_exact_rational_reference(self):
        # resolve_parameters merges a condition dict with the configured nominal values
        # (r_c_inner/r_c_outer override the common r_c; t_scale = (1 + t_bias)(1 + t_dev); film held
        # nominal; blocked token -> R_rej = inf).  The exact route re-derives every resistance from the
        # same declarations.  Both-exits-absent draws must map to the reference's status words.
        cfg = copy.deepcopy(BASE_CFG)
        rho_sil = exact(cfg["materials"]["silicone_ref"]["density_kg_m3"])
        rho_film = exact(cfg["materials"]["polyimide_film_ref"]["density_kg_m3"])
        for i in range(N):
            stack = rand_stack(self.rng, "S")
            cnd = {"condition_id": "rnd_%d" % i, "group": "T_random", "P_body": rnd_dec(self.rng, 0.0, 20.0, 3)}
            rng = self.rng
            draws = {
                "k_sil": lambda: rnd_dec(rng, 0.1, 1.0, 3), "k_film": lambda: rnd_dec(rng, 0.1, 0.5, 3),
                "r_c": lambda: rnd_dec(rng, 0.0, 3e-3, 5), "r_c_inner": lambda: rnd_dec(rng, 0.0, 3e-3, 5),
                "r_c_outer": lambda: rnd_dec(rng, 0.0, 3e-3, 5),
                "h": lambda: 0.0 if rng.random() < 0.1 else rnd_dec(rng, 0.5, 50.0, 2),
                "R_rej": lambda: "blocked" if rng.random() < 0.2 else rng.choice([rnd_dec(rng, 0.3, 30.0, 2), 1, 2, 10]),
                "t_bias": lambda: rnd_dec(rng, -0.5, 0.5, 2), "t_dev_inner": lambda: rnd_dec(rng, -0.5, 0.5, 2),
                "t_dev_outer": lambda: rnd_dec(rng, -0.5, 0.5, 2), "P_sensor": lambda: rnd_dec(rng, 0.0, 1.0, 3),
                "T_amb": lambda: rnd_dec(rng, -30.0, 60.0, 1), "T_res": lambda: rnd_dec(rng, -30.0, 60.0, 1),
            }
            for key, draw in draws.items():
                if rng.random() < 0.5:
                    cnd[key] = draw()
            case = tc.run_case(cfg, stack, cnd)
            ex = exact_from_cfg_cond(cfg, stack, cnd)
            info = (i, stack, cnd)
            self.assertEqual(case["case_id"], "%s__%s" % (stack["stack_id"], cnd["condition_id"]))
            self.assertEqual(case["condition_id"], cnd["condition_id"])
            self.assertEqual(case["P_body_W"], float(cnd["P_body"]))
            self.assertEqual(case["overrides_vs_nominal"],
                             {k: v for k, v in cnd.items() if k not in ("condition_id", "group")})
            blocked = cnd.get("R_rej") == "blocked"
            self.assertEqual(case["R_rej_K_W"], "blocked" if blocked else
                             float(cnd.get("R_rej", cfg["boundaries"]["R_rej_K_W"])))
            self.assertEqual(case["rear_boundary_condition"],
                             "blocked_G_rej_zero" if blocked else "finite_R_rej_to_ideal_isothermal_reservoir")
            self.assertClose(case["modeled_total_thickness_m"], float(ex["t_in"] + ex["t_out"] + ex["t_f"]), 1e-12)
            self.assertClose(case["modeled_mass_kg_nominal_density_not_weighed"],
                             float(ex["A"] * ((ex["t_out"] + ex["t_in"]) * rho_sil + ex["t_f"] * rho_film)), 1e-12)
            assert_resistances_match_exact(self, case, ex, info)
            if "H" not in ex:                            # both exits absent
                self.assertFalse(case["status"].startswith("solved"), info)
                word = "no_finite_steady_state" if ex["status"] == "no_finite_steady_state" else "nonunique"
                self.assertTrue(case["status"].startswith(word), (case["status"], ex["status"], info))
                self.assertEqual(case["checks"], {"solvable": False})
                for key in tc.RESULT_KEYS:
                    self.assertIsNone(case[key], (key, info))
                continue
            self.assertIn(case["status"], ("solved", "solved_merged_node_R_HS_zero"), info)
            assert_matches_exact(self, case, ex, info)
            self.assertTrue(case["energy_check_pass"], info)
            for key, val in case["checks"].items():
                self.assertIn(val, (True, None), (key, info))

    def test_full_deterministic_plan_on_random_admitted_configs_agrees_with_exact_rational_reference(self):
        # For any admitted configuration the plan has 36 conditions in the documented groups; with
        # h > 0 and positive layer thickness every case has det > 0 and must equal the exact
        # reference; the summary must then count every case as solved, energy-passing and check-passing.
        for i in range(N_CFG):
            cfg = rand_config(self.rng)
            self.assertIs(tc.validate_config(cfg), cfg)
            conds = tc.build_shared_conditions(cfg)
            self.assertEqual(len(conds), 36)
            counts = {}
            for c in conds:
                counts[c["group"]] = counts.get(c["group"], 0) + 1
            self.assertEqual(counts, EXPECTED_GROUP_COUNTS)
            cond_by_id = {c["condition_id"]: c for c in conds}
            stack_by_id = {s["stack_id"]: s for s in cfg["stacks"]}
            cases = run_all_cases(cfg)
            self.assertEqual(len(cases), 36 * len(cfg["stacks"]))
            self.assertEqual(len({c["case_id"] for c in cases}), len(cases))
            for case in cases:
                info = (i, case["case_id"])
                ex = exact_from_cfg_cond(cfg, stack_by_id[case["stack_id"]], cond_by_id[case["condition_id"]])
                self.assertEqual(case["status"], "solved", info)
                assert_matches_exact(self, case, ex, info)
                assert_resistances_match_exact(self, case, ex, info)
            summary = tc.summarize(cases)
            self.assertEqual(summary["n_cases"], len(cases))
            self.assertEqual(summary["n_solved"], len(cases))
            self.assertEqual(summary["n_not_solved"], 0)
            self.assertEqual(summary["n_energy_pass"], len(cases))
            self.assertEqual(summary["n_all_semantic_checks_pass"], len(cases))

    def test_both_exits_absent_statuses_agree_with_reference(self):
        # G_SA = G_rej = 0 (h = 0 and blocked rear): the reference reports no finite steady state for
        # P + J > 0 and 'nonunique' for zero sources; the module's documented statuses must agree.
        for _ in range(N // 5):
            stack, p = rand_stack(self.rng), rand_params(self.rng, h=0.0, R_rej=math.inf)
            if self.rng.random() < 0.5:
                p["P_body"] = p["P_sensor"] = 0.0
            R, sol, res = solve_path(stack, p)
            ex = exact_from_params(stack, p)
            self.assertIsNone(res)
            self.assertIsNone(sol["T_H"])
            self.assertIn(sol["status"], tc.STATUS_NOTES)
            if ex["status"] == "no_finite_steady_state":
                self.assertTrue(sol["status"].startswith("no_finite_steady_state"), sol["status"])
            else:
                self.assertEqual(ex["status"], "nonunique")
                self.assertTrue(sol["status"].startswith("nonunique"), sol["status"])


# ----------------------------------------------------------------------------
# 4. run_case, deterministic plan, summary and serialisation
# ----------------------------------------------------------------------------

class TestRunCaseAndPlan(_Base):

    def setUp(self):
        self.rng = random.Random(SEED + 4)

    def test_stack_relabelling_reordering_and_key_order_do_not_change_results(self):
        # Results are functions of the thickness triple and the condition, never of stack_id, of the
        # position of a stack in the list or of JSON object key order; only case_id/stack_id echo.
        for _ in range(N_CFG):
            cfg = rand_config(self.rng)
            while len(cfg["stacks"]) < 2:
                cfg = rand_config(self.rng)
            cases_a = run_all_cases(cfg)
            cfg_b = copy.deepcopy(cfg)
            cfg_b["stacks"] = [dict(s, stack_id="Z_%d" % i) for i, s in enumerate(reversed(cfg["stacks"]))]
            cases_b = run_all_cases(cfg_b)
            self.assertEqual(len(cases_a), len(cases_b))

            def key(c, stacks):
                s = {x["stack_id"]: x for x in stacks}[c["stack_id"]]
                return (c["condition_id"], s["t_outer_silicone_m"], s["t_film_m"], s["t_inner_silicone_m"])

            index_a = {key(c, cfg["stacks"]): c for c in cases_a}
            for cb in cases_b:
                ca = index_a[key(cb, cfg_b["stacks"])]
                strip = lambda c: {k: v for k, v in c.items() if k not in ("case_id", "stack_id")}
                self.assertEqual(strip(ca), strip(cb))
            self.assertEqual(tc.summarize(cases_a), tc.summarize(cases_b))
            cfg_r = reversed_keys(cfg)
            self.assertIs(tc.validate_config(cfg_r), cfg_r)
            self.assertEqual(tc.build_shared_conditions(cfg_r), tc.build_shared_conditions(cfg))
            self.assertEqual(run_all_cases(cfg_r), cases_a)

    def test_override_identities(self):
        # Explicit overrides equal to the nominal values, common r_c vs. equal split contacts, int vs.
        # float overrides, and (t_bias, t_dev) vs. the equivalent pre-scaled stack must give identical
        # or (for the re-scaled stack, up to rounding) equal numbers; shifting both boundary
        # temperatures by D shifts every temperature by D and no heat rate.
        cfg = copy.deepcopy(BASE_CFG)
        b, m, c, s = cfg["boundaries"], cfg["materials"], cfg["contacts"], cfg["sources"]
        for i in range(N // 3):
            stack = rand_stack(self.rng, "S")
            P = rnd_dec(self.rng, 0.0, 20.0, 2)
            base = tc.run_case(cfg, stack, cond("base", P))
            explicit = tc.run_case(cfg, stack, cond(
                "explicit", P, h=b["h_W_m2K"], k_sil=m["silicone_ref"]["k_W_mK"],
                k_film=m["polyimide_film_ref"]["k_W_mK"], r_c=c["r_c_m2K_W"], R_rej=b["R_rej_K_W"],
                t_bias=0.0, t_dev_inner=0.0, t_dev_outer=0.0, P_sensor=s["sensor"]["P_W"],
                T_amb=b["T_amb_C"], T_res=b["T_res_C"]))
            self.assertEqual(numeric_view(explicit), numeric_view(base))
            x = rnd_dec(self.rng, 0.0, 3e-3, 5)
            common = tc.run_case(cfg, stack, cond("common", P, r_c=x))
            split = tc.run_case(cfg, stack, cond("split", P, r_c_inner=x, r_c_outer=x))
            self.assertEqual(numeric_view(split), numeric_view(common))
            as_int = tc.run_case(cfg, stack, cond("int", 5, R_rej=2, h=8, P_sensor=0))
            as_float = tc.run_case(cfg, stack, cond("float", 5.0, R_rej=2.0, h=8.0, P_sensor=0.0))
            self.assertEqual(numeric_view(as_int), numeric_view(as_float))
            bias, d_in, d_out = (rnd_dec(self.rng, -0.4, 0.4, 2) for _ in range(3))
            scaled = tc.run_case(cfg, stack, cond("scaled", P, t_bias=bias, t_dev_inner=d_in, t_dev_outer=d_out))
            pre = dict(stack, t_inner_silicone_m=stack["t_inner_silicone_m"] * (1.0 + bias) * (1.0 + d_in),
                       t_outer_silicone_m=stack["t_outer_silicone_m"] * (1.0 + bias) * (1.0 + d_out))
            plain = tc.run_case(cfg, pre, cond("plain", P))
            self.assertEqual(scaled["R_film_K_W"], plain["R_film_K_W"])
            for k in FIELDS6 + ("R_HS_K_W", "R_SA_K_W", "modeled_total_thickness_m",
                                "modeled_mass_kg_nominal_density_not_weighed"):
                self.assertClose(scaled[k], plain[k], msg=k)
            D = rnd_dec(self.rng, -50.0, 50.0, 1)
            shifted = tc.run_case(cfg, stack, cond("shift", P, T_amb=b["T_amb_C"] + D, T_res=b["T_res_C"] + D))
            for k in ("T_H_C", "T_S_C", "T_outer_C"):
                self.assertClose(shifted[k] - base[k], D, msg=k)
            for k in ("Q_HS_W", "Q_front_W", "Q_rear_W"):
                self.assertClose(shifted[k], base[k], msg=k)

    def test_comparators_numerics_and_densities_only_touch_their_own_outputs(self):
        # Comparators enter only the two margins (margin = comparator - temperature) and the summary
        # crossing counts; numerics tolerances enter only energy_tolerance_W (and the pass flags);
        # densities enter only the reported modeled mass, linearly.  Everything else is invariant.
        cfg = rand_config(self.rng)
        cases = run_all_cases(cfg)
        margins = ("margin_outer_K_study_comparator_only", "margin_internal_K_study_comparator_only")
        dx, dy = rnd_dec(self.rng, -30.0, 30.0, 1), rnd_dec(self.rng, -30.0, 30.0, 1)
        cfg2 = copy.deepcopy(cfg)
        cfg2["comparators"]["outer_surface_C"] += dx
        cfg2["comparators"]["internal_node_C"] += dy
        cases2 = run_all_cases(cfg2)
        for a, b2 in zip(cases, cases2):
            self.assertClose(b2[margins[0]] - a[margins[0]], dx, 1e-12)
            self.assertClose(b2[margins[1]] - a[margins[1]], dy, 1e-12)
            self.assertEqual({k: v for k, v in a.items() if k not in margins},
                             {k: v for k, v in b2.items() if k not in margins})
        summary2 = tc.summarize(cases2)
        self.assertEqual(summary2["n_outer_comparator_exceeded_study_comparator_only"],
                         sum(1 for c in cases2 if c[margins[0]] < 0.0))
        self.assertEqual(summary2["n_internal_comparator_exceeded_study_comparator_only"],
                         sum(1 for c in cases2 if c[margins[1]] < 0.0))
        cfg3 = copy.deepcopy(cfg)
        for key in ("energy_abs_tol_W", "energy_rel_tol", "agreement_tol_K"):
            cfg3["numerics"][key] *= 10.0
        for a, b3 in zip(cases, run_all_cases(cfg3)):
            self.assertClose(b3["energy_tolerance_W"], 10.0 * a["energy_tolerance_W"], 1e-12)
            self.assertTrue(b3["energy_check_pass"])
            self.assertEqual({k: v for k, v in a.items() if k != "energy_tolerance_W"},
                             {k: v for k, v in b3.items() if k != "energy_tolerance_W"})
        cfg4 = copy.deepcopy(cfg)
        cfg4["materials"]["silicone_ref"]["density_kg_m3"] *= 2.0
        cfg4["materials"]["polyimide_film_ref"]["density_kg_m3"] *= 2.0
        mass = "modeled_mass_kg_nominal_density_not_weighed"
        for a, b4 in zip(cases, run_all_cases(cfg4)):
            self.assertClose(b4[mass], 2.0 * a[mass], 1e-12)
            self.assertEqual({k: v for k, v in a.items() if k != mass}, {k: v for k, v in b4.items() if k != mass})

    def test_summary_is_order_independent_and_consistent_with_the_cases(self):
        # summarize() reports multiset counts, so any permutation of the cases gives the same summary;
        # n_solved + n_not_solved = n_cases, and the counts agree with direct recounts.
        cfg = copy.deepcopy(BASE_CFG)
        cases = run_all_cases(cfg)
        for i in range(3):
            cases.append(tc.run_case(cfg, cfg["stacks"][i], cond("unsolvable_%d" % i, 5.0, h=0.0, R_rej="blocked")))
        shuffled = list(cases)
        self.rng.shuffle(shuffled)
        summary = tc.summarize(cases)
        self.assertEqual(tc.summarize(shuffled), summary)
        solved = [c for c in cases if c["status"].startswith("solved")]
        self.assertEqual(summary["n_cases"], len(cases))
        self.assertEqual(summary["n_solved"], len(solved))
        self.assertEqual(summary["n_not_solved"], 3)
        self.assertEqual(summary["n_solved"] + summary["n_not_solved"], summary["n_cases"])
        self.assertEqual(summary["n_energy_pass"], sum(1 for c in solved if c["energy_check_pass"]))
        self.assertEqual(summary["n_all_semantic_checks_pass"],
                         sum(1 for c in solved if all(v in (True, None) for v in c["checks"].values())))
        self.assertEqual(summary["n_outer_comparator_exceeded_study_comparator_only"],
                         sum(1 for c in solved if c["margin_outer_K_study_comparator_only"] < 0.0))

    def test_plan_structure_and_frozen_base_anchor(self):
        # The plan is a pure function of loads, assumed ranges and the perturbation fraction:
        # 3 + 3 + 13 + 8 + 7 + 2 = 36 unique conditions (bound 60), every override drawn from the
        # configured ranges/tokens; comparators, numerics, densities and study_id are irrelevant.
        # For the sample-valued BASE_CFG the plan must equal the frozen expected_plan.json.
        conds = tc.build_shared_conditions(copy.deepcopy(BASE_CFG))
        self.assertEqual([{k: v for k, v in c.items() if k != "group"} for c in conds], EXPECTED_BASE_PLAN)
        for _ in range(N_CFG):
            cfg = rand_config(self.rng)
            conds = tc.build_shared_conditions(cfg)
            self.assertEqual(len(conds), 36)
            self.assertLessEqual(len(conds), tc.MAX_SETTINGS_PER_STACK)
            self.assertEqual(len({c["condition_id"] for c in conds}), 36)
            counts = {}
            for c in conds:
                counts[c["group"]] = counts.get(c["group"], 0) + 1
            self.assertEqual(counts, EXPECTED_GROUP_COUNTS)
            loads = [float(x) for x in cfg["sources"]["body"]["P_W_list"]]
            k_s = cfg["materials"]["silicone_ref"]["k_assumed_range_W_mK"]
            k_f = cfg["materials"]["polyimide_film_ref"]["k_assumed_range_W_mK"]
            rc = cfg["contacts"]["r_c_assumed_range_m2K_W"]
            hr = cfg["boundaries"]["h_assumed_range_W_m2K"]
            Rr = cfg["boundaries"]["R_rej_assumed_range_K_W"]
            f = cfg["thickness_perturbation"]["fraction"]
            for c in conds:
                self.assertIn(c["P_body"], loads)
                for key, val in c.items():
                    if key in ("condition_id", "group", "P_body"):
                        continue
                    self.assertIn(key, ALLOWED_OVERRIDES, c)
                    if key == "R_rej":
                        self.assertTrue(val == "blocked" or Rr[0] <= val <= Rr[1], c)
                    elif key == "h":
                        self.assertTrue(hr[0] <= val <= hr[1], c)
                    elif key == "k_sil":
                        self.assertTrue(k_s[0] <= val <= k_s[1], c)
                    elif key == "k_film":
                        self.assertTrue(k_f[0] <= val <= k_f[1], c)
                    elif key == "r_c":
                        self.assertTrue(rc[0] <= val <= rc[1], c)
                    elif key in ("t_bias", "t_dev_inner", "t_dev_outer"):
                        self.assertEqual(abs(val), f, c)
                    elif key == "P_sensor":
                        self.assertEqual(val, 0.0, c)
            cfg2 = copy.deepcopy(cfg)
            cfg2["comparators"]["outer_surface_C"] += 5.0
            cfg2["numerics"]["agreement_tol_K"] *= 10.0
            cfg2["materials"]["silicone_ref"]["density_kg_m3"] *= 2.0
            cfg2["study_id"] = "other_study"
            self.assertEqual(tc.build_shared_conditions(cfg2), conds)

    def test_blocked_rear_group_has_layer_independent_outer_temperature(self):
        # Group B: G_rej = 0 exactly, so Q_rear = 0, Q_front = P_total and
        # T_outer = T_amb + P_total/(h A): identical for every stack and affine in the load.
        cfg = copy.deepcopy(BASE_CFG)
        A = cfg["geometry"]["area_m2"]
        T_amb = cfg["boundaries"]["T_amb_C"]
        by_cond = {}
        for c in run_all_cases(cfg):
            by_cond.setdefault(c["condition_id"], []).append(c)
        n_B = 0
        for cid, group in by_cond.items():
            if not cid.startswith("B_"):
                continue
            n_B += 1
            self.assertEqual(len(group), 3)
            for c in group:
                self.assertEqual(c["status"], "solved")
                self.assertEqual(c["rear_boundary_condition"], "blocked_G_rej_zero")
                self.assertEqual(c["R_rej_K_W"], "blocked")
                self.assertEqual(c["Q_rear_W"], 0.0)
                self.assertClose(c["Q_front_W"], c["P_total_W"])
                self.assertClose(c["T_outer_C"], T_amb + c["P_total_W"] / (c["h_W_m2K"] * A))
                self.assertClose(c["T_outer_C"], group[0]["T_outer_C"])
                self.assertIsNone(c["checks"]["pareto_line_identity_T_H_vs_T_outer"])
                self.assertIsNone(c["checks"]["resistance_divider_closed_form"])
        self.assertEqual(n_B, 3)

    def test_pareto_line_identity_holds_for_every_finite_rear_case(self):
        # Series front path: Q_front = h A (T_outer - T_amb); Q_rear = P_total - Q_front; so
        # T_H = T_res + R_rej (P_total - h A (T_outer - T_amb)) for every case with finite R_rej
        # (the module's interpretation caveat), and the module's own check must say True.
        for _ in range(max(2, N_CFG // 2)):
            cfg = rand_config(self.rng)
            A = cfg["geometry"]["area_m2"]
            for c in run_all_cases(cfg):
                if c["R_rej_K_W"] == "blocked":
                    continue
                line = c["T_res_C"] + c["R_rej_K_W"] * (c["P_total_W"] - c["h_W_m2K"] * A * (c["T_outer_C"] - c["T_amb_C"]))
                self.assertClose(line, c["T_H_C"], msg=c["case_id"])
                self.assertIs(c["checks"]["pareto_line_identity_T_H_vs_T_outer"], True, c["case_id"])

    def test_h_zero_nominal_config_runs_with_documented_unsolvable_blocked_cases(self):
        # h = 0 is admitted ("limiting case only").  With P_total > 0 every blocked-rear condition at
        # h = 0 (the three B conditions and E4) has no steady state; all other conditions keep det > 0.
        # Unsolvable cases must carry a documented status, no numbers and checks == {'solvable': False}.
        cfg = copy.deepcopy(BASE_CFG)
        cfg["boundaries"]["h_W_m2K"] = 0.0
        cfg["boundaries"]["h_assumed_range_W_m2K"] = [0.0, 15.0]
        self.assertIs(tc.validate_config(cfg), cfg)
        cases = run_all_cases(cfg)
        self.assertEqual(len(cases), 108)
        not_solved = [c for c in cases if not c["status"].startswith("solved")]
        self.assertEqual(len(not_solved), 12)
        self.assertEqual({c["condition_id"] for c in not_solved},
                         {"B_rear_blocked_P1", "B_rear_blocked_P5", "B_rear_blocked_P10", "E4_blocked_adverse_P10"})
        for c in not_solved:
            self.assertEqual(c["status"], "no_finite_steady_state_both_exits_absent_net_source_nonzero")
            self.assertEqual(c["status_note"], tc.STATUS_NOTES[c["status"]])
            self.assertEqual(c["checks"], {"solvable": False})
            for key in tc.RESULT_KEYS:
                self.assertIsNone(c[key], key)
            json.dumps(tc._sanitize(c), allow_nan=False)
        for c in cases:
            if c["condition_id"].startswith("D_h_lo") or c["condition_id"] in ("C_h_lo_P5", "A_nominal_P5"):
                self.assertEqual(c["status"], "solved", c["case_id"])
                self.assertEqual(c["Q_front_W"], 0.0)
                self.assertEqual(c["T_outer_C"], c["T_S_C"])
                self.assertEqual(tc._sanitize(c)["R_conv_K_W"], "inf")
        summary = tc.summarize(cases)
        self.assertEqual(summary["n_not_solved"], 12)
        self.assertEqual(summary["n_solved"], 96)

    def test_blocked_nominal_rear_is_admitted_and_overridden_by_finite_conditions(self):
        # The blocked token is a valid nominal: A-group cases are then blocked, while the C/D
        # R_rej conditions override it with finite values from the assumed range.
        cfg = copy.deepcopy(BASE_CFG)
        cfg["boundaries"]["R_rej_K_W"] = "blocked"
        self.assertIs(tc.validate_config(cfg), cfg)
        for c in run_all_cases(cfg):
            self.assertEqual(c["status"], "solved", c["case_id"])
            if c["condition_id"].startswith("A_"):
                self.assertEqual(c["R_rej_K_W"], "blocked")
            if "R_rej_lo" in c["condition_id"]:
                self.assertEqual(c["R_rej_K_W"], 1.0)
                self.assertEqual(c["rear_boundary_condition"], "finite_R_rej_to_ideal_isothermal_reservoir")

    def test_sanitize_is_a_strict_json_projection(self):
        # _sanitize maps inf -> 'inf', -inf -> '-inf', nan -> None, leaves every other leaf and the
        # container structure untouched, is idempotent, and its output is dumpable with allow_nan=False.
        self.assertEqual(tc._sanitize(math.inf), "inf")
        self.assertEqual(tc._sanitize(-math.inf), "-inf")
        self.assertIsNone(tc._sanitize(float("nan")))
        for leaf in (2.5, 0, -7, True, False, None, "txt", "inf"):
            self.assertIs(tc._sanitize(leaf), leaf)
        for _ in range(N):
            obj = rand_json_like(self.rng)
            out = tc._sanitize(obj)
            self.assertEqual(out, my_sanitize(obj))
            self.assertEqual(tc._sanitize(out), out)
            self.assertIs(type(out), type(obj))
            json.dumps(out, allow_nan=False)
        cfg = copy.deepcopy(BASE_CFG)
        for over in ({}, {"h": 0.0}, {"R_rej": "blocked"}, {"h": 0.0, "R_rej": "blocked"}):
            case = tc.run_case(cfg, cfg["stacks"][0], cond("s", 5.0, **over))
            json.dumps(tc._sanitize(case), allow_nan=False)


# ----------------------------------------------------------------------------
# 5. configuration boundary
# ----------------------------------------------------------------------------

class TestConfigurationBoundary(_Base):

    def setUp(self):
        self.rng = random.Random(SEED + 5)

    def assert_rejected(self, cfg, info=None):
        outcome = validation_outcome(cfg)
        self.assertEqual(outcome, "rejected", info)

    def assert_admitted(self, cfg, info=None):
        snapshot = copy.deepcopy(cfg)
        self.assertIs(tc.validate_config(cfg), cfg, info)
        self.assertEqual(cfg, snapshot, ("validation mutated the configuration", info))

    def test_base_configuration_is_admitted_and_unknown_keys_are_ignored(self):
        # The documented validator checks required fields only; documentation-only keys pass through.
        self.assert_admitted(copy.deepcopy(BASE_CFG))
        cfg = copy.deepcopy(BASE_CFG)
        cfg["claim_status"] = "doc"
        cfg["geometry"]["side_m"] = 0.1
        cfg["stacks"][0]["note"] = "x"
        cfg["boundaries"]["radiation"] = "omitted"
        self.assert_admitted(cfg)

    def test_numeric_leaf_type_and_finiteness_mutations_are_rejected(self):
        # Every numeric leaf requires a finite int/float (bool excluded).  Strings, containers, None,
        # bytes, NaN, +-inf and integers too large for float must all be ConfigError, never another
        # exception.  EXPECTED-DIFF: 10**400 raises OverflowError in the frozen original (repair 2).
        for path in NUMERIC_LEAVES:
            for bad in BAD_NUMBERS:
                with self.subTest(path=path, bad=repr(bad)[:40]):
                    cfg = copy.deepcopy(BASE_CFG)
                    set_path(cfg, path, bad)
                    self.assert_rejected(cfg, (path, bad))

    def test_range_leaf_mutations_are_rejected(self):
        # Assumed ranges must be two-element ordered lists of finite numbers (bool excluded).
        for path in RANGE_LEAVES:
            for bad in BAD_RANGES:
                with self.subTest(path=path, bad=repr(bad)):
                    cfg = copy.deepcopy(BASE_CFG)
                    set_path(cfg, path, bad)
                    self.assert_rejected(cfg, (path, bad))

    def test_string_leaf_mutations_are_rejected(self):
        # schema, schema_version, scenario_plan, token, node names and label are fixed literals;
        # study_id is any non-empty string; stack_id is any string.
        # EXPECTED-DIFF: non-string stack_id (None/int/list/dict) is admitted or leaks TypeError in
        # the frozen original (repair 2).
        for path in STRING_LEAVES:
            if path == ("study_id",):
                bads = [b for b in BAD_STRINGS if b != "unexpected"]
            elif path == ("stacks", 0, "stack_id"):
                bads = [None, 1, 1.5, True, [], {}]
            else:
                bads = BAD_STRINGS
            for bad in bads:
                with self.subTest(path=path, bad=repr(bad)):
                    cfg = copy.deepcopy(BASE_CFG)
                    set_path(cfg, path, bad)
                    self.assert_rejected(cfg, (path, bad))

    def test_load_list_mutations_are_rejected(self):
        # P_W_list: exactly three finite numbers ordered low <= mid <= high.
        for bad in BAD_LOADS:
            with self.subTest(bad=repr(bad)):
                cfg = copy.deepcopy(BASE_CFG)
                set_path(cfg, ("sources", "body", "P_W_list"), bad)
                self.assert_rejected(cfg, bad)

    def test_missing_required_fields_are_rejected(self):
        # A missing field is a KeyError inside the validator, converted to ConfigError at its boundary.
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                cfg = copy.deepcopy(BASE_CFG)
                del_path(cfg, path)
                self.assert_rejected(cfg, path)

    def test_section_and_structural_type_mutations_are_rejected(self):
        # Sections and nested objects must be JSON objects; stacks a non-empty list of objects with
        # unique string ids.  EXPECTED-DIFF: the frozen original leaks TypeError for list/str/None/int
        # sections, nested non-objects and non-object stack entries (repair 2).
        for name in SECTIONS:
            for bad in (None, [], "section", 5, 1.5, True):
                with self.subTest(section=name, bad=repr(bad)):
                    cfg = copy.deepcopy(BASE_CFG)
                    cfg[name] = bad
                    self.assert_rejected(cfg, (name, bad))
        for path in (("materials", "silicone_ref"), ("materials", "polyimide_film_ref"),
                     ("sources", "body"), ("sources", "sensor")):
            for bad in (None, [], "x", 5):
                with self.subTest(path=path, bad=repr(bad)):
                    cfg = copy.deepcopy(BASE_CFG)
                    set_path(cfg, path, bad)
                    self.assert_rejected(cfg, (path, bad))
        good = BASE_CFG["stacks"][0]
        for bad_stacks in (None, {}, [], "H1", 5, [None], ["H1"], [5], [[]], [{"stack_id": "H1"}],
                           [dict(good, stack_id=None)], [dict(good, stack_id=7)], [good, dict(good)]):
            with self.subTest(stacks=repr(bad_stacks)[:60]):
                cfg = copy.deepcopy(BASE_CFG)
                cfg["stacks"] = copy.deepcopy(bad_stacks)
                self.assert_rejected(cfg, bad_stacks)
        cfg = copy.deepcopy(BASE_CFG)
        cfg["stacks"] = [copy.deepcopy(good)]
        self.assert_admitted(cfg, "single stack")

    def test_sign_and_range_table(self):
        # Documented admission rules, value by value (True = admitted, False = rejected).
        table = [
            (("geometry", "area_m2"), 0.0, False), (("geometry", "area_m2"), -1e-3, False),
            (("geometry", "area_m2"), 1e-9, True), (("geometry", "area_m2"), 1, True),
            (("materials", "silicone_ref", "k_W_mK"), 0.0, False),
            (("materials", "silicone_ref", "k_W_mK"), -0.27, False),
            (("materials", "silicone_ref", "k_W_mK"), 0.5, False),      # outside [0.18, 0.35]
            (("materials", "silicone_ref", "k_W_mK"), 0.18, True),
            (("materials", "silicone_ref", "k_W_mK"), 0.35, True),
            (("materials", "silicone_ref", "k_assumed_range_W_mK"), [0.0, 0.35], False),   # lo_ok 1e-9
            (("materials", "silicone_ref", "k_assumed_range_W_mK"), [1e-9, 0.35], True),
            (("materials", "silicone_ref", "k_assumed_range_W_mK"), [0.27, 0.27], True),
            (("materials", "polyimide_film_ref", "k_W_mK"), 0.3, False),  # outside [0.12, 0.25]
            (("materials", "silicone_ref", "density_kg_m3"), 0, False),
            (("materials", "silicone_ref", "density_kg_m3"), -5, False),
            (("materials", "silicone_ref", "density_kg_m3"), 1, True),
            (("contacts", "r_c_m2K_W"), -1e-6, False), (("contacts", "r_c_m2K_W"), 0.0, True),
            (("contacts", "r_c_assumed_range_m2K_W"), [-1e-6, 0.002], False),
            (("contacts", "r_c_assumed_range_m2K_W"), [0.0, 0.0], True),
            (("stacks", 0, "t_outer_silicone_m"), -1e-6, False), (("stacks", 0, "t_outer_silicone_m"), 0.0, True),
            (("stacks", 1, "t_inner_silicone_m"), 0.0, True),
            (("thickness_perturbation", "fraction"), -0.1, False), (("thickness_perturbation", "fraction"), 1.0, False),
            (("thickness_perturbation", "fraction"), 0.0, True), (("thickness_perturbation", "fraction"), 0.999, True),
            (("boundaries", "T_amb_C"), -273.15, True), (("boundaries", "T_res_C"), 1e6, True),
            (("boundaries", "h_W_m2K"), -1.0, False), (("boundaries", "h_W_m2K"), 0.0, True),
            (("boundaries", "h_assumed_range_W_m2K"), [-1.0, 15.0], False),
            (("boundaries", "h_assumed_range_W_m2K"), [0.0, 15.0], True),
            (("boundaries", "R_rej_K_W"), 0.0, False), (("boundaries", "R_rej_K_W"), -2.0, False),
            (("boundaries", "R_rej_K_W"), "blocked", True), (("boundaries", "R_rej_K_W"), "Blocked", False),
            (("boundaries", "R_rej_K_W"), "inf", False), (("boundaries", "R_rej_K_W"), math.inf, False),
            (("boundaries", "R_rej_K_W"), 1e-300, True),
            (("boundaries", "R_rej_assumed_range_K_W"), [0.0, 10.0], False),
            (("boundaries", "R_rej_assumed_range_K_W"), [1e-12, 10.0], True),
            (("boundaries", "R_rej_assumed_range_K_W"), [1e-13, 10.0], False),
            (("boundaries", "R_rej_blocked_token"), "BLOCKED", False),
            (("sources", "body", "P_W_list"), [5.0, 5.0, 5.0], True),
            (("sources", "body", "P_W_list"), [-1.0, 0.0, 1.0], True),
            (("sources", "body", "P_W_list"), [1.0, 0.5, 10.0], False),
            (("sources", "sensor", "P_W"), -0.1, True), (("sources", "sensor", "P_W"), 0.0, True),
            (("comparators", "label"), "study_comparator", False),
            (("comparators", "outer_surface_C"), -1000.0, True),
            (("numerics", "energy_abs_tol_W"), 0.0, False), (("numerics", "energy_abs_tol_W"), -1e-10, False),
            (("numerics", "energy_abs_tol_W"), 1.0, True),
            (("numerics", "energy_rel_tol"), 0.0, False), (("numerics", "agreement_tol_K"), 0.0, False),
            (("scenario_plan",), "deterministic_builtin_v2", False),
            (("schema",), "stage.thermal_contract.steady ", False),
            (("schema_version",), "T0-HYP-1.1", False),
            (("study_id",), " ", True),
        ]
        for path, value, admitted in table:
            with self.subTest(path=path, value=repr(value)):
                cfg = copy.deepcopy(BASE_CFG)
                set_path(cfg, path, value)
                if admitted:
                    self.assert_admitted(cfg, (path, value))
                else:
                    self.assert_rejected(cfg, (path, value))

    def test_equal_film_thickness_property(self):
        # The output asserts "film thickness held equal across stacks"; the validator must therefore
        # reject any pair of stacks with different t_film_m and admit equal ones regardless of int/float
        # spelling or stack order.  EXPECTED-DIFF: the frozen original admits unequal films (repair 3).
        for _ in range(N_CFG):
            cfg = rand_config(self.rng)
            while len(cfg["stacks"]) < 2:
                cfg = rand_config(self.rng)
            self.assert_admitted(cfg)
            cfg_bad = copy.deepcopy(cfg)
            j = self.rng.randrange(len(cfg_bad["stacks"]))
            cfg_bad["stacks"][j]["t_film_m"] = cfg_bad["stacks"][j]["t_film_m"] * 2.0 + 1e-6
            self.assert_rejected(cfg_bad, "unequal film")
            cfg_zero = copy.deepcopy(cfg)
            for i, s in enumerate(cfg_zero["stacks"]):
                s["t_film_m"] = 0 if i % 2 == 0 else 0.0
            self.assert_admitted(cfg_zero, "zero film, int/float spelling")
            cfg_rev = copy.deepcopy(cfg)
            cfg_rev["stacks"].reverse()
            self.assert_admitted(cfg_rev, "reversed stacks")

    def test_parse_R_rej_table(self):
        # Exactly the blocked token maps to inf; finite positive numbers map to float; all else is a
        # ConfigError.  EXPECTED-DIFF: 10**400 raises OverflowError in the frozen original.
        self.assertEqual(tc.parse_R_rej("blocked"), math.inf)
        for v in (2, 2.0, 1e-300, 1e300):
            out = tc.parse_R_rej(v)
            self.assertIsInstance(out, float)
            self.assertEqual(out, float(v))
        for v in (0, 0.0, -2.0, math.inf, -math.inf, float("nan"), None, True, "2.0", "BLOCKED", "", [], {}, 10 ** 400):
            with self.subTest(v=repr(v)[:40]):
                with self.assertRaises(tc.ConfigError):
                    tc.parse_R_rej(v)

    def test_finite_predicate_table(self):
        # _finite accepts exactly finite int/float values; bool, NaN, infinities, non-numbers and ints
        # that overflow float are False.  EXPECTED-DIFF: 10**400 raises OverflowError in the original.
        for v in (0, 1, -1, 0.0, 1e-300, -1e300, 2 ** 53, 10 ** 300):
            self.assertTrue(tc._finite(v), v)
        for v in (True, False, math.inf, -math.inf, float("nan"), None, "1", [], {}, 10 ** 400, -(10 ** 400)):
            self.assertFalse(tc._finite(v), repr(v)[:40])

    def test_random_admitted_configurations_build_a_plan_and_run_end_to_end(self):
        # Admission implies the plan builds (36 unique ids) and every case runs solved with passing
        # energy and semantic checks; validation is pure (returns its argument unchanged).
        for _ in range(N_CFG):
            cfg = rand_config(self.rng)
            self.assert_admitted(cfg)
            conds = tc.build_shared_conditions(cfg)
            self.assertEqual(len({c["condition_id"] for c in conds}), 36)
            cases = run_all_cases(cfg)
            self.assertEqual(len(cases), 36 * len(cfg["stacks"]))
            for c in cases:
                self.assertEqual(c["status"], "solved", c["case_id"])
                self.assertTrue(c["energy_check_pass"], c["case_id"])
                self.assertEqual(c["status_note"], tc.STATUS_NOTES["solved"])
                for key, val in c["checks"].items():
                    self.assertIn(val, (True, None), (key, c["case_id"]))

    def test_helper_and_condition_boundaries_reject_invalid_arguments(self):
        # conductance_W_K: R >= 0 with both limits explicit; layer_resistance_K_W: t >= 0, k > 0, A > 0;
        # resolve_parameters: finite values, k > 0, r_c and h >= 0, thickness scale > 0, valid R_rej.
        self.assertEqual(tc.conductance_W_K(0.0), math.inf)
        self.assertEqual(tc.conductance_W_K(math.inf), 0.0)
        self.assertEqual(tc.conductance_W_K(4.0), 0.25)
        for bad in (-1.0, -1e-300, float("nan")):
            with self.assertRaises(ValueError):
                tc.conductance_W_K(bad)
        for args in ((-1e-3, 0.27, 0.01), (1e-3, 0.0, 0.01), (1e-3, -0.27, 0.01), (1e-3, 0.27, 0.0),
                     (1e-3, 0.27, -0.01)):
            with self.assertRaises(ValueError):
                tc.layer_resistance_K_W(*args)
        self.assertEqual(tc.layer_resistance_K_W(0.0, 0.27, 0.01), 0.0)
        cfg = copy.deepcopy(BASE_CFG)
        for over in ({"h": -1.0}, {"k_sil": 0.0}, {"k_film": -0.2}, {"r_c": -1e-6}, {"r_c_inner": -1e-6},
                     {"t_bias": -1.0}, {"t_dev_inner": -1.5}, {"t_bias": float("nan")}, {"h": math.inf},
                     {"R_rej": 0.0}, {"R_rej": -1.0}, {"R_rej": "BLOCKED"}, {"P_sensor": float("nan")},
                     {"T_amb": math.inf}):
            with self.subTest(over=repr(over)):
                with self.assertRaises(tc.ConfigError):
                    tc.resolve_parameters(cfg, cond("bad", 5.0, **over))
        p = tc.resolve_parameters(cfg, cond("ok", 5.0, R_rej="blocked", t_bias=0.1, t_dev_inner=-0.1))
        self.assertEqual(p["R_rej"], math.inf)
        self.assertClose(p["t_scale_inner"], 1.1 * 0.9, 1e-12)
        self.assertClose(p["t_scale_outer"], 1.1, 1e-12)
        self.assertEqual(p["t_scale_film"], 1.0)


# ----------------------------------------------------------------------------
# 6. informational: relations the documented contract does NOT promise
# ----------------------------------------------------------------------------

@unittest.skipUnless(INFORMATIONAL, "relations the contract does not promise; THERMAL_TEST_INFORMATIONAL=1 to run")
class InformationalNotPromised(_Base):
    """Each method asserts something I initially expected that the module's documented contract
    does not promise.  Failures here are expected and are not defects by themselves; they mark the
    boundary of the contract (see the accompanying notes)."""

    def setUp(self):
        self.rng = random.Random(SEED + 6)

    def test_info_T_S_monotone_in_contact_resistance_with_sensor_off(self):
        # With P_s = 0: T_S - T0 = R_rej P_b (R_SA + d)/(R_sum + 2d); its derivative has the sign of
        # R_HS + R_rej - R_SA, negative whenever the front path already dominates.  Not promised.
        for _ in range(N):
            stack, p = rand_stack(self.rng), rand_params(self.rng, P_sensor=0.0)
            p["T_res"] = p["T_amb"]
            _, _, r0 = solve_path(stack, p)
            _, _, r1 = solve_path(stack, dict(p, r_c_inner=p["r_c_inner"] * 5.0 + 1e-3,
                                              r_c_outer=p["r_c_outer"] * 5.0 + 1e-3))
            self.assertLE(r0["T_S_C"], r1["T_S_C"], msg=(stack, p))

    def test_info_T_H_monotone_in_silicone_thickness_with_sensor_on(self):
        # dQ_front/dR_HS has the sign of P_s R_SA - R_rej P_b - (T_res - T_amb); T_H can fall when the
        # inner layer thickens.  Built-in v12 documents exactly this exception.  Not promised.
        for _ in range(N):
            stack, p = rand_stack(self.rng), rand_params(self.rng)
            p["T_res"] = p["T_amb"]
            _, _, r0 = solve_path(stack, p)
            _, _, r1 = solve_path(stack, dict(p, t_scale_inner=1.5, t_scale_outer=1.5))
            self.assertLE(r0["T_H_C"], r1["T_H_C"], msg=(stack, p))

    def test_info_gauss_cross_check_agrees_under_extreme_conditioning(self):
        # The repair only returns None when the pivot cancels exactly; a catastrophically cancelled
        # but non-zero pivot yields a disagreeing Gauss result, reported False by semantic_checks.
        # The repair report excludes "other extreme-value conditioning".  Not promised.
        for G_rej in (1e-12, 1e-13, 1e-14, 1e-15):
            sol = tc.solve_two_node(1.0, 0.0, G_rej, 5.0, 0.1, 25.0, 25.0)
            if sol["T_H_gauss"] is not None:
                self.assertClose(sol["T_H_gauss"], sol["T_H"], msg=G_rej)
                self.assertClose(sol["T_S_gauss"], sol["T_S"], msg=G_rej)

    def test_info_tiny_positive_conductances_do_not_underflow_the_determinant(self):
        # det = 3e-400 underflows to 0.0 -> classify_singular -> 'singular_unclassified', a status that
        # is not in STATUS_NOTES.  Explicitly outside the bounded repair.  Not promised.
        sol = tc.solve_two_node(1e-200, 1e-200, 1e-200, 1.0, 0.0, 25.0, 25.0)
        self.assertEqual(sol["status"], "solved")
        self.assertIn(sol["status"], tc.STATUS_NOTES)

    def test_info_equal_or_tag_colliding_loads_build_a_plan(self):
        # validate_config admits ordered loads with equal or %g-colliding values; build_shared_conditions
        # then rejects the duplicate condition_id ("identifier rounding", outside the repair).
        for loads in ([5.0, 5.0, 5.0], [1.0, 1.0000000001, 10.0], [0.1, 0.1000001, 10.0]):
            cfg = copy.deepcopy(BASE_CFG)
            cfg["sources"]["body"]["P_W_list"] = loads
            tc.validate_config(cfg)
            conds = tc.build_shared_conditions(cfg)
            self.assertEqual(len(conds), 36, loads)

    def test_info_validator_rejects_negative_or_unordered_physical_choices(self):
        # Any finite sensor or body power is admitted (the exact reference rejects negative sources);
        # nominal r_c, h and R_rej are not required to lie inside their assumed ranges (only k is).
        for path, value in ((("sources", "sensor", "P_W"), -0.1),
                            (("sources", "body", "P_W_list"), [-5.0, 0.0, 5.0]),
                            (("contacts", "r_c_m2K_W"), 0.01),
                            (("boundaries", "h_W_m2K"), 100.0),
                            (("boundaries", "R_rej_K_W"), 100.0),
                            (("stacks", 0, "stack_id"), ""),
                            (("study_id",), " ")):
            with self.subTest(path=path, value=value):
                cfg = copy.deepcopy(BASE_CFG)
                set_path(cfg, path, value)
                self.assertEqual(validation_outcome(cfg), "rejected", (path, value))

    def test_info_h_zero_nominal_study_is_fully_solvable(self):
        # h = 0 nominal is admitted but the blocked-rear conditions then have no steady state.
        cfg = copy.deepcopy(BASE_CFG)
        cfg["boundaries"]["h_W_m2K"] = 0.0
        cfg["boundaries"]["h_assumed_range_W_m2K"] = [0.0, 15.0]
        tc.validate_config(cfg)
        self.assertEqual(tc.summarize(run_all_cases(cfg))["n_not_solved"], 0)

    def test_info_large_h_drives_T_S_to_T_amb(self):
        # Only R_conv vanishes; the solid front resistance keeps T_S above T_amb (first report).
        _, _, res = solve_path(tc._ref_stack(), tc._ref_params(h=1e30))
        self.assertClose(res["T_S_C"], 25.0, 1e-6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
