Red — continuing from the truncation point. The earlier instance delivered the predeclaration in full and only the first part of the docstring of `steady_closed_form.py` (cut off mid-formula); a fragment of a docstring is not usable code, so that file is delivered here **complete** (same conventions and formulas, docstring finished), together with every other missing file. Nothing in `PREDECLARED_SENSITIVITY.md` is changed. Everything below is unexecuted static work; please run and return observed output.

## Files delivered here (all new/completing; stdlib only, Python 3.10+)

- `validation/thermal_sensitivity/steady_closed_form.py` — (a) exact closed form, exact partials (hand formulas + exact dual-number AD + exact central differences), ranking classification, analytic discriminant, uniform-measure flip fraction, Coda's 12 reference rows embedded as fixtures.
- `validation/thermal_sensitivity/sampling.py` — (b) Morris elementary effects, Latin-hypercube Saltelli/Jansen Sobol estimators, deterministic string seeds, design digests.
- `validation/thermal_sensitivity/transient_wrapper.py` — loads Coda's `rc_transient.py` by path and calls `simulate`/`nominal`; builds T0-LUMP2-1 parameters from the sensitivity factors; scenario schedules; peak extraction.
- `validation/thermal_sensitivity/thermal_sensitivity.py` — driver: reference check, nominal partial tables, analytic condition, exact grid classification, steady and transient Morris/Sobol, acceptance checks AC1–AC10, predictions P1–P4, deviations, single JSON output to `--output`.
- `validation/thermal_sensitivity/test_steady_closed_form.py`, `test_sampling.py`, `test_thermal_sensitivity.py` — (d) unittests.

