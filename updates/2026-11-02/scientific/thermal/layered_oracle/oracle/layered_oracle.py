"""Semi-analytic oracle for the transient T0-HYP-1 layered stack (eigenfunction expansion).

Stack (outer to inner): outer silicone | film with sensor sheet at midplane | inner silicone |
lumped node H (capacity C_H, conductance G_rej to a reservoir). Convection h*A at the outer
face; areal contact resistances at both silicone|film interfaces.

Method: per piecewise-constant segment, T(x,t) = T_ss(x) + sum_n a_n exp(-lam_n (t-t0)) psi_n(x).
Modes via a transfer matrix; roots bracketed by the Dirichlet-at-H spectrum (Herglotz
interlacing, derivation A.5). Fix 003: the Dirichlet points are located with the EXACT lifted
Prufer phase (derivation A.9; no modular wrap-around), every root is cross-checked by its Sturm
index, an argument-principle zero count is available, the root-accuracy diagnostic is
conditioning-corrected (A.11) and the Weyl diagnostic carries its rigorous bracket (A.10).
NOT a time-stepping finite-volume code.

Standard library only; deterministic; no network; writes a file only when --out is given.
Contributors: Claude (Anthropic) for Red / Richard (Andrei) Pemberton, The Stage. Steady network
and reference values: Coda (Codex Lily), validation/thermal/thermal_reference.py. Earlier
packet work: Claude Fable 5.1. Private computational research on a model; no safety claim.
"""
from __future__ import annotations

import argparse
import cmath
import json
import math
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

PI = math.pi
LOCATIONS = ("surface", "sensor", "H")


@dataclass(frozen=True)
class Layer:
    thickness: float
    k: float
    rho: float
    cp: float

    @property
    def rc(self) -> float:
        return self.rho * self.cp

    @property
    def alpha(self) -> float:
        return self.k / (self.rho * self.cp)


@dataclass(frozen=True)
class Params:
    outer: Layer
    film: Layer
    inner: Layer
    area: float = 0.01
    r_outer: float = 2.0e-4   # m2 K/W, outer silicone | film
    r_inner: float = 2.0e-4   # m2 K/W, film | inner silicone
    h: float = 8.0            # W/(m2 K)
    G_rej: float = 0.5        # W/K (0.0 = blocked rear path)
    C_H: float = 20.0         # J/K
    T_amb: float = 25.0
    T_res: float = 25.0
    P_body: float = 5.0       # W at H
    P_sensor: float = 0.1     # W at film midplane


def _finite(name: str, v) -> None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number, got {v!r}")


def validate(p: Params) -> None:
    for lname, layer in (("outer", p.outer), ("film", p.film), ("inner", p.inner)):
        for fname in ("thickness", "k", "rho", "cp"):
            v = getattr(layer, fname)
            _finite(f"{lname}.{fname}", v)
            if v <= 0:
                raise ValueError(f"{lname}.{fname} must be positive")
    for name in ("area", "r_outer", "r_inner", "h", "G_rej", "C_H",
                 "T_amb", "T_res", "P_body", "P_sensor"):
        _finite(name, getattr(p, name))
    if p.area <= 0 or p.h <= 0:
        raise ValueError("area and h must be positive (h=0 would admit a zero eigenvalue)")
    for name in ("r_outer", "r_inner", "G_rej", "C_H", "P_body", "P_sensor"):
        if getattr(p, name) < 0:
            raise ValueError(f"{name} must be non-negative")


# ----------------------------------------------------------------------------- geometry
def segment_geometry(p: Params) -> Tuple[Tuple[float, float, float, float], ...]:
    """Four segments (ell, k, rho*cp, alpha): outer silicone, film outer half, film inner half,
    inner silicone. The sensor sheet sits between segments 1 and 2 (0-based)."""
    f = p.film
    return (
        (p.outer.thickness, p.outer.k, p.outer.rc, p.outer.alpha),
        (0.5 * f.thickness, f.k, f.rc, f.alpha),
        (0.5 * f.thickness, f.k, f.rc, f.alpha),
        (p.inner.thickness, p.inner.k, p.inner.rc, p.inner.alpha),
    )


def interface_resistances(p: Params) -> Tuple[float, float, float]:
    return (p.r_outer, 0.0, p.r_inner)


def _boundaries(geo) -> List[float]:
    xs = [0.0]
    for seg in geo:
        xs.append(xs[-1] + seg[0])
    return xs


def _locate(geo, x: float, side: int) -> Tuple[int, float]:
    xs = _boundaries(geo)
    L = xs[-1]
    tol = 1e-15 * max(1.0, L)
    if x < -tol or x > L + tol:
        raise ValueError("x outside the slab")
    for i in range(len(geo)):
        lo, hi = xs[i], xs[i + 1]
        if abs(x - hi) <= tol:
            if side < 0 or i == len(geo) - 1:
                return i, geo[i][0]
            return i + 1, 0.0
        if lo - tol <= x < hi:
            return i, max(0.0, x - lo)
    raise ValueError("x not located")


