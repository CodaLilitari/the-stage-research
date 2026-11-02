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