FILE: validation/thermal_sensitivity/steady_closed_form.py
```python
"""Exact closed-form steady temperatures, partial derivatives and the surface/internal
ranking-reversal condition for the T0-HYP-1 two-node steady reduction (thermal-sensitivity-001).

Author: Claude (Anthropic), static contribution coordinated by Red; executed by Red, not the author.
The network and elimination follow Coda's validation/thermal/ACCEPTANCE_PREDECLARED.md and
thermal_reference.py (Coda = Codex Lily, collaborating with Andrei). Standard library only.

Symbols (W, K/W, m, Celsius):
  A area; k_s silicone conductivity; k_f film conductivity; r_c areal contact resistance;
  h outer convection coefficient; r = R_rej rear resistance (None = blocked, zero rear conductance);
  P body power at H; J sensor power at the film midplane S; t_o, t_f, t_i outer silicone, film and
  inner silicone thickness; T_amb, T_res reservoir temperatures.

Closed form (finite r):
  a  = R_HS = t_i/(k_s A) + t_f/(2 k_f A) + r_c/A
  b0 = t_o/(k_s A) + t_f/(2 k_f A) + r_c/A,   c = 1/(h A),   b = R_SA = b0 + c
  D = a + b + r,   N = (T_res - T_amb) + r (P + J) + a J,   F = N/D      (front flux, + outward)
  B = P + J - F                                                           (rear flux, + outward)
  T_surface = T_amb + c F,   T_S = T_amb + b F,   T_H = T_S + a (F - J) = T_res + r B
Rear blocked: F = P + J, B = 0, same temperature expressions.

Exact partials (finite r):
  dF/da = (J b - r P - (T_res - T_amb))/D^2,  dF/db = -F/D,  dF/dr = B/D,
  dF/dP = r/D,  dF/dJ = (a + r)/D,  dF/dT_res = 1/D = -dF/dT_amb
  da/dk_s = -t_i/(k_s^2 A),  db/dk_s = -t_o/(k_s^2 A),  da/dk_f = db/dk_f = -t_f/(2 k_f^2 A)
  da/dr_c = db/dr_c = 1/A,  db/dh = dc/dh = -1/(h^2 A)
  da/dt_i = db/dt_o = 1/(k_s A),  da/dt_f = db/dt_f = 1/(2 k_f A)
  dF/dx = (dF/da)(da/dx) + (dF/db)(db/dx) + direct terms for x in {r, P, J, T_amb, T_res}
  dT_surface/dx = [x = T_amb] + (dc/dx) F + c dF/dx
  dT_S/dx       = [x = T_amb] + (db/dx) F + b dF/dx
  dT_H/dx       = dT_S/dx + (da/dx)(F - J) + a (dF/dx - [x = J])
Rear blocked: dF/dP = dF/dJ = 1, all other dF/dx = 0, same temperature chain.

Ranking of two stacks X (thinner) and Y (thicker) under identical exogenous conditions:
  T_surface(X) - T_surface(Y) = c (F_X - F_Y),   T_H(X) - T_H(Y) = -r (F_X - F_Y)
  sign(F_X - F_Y) = sign(N_X D_Y - N_Y D_X)   (the "discriminant")
  symmetric stacks (t_o = t_i, shared relative deviations):
  N_X D_Y - N_Y D_X = (a_Y - a_X) [ r (2P + J) - J/(h A) + 2 (T_res - T_amb) ]
  general stacks with shared u = (1+d_i)/(k_s A), v = (1+d_o)/(k_s A), s = half-film + contact, E = c + r:
  N_X D_Y - N_Y D_X = (t_Y - t_X) [ K (u + v) - J s (u - v) - J E u ],  K = (T_res - T_amb) + r (P + J)
Classes: reference (X warmer surface, cooler interior), flipped, tie, tie_surface, tie_interior,
same_direction (impossible with finite shared r > 0 and c > 0).

Exact arithmetic uses fractions.Fraction; the same functions also run on floats (used by sampling)
and on the small Dual class (exact forward-mode AD used only as a cross-check of the hand partials).
Nothing here is physical validation.
"""
from fractions import Fraction
import math

STACKS = ("H1", "H2", "H3")
PAIRS = (("H1", "H2"), ("H2", "H3"), ("H1", "H3"))
FACTOR_NAMES = ("k_s", "k_f", "r_c", "h", "r", "P", "J", "T_amb", "T_res", "t_o", "t_f", "t_i")
EXOGENOUS_NAMES = ("k_s", "k_f", "r_c", "h", "r", "P", "J", "T_amb", "T_res")
THICKNESS_MODES = ("nominal", "common_bias", "independent_layers")
OUTPUT_KEYS = ("F", "T_surface", "T_S", "T_H")
RANKING_CLASSES = ("reference", "flipped", "tie", "tie_surface", "tie_interior", "same_direction")

AREA_M2 = Fraction(1, 100)
FILM_M = Fraction(1, 20000)
STACK_SILICONE_M = {"H1": Fraction(1, 2000), "H2": Fraction(1, 1000), "H3": Fraction(1, 500)}
NOMINAL_EXOGENOUS = {"k_s": Fraction(27, 100), "k_f": Fraction(1, 5), "r_c": Fraction(1, 5000),
                     "h": Fraction(8), "r": Fraction(2), "P": Fraction(5), "J": Fraction(1, 10),
                     "T_amb": Fraction(25), "T_res": Fraction(25)}


def exact(x):
    """Fraction from int/Fraction/float/str. Floats use their shortest repr (0.1 -> 1/10)."""
    if isinstance(x, bool):
        raise TypeError("Boolean is not a number")
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError("Nonfinite value")
        return Fraction(repr(x))
    if isinstance(x, str):
        return Fraction(x)
    raise TypeError("Unsupported numeric type: %r" % type(x))


def _blocked(value):
    return value is None or (isinstance(value, float) and math.isinf(value))


def thicknesses(stack, mode="nominal", deltas=None):
    """(t_o, t_f, t_i) for a stack under a thickness perturbation mode (relative deltas)."""
    if stack not in STACK_SILICONE_M:
        raise ValueError("Unknown stack " + repr(stack))
    t, f = STACK_SILICONE_M[stack], FILM_M
    deltas = deltas or {}
    if mode == "nominal":
        return t, f, t
    if mode == "common_bias":
        d = deltas["delta_all"]
        return t * (1 + d), f * (1 + d), t * (1 + d)
    if mode == "independent_layers":
        return (t * (1 + deltas["delta_outer"]), f * (1 + deltas["delta_film"]),
                t * (1 + deltas["delta_inner"]))
    raise ValueError("Unknown thickness mode " + repr(mode))


def validate(p):
    for name in ("k_s", "k_f", "h", "t_o", "t_f", "t_i", "A"):
        if not p[name] > 0:
            raise ValueError(name + " must be positive")
    for name in ("r_c", "P", "J"):
        if p[name] < 0:
            raise ValueError(name + " must be nonnegative")
    if p["r"] is not None and not p["r"] > 0:
        raise ValueError("r must be positive or None (blocked rear)")
    for name in ("T_amb", "T_res"):
        if isinstance(p[name], float) and not math.isfinite(p[name]):
            raise ValueError(name + " must be finite")
    return p


def make_params(stack, mode="nominal", deltas=None, exact_arithmetic=True, **exogenous):
    """Parameter dict for one stack. Exogenous overrides: k_s k_f r_c h r (or R_rej) P J T_amb T_res.
    r=None or r=inf means blocked rear. exact_arithmetic=True converts everything to Fraction."""
    if "R_rej" in exogenous:
        exogenous["r"] = exogenous.pop("R_rej")
    unknown = set(exogenous) - set(EXOGENOUS_NAMES)
    if unknown:
        raise ValueError("Unknown exogenous names " + repr(sorted(unknown)))
    p = dict(NOMINAL_EXOGENOUS)
    p.update(exogenous)
    deltas = dict(deltas or {})
    if exact_arithmetic:
        conv = exact
    else:
        conv = float
    deltas = {k: conv(v) for k, v in deltas.items()}
    for k in list(p):
        p[k] = None if (k == "r" and _blocked(p[k])) else conv(p[k])
    t_o, t_f, t_i = thicknesses(stack, mode, deltas)
    p.update(A=conv(AREA_M2), t_o=conv(t_o), t_f=conv(t_f), t_i=conv(t_i), stack=stack, mode=mode)
    return validate(p)


def resistances(p):
    """Return (a, b0, c, b)."""
    A = p["A"]
    half_film = p["t_f"] / (2 * p["k_f"] * A)
    contact = p["r_c"] / A
    a = p["t_i"] / (p["k_s"] * A) + half_film + contact
    b0 = p["t_o"] / (p["k_s"] * A) + half_film + contact
    c = 1 / (p["h"] * A)
    return a, b0, c, b0 + c


def steady(p):
    """Closed-form steady state (generic arithmetic: Fraction, float or Dual)."""
    a, b0, c, b = resistances(p)
    P, J, r = p["P"], p["J"], p["r"]
    if r is None:
        N = None
        D = None
        F = P + J
    else:
        D = a + b + r
        N = (p["T_res"] - p["T_amb"]) + r * (P + J) + a * J
        F = N / D
    B = P + J - F
    T_surface = p["T_amb"] + c * F
    T_S = p["T_amb"] + b * F
    T_H = T_S + a * (F - J)
    return {"a": a, "b0": b0, "c": c, "b": b, "r": r, "D": D, "N": N, "F": F, "B": B,
            "T_surface": T_surface, "T_S": T_S, "T_H": T_H, "P": P, "J": J,
            "T_amb": p["T_amb"], "T_res": p["T_res"]}


def steady_from_resistances(a, b0, c, r, P, J, T_amb=0, T_res=0):
    """Convenience for Coda's resistance-level fixtures (all values exact)."""
    p = {"A": Fraction(1), "k_s": Fraction(1), "k_f": Fraction(1), "r_c": Fraction(0),
         "h": None, "t_f": Fraction(0), "t_o": exact(b0), "t_i": exact(a),
         "P": exact(P), "J": exact(J), "T_amb": exact(T_amb), "T_res": exact(T_res),
         "r": None if _blocked(r) else exact(r)}
    # h enters only through c; emulate c directly by a private override below.
    a_, b0_, c_, b_ = exact(a), exact(b0), exact(c), exact(b0) + exact(c)
    P_, J_, r_ = p["P"], p["J"], p["r"]
    if r_ is None:
        D = N = None
        F = P_ + J_
    else:
        D = a_ + b_ + r_
        N = (p["T_res"] - p["T_amb"]) + r_ * (P_ + J_) + a_ * J_
        F = N / D
    B = P_ + J_ - F
    T_surface = p["T_amb"] + c_ * F
    T_S = p["T_amb"] + b_ * F
    T_H = T_S + a_ * (F - J_)
    return {"a": a_, "b0": b0_, "c": c_, "b": b_, "r": r_, "D": D, "N": N, "F": F, "B": B,
            "T_surface": T_surface, "T_S": T_S, "T_H": T_H, "P": P_, "J": J_,
            "T_amb": p["T_amb"], "T_res": p["T_res"]}


def partials(p, x):
    """Hand-coded exact partials of F, T_surface, T_S, T_H with respect to factor x."""
    if x not in FACTOR_NAMES:
        raise ValueError("Unknown factor " + repr(x))
    s = steady(p)
    a, b, c, F, B, D = s["a"], s["b"], s["c"], s["F"], s["B"], s["D"]
    A, k_s, k_f, h, r, P, J = p["A"], p["k_s"], p["k_f"], p["h"], p["r"], p["P"], p["J"]
    if r is None and x == "r":
        raise ValueError("Rear path blocked: no finite r to differentiate")
    zero = 0 * F
    da = db = dc = zero
    if x == "k_s":
        da = -p["t_i"] / (k_s * k_s * A)
        db = -p["t_o"] / (k_s * k_s * A)
    elif x == "k_f":
        da = db = -p["t_f"] / (2 * k_f * k_f * A)
    elif x == "r_c":
        da = db = 1 / A
    elif x == "h":
        dc = -1 / (h * h * A)
        db = dc
    elif x == "t_i":
        da = 1 / (k_s * A)
    elif x == "t_o":
        db = 1 / (k_s * A)
    elif x == "t_f":
        da = db = 1 / (2 * k_f * A)
    if r is None:
        dF = 1 if x in ("P", "J") else 0
    else:
        dT = p["T_res"] - p["T_amb"]
        dF_da = (J * b - r * P - dT) / (D * D)
        dF_db = -F / D
        dF = dF_da * da + dF_db * db
        if x == "r":
            dF = dF + B / D
        elif x == "P":
            dF = dF + r / D
        elif x == "J":
            dF = dF + (a + r) / D
        elif x == "T_res":
            dF = dF + 1 / D
        elif x == "T_amb":
            dF = dF - 1 / D
    amb = 1 if x == "T_amb" else 0
    dT_surface = amb + dc * F + c * dF
    dT_S = amb + db * F + b * dF
    dT_H = dT_S + da * (F - J) + a * (dF - (1 if x == "J" else 0))
    return {"F": dF, "T_surface": dT_surface, "T_S": dT_S, "T_H": dT_H}


class Dual:
    """Minimal forward-mode dual number (value, derivative) for the exact AD cross-check."""
    __slots__ = ("v", "d")

    def __init__(self, v, d=0):
        self.v = v
        self.d = d

    @staticmethod
    def lift(o):
        return o if isinstance(o, Dual) else Dual(o, 0)

    def __add__(self, o):
        o = Dual.lift(o)
        return Dual(self.v + o.v, self.d + o.d)

    __radd__ = __add__

    def __sub__(self, o):
        o = Dual.lift(o)
        return Dual(self.v - o.v, self.d - o.d)

    def __rsub__(self, o):
        o = Dual.lift(o)
        return Dual(o.v - self.v, o.d - self.d)

    def __mul__(self, o):
        o = Dual.lift(o)
        return Dual(self.v * o.v, self.v * o.d + self.d * o.v)

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = Dual.lift(o)
        return Dual(self.v / o.v, (self.d * o.v - self.v * o.d) / (o.v * o.v))

    def __rtruediv__(self, o):
        return Dual.lift(o).__truediv__(self)

    def __neg__(self):
        return Dual(-self.v, -self.d)


def partials_by_dual(p, x):
    """Exact partials via dual numbers (independent of the hand formulas)."""
    if x not in FACTOR_NAMES:
        raise ValueError("Unknown factor " + repr(x))
    if p["r"] is None and x == "r":
        raise ValueError("Rear path blocked: no finite r to differentiate")
    q = dict(p)
    one = Fraction(1) if isinstance(p[x], Fraction) else 1.0
    q[x] = Dual(p[x], one)
    s = steady(q)
    return {k: (s[k].d if isinstance(s[k], Dual) else 0) for k in OUTPUT_KEYS}


def partials_by_central_difference(p, x, relative_step=Fraction(1, 10 ** 6)):
    """Exact-arithmetic central differences (truncation error only, no rounding)."""
    if p["r"] is None and x == "r":
        raise ValueError("Rear path blocked: no finite r to differentiate")
    x0 = p[x]
    eps = abs(x0) * relative_step if x0 != 0 else relative_step / 1000
    plus, minus = dict(p), dict(p)
    plus[x] = x0 + eps
    minus[x] = x0 - eps
    sp, sm = steady(plus), steady(minus)
    return {k: (sp[k] - sm[k]) / (2 * eps) for k in OUTPUT_KEYS}


def sign(x):
    return (x > 0) - (x < 0)


def ranking_class(surface_sign, interior_sign):
    """surface_sign = sign(T_surface(thin) - T_surface(thick)); interior_sign likewise for T_H."""
    if surface_sign == 0 and interior_sign == 0:
        return "tie"
    if surface_sign == 0:
        return "tie_surface"
    if interior_sign == 0:
        return "tie_interior"
    if surface_sign > 0 and interior_sign < 0:
        return "reference"
    if surface_sign < 0 and interior_sign > 0:
        return "flipped"
    return "same_direction"


def brute_force_class(s_thin, s_thick):
    """Classification from the temperatures themselves (steady() dicts, exact arithmetic)."""
    return ranking_class(sign(s_thin["T_surface"] - s_thick["T_surface"]),
                         sign(s_thin["T_H"] - s_thick["T_H"]))


def discriminant(s_thin, s_thick):
    """N_X D_Y - N_Y D_X; sign equals sign(F_X - F_Y) under shared finite r. None if blocked."""
    if s_thin["D"] is None or s_thick["D"] is None:
        return None
    return s_thin["N"] * s_thick["D"] - s_thick["N"] * s_thin["D"]


def analytic_class(s_thin, s_thick):
    """Classification from the analytic condition only (requires identical exogenous conditions,
    shared c > 0 and shared r > 0 or both blocked)."""
    d = discriminant(s_thin, s_thick)
    if d is None:
        P, J = s_thin["P"], s_thin["J"]
        interior = sign((s_thin["a"] - s_thick["a"]) * P + (s_thin["b"] - s_thick["b"]) * (P + J))
        return ranking_class(0, interior)
    return ranking_class(sign(d), -sign(d))


def symmetric_bracket(s):
    """r (2P + J) - J/(h A) + 2 (T_res - T_amb) for a steady() dict; None if blocked."""
    if s["r"] is None:
        return None
    return s["r"] * (2 * s["P"] + s["J"]) - s["J"] * s["c"] + 2 * (s["T_res"] - s["T_amb"])


def symmetric_discriminant(s_thin, s_thick):
    br = symmetric_bracket(s_thin)
    return None if br is None else (s_thick["a"] - s_thin["a"]) * br


def kappa(P, J=Fraction(1, 10), A=AREA_M2):
    """Flip threshold with equal reservoirs: flipped iff R_rej < kappa/h, kappa = J/(A (2P + J))."""
    return exact(J) / (exact(A) * (2 * exact(P) + exact(J)))


def uniform_flip_fraction(kap, h_lo=3.0, h_hi=15.0, r_lo=1.0, r_hi=10.0):
    """Uniform-measure fraction of [h_lo,h_hi]x[r_lo,r_hi] with r < kap/h (a domain fraction,
    not a probability)."""
    kap, h_lo, h_hi, r_lo, r_hi = (float(v) for v in (kap, h_lo, h_hi, r_lo, r_hi))
    if kap <= 0:
        return 0.0
    h1 = min(h_hi, max(h_lo, kap / r_hi))
    h2 = min(h_hi, max(h_lo, kap / r_lo))
    area = (h1 - h_lo) * (r_hi - r_lo)
    if h2 > h1:
        area += kap * math.log(h2 / h1) - r_lo * (h2 - h1)
    return area / ((h_hi - h_lo) * (r_hi - r_lo))


# Coda's executed reference rows (validation/thermal/reference_results.json, sha256 e97cf35c...af56).
# Values copied verbatim; they are the acceptance targets, independent of the functions above.
CODA_REFERENCE_ROWS = (
    ("H1", 1, False, "239951/1613020", 26.90248230028146, 26.891868221020427, 26.85948562324088),
    ("H1", 5, False, "1103951/1613020", 33.83119986113005, 33.70398462379287, 33.55500086793716),
    ("H1", 10, False, "2183951/1613020", 42.492096812190795, 42.21913012725842, 41.92439492380752),
    ("H1", 5, True, "51/10", 90.94862037037036, 89.86019444444445, 88.75),
    ("H2", 1, False, "241951/1653020", 26.907261860110584, 26.88858113572823, 26.829613374308842),
    ("H2", 5, False, "1105951/1653020", 33.86190245732054, 33.6326495680521, 33.36310964174662),
    ("H2", 10, False, "2185951/1653020", 42.55520320383298, 42.062735108456934, 41.52997997604385),
    ("H2", 5, True, "51/10", 92.81899074074074, 90.80463888888889, 88.75),
    ("H3", 1, False, "245951/1733020", 26.916159074909697, 26.883744465399086, 26.774005781814406),
    ("H3", 5, False, "1109951/1733020", 33.91905575238601, 33.501140687023764, 33.00590154758745),
    ("H3", 10, False, "2189951/1733020", 42.6726765992314, 41.772885964054616, 40.79577125480375),
    ("H3", 5, True, "51/10", 96.55973148148148, 92.69352777777777, 88.75),
)


def reference_rows_check():
    """AC1: exact front-flux equality and |dT| <= 1e-9 K for Coda's 12 rows."""
    rows = []
    for stack, P, blocked, front_exact, H, S, surf in CODA_REFERENCE_ROWS:
        s = steady(make_params(stack, P=P, r=None if blocked else NOMINAL_EXOGENOUS["r"]))
        row = {"stack": stack, "P": P, "rear_blocked": blocked,
               "front_exact_equal": s["F"] == Fraction(front_exact),
               "front_exact": str(s["F"]),
               "dH": abs(float(s["T_H"]) - H), "dS": abs(float(s["T_S"]) - S),
               "dsurface": abs(float(s["T_surface"]) - surf)}
        row["passed"] = row["front_exact_equal"] and max(row["dH"], row["dS"], row["dsurface"]) <= 1e-9
        rows.append(row)
    return rows
```