# ----------------------------------------------------------------------------- steady state
def steady_state(p: Params) -> dict:
    """Exact steady network of the contract (same algebra as Coda's heat-flow elimination)."""
    validate(p)
    A = p.area
    geo = segment_geometry(p)
    R_HS = (geo[3][0] / geo[3][1] + geo[2][0] / geo[2][1] + p.r_inner) / A
    R_SA = (geo[1][0] / geo[1][1] + geo[0][0] / geo[0][1] + p.r_outer) / A + 1.0 / (p.h * A)
    g1, g2, G = 1.0 / R_HS, 1.0 / R_SA, p.G_rej
    det = g1 * g2 + G * (g1 + g2)
    rhs1 = p.P_sensor + g2 * p.T_amb
    rhs2 = p.P_body + G * p.T_res
    S = (rhs1 * (g1 + G) + g1 * rhs2) / det
    TH = ((g1 + g2) * rhs2 + g1 * rhs1) / det
    front = g2 * (S - p.T_amb)        # W toward ambient
    Q_in = g1 * (TH - S)              # W from H toward the sheet
    rear = G * (TH - p.T_res)
    surface = p.T_amb + front / (p.h * A)
    q_outer, q_inner = -front / A, -Q_in / A   # flux density, +x toward H
    qs = (q_outer, q_outer, q_inner, q_inner)
    r = interface_resistances(p)
    segs = []
    x0, T = 0.0, surface
    for i, (ell, k, rc, alpha) in enumerate(geo):
        slope = -qs[i] / k
        segs.append({"x0": x0, "ell": ell, "T0": T, "slope": slope, "k": k, "rc": rc, "q": qs[i]})
        T = T + slope * ell
        x0 += ell
        if i < 3:
            T = T - r[i] * qs[i]       # T- - T+ = r q
    return {"surface": surface, "S": S, "H": TH, "H_from_profile": T, "front": front,
            "rear": rear, "Q_in": Q_in, "R_HS": R_HS, "R_SA": R_SA,
            "balance": p.P_body + p.P_sensor - front - rear, "segments": segs}


# ----------------------------------------------------------------------------- modes
@dataclass(frozen=True)
class Mode:
    lam: float
    seg: Tuple[Tuple[float, float, float], ...]   # (A, B, mu) per segment, psi = A cos + B sin
    psi_L: float
    norm: float      # <psi, psi>
    one: float       # <1, psi>
    psi_S: float     # value at the sensor midplane (psi(0) == 1 by normalisation)


@dataclass(frozen=True)
class ModeSet:
    geo: tuple
    ifaces: tuple
    area: float
    C_H: float
    h: float
    G_rej: float
    modes: Tuple[Mode, ...]
    diagnostics: dict


def _propagate(geo, ifaces, h: float, lam: float):
    """Transfer the normalised state (psi, q)(0) = (1, -h) to x = L. Returns (coeffs, psi_L, q_L);
    coeffs are (A, B, mu) per segment for lam > 0 (for lam == 0 the linear limit is used and
    coeffs carry (A, slope, 0.0) and must not be used as mode coefficients)."""
    psi, q = 1.0, -h
    coeffs = []
    for i, (ell, k, rc, alpha) in enumerate(geo):
        if lam > 0.0:
            mu = math.sqrt(lam / alpha)
            a, b = psi, -q / (k * mu)
            c, s = math.cos(mu * ell), math.sin(mu * ell)
            coeffs.append((a, b, mu))
            psi = a * c + b * s
            q = k * mu * (a * s - b * c)
        else:
            coeffs.append((psi, -q / k, 0.0))
            psi = psi - q * ell / k
        if i < len(ifaces):
            psi = psi - ifaces[i] * q
    return coeffs, psi, q


def characteristic(p: Params, lam: float) -> float:
    """F(lam) = A q(L) - (G - lam C_H) psi(L); eigenvalues are its (simple) zeros."""
    geo, ifaces = segment_geometry(p), interface_resistances(p)
    _c, psiL, qL = _propagate(geo, ifaces, p.h, lam)
    return p.area * qL - (p.G_rej - lam * p.C_H) * psiL


# ---- Fix 003: exact lifted Prufer phase (derivation A.9) ---------------------------------
def lifted_terminal_phase(geo, ifaces, h: float, lam: float) -> Tuple[float, float, float]:
    """Exact lifted Prufer angle Theta_L(lam) of the normalised solution at x = L (A.9).

    In segment i, with natural scale c_i = 1/(k_i mu_i), the angle atan2(c_i q, psi) advances
    by exactly mu_i*ell_i. A change of scale keeps sign(psi) and sign(q) (same quadrant) and an
    interface map (psi, q) -> (psi - r q, q) keeps sign(q); both corrections are therefore plain
    atan2 differences and no modular wrap-around can occur. Anchored at atan2(-c_1 h, 1) in
    (-pi/2, 0). Theta_L is continuous and strictly increasing in lam > 0 (A.5), tends to -pi/2
    as lam -> 0+, and psi(L; lam) = 0 iff Theta_L = pi/2 (mod pi). Returns (Theta_L, psi_L, q_L).
    Requires lam > 0."""
    if not (lam > 0.0):
        raise ValueError("lam must be positive")
    psi, q = 1.0, -h
    theta = 0.0
    c_prev: Optional[float] = None
    for i, (ell, k, rc, alpha) in enumerate(geo):
        mu = math.sqrt(lam / alpha)
        c = 1.0 / (k * mu)
        if c_prev is None:
            theta = math.atan2(c * q, psi)
        else:                                   # rescale: quadrant preserved, |delta| < pi/2
            theta += math.atan2(c * q, psi) - math.atan2(c_prev * q, psi)
        a, b = psi, -q / (k * mu)
        co, si = math.cos(mu * ell), math.sin(mu * ell)
        psi = a * co + b * si
        q = k * mu * (a * si - b * co)
        theta += mu * ell                       # exact advance in the natural scale
        if i < len(ifaces) and ifaces[i] > 0.0:
            psi_new = psi - ifaces[i] * q       # sign(q) preserved: jump in [0, pi)
            jump = math.atan2(c * q, psi_new) - math.atan2(c * q, psi)
            if jump < -1e-9:
                raise RuntimeError("interface phase jump negative (theorem A.9 violated)")
            theta += max(jump, 0.0)
            psi = psi_new
        c_prev = c
    return theta, psi, q


