# thermal-layered-oracle-fix-003 — diagnosis, fix, and trust assessment (Claude for Red)

Provenance: analysis, patched module and tests below are by Claude (Anthropic) for Red, working with Richard (Andrei) Pemberton in The Stage, on top of the wave-10 oracle (Claude). Steady network and reference rows: Coda (Codex Lily). Earlier packet contributions: Claude Fable 5.1. **Nothing below has been executed by me**; the only executed numbers are those in Red's receipts, quoted as such. Every other number is a static estimate derived from the model constants and is labelled "(static)". This is private computational research on a model; no safety claim.

---

## 1. Diagnosis from the code and the executed numbers

### 1.1 `test_structure_all_stacks` (H1, 40 modes): residual 2.85e-08 > 1e-08 — **threshold artefact (ill-conditioned metric), not a root error**

Exact identity (new A.11 below): for the propagated solution at *any* λ, integrating (kψ')' = −λρcψ over each segment and using continuity of q gives

  λ⟨1,ψ⟩ − hAψ(0) − Gψ(L) = F(λ)  exactly.

So the "energy identity residual" is literally |F(λ̂)| at the computed root, and by A.5, F'(λ_n) = N_n/ψ_n(L). With C_H = 20 J/K (larger than the whole H1 slab capacity, ≈16 J/K, static) the H end is Dirichlet-like for λ ≫ k₄A/(C_H√α₄))² ≈ 0.1 s⁻¹ (static): ψ_n(L) ≈ −Aq_n(L)/(λ_nC_H) → 0, so F'(λ_n) = N_n/|ψ_n(L)| ∝ λ_n·(mode amplitude). The bisection returns λ̂ within ≈1 ulp of the root of the *computed* F; the computed-F noise is ≪ F'·ulp. Static estimate for H1 mode 39 (λ₃₉ ≈ 2×10³ s⁻¹): ulp ≈ 4.5e-13, N/|ψ_L| ≈ 10³–10⁴ ⇒ |F(λ̂)| ≈ 10⁻⁹…10⁻⁸ against a denominator ≈ 2hA = 0.16 ⇒ relative residual 10⁻⁸ — exactly the observed 2.85e-08. The residual grew from 7e-12 (λ_max = 43.6, executed) to 2.85e-8 at λ ≈ 2×10³ because the metric scales like λ × amplitude; the underlying root error is δλ/λ ≈ 10⁻¹⁶. The right quantity is the conditioning-corrected estimate res·|ψ_L|/(N_n λ_n) ≈ |δλ|/λ, bounded by a few ulps; tolerance 1e-13 (≈450 ulps) is adopted; a wrong or missed root would give O(1).

### 1.2 `test_weyl_count` (H1, 60 modes): |60 − E| = 2.746 > 2.0 — **wrong threshold; no evidence of missed roots**

E = √λ₅₉·rot/π with rot = Σℓ/√α = 2.531 s^{1/2} for H1 (confirmed by the executed spacing π/rot = 1.24114). 60 − E = 2.746 ⇒ E = 57.25 ⇒ λ₅₉ ≈ (57.25·1.2411)² ≈ 5.0×10³ s⁻¹ (static). At that λ the contact resistances are no longer transparent: r·k_s·μ_s = 2e-4·0.27·√(5050/1.75e-7) ≈ 9 (static) ≫ 1, i.e. the interfaces are nearly insulating for the modes, and each interface adds a Prüfer phase in [0, π) (new A.9). The Weyl offset N − E therefore drifts from ≈1.5 in the transparent regime (½ from near-Neumann/Dirichlet ends + 1 for the node mode) toward the decoupled-limit range (1.5, 3.5], mean 2.5. The executed nine case sets (λ_max ≈ 43–48, r k μ ≈ 0.85, static) all show N − E = 1.68–1.69, the transparent value plus a small partial-interface phase. Rigorous bracket by Dirichlet–Neumann decoupling of the quadratic form (new A.10): **E − 3 < N(λ) < E + 4 for every λ**, i.e. −3 < N − E < 4. The old tolerance 2.0 was a transparent-regime heuristic.

### 1.3 Could roots have been missed or duplicated anyway?

- A single missed Dirichlet point is impossible to hide: q(L;d_j) alternates rigorously, so the bracket-sign check would have raised `RuntimeError`; no run raised. Duplicates are excluded by strict monotonicity of the lifted phase (each level crossed once).
- The only silent failure mode of the old scan is an aliased step (true increment of the fixed-scale angle in [2π, 2π+1.2]), which needs ≳2π of phase in one √λ step of π/(8·rot). Static analysis (A.9 remark): a sharp interface jump contributes <π, the thin film's interface phase is spread over Δ√λ ≈ 1 ≫ step, and the fixed-scale distortion adds <π but cannot bring the total to 2π unless the natural increment itself is ≈2π. So for these stacks aliasing was excluded, but the A.5 heuristic "increments < π" was wrong in the decoupled regime (a step can carry ≈π + distortion). The fix removes the issue by construction (exact lifted phase, no wrapping) and adds two independent cross-counts.
- Loop masking: both failing tests iterate H1 first, so H2/H3 were never checked by those assertions. The new tests use `subTest`.

### 1.4 Verdict on the 9 executed case results

**They can be trusted as solutions of the stated model at the tabulated times.** Evidence: steady state equals Coda's exact rows (test passed); all nine mode sets have `alternation_ok`, passed the bracket-sign check, show the expected transparent-regime Weyl offset 1.68–1.69, identity residuals ≤ 5e-11 (consistent with the conditioning analysis at λ ≤ 48), energy-audit residuals ~10⁻¹² J, initial-energy defects ≤ 8e-7 J, tail estimates ~10⁻²⁹ K at Δt = 1 s. The default policy keeps all eigenvalues below 50/Δt_min, so truncation error at every tabulated time (Δt ≥ 1 s after each segment start) is ≲ e^{−47}·|θ₀| — negligible. Caveats that are not root-finding issues: (i) the F2 post-event projection has relative Parseval defect 4.9e-4 (H1) / 2.2e-5 (H3) because the r_inner change mismatches the interface jump; the missing content lives at λ > 47 and is irrelevant for Δt ≥ 1 s, but values within ~0.02 s after 600 s would not be resolved (none tabulated); (ii) F1/F2 definitions remain labelled assumptions; (iii) the four H2/H3 cases omitted by Red for size were not inspected here. Re-running the patched module should reproduce the rows to ≲10⁻¹² K (eigenvalues unchanged up to ≤1 ulp; only the bracket-location method changed). The new `sturm_index_ok` and the argument-principle test are the independent confirmation Red's run will provide.

---

## 2. Derivation addendum

**A.9 Exact lifted phase and Sturm index.** In segment i, with natural scale c_i = 1/(k_iμ_i), the angle θ = atan2(c_i q, ψ) satisfies (ψ, c_i q)' = μ_i(−c_i q, ψ), hence θ' = μ_i exactly: the lift advances by μ_iℓ_i. A change of scale c → c' at fixed state keeps sign ψ and sign q, so the lifted change is the plain atan2 difference (|Δ| < π/2, no wrap). The interface map (ψ,q) → (ψ − rq, q) keeps q, so the lifted jump is again the plain atan2 difference; dθ/dr = c q²/(ψ²+c²q²) ≥ 0 and the state never crosses q = 0, so the jump lies in [0, π). Anchored at θ(0) = atan2(−c₁h, 1) ∈ (−π/2, 0), Θ_L(λ) is continuous and strictly increasing on λ > 0 with Θ_L(0⁺) → −π/2, and ψ(L;λ) = 0 ⇔ Θ_L ≡ π/2 (mod π). Hence #{Dirichlet points in (0,λ]} = ⌊(Θ_L − π/2)/π⌋ + 1 (0 if Θ_L < π/2), computed with no modular ambiguity; the Dirichlet brackets are the level crossings of a monotone function, found by bisection. By interlacing λ_n ∈ (d_{n−1}, d_n), so this count evaluated at a computed eigenvalue must equal its position n (Sturm index) — an x-sweep at fixed λ, independent of the λ-sweep that produced the brackets. Margin (static): at λ_n the phase sits ≈ atan(Ak₄/(C_H√(α₄λ))) above the level (≈5e-3 rad at λ ≈ 5×10³), far above rounding.

**A.10 Rigorous Weyl bracket.** Restrict the form domain by f = 0 on both sides of both interfaces and f(L) = f_H = 0 (min–max: eigenvalues rise): N(λ) ≥ N^{RD}(ℓ₁) + N^{DD}(ℓ_f) + N^{DD}(ℓ₄) ≥ Σ⌊x_i⌋ > E − 3, with x_i = √λℓ_i/(π√α_i). Enlarge it by dropping the [f]²/r terms and the constraint f(L) = f_H (eigenvalues fall; the node becomes a free 1-D mode G/C_H): N(λ) ≤ N^{RN}(ℓ₁) + N^{NN}(ℓ_f) + N^{NN}(ℓ₄) + 1 ≤ Σ⌊x_i⌋ + 4 ≤ E + 4. Thus −3 < N − E < 4 whenever the found set is complete. Weak as a completeness test (a skipped root shifts E by one spacing), hence the cross-counts.

**A.11 Identity residual = |F(λ̂)|** (Section 1.1), amplified by N_n/|ψ_n(L)|; test the conditioning-corrected estimate res·|ψ_L|/(N λ) ≈ |δλ|/λ.

**Argument principle (new cross-count).** F is entire of order ½ in λ (cos μℓ, sin(μℓ)/μ, μ sin μℓ are even in μ) and all its zeros are real and positive (A.4), so the winding number of F around a rectangle [−c, b] × [−c, c] equals the number of eigenvalues below b. Adaptive sampling accepts a step only if |Δarg| ≤ π/4 with initial steps ≤ c/8; the count is recomputed with height c/3 and must agree.

---

## 3. Minimal diff summary (what changed; full files follow)

`oracle/layered_oracle.py`
1. `import cmath`; header docstring note.
2. **New** `lifted_terminal_phase(geo, ifaces, h, lam)`, `_level_count`, `sturm_index(p, lam)` (A.9).
3. **Rewritten** `_dirichlet_points(geo, ifaces, h, stop, max_points)`: exact lifted phase, monotonicity assertion, bisection on levels; parameter `scale` removed (no wrap-lift, no adaptive halving).
4. `compute_modes`: drop `scale`; new diagnostics `max_root_rel_error_est`, `sturm_index_ok`, `dirichlet_residual_max`, `weyl_offset`, `weyl_offset_bounds_open`.
5. **New** `_propagate_c`, `characteristic_c`, `count_zeros_argument_principle(p, lam_hi, lam_lo=None, half_height=None, verify=True, max_evals=400000)`.
6. `run_default_cases`: method string updated. Everything else verbatim.

`oracle/test_layered_oracle.py`
7. `test_structure_all_stacks`: `subTest`; `max_root_rel_error_est < 1e-13`; raw identity residual loose cap 1e-6 (documented); `sturm_index_ok`; `dirichlet_residual_max < 1e-9`; interlacing kept.
8. `test_weyl_count` → `test_weyl_count_rigorous_bracket`: all stacks, −3 < 60 − E < 4.
9. **New** `test_cross_count_sturm_index`, `test_cross_count_argument_principle`, `test_lifted_phase_monotone_and_dirichlet_zero`. Other 14 tests unchanged.

---

## 4. Files

FILE: oracle/layered_oracle.py
```python
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


def schedule_F2(stack: str, event_s: float = 600.0, r_inner_after: float = 2.0e-3, P_body: float = 5.0,
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
```

FILE: oracle/test_layered_oracle.py
```python
"""Tests for layered_oracle.py (unittest, stdlib only). Expected values are independent of the
code under test: Coda's exact rational rows (copied verbatim from reference_results.json),
textbook plane-wall series, the one-node exponential, and analytic identities.

Fix 003: the mode-structure test uses the conditioning-corrected root-accuracy estimate
(derivation A.11), the Weyl test uses the rigorous Dirichlet-Neumann bracket (A.10), and two
independent cross-counts are added (Sturm index, A.9; argument principle on complex F)."""
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
            with self.subTest(stack=stack):
                p = lo.nominal_params(stack)
                ms = lo.compute_modes(p, n_modes=40)
                lams = [m.lam for m in ms.modes]
                self.assertEqual(len(lams), 40)
                self.assertGreater(lams[0], 0.0)
                self.assertTrue(all(b > a for a, b in zip(lams, lams[1:])))
                self.assertTrue(ms.diagnostics["alternation_ok"])
                self.assertTrue(ms.diagnostics["sturm_index_ok"])
                # Root accuracy, conditioning-corrected (A.11): |dlam|/lam; 1e-13 ~ 450 ulp.
                self.assertLess(ms.diagnostics["max_root_rel_error_est"], 1e-13)
                # Raw identity residual == |F(lam_hat)|, amplified by N_n/|psi_n(L)| ~ lam_n;
                # informational, loose sanity cap only (a wrong root would be O(1)).
                self.assertLess(ms.diagnostics["max_energy_identity_residual_rel"], 1e-6)
                self.assertLess(ms.diagnostics["dirichlet_residual_max"], 1e-9)
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

    def test_weyl_count_rigorous_bracket(self):
        # Dirichlet-Neumann bracketing (A.10): E - 3 < N(lam) < E + 4 for every lam, so with the
        # N-th found eigenvalue -3 < N - E < 4. The old tolerance 2.0 only held in the
        # transparent-interface regime (r k mu << 1); at lam ~ 5e3 1/s (H1, 60 modes) the
        # interfaces decouple and N - E drifts toward the decoupled range (1.5, 3.5].
        for stack in ("H1", "H2", "H3"):
            with self.subTest(stack=stack):
                ms = lo.compute_modes(lo.nominal_params(stack), n_modes=60)
                off = 60 - ms.diagnostics["weyl_estimate_at_lam_max"]
                self.assertGreater(off, -3.0)
                self.assertLess(off, 4.0)
                self.assertAlmostEqual(off, ms.diagnostics["weyl_offset"], delta=1e-12)

    def test_cross_count_sturm_index(self):
        # Independent per-root count (A.9): the lifted phase at each eigenvalue, swept in x at
        # fixed lam, must place it at its own index. A missed root shifts all later indices.
        for stack in ("H1", "H2", "H3"):
            for over in ({}, {"G_rej": 0.0}, {"r_inner": 2.0e-3}):
                with self.subTest(stack=stack, over=over):
                    p = lo.nominal_params(stack, **over)
                    ms = lo.compute_modes(p, n_modes=60)
                    for n, m in enumerate(ms.modes):
                        self.assertEqual(lo.sturm_index(p, m.lam), n)
                    self.assertTrue(ms.diagnostics["sturm_index_ok"])

    def test_cross_count_argument_principle(self):
        # Fully independent of the Dirichlet bracketing: winding number of the entire function
        # F around a rectangle enclosing (0, b) counts the zeros below b exactly.
        for stack in ("H1", "H2", "H3"):
            with self.subTest(stack=stack):
                p = lo.nominal_params(stack)
                ms = lo.compute_modes(p, n_modes=61)
                lams = [m.lam for m in ms.modes]
                b = 0.5 * (lams[59] + lams[60])
                self.assertEqual(lo.count_zeros_argument_principle(p, b), 60)
        # The default lam_max policy sets used by the nine cases: all zeros below the last
        # Dirichlet point must be exactly the modes found.
        for p in (lo.nominal_params("H1", G_rej=0.0), lo.nominal_params("H1", r_inner=2.0e-3),
                  lo.nominal_params("H3", r_inner=2.0e-3)):
            with self.subTest(G_rej=p.G_rej, r_inner=p.r_inner, L=p.outer.thickness):
                ms = lo.compute_modes(p, lam_max=50.0)
                d_last = ms.diagnostics["dirichlet"][-1]
                self.assertEqual(lo.count_zeros_argument_principle(p, d_last), len(ms.modes))

    def test_lifted_phase_monotone_and_dirichlet_zero(self):
        p = lo.nominal_params("H1")
        geo, ifaces = lo.segment_geometry(p), lo.interface_resistances(p)
        prev = -math.inf
        for i in range(1, 400):
            s = 0.25 * i
            th = lo.lifted_terminal_phase(geo, ifaces, p.h, s * s)[0]
            self.assertGreater(th, prev)
            prev = th
        ms = lo.compute_modes(p, n_modes=30)
        for j, d in enumerate(ms.diagnostics["dirichlet"]):
            th, psiL, qL = lo.lifted_terminal_phase(geo, ifaces, p.h, d)
            self.assertAlmostEqual(th, 0.5 * math.pi + j * math.pi, delta=1e-9)
            self.assertEqual(lo.sturm_index(p, ms.modes[j].lam), j)

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
# Layered semi-analytic oracle (thermal-layered-oracle-001, fix 003)

Run tests:  `cd oracle && python -B -m unittest -v test_layered_oracle`   (21 tests expected)
Run cases:  `python -B oracle/layered_oracle.py --out <path>/oracle_results.json`
            (prints to stdout if --out is omitted; no other file writes)

Time semantics: t = 0 returns the uniform initial state; an event instant (600 s, 900 s) is
evaluated as the left limit (earlier segment). Default mode count per segment: all eigenvalues
below 50 / max(min requested elapsed time, dt_floor=0.02 s); `n_modes` forces a count.

Root finding (fix 003): Dirichlet-at-H brackets are the level crossings of the EXACT lifted
Prufer phase (no modular wrap-around); one eigenvalue per bracket by sign bisection. Per-mode
diagnostics: `sturm_index_ok` (each root at its own Sturm index), `max_root_rel_error_est`
(conditioning-corrected |dlam|/lam, expect <= 1e-13), `max_energy_identity_residual_rel`
(raw |F(lam_hat)|-based residual, amplified by N_n/|psi_n(L)| ~ lam_n; informational),
`weyl_offset` with its rigorous open bracket (-3, 4). `count_zeros_argument_principle(p, b)`
gives an independent zero count below b (complex contour; used in the tests).

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

## 5. What to expect from the re-run, and what is not done

Expected (static, unexecuted): all 21 tests pass; the nine case JSONs reproduce the earlier rows to ≲10⁻¹² K with the new diagnostics `sturm_index_ok: true`, `max_root_rel_error_est` ≲ 10⁻¹⁵, `weyl_offset` ≈ 1.68–1.69 for all nine sets. If `max_root_rel_error_est` comes out between 1e-15 and 1e-13 the tolerance is simply generous; if it exceeds 1e-13 for any set, that would indicate a genuine root-accuracy problem and I would want the per-mode values. If the argument-principle test raises "counts disagree" or "step did not resolve" for one stack, please return the stack, `b` and the two counts — that would be a sampling issue in my contour walk, not evidence about the roots (the Sturm test is the primary check).

Static-reasoning caveats: (i) the per-step phase margins quoted in 1.3 and A.9 are order-of-magnitude estimates for the three nominal stacks; the exact-lift scan removes the dependence on them. (ii) The rigorous Weyl bracket is weak as a completeness test by design; completeness rests on A.5/A.9 and is cross-checked by the two new tests. (iii) The argument-principle walk's aliasing argument assumes at most two eigenvalues cluster near the contour edge (true for a three-slab structure in the decoupled limit); the `verify=True` recomputation guards the remaining risk.

Not implemented (unchanged): erfc small-time acceleration; Laplace/Talbot cross-check of the time series; FV comparison harness; the four H2/H3 compact-JSON cases omitted by Red were not reviewed line by line.