FILE: validation/thermal_sensitivity/sampling.py
```python
"""Standard-library Morris elementary-effects screening and Saltelli/Jansen Sobol estimators
(thermal-sensitivity-001). Author: Claude (Anthropic); executed by Red.

Conventions: factors live on the unit cube and are mapped linearly onto declared study domains
(uniform measure as a description convention, not a belief distribution). Morris effects are per
unit of normalized factor range. Seeds are derived from strings through SHA-256 so results do not
depend on hash randomization. Evaluation functions receive a dict {factor name: value} and return
a dict {output name: float}.
"""
import hashlib
import math
import random


def derive_seed(*parts):
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng_for(*parts):
    return random.Random(derive_seed(*parts))


def mean(values):
    return math.fsum(values) / len(values) if values else 0.0


def sample_sd(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(math.fsum((v - m) ** 2 for v in values) / (len(values) - 1))


def latin_hypercube(n, k, rng):
    """n points in k dimensions; each column has exactly one point per stratum [i/n, (i+1)/n)."""
    columns = []
    for _ in range(k):
        perm = list(range(n))
        rng.shuffle(perm)
        columns.append([(perm[i] + rng.random()) / n for i in range(n)])
    return [[columns[j][i] for j in range(k)] for i in range(n)]


def design_digest(points):
    text = "\n".join(",".join(repr(float(v)) for v in pt) for pt in points)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scale(point, factors):
    """Map a unit-cube point onto factors = [(name, lo, hi), ...]."""
    return {name: lo + (hi - lo) * u for u, (name, lo, hi) in zip(point, factors)}


def _clamp(v):
    return min(1.0, max(0.0, v))


def morris_delta(p):
    return p / (2.0 * (p - 1))


def morris_trajectories(k, r, p, rng):
    """r trajectories on a p-level grid (p even). Each: {'points': [k+1 points], 'moves': [(i, step)]}."""
    if p < 2 or p % 2:
        raise ValueError("Morris level count p must be even and >= 2")
    delta = morris_delta(p)
    base_levels = [i / (p - 1) for i in range(p // 2)]
    trajectories = []
    for _ in range(r):
        base = [rng.choice(base_levels) for _ in range(k)]
        signs = [rng.choice((1, -1)) for _ in range(k)]
        x = [_clamp(base[i] if signs[i] > 0 else base[i] + delta) for i in range(k)]
        order = list(range(k))
        rng.shuffle(order)
        points, moves = [list(x)], []
        for i in order:
            x = list(x)
            x[i] = _clamp(x[i] + signs[i] * delta)
            points.append(x)
            moves.append((i, signs[i] * delta))
        trajectories.append({"points": points, "moves": moves})
    return trajectories


def morris_points(trajectories):
    return [pt for tr in trajectories for pt in tr["points"]]


def morris_effects(trajectories, values, output_names, k):
    """values: list of output dicts aligned with morris_points(trajectories)."""
    effects = {name: [[] for _ in range(k)] for name in output_names}
    index = 0
    for tr in trajectories:
        n = len(tr["points"])
        vals = values[index:index + n]
        index += n
        for j, (i, step) in enumerate(tr["moves"]):
            for name in output_names:
                effects[name][i].append((vals[j + 1][name] - vals[j][name]) / step)
    result = {}
    for name in output_names:
        result[name] = []
        for i in range(k):
            e = effects[name][i]
            result[name].append({"mu": mean(e), "mu_star": mean([abs(v) for v in e]),
                                 "sigma": sample_sd(e), "count": len(e)})
    return result


def sobol_points(k, n, rng):
    """Saltelli design: A (n), B (n), then AB_i (n each, column i of A replaced by B's)."""
    A = latin_hypercube(n, k, rng)
    B = latin_hypercube(n, k, rng)
    points = [list(x) for x in A] + [list(x) for x in B]
    for i in range(k):
        for row in range(n):
            x = list(A[row])
            x[i] = B[row][i]
            points.append(x)
    return points


def sobol_indices(k, n, values, output_names):
    """S_i (Saltelli 2010) and S_Ti (Jansen 1999) with pooled centring and pooled variance."""
    result = {}
    for name in output_names:
        fA = [values[r][name] for r in range(n)]
        fB = [values[n + r][name] for r in range(n)]
        m = mean(fA + fB)
        fA = [v - m for v in fA]
        fB = [v - m for v in fB]
        V = mean([v * v for v in fA + fB])
        S, ST = [], []
        for i in range(k):
            fAB = [values[(2 + i) * n + r][name] - m for r in range(n)]
            if V <= 0.0:
                S.append(None)
                ST.append(None)
                continue
            S.append(mean([fB[r] * (fAB[r] - fA[r]) for r in range(n)]) / V)
            ST.append(mean([(fA[r] - fAB[r]) ** 2 for r in range(n)]) / (2.0 * V))
        result[name] = {"S": S, "ST": ST, "variance": V, "mean": m}
    return result


def run_morris(factors, evaluate, seed_parts, r, p):
    k = len(factors)
    names = [f[0] for f in factors]
    trajectories = morris_trajectories(k, r, p, rng_for(*seed_parts, "morris"))
    points = morris_points(trajectories)
    values = [evaluate(scale(pt, factors)) for pt in points]
    outputs = sorted(values[0])
    effects = morris_effects(trajectories, values, outputs, k)
    ranking = {}
    for name in outputs:
        order = sorted(range(k), key=lambda i: (-effects[name][i]["mu_star"], i))
        total = math.fsum(effects[name][i]["mu_star"] for i in range(k))
        ranking[name] = [{"factor": names[i], "mu_star": effects[name][i]["mu_star"],
                          "share": (effects[name][i]["mu_star"] / total) if total > 0 else None}
                         for i in order]
    return {"r": r, "p": p, "delta": morris_delta(p), "evaluations": len(points),
            "design_sha256": design_digest(points), "factors": names,
            "effects": {name: dict(zip(names, effects[name])) for name in outputs},
            "ranking_by_mu_star": ranking}


def run_sobol(factors, evaluate, seed_parts, n):
    k = len(factors)
    names = [f[0] for f in factors]
    points = sobol_points(k, n, rng_for(*seed_parts, "sobol"))
    values = [evaluate(scale(pt, factors)) for pt in points]
    outputs = sorted(values[0])
    indices = sobol_indices(k, n, values, outputs)
    sanity = {}
    for name in outputs:
        S, ST = indices[name]["S"], indices[name]["ST"]
        if S[0] is None:
            sanity[name] = {"constant_output": True}
            continue
        sanity[name] = {"min_S": min(S), "sum_S": math.fsum(S),
                        "min_ST_minus_S": min(st - s for s, st in zip(S, ST))}
    return {"N": n, "evaluations": len(points), "design_sha256": design_digest(points),
            "factors": names, "indices": {name: {"S": dict(zip(names, indices[name]["S"])),
                                                 "ST": dict(zip(names, indices[name]["ST"])),
                                                 "variance": indices[name]["variance"],
                                                 "mean": indices[name]["mean"]}
                                          for name in outputs},
            "sanity": sanity}
```