def _level_count(theta: float) -> int:
    """Number of levels pi/2 + j*pi (j >= 0) at or below theta."""
    if theta < 0.5 * PI:
        return 0
    return int(math.floor((theta - 0.5 * PI) / PI)) + 1


def sturm_index(p: Params, lam: float) -> int:
    """Number of Dirichlet-at-H eigenvalues in (0, lam]; by interlacing (A.5) this equals the
    0-based index n of lam when lam is an eigenvalue of the full problem. Independent per-root
    cross-count (x-sweep at fixed lam; derivation A.9)."""
    validate(p)
    if not (isinstance(lam, (int, float)) and math.isfinite(lam) and lam > 0.0):
        raise ValueError("lam must be positive and finite")
    theta = lifted_terminal_phase(segment_geometry(p), interface_resistances(p), p.h, lam)[0]
    return _level_count(theta)


def _sinc_len(delta: float, ell: float) -> float:   # int_0^ell cos(delta s) ds
    return ell if delta == 0.0 else math.sin(delta * ell) / delta


def _vers_len(delta: float, ell: float) -> float:   # int_0^ell sin(delta s) ds
    if delta == 0.0:
        return 0.0
    x = 0.5 * delta * ell
    return 2.0 * math.sin(x) * math.sin(x) / delta


def _seg_prod(a, b, mu, c, d, nu, ell) -> float:
    """int_0^ell (a cos mu s + b sin mu s)(c cos nu s + d sin nu s) ds (product-to-sum)."""
    Icc = 0.5 * (_sinc_len(mu - nu, ell) + _sinc_len(mu + nu, ell))
    Iss = 0.5 * (_sinc_len(mu - nu, ell) - _sinc_len(mu + nu, ell))
    Isc = 0.5 * (_vers_len(mu - nu, ell) + _vers_len(mu + nu, ell))   # sin(mu s) cos(nu s)
    Ics = 0.5 * (_vers_len(mu + nu, ell) - _vers_len(mu - nu, ell))   # cos(mu s) sin(nu s)
    return a * c * Icc + a * d * Ics + b * c * Isc + b * d * Iss


def _seg_one(a, b, mu, ell) -> float:
    return a * _sinc_len(mu, ell) + b * _vers_len(mu, ell)


def _seg_lin(c0, c1, a, b, mu, ell) -> float:
    """int_0^ell (c0 + c1 s)(a cos mu s + b sin mu s) ds, cancellation-safe for small mu*ell."""
    x = mu * ell
    s_, c_ = math.sin(x), math.cos(x)
    I0 = a * s_ / mu + b * _vers_len(mu, ell)
    if x < 0.1:
        x2 = x * x
        Jc = ell * ell * (0.5 - x2 * (1.0 / 8 - x2 * (1.0 / 144 - x2 * (1.0 / 5760 - x2 / 403200))))
        Js = ell * ell * x * (1.0 / 3 - x2 * (1.0 / 30 - x2 * (1.0 / 840 - x2 / 45360)))
    else:
        Jc = ell * s_ / mu - _vers_len(mu, ell) / mu
        Js = (s_ - x * c_) / (mu * mu)
    return c0 * I0 + c1 * (a * Jc + b * Js)


def _dirichlet_points(geo, ifaces, h, stop: Callable[[list], bool], max_points: int):
    """Zeros d_0 < d_1 < ... of psi(L; lam) (derivation A.5/A.9). Fix 003: they are the level
    crossings Theta_L = pi/2 + j*pi of the EXACT lifted terminal phase, a strictly increasing
    function of lam, so each level is bracketed by a plain scan and found by bisection; no
    wrap-around lifting, hence no aliasing. Monotonicity is asserted (a theorem)."""
    rot = sum(ell / math.sqrt(alpha) for ell, _k, _rc, alpha in geo)
    ds0 = PI / (8.0 * rot)

    def lift(s: float) -> float:
        if s <= 0.0:
            return -0.5 * PI               # lim lam -> 0+ (A.9)
        return lifted_terminal_phase(geo, ifaces, h, s * s)[0]

    points: List[float] = []
    s_a, lift_a = 0.0, lift(0.0)
    j, steps = 0, 0
    while not stop(points):
        steps += 1
        if steps > 2_000_000 or len(points) > max_points:
            raise RuntimeError("Dirichlet phase scan exceeded its work cap")
        s_b = s_a + ds0
        lift_b = lift(s_b)
        if lift_b < lift_a - 1e-9:
            raise RuntimeError("lifted terminal phase decreased (theorem A.5/A.9 violated)")
        while lift_b >= 0.5 * PI + j * PI:
            thr = 0.5 * PI + j * PI
            lo, hi = s_a, s_b
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                if mid <= lo or mid >= hi:
                    break
                if lift(mid) < thr:
                    lo = mid
                else:
                    hi = mid
            d = 0.5 * (lo + hi)
            points.append(d * d)
            j += 1
        s_a, lift_a = s_b, lift_b
    return points


