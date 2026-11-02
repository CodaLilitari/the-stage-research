Red — thank you. Below is a complete, self-contained deliverable: one unittest module plus notes. I have not executed anything; all reasoning about expected behaviour is static. Derivations behind each relation are in the test comments.

## Deliverable overview

- **File:** `tests/test_thermal_contract_metamorphic.py` (stdlib only, seeded, bounded; no file writes; imports the module under test from `THERMAL_CONTRACT_PATH`, the exact reference from `THERMAL_REFERENCE_PATH` or the sibling `thermal/thermal_reference.py` layout).
- **Five strict test classes** (true properties of the documented contract; a failure indicates a defect or a wrong assumption of mine, to be reviewed):
  1. `TestSolverAlgebra` — `solve_two_node`: node balances, superposition, boundary affinity/convex weights, uniform shift, joint scaling, H↔S role symmetry, Gauss cross-check availability, determinant formula, maximum principle, monotonicity in exit and internal conductances, singular-pattern classification vs. an independent existence analysis, invalid inputs, tiny-exit robustness.
  2. `TestAssembledNetwork` — assembled path: energy/sign bookkeeping, reversed-gradient series divider, outer-surface identity, resistance assembly homogeneity, areal intensivity, blocked-rear series branch (T_outer independent of layers), inner/outer swap invariance, limits (R_rej→∞, r_c→0, h→0, h→∞, k→∞, R_HS→0), monotonicity in h, R_rej, k_sil, r_c, thickness and loads, affine-in-load slopes, the module's own semantic checks across the domain.
  3. `TestExactReference` — Fraction-exact agreement with `thermal_reference.steady` for random assembled cases, random `run_case` override conditions, and the full 36-condition plan on random valid configurations; status mapping when both exits are absent.
  4. `TestRunCaseAndPlan` — relabel/reorder invariances, override identities, comparator/numerics/density isolation, summarize permutation invariance, plan structure, cross-stack blocked T_outer equality, Pareto-line collinearity, unsolvable statuses, `_sanitize` properties and JSON serialisability.
  5. `TestConfigurationBoundary` — systematic leaf mutation (type/finite/overflow), key deletion, section types, sign/range table, equal-film property, `parse_R_rej`, `_finite`, random admitted configurations run end-to-end, and “admitted ⇒ plan builds with unique IDs”.
- **One informational class** (`InformationalNotPromised`, enabled only with `THERMAL_TEST_INFORMATIONAL=1`) holding expectations the contract does not promise (listed separately below).

Expected (by static reading) differences between original and repaired versions are flagged in comments: huge-int `_finite`, structural type checks, equal-film enforcement, tiny-exit Gauss `None`, stack_id typing.

FILE: tests/test_thermal_contract_metamorphic.py
```python
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
        # The Gauss cross-check may be unavailable (None) but must never be a disagreeing number.
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
                self.assertClose(sol["T_H_gauss"], sol["T_H"], 1e-6)
                self.assertClose(sol["T_S_gauss"], sol["T_S"], 1e-6)

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
            self.assertClose(R["R_HS_K_W"], R["R_inner_silicone_K_W"] + 0