FILE: validation/thermal_sensitivity/transient_wrapper.py
```python
"""Thin wrapper that CALLS Coda's T0-LUMP2-1 two-node model (validation/thermal_transient/rc_transient.py)
for thermal-sensitivity-001. It does not reimplement the integrator. Author: Claude (Anthropic).

Capacity convention copied from Coda's PREDECLARED.md: C_H = 20 J/K; C_S = silicone rho 1030 * A *
(t_o + t_i) * cp 1500 + film rho 1420 * A * t_f * cp 1090 (assumed properties, fixed; not in any
sensitivity domain). Front surface is Coda's quasi-steady reconstruction T_amb + Rconv * q_front.
"""
import importlib.util
import os
from pathlib import Path

C_H_J_PER_K = 20.0
SILICONE_RHO_CP = 1030.0 * 1500.0
FILM_RHO_CP = 1420.0 * 1090.0
SCENARIOS = ("intact_sensor_on", "rear_loss_sensor_on", "rear_blocked_from_start")


def locate_rc_transient(path=None):
    candidates = []
    if path:
        candidates.append(Path(path))
    env = os.environ.get("THERMAL_TRANSIENT_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "thermal_transient" / "rc_transient.py")
    candidates.append(here / "rc_transient.py")
    for cand in candidates:
        cand = cand / "rc_transient.py" if cand.is_dir() else cand
        if cand.is_file():
            return cand
    raise FileNotFoundError("rc_transient.py not found; set THERMAL_TRANSIENT_DIR")


def load_rc_transient(path=None):
    """Return (module, file path). The module is Coda's code, imported unchanged."""
    file = locate_rc_transient(path)
    spec = importlib.util.spec_from_file_location("coda_rc_transient", str(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, file


def cover_capacity(p):
    return SILICONE_RHO_CP * p["A"] * (p["t_o"] + p["t_i"]) + FILM_RHO_CP * p["A"] * p["t_f"]


def lump_parameters(rc, p):
    """rc.Parameters from a float parameter dict of steady_closed_form.make_params."""
    A = p["A"]
    half_film = p["t_f"] / (2 * p["k_f"] * A)
    contact = p["r_c"] / A
    a = p["t_i"] / (p["k_s"] * A) + half_film + contact
    c = 1 / (p["h"] * A)
    b = p["t_o"] / (p["k_s"] * A) + half_film + contact + c
    gr = 0.0 if p["r"] is None else 1.0 / float(p["r"])
    return rc.Parameters(ch=C_H_J_PER_K, cs=float(cover_capacity(p)), g=1.0 / a, ga=1.0 / b, gr=gr,
                         ambient=float(p["T_amb"]), reservoir=float(p["T_res"]), rconv=c)


def scenario_segments(name, body_power, sensor_power=0.1, horizon=1800.0, body_off=900.0, loss=600.0):
    """Segment lists for rc.simulate. Rear-loss schedule is Coda's fault suite: body on until body_off,
    sensor on throughout, rear conductance set to exactly zero at `loss`."""
    P, J = float(body_power), float(sensor_power)
    if not loss < body_off < horizon:
        raise ValueError("Require loss < body_off < horizon")
    if name == "intact_sensor_on":
        return [{"duration": body_off, "p": P, "j": J},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    if name == "rear_loss_sensor_on":
        return [{"duration": loss, "p": P, "j": J},
                {"duration": body_off - loss, "p": P, "j": J, "gr": 0.0},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    if name == "rear_blocked_from_start":
        return [{"duration": body_off, "p": P, "j": J, "gr": 0.0},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    raise ValueError("Unknown scenario " + repr(name))


def run_case(rc, params, segments, dt, initial=(25.0, 25.0)):
    """Call rc.simulate and reduce the trace to peaks, endpoint and energy audit."""
    result = rc.simulate(params, tuple(initial), segments, dt)
    peak_H = t_H = peak_s = t_s = None
    for row in result["trace"]:
        if peak_H is None or row["H"] > peak_H:
            peak_H, t_H = row["H"], row["time"]
        s = row["surface"]
        if s is not None and (peak_s is None or s > peak_s):
            peak_s, t_s = s, row["time"]
    last = result["trace"][-1]
    return {"peak_H": peak_H, "t_peak_H": t_H, "peak_surface": peak_s, "t_peak_surface": t_s,
            "final_H": last["H"], "final_S": last["S"], "final_surface": last["surface"],
            "final_time": last["time"], "steps": result["steps"],
            "injected_J": result["injected_J"], "exported_front_J": result["exported_front_J"],
            "exported_rear_J": result["exported_rear_J"],
            "max_energy_residual_abs_J": result["max_energy_residual_abs_J"],
            "energy_tolerance_J": result["energy_tolerance_J"],
            "energy_ok": result["max_energy_residual_abs_J"] <= result["energy_tolerance_J"]}
```