def _bisect_char(geo, ifaces, p: Params, lo: float, hi: float, sign_lo: int) -> float:
    for _ in range(400):
        mid = 0.5 * (lo + hi)
        if mid <= lo or mid >= hi:
            break
        _c, psiL, qL = _propagate(geo, ifaces, p.h, mid)
        Fm = p.area * qL - (p.G_rej - mid * p.C_H) * psiL
        if Fm == 0.0:
            return mid
        if (Fm < 0.0) == (sign_lo < 0):
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _make_mode(geo, ifaces, p: Params, lam: float) -> Mode:
    coeffs, psiL, _qL = _propagate(geo, ifaces, p.h, lam)
    A = p.area
    norm = p.C_H * psiL * psiL
    one = p.C_H * psiL
    for (ell, k, rc, alpha), (a, b, mu) in zip(geo, coeffs):
        norm += rc * A * _seg_prod(a, b, mu, a, b, mu, ell)
        one += rc * A * _seg_one(a, b, mu, ell)
    return Mode(lam=lam, seg=tuple(coeffs), psi_L=psiL, norm=norm, one=one, psi_S=coeffs[2][0])


def compute_modes(p: Params, n_modes: Optional[int] = None, lam_max: Optional[float] = None,
                  max_modes: int = 800) -> ModeSet:
    """All eigenvalues up to lam_max (at least one; possibly one above it), or exactly n_modes of
    them, with guaranteed count via Dirichlet interlacing (exact lifted phase, A.9).

    Diagnostics (Fix 003): 'max_root_rel_error_est' = max_n |F(lam_n)| |psi_n(L)| / (N_n lam_n),
    i.e. the conditioning-corrected root error |dlam|/lam (A.11; a few ulps expected);
    'max_energy_identity_residual_rel' is the raw identity residual, which is amplified by
    N_n/|psi_n(L)| ~ lam_n and is informational only; 'sturm_index_ok' = every root sits at its
    own Sturm index; 'weyl_offset' = count - sqrt(lam_max) rot / pi, rigorously in (-3, 4) when
    the set is complete (A.10)."""
    validate(p)
    if (n_modes is None) == (lam_max is None):
        raise ValueError("give exactly one of n_modes or lam_max")
    geo, ifaces = segment_geometry(p), interface_resistances(p)
    if n_modes is not None:
        if not isinstance(n_modes, int) or n_modes < 1 or n_modes > max_modes:
            raise ValueError("n_modes must be an int in [1, max_modes]")
        stop = lambda pts: len(pts) >= n_modes
    else:
        if not (lam_max > 0.0) or not math.isfinite(lam_max):
            raise ValueError("lam_max must be positive and finite")
        stop = lambda pts: bool(pts) and pts[-1] > lam_max
    points = _dirichlet_points(geo, ifaces, p.h, stop, max_modes)
    if n_modes is not None:
        points = points[:n_modes]
    lo, sign_lo = 0.0, -1          # F(0) = -hA - G psi_L(0) < 0 since psi_L(0) = 1 + h*R > 0
    modes: List[Mode] = []
    for d in points:
        _c, _psiLd, qLd = _propagate(geo, ifaces, p.h, d)
        sign_hi = 1 if qLd > 0.0 else -1
        if sign_hi == sign_lo:
            raise RuntimeError("Dirichlet bracket sign pattern violated; count unreliable")
        lam = _bisect_char(geo, ifaces, p, lo, d, sign_lo)
        modes.append(_make_mode(geo, ifaces, p, lam))
        lo, sign_lo = d, sign_hi
    hA = p.h * p.area
    alternation = all(modes[i].psi_L * modes[i - 1].psi_L < 0.0 for i in range(1, len(modes)))
    alternation = alternation and modes[0].psi_L > 0.0
    ident = 0.0
    rel_root = 0.0
    for m in modes:
        res = abs(m.lam * m.one - (hA + p.G_rej * m.psi_L))        # == |F(lam_hat)| (A.11)
        ident = max(ident, res / (hA + p.G_rej * abs(m.psi_L) + m.lam * abs(m.one)))
        rel_root = max(rel_root, res * abs(m.psi_L) / (m.norm * m.lam))
    sturm_ok = all(_level_count(lifted_terminal_phase(geo, ifaces, p.h, m.lam)[0]) == n
                   for n, m in enumerate(modes))
    k4, alpha4 = geo[-1][1], geo[-1][3]
    dres = 0.0
    for d in points:
        _th, psiLd, qLd = lifted_terminal_phase(geo, ifaces, p.h, d)
        dres = max(dres, abs(psiLd) / (abs(psiLd) + abs(qLd) / (k4 * math.sqrt(d / alpha4))))
    rot = sum(ell / math.sqrt(alpha) for ell, _k, _rc, alpha in geo)
    weyl = math.sqrt(modes[-1].lam) * rot / PI
    diag = {"count": len(modes), "lam_min": modes[0].lam, "lam_max": modes[-1].lam,
            "dirichlet": list(points), "alternation_ok": alternation,
            "sturm_index_ok": sturm_ok,
            "max_root_rel_error_est": rel_root,
            "max_energy_identity_residual_rel": ident,
            "dirichlet_residual_max": dres,
            "weyl_estimate_at_lam_max": weyl,
            "weyl_offset": len(modes) - weyl,
            "weyl_offset_bounds_open": (-3.0, 4.0),
            "asymptotic_sqrt_lambda_spacing": PI / rot}
    return ModeSet(geo=geo, ifaces=ifaces, area=p.area, C_H=p.C_H, h=p.h, G_rej=p.G_rej,
                   modes=tuple(modes), diagnostics=diag)


