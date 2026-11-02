"""release_model.py -- stable binary64 evaluation of the AB-LFR1 linear
finite-release model and of its difference from the algebraic equilibrium model.

Model (material transit time t [s], rates [1/s], equilibrated inlet):
    c' = -(alpha + k*gamma) c + k b,   b' = k*gamma c - k b,
    c(0) = c0,  b(0) = gamma*c0.         Release flux J = k (b - gamma c) = -b'.
Equilibrium model (separate algebraic model, never a finite k):
    c_eq = c0 exp(-alpha t/(1+gamma)), b_eq = gamma c_eq, J_eq = -b_eq'.

Formulas for r_f, r_s, Delta follow Lilitari's AB-LFR1 DERIVATION.md.  The
eigenmode amplitudes, cancellation-free model differences, slow-mode impostor
and endpoint leading-order forms were derived for The Stage task
release-observability-002b (Claude, Anthropic; coordination Red).  This module
does not import benchmark.py.  Standard library only.

Study restriction: alpha, k, gamma, c0 strictly positive (real, distinct
rates).  Zero/degenerate reference cases are out of scope here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Params:
    alpha: float
    k: float
    gamma: float
    c0: float

    def __post_init__(self) -> None:
        for name in ("alpha", "k", "gamma", "c0"):
            v = getattr(self, name)
            if (isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v) or v <= 0):
                raise ValueError(f"{name} must be a finite number > 0 (study restriction)")


@dataclass(frozen=True)
class Modes:
    r_s: float          # slow decay rate
    r_f: float          # fast decay rate
    delta: float        # r_f - r_s
    r_eq: float         # alpha/(1+gamma), equilibrium decay rate
    rate_shift: float   # r_eq - r_s > 0, cancellation-free
    A_c: float          # slow amplitude of c
    B_c: float          # fast amplitude of c
    A_b: float          # slow amplitude of b
    B_b: float          # fast amplitude of b (negative)
    kappa: float        # k/delta
    kappa_defect: float  # kappa*(1+gamma) - 1, cancellation-free


def modes(p: Params) -> Modes:
    a, k, g, c0 = float(p.alpha), float(p.k), float(p.gamma), float(p.c0)
    kg = k * g
    big_s = a + k + kg
    h = math.fsum([a, kg, -k])      # alpha + k*gamma - k
    h2 = math.fsum([k, kg, -a])     # k*(1+gamma) - alpha
    delta = math.hypot(h, 2.0 * k * math.sqrt(g))
    if not (math.isfinite(big_s) and math.isfinite(delta)):
        raise OverflowError("rates exceed binary64; rescale time")
    r_f = 0.5 * big_s + 0.5 * delta
    r_s = (a / r_f) * k                      # product formula r_s r_f = alpha k
    r_eq = a / (1.0 + g)
    # Delta^2 - h^2 = 4 k^2 gamma ; Delta^2 - h2^2 = 4 k gamma alpha
    h_plus_delta = (h + delta) if h >= 0.0 else (4.0 * k * k * g) / (delta - h)
    h2_plus_delta = (h2 + delta) if h2 >= 0.0 else (4.0 * kg * a) / (delta - h2)
    rate_shift = (2.0 * a * a * kg) / (h2_plus_delta * r_f * (1.0 + g))
    A_c = c0 * h2_plus_delta / (2.0 * delta)              # c0 (r_f - alpha)/Delta
    B_c = c0 * a * h_plus_delta / (2.0 * r_f * delta)     # c0 (alpha - r_s)/Delta
    A_b = g * c0 * r_f / delta
    B_b = -g * c0 * r_s / delta
    kappa = k / delta
    kappa_defect = (2.0 * k * a * (1.0 - g) - a * a) / (delta * (k * (1.0 + g) + delta))
    return Modes(r_s, r_f, delta, r_eq, rate_shift, A_c, B_c, A_b, B_b, kappa, kappa_defect)


def _m(p: Params, m: Optional[Modes]) -> Modes:
    return m if m is not None else modes(p)


def finite_state(p: Params, t: float, m: Optional[Modes] = None) -> Tuple[float, float]:
    m = _m(p, m)
    es, ef = math.exp(-m.r_s * t), math.exp(-m.r_f * t)
    return m.A_c * es + m.B_c * ef, m.A_b * es + m.B_b * ef


def finite_derivative(p: Params, t: float, m: Optional[Modes] = None) -> Tuple[float, float]:
    m = _m(p, m)
    es, ef = math.exp(-m.r_s * t), math.exp(-m.r_f * t)
    return (-(m.r_s * m.A_c * es + m.r_f * m.B_c * ef),
            -(m.r_s * m.A_b * es + m.r_f * m.B_b * ef))


def release_flux(p: Params, t: float, m: Optional[Modes] = None) -> float:
    """J = k(b - gamma c) = alpha gamma c0 (k/Delta)(e_s - e_f), cancellation-free."""
    m = _m(p, m)
    es = math.exp(-m.r_s * t)
    return p.alpha * p.gamma * p.c0 * m.kappa * es * (-math.expm1(-m.delta * t))


def flux_scale(alpha: float, gamma: float, c0: float) -> float:
    """Quasi-steady release-flux scale = equilibrium release flux at t=0."""
    return alpha * gamma * c0 / (1.0 + gamma)


def equilibrium_state(alpha: float, gamma: float, c0: float, t: float) -> Tuple[float, float]:
    c = c0 * math.exp(-alpha * t / (1.0 + gamma))
    return c, gamma * c


def equilibrium_flux(alpha: float, gamma: float, c0: float, t: float) -> float:
    return flux_scale(alpha, gamma, c0) * math.exp(-alpha * t / (1.0 + gamma))


def relative_differences(p: Params, t: float, m: Optional[Modes] = None) -> Tuple[float, float, float]:
    """(c-c_eq)/c0, (b-b_eq)/b0, (J-J_eq)/J_scale without catastrophic cancellation."""
    m = _m(p, m)
    es, ef = math.exp(-m.r_s * t), math.exp(-m.r_f * t)
    eeq = math.exp(-m.r_eq * t)
    g1 = math.expm1(m.rate_shift * t)             # (e_s - e_eq)/e_eq >= 0
    g2 = math.expm1(-(m.r_f - m.r_eq) * t)        # (e_f - e_eq)/e_eq <= 0
    dc = eeq * (m.A_c * g1 + m.B_c * g2) / p.c0
    db = eeq * (m.A_b * g1 + m.B_b * g2) / (p.gamma * p.c0)
    dJ = m.kappa_defect * es + eeq * g1 - m.kappa * (1.0 + p.gamma) * ef
    return dc, db, dJ


def fast_mode_relative(p: Params, t: float, m: Optional[Modes] = None) -> Tuple[float, float, float]:
    """Finite-k minus slow-mode impostor, relative units: exactly the fast modes."""
    m = _m(p, m)
    ef = math.exp(-m.r_f * t)
    return (m.B_c / p.c0 * ef, m.B_b / (p.gamma * p.c0) * ef, -m.kappa * (1.0 + p.gamma) * ef)


def impostor_params(p: Params, m: Optional[Modes] = None) -> Tuple[float, float, float]:
    """Equilibrium parameters (c0', gamma', alpha') reproducing the slow modes exactly."""
    m = _m(p, m)
    c0_i = m.A_c
    g_i = m.A_b / m.A_c
    a_i = m.r_s * (1.0 + g_i)
    return c0_i, g_i, a_i


def joint_gamma_known_impostor_relative(p: Params, t: float, m: Optional[Modes] = None) -> Tuple[float, float]:
    """Residual of the best slow-mode equilibrium fit with gamma calibrated.

    In relative units the equilibrium family at rate r_s is a*(e_s, e_s); the
    finite-k slow modes are (A_c/c0, A_b/b0) e_s.  Least squares gives a* = mean.
    The returned residual (including the fast modes) is an upper bound on the
    nuisance-minimized separation.
    """
    m = _m(p, m)
    es, ef = math.exp(-m.r_s * t), math.exp(-m.r_f * t)
    a_c = m.A_c / p.c0
    a_b = m.A_b / (p.gamma * p.c0)
    a_star = 0.5 * (a_c + a_b)
    return ((a_c - a_star) * es + m.B_c / p.c0 * ef,
            (a_b - a_star) * es + m.B_b / (p.gamma * p.c0) * ef)


def leading_order_endpoint(p: Params, T: float) -> Tuple[float, float, float]:
    """Large-k leading order of (dc/c0, db/b0, dJ/J_scale) at t=T >> 1/r_f."""
    a, k, g = p.alpha, p.k, p.gamma
    eeq = math.exp(-a * T / (1.0 + g))
    pref = a * eeq / (k * (1.0 + g) ** 2)
    x = a * g * T / (1.0 + g)
    return pref * g * (a * T / (1.0 + g) - 1.0), pref * (x + 1.0), pref * (x + 1.0 - g)


def blind_spot_times(p: Params) -> Tuple[float, Optional[float]]:
    """Transit times where the leading-order endpoint sensitivity of c (resp. J) vanishes."""
    a, g = p.alpha, p.gamma
    t_c = (1.0 + g) / a
    t_j = ((g - 1.0) * (1.0 + g) / (a * g)) if g > 1.0 else None
    return t_c, t_j