FILE: validation/thermal_sensitivity/thermal_sensitivity.py
```python
#!/usr/bin/env python3
"""thermal-sensitivity-001 driver: which T0-HYP-1 assumptions control the surface/internal ranking
reversal and the steady/transient temperatures. Author: Claude (Anthropic), coordinated by Red;
Coda's (Codex Lily, with Andrei) steady reference and two-node transient are read-only inputs.
Standard library only; deterministic; writes only to --output. Not physical validation.

Usage:
  python thermal_sensitivity.py --output sensitivity_results.json
  options: --seed --morris-r --sobol-n --transient-morris-r --transient-n --grid-stride
           --skip-transient --skip-grid   (any change from defaults is recorded as a deviation)
"""
import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import steady_closed_form as scf  # noqa: E402
import sampling as smp  # noqa: E402
import transient_wrapper as tw  # noqa: E402

TASK = "thermal-sensitivity-001"
DEFAULTS = {"seed": 20261101, "morris_r": 20, "morris_p": 4, "sobol_n": 2048,
            "transient_morris_r": 10, "transient_sobol_n": 64, "transient_dt": 1.0,
            "transient_horizon": 1800.0, "transient_P": 5, "grid_stride": 1,
            "skip_transient": False, "skip_grid": False}
P_LEVELS = (1, 5, 10)
MODES = ("common_bias", "independent_layers")
BASE_FACTORS = [("k_s", 0.18, 0.35), ("k_f", 0.12, 0.25), ("r_c", 0.0, 2.0e-3),
                ("h", 3.0, 15.0), ("R_rej", 1.0, 10.0)]
FACTOR_DOMAINS = {
    "common_bias": BASE_FACTORS + [("delta_all", -0.1, 0.1)],
    "independent_layers": BASE_FACTORS + [("delta_outer", -0.1, 0.1), ("delta_film", -0.1, 0.1),
                                          ("delta_inner", -0.1, 0.1)],
}
GRIDS = {
    "common_bias": [("k_s", ["0.18", "0.265", "0.35"]), ("k_f", ["0.12", "0.185", "0.25"]),
                    ("r_c", ["0", "0.001", "0.002"]),
                    ("h", ["3", "3.5", "4", "4.5", "5", "6", "8", "10", "12", "15"]),
                    ("R_rej", ["1", "1.1", "1.2", "1.3", "1.5", "2", "3", "5", "7", "10"]),
                    ("delta_all", ["-0.1", "0", "0.1"])],
    "independent_layers": [("k_s", ["0.18", "0.35"]), ("k_f", ["0.12", "0.25"]),
                           ("r_c", ["0", "0.002"]), ("h", ["3", "3.5", "4", "4.5", "5", "8", "15"]),
                           ("R_rej", ["1", "1.2", "1.5", "2", "5", "10"]),
                           ("delta_outer", ["-0.1", "0", "0.1"]), ("delta_film", ["-0.1", "0", "0.1"]),
                           ("delta_inner", ["-0.1", "0", "0.1"])],
}
P1_FLIPPED_CELLS = sorted(["3,1", "3,1.1", "3,1.2", "3,1.3", "3,1.5", "3.5,1", "3.5,1.1", "3.5,1.2",
                           "3.5,1.3", "4,1", "4,1.1", "4.5,1"])
DECLARED_HASHES = {
    "thermal/thermal_reference.py": "7032eb2cdb7677c3f29401865d3f5f1f185c826d5f8395e5ec263ea15d642c56d",
    "thermal/reference_results.json": "e97cf35c8accb051096fdca20ec89a0a157015b863e94cb01020a8fdb5af3a56",
    "thermal_transient/rc_transient.py": "94ff435da55d2bccef769197d534e735e5813612a3275a829f703f05b5db6e0b",
}
# Coda's executed fault-suite peaks (validation/thermal_transient/REPORT.md): peak H (time), peak surface (time).
CODA_TRANSIENT_PEAKS = {
    ("H1", "intact_sensor_on"): (33.831193, 900, 33.554994, 900),
    ("H1", "rear_loss_sensor_on"): (61.143480, 900, 59.747155, 901),
    ("H2", "intact_sensor_on"): (33.861287, 900, 33.362444, 900),
    ("H2", "rear_loss_sensor_on"): (55.545063, 900, 53.153638, 904),
    ("H3", "intact_sensor_on"): (33.884652, 900, 32.963939, 900),
    ("H3", "rear_loss_sensor_on"): (50.169875, 900, 45.881263, 914),
}
LATE_PEAK_MARGIN_S = 300.0


def jsonable(o):
    if isinstance(o, Fraction):
        return str(o)
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, set):
        return sorted(jsonable(v) for v in o)
    return o


def accept(acceptance, ident, passed, detail):
    acceptance.append({"id": ident, "passed": bool(passed), "detail": detail})


def check_input_hashes(deviations):
    out = {}
    for rel, declared in DECLARED_HASHES.items():
        path = HERE.parent / rel
        entry = {"path": str(path), "declared_sha256": declared, "found": path.is_file()}
        if path.is_file():
            entry["observed_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["match"] = entry["observed_sha256"] == declared
            if not entry["match"]:
                deviations.append("hash mismatch for " + rel)
        else:
            deviations.append("input file not found: " + rel)
        out[rel] = entry
    return out


def params_from_named(stack, mode, named, P, exact_arithmetic):
    deltas = {k: v for k, v in named.items() if k.startswith("delta_")}
    r = named.get("R_rej")
    return scf.make_params(stack, mode, deltas, exact_arithmetic, k_s=named["k_s"], k_f=named["k_f"],
                           r_c=named["r_c"], h=named["h"], r=r, P=P)


def steady_outputs(named, P, mode):
    out = {}
    for stack in scf.STACKS:
        s = scf.steady(params_from_named(stack, mode, named, P, False))
        out["T_surface_" + stack] = s["T_surface"]
        out["T_H_" + stack] = s["T_H"]
    out["gap_surface_H1_H3"] = out["T_surface_H1"] - out["T_surface_H3"]
    out["gap_H_H1_H3"] = out["T_H_H1"] - out["T_H_H3"]
    return out


def reference_section(acceptance):
    rows = scf.reference_rows_check()
    accept(acceptance, "AC1", all(r["passed"] for r in rows),
           "closed form vs Coda's 12 reference rows (exact front flux, |dT| <= 1e-9 K)")
    return rows


def nominal_tables(acceptance):
    closed, partial_rows = [], []
    all_equal = True
    for stack in scf.STACKS:
        for P in P_LEVELS:
            for blocked in (False, True):
                p = scf.make_params(stack, P=P, r=None if blocked else scf.NOMINAL_EXOGENOUS["r"])
                s = scf.steady(p)
                closed.append({"stack": stack, "P": P, "rear_blocked": blocked,
                               **{k: {"exact": str(s[k]), "float": float(s[k])}
                                  for k in ("a", "b", "c", "F", "B", "T_surface", "T_S", "T_H")},
                               "margin_surface_40C_study_comparator_only": 40.0 - float(s["T_surface"]),
                               "margin_internal_60C_study_comparator_only": 60.0 - float(s["T_H"])})
                for x in scf.FACTOR_NAMES:
                    if blocked and x == "r":
                        continue
                    hand = scf.partials(p, x)
                    dual = scf.partials_by_dual(p, x)
                    equal = all(hand[k] == dual[k] for k in scf.OUTPUT_KEYS)
                    all_equal = all_equal and equal
                    partial_rows.append({"stack": stack, "P": P, "rear_blocked": blocked, "factor": x,
                                         "dual_equal": equal,
                                         **{"d" + k: {"exact": str(hand[k]), "float": float(hand[k])}
                                            for k in scf.OUTPUT_KEYS}})
    accept(acceptance, "AC2", all_equal, "hand partials == exact dual-number partials for 18 nominal cases")
    return closed, partial_rows


def analytic_condition():
    out = {"statement": "T_surface(X)-T_surface(Y) = c (F_X-F_Y); T_H(X)-T_H(Y) = -R_rej (F_X-F_Y); "
                        "symmetric discriminant (a_Y-a_X)[R_rej(2P+J) - J/(hA) + 2(T_res-T_amb)]",
           "per_P": {}}
    for P in P_LEVELS:
        kap = scf.kappa(P)
        brackets = {}
        for stack in scf.STACKS:
            s = scf.steady(scf.make_params(stack, P=P))
            brackets[stack] = str(scf.symmetric_bracket(s))
        out["per_P"][str(P)] = {
            "kappa_K_per_W_times_W_per_m2K": {"exact": str(kap), "float": float(kap)},
            "flip_condition": "R_rej < kappa/h (equal reservoirs)",
            "h_upper_bound_for_any_flip_in_domain": float(kap),
            "uniform_measure_flip_fraction_h3_15_R1_10": scf.uniform_flip_fraction(kap),
            "symmetric_bracket_at_nominal": brackets}
    return out


def method_self_checks(acceptance):
    lin = [("x1", 0.0, 1.0), ("x2", 0.0, 1.0), ("x3", 0.0, 1.0)]
    coeff = (2.0, -3.0, 0.5)
    morris = smp.run_morris(lin, lambda v: {"f": 1.0 + coeff[0] * v["x1"] + coeff[1] * v["x2"]
                                             + coeff[2] * v["x3"]}, ("selfcheck", "linear"), 8, 4)
    eff = morris["effects"]["f"]
    morris_ok = all(abs(eff[n]["mu"] - c) <= 1e-9 and eff[n]["sigma"] <= 1e-9
                    for n, c in zip(("x1", "x2", "x3"), coeff))
    sobol = smp.run_sobol(lin, lambda v: {"f": v["x1"] + 2.0 * v["x2"] * v["x3"]}, ("selfcheck", "sobol"), 4096)
    S, ST = sobol["indices"]["f"]["S"], sobol["indices"]["f"]["ST"]
    exact_S, exact_ST = (0.3, 0.3, 0.3), (0.3, 0.4, 0.4)
    sobol_ok = all(abs(S[n] - e) <= 0.05 for n, e in zip(("x1", "x2", "x3"), exact_S)) and \
        all(abs(ST[n] - e) <= 0.05 for n, e in zip(("x1", "x2", "x3"), exact_ST))
    accept(acceptance, "AC5", morris_ok and sobol_ok, "Morris linear exactness and Sobol test function N=4096")
    return {"morris_linear": {"coefficients": coeff, "effects": eff, "passed": morris_ok},
            "sobol_x1_plus_2x2x3": {"S": S, "ST": ST, "exact_S": exact_S, "exact_ST": exact_ST,
                                    "passed": sobol_ok}}


def classify_grid(mode, P, blocked=False, stride=1):
    """Exact classification of every (stride-th) grid point, brute force and analytic, all pairs."""
    grid = [(k, v) for k, v in GRIDS[mode] if not (blocked and k == "R_rej")]
    keys = [k for k, _ in grid]
    counts = Counter()
    cell_classes = {}
    checked = agree = pair_identical = 0
    for n, combo in enumerate(itertools.product(*[v for _, v in grid])):
        if n % stride:
            continue
        literal = dict(zip(keys, combo))
        named = {k: Fraction(v) for k, v in literal.items()}
        if blocked:
            named["R_rej"] = None
        states = {s: scf.steady(params_from_named(s, mode, named, Fraction(P), True)) for s in scf.STACKS}
        bf = {pair: scf.brute_force_class(states[pair[0]], states[pair[1]]) for pair in scf.PAIRS}
        an = {pair: scf.analytic_class(states[pair[0]], states[pair[1]]) for pair in scf.PAIRS}
        checked += 1
        agree += all(bf[pair] == an[pair] for pair in scf.PAIRS)
        pair_identical += len(set(bf.values())) == 1
        cls = bf[("H1", "H3")]
        counts[cls] += 1
        cell = literal["h"] + "," + (literal["R_rej"] if not blocked else "blocked")
        cell_classes.setdefault(cell, set()).add(cls)
    flipped_cells = sorted(c for c, s in cell_classes.items() if "flipped" in s)
    mixed_cells = sorted(c for c, s in cell_classes.items() if len(s) > 1)
    return {"mode": mode, "P": P, "rear_blocked": blocked, "stride": stride, "checked": checked,
            "counts_H1_vs_H3": dict(sorted(counts.items())), "flipped_cells_h_R": flipped_cells,
            "cells_with_mixed_classes": mixed_cells, "analytic_agreement": agree,
            "pair_pattern_identical": pair_identical,
            "cell_classes": {c: sorted(s) for c, s in sorted(cell_classes.items())}}


def grid_section(cfg, acceptance):
    stride = cfg["grid_stride"]
    results = []
    for mode in MODES:
        for P in P_LEVELS:
            results.append(classify_grid(mode, P, False, stride))
            results.append(classify_grid(mode, P, True, stride))
    finite = [g for g in results if not g["rear_blocked"]]
    blocked = [g for g in results if g["rear_blocked"]]
    total = sum(g["checked"] for g in results)
    accept(acceptance, "AC3", sum(g["counts_H1_vs_H3"].get("same_direction", 0) for g in results) == 0,
           "no same-direction ranking at any checked grid point (%d points)" % total)
    accept(acceptance, "AC4", all(g["analytic_agreement"] == g["checked"] for g in results),
           "analytic class equals brute-force class at every checked point, all three pairs")
    accept(acceptance, "AC4b", all(g["pair_pattern_identical"] == g["checked"] for g in results),
           "pairs (H1,H2),(H2,H3),(H1,H3) share the class at every checked point")
    common = [g for g in finite if g["mode"] == "common_bias"]
    p1_other = all(g["counts_H1_vs_H3"].get("flipped", 0) == 0 for g in common if g["P"] != 1)
    g1 = [g for g in common if g["P"] == 1][0]
    p1_cells = g1["flipped_cells_h_R"] == P1_FLIPPED_CELLS
    p1_constant = all(g1["cell_classes"][c] == ["flipped"] for c in g1["flipped_cells_h_R"])
    ties = sum(g["counts_H1_vs_H3"].get(k, 0) for g in finite for k in ("tie", "tie_surface", "tie_interior"))
    indep = [g for g in finite if g["mode"] == "independent_layers"]
    p3 = all(g["counts_H1_vs_H3"].get("flipped", 0) == 0 for g in indep if g["P"] != 1) and all(
        float(c.split(",")[0]) <= 5 and float(c.split(",")[1]) <= 1.5
        for g in indep if g["P"] == 1 for c in g["flipped_cells_h_R"])
    p4 = all(g["counts_H1_vs_H3"] == {"tie_surface": g["checked"]} for g in blocked)
    predictions = {
        "P1": {"passed": p1_other and p1_cells and p1_constant,
               "flipped_only_at_P1": p1_other, "cells_equal_predicted": p1_cells,
               "class_constant_in_flipped_cells": p1_constant, "observed_cells": g1["flipped_cells_h_R"],
               "predicted_cells": P1_FLIPPED_CELLS},
        "P2": {"passed": ties == 0, "ties_at_finite_R_rej": ties},
        "P3": {"passed": p3, "flipped_cells_P1": [g["flipped_cells_h_R"] for g in indep if g["P"] == 1][0]},
        "P4": {"passed": p4},
        "evaluated_on_full_grid": stride == 1,
    }
    return {"grids": results, "predictions": predictions,
            "note": "grid counts over-resolve the low-h/low-R_rej corner by design; they are not domain fractions"}


def screen(factors, evaluate, seed_parts, morris_r, morris_p, sobol_n):
    return {"morris": smp.run_morris(factors, evaluate, seed_parts, morris_r, morris_p),
            "sobol": smp.run_sobol(factors, evaluate, seed_parts, sobol_n)}


def sobol_sanity_ok(sobol, min_s, max_sum, min_gap):
    for name, s in sobol["sanity"].items():
        if s.get("constant_output"):
            continue
        if s["min_S"] < min_s or s["sum_S"] > max_sum or s["min_ST_minus_S"] < min_gap:
            return False
    return True


def steady_section(cfg, acceptance):
    out = {}
    sanity_ok = True
    for mode in MODES:
        for P in P_LEVELS:
            label = (cfg["seed"], "steady", mode, "P%d" % P)
            res = screen(FACTOR_DOMAINS[mode], lambda v, P=P, mode=mode: steady_outputs(v, P, mode),
                         label, cfg["morris_r"], cfg["morris_p"], cfg["sobol_n"])
            sanity_ok = sanity_ok and sobol_sanity_ok(res["sobol"], -0.05, 1.10, -0.05)
            out["%s|P%d" % (mode, P)] = res
    accept(acceptance, "AC10-steady", sanity_ok, "steady Sobol sanity bounds (min S>=-0.05, sum S<=1.10, ST>=S-0.05)")
    again = screen(FACTOR_DOMAINS["common_bias"], lambda v: steady_outputs(v, 5, "common_bias"),
                   (cfg["seed"], "steady", "common_bias", "P5"), cfg["morris_r"], cfg["morris_p"], cfg["sobol_n"])
    first = out["common_bias|P5"]
    repro = (again["morris"]["design_sha256"] == first["morris"]["design_sha256"]
             and again["sobol"]["design_sha256"] == first["sobol"]["design_sha256"]
             and json.dumps(jsonable(again), sort_keys=True) == json.dumps(jsonable(first), sort_keys=True))
    accept(acceptance, "AC6", repro, "regenerated steady common_bias P5 designs and indices identical")
    return out


def transient_section(cfg, acceptance, deviations):
    try:
        rc, rc_file = tw.load_rc_transient()
    except (FileNotFoundError, ImportError, AttributeError) as exc:
        deviations.append("transient section not run: " + str(exc))
        for ident in ("AC7", "AC8", "AC9", "AC10-transient"):
            accept(acceptance, ident, False, "not evaluated: rc_transient unavailable")
        return {"available": False, "error": str(exc)}
    horizon, dt = cfg["transient_horizon"], cfg["transient_dt"]
    audit = {"runs": 0, "energy_failures": 0, "late_peaks": 0, "late_peak_margin_s": LATE_PEAK_MARGIN_S}

    def audited(params, segments):
        res = tw.run_case(rc, params, segments, dt)
        audit["runs"] += 1
        audit["energy_failures"] += 0 if res["energy_ok"] else 1
        if max(res["t_peak_H"], res["t_peak_surface"]) > horizon - LATE_PEAK_MARGIN_S:
            audit["late_peaks"] += 1
        return res

    nominal = {}
    ac7 = True
    fields = ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv")
    for stack in scf.STACKS:
        ref = rc.nominal(stack)
        mine = tw.lump_parameters(rc, scf.make_params(stack, exact_arithmetic=False))
        dev = max(abs(getattr(mine, f) - getattr(ref, f)) / max(1.0, abs(getattr(ref, f))) for f in fields)
        ac7 = ac7 and dev <= 1e-12
        entry = {"parameter_max_relative_deviation_vs_rc_nominal": dev, "cases": {}}
        for case in ("intact_sensor_on", "rear_loss_sensor_on"):
            res = audited(mine, tw.scenario_segments(case, 5.0, horizon=horizon))
            cH, tH, cS, tS = CODA_TRANSIENT_PEAKS[(stack, case)]
            cmp_ = {"dpeak_H": abs(res["peak_H"] - cH), "dt_peak_H": abs(res["t_peak_H"] - tH),
                    "dpeak_surface": abs(res["peak_surface"] - cS), "dt_peak_surface": abs(res["t_peak_surface"] - tS)}
            ok = cmp_["dpeak_H"] <= 1e-5 and cmp_["dpeak_surface"] <= 1e-5 and \
                cmp_["dt_peak_H"] <= 1.0 and cmp_["dt_peak_surface"] <= 1.0
            ac7 = ac7 and ok
            entry["cases"][case] = {"result": res, "vs_coda_table": cmp_, "passed": ok}
        for P in P_LEVELS:
            res = audited(mine, tw.scenario_segments("rear_blocked_from_start", float(P), horizon=horizon))
            entry["cases"]["rear_blocked_from_start|P%d" % P] = {"result": res}
        nominal[stack] = entry
    accept(acceptance, "AC7", ac7, "wrapper reproduces rc_transient.nominal (1e-12) and Coda's six tabulated peaks (1e-5 K, 1 s)")

    P = cfg["transient_P"]

    def transient_outputs(named, mode):
        out = {}
        for stack in scf.STACKS:
            params = tw.lump_parameters(rc, params_from_named(stack, mode, named, P, False))
            res = audited(params, tw.scenario_segments("rear_loss_sensor_on", float(P), horizon=horizon))
            out["peak_H_" + stack] = res["peak_H"]
            out["peak_surface_" + stack] = res["peak_surface"]
        out["gap_peak_H_H1_H3"] = out["peak_H_H1"] - out["peak_H_H3"]
        out["gap_peak_surface_H1_H3"] = out["peak_surface_H1"] - out["peak_surface_H3"]
        return out

    screening = {}
    sanity_ok = True
    for mode in MODES:
        res = screen(FACTOR_DOMAINS[mode], lambda v, mode=mode: transient_outputs(v, mode),
                     (cfg["seed"], "transient", mode, "P%d" % P),
                     cfg["transient_morris_r"], cfg["morris_p"], cfg["transient_sobol_n"])
        sanity_ok = sanity_ok and sobol_sanity_ok(res["sobol"], -0.15, 1.30, -0.25)
        screening["%s|P%d|rear_loss_sensor_on" % (mode, P)] = res
    accept(acceptance, "AC8", audit["energy_failures"] == 0, "every transient run passes rc_transient's energy audit")
    accept(acceptance, "AC9", audit["late_peaks"] == 0, "every peak at least %.0f s before the horizon" % LATE_PEAK_MARGIN_S)
    accept(acceptance, "AC10-transient", sanity_ok, "transient Sobol sanity bounds (min S>=-0.15, sum S<=1.30, ST>=S-0.25)")
    return {"available": True, "rc_transient_file": str(rc_file), "model": "T0-LUMP2-1 (Coda), called",
            "dt_s": dt, "horizon_s": horizon, "audit": audit, "nominal": nominal, "screening": screening}


def run(config=None):
    cfg = dict(DEFAULTS)
    cfg.update(config or {})
    t0 = time.perf_counter()
    deviations, acceptance = [], []
    for k in DEFAULTS:
        if cfg[k] != DEFAULTS[k]:
            deviations.append("config %s=%r differs from predeclared default %r" % (k, cfg[k], DEFAULTS[k]))
    result = {"task": TASK, "status": "computed_synthetic_sensitivity_study", "physical_validation": False,
              "study_comparator_only": {"surface_C": 40, "internal_C": 60},
              "config": cfg, "sampling_convention": "uniform measure on declared study domains; not a belief distribution; no confidence intervals",
              "credits": "Coda (Codex Lily) with Andrei: steady reference and T0-LUMP2-1 transient (read-only inputs). "
                         "Claude (Anthropic): this analysis. Red: coordination and execution."}
    result["input_hashes"] = check_input_hashes(deviations)
    result["reference_check"] = reference_section(acceptance)
    result["closed_form_nominal"], result["partials_nominal"] = nominal_tables(acceptance)
    result["analytic_condition"] = analytic_condition()
    result["method_self_checks"] = method_self_checks(acceptance)
    if cfg["skip_grid"]:
        deviations.append("grid classification skipped")
    else:
        result["grid_classification"] = grid_section(cfg, acceptance)
    result["steady_screening"] = steady_section(cfg, acceptance)
    if cfg["skip_transient"]:
        deviations.append("transient section skipped")
    else:
        result["transient"] = transient_section(cfg, acceptance, deviations)
    result["acceptance"] = acceptance
    result["deviations"] = deviations
    result["claim_boundary"] = ("Synthetic two-node steady and lumped transient models with fixed nominal properties "
                                "and assumed convection; no spatial mesh, delamination, radiation, controller, contact "
                                "safety, biological viability or deployment claim; PF0 6/7 history unchanged.")
    result["timing_s"] = time.perf_counter() - t0
    return result


def summary(result):
    out = {"acceptance": {a["id"]: a["passed"] for a in result["acceptance"]},
           "deviations": result["deviations"], "timing_s": result.get("timing_s")}
    if "grid_classification" in result:
        out["predictions"] = {k: v["passed"] for k, v in result["grid_classification"]["predictions"].items()
                              if isinstance(v, dict)}
        out["flipped_counts"] = {"%s|P%d|%s" % (g["mode"], g["P"], "blocked" if g["rear_blocked"] else "finite"):
                                 g["counts_H1_vs_H3"].get("flipped", 0) for g in result["grid_classification"]["grids"]}
    key = "common_bias|P5"
    if key in result["steady_screening"]:
        out["steady_top_factor_by_mu_star"] = {
            name: rank[0]["factor"] for name, rank in result["steady_screening"][key]["morris"]["ranking_by_mu_star"].items()}
    tr = result.get("transient", {})
    if tr.get("available"):
        k2 = "common_bias|P%d|rear_loss_sensor_on" % result["config"]["transient_P"]
        out["transient_top_factor_by_mu_star"] = {
            name: rank[0]["factor"] for name, rank in tr["screening"][k2]["morris"]["ranking_by_mu_star"].items()}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default=None, help="JSON output path (only file written)")
    ap.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    ap.add_argument("--morris-r", type=int, default=DEFAULTS["morris_r"])
    ap.add_argument("--sobol-n", type=int, default=DEFAULTS["sobol_n"])
    ap.add_argument("--transient-morris-r", type=int, default=DEFAULTS["transient_morris_r"])
    ap.add_argument("--transient-n", type=int, default=DEFAULTS["transient_sobol_n"])
    ap.add_argument("--grid-stride", type=int, default=DEFAULTS["grid_stride"])
    ap.add_argument("--skip-transient", action="store_true")
    ap.add_argument("--skip-grid", action="store_true")
    args = ap.parse_args(argv)
    cfg = {"seed": args.seed, "morris_r": args.morris_r, "sobol_n": args.sobol_n,
           "transient_morris_r": args.transient_morris_r, "transient_sobol_n": args.transient_n,
           "grid_stride": args.grid_stride, "skip_transient": args.skip_transient, "skip_grid": args.skip_grid}
    result = run(cfg)
    if args.output:
        path = Path(args.output)
        if path.exists():
            raise SystemExit("Refusing to overwrite existing output " + str(path))
        path.write_text(json.dumps(jsonable(result), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(jsonable(summary(result)), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: validation/thermal_sensitivity/test_steady_closed_form.py
```python
"""Unit tests for steady_closed_form (thermal-sensitivity-001). Expected values come from Coda's
executed reference and predeclared fixtures, not from the functions under test."""
from fractions import Fraction
import itertools
import math
import unittest