# ---- Fix 003: argument-principle cross-count (complex F) -----------------------------------
def _propagate_c(geo, ifaces, h: float, lam: complex) -> Tuple[complex, complex]:
    """Complex-lam version of _propagate (entire in lam; even in mu, so branch-free)."""
    psi, q = complex(1.0, 0.0), complex(-h, 0.0)
    for i, (ell, k, rc, alpha) in enumerate(geo):
        mu = cmath.sqrt(lam / alpha)
        a, b = psi, -q / (k * mu)
        c, s = cmath.cos(mu * ell), cmath.sin(mu * ell)
        psi = a * c + b * s
        q = k * mu * (a * s - b * c)
        if i < len(ifaces):
            psi = psi - ifaces[i] * q
    return psi, q


def characteristic_c(p: Params, lam: complex) -> complex:
    """F(lam) for complex lam (lam != 0)."""
    geo, ifaces = segment_geometry(p), interface_resistances(p)
    z = complex(lam)
    psiL, qL = _propagate_c(geo, ifaces, p.h, z)
    return p.area * qL - (p.G_rej - z * p.C_H) * psiL


def count_zeros_argument_principle(p: Params, lam_hi: float, lam_lo: Optional[float] = None,
                                   half_height: Optional[float] = None, verify: bool = True,
                                   max_evals: int = 400_000) -> int:
    """Number of zeros of the entire function F inside [lam_lo, lam_hi] x [-c, c] (argument
    principle: winding number of F along the boundary, adaptively sampled, |delta arg| <= pi/4
    per accepted step, initial steps <= c/8). Independent of the Dirichlet bracketing. All zeros
    of F are real and positive (A.4), so with lam_lo < 0 (default -c) the result is the number of
    eigenvalues below lam_hi; lam_hi must not be an eigenvalue. With verify=True the count is
    recomputed with height c/3 and must agree (guards against an aliased step)."""
    validate(p)
    if not (isinstance(lam_hi, (int, float)) and math.isfinite(lam_hi) and lam_hi > 0.0):
        raise ValueError("lam_hi must be positive and finite")
    geo, ifaces = segment_geometry(p), interface_resistances(p)
    rot = sum(ell / math.sqrt(alpha) for ell, _k, _rc, alpha in geo)
    if half_height is None:
        half_height = min(0.02 * lam_hi, 2.0 * (200.0 / rot) ** 2)   # keeps |F| <~ e^200
    if not (half_height > 0.0):
        raise ValueError("half_height must be positive")
    a = -half_height if lam_lo is None else lam_lo
    if not (a < lam_hi):
        raise ValueError("lam_lo must be below lam_hi")
    budget = [max_evals]

    def winding(c: float) -> int:
        def F(z: complex) -> complex:
            budget[0] -= 1
            if budget[0] < 0:
                raise RuntimeError("argument-principle walk exceeded its work cap")
            psiL, qL = _propagate_c(geo, ifaces, p.h, z)
            f = p.area * qL - (p.G_rej - z * p.C_H) * psiL
            if f == 0:
                raise RuntimeError("contour passes through a zero of F")
            return f

        def walk(za, fa, zb, fb, depth):
            d = math.remainder(cmath.phase(fb) - cmath.phase(fa), 2.0 * PI)
            if abs(d) <= 0.25 * PI:
                return d
            if depth > 60:
                raise RuntimeError("argument-principle step did not resolve")
            zm = 0.5 * (za + zb)
            fm = F(zm)
            return walk(za, fa, zm, fm, depth + 1) + walk(zm, fm, zb, fb, depth + 1)

        corners = [complex(a, -c), complex(lam_hi, -c), complex(lam_hi, c), complex(a, c)]
        total = 0.0
        for z0, z1 in zip(corners, corners[1:] + corners[:1]):
            n = int(abs(z1 - z0) / (0.125 * c)) + 1
            zs = [z0 + (z1 - z0) * (i / n) for i in range(n + 1)]
            fs = [F(z) for z in zs]
            total += math.fsum(walk(zs[i], fs[i], zs[i + 1], fs[i + 1], 0) for i in range(n))
        w = total / (2.0 * PI)
        count = int(round(w))
        if abs(w - count) > 1e-6:
            raise RuntimeError(f"winding number not integral: {w!r}")
        return count

    count = winding(half_height)
    if verify:
        count2 = winding(half_height / 3.0)
        if count2 != count:
            raise RuntimeError(f"argument-principle counts disagree: {count} vs {count2}")
    return count


