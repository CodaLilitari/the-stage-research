Red — this is the **computational half** of release-observability-002b. Everything below is static reasoning plus code I have **not executed**. Red runs it; the numbers in the predictions are *predeclared expectations*, not results.

## 0. Scope and credit

- Model and stable-evaluation formulas (`r_f, r_s, Δ`, `expm1` divided exponential, stable release identity): **Lilitari (Lily), AB-LFR1 DERIVATION.md / benchmark.py**. My code does not import `benchmark.py`; it re-derives the eigenmode amplitudes from the same ODE and uses REPORT.md terminal rows (as quoted by Lily and in Muse Code's script) only as *cross-check values*.
- Decimal-60 reproduction and log-k sweep: **Muse Code** (via INTAKE.md). Not reused as code; its documented limitation (binary64 conversion before tiny differences) motivated the cancellation-free difference forms below.
- Study design, difference forms, impostor construction, projection theorem, code and tests: **Claude (Anthropic), this request**, coordinated by Red for Richard (Andrei) Pemberton; original task text by Coda.
- Synthetic model only. No biology, hardware, efficacy, or fit to real data.

## 1. Predeclared study specification (fixed before any execution)

**Model (known structure).** `c' = -(α+kγ)c + kb`, `b' = kγc - kb`, `c(0)=c0`, `b(0)=γc0`. Release flux `J = k(b-γc) = -b'`. Equilibrium (separate algebraic model): `c_eq = c0 e^{-αt/(1+γ)}`, `b_eq = γc_eq`, `J_eq = -b_eq' = αγc0/(1+γ)·e^{-αt/(1+γ)}`. Study restriction: `α, k, γ, c0 > 0` (real distinct rates).

**Parameter sets.** Family A: `α=1, γ=4, c0=1, T=1`, `k ∈ {1,10,100,1000,10000}`. Family B (C19-like dimensional coordinates): `α=0.5, γ=4, c0=0.2, T=3`, `k ∈ {2,20,200}`. Separate asymptotic probes: `k=10⁶` (test), `k=10¹²` (stiff-flux diagnostic only).

**Observables.** `c`, `b`, joint `(c,b)`, genuine independent release flux `J` (own noise), and a flux *computed* from the same `b` samples by first differences `Ĵ_i = -(y_{i+1}-y_i)/Δt`. (Sink flux `αc` is proportional to `c` and is not a separate observable.)

**Time grids.** `t_i = t_start + i(T-t_start)/n`, `i=1..n`, `n ∈ {1,4,16,64,256,1024,4096,16384}`; windows: full (`t_start=0`) and late (`t_start=T/2`). `n=1` is the single endpoint observation. Boundary-layer resolution criterion: `n_res(k) = ⌈T·r_f⌉` (`Δt ≤ 1/r_f`, `r_f ≈ k(1+γ)`).

**Noise model and normalization.** Additive iid Gaussian noise per sample, with relative precision `ε`: `σ_c = εc0`, `σ_b = εγc0`, `σ_J = ε·αγc0/(1+γ)` (quasi-steady release flux scale). Joint `(c,b)` counts as `2n` samples. Per-sample noise does not shrink with denser sampling (declared assumption; the alternative fixed-budget reading is recovered from the reported RMS, see §2.6).

**Known vs nuisance.** Scenario K (all of `α, γ, c0` known/calibrated): statistic is the matched filter with separation `d = ‖δ‖/σ`, `δ = μ_finite − μ_eq`. Scenario N (nuisance free in the equilibrium model): the separation is bounded above by the residual against the *slow-mode impostor* equilibrium model (§2.3): `c`-only and `b`-only with `(c0', α')` free; `J` with `(c0', γ', α')` free; joint `(c,b)` with `(c0', α')` free (γ calibrated) and with `(c0', γ', α')` free. The impostor residual is an **upper bound** on the true nuisance-minimized separation and is used as the identifiability indicator.

**Decision criteria.** Two simple Gaussian hypotheses with midpoint threshold have total error `Φ(−d/2)`. Decision rule: "distinguishable at precision ε with N samples" iff `d = √N·RMS/ε ≥ D* = 2·z₀.₉₅ = 3.2897` (size 5%, power 95%; equivalently Bayes error ≤ 5% with equal priors). Required precision `ε_req = √N·RMS/D*`. `RMS = sqrt(mean((δ/scale)²))` over all components.

**Monte Carlo cells (deterministic seeds, 1000 replicates per hypothesis).** Family A, `k=100`, `n=64`, full window; for each of `c`, `b`, `J`: `σ` calibrated by rule `σ = ‖δ‖/3` (predicted error `Φ(−1.5)=0.0668`). For the computed flux: `σ_b = ‖δ_b‖/3`; the naive filter (treats difference noise as independent) has predicted realized error `Φ(−d_real/2)`, while an analyst ignoring correlation would predict `Φ(−d_naive/2)`. Agreement tolerance: `|p_emp − p_pred| ≤ 3·sqrt(p_pred(1−p_pred)/(2·reps))`.

**Predeclared predictions** (evaluated PASS/FAIL by the runner; defaults assume the full grid list):
- **P1** (structural non-identifiability, late window, A, `k ≥ 10`, `n = n_max`): impostor-bound RMS for `c`, `b`, `J`, `(c,b)` with γ free all `≤ 1e-6`; joint `(c,b)` with γ known `≥ 0.05/k`.
- **P2** (resolved independent flux dominates, full window, `n_max ≥ n_res`): `RMS_J ≥ 2·max(RMS_c, RMS_b)`.
- **P3** (computed-flux theorems, every full-window cell, `n ≥ 2`): `d_real ≤ d_comp ≤ d_b` (to 1e-12 relative).
- **P4a** (A, `k=1000`, `T=1`): exact endpoint `δ/scale` within 5% of the leading-order formulas of §2.4 for `c, b, J`. **P4b** (blind spots): `|δ_c(T=5)|` and `|δ_J(T=3.75)|` at `k=1000` vs `k=100` have ratio `≤ 0.03` (∝1/k², not 1/k).
- **P5a** (A, `4·n_res ≤ n_max`): `RMS_J(n_max) ∈ [0.7,1.3]·(2r_fT)^{-1/2}`. **P5b** (A, `n_res > n_max`, i.e. `k=10⁴`): `RMS_J(n_max) ≤ 0.5·(2r_fT)^{-1/2}`. **P5c** (A, resolved k): `RMS_J(n_max)/RMS_J(4)` nondecreasing in k.
- **P6**: MC error rates within tolerance of `Φ(−d/2)` (`d_real` for the computed flux).

**Precision statement.** All model differences are evaluated in cancellation-free forms (§2.2) with relative accuracy ≈1e-14 on the declared sets (static estimate: a few ulps of the larger term). Direct subtraction `c − c_eq` at `k=10¹²` carries ≈2e-16 absolute error on a 1.05e-13 difference (≈0.2% relative); the REPORT value `1.04694e-13` is therefore checked only to 1e-15 absolute. No claim is made beyond this.

## 2. Derivations the code relies on (static)

**2.1 Modes.** With `S=α+k(1+γ)`, `h=α+kγ−k`, `Δ=sqrt(h²+4k²γ)`, `r_f=(S+Δ)/2`, `r_s=αk/r_f`, eigenvector ratios `q(r)=kγ/(k−r)`, and `c'(0)=−αc0`:
`A_c = c0(r_f−α)/Δ`, `B_c = c0(α−r_s)/Δ`, `A_b = γc0 r_f/Δ`, `B_b = −γc0 r_s/Δ` (using `r_s(r_f−α)=α(k−r_s)` and `r_f(α−r_s)=α(r_f−k)`), so `c=A_c e_s+B_c e_f`, `b=A_b e_s+B_b e_f`, `J = αγc0 (k/Δ)(e_s−e_f) = αγc0 κ e_s(−expm1(−Δt))`. Stable pieces: `r_f−α=(h₂+Δ)/2` with `h₂=k(1+γ)−α`, `Δ²−h₂²=4kγα`; `r_f−k=(h+Δ)/2`, `Δ²−h²=4k²γ`.

**2.2 Cancellation-free differences** (`r_eq=α/(1+γ)`, `shift=r_eq−r_s=2α²kγ/((h₂+Δ)r_f(1+γ))>0`, `g₁=expm1(shift·t)`, `g₂=expm1(−(r_f−r_eq)t)`):
`δ_c/c0 = e_eq[A_c g₁+B_c g₂]/c0`, `δ_b/b0 = e_eq[A_b g₁+B_b g₂]/(γc0)`, `δ_J/J_scale = κ_d e_s + e_eq g₁ − κ(1+γ)e_f`, with `κ=k/Δ`, `κ_d=κ(1+γ)−1=(2kα(1−γ)−α²)/(Δ(k(1+γ)+Δ))`.

**2.3 Impostor.** Equilibrium model with `(c0',γ',α') = (A_c, A_b/A_c, r_s(1+A_b/A_c))` reproduces the finite-k *slow modes* of `c`, `b`, and `J` exactly; the residual is exactly the fast mode: `(B_c e_f, B_b e_f, −αγc0κe_f)`. Hence late-window data (`t ≫ 1/r_f`) cannot distinguish finite k from equilibrium when those parameters are free (counterexample to "both pools identify k"). With γ calibrated, the joint residual is at least `(α/2Δ)e_s(1,−1)` in relative units — `O(1/k)` and persistent.

**2.4 Endpoint leading order** (`T ≫ 1/r_f`, pref `= αe_eq(T)/(k(1+γ)²)`): `δ_c/c0 ≈ pref·γ(αT/(1+γ)−1)`, `δ_b/b0 ≈ pref·(αγT/(1+γ)+1)`, `δ_J/J_scale ≈ pref·(αγT/(1+γ)+1−γ)`. Blind spots: `c` at `T=(1+γ)/α`, `J` at `T=(γ−1)(1+γ)/(αγ)`; `b` has none. For family A, `T=1`: `δ_c/c0 ≈ −0.1048/k` (REPORT: 1.047617e-3 at k=100).

**2.5 Computed flux.** With `D` the first-difference operator, `f=−Dy/Δt`, `Cov f = σ²DDᵀ/Δt²`. GLS separation `d_comp² = δᵀDᵀ(DDᵀ)⁻¹Dδ/σ² = ‖δ−δ̄𝟙‖²/σ²` (projector onto `𝟙⊥`): the computed flux loses exactly the grid mean of `δ_b`, nothing else. Naive filter `w=Dδ`: reported `d_naive=‖Dδ‖/(√2σ)`, realized `d_real=‖Dδ‖²/(σ‖DᵀDδ‖) ≤ d_comp ≤ d_b` (Cauchy–Schwarz / optimality).

**2.6** Under the fixed-budget alternative (`σ² ∝ n`), the index is `√n_ref·RMS/ε`; RMS tables therefore serve both readings.

## 3. Files

FILE: release_model.py
```python
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
```

FILE: release_study.py
```python
"""release_study.py -- predeclared synthetic measurement study: which observable,
time resolution and precision separate finite k from the algebraic-equilibrium
model (AB-LFR1 linear release model).  The Stage, task release-observability-002b
(computational half).  Claude (Anthropic), coordinated by Red for Richard
(Andrei) Pemberton.  Standard library only; deterministic; writes only to a
caller-supplied --out path.  Synthetic model only: no biology, no hardware
recommendation, no fit to real measurements.

Usage:  python release_study.py [--out results.json] [--reps 1000] [--max-n 16384]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from typing import Dict, List, Optional, Sequence

import release_model as rm

Z95 = 1.6448536269514722
D_STAR = 2.0 * Z95

FAMILIES: Dict[str, dict] = {
    "A": {"alpha": 1.0, "gamma": 4.0, "c0": 1.0, "T": 1.0,
          "ks": [1.0, 10.0, 100.0, 1000.0, 10000.0]},
    "B": {"alpha": 0.5, "gamma": 4.0, "c0": 0.2, "T": 3.0,
          "ks": [2.0, 20.0, 200.0]},
}
GRID_SIZES: List[int] = [1, 4, 16, 64, 256, 1024, 4096, 16384]
WINDOWS: Dict[str, float] = {"full": 0.0, "late": 0.5}
OBSERVABLES = ("c", "b", "cb", "J")
EPSILONS = (1e-2, 1e-3, 1e-4)
MC_SPEC = {"family": "A", "k": 100.0, "n": 64, "target_index": 3.0, "reps": 1000,
           "seeds": {"c": 20261101, "b": 20261102, "J": 20261103,
                     "computed_flux_from_b": 20261104}}


# ---------------------------------------------------------------- utilities
def phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def time_grid(T: float, n: int, start_frac: float = 0.0) -> List[float]:
    if n < 1:
        raise ValueError("n must be >= 1")
    t0 = start_frac * T
    return [t0 + (i + 1) * (T - t0) / n for i in range(n)]


def norm(xs: Sequence[float]) -> float:
    return math.sqrt(math.fsum(x * x for x in xs))


def rms(xs: Sequence[float]) -> float:
    return norm(xs) / math.sqrt(len(xs))


def computed_flux_indices(delta_b: Sequence[float]) -> Dict[str, float]:
    """Separation indices (per unit noise sigma) for a flux computed by first
    differences of the same b samples.  d_b: raw samples; d_comp: GLS-optimal use
    of the computed flux (= mean-removed delta); d_naive: index an analyst reports
    when treating difference noise as independent; d_real: actual deflection of
    that naive filter.  Theorem: d_real <= d_comp <= d_b."""
    n = len(delta_b)
    if n < 2:
        raise ValueError("need n >= 2")
    mean = math.fsum(delta_b) / n
    d_b = norm(delta_b)
    d_comp = norm([x - mean for x in delta_b])
    diff = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nd = norm(diff)
    d_naive = nd / math.sqrt(2.0)
    dtd = [(diff[j - 1] if j >= 1 else 0.0) - (diff[j] if j <= n - 2 else 0.0) for j in range(n)]
    ndtd = norm(dtd)
    d_real = (nd * nd / ndtd) if ndtd > 0.0 else 0.0
    return {"d_b": d_b, "d_comp": d_comp, "d_naive": d_naive, "d_real": d_real,
            "ratio_comp": d_comp / d_b if d_b > 0 else 0.0,
            "ratio_naive": d_naive / d_b if d_b > 0 else 0.0,
            "ratio_real": d_real / d_b if d_b > 0 else 0.0}


# ---------------------------------------------------------------- Monte Carlo
def mc_direct(delta: Sequence[float], sigma: float, reps: int, seed: int) -> float:
    """Empirical total error of the matched filter with midpoint threshold."""
    rng = random.Random(seed)
    nd2 = math.fsum(d * d for d in delta)
    thresh = 0.5 * nd2
    err = 0
    for _ in range(reps):
        s0 = math.fsum(d * rng.gauss(0.0, sigma) for d in delta)
        if s0 > thresh:
            err += 1
        s1 = nd2 + math.fsum(d * rng.gauss(0.0, sigma) for d in delta)
        if s1 <= thresh:
            err += 1
    return err / (2 * reps)


def mc_computed_flux(delta_b: Sequence[float], sigma: float, reps: int, seed: int) -> float:
    """Empirical total error of the naive matched filter applied to first differences."""
    rng = random.Random(seed)
    n = len(delta_b)
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    thresh = 0.5 * nw2
    err = 0
    for _ in range(reps):
        e = [rng.gauss(0.0, sigma) for _ in range(n)]
        s0 = math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
        if s0 > thresh:
            err += 1
        e = [rng.gauss(0.0, sigma) for _ in range(n)]
        s1 = nw2 + math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
        if s1 <= thresh:
            err += 1
    return err / (2 * reps)


# ---------------------------------------------------------------- analysis
def evaluate_arrays(p: rm.Params, m: rm.Modes, grid: Sequence[float]) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {k: [] for k in ("dc", "db", "dJ", "fc", "fb", "fJ", "rc", "rb")}
    for t in grid:
        dc, db, dJ = rm.relative_differences(p, t, m)
        fc, fb, fJ = rm.fast_mode_relative(p, t, m)
        rc, rb = rm.joint_gamma_known_impostor_relative(p, t, m)
        for key, val in zip(("dc", "db", "dJ", "fc", "fb", "fJ", "rc", "rb"),
                            (dc, db, dJ, fc, fb, fJ, rc, rb)):
            out[key].append(val)
    return out


def summarize_cell(arr: Dict[str, List[float]], n: int, window: str) -> dict:
    known = {"c": rms(arr["dc"]), "b": rms(arr["db"]),
             "cb": rms(arr["dc"] + arr["db"]), "J": rms(arr["dJ"])}
    bound = {"c": rms(arr["fc"]), "b": rms(arr["fb"]), "J": rms(arr["fJ"]),
             "cb_gamma_free": rms(arr["fc"] + arr["fb"]),
             "cb_gamma_known": rms(arr["rc"] + arr["rb"])}
    n_eff = {"c": n, "b": n, "cb": 2 * n, "J": n}
    eps_req = {o: math.sqrt(n_eff[o]) * known[o] / D_STAR for o in OBSERVABLES}
    disting = {str(eps): {o: (math.sqrt(n_eff[o]) * known[o] / eps >= D_STAR) for o in OBSERVABLES}
               for eps in EPSILONS}
    cell = {"n": n, "rms_known": known, "rms_impostor_bound": bound,
            "eps_required": eps_req, "distinguishable": disting}
    if window == "full" and n >= 2:
        cell["computed_flux_from_b"] = computed_flux_indices(arr["db"])
    return cell


def analyze_family(name: str, fam: dict, grid_sizes: Sequence[int]) -> dict:
    alpha, gamma, c0, T = fam["alpha"], fam["gamma"], fam["c0"], fam["T"]
    res = {"params": {k: v for k, v in fam.items() if k != "ks"}, "per_k": {}}
    for k in fam["ks"]:
        p = rm.Params(alpha, k, gamma, c0)
        m = rm.modes(p)
        kres = {"k": k, "r_f": m.r_f, "r_s": m.r_s, "r_eq": m.r_eq, "rate_shift": m.rate_shift,
                "boundary_layer_width": 1.0 / m.r_f, "n_res": math.ceil(T * m.r_f),
                "impostor_params": dict(zip(("c0", "gamma", "alpha"), rm.impostor_params(p, m))),
                "windows": {}}
        for wname, frac in WINDOWS.items():
            wres = {}
            for n in grid_sizes:
                arr = evaluate_arrays(p, m, time_grid(T, n, frac))
                wres[str(n)] = summarize_cell(arr, n, wname)
            kres["windows"][wname] = wres
        exact = rm.relative_differences(p, T, m)
        lead = rm.leading_order_endpoint(p, T)
        kres["endpoint"] = {"exact": dict(zip(("c", "b", "J"), exact)),
                            "leading_order": dict(zip(("c", "b", "J"), lead)),
                            "ratio_exact_over_leading": {
                                o: (e / l if l != 0.0 else None) for o, e, l in zip(("c", "b", "J"), exact, lead)}}
        t_c, t_j = rm.blind_spot_times(p)
        kres["blind_spots"] = {"T_c": t_c, "dc_at_T_c": rm.relative_differences(p, t_c, m)[0],
                               "T_J": t_j, "dJ_at_T_J": (rm.relative_differences(p, t_j, m)[2] if t_j else None)}
        res["per_k"][str(k)] = kres
    return res


def stiff_flux_diagnostic() -> dict:
    p = rm.Params(1.0, 1e12, 4.0, 1.0)
    t = 1e-3
    c, b = rm.finite_state(p, t)
    direct = p.k * (b - p.gamma * c)
    stable = rm.release_flux(p, t)
    return {"k": p.k, "t": t, "direct_k_times_b_minus_gamma_c_binary64": direct,
            "stable_alpha_gamma_c0_E12": stable, "abs_split": abs(direct - stable),
            "report_reference_values": {"stable": 0.7998400160, "direct_reported": 0.7989164885}}


def run_mc(reps: int) -> List[dict]:
    fam = FAMILIES[MC_SPEC["family"]]
    p = rm.Params(fam["alpha"], MC_SPEC["k"], fam["gamma"], fam["c0"])
    m = rm.modes(p)
    arr = evaluate_arrays(p, m, time_grid(fam["T"], MC_SPEC["n"], 0.0))
    target = MC_SPEC["target_index"]
    cells = []
    for obs, key in (("c", "dc"), ("b", "db"), ("J", "dJ")):
        delta = arr[key]
        sigma = norm(delta) / target
        p_pred = phi(-target / 2.0)
        p_emp = mc_direct(delta, sigma, reps, MC_SPEC["seeds"][obs])
        tol = 3.0 * math.sqrt(p_pred * (1.0 - p_pred) / (2.0 * reps))
        cells.append({"observable": obs, "sigma_relative": sigma, "index": target,
                      "predicted_error": p_pred, "empirical_error": p_emp,
                      "tolerance": tol, "within_tolerance": abs(p_emp - p_pred) <= tol})
    delta = arr["db"]
    sigma = norm(delta) / target
    ci = computed_flux_indices(delta)
    d_real, d_naive, d_comp = ci["d_real"] / sigma, ci["d_naive"] / sigma, ci["d_comp"] / sigma
    p_real, p_naive = phi(-d_real / 2.0), phi(-d_naive / 2.0)
    p_emp = mc_computed_flux(delta, sigma, reps, MC_SPEC["seeds"]["computed_flux_from_b"])
    tol = 3.0 * math.sqrt(p_real * (1.0 - p_real) / (2.0 * reps))
    cells.append({"observable": "computed_flux_from_b (naive filter)", "sigma_relative": sigma,
                  "index_b": target, "index_comp_gls": d_comp, "index_naive_reported": d_naive,
                  "index_realized": d_real, "predicted_error_realized": p_real,
                  "predicted_error_naive": p_naive, "empirical_error": p_emp, "tolerance": tol,
                  "within_tolerance": abs(p_emp - p_real) <= tol,
                  "naive_prediction_also_within_tolerance": abs(p_emp - p_naive) <= tol})
    return cells


def evaluate_predictions(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    n_lo = 4 if 4 in grid_sizes else min(grid_sizes)
    preds: List[dict] = []
    fam_a = results["families"]["A"]
    T_a = FAMILIES["A"]["T"]

    # P1 late-window structural non-identifiability
    ok, details = True, {}
    for kstr, kres in fam_a["per_k"].items():
        k = kres["k"]
        if k < 10.0:
            continue
        bnd = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]
        free_ok = all(bnd[o] <= 1e-6 for o in ("c", "b", "J", "cb_gamma_free"))
        known_ok = bnd["cb_gamma_known"] >= 0.05 / k
        details[kstr] = {"free_bounds": {o: bnd[o] for o in ("c", "b", "J", "cb_gamma_free")},
                         "cb_gamma_known": bnd["cb_gamma_known"], "pass": free_ok and known_ok}
        ok = ok and free_ok and known_ok
    preds.append({"id": "P1", "statement": "late window: nuisance-free impostor bounds <=1e-6; joint with gamma known >=0.05/k",
                  "passed": ok, "details": details})

    # P2 resolved independent flux dominates
    ok, details = True, {}
    for fname, fres in results["families"].items():
        for kstr, kres in fres["per_k"].items():
            if kres["n_res"] > n_max:
                continue
            kn = kres["windows"]["full"][str(n_max)]["rms_known"]
            ratio = kn["J"] / max(kn["c"], kn["b"])
            details[f"{fname}:{kstr}"] = ratio
            ok = ok and ratio >= 2.0
    preds.append({"id": "P2", "statement": "resolved grids: RMS_J >= 2*max(RMS_c, RMS_b)",
                  "passed": ok, "details": details})

    # P3 computed-flux chain
    ok, worst = True, 0.0
    for fres in results["families"].values():
        for kres in fres["per_k"].values():
            for cell in kres["windows"]["full"].values():
                ci = cell.get("computed_flux_from_b")
                if not ci:
                    continue
                v1 = ci["d_real"] - ci["d_comp"] * (1.0 + 1e-12)
                v2 = ci["d_comp"] - ci["d_b"] * (1.0 + 1e-12)
                worst = max(worst, v1, v2)
                ok = ok and v1 <= 0.0 and v2 <= 0.0
    preds.append({"id": "P3", "statement": "d_real <= d_comp <= d_b for every full-window cell",
                  "passed": ok, "details": {"worst_violation": worst}})

    # P4a leading-order endpoint at k=1000
    k1000 = fam_a["per_k"].get("1000.0")
    ok, details = True, {}
    if k1000:
        for o, r in k1000["endpoint"]["ratio_exact_over_leading"].items():
            details[o] = r
            ok = ok and (r is not None) and abs(r - 1.0) <= 0.05
    else:
        ok = False
    preds.append({"id": "P4a", "statement": "k=1000, T=1: exact/leading-order within 5% for c, b, J",
                  "passed": ok, "details": details})

    # P4b blind spots scale faster than 1/k
    ok, details = True, {}
    k100 = fam_a["per_k"].get("100.0")
    if k100 and k1000:
        rc = abs(k1000["blind_spots"]["dc_at_T_c"]) / abs(k100["blind_spots"]["dc_at_T_c"])
        rj = abs(k1000["blind_spots"]["dJ_at_T_J"]) / abs(k100["blind_spots"]["dJ_at_T_J"])
        details = {"ratio_c": rc, "ratio_J": rj}
        ok = rc <= 0.03 and rj <= 0.03
    else:
        ok = False
    preds.append({"id": "P4b", "statement": "endpoint blind spots: |delta(k=1000)|/|delta(k=100)| <= 0.03 for c at T=5, J at T=3.75",
                  "passed": ok, "details": details})

    # P5a/P5b/P5c resolution
    oka, okb, da, db_ = True, True, {}, {}
    ratios = []
    for kstr, kres in fam_a["per_k"].items():
        est = 1.0 / math.sqrt(2.0 * kres["r_f"] * T_a)
        rj_max = kres["windows"]["full"][str(n_max)]["rms_known"]["J"]
        if 4 * kres["n_res"] <= n_max:
            da[kstr] = rj_max / est
            oka = oka and 0.7 <= rj_max / est <= 1.3
        if kres["n_res"] > n_max:
            db_[kstr] = rj_max / est
            okb = okb and rj_max / est <= 0.5
        if kres["n_res"] <= n_max:
            ratios.append((kres["k"], rj_max / kres["windows"]["full"][str(n_lo)]["rms_known"]["J"]))
    ratios.sort()
    okc = all(ratios[i][1] <= ratios[i + 1][1] for i in range(len(ratios) - 1))
    preds.append({"id": "P5a", "statement": "4*n_res <= n_max: RMS_J(n_max) within [0.7,1.3] of (2 r_f T)^-1/2",
                  "passed": oka, "details": da})
    preds.append({"id": "P5b", "statement": "n_res > n_max: RMS_J(n_max) <= 0.5*(2 r_f T)^-1/2",
                  "passed": okb, "details": db_})
    preds.append({"id": "P5c", "statement": f"resolved k: RMS_J(n_max)/RMS_J({n_lo}) nondecreasing in k",
                  "passed": okc, "details": {str(k): r for k, r in ratios}})

    # P6 Monte Carlo
    mc = results["monte_carlo"]
    ok = all(cell["within_tolerance"] for cell in mc)
    preds.append({"id": "P6", "statement": "MC error rates match Phi(-d/2) (d_real for computed flux)",
                  "passed": ok, "details": {cell["observable"]: cell["within_tolerance"] for cell in mc}})
    return preds


def run_study(grid_sizes: Sequence[int] = GRID_SIZES, reps: int = MC_SPEC["reps"]) -> dict:
    grid_sizes = sorted(set(int(n) for n in grid_sizes))
    results = {"spec": {"families": FAMILIES, "grid_sizes": grid_sizes, "windows": WINDOWS,
                        "observables": list(OBSERVABLES), "epsilons": list(EPSILONS),
                        "D_star": D_STAR, "mc": dict(MC_SPEC, reps=reps),
                        "noise_model": "iid Gaussian; sigma_c=eps*c0, sigma_b=eps*gamma*c0, "
                                       "sigma_J=eps*alpha*gamma*c0/(1+gamma); fixed per sample"},
               "families": {name: analyze_family(name, fam, grid_sizes) for name, fam in FAMILIES.items()},
               "stiff_flux_diagnostic": stiff_flux_diagnostic(),
               "monte_carlo": run_mc(reps)}
    results["predictions"] = evaluate_predictions(results, grid_sizes)
    return results


# ---------------------------------------------------------------- reporting
def _f(x: Optional[float]) -> str:
    return "   n/a   " if x is None else f"{x:9.3e}"


def print_summary(results: dict, out=sys.stdout) -> None:
    w = out.write
    grid_sizes = results["spec"]["grid_sizes"]
    n_max = max(grid_sizes)
    w(f"release-observability-002b synthetic study  (D* = {D_STAR:.4f}; decision d >= D*)\n")
    for fname, fres in results["families"].items():
        prm = fres["params"]
        w(f"\n=== Family {fname}: alpha={prm['alpha']} gamma={prm['gamma']} c0={prm['c0']} T={prm['T']} ===\n")
        for obs in OBSERVABLES:
            w(f"\n-- RMS relative separation, all parameters known, full window, observable {obs} --\n")
            w(f"{'k':>8} " + " ".join(f"{'n=' + str(n):>9}" for n in grid_sizes) + "\n")
            for kstr, kres in fres["per_k"].items():
                row = [kres["windows"]["full"][str(n)]["rms_known"][obs] for n in grid_sizes]
                w(f"{kres['k']:8.0f} " + " ".join(_f(x) for x in row) + "\n")
        w(f"\n-- Late window [T/2,T], n={n_max}: impostor-bound RMS (nuisance parameters free) --\n")
        w(f"{'k':>8} {'c':>9} {'b':>9} {'J':>9} {'cb(g free)':>10} {'cb(g known)':>11} {'0.05/k':>9}\n")
        for kstr, kres in fres["per_k"].items():
            b = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]
            w(f"{kres['k']:8.0f} {_f(b['c'])} {_f(b['b'])} {_f(b['J'])} {_f(b['cb_gamma_free']):>10} "
              f"{_f(b['cb_gamma_known']):>11} {_f(0.05 / kres['k'])}\n")
        w(f"\n-- Required relative precision eps_req (full window, known params) at n=64 and n={n_max} --\n")
        w(f"{'k':>8} " + " ".join(f"{o + '@64':>9}" for o in OBSERVABLES)
          + " " + " ".join(f"{o + '@max':>9}" for o in OBSERVABLES) + "\n")
        for kstr, kres in fres["per_k"].items():
            e64 = kres["windows"]["full"].get("64", kres["windows"]["full"][str(n_max)])["eps_required"]
            emx = kres["windows"]["full"][str(n_max)]["eps_required"]
            w(f"{kres['k']:8.0f} " + " ".join(_f(e64[o]) for o in OBSERVABLES)
              + " " + " ".join(_f(emx[o]) for o in OBSERVABLES) + "\n")
        w("\n-- Time resolution of the independent release flux --\n")
        w(f"{'k':>8} {'r_f':>10} {'1/r_f':>9} {'n_res':>7} {'(2r_fT)^-1/2':>12} "
          + " ".join(f"{'J@' + str(n):>9}" for n in grid_sizes) + "\n")
        for kstr, kres in fres["per_k"].items():
            est = 1.0 / math.sqrt(2.0 * kres["r_f"] * prm["T"])
            row = [kres["windows"]["full"][str(n)]["rms_known"]["J"] for n in grid_sizes]
            w(f"{kres['k']:8.0f} {kres['r_f']:10.3e} {_f(1.0 / kres['r_f'])} {kres['n_res']:7d} {est:12.3e} "
              + " ".join(_f(x) for x in row) + "\n")
        w(f"\n-- Flux computed from the same b samples (full window): ratios to raw-b index --\n")
        w(f"{'k':>8} {'n':>6} {'comp/b':>9} {'naive/b':>9} {'real/b':>9}\n")
        for kstr, kres in fres["per_k"].items():
            for n in grid_sizes:
                ci = kres["windows"]["full"][str(n)].get("computed_flux_from_b")
                if ci and n in (64, n_max):
                    w(f"{kres['k']:8.0f} {n:6d} {_f(ci['ratio_comp'])} {_f(ci['ratio_naive'])} {_f(ci['ratio_real'])}\n")
        w("\n-- Endpoint t=T: exact relative difference / leading-order ratio; blind spots --\n")
        for kstr, kres in fres["per_k"].items():
            ep, bs = kres["endpoint"], kres["blind_spots"]
            w(f"k={kres['k']:.0f}: exact c={_f(ep['exact']['c'])} b={_f(ep['exact']['b'])} J={_f(ep['exact']['J'])}"
              f" | ratio c={_f(ep['ratio_exact_over_leading']['c'])} b={_f(ep['ratio_exact_over_leading']['b'])}"
              f" J={_f(ep['ratio_exact_over_leading']['J'])} | dc(T_c={bs['T_c']:.3g})={_f(bs['dc_at_T_c'])}"
              f" dJ(T_J={bs['T_J']})={_f(bs['dJ_at_T_J'])}\n")
    sd = results["stiff_flux_diagnostic"]
    w(f"\n=== Stiff-flux diagnostic (k=1e12, t=1e-3): direct={sd['direct_k_times_b_minus_gamma_c_binary64']:.10f}"
      f" stable={sd['stable_alpha_gamma_c0_E12']:.10f} |split|={sd['abs_split']:.3e}"
      f" (REPORT: stable 0.7998400160, direct 0.7989164885) ===\n")
    w("\n=== Monte Carlo (predeclared cells) ===\n")
    for cell in results["monte_carlo"]:
        w(json.dumps(cell) + "\n")
    w("\n=== Predeclared predictions ===\n")
    for pr in results["predictions"]:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
        w(f"      details: {json.dumps(pr['details'])}\n")
    passed = sum(1 for pr in results["predictions"] if pr["passed"])
    w(f"\n{passed}/{len(results['predictions'])} predeclared predictions passed. "
      f"Executed numbers supersede any expectation stated in the request text.\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write full JSON results to this path")
    ap.add_argument("--reps", type=int, default=MC_SPEC["reps"], help="MC replicates per hypothesis")
    ap.add_argument("--max-n", type=int, default=max(GRID_SIZES), help="cap on grid sizes (quick runs)")
    args = ap.parse_args(argv)
    grids = [n for n in GRID_SIZES if n <= args.max_n] or [1]
    results = run_study(grids, args.reps)
    print_summary(results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: test_release_study.py
```python
"""Unit tests for release_model.py and release_study.py (standard library only).

Cross-check values quoted from AB-LFR1 REPORT.md (Lilitari) and the terminal
rows reproduced in Muse Code's independent check; they are values of the same
synthetic model, not external facts.  Run:  python -m unittest test_release_study -v
"""
import json
import math
import unittest

import release_model as rm
import release_study as rs


def solve_tridiag_2m1(r):
    """Solve (D D^T) z = r with D the first-difference operator (diag 2, off -1)."""
    m = len(r)
    cp, dp = [0.0] * m, [0.0] * m
    cp[0], dp[0] = -0.5, r[0] / 2.0
    for i in range(1, m):
        denom = 2.0 + cp[i - 1]
        cp[i] = -1.0 / denom if i < m - 1 else 0.0
        dp[i] = (r[i] + dp[i - 1]) / denom
    z = [0.0] * m
    z[-1] = dp[-1]
    for i in range(m - 2, -1, -1):
        z[i] = dp[i] - cp[i] * z[i + 1]
    return z


class TestModel(unittest.TestCase):
    CASES = [rm.Params(1.0, 1.0, 4.0, 1.0), rm.Params(1.0, 100.0, 4.0, 1.0),
             rm.Params(1.0, 1000.0, 4.0, 1.0), rm.Params(0.5, 2.0, 4.0, 0.2),
             rm.Params(3.0, 0.1, 0.5, 2.0), rm.Params(1.0, 0.05, 0.2, 1.0)]

    def test_params_validation(self):
        for bad in ((0.0, 1.0, 1.0, 1.0), (1.0, -1.0, 1.0, 1.0), (1.0, 1.0, float("inf"), 1.0),
                    (1.0, 1.0, 1.0, 0.0)):
            with self.assertRaises(ValueError):
                rm.Params(*bad)

    def test_initial_condition_and_amplitude_identities(self):
        for p in self.CASES:
            m = rm.modes(p)
            c, b = rm.finite_state(p, 0.0, m)
            self.assertAlmostEqual(c / p.c0, 1.0, delta=1e-14)
            self.assertAlmostEqual(b / (p.gamma * p.c0), 1.0, delta=1e-14)
            self.assertAlmostEqual((m.r_f - m.r_s) / m.delta, 1.0, delta=1e-13)
            self.assertAlmostEqual(m.r_s * m.r_f / (p.alpha * p.k), 1.0, delta=1e-13)
            self.assertAlmostEqual((m.r_eq - m.r_s) / m.rate_shift, 1.0, delta=1e-9)
            self.assertAlmostEqual((m.kappa * (1 + p.gamma) - 1.0) / m.kappa_defect, 1.0, delta=1e-9)

    def test_ode_residual(self):
        for p in self.CASES:
            m = rm.modes(p)
            for t in (0.01, 0.3, 2.0):
                c, b = rm.finite_state(p, t, m)
                dc, db = rm.finite_derivative(p, t, m)
                rhs_c = -(p.alpha + p.k * p.gamma) * c + p.k * b
                rhs_b = p.k * p.gamma * c - p.k * b
                scale = (p.alpha + p.k * p.gamma) * abs(c) + p.k * abs(b) + 1e-300
                self.assertLess(abs(dc - rhs_c) / scale, 1e-10)
                self.assertLess(abs(db - rhs_b) / scale, 1e-10)
                # release flux = -b'
                self.assertLess(abs(rm.release_flux(p, t, m) + db) / (abs(db) + 1e-300), 1e-9)

    def test_report_crosschecks(self):
        # REPORT.md one-second family, binary64 terminal rows as quoted by Muse's script.
        rows = {1.0: (0.7194121558656852, 3.4711913532255587),
                100.0: (0.8176831359534535, 3.2772766223496683),
                1000.0: (0.8186259591066365, 3.2751587633867185),
                1e12: (0.8187307530778771, 3.274923012312163)}
        for k, (c_ref, b_ref) in rows.items():
            c, b = rm.finite_state(rm.Params(1.0, k, 4.0, 1.0), 1.0)
            self.assertAlmostEqual(c, c_ref, delta=1e-13)
            self.assertAlmostEqual(b, b_ref, delta=4e-13)
        c, b = rm.finite_state(rm.Params(0.5, 2.0, 4.0, 0.2), 3.0)   # C19 fixture
        self.assertAlmostEqual(c, 0.14402585951785102, delta=1e-13)
        self.assertAlmostEqual(b, 0.6051881664743007, delta=2e-13)
        # normalized endpoint differences reported: 1.047617e-3 (k=100), 1.047940e-4 (k=1000), 1.04694e-13 (k=1e12)
        for k, ref, tol in ((100.0, 1.047617e-3, 1e-9), (1000.0, 1.047940e-4, 1e-10), (1e12, 1.04694e-13, 1e-15)):
            dc, db, _ = rm.relative_differences(rm.Params(1.0, k, 4.0, 1.0), 1.0)
            self.assertAlmostEqual(max(abs(dc), abs(db)), ref, delta=tol)
        # stiff flux k=1e12, t=1e-3 (stable identity value reported 0.7998400160)
        self.assertAlmostEqual(rm.release_flux(rm.Params(1.0, 1e12, 4.0, 1.0), 1e-3), 0.7998400160, delta=1e-9)

    def test_stable_differences_match_direct_subtraction(self):
        for p in self.CASES[:4]:
            m = rm.modes(p)
            for t in (0.05, 0.5, 1.0):
                dc, db, dJ = rm.relative_differences(p, t, m)
                c, b = rm.finite_state(p, t, m)
                ce, be = rm.equilibrium_state(p.alpha, p.gamma, p.c0, t)
                self.assertAlmostEqual(dc, (c - ce) / p.c0, delta=2e-15)
                self.assertAlmostEqual(db, (b - be) / (p.gamma * p.c0), delta=2e-15)
                js = rm.flux_scale(p.alpha, p.gamma, p.c0)
                dJ_direct = (rm.release_flux(p, t, m) - rm.equilibrium_flux(p.alpha, p.gamma, p.c0, t)) / js
                self.assertAlmostEqual(dJ, dJ_direct, delta=4e-15)

    def test_impostor_reproduces_slow_modes_exactly(self):
        for p in self.CASES:
            m = rm.modes(p)
            c0i, gi, ai = rm.impostor_params(p, m)
            self.assertAlmostEqual(ai / (1.0 + gi) / m.r_s, 1.0, delta=1e-13)
            for t in (0.3 / m.r_f, 1.0 / m.r_f, 3.0 / m.r_f, 1.0):
                c, b = rm.finite_state(p, t, m)
                ci, bi = rm.equilibrium_state(ai, gi, c0i, t)
                fc, fb, fJ = rm.fast_mode_relative(p, t, m)
                self.assertAlmostEqual((c - ci) / p.c0, fc, delta=1e-13)
                self.assertAlmostEqual((b - bi) / (p.gamma * p.c0), fb, delta=1e-13)
                js = rm.flux_scale(p.alpha, p.gamma, p.c0)
                self.assertAlmostEqual((rm.release_flux(p, t, m) - rm.equilibrium_flux(ai, gi, c0i, t)) / js,
                                       fJ, delta=1e-12)

    def test_leading_order_endpoint_large_k(self):
        p = rm.Params(1.0, 1e6, 4.0, 1.0)
        exact = rm.relative_differences(p, 1.0)
        lead = rm.leading_order_endpoint(p, 1.0)
        for e, l in zip(exact, lead):
            self.assertLess(abs(e / l - 1.0), 1e-3)
        t_c, t_j = rm.blind_spot_times(p)
        self.assertAlmostEqual(t_c, 5.0)
        self.assertAlmostEqual(t_j, 3.75)
        # at the c blind spot the leading-order term vanishes identically
        self.assertAlmostEqual(rm.leading_order_endpoint(p, t_c)[0], 0.0, delta=1e-30)


class TestStudy(unittest.TestCase):
    def test_phi(self):
        self.assertAlmostEqual(rs.phi(0.0), 0.5, delta=1e-15)
        self.assertAlmostEqual(rs.phi(-rs.Z95), 0.05, delta=1e-9)
        self.assertAlmostEqual(rs.phi(-rs.D_STAR / 2.0), 0.05, delta=1e-9)

    def test_time_grid(self):
        g = rs.time_grid(1.0, 4, 0.0)
        self.assertEqual(len(g), 4)
        self.assertAlmostEqual(g[0], 0.25)
        self.assertAlmostEqual(g[-1], 1.0)
        g = rs.time_grid(3.0, 2, 0.5)
        self.assertAlmostEqual(g[0], 2.25)
        self.assertAlmostEqual(g[-1], 3.0)
        with self.assertRaises(ValueError):
            rs.time_grid(1.0, 0)

    def test_projection_theorem_for_computed_flux(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[1] for t in rs.time_grid(1.0, 64, 0.0)]
        ci = rs.computed_flux_indices(delta)
        n = len(delta)
        r = [delta[i + 1] - delta[i] for i in range(n - 1)]
        z = solve_tridiag_2m1(r)
        d2_gls = math.fsum(a * b for a, b in zip(r, z))
        self.assertAlmostEqual(d2_gls / ci["d_comp"] ** 2, 1.0, delta=1e-9)
        self.assertLessEqual(ci["d_real"], ci["d_comp"] * (1 + 1e-12))
        self.assertLessEqual(ci["d_comp"], ci["d_b"] * (1 + 1e-12))
        # Cauchy-Schwarz bound: d_real >= d_naive/sqrt(2) since ||D^T D|| <= 4
        self.assertGreaterEqual(ci["d_real"], ci["d_naive"] / math.sqrt(2.0) * (1 - 1e-12))

    def test_mc_deterministic_and_calibrated(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[0] for t in rs.time_grid(1.0, 64, 0.0)]
        sigma = rs.norm(delta) / 3.0
        a = rs.mc_direct(delta, sigma, 400, 12345)
        b = rs.mc_direct(delta, sigma, 400, 12345)
        self.assertEqual(a, b)
        p_pred = rs.phi(-1.5)
        self.assertLessEqual(abs(a - p_pred), 3.0 * math.sqrt(p_pred * (1 - p_pred) / 800.0))
        # computed-flux MC runs and returns a probability
        e = rs.mc_computed_flux(delta, sigma, 50, 7)
        self.assertTrue(0.0 <= e <= 1.0)

    def test_run_study_quick_pipeline(self):
        res = rs.run_study(grid_sizes=[1, 4, 16], reps=20)
        self.assertIn("families", res)
        self.assertIn("predictions", res)
        self.assertEqual(len(res["monte_carlo"]), 4)
        cell = res["families"]["A"]["per_k"]["100.0"]["windows"]["full"]["16"]
        for key in ("rms_known", "rms_impostor_bound", "eps_required", "distinguishable", "computed_flux_from_b"):
            self.assertIn(key, cell)
        self.assertNotIn("computed_flux_from_b", res["families"]["A"]["per_k"]["100.0"]["windows"]["late"]["16"])
        json.dumps(res)   # serializable
        # endpoint cell (n=1) equals the exact endpoint difference
        ep = res["families"]["A"]["per_k"]["100.0"]["endpoint"]["exact"]["c"]
        self.assertAlmostEqual(cell_n1 := res["families"]["A"]["per_k"]["100.0"]["windows"]["full"]["1"]["rms_known"]["c"],
                               abs(ep), delta=1e-15)
        self.assertGreater(cell_n1, 0.0)


if __name__ == "__main__":
    unittest.main()
```

## 4. What Red should run and send back

```
python -m unittest test_release_study -v
python release_study.py --out results.json          # full predeclared study (~several seconds)
python release_study.py --max-n 64 --reps 100       # quick smoke run if needed
```
Please return: the unittest output, the full stdout summary, and `results.json` (or its `predictions` and `monte_carlo` sections if large). I will then correct any derivation or code error against the executed numbers.

## 5. Status, limitations, and what remains

- **Nothing here has been executed by me.** All checks are static. Expected-value statements in §1–§2 (e.g. `δ_c(T)/c0 ≈ −0.1048/k`, `RMS_J ≈ (2r_fT)^{-1/2}`) are hand asymptotics; the runner's PASS/FAIL list is the executed verdict. If P4a–P5 fail, the most likely causes are my tolerance choices, not the identities, which are separately unit-tested.
- Unit test `test_mc_deterministic_and_calibrated` and prediction P6 are statistical at a 3σ tolerance: deterministic given seed and CPython's `random.gauss`, but a ~0.3% a-priori chance of a legitimate failure was accepted at predeclaration.
- The nuisance-parameter analysis uses the slow-mode impostor as an **upper bound** on the nuisance-minimized separation (exact for `c`-only, `b`-only, `J`, and joint-with-γ-free in the late window; a declared least-squares choice for joint-with-γ-known). A true profile-likelihood minimization over `(c0', γ', α')` is **not implemented**.
- Not implemented: non-Gaussian or multiplicative noise; noise that scales with sampling rate (only the two readings in §2.6); non-equilibrated inlets; `k=0`, `γ=0`, repeated-root cases (covered by Lily's benchmark, out of this study's restriction); uptake inventory `U(T)` as an observable; the full-analysis narrative (other instance).
- Precision: differences are evaluated cancellation-free (≈1e-14 relative on the declared sets, static estimate). The REPORT's `1.04694e-13` is itself a binary64 direct-subtraction value and is checked only to 1e-15 absolute. No claim beyond binary64 behaviour is made; no Decimal/mpmath enclosure was computed.
- Inputs to the analysis half (expected, to be confirmed by execution): the early boundary layer of the independent release flux (`J(0)=0` vs `J_eq(0)=αγc0/(1+γ)`, width `≈1/(k(1+γ))`) is the only O(1) discriminator and requires `Δt ≲ 1/r_f`; late-window `c`, `b`, or `J` alone are structurally non-identifiable when `(c0,α)` (or `γ`) are free; joint `(c,b)` with calibrated γ retains an O(1/k) late-time signature via `b/c ≠ γ`; a flux computed from the same samples cannot beat the raw samples (loses exactly the grid mean) and its naive analysis mis-predicts the error rate; endpoint-only `c` has a blind spot at `T=(1+γ)/α`.