import steady_closed_form as scf

F = Fraction


class ClosedFormTests(unittest.TestCase):
    def test_coda_resistance_fixtures_1_to_7(self):
        s = scf.steady_from_resistances(1, 1, 0, 1, 1, 0)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(2, 3), F(1, 3), F(1, 3), F(2, 3)))
        s = scf.steady_from_resistances(1, 1, 0, 1, 0, 1)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(1, 3), F(2, 3), F(2, 3), F(1, 3)))
        s = scf.steady_from_resistances(1, 1, 0, 1, 0, 0, T_amb=0, T_res=10)
        self.assertEqual((s["T_H"], s["T_S"], s["F"], s["B"]), (F(20, 3), F(10, 3), F(10, 3), F(-10, 3)))
        s = scf.steady_from_resistances(2, 2, 1, None, 1, 2, T_amb=10, T_res=0)  # rear absent, b=3 incl. c=1
        self.assertEqual((s["F"], s["T_S"], s["T_H"], s["T_surface"]), (3, 19, 21, 13))
        s = scf.steady_from_resistances(0, 1, 0, 1, 1, 0)
        self.assertEqual((s["T_H"], s["T_S"]), (F(1, 2), F(1, 2)))
        base = scf.steady_from_resistances(1, 1, 0, 1, 1, 0)
        shifted = scf.steady_from_resistances(1, 1, 0, 1, 1, 0, T_amb=37, T_res=37)
        for k in ("T_H", "T_S", "T_surface"):
            self.assertEqual(shifted[k] - base[k], 37)
        self.assertEqual((shifted["F"], shifted["B"]), (base["F"], base["B"]))

    def test_coda_fixture_8_and_9(self):
        p = scf.make_params("H1", P=5)
        s = scf.steady(p)
        self.assertEqual(s["a"], F(2351, 10800))
        self.assertEqual(s["b"], F(2351, 10800) + F(25, 2))
        self.assertEqual(s["F"], F(1103951, 1613020))
        sym = scf.partials(p, "t_i")["F"] + scf.partials(p, "t_o")["F"]  # = (dF/da + dF/db)/(k_s A)
        self.assertEqual(sym * p["k_s"] * p["A"] * s["D"] ** 2, F(-1895, 100))
        self.assertLess(sym, 0)

    def test_reference_rows_ac1(self):
        rows = scf.reference_rows_check()
        self.assertEqual(len(rows), 12)
        for row in rows:
            self.assertTrue(row["passed"], row)

    def test_internal_identity_T_H_equals_T_res_plus_rB(self):
        for stack in scf.STACKS:
            for P in (1, 5, 10):
                s = scf.steady(scf.make_params(stack, P=P, T_res=30, T_amb=20, h=F("4.5"), r=F(7, 3)))
                self.assertEqual(s["T_H"], s["T_res"] + s["r"] * s["B"])
                self.assertEqual(s["F"] + s["B"], s["P"] + s["J"])

    def test_partials_match_dual_exactly_ac2(self):
        for stack, P, blocked in itertools.product(scf.STACKS, (1, 5, 10), (False, True)):
            p = scf.make_params(stack, P=P, r=None if blocked else 2)
            for x in scf.FACTOR_NAMES:
                if blocked and x == "r":
                    with self.assertRaises(ValueError):
                        scf.partials(p, x)
                    continue
                hand, dual = scf.partials(p, x), scf.partials_by_dual(p, x)
                for k in scf.OUTPUT_KEYS:
                    self.assertEqual(hand[k], dual[k], (stack, P, blocked, x, k))

    def test_partials_match_central_differences(self):
        for stack, blocked in itertools.product(scf.STACKS, (False, True)):
            p = scf.make_params(stack, P=5, r=None if blocked else 2, T_res=27)
            for x in scf.FACTOR_NAMES:
                if blocked and x == "r":
                    continue
                hand, cd = scf.partials(p, x), scf.partials_by_central_difference(p, x)
                for k in scf.OUTPUT_KEYS:
                    self.assertLessEqual(abs(hand[k] - cd[k]), F(1, 10 ** 9) * (1 + abs(hand[k])), (stack, x, k))

    def test_translation_partials(self):
        p = scf.make_params("H2", P=5)
        for k in ("T_surface", "T_S", "T_H"):
            self.assertEqual(scf.partials(p, "T_amb")[k] + scf.partials(p, "T_res")[k], 1)
        pb = scf.make_params("H2", P=5, r=None)
        for k in ("T_surface", "T_S", "T_H"):
            self.assertEqual(scf.partials(pb, "T_amb")[k], 1)
            self.assertEqual(scf.partials(pb, "T_res")[k], 0)

    def test_nominal_reversal_direction(self):
        s1, s3 = (scf.steady(scf.make_params(s, P=5)) for s in ("H1", "H3"))
        self.assertEqual(scf.brute_force_class(s1, s3), "reference")
        self.assertEqual(scf.analytic_class(s1, s3), "reference")
        self.assertEqual(scf.discriminant(s1, s3), scf.symmetric_discriminant(s1, s3))
        self.assertEqual(s1["T_surface"] - s3["T_surface"], s1["c"] * (s1["F"] - s3["F"]))
        self.assertEqual(s1["T_H"] - s3["T_H"], -s1["r"] * (s1["F"] - s3["F"]))

    def test_flip_condition_kappa_and_examples(self):
        self.assertEqual(scf.kappa(1), F(100, 21))
        self.assertEqual(scf.kappa(5), F(100, 101))
        self.assertEqual(scf.kappa(10), F(100, 201))
        flipped = [scf.steady(scf.make_params(s, P=1, h=3, r=F(3, 2))) for s in ("H1", "H3")]
        self.assertEqual(scf.brute_force_class(*flipped), "flipped")
        self.assertEqual(scf.analytic_class(*flipped), "flipped")
        tie = [scf.steady(scf.make_params(s, P=1, h=3, r=F(100, 63))) for s in ("H1", "H3")]  # r = kappa/h exactly
        self.assertEqual(scf.brute_force_class(*tie), "tie")
        self.assertEqual(scf.analytic_class(*tie), "tie")
        blocked = [scf.steady(scf.make_params(s, P=5, r=None)) for s in ("H1", "H3")]
        self.assertEqual(scf.brute_force_class(*blocked), "tie_surface")
        self.assertEqual(scf.analytic_class(*blocked), "tie_surface")

    def test_reversal_condition_vs_brute_force_on_grid(self):
        import thermal_sensitivity as ts
        for mode in ts.MODES:
            for P in (1, 5, 10):
                for blocked in (False, True):
                    g = ts.classify_grid(mode, P, blocked, stride=7)
                    self.assertGreater(g["checked"], 50)
                    self.assertEqual(g["analytic_agreement"], g["checked"], g)
                    self.assertEqual(g["pair_pattern_identical"], g["checked"], g)
                    self.assertNotIn("same_direction", g["counts_H1_vs_H3"])
                    if blocked:
                        self.assertEqual(g["counts_H1_vs_H3"], {"tie_surface": g["checked"]})
                    else:
                        for k in ("tie", "tie_surface", "tie_interior"):
                            self.assertNotIn(k, g["counts_H1_vs_H3"])
                    if P != 1 and not blocked:
                        self.assertEqual(g["counts_H1_vs_H3"].get("flipped", 0), 0)

    def test_prediction_P1_full_grid(self):
        import thermal_sensitivity as ts
        g = ts.classify_grid("common_bias", 1, False, stride=1)
        self.assertEqual(g["flipped_cells_h_R"], ts.P1_FLIPPED_CELLS)
        self.assertEqual(g["cells_with_mixed_classes"], [])
        self.assertEqual(g["counts_H1_vs_H3"]["flipped"], 12 * 81)

    def test_uniform_flip_fraction(self):
        kap = float(scf.kappa(1))
        n = 200000
        hits = 0
        for i in range(n):  # deterministic midpoint check against the closed form
            h = 3 + 12 * (i % 500 + 0.5) / 500
            r = 1 + 9 * (i // 500 + 0.5) / 400
            hits += r < kap / h
        self.assertAlmostEqual(scf.uniform_flip_fraction(kap), hits / n, delta=5e-4)
        self.assertAlmostEqual(scf.uniform_flip_fraction(kap), 0.0041, delta=3e-4)
        self.assertEqual(scf.uniform_flip_fraction(scf.kappa(5)), 0.0)
        self.assertEqual(scf.uniform_flip_fraction(scf.kappa(10)), 0.0)

    def test_thickness_modes(self):
        self.assertEqual(scf.thicknesses("H3"), (F(1, 500), F(1, 20000), F(1, 500)))
        self.assertEqual(scf.thicknesses("H1", "common_bias", {"delta_all": F(1, 10)}),
                         (F(11, 20000), F(11, 200000), F(11, 20000)))
        t_o, t_f, t_i = scf.thicknesses("H2", "independent_layers",
                                        {"delta_outer": F(-1, 10), "delta_film": 0, "delta_inner": F(1, 10)})
        self.assertEqual((t_o, t_f, t_i), (F(9, 10000), F(1, 20000), F(11, 10000)))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            scf.make_params("H1", k_s=0)
        with self.assertRaises(ValueError):
            scf.make_params("H1", h=-1)
        with self.assertRaises(ValueError):
            scf.make_params("H1", r=0)
        with self.assertRaises(ValueError):
            scf.make_params("H1", P=-1)
        with self.assertRaises(ValueError):
            scf.make_params("H9")
        with self.assertRaises(ValueError):
            scf.make_params("H1", bogus=1)
        with self.assertRaises(ValueError):
            scf.partials(scf.make_params("H1"), "nope")
        self.assertIsNone(scf.make_params("H1", r=math.inf)["r"])


if __name__ == "__main__":
    unittest.main()
```

FILE: validation/thermal_sensitivity/test_sampling.py
```python
"""Unit tests for sampling.py (Morris and Sobol estimators)."""
import math
import unittest

import sampling as smp


class SamplingTests(unittest.TestCase):
    def test_seed_derivation_is_deterministic_and_distinct(self):
        self.assertEqual(smp.derive_seed(1, "a"), smp.derive_seed(1, "a"))
        self.assertNotEqual(smp.derive_seed(1, "a"), smp.derive_seed(1, "b"))
        self.assertEqual(smp.rng_for(7).random(), smp.rng_for(7).random())

    def test_latin_hypercube_stratification(self):
        n, k = 16, 3
        pts = smp.latin_hypercube(n, k, smp.rng_for("lhs"))
        self.assertEqual(len(pts), n)
        for j in range(k):
            strata = sorted(int(pt[j] * n) for pt in pts)
            self.assertEqual(strata, list(range(n)))
            self.assertTrue(all(0.0 <= pt[j] < 1.0 for pt in pts))

    def test_morris_trajectory_structure(self):
        k, r, p = 5, 6, 4
        trajs = smp.morris_trajectories(k, r, p, smp.rng_for("m"))
        delta = smp.morris_delta(p)
        for tr in trajs:
            self.assertEqual(len(tr["points"]), k + 1)
            self.assertEqual(sorted(i for i, _ in tr["moves"]), list(range(k)))
            for (i, step), before, after in zip(tr["moves"], tr["points"], tr["points"][1:]):
                self.assertAlmostEqual(after[i] - before[i], step, places=12)
                self.assertAlmostEqual(abs(step), delta, places=12)
                for j in range(k):
                    if j != i:
                        self.assertEqual(after[j], before[j])
                    self.assertTrue(0.0 <= after[j] <= 1.0)
        with self.assertRaises(ValueError):
            smp.morris_trajectories(2, 1, 3, smp.rng_for("odd"))

    def test_morris_linear_exact_ac5(self):
        factors = [("x1", 0.0, 1.0), ("x2", -2.0, 2.0), ("x3", 0.0, 1.0)]
        # per unit of normalized range: x1 coefficient 2, x2 coefficient -3*4 = -12, x3 0.5
        res = smp.run_morris(factors, lambda v: {"f": 1.0 + 2.0 * v["x1"] - 3.0 * v["x2"] + 0.5 * v["x3"]},
                             ("test", "linear"), 8, 4)
        eff = res["effects"]["f"]
        for name, c in (("x1", 2.0), ("x2", -12.0), ("x3", 0.5)):
            self.assertAlmostEqual(eff[name]["mu"], c, delta=1e-9)
            self.assertAlmostEqual(eff[name]["mu_star"], abs(c), delta=1e-9)
            self.assertLessEqual(eff[name]["sigma"], 1e-9)
            self.assertEqual(eff[name]["count"], 8)
        self.assertEqual([r["factor"] for r in res["ranking_by_mu_star"]["f"]], ["x2", "x1", "x3"])
        self.assertEqual(res["evaluations"], 8 * 4)

    def test_sobol_test_function_ac5(self):
        factors = [("x1", 0.0, 1.0), ("x2", 0.0, 1.0), ("x3", 0.0, 1.0)]
        res = smp.run_sobol(factors, lambda v: {"f": v["x1"] + 2.0 * v["x2"] * v["x3"]}, ("test", "sobol"), 4096)
        S, ST = res["indices"]["f"]["S"], res["indices"]["f"]["ST"]
        for name, s, st in (("x1", 0.3, 0.3), ("x2", 0.3, 0.4), ("x3", 0.3, 0.4)):
            self.assertAlmostEqual(S[name], s, delta=0.05)
            self.assertAlmostEqual(ST[name], st, delta=0.05)
        self.assertAlmostEqual(res["indices"]["f"]["variance"], 5.0 / 18.0, delta=0.01)
        self.assertEqual(res["evaluations"], 5 * 4096)

    def test_sobol_constant_output(self):
        res = smp.run_sobol([("x1", 0.0, 1.0)], lambda v: {"f": 3.0}, ("test", "const"), 16)
        self.assertIsNone(res["indices"]["f"]["S"]["x1"])
        self.assertTrue(res["sanity"]["f"]["constant_output"])

    def test_reproducibility_ac6(self):
        factors = [("a", 0.0, 1.0), ("b", 1.0, 3.0)]
        f = lambda v: {"g": math.sin(v["a"]) * v["b"]}  # noqa: E731
        m1, m2 = (smp.run_morris(factors, f, ("seed", "x"), 5, 4) for _ in range(2))
        s1, s2 = (smp.run_sobol(factors, f, ("seed", "x"), 32) for _ in range(2))
        self.assertEqual(m1, m2)
        self.assertEqual(s1, s2)
        self.assertNotEqual(m1["design_sha256"], smp.run_morris(factors, f, ("seed", "y"), 5, 4)["design_sha256"])
        self.assertNotEqual(s1["design_sha256"], smp.run_sobol(factors, f, ("seed", "y"), 32)["design_sha256"])


if __name__ == "__main__":
    unittest.main()
```

FILE: validation/thermal_sensitivity/test_thermal_sensitivity.py
```python
"""Driver-level tests: transient wrapper against Coda's rc_transient, energy audits, reproducibility."""
import json
import unittest

import steady_closed_form as scf
import thermal_sensitivity as ts
import transient_wrapper as tw

QUICK = {"morris_r": 2, "sobol_n": 8, "transient_morris_r": 1, "transient_sobol_n": 2, "grid_stride": 97}


class TransientWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.rc, cls.rc_file = tw.load_rc_transient()
        except FileNotFoundError as exc:
            raise unittest.SkipTest("rc_transient.py unavailable (deviation to report): %s" % exc)

    def test_lump_parameters_match_rc_nominal(self):
        for stack in scf.STACKS:
            ref = self.rc.nominal(stack)
            mine = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            for f in ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv"):
                self.assertAlmostEqual(getattr(mine, f), getattr(ref, f),
                                       delta=1e-12 * max(1.0, abs(getattr(ref, f))), msg=(stack, f))
        self.assertAlmostEqual(tw.lump_parameters(self.rc, scf.make_params("H1", exact_arithmetic=False)).cs, 16.2239, places=4)

    def test_blocked_rear_gives_zero_rear_conductance(self):
        mine = tw.lump_parameters(self.rc, scf.make_params("H2", exact_arithmetic=False, r=None))
        self.assertEqual(mine.gr, 0.0)

    def test_nominal_peaks_match_coda_table_ac7(self):
        for (stack, case), (cH, tH, cS, tS) in ts.CODA_TRANSIENT_PEAKS.items():
            params = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            res = tw.run_case(self.rc, params, tw.scenario_segments(case, 5.0, horizon=1800.0), 1.0)
            self.assertAlmostEqual(res["peak_H"], cH, delta=1e-5, msg=(stack, case))
            self.assertAlmostEqual(res["peak_surface"], cS, delta=1e-5, msg=(stack, case))
            self.assertLessEqual(abs(res["t_peak_H"] - tH), 1.0)
            self.assertLessEqual(abs(res["t_peak_surface"] - tS), 1.0)
            self.assertTrue(res["energy_ok"])
            self.assertLessEqual(max(res["t_peak_H"], res["t_peak_surface"]), 1800.0 - ts.LATE_PEAK_MARGIN_S)

    def test_steady_state_limit_of_transient_matches_closed_form(self):
        for stack in scf.STACKS:
            params = tw.lump_parameters(self.rc, scf.make_params(stack, exact_arithmetic=False))
            res = tw.run_case(self.rc, params, [{"duration": 10000.0, "p": 5.0, "j": 0.1}], 10.0)
            s = scf.steady(scf.make_params(stack, P=5))
            self.assertAlmostEqual(res["final_H"], float(s["T_H"]), delta=1e-9)
            self.assertAlmostEqual(res["final_S"], float(s["T_S"]), delta=1e-9)
            self.assertAlmostEqual(res["final_surface"], float(s["T_surface"]), delta=1e-9)

    def test_scenario_schedules(self):
        seg = tw.scenario_segments("rear_loss_sensor_on", 5, horizon=1800.0)
        self.assertEqual([s["duration"] for s in seg], [600.0, 300.0, 900.0])
        self.assertEqual(seg[1]["gr"], 0.0)
        self.assertEqual([s["p"] for s in seg], [5.0, 5.0, 0.0])
        self.assertEqual(tw.scenario_segments("rear_blocked_from_start", 1)[0]["gr"], 0.0)
        with self.assertRaises(ValueError):
            tw.scenario_segments("unknown", 5)


class DriverTests(unittest.TestCase):
    def test_quick_run_core_acceptance_and_reproducibility_ac6(self):
        first = ts.run(QUICK)
        second = ts.run(QUICK)
        for r in (first, second):
            r.pop("timing_s")
        self.assertEqual(json.dumps(ts.jsonable(first), sort_keys=True), json.dumps(ts.jsonable(second), sort_keys=True))
        status = {a["id"]: a["passed"] for a in first["acceptance"]}
        for ident in ("AC1", "AC2", "AC3", "AC4", "AC4b", "AC5", "AC6"):
            self.assertTrue(status[ident], (ident, first["acceptance"]))
        self.assertTrue(first["grid_classification"]["predictions"]["P4"]["passed"])
        self.assertTrue(first["grid_classification"]["predictions"]["P2"]["passed"])
        self.assertTrue(any("grid_stride" in d for d in first["deviations"]))
        self.assertEqual(len(first["closed_form_nominal"]), 18)
        self.assertEqual(first["analytic_condition"]["per_P"]["5"]["uniform_measure_flip_fraction_h3_15_R1_10"], 0.0)

    def test_summary_is_json_serialisable(self):
        result = ts.run(dict(QUICK, skip_transient=True))
        text = json.dumps(ts.jsonable(ts.summary(result)), sort_keys=True)
        self.assertIn("AC1", text)
        self.assertIn("transient section skipped", result["deviations"])


if __name__ == "__main__":
    unittest.main()
```

## Notes for execution and review (static, unexecuted)

- **Run order:** tests first (`python -m unittest discover -s validation/thermal_sensitivity -p "test_*.py"`), then the driver with `--output`. The driver refuses to overwrite an existing output file. Expected runtime (static estimate only): grid classification ≈ 15–30 s of exact `Fraction` arithmetic (≈ 51,000 grid points × 3 stacks), steady Sobol a few seconds, transient ≈ 3,950 `rc_transient.simulate` calls of 1,800 steps ≈ 1 minute. If the sandbox deadline is tighter, `--transient-n 32 --grid-stride 2` keeps everything else intact and is recorded as a deviation.
- **Fixed paths/assumptions:** `rc_transient.py` is located at `validation/thermal_transient/rc_transient.py` relative to the new directory (override with `THERMAL_TRANSIENT_DIR`); the hash check looks for Coda's three files relative to `validation/`. A missing file is a recorded deviation, not an error, except that the transient section and its tests are then skipped/marked failed.
- **Known static risks (please report observed behaviour):** (1) AC7 assumes Coda's fault-suite table was produced at dt = 1 s with the same schedule; the report implies it but does not state the dt — a mismatch would show as an AC7 failure at the 1e-5 K level and should be reported, not patched. (2) The Sobol self-check tolerance 0.05 at N = 4096 is a predeclared bound; the LHS estimate should land well inside it, but if it does not, that is a result. (3) Coda's fixture 5 (front branch absent) is not representable in this closed form (b finite by construction) and is intentionally not tested.
- **Left unimplemented (by scope, not by truncation):** stack-specific (non-shared) thickness deviations; radiation/Kelvin extensions; a capacity cap on the rear reservoir; any comparison with Fable's nodal formulation (not contained in the sources).
- **Credits:** Coda (Codex Lily) with Andrei (Richard Pemberton): exact steady reference, T0-LUMP2-1 transient model, predeclarations, executed reports — all used read-only, with `rc_transient.simulate`/`nominal` called rather than reimplemented. Earlier Claude Fable 5.1 contributions are referenced in the sources but not contained in them. The earlier Claude instance: predeclaration and the analytic derivation; this instance: the remaining code and tests. Red: coordination and execution.