# ----------------------------------------------------------------------------- projections
def _lin_inner(ms: ModeSet, lin, linH: float, m: Mode) -> float:
    acc = ms.C_H * linH * m.psi_L
    for (ell, k, rc, alpha), (c0, c1), (a, b, mu) in zip(ms.geo, lin, m.seg):
        acc += rc * ms.area * _seg_lin(c0, c1, a, b, mu, ell)
    return acc


def _mode_inner(ms: ModeSet, m1: Mode, m2: Mode) -> float:
    acc = ms.C_H * m1.psi_L * m2.psi_L
    for (ell, k, rc, alpha), (a, b, mu), (c, d, nu) in zip(ms.geo, m1.seg, m2.seg):
        acc += rc * ms.area * _seg_prod(a, b, mu, c, d, nu, ell)
    return acc


def _lin_norm(ms: ModeSet, lin, linH: float) -> float:
    acc = ms.C_H * linH * linH
    for (ell, k, rc, alpha), (c0, c1) in zip(ms.geo, lin):
        acc += rc * ms.area * (c0 * c0 * ell + c0 * c1 * ell * ell + c1 * c1 * ell ** 3 / 3.0)
    return acc


def project(ms: ModeSet, lin, linH: float, src: Optional[ModeSet] = None,
            amps: Optional[Sequence[float]] = None):
    """Coefficients b_m = <theta, psi_m>/N_m for theta = piecewise-linear part (lin, linH)
    plus optional modal part sum_n amps_n psi_n^src. Returns (coeffs, defect, <theta,theta>)."""
    coeffs = []
    for m in ms.modes:
        ip = _lin_inner(ms, lin, linH, m)
        if src is not None:
            ip += math.fsum(a * _mode_inner(ms, sm, m) for a, sm in zip(amps, src.modes))
        coeffs.append(ip / m.norm)
    theta2 = _lin_norm(ms, lin, linH)
    if src is not None:
        theta2 += 2.0 * math.fsum(a * _lin_inner(ms, lin, linH, sm) for a, sm in zip(amps, src.modes))
        theta2 += math.fsum(a1 * a2 * _mode_inner(ms, s1, s2)
                            for a1, s1 in zip(amps, src.modes) for a2, s2 in zip(amps, src.modes))
    captured = math.fsum(c * c * m.norm for c, m in zip(coeffs, ms.modes))
    return coeffs, theta2 - captured, theta2


# ----------------------------------------------------------------------------- solution
@dataclass
class _Segment:
    t_start: float
    t_end: float
    params: Params
    steady: dict
    modes: ModeSet
    coeffs: List[float]
    defect: float
    theta2: float

    def summary(self) -> dict:
        d = dict(self.modes.diagnostics)
        d.pop("dirichlet", None)
        return {"t_start": self.t_start, "t_end": self.t_end, "P_body": self.params.P_body,
                "P_sensor": self.params.P_sensor, "G_rej": self.params.G_rej,
                "r_inner": self.params.r_inner, "projection_defect": self.defect,
                "projection_defect_rel": (self.defect / self.theta2 if self.theta2 > 0 else 0.0),
                "modes": d}


