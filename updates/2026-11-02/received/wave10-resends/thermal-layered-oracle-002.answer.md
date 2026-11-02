# thermal-layered-oracle-001 — semi-analytic layered transient oracle (Claude for Red)

Contributors and provenance: derivation, module and tests below are by Claude (Anthropic) for Red, working with Richard (Andrei) Pemberton in The Stage. The steady network form and all reference values come from Coda's (Codex Lily) `validation/thermal/thermal_reference.py` / `reference_results.json` (verbatim in the bundle). Coda's two-node transient report is a different (lumped) model and is *not* used as a target. Earlier packet contributions by Claude Fable 5.1 are acknowledged but not reproduced here. Textbook citations below are from memory, not from the bundle.

**Nothing below has been executed.** All numbers quoted are either copied from the bundle or are order-of-magnitude estimates labelled as such. Red will run the code; results must be reviewed before any use.

---

## (a) Derivation

### A.1 Model

Coordinate x from the outer face (x=0) toward H (x=L). Four bookkeeping segments i=1..4: outer silicone (ℓ₁), film outer half (ℓ₂=ℓ_f/2), film inner half (ℓ₃=ℓ_f/2), inner silicone (ℓ₄); conductivities k_i, volumetric capacities (ρc)_i, diffusivities α_i=k_i/(ρc)_i. Flux density q=−k∂T/∂x (positive toward H). Constants exactly as the contract: silicone k=0.27, ρ=1030, cp=1500; film k=0.20, ρ=1420, cp=1090; A=0.01 m²; r_c=2.0e-4 m²K/W at both silicone|film interfaces; h=8; G_rej=1/R_rej=0.5 W/K (0 if blocked); C_H=20 J/K; T_amb=T_res=25 °C.

Equations (within a segment of constant sources/parameters):

- (ρc)_i ∂T/∂t = k_i ∂²T/∂x²  in each segment.
- x=0: q(0,t) = −h[T(0,t) − T_amb]  (equivalently k₁T_x(0)=h[T(0)−T_amb]).
- Silicone|film interface (x₁=ℓ₁, areal r_o): q continuous, T(x₁⁻)−T(x₁⁺)=r_o q(x₁).
- Sheet source at x_s=ℓ₁+ℓ_f/2 (between segments 2 and 3): T continuous, q(x_s⁺)−q(x_s⁻)=P_sensor/A.
- Film|silicone interface (x₃=ℓ₁+ℓ_f, areal r_i): q continuous, T(x₃⁻)−T(x₃⁺)=r_i q(x₃).
- x=L: ideal contact T(L,t)=T_H(t); node balance C_H dT_H/dt = P_body + A q(L,t) − G(T_H − T_res).

### A.2 Steady state (closed form, matches the contract's two-node reduction)

With R_HS = (ℓ₄/k₄ + ℓ₃/k₃ + r_i)/A and R_SA = (ℓ₂/k₂ + ℓ₁/k₁ + r_o)/A + 1/(hA), g₁=1/R_HS, g₂=1/R_SA:

(g₁+g₂)S − g₁T_H = P_s + g₂T_amb,  −g₁S + (g₁+G)T_H = P_b + G T_res,

determinant g₁g₂ + G(g₁+g₂) (assembled as positive terms). Front flow F=g₂(S−T_amb) (toward ambient), Q_in=g₁(T_H−S) (from H toward the sheet), rear = G(T_H−T_res), surface T(0)=T_amb+F/(hA). The profile is piecewise linear: q=−F/A for x<x_s, q=−Q_in/A for x>x_s (jump P_s/A at the sheet), slope −q_i/k_i, and interface jumps T⁺=T⁻−r q. Signs are preserved automatically if the reservoir warms the assembly. This is algebraically the same network as Coda's heat-flow elimination, so the long-time limit of the oracle must reproduce `reference_results.json` (test).

### A.3 Homogeneous modes and the transcendental equation

Put T=e^{−λt}ψ(x), T_H=e^{−λt}ψ_H with ψ_H=ψ(L). Then ψ''+(λ/α_i)ψ=0 in each segment, k₁ψ'(0)=hψ(0), the homogeneous interface conditions, and at x=L

  −λC_Hψ(L) = A q_ψ(L) − Gψ(L)  ⇔  A q_ψ(L) = (G − λC_H)ψ(L),  q_ψ=−kψ'.

Transfer matrix in the state (ψ,q): for a segment with μ_i=√(λ/α_i),

  M_i(λ) = [[cos μ_iℓ_i, −sin(μ_iℓ_i)/(k_iμ_i)], [k_iμ_i sin(μ_iℓ_i), cos μ_iℓ_i]],

interface with areal resistance r: J(r) = [[1, −r],[0, 1]] (det 1). Starting from the normalised left data (ψ,q)(0)=(1,−h),

  (ψ,q)(L) = M₄ J(r_i) M₃ M₂ J(r_o) M₁ (1, −h)ᵀ,  F(λ) := A q(L;λ) − (G − λC_H) ψ(L;λ) = 0.

