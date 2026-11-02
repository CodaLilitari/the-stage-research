"""Two-node plant for the supervisory study.

Algebra reproduced from Coda's executed rc_transient.py (T0-LUMP2-1, Codex Lily) so that a
controller can be placed inside the time loop; this file is not a replacement for Coda's
module and test_supervisor.py cross-checks against it when RC_TRANSIENT_PATH is set.
  C_H H' = P - g (H - S) - gr (H - T_res)
  C_S S' = J + g (H - S) - ga (S - T_amb)
  surface = T_amb + Rconv * ga * (S - T_amb)   (quasi-steady algebraic reconstruction)
Model study only; no physical validation is implied.
"""
from dataclasses import dataclass, replace
import math

AREA_M2 = 0.01
FILM_THICKNESS_M = 0.00005
SILICONE_DENSITY = 1030.0
FILM_DENSITY = 1420.0
FILM_CP = 1090.0
THICKNESS_M = {"H1": 0.0005, "H2": 0.001, "H3": 0.002}
P_MAX_W = 10.0
J_MAX_W = 0.2
NOMINAL_PROPERTIES = dict(k_sil=0.27, k_film=0.20, r_c=0.0002, h=8.0, r_rej=2.0, c_h=20.0, cp_sil=1500.0)


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be a finite non-Boolean number")
    return float(value)


@dataclass(frozen=True)
class Params:
    ch: float
    cs: float
    g: float
    ga: float
    gr: float
    ambient: float
    reservoir: float
    rconv: float

    def __post_init__(self):
        for name in ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if self.ch <= 0 or self.cs <= 0:
            raise ValueError("Capacities must be positive")
        if min(self.g, self.ga, self.gr, self.rconv) < 0:
            raise ValueError("Negative passive parameter")


def build(stack, k_sil=0.27, k_film=0.20, r_c=0.0002, h=8.0, r_rej=2.0, c_h=20.0, cp_sil=1500.0,
          ambient=25.0, reservoir=25.0):
    """Stack parameters; with defaults this is bit-for-bit Coda's nominal()."""
    if stack not in THICKNESS_M:
        raise ValueError("Unknown reference stack")
    thick = THICKNESS_M[stack]
    area = AREA_M2
    a = thick / (k_sil * area) + FILM_THICKNESS_M / (2 * k_film * area) + r_c / area
    c = 1 / (h * area)
    cs = SILICONE_DENSITY * area * (2 * thick) * cp_sil + FILM_DENSITY * area * FILM_THICKNESS_M * FILM_CP
    gr = 0.0 if r_rej == math.inf else 1 / r_rej
    return Params(ch=c_h, cs=cs, g=1 / a, ga=1 / (a + c), gr=gr, ambient=ambient, reservoir=reservoir, rconv=c)


def nominal(stack):
    return build(stack)


def step(p, H, S, P, J, dt):
    """One backward-Euler step; same algebra as rc_transient.simulate (Coda)."""
    A = p.ch / dt + p.gr
    B = p.cs / dt + p.ga
    determinant = A * B + p.g * (A + B)
    bh = p.ch * H / dt + P + p.gr * p.reservoir
    bs = p.cs * S / dt + J + p.ga * p.ambient
    new_H = (bh * (B + p.g) + p.g * bs) / determinant
    new_S = (bs * (A + p.g) + p.g * bh) / determinant
    if not (math.isfinite(new_H) and math.isfinite(new_S)):
        raise ValueError("Nonfinite numerical state")
    return new_H, new_S


def surface(p, S):
    front = p.ga * (S - p.ambient)
    return p.ambient + p.rconv * front


def steady_state(p, P, J):
    """Exact linear steady state (H, S); raises if both exits are blocked."""
    a11 = p.g + p.gr
    a12 = -p.g
    a21 = -p.g
    a22 = p.g + p.ga
    b1 = P + p.gr * p.reservoir
    b2 = J + p.ga * p.ambient
    det = a11 * a22 - a12 * a21
    if det <= 0:
        raise ValueError("No finite steady state: both environmental exits blocked")
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def blocked(p, fraction=0.0):
    return replace(p, gr=p.gr * fraction)