class Solution:
    def __init__(self, segments: List[_Segment], T_initial: float, T_ref: float):
        self.segments = segments
        self.T_initial = T_initial
        self.T_ref = T_ref

    def segment_at(self, t: float) -> _Segment:
        if t < self.segments[0].t_start:
            raise ValueError("time before schedule start")
        for s in self.segments:
            if t <= s.t_end:            # left-limit rule at event instants
                return s
        return self.segments[-1]

    @staticmethod
    def _psi(m: Mode, loc: str) -> float:
        return 1.0 if loc == "surface" else (m.psi_S if loc == "sensor" else m.psi_L)

    def temperature(self, loc: str, t: float) -> float:
        if loc not in LOCATIONS:
            raise ValueError("loc must be one of " + ", ".join(LOCATIONS))
        if t == self.segments[0].t_start:
            return self.T_initial
        seg = self.segment_at(t)
        dt = t - seg.t_start
        base = seg.steady[{"surface": "surface", "sensor": "S", "H": "H"}[loc]]
        terms = [a * math.exp(-m.lam * dt) * self._psi(m, loc)
                 for a, m in zip(seg.coeffs, seg.modes.modes)]
        return base + math.fsum(reversed(terms))

    def temperature_at(self, x: float, t: float, side: int = 1) -> float:
        if t == self.segments[0].t_start:
            return self.T_initial
        seg = self.segment_at(t)
        dt = t - seg.t_start
        i, s = _locate(seg.modes.geo, x, side)
        st = seg.steady["segments"][i]
        terms = [a * math.exp(-m.lam * dt) * (m.seg[i][0] * math.cos(m.seg[i][2] * s)
                                             + m.seg[i][1] * math.sin(m.seg[i][2] * s))
                 for a, m in zip(seg.coeffs, seg.modes.modes)]
        return st["T0"] + st["slope"] * s + math.fsum(reversed(terms))

    def flux_at(self, x: float, t: float, side: int = 1) -> float:
        """Flux density q = -k dT/dx (W/m2, positive toward H) from the series."""
        seg = self.segment_at(t)
        dt = t - seg.t_start
        i, s = _locate(seg.modes.geo, x, side)
        st = seg.steady["segments"][i]
        k = seg.modes.geo[i][1]
        terms = []
        for a, m in zip(seg.coeffs, seg.modes.modes):
            A_, B_, mu = m.seg[i]
            dpsi = mu * (-A_ * math.sin(mu * s) + B_ * math.cos(mu * s))
            terms.append(-k * a * math.exp(-m.lam * dt) * dpsi)
        return st["q"] + math.fsum(reversed(terms))

    def values(self, t: float) -> Dict[str, float]:
        seg = self.segment_at(t)
        p = seg.params
        Ts, Tsen, TH = (self.temperature(loc, t) for loc in LOCATIONS)
        return {"t_s": t, "surface_C": Ts, "sensor_C": Tsen, "H_C": TH,
                "front_W": p.h * p.area * (Ts - p.T_amb), "rear_W": p.G_rej * (TH - p.T_res),
                "segment_index": self.segments.index(seg)}

    def rows(self, times: Sequence[float]) -> List[dict]:
        return [self.values(t) for t in times]

    def _E_series(self, seg: _Segment, dt: float) -> float:
        p = seg.params
        E = p.C_H * (seg.steady["H"] - self.T_ref)
        for st in seg.steady["segments"]:
            E += st["rc"] * p.area * (st["ell"] * (st["T0"] - self.T_ref)
                                      + 0.5 * st["slope"] * st["ell"] ** 2)
        return E + math.fsum(a * math.exp(-m.lam * dt) * m.one
                             for a, m in zip(seg.coeffs, seg.modes.modes))

    def stored_energy(self, t: float) -> float:
        seg = self.segment_at(t)
        return self._E_series(seg, t - seg.t_start)

    def total_capacity(self) -> float:
        p = self.segments[0].params
        return p.C_H + sum(rc * p.area * ell for ell, _k, rc, _a in segment_geometry(p))

    def energy_audit(self, t: float) -> dict:
        """Closed-form energy bookkeeping of the represented solution (derivation A.4)."""
        residual = input_J = front_J = rear_J = 0.0
        jumps = []
        prev_end_E = None
        for seg in self.segments:
            if seg.t_start >= t and seg is not self.segments[0]:
                break
            p = seg.params
            tau = min(t, seg.t_end)
            dt = tau - seg.t_start
            E0, E1 = self._E_series(seg, 0.0), self._E_series(seg, dt)
            if prev_end_E is not None:
                jumps.append(E0 - prev_end_E)
            inp = (p.P_body + p.P_sensor) * dt
            tail_f = math.fsum(a * (-math.expm1(-m.lam * dt)) / m.lam
                               for a, m in zip(seg.coeffs, seg.modes.modes))
            tail_r = math.fsum(a * m.psi_L * (-math.expm1(-m.lam * dt)) / m.lam
                               for a, m in zip(seg.coeffs, seg.modes.modes))
            fr = p.h * p.area * ((seg.steady["surface"] - p.T_amb) * dt + tail_f)
            re = p.G_rej * ((seg.steady["H"] - p.T_res) * dt + tail_r)
            residual += (E1 - E0) - (inp - fr - re)
            input_J += inp
            front_J += fr
            rear_J += re
            prev_end_E = E1
            if tau == t:
                break
        E_exact0 = self.total_capacity() * (self.T_initial - self.T_ref)
        return {"t_s": t, "stored_J": self.stored_energy(t), "input_J": input_J,
                "front_loss_J": front_J, "rear_loss_J": rear_J, "residual_J": residual,
                "initial_energy_defect_J": self._E_series(self.segments[0], 0.0) - E_exact0,
                "event_energy_jumps_J": jumps}

    def tail_estimate(self, loc: str, t: float) -> float:
        """Heuristic a posteriori truncation estimate (not a rigorous bound)."""
        seg = self.segment_at(t)
        dt = t - seg.t_start
        if dt <= 0.0:
            return math.inf
        ms = seg.modes.modes
        last = list(zip(seg.coeffs, ms))[-5:]
        M = max(abs(a * self._psi(m, loc)) for a, m in last)
        delta = seg.modes.diagnostics["asymptotic_sqrt_lambda_spacing"]
        sN = math.sqrt(ms[-1].lam)
        tot, j = 0.0, 1
        while j <= 100000:
            term = math.exp(-((sN + j * delta) ** 2) * dt)
            tot += term
            if term < 1e-30:
                break
            j += 1
        return M * tot