This is the eigenvalue equation including both interface resistances and the H-node capacity. Within a segment ψ(s)=A_i cos μ_is + B_i sin μ_is, A_i=ψ(x_i⁺), B_i=−q(x_i⁺)/(k_iμ_i); the sheet contributes nothing to the homogeneous modes (r=0, continuity).

### A.4 Orthogonality with interface jumps and the point mass (weighting)

For f,g satisfying the homogeneous interface conditions, summing Green's identity over segments:

Σ_i∫(k_if')'g dx = −h f(0)g(0) + k₄f'(L)g(L) − r_o q_f(x₁)q_g(x₁) − r_i q_f(x₃)q_g(x₃) − Σ_i∫k_if'g' dx.

At an interface the two one-sided boundary terms combine to −q_f·[g] = −q_f(r q_g) = −r q_f q_g, symmetric in (f,g). Applying this to eigenfunctions, using −λ_n(ρc)_iψ_n=(k_iψ_n')' and k₄ψ_n'(L) = −(G − λ_nC_H)ψ_n(L)/A, and antisymmetrising in (n,m):

  (λ_m − λ_n)[ Σ_i∫(ρc)_i ψ_nψ_m dx + (C_H/A) ψ_n(L)ψ_m(L) ] = 0.

Hence the correct inner product is

  ⟨f,g⟩ = Σ_i A(ρc)_i ∫_segment_i f g dx + C_H f_H g_H,  N_n = ⟨ψ_n,ψ_n⟩,

i.e. the slab capacity density plus a point mass C_H at x=L. The n=m identity gives λ_nN_n = hAψ_n(0)² + Gψ_n(L)² + A Σ r q_n² + A Σ∫k ψ_n'² ≥ 0, so λ_n>0 whenever h>0 (λ=0 only if h=G=0). Eigenvalues are simple (the solution is fixed by the left initial data). Taking g≡1: λ_n⟨1,ψ_n⟩ = hAψ_n(0) + Gψ_n(L) — an exact per-mode energy identity used as a root-accuracy test.

### A.5 Simplicity of the zeros of F and robust bracketing (interlacing)

Let W=ψq_λ−qψ_λ (λ-derivatives at fixed x of the normalised solution). In a segment, ψ'=−q/k, q'=λ(ρc)ψ, hence W'=(ρc)ψ²; W(0)=0 (λ-independent data) and W passes unchanged through the det-1 interface maps. So W(L)=Σ∫(ρc)ψ²dx>0 and, at a root λ_n (where G−λC_H = Aq(L)/ψ(L) if ψ(L)≠0),

  F'(λ_n) ψ_n(L) = A Σ∫(ρc)ψ_n² dx + C_H ψ_n(L)² = N_n > 0.

Therefore every zero of F is simple, F changes sign at each eigenvalue and sign ψ_n(L) alternates with n (both are tests). Two consequences used for *provably complete* root finding:

1. Dirichlet-at-H spectrum. The terminal angle Θ(λ)=atan2(c q(L), ψ(L)) with any λ-independent c>0 satisfies dΘ/dλ = cW(L)/(ψ²+c²q²) > 0. Zeros d₀<d₁<… of ψ(L;λ) (the problem with T(L)=0) occur exactly where the continuously lifted Θ passes π/2+jπ, each once. Counting them by the lifted phase cannot miss or double count a root.
2. Herglotz interlacing. Y(λ)=A q(L)/ψ(L) has Y'=A W(L)/ψ(L)²>0 on each (d_{j−1},d_j), running from −∞ to +∞, while R(λ)=G−λC_H is non-increasing. Since F=0 ⇔ Y=R, there is exactly one eigenvalue in each (d_{j−1},d_j). On (0,d₀): Y(0)=−hA/ψ(L;0)<0≤G=R(0) and Y→+∞, so exactly one eigenvalue (the "node" mode) lies in (0,d₀). The end-point signs of F are known analytically: F(0)=−hA−Gψ(L;0)<0 and F(d_j)=A q(L;d_j), whose sign alternates. Bisection inside each bracket is then guaranteed to converge to the unique root, however clustered the roots are.

This is what the module does. The phase lift uses steps of π/8 in the asymptotic natural rotation (√λ step π/(8Σℓ_i/√α_i)) with adaptive halving; the distortion between the natural angle and the fixed-scale angle is bounded by π/2 per step, so increments stay below π and wrap-around aliasing is excluded (heuristic argument, backed by monotonicity assertion, Weyl count and alternation diagnostics).

Asymptotics (phase accumulation μ_iℓ_i per segment, bounded phase at interfaces/ends): √λ_n = nπ/Σ_i(ℓ_i/√α_i) + O(1). Order of magnitude (static estimate, not executed): spacing ≈1.24 s^{-1/2} for H1, ≈0.32 for H3; film-internal resonances start near λ≈5×10² s⁻¹ where local spacings shrink (the "clustered thin-film" region).

### A.6 Treatment of the sheet source, body source and initial data

All sources are piecewise constant, the problem is linear, and the sheet is modelled exactly by the flux jump in the steady profile; so within a segment starting at t₀ with state T(x,t₀), T_H(t₀):

  T(x,t) = T_ss(x) + Σ_n a_n e^{−λ_n(t−t₀)} ψ_n(x),  T_H(t) = T_H,ss + Σ_n a_n e^{−λ_n(t−t₀)} ψ_n(L),
  a_n = ⟨T(·,t₀) − T_ss, ψ_n⟩ / N_n  (with H-component T_H(t₀) − T_H,ss).

This equals the Duhamel/Green's-function solution for a step in the delta sheet and in P_body; no regularisation of the delta is needed. For a uniform start, θ₀=T₀−T_ss is piecewise linear with interface jumps, so all projections are closed form (∫(c₀+c₁s)cos μs, ∫(c₀+c₁s)sin μs; small-argument series are used where the direct forms cancel).

### A.7 Events (F1/F2) as new initial-value problems

At t_e the state of segment 1 is known exactly (series). For segment 2 (new G, or new r_i): new steady profile T_ss⁽²⁾ and new modes ψ_m⁽²⁾. Initial data θ = [T_ss⁽¹⁾ − T_ss⁽²⁾] + Σ_n a_n e^{−λ_n(t_e−t₀)} ψ_n⁽¹⁾, projected with closed-form cross products ∫(A cos μs+B sin μs)(C cos νs+D sin νs)ds (product-to-sum, with safe sinc for μ≈ν) plus the point-mass term C_Hψ_n⁽¹⁾(L)ψ_m⁽²⁾(L). Temperature and H state are continuous (no impulse); for a contact-resistance change the old state satisfies the old jump condition while the new modes satisfy the new one — the expansion converges in the weighted L² norm at t_e and pointwise for t>t_e (parabolic smoothing). The module reports the Parseval defect ⟨θ,θ⟩ − Σ b_m²N_m of each projection. Evaluation exactly at t_e uses the left limit (segment 1).

### A.8 Completeness and convergence

Hilbert space 𝓗 = ⊕_i L²(segment_i; A(ρc)_i dx) ⊕ ℝ (weight C_H), quadratic form a(f,f) = Σ_i A∫k_if'² + hA f(0)² + Σ_interfaces A[f]²/r + G f_H² on the form domain {f ∈ ⊕H¹, f(L)=f_H} (continuity imposed where r=0). The form is closed, symmetric, non-negative, and the form domain embeds compactly in 𝓗 (Rellich on bounded intervals plus a finite-dimensional part), so the associated self-adjoint operator has compact resolvent and an orthonormal eigenbasis of 𝓗 with 0<λ₀<λ₁<…→∞ (eigenparameter-in-BC theory: Walter 1973, Fulton 1977; composite media with contact resistance: Tittle 1965, Mikhailov & Özişik 1984 — cited from memory). Hence θ₀∈𝓗 expands as Σa_nψ_n in 𝓗, and for t−t₀>0 the series converges absolutely and uniformly: |Σ_{n>N} a_n e^{−λ_nΔt}ψ_n(x)| ≤ ‖θ₀‖ (Σ_{n>N} e^{−2λ_nΔt} ψ̂_n(x)²)^{1/2} with normalised ψ̂_n uniformly bounded (WKB amplitude), and λ_n≥(√λ_N+(n−N)Δ_min)² gives the tail bound ∝ e^{−λ_NΔt}/(Δ√(λ_N)Δt). A posteriori, the module estimates the tail by max of the last retained |a_nψ_n| times Σ_{j≥1} exp(−(√λ_N+jΔ_asym)²Δt) (heuristic, labelled).

---

## (b) Module

FILE: oracle/layered_oracle.py
```python
"""Semi-analytic oracle for the transient T0-HYP-1 layered stack (eigenfunction expansion).

Stack (outer to inner): outer silicone | film with sensor sheet at midplane | inner silicone |
lumped node H (capacity C_H, conductance G_rej to a reservoir). Convection h*A at the outer
face; areal contact resistances at both silicone|film interfaces.

Method: per piecewise-constant segment, T(x,t) = T_ss(x) + sum_n a_n exp(-lam_n (t-t0)) psi_n(x).
Modes via a transfer matrix; roots bracketed by the Dirichlet-at-H spectrum (Herglotz
interlacing, see derivation A.5). NOT a time-stepping finite-volume code.

Standard library only; deterministic; no network; writes a file only when --out is given.
Contributors: Claude (Anthropic) for Red / Richard (Andrei) Pemberton, The Stage. Steady network
and reference values: Coda (Codex Lily), validation/thermal/thermal_reference.py. Earlier
packet work: Claude Fable 5.1. Private computational research on a model; no safety claim.
"""
from __future__ import annotations

import argparse
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


def _dirichlet_points(geo, ifaces, h, scale, stop: Callable[[list], bool], max_points: int):
    """Zeros of psi(L; lam) found by the monotone lifted terminal phase (derivation A.5)."""
    rot = sum(ell / math.sqrt(alpha) for ell, _k, _rc, alpha in geo)
    ds0 = PI / (8.0 * rot)

    def ang(s: float) -> float:
        _c, psiL, qL = _propagate(geo, ifaces, h, s * s)
        return math.atan2(scale * qL, psiL)

    def wrap(d: float) -> float:
        return math.remainder(d, 2.0 * PI)

    points: List[float] = []
    s_a, th_a = 0.0, ang(0.0)
    lift_a = th_a
    j, steps = 0, 0
    while not stop(points):
        steps += 1
        if steps > 2_000_000 or len(points) > max_points:
            raise RuntimeError("Dirichlet phase scan exceeded its work cap")
        sub = ds0
        while True:
            s_b = s_a + sub
            th_b = ang(s_b)
            inc = wrap(th_b - th_a)
            if -1e-9 <= inc <= 1.2:
                break
            sub *= 0.5
            if sub < ds0 * 1e-8:
                raise RuntimeError("terminal phase lift failed (non-monotone or aliased step)")
        lift_b = lift_a + max(inc, 0.0)
        while lift_b >= 0.5 * PI + j * PI:
            thr = 0.5 * PI + j * PI
            lo, hi = s_a, s_b
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                if mid <= lo or mid >= hi:
                    break
                if lift_a + wrap(ang(mid) - th_a) < thr:
                    lo = mid
                else:
                    hi = mid
            d = 0.5 * (lo + hi)
            points.append(d * d)
            j += 1
        s_a, th_a, lift_a = s_b, th_b, lift_b
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
    """All eigenvalues up to lam_max (at least one), or exactly n_modes of them, with
    guaranteed count via Dirichlet interlacing."""
    validate(p)
    if (n_modes is None) == (lam_max is None):
        raise ValueError("give exactly one of n_modes or lam_max")
    geo, ifaces = segment_geometry(p), interface_resistances(p)
    scale = sum(ell / k for ell, k, _rc, _a in geo) + p.r_outer + p.r_inner
    if n_modes is not None:
        if not isinstance(n_modes, int) or n_modes < 1 or n_modes > max_modes:
            raise ValueError("n_modes must be an int in [1, max_modes]")
        stop = lambda pts: len(pts) >= n_modes
    else:
        if not (lam_max > 0.0) or not math.isfinite(lam_max):
            raise ValueError("lam_max must be positive and finite")
        stop = lambda pts: bool(pts) and pts[-1] > lam_max
    points = _dirichlet_points(geo, ifaces, p.h, scale, stop, max_modes)
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
    for m in modes:
        res = abs(m.lam * m.one - (hA + p.G_rej * m.psi_L))
        ident = max(ident, res / (hA + p.G_rej * abs(m.psi_L) + m.lam * abs(m.one)))
    rot = sum(ell / math.sqrt(alpha) for ell, _k, _rc, alpha in geo)
    diag = {"count": len(modes), "lam_min": modes[0].lam, "lam_max": modes[-1].lam,
            "dirichlet": list(points), "alternation_ok": alternation,
            "max_energy_identity_residual_rel": ident,
            "weyl_estimate_at_lam_max": math.sqrt(modes[-1].lam) * rot / PI,
            "asymptotic_sqrt_lambda_spacing": PI / rot}
    return ModeSet(geo=geo, ifaces=ifaces, area=p.area, C_H=p.C_H, h=p.h, G_rej=p.G_rej,
                   modes=tuple(modes), diagnostics=diag)


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


def schedule_F2(stack: str, event_s: float = 600.0, r_inner_after: float = 2.0e-3, P_body: float = 5.0,
                body_off_s: float = 900.0, P_sensor: float = 0.1):
    """ASSUMPTION: F2 = inner contact resistance change at event_s (default: contract upper bound)."""
    p = nominal_params(stack, P_body=P_body, P_sensor=P_sensor)
    return [(0.0, p), (event_s, replace(p, r_inner=r_inner_after)),
            (body_off_s, replace(p, r_inner=r_inner_after, P_body=0.0))]


DEFAULT_TIMES = (0.0, 1.0, 10.0, 60.0, 300.0, 600.0, 601.0, 660.0, 900.0, 901.0, 960.0, 1800.0, 3600.0)


def run_default_cases(n_modes: Optional[int] = None, times: Sequence[float] = DEFAULT_TIMES) -> dict:
    out = {"contract": "T0-HYP-1", "method": "eigenfunction expansion; transfer matrix; "
           "Dirichlet-interlaced roots", "executed_by": "caller (see Red's run log)",
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
```

## (c) Unit tests

FILE: oracle/test_layered_oracle.py
```python
"""Tests for layered_oracle.py (unittest, stdlib only). Expected values are independent of the
code under test: Coda's exact rational rows (copied verbatim from reference_results.json),
textbook plane-wall series, the one-node exponential, and analytic identities."""
import math
import os
import sys
import unittest
from dataclasses import replace
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layered_oracle as lo  # noqa: E402

# (stack, P_body, blocked, H, S, surface, front, rear) from reference_results.json (Coda)
REFERENCE_ROWS = [
    ("H1", 1, False, 26.90248230028146, 26.891868221020427, 26.85948562324088, 0.14875884985927018, 0.9512411501407299),
    ("H1", 5, False, 33.83119986113005, 33.70398462379287, 33.55500086793716, 0.6844000694349729, 4.415599930565027),
    ("H1", 10, False, 42.492096812190795, 42.21913012725842, 41.92439492380752, 1.3539515939046014, 8.7460484060954),
    ("H1", 5, True, 90.94862037037036, 89.86019444444445, 88.75, 5.1, 0.0),
    ("H2", 1, False, 26.907261860110584, 26.88858113572823, 26.829613374308842, 0.14636906994470728, 0.9536309300552928),
    ("H2", 5, False, 33.86190245732054, 33.6326495680521, 33.36310964174662, 0.6690487713397297, 4.430951228660271),
    ("H2", 10, False, 42.55520320383298, 42.062735108456934, 41.52997997604385, 1.3223983980835077, 8.777601601916492),
    ("H2", 5, True, 92.81899074074074, 90.80463888888889, 88.75, 5.1, 0.0),
    ("H3", 1, False, 26.916159074909697, 26.883744465399086, 26.774005781814406, 0.1419204625451524, 0.9580795374548476),
    ("H3", 5, False, 33.91905575238601, 33.501140687023764, 33.00590154758745, 0.6404721238069959, 4.459527876193004),
    ("H3", 10, False, 42.6726765992314, 41.772885964054616, 40.79577125480375, 1.2636617003843003, 8.836338299615699),
    ("H3", 5, True, 96.55973148148148, 92.69352777777777, 88.75, 5.1, 0.0),
]


def textbook_plane_wall(theta_i, Bi, Fo, xi, nterms=80):
    """Plane wall, insulated face xi=0, convection at xi=1 (Carslaw & Jaeger; Incropera Table 5.1)."""
    total = 0.0
    for n in range(1, nterms + 1):
        lo_, hi_ = (n - 1) * math.pi + 1e-12, (n - 1) * math.pi + math.pi / 2 - 1e-9
        for _ in range(300):
            mid = 0.5 * (lo_ + hi_)
            if mid <= lo_ or mid >= hi_:
                break
            if mid * math.tan(mid) - Bi < 0.0:
                lo_ = mid
            else:
                hi_ = mid
        z = 0.5 * (lo_ + hi_)
        Cn = 4.0 * math.sin(z) / (2.0 * z + math.sin(2.0 * z))
        total += Cn * math.exp(-z * z * Fo) * math.cos(z * xi)
    return theta_i * total


class TestSteady(unittest.TestCase):
    def test_matches_reference_rows(self):
        for stack, P, blocked, H, S, surf, front, rear in REFERENCE_ROWS:
            p = lo.nominal_params(stack, P_body=float(P), G_rej=0.0 if blocked else 0.5)
            st = lo.steady_state(p)
            for got, exp in ((st["H"], H), (st["S"], S), (st["surface"], surf),
                             (st["front"], front), (st["rear"], rear)):
                self.assertAlmostEqual(got, exp, delta=1e-9, msg=f"{stack} P={P} blocked={blocked}")
            self.assertAlmostEqual(st["balance"], 0.0, delta=1e-12)
            self.assertAlmostEqual(st["H_from_profile"], st["H"], delta=1e-9)

    def test_exact_fraction_h1_5w_front(self):
        st = lo.steady_state(lo.nominal_params("H1", P_body=5.0))
        self.assertAlmostEqual(st["front"], float(Fraction(1103951, 1613020)), delta=1e-12)

    def test_profile_interface_jumps(self):
        p = lo.nominal_params("H2", P_body=5.0)
        st = lo.steady_state(p)
        segs = st["segments"]
        for i, r in enumerate(lo.interface_resistances(p)):
            T_minus = segs[i]["T0"] + segs[i]["slope"] * segs[i]["ell"]
            T_plus = segs[i + 1]["T0"]
            self.assertAlmostEqual(T_minus - T_plus, r * segs[i]["q"], delta=1e-12)
        self.assertAlmostEqual(segs[2]["T0"], st["S"], delta=1e-9)
        self.assertAlmostEqual((segs[2]["q"] - segs[1]["q"]) * p.area, p.P_sensor, delta=1e-12)

    def test_long_time_limit_equals_steady(self):
        p = lo.nominal_params("H3", P_body=5.0)
        sol = lo.solve([(0.0, p)], [1.0e6])
        st = lo.steady_state(p)
        self.assertAlmostEqual(sol.temperature("surface", 1.0e6), st["surface"], delta=1e-9)
        self.assertAlmostEqual(sol.temperature("sensor", 1.0e6), st["S"], delta=1e-9)
        self.assertAlmostEqual(sol.temperature("H", 1.0e6), st["H"], delta=1e-9)


class TestModes(unittest.TestCase):
    def test_structure_all_stacks(self):
        for stack in ("H1", "H2", "H3"):
            p = lo.nominal_params(stack)
            ms = lo.compute_modes(p, n_modes=40)
            lams = [m.lam for m in ms.modes]
            self.assertEqual(len(lams), 40)
            self.assertGreater(lams[0], 0.0)
            self.assertTrue(all(b > a for a, b in zip(lams, lams[1:])))
            self.assertTrue(ms.diagnostics["alternation_ok"], stack)
            self.assertLess(ms.diagnostics["max_energy_identity_residual_rel"], 1e-8, stack)
            d = ms.diagnostics["dirichlet"]
            for n in range(39):            # interlacing lam_n < d_n < lam_{n+1}
                self.assertLess(lams[n], d[n])
                self.assertLess(d[n], lams[n + 1])

    def test_orthogonality_and_derivative_identity(self):
        p = lo.nominal_params("H1")
        ms = lo.compute_modes(p, n_modes=12)
        for i in range(12):
            for j in range(i + 1, 12):
                ip = lo._mode_inner(ms, ms.modes[i], ms.modes[j])
                self.assertLess(abs(ip) / math.sqrt(ms.modes[i].norm * ms.modes[j].norm), 1e-8)
        for m in ms.modes:
            eps = 1e-6 * m.lam
            dF = (lo.characteristic(p, m.lam + eps) - lo.characteristic(p, m.lam - eps)) / (2 * eps)
            self.assertAlmostEqual(dF * m.psi_L / m.norm, 1.0, delta=1e-5)

    def test_weyl_count(self):
        for stack in ("H1", "H3"):
            ms = lo.compute_modes(lo.nominal_params(stack), n_modes=60)
            self.assertLessEqual(abs(60 - ms.diagnostics["weyl_estimate_at_lam_max"]), 2.0, stack)

    def test_lam_max_policy_includes_all_below(self):
        p = lo.nominal_params("H2")
        ms = lo.compute_modes(p, lam_max=200.0)
        ref = lo.compute_modes(p, n_modes=len(ms.modes) + 5)
        for a, b in zip(ms.modes, ref.modes):
            self.assertAlmostEqual(a.lam, b.lam, delta=1e-12 * max(1.0, a.lam))
        self.assertGreater(ref.modes[len(ms.modes)].lam, 200.0 - 1e-9)


class TestTransient(unittest.TestCase):
    def test_truncation_convergence(self):
        sched = lo.schedule_F0("H1")
        t = 0.05
        vals = {}
        for N in (6, 12, 24, 48, 96):
            sol = lo.solve(sched, [t], n_modes=N)
            vals[N] = [sol.temperature(loc, t) for loc in lo.LOCATIONS]
        d = {N: max(abs(a - b) for a, b in zip(vals[N], vals[2 * N])) for N in (6, 12, 24, 48)}
        self.assertGreater(d[6], d[24])
        self.assertLess(d[24], 1e-6)
        self.assertLess(d[48], 1e-9)

    def test_energy_balance_F0(self):
        sol = lo.solve(lo.schedule_F0("H1"), [1.0, 10.0, 100.0, 600.0, 900.0, 1000.0, 3600.0])
        for t in (1.0, 10.0, 100.0, 600.0, 900.0, 1000.0, 3600.0):
            a = sol.energy_audit(t)
            self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["input_J"]), t)
        self.assertAlmostEqual(sol.energy_audit(3600.0)["input_J"], 5.0 * 900.0 + 0.1 * 3600.0, delta=1e-9)

    def test_energy_balance_F1_F2_with_events(self):
        for sched in (lo.schedule_F1("H2"), lo.schedule_F2("H3")):
            sol = lo.solve(sched, [601.0, 901.0, 3600.0])
            a = sol.energy_audit(3600.0)
            self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["input_J"]))
            self.assertEqual(len(a["event_energy_jumps_J"]), 2)
            for j in a["event_energy_jumps_J"]:
                self.assertLess(abs(j), 0.05)        # truncation at the projection, J

    def test_initial_energy_defect_decreases(self):
        sched = lo.schedule_F0("H1")
        defects = [abs(lo.solve(sched, [1.0], n_modes=N).energy_audit(1.0)["initial_energy_defect_J"])
                   for N in (8, 32, 128)]
        self.assertGreater(defects[0], defects[1])
        self.assertGreater(defects[1], defects[2])
        self.assertLess(defects[2], 0.1)

    def test_event_state_continuity_F1(self):
        sol = lo.solve(lo.schedule_F1("H1"), [600.0, 600.05])
        self.assertLess(abs(sol.temperature("H", 600.05) - sol.temperature("H", 600.0)), 0.05)
        self.assertLess(abs(sol.temperature("surface", 600.05) - sol.temperature("surface", 600.0)), 0.01)
        self.assertLess(abs(sol.temperature("sensor", 600.05) - sol.temperature("sensor", 600.0)), 0.01)
        seg2 = sol.segments[1]
        self.assertLess(seg2.defect / seg2.theta2, 1e-2)
        sol_big = lo.solve(lo.schedule_F1("H1"), [600.0, 600.05], n_modes=120)
        self.assertLess(sol_big.segments[1].defect / sol_big.segments[1].theta2, seg2.defect / seg2.theta2)

    def test_F2_interface_jump_and_flux_continuity(self):
        sched = lo.schedule_F2("H1")
        sol = lo.solve(sched, [700.0])
        p = sched[1][1]
        x_i = p.outer.thickness + p.film.thickness
        q_minus, q_plus = sol.flux_at(x_i, 700.0, -1), sol.flux_at(x_i, 700.0, +1)
        self.assertLess(abs(q_minus - q_plus), 1e-9 * max(1.0, abs(q_minus)))
        jump = sol.temperature_at(x_i, 700.0, -1) - sol.temperature_at(x_i, 700.0, +1)
        self.assertAlmostEqual(jump, p.r_inner * q_minus, delta=1e-9)
        x_o = p.outer.thickness
        jump_o = sol.temperature_at(x_o, 700.0, -1) - sol.temperature_at(x_o, 700.0, +1)
        self.assertAlmostEqual(jump_o, p.r_outer * sol.flux_at(x_o, 700.0, -1), delta=1e-9)

    def test_blocked_steady_from_F1_segment(self):
        sol = lo.solve(lo.schedule_F1("H1", body_off_s=1.0e9), [700.0])
        st = sol.segments[1].steady
        self.assertAlmostEqual(st["H"], 90.94862037037036, delta=1e-9)
        self.assertAlmostEqual(st["surface"], 88.75, delta=1e-9)


class TestLimits(unittest.TestCase):
    def test_single_slab_textbook(self):
        sil = lo.Layer(0.0005, 0.27, 1030.0, 1500.0)
        film = lo.Layer(5.0e-5, 0.27, 1030.0, 1500.0)
        p = lo.Params(outer=sil, film=film, inner=sil, r_outer=0.0, r_inner=0.0, h=200.0,
                      G_rej=0.0, C_H=0.0, P_body=0.0, P_sensor=0.0, T_amb=25.0, T_res=25.0)
        T_i = 35.0
        sol = lo.solve([(0.0, p)], [1.0, 5.0, 20.0], T_initial=T_i, n_modes=30)
        L = 2 * 0.0005 + 5.0e-5
        Bi, alpha = p.h * L / sil.k, sil.alpha
        for t in (1.0, 5.0, 20.0):
            Fo = alpha * t / (L * L)
            for x in (0.0, 0.3 * L, 0.5 * L, L):
                exp = 25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, (L - x) / L)
                self.assertAlmostEqual(sol.temperature_at(x, t), exp, delta=1e-8, msg=f"t={t} x={x}")
            self.assertAlmostEqual(sol.temperature("surface", t),
                                   25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, 1.0), delta=1e-8)
            self.assertAlmostEqual(sol.temperature("H", t),
                                   25.0 + textbook_plane_wall(T_i - 25.0, Bi, Fo, 0.0), delta=1e-8)

    def test_one_node_limit(self):
        # Coda's predeclared fixture: C 10 J/K, R 2 K/W, P 3 W, T0=Tb=20 C -> 23.792723352971347 at 20 s
        thin = lo.Layer(0.0005, 0.27, 1.0e-6, 1.0)
        film = lo.Layer(5.0e-5, 0.20, 1.0e-6, 1.0)
        p = lo.Params(outer=thin, film=film, inner=thin, h=1.0e-9, G_rej=0.5, C_H=10.0,
                      T_amb=20.0, T_res=20.0, P_body=3.0, P_sensor=0.0)
        sol = lo.solve([(0.0, p)], [20.0], T_initial=20.0)
        self.assertAlmostEqual(sol.temperature("H", 20.0), 23.792723352971347, delta=1e-7)
        self.assertAlmostEqual(sol.temperature("H", 20.0),
                               20.0 + 6.0 * (-math.expm1(-20.0 / 20.0)), delta=1e-7)


class TestValidation(unittest.TestCase):
    def test_rejections(self):
        p = lo.nominal_params("H1")
        for bad in (replace(p, h=0.0), replace(p, h=-1.0), replace(p, C_H=-1.0), replace(p, G_rej=-0.1),
                    replace(p, r_inner=-1e-4), replace(p, area=0.0), replace(p, P_body=math.nan),
                    replace(p, T_amb=math.inf), replace(p, outer=lo.Layer(0.0, 0.27, 1030.0, 1500.0))):
            with self.assertRaises(ValueError):
                lo.validate(bad)
        with self.assertRaises(ValueError):
            lo.compute_modes(p)
        with self.assertRaises(ValueError):
            lo.solve([(1.0, p)], [2.0])
        with self.assertRaises(ValueError):
            lo.solve([(0.0, p), (600.0, lo.nominal_params("H2"))], [700.0])


if __name__ == "__main__":
    unittest.main()
```

FILE: oracle/README.md
```markdown
# Layered semi-analytic oracle (thermal-layered-oracle-001)

Run tests:  `cd oracle && python -B -m unittest -v test_layered_oracle`
Run cases:  `python -B oracle/layered_oracle.py --out <path>/oracle_results.json`
            (prints to stdout if --out is omitted; no other file writes)

Time semantics: t = 0 returns the uniform initial state; an event instant (600 s, 900 s) is
evaluated as the left limit (earlier segment). Default mode count per segment: all eigenvalues
below 50 / max(min requested elapsed time, dt_floor=0.02 s); `n_modes` forces a count.

Scenario assumptions (labelled): F0 body 5 W until 900 s then 0, sensor 0.10 W throughout.
F1 = rear conductance change at 600 s (default G_rej -> 0, blocked), body off at 900 s.
F2 = inner silicone|film contact change at 600 s (default r_inner -> 2.0e-3 m2 K/W, the
contract's sensitivity upper bound), body off at 900 s. Both are parameters of
schedule_F1/schedule_F2; the task did not specify the post-event values.

Not implemented: small-time (erfc) acceleration of the series; Laplace/Talbot alternative;
radiation, in-plane spreading, capacity caps; uncertainty sweeps; sensor-off variants (set
P_sensor=0.0 in the schedule helpers to run them); comparison harness against the FV code.
```

---

## (d) Numerical-risk notes

1. **Clustered eigenvalues from the thin film.** Film-internal resonances begin near λ ≈ α_f(π/ℓ_f)² ≈ 5×10² s⁻¹ (static estimate), where a film mode and a silicone mode can nearly coincide and the local root spacing of F collapses. A naive sign-change scan can miss root pairs there. Mitigation: roots are never scanned; each is bracketed between consecutive Dirichlet-at-H eigenvalues (A.5), where exactly one root exists and the bracket end signs are known analytically (sign q(L;d_j), alternating). Residual risk is in the Dirichlet phase lift itself (step aliasing). Guards: √λ steps of π/8 in natural rotation, adaptive halving if an increment exceeds 1.2 rad or is negative beyond rounding (monotonicity is a theorem, so a negative increment indicates aliasing), `RuntimeError` on failure, plus interlacing, sign-alternation, per-mode energy identity and Weyl-count diagnostics. If a Dirichlet point is missed, the bracket-sign check raises rather than silently dropping modes.

2. **Near-coincidence of λ_n and d_n.** When ψ_n(L)≈0, F is tiny at the bracket end and the root sits within rounding of d_n; bisection then converges to the end point. Accuracy is limited to bisection tolerance (~1e-15 relative), acceptable; the H temperature of such a mode is ≈0 anyway.

3. **Cancellation at small t.** The representation T = T_ss + Σ reconstructs θ₀ = T₀ − T_ss, which for the blocked segment is of order −64 K at the surface (steady 88.75 °C) while the physical change over the first second is small. Errors of truncation/rounding are relative to |θ₀|, not to the small physical change; the data has interface jumps, so coefficients decay only like 1/n and the series exhibits Gibbs behaviour at Δt→0 near interfaces. Mitigation: default `lam_max = 50/Δt` (e^{-50} damping), `dt_floor`, left-limit evaluation at events, tail estimate, and the integral/Parseval defects reported per segment. Not implemented: subtracting the semi-infinite erfc response for Δt ≪ ℓ²/α. Trigonometric integrals with small μℓ (film with the node mode, μℓ ~ 3×10⁻³, static estimate) use series forms to avoid (sin x − x cos x) cancellation.

4. **Truncation error bounds.** For Δt>0, |R_N(x,Δt)| ≤ ‖θ₀‖·sup|ψ̂_n|·Σ_{n>N} e^{−λ_nΔt}, with λ_n ≥ (√λ_N + (n−N)Δ_min)² and Δ_min the smallest subsequent √λ spacing — not available in closed form for the composite slab (the film reduces local spacing near resonances), so `tail_estimate` uses the asymptotic mean spacing and the last five retained |a_nψ_n|: **heuristic, labelled, not a rigorous bound**. Convergence is verified a posteriori by the N → 2N test.

5. **Event projection.** The new-basis expansion of a state with mismatched interface jumps (F2; also F1 because the blocked steady profile has larger jumps) converges in the weighted L² norm; pointwise agreement right after the event at interfaces is only asymptotic. Parseval defect and the energy jump at the event are reported; both should fall with more modes (tests).

6. **Energy audit scope.** The closed-form residual is exactly zero per mode when λ_n is an exact root (A.4), so a small residual tests root accuracy and the steady profile, not completeness; completeness/truncation is what `initial_energy_defect_J`, `event_energy_jumps_J` and the Parseval defects measure.

7. **Transfer-matrix growth.** Entries grow like k_iμ_i ∝ √λ; for ≤800 modes no overflow or renormalisation issue is expected, but the normalisation ψ(0)=1 makes high-mode amplitudes in the inner layers vary with impedance mismatch; coefficients a_n absorb this (a_n = ⟨θ₀,ψ_n⟩/N_n), so results are scale-invariant.

8. **Model-level caveats (unchanged from the contract).** 1-D, no radiation/in-plane/human contact; the reservoir is ideal; 40/60 °C are study comparators only. Agreement between this oracle and the finite-volume code checks mathematics, not hardware.

**Unexecuted claims to be checked by Red's run:** all tolerances in the tests are static expectations; the phase-lift step argument (A.5, increments < π) is a heuristic bound; expected mode counts (e.g. ~6 for H1 at Δt=1 s, ~22 for H3) are order-of-magnitude estimates. Please return the full unittest log and the JSON so I can review discrepancies and correct the derivation or code.