def solve(schedule: Sequence[Tuple[float, Params]], times: Sequence[float], T_initial: float = 25.0,
          n_modes: Optional[int] = None, dt_floor: float = 0.02, max_modes: int = 800,
          T_ref: Optional[float] = None) -> Solution:
    """schedule: [(t_start, Params), ...] with t_start[0] == 0 and strictly increasing starts.
    Each event is a new initial-value problem from the exact state (derivation A.7)."""
    if not schedule or schedule[0][0] != 0.0:
        raise ValueError("schedule must start at t = 0")
    starts = [t for t, _ in schedule]
    if any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError("schedule starts must be strictly increasing")
    _finite("T_initial", T_initial)
    for t in times:
        _finite("time", t)
        if t < 0:
            raise ValueError("times must be non-negative")
    ends = starts[1:] + [math.inf]
    base = schedule[0][1]
    cache: Dict[tuple, ModeSet] = {}
    segments: List[_Segment] = []
    prev: Optional[_Segment] = None
    for (t0, p), t1 in zip(schedule, ends):
        validate(p)
        if (p.outer, p.film, p.inner, p.area) != (base.outer, base.film, base.inner, base.area):
            raise ValueError("layer geometry/materials must be identical across segments")
        st = steady_state(p)
        if n_modes is not None:
            key = (replace(p, T_amb=0.0, T_res=0.0, P_body=0.0, P_sensor=0.0), n_modes, None)
            if key not in cache:
                cache[key] = compute_modes(p, n_modes=n_modes, max_modes=max_modes)
        else:
            dts = [t - t0 for t in times if t0 < t <= t1]
            dt_min = min(dts) if dts else (t1 - t0 if math.isfinite(t1) else 1.0)
            lam_max = 50.0 / max(dt_min, dt_floor)
            key = (replace(p, T_amb=0.0, T_res=0.0, P_body=0.0, P_sensor=0.0), None, lam_max)
            if key not in cache:
                cache[key] = compute_modes(p, lam_max=lam_max, max_modes=max_modes)
        ms = cache[key]
        if prev is None:
            lin = [(T_initial - s["T0"], -s["slope"]) for s in st["segments"]]
            coeffs, defect, theta2 = project(ms, lin, T_initial - st["H"])
        else:
            dtp = t0 - prev.t_start
            amps = [a * math.exp(-m.lam * dtp) for a, m in zip(prev.coeffs, prev.modes.modes)]
            lin = [(s1["T0"] - s2["T0"], s1["slope"] - s2["slope"])
                   for s1, s2 in zip(prev.steady["segments"], st["segments"])]
            coeffs, defect, theta2 = project(ms, lin, prev.steady["H"] - st["H"], prev.modes, amps)
        seg = _Segment(t0, t1, p, st, ms, coeffs, defect, theta2)
        segments.append(seg)
        prev = seg
    return Solution(segments, T_initial, base.T_amb if T_ref is None else T_ref)


# ----------------------------------------------------------------------------- schedules
def nominal_params(stack: str, **over) -> Params:
    th = {"H1": 0.0005, "H2": 0.001, "H3": 0.002}[stack]
    sil = Layer(th, 0.27, 1030.0, 1500.0)
    film = Layer(5.0e-5, 0.20, 1420.0, 1090.0)
    return replace(Params(outer=sil, film=film, inner=sil), **over)


def schedule_F0(stack: str, P_body: float = 5.0, body_off_s: float = 900.0, P_sensor: float = 0.1):
    p = nominal_params(stack, P_body=P_body, P_sensor=P_sensor)
    return [(0.0, p), (body_off_s, replace(p, P_body=0.0))]


def schedule_F1(stack: str, event_s: float = 600.0, G_after: float = 0.0, P_body: float = 5.0,
                body_off_s: float = 900.0, P_sensor: float = 0.1):
    """ASSUMPTION: F1 = rear conductance change at event_s (default: rear path blocked)."""
    p = nominal_params(stack, P_body=P_body, P_sensor=P_sensor)
    return [(0.0, p), (event_s, replace(p, G_rej=G_after)),
            (body_off_s, replace(p, G_rej=G_after, P_body=0.0))]


def schedule_F2(stack: str, event_s: float = 600.0, r_inner_after: float = 2.0e-2, P_body: float = 5.0,
                body_off_s: float = 900.0, P_sensor: float = 0.1):
    """ASSUMPTION: F2 = inner contact resistance change at event_s (default: contract upper bound)."""
    p = nominal_params(stack, P_body=P_body, P_sensor=P_sensor)
    return [(0.0, p), (event_s, replace(p, r_inner=r_inner_after)),
            (body_off_s, replace(p, r_inner=r_inner_after, P_body=0.0))]


DEFAULT_TIMES = (0.0, 1.0, 10.0, 60.0, 300.0, 600.0, 601.0, 660.0, 900.0, 901.0, 960.0, 1800.0, 3600.0)


def run_default_cases(n_modes: Optional[int] = None, times: Sequence[float] = DEFAULT_TIMES) -> dict:
    out = {"contract": "T0-HYP-1", "method": "eigenfunction expansion; transfer matrix; "
           "Dirichlet-interlaced roots (exact lifted phase, fix 003)",
           "executed_by": "caller (see Red's run log)",
           "physical_validation": False, "cases": []}
    for stack in ("H1", "H2", "H3"):
        for name, sched in (("F0", schedule_F0(stack)), ("F1", schedule_F1(stack)), ("F2", schedule_F2(stack))):
            sol = solve(sched, times, n_modes=n_modes)
            segs = []
            for s in sol.segments:
                d = s.summary()
                d["tail_estimate_K_at_dt_1s"] = {loc: sol.tail_estimate(loc, s.t_start + 1.0)
                                                  for loc in LOCATIONS}
                segs.append(d)
            out["cases"].append({"stack": stack, "scenario": name, "segments": segs,
                                 "rows": sol.rows(times),
                                 "energy_audits": [sol.energy_audit(t) for t in (600.0, 900.0, 3600.0)]})
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="T0-HYP-1 semi-analytic layered transient oracle")
    ap.add_argument("--out", default=None, help="write JSON results to this path (no default write)")
    ap.add_argument("--n-modes", type=int, default=None, help="force a fixed number of modes")
    args = ap.parse_args(argv)
    result = run_default_cases(n_modes=args.n_modes)
    text = json.dumps(result, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(json.dumps({"written": args.out, "cases": len(result["cases"])}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
