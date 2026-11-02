# thermal-radiation-001 — outer-face radiation extension of T0-HYP-1

Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton. This builds directly on Coda's (Codex Lily) two executed references quoted in the bundle: `validation/thermal/thermal_reference.py` (T0-HYP-1 exact rational steady network, `reference_results.json`) and `validation/thermal_transient/rc_transient.py` (T0-LUMP2-1 two-node backward Euler, REPORT.md). No Fable artefact is in my bundle, so none is used or judged. Nothing below was executed by me: I have no tools. All numerical claims are deferred to Red's sandbox run; the text contains only definitions, proofs, tolerances and design values.

Model IDs introduced: **T0-RAD-1** (steady, labelled extension — the T0-HYP-1 baseline is not changed) and **T0-LUMP2-RAD-1** (two-node transient with the nonlinear massless surface). Everything inside the code is in Kelvin, as the contract requires for radiation; the nominal 25 °C boundaries become 298.15 K.

---

## (a) Existence, uniqueness, and a convergent safeguarded solver

**Network.** Nodes: internal H, sensor midplane S, massless outer surface O. Resistances (K/W): `R_HS` (inner silicone + half film + inner contact), `R_SO` (outer silicone + half film + outer contact), `R_rej ∈ (0, ∞]` (rear path to the reservoir at `T_r`; `∞` = blocked). For the symmetric stacks `R_HS = R_SO = a` and the reference's `b = R_SO + 1/(hA)`. Outer boundary, positive outward:

Φ(T) = hA (T − T_a) + εσA (T⁴ − T_w⁴),   T > 0 K,   h ≥ 0, ε ∈ [0,1].

Steady equations: (1) P = (H−S)/R_HS + (H−T_r)/R_rej; (2) J + (H−S)/R_HS = (S−O)/R_SO; (3) (S−O)/R_SO = Φ(O).

**Reduction.** Let q = (S−O)/R_SO. From (2),(1): H = T_r + R_rej(P+J−q), S = H − R_HS(q−J), O = S − R_SO q, hence O = E − R_th q with E := T_r + R_rej(P+J) + R_HS J and R_th := R_HS + R_SO + R_rej (finite rear). Then (3) is Φ(O) = (E−O)/R_th. For a blocked rear, q = P+J and (3) is Φ(O) = P+J. Both are instances of the **canonical scalar equation**

Γ(T) := K T + M Φ(T) − D = 0,  with (K,M,D) = (1/R_th, 1, E/R_th) or (0, 1, P+J).

**Lemma 1 (monotone convex).** On T > 0: Φ′(T) = hA + 4εσA T³ ≥ 0 (strictly if h>0 or ε>0) and Φ″(T) = 12εσA T² ≥ 0. So Γ is convex, and strictly increasing whenever K>0 or h>0 or ε>0.

**Lemma 2 (explicit bracket).** Let T_lo = min(T_a,T_w), T_hi = max(T_a,T_w) > 0. Each summand of Φ has the sign of T minus its own bath temperature, so Φ ≤ 0 on (0,T_lo] and Φ ≥ 0 on [T_hi,∞). 
Upper end: by convexity Φ(T) ≥ Φ(T_hi) + Φ′(T_hi)(T−T_hi) ≥ Φ′(T_hi)(T−T_hi) for T ≥ T_hi. Put U := T_hi + max(0, D − K T_hi)/(K + MΦ′(T_hi)) (denominator > 0 when K>0 or Φ′(T_hi)>0). Then Γ(U) ≥ K T_hi + (K+MΦ′(T_hi))(U−T_hi) − D = max(0, D−K T_hi) + K T_hi − D ≥ 0. 
Lower end: if K>0, L := min(T_lo, D/K) gives Γ(L) ≤ K·L − D + MΦ(L) ≤ 0 (if L = D/K ≤ T_lo the first two terms cancel and Φ(L) ≤ 0; if L = T_lo < D/K then KL−D<0 and Φ(L)≤0). If K=0 and D ≥ 0, L := T_lo gives Γ(L) = MΦ(T_lo) − D ≤ 0. 
Positivity: L > 0 because D > 0 for nonnegative sources and positive-Kelvin baths (steady: D = E/R_th with E = T_r + R_rej(P+J) + R_HS J > 0; transient step: D = κS_n + J + gβ/α > 0 when S_n, H_n, T_r > 0 K).

**Theorem 1 (existence and uniqueness).** If K>0 or h>0 or ε>0, Γ is continuous and strictly increasing on [L,U] with Γ(L) ≤ 0 ≤ Γ(U), so it has exactly one root T* in [L,U]; strict monotonicity on (0,∞) makes it the unique positive root. Back-substitution O=T*, q=Φ(T*), S=O+R_SO q, H=S+R_HS(q−J) yields the unique steady state. If K=0 and h=ε=0 (both exits closed) Γ ≡ −D: no solution when P+J>0, every T when P+J=0 — exactly the reference's `no_finite_steady_state` / `nonunique` statuses, which the code returns.

**Corollary (signs for the contract's common 25 °C boundaries).** With T_a=T_w=T_r and P,J ≥ 0: E ≥ T_a, Γ(T_a) = (T_a−E)/R_th ≤ 0 and Γ(E) = Φ(E) ≥ 0, so T* ∈ [T_a, E], q = (E−T*)/R_th ∈ [0, P+J] (the upper bound follows from R_HS J ≤ (R_HS+R_SO)(P+J)), and the reservoir receives q_r = P+J−q ≥ 0. With ε>0 and P+J>0 the root is strictly above T_a, and since ∂Γ/∂ε = σA(T⁴−T_w⁴) > 0 there, **T* strictly decreases in ε**; S = T*(1−R_SO/R_th)+const and H = T*(1−(R_SO+R_HS)/R_th)+const (for finite R_rej; H = T*+const if blocked) decrease likewise, q increases, q_r decreases. The same argument gives monotonicity in h.

**Theorem 2 (safeguarded Newton converges).** The solver starts at T₀ = U and keeps a bracket [L_k,U_k] with Γ(L_k) ≤ 0 ≤ Γ(U_k). Each iteration takes the Newton point N_k = T_k − Γ(T_k)/Γ′(T_k) if it lies strictly inside the bracket and |2Γ(T_k)| ≤ |Γ′(T_k)|·|step two iterations ago| (the standard "decreasing fast enough" rule); otherwise it bisects. 
(i) Exact arithmetic: for convex increasing Γ with T_k ≥ T*, convexity gives 0 = Γ(T*) ≥ Γ(T_k) + Γ′(T_k)(T*−T_k), i.e. N_k ≥ T*, and Γ(T_k) ≥ 0 gives N_k ≤ T_k. Starting at U the Newton iterates are monotone non-increasing and bounded below by T*, hence convergent to a limit with Γ/Γ′ = 0, i.e. to T*; convergence is quadratic since Γ′(T*) ≥ K + M·hA > 0 or ≥ M·4εσA T*³ > 0 and Γ″ is bounded on the bracket. 
(ii) Any arithmetic: whenever Newton is accepted the step is at most half the step two iterations before (geometric shrinkage, and Γ′ ≥ Γ′(L) > 0 on the bracket forces Γ(T_k) → 0); whenever it is rejected the bracket halves. Hence the bracket width is below any τ after at most 2⌈log₂((U−L)/τ)⌉ iterations and the returned point always lies in a bracket containing a sign change of the evaluated Γ. Termination is on a scale-aware residual floor (8·ε_mach·(|KT|+|D|+M(|conv|+|rad|))), on a relative step/bracket size 1e-13, or on no representable progress; the 200-iteration cap is a guard that raises rather than returning silently.

**Transient (T0-LUMP2-RAD-1).** C_H Ḣ = P − g(H−S) − g_r(H−T_r), C_S Ṡ = J + g(H−S) − q, q = (S−O)/R_SO = Φ(O) (surface massless, quasi-steady, as in Coda's model). Backward Euler with step Δ: α = C_H/Δ+g+g_r, β = C_H H_n/Δ + P + g_r T_r, H_{n+1} = (β + g S_{n+1})/α; eliminating H gives κ S_{n+1} + q = D_n with κ = C_S/Δ + g(C_H/Δ+g_r)/α > 0, D_n = C_S S_n/Δ + J + gβ/α, and with S_{n+1} = O + R_SO q: **κ O + (1+κR_SO) Φ(O) = D_n** — again canonical with K=κ>0, M=1+κR_SO. Theorems 1–2 give a unique, convergently computed implicit step for every Δ>0. Stability: differences of two solutions satisfy N δ = (C_H δH₀/Δ, C_S δS₀/Δ) with N = [[C_H/Δ+g+g_r, −g],[−g, C_S/Δ+g+Q′]], Q′ ∈ [0,1/R_SO] by the mean value theorem; N is a Z-matrix with column sums ≥ C_i/Δ, so Σ C_i|δ_i| is non-increasing (unconditional ℓ¹-nonexpansiveness) and N⁻¹ ≥ 0 gives the discrete comparison principle used by the ordering tests (larger ε or an open rear path adds a nonpositive source ⇒ pointwise cooler trajectory). The per-step energy identity C_HΔH + C_SΔS = Δ(P+J−q−q_r) + Δ·Γ(O) holds exactly, so the audited energy residual equals Δ times the Newton residual plus roundoff. At ε=0 the step is algebraically identical to Coda's 2×2 formula (checked in the tests).

## (b) Error of the linearized radiative coefficient h_r = 4εσT_m³

Let ΔT = O − T_w (rise above the surroundings), T̄ = (O+T_w)/2. With O = T̄ + ΔT/2, T_w = T̄ − ΔT/2 the odd terms of the binomial expansions survive:

**Identity:** O⁴ − T_w⁴ = 4T̄³ΔT + T̄ΔT³, hence q_rad = h̄_r A ΔT · (1 + ΔT²/(4T̄²)) with h̄_r = 4εσT̄³.

Consequences (all exact, so the "rigorous bound" holds with equality):
* Arithmetic-mean coefficient: relative error of h̄_rAΔT versus the exact flux (relative to the linear value) is e_mean(ΔT) = ΔT²/(4T̄²) = (ΔT/(2T_w+ΔT))², always an **underestimate** of the radiative loss, increasing in ΔT ≥ 0, so sup over 0 ≤ ΔT ≤ ΔT_max is e_mean(ΔT_max) < (ΔT_max/2T_w)².
* Cold-side coefficient (T_m = T_w): O⁴−T_w⁴ = 4T_w³ΔT(1 + 3x/2 + x² + x³/4), x = ΔT/T_w — first order in the rise.
* General evaluation temperature T_m: q_rad − h_r(T_m)AΔT = εσAΔT[4(T̄³−T_m³) + T̄ΔT²], and by the mean value theorem  
  **(B1)** |q_rad − h_rAΔT| ≤ εσA|ΔT|[12·max(T̄,T_m)²·|T̄−T_m| + T̄ΔT²].

**Propagation to the solved temperatures.** Replace Φ by Φ_lin(T) = hA(T−T_a) + h_rA(T−T_w) with h_r fixed a priori; the linear network has the unique solution T_lin. With Δq(T) := εσA(T⁴−T_w⁴) − h_rA(T−T_w) and G_lin := K + M(h+h_r)A:  
**(B2)** T_lin − T* = M·Δq(T*)/G_lin (exact identity; H_lin − H* = (T_lin−T*)·R_rej/R_th for finite rear, = T_lin−T* if blocked).  
Since Δq is convex with stationary point T_m, its modulus on the Lemma-2 bracket [L,U] (which needs no knowledge of T*) is bounded by max(|Δq(L)|, |Δq(U)|, |Δq(T_m)| if T_m ∈ [L,U]):  
**(B3)** |T_lin − T*| ≤ M·max{…}/G_lin (a priori).  
Sign: Δq(T*) ≥ 0 whenever T_m ≤ T̄*, so any coefficient evaluated at or below the true mean **overpredicts** every node temperature (conservative in the hot direction); for T_m = T̄* the error is the cubic law T_lin − T* = M εσA T̄* ΔT*³/G_lin. The study evaluates three variants per row: a priori T_m = (ε=0 surface + T_w)/2 (an engineering guess, which sits above the true mean, so (B2) may be of either sign), the exact mean, and the cold coefficient; (B2) and (B3) are asserted in the tests and the study criteria.

## (c) Implementation

`thermal_radiation.py` (stdlib only). The two-node equations are **reimplemented explicitly** (not imported from `rc_transient.py`), preserving Coda's documented structure (segments with `duration/p/j` and an optional rear-conductance change, bounded source envelope, step budget, end-step flux quadrature, energy audit) and replacing the algebraic surface by the nonlinear massless node solved implicitly inside each backward-Euler step. The steady solver uses the same canonical routine. The ε=0 network is linear, so an exact `Fraction` closed form (`steady_linear_exact`) is provided for the exactness check; the float Newton path must agree with it and with Coda's floats to 1e-9 K.

## (d) Tests (`test_thermal_radiation.py`, unittest)

ε=0 exact reproduction of all 12 T0-HYP-1 rows (Fraction equality including Coda's `front_exact` strings, and float equality with `reference_results.json`); Newton path at ε=0 within 1e-9 K; global and node energy balances over the full grid; strict monotonicity in ε and in h; bracket containment; blocked rear (front = P+J); degenerate statuses; pure radiation (h=0); signed warm-reservoir flux; flux-level identities (mean, cold) and bound (B1); solution-level identity (B2) and bound (B3) over the grid, with sign checks; transient ε=0 step equals Coda's 2×2 algebra; long-time equilibrium equals the nonlinear steady state; equilibrium held; energy accounting with independent trace reconstruction; rear-loss event (continuity, exactly zero rear flux); pointwise ε-ordering; loss ≥ intact; one-node limit versus Coda's analytic fixture and backward-Euler errors; ε=0 cross-check against Coda's REPORT scenario values (tolerances labelled, because the REPORT does not state its scenario `dt`; I assume 1 s); input rejection.

## (e) Predeclared study RAD-STUDY-1

Steady grid: stacks H1/H2/H3 × P_body 1/5/10 W × h 3/8/15 × ε 0 (baseline comparator)/0.1/0.5/0.9 at R_rej = 2 K/W (108 rows), plus the blocked-rear extension at 5 W over the same h and ε (36 rows). Transient: stacks × ε 0/0.5/0.9 × {intact, rear loss at 600 s} with Coda's fault schedule (5 W to 900 s then 0, 0.1 W sensor throughout), h = 8, dt = 1 s, 3600 s (18 runs; peaks, 600/900 s checkpoints, horizon state, 60-s samples, energy audit). Criteria C1–C6 (balance/convergence, reference reproduction, monotonicity, linearization identity/bound, blocked-rear flux, transient energy/ordering) are fixed in `ANALYSIS.md` §8 and evaluated into `criteria_results`; failures are retained, never relaxed. Output schema is in the JSON (`schema` key) and in `ANALYSIS.md` §8. Comparator margins to 40 °C / 60 °C carry the label `study_comparator_only`; rear flux is reported as the ideal reservoir's heat demand.

---

FILE: validation/thermal_radiation/thermal_radiation.py
```python
"""T0-RAD-1 / T0-LUMP2-RAD-1: outer-face grey-body radiation extension of the T0-HYP-1
synthetic thermal reference.  Python 3.10+ standard library only; deterministic; no I/O.

Provenance.  Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton, task
thermal-radiation-001.  Builds on Coda's (Codex Lily) executed references:
validation/thermal/thermal_reference.py (T0-HYP-1 exact rational steady network) and
validation/thermal_transient/rc_transient.py (T0-LUMP2-1 two-node backward Euler).  The
two-node equations are REIMPLEMENTED explicitly here (not imported) so that the eps = 0
limit can be compared with the documented T0-LUMP2-1 step algebra in the tests.

Model (Kelvin inside this module; the contract says radiation uses absolute Kelvin).
Nodes: internal H, sensor midplane S, massless outer surface O.
  R_HS  inner silicone + half film + inner contact            (K/W)
  R_SO  outer silicone + half film + outer contact            (K/W)
  R_rej rear path H -> isothermal reservoir, +inf = blocked   (K/W)
Outer boundary, convection and grey-body radiation in parallel, positive outward:
  Phi(T) = h*A*(T - T_amb) + eps*sigma*A*(T^4 - T_sur^4)       (W)
The steady problem and every backward-Euler step reduce to one scalar equation
  K*T + M*Phi(T) = D,   K >= 0, M > 0,
solved by a bracketed, safeguarded Newton iteration (proofs in ANALYSIS.md).

Scope.  Synthetic computational modelling only.  Emissivity and convection coefficient
are assumed study parameters, not material or measured properties.  No physical
validation, safety certification or hardware recommendation is implied.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import math
import sys

SIGMA_W_M2K4 = 5.670374419e-8          # Stefan-Boltzmann constant, CODATA 2018
KELVIN_OFFSET = 273.15
AREA_M2 = 0.01
EPSILON_MACHINE = sys.float_info.epsilon
P_MAX_W = 10.0                         # computational input envelope (as T0-LUMP2-1), not a hardware limit
J_MAX_W = 0.2
MAX_STEPS = 100_000
MAX_NEWTON_ITERATIONS = 200
NEWTON_RELATIVE_TOLERANCE = 1e-13
RESIDUAL_FLOOR_FACTOR = 8.0

STACK_SILICONE_THICKNESS_M = {"H1": "0.0005", "H2": "0.001", "H3": "0.002"}
FILM_THICKNESS_M = "0.00005"
NOMINAL_K_SILICONE_W_MK = "0.27"
NOMINAL_K_FILM_W_MK = "0.20"
NOMINAL_CONTACT_M2K_W = "0.0002"
NOMINAL_SENSOR_POWER_W = 0.1
NOMINAL_R_REJ_K_W = 2.0
NOMINAL_C_H_J_K = 20.0                 # hypothetical internal storage, T0-LUMP2-1 assumption


def kelvin(celsius_value):
    """Celsius -> Kelvin with the exact 273.15 offset."""
    return celsius_value + KELVIN_OFFSET


def celsius(kelvin_value):
    return kelvin_value - KELVIN_OFFSET


def finite_number(value, name, allow_inf=False):
    """Admit non-Boolean int/float; reject NaN and (unless allowed) infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-Boolean int or float")
    value = float(value)
    if math.isnan(value) or (math.isinf(value) and not allow_inf):
        raise ValueError(f"{name} must be finite")
    return value


def exact_stack_resistances(stack, k_silicone=NOMINAL_K_SILICONE_W_MK, k_film=NOMINAL_K_FILM_W_MK,
                            contact_r=NOMINAL_CONTACT_M2K_W, area="0.01", thickness_factor="1"):
    """Exact rational T0-HYP-1 half-stack resistances (K/W); decimal strings keep rationals exact.
    The contract stacks are symmetric (outer thickness = inner thickness), so R_HS = R_SO."""
    if stack not in STACK_SILICONE_THICKNESS_M:
        raise ValueError("Unknown reference stack")
    A = Fraction(area)
    t = Fraction(STACK_SILICONE_THICKNESS_M[stack])*Fraction(thickness_factor)
    half = (t/(Fraction(k_silicone)*A) + Fraction(FILM_THICKNESS_M)/(2*Fraction(k_film)*A)
            + Fraction(contact_r)/A)
    return {"R_HS": half, "R_SO": half, "area": A}


def nominal_panel_capacity(stack):
    """T0-LUMP2-1 effective panel storage C_S (J/K): silicone rho 1030 kg/m3, cp 1500 J/(kg K);
    film rho 1420, cp 1090 -- assumed by Coda; transcribed with the same float expression order."""
    if stack not in STACK_SILICONE_THICKNESS_M:
        raise ValueError("Unknown reference stack")
    thick = {"H1": .0005, "H2": .001, "H3": .002}[stack]
    area = .01
    return 1030*area*(2*thick)*1500 + 1420*area*.00005*1090


@dataclass(frozen=True)
class FrontBoundary:
    """Massless outer surface: convection to T_amb_K and grey-body radiation to T_sur_K."""
    h: float
    eps: float
    area: float
    T_amb_K: float
    T_sur_K: float

    def __post_init__(self):
        for name in ("h", "eps", "area", "T_amb_K", "T_sur_K"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        if self.h < 0.0:
            raise ValueError("h must be nonnegative")
        if not 0.0 <= self.eps <= 1.0:
            raise ValueError("eps must lie in [0, 1]")
        if self.area <= 0.0:
            raise ValueError("area must be positive")
        if self.T_amb_K <= 0.0 or self.T_sur_K <= 0.0:
            raise ValueError("bath temperatures must be positive Kelvin")

    @property
    def hA(self):
        return self.h*self.area

    @property
    def radiation_constant(self):
        """eps*sigma*A in W/K^4."""
        return self.eps*SIGMA_W_M2K4*self.area

    def convective_flux(self, T):
        return self.hA*(T - self.T_amb_K)

    def radiative_flux(self, T):
        """eps*sigma*A*(T^4 - T_sur^4), factored to avoid cancellation near T_sur."""
        Tw = self.T_sur_K
        return self.radiation_constant*(T - Tw)*(T + Tw)*(T*T + Tw*Tw)

    def flux(self, T):
        return self.convective_flux(T) + self.radiative_flux(T)

    def derivative(self, T):
        return self.hA + 4.0*self.radiation_constant*T*T*T

    def exit_open(self):
        return self.h > 0.0 or self.eps > 0.0


@dataclass(frozen=True)
class ScalarSolution:
    T_K: float
    iterations: int
    bisections: int
    residual_W: float
    bracket_lo_K: float
    bracket_hi_K: float
    final_lo_K: float
    final_hi_K: float


def canonical_bracket(K, M, D, front):
    """ANALYSIS.md Lemma 2: [lo, hi] with Gamma(lo) <= 0 <= Gamma(hi) in exact arithmetic."""
    T_lo = min(front.T_amb_K, front.T_sur_K)
    T_hi = max(front.T_amb_K, front.T_sur_K)
    slope = K + M*front.derivative(T_hi)
    if slope <= 0.0:
        raise ValueError("No exit path (K = 0 and closed front): no finite solution")
    hi = T_hi + max(0.0, D - K*T_hi)/slope
    if K > 0.0:
        lo = min(T_lo, D/K)
    else:
        if D < 0.0:
            raise ValueError("Negative net source with blocked rear is outside the admitted domain")
        lo = T_lo
    if not lo > 0.0:
        raise ValueError("Bracket lower end is not a positive Kelvin temperature")
    return lo, hi


def solve_canonical(K, M, D, front, rel_tol=NEWTON_RELATIVE_TOLERANCE):
    """Solve K*T + M*Phi(T) = D for T > 0 K by bracketed, safeguarded Newton (Theorem 2)."""
    for name, value in (("K", K), ("M", M), ("D", D)):
        if not isinstance(value, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite float")
    if K < 0.0 or M <= 0.0:
        raise ValueError("Canonical coefficients need K >= 0 and M > 0")
    if not isinstance(front, FrontBoundary):
        raise ValueError("front must be a FrontBoundary")

    def gamma(T):
        return K*T + M*front.flux(T) - D

    def dgamma(T):
        return K + M*front.derivative(T)

    lo0, hi0 = canonical_bracket(K, M, D, front)
    lo, hi = lo0, hi0
    g_lo, g_hi = gamma(lo), gamma(hi)
    widen = max(1e-9, 1e-12*hi)
    tries = 0
    while g_lo > 0.0 and tries < 64:          # rounding guard; unreachable in exact arithmetic
        lo -= widen
        widen *= 2.0
        tries += 1
        if lo <= 0.0:
            raise RuntimeError("Could not establish a positive lower bracket")
        g_lo = gamma(lo)
    tries = 0
    while g_hi < 0.0 and tries < 64:
        hi += widen
        widen *= 2.0
        tries += 1
        g_hi = gamma(hi)
    if g_lo > 0.0 or g_hi < 0.0:
        raise RuntimeError("Bracket failure")
    if g_lo == 0.0:
        return ScalarSolution(lo, 0, 0, 0.0, lo0, hi0, lo, hi)
    if g_hi == 0.0:
        return ScalarSolution(hi, 0, 0, 0.0, lo0, hi0, lo, hi)

    T, f, df = hi, g_hi, dgamma(hi)          # start at the upper end: monotone Newton descent
    dx_old = dx = hi - lo
    bisections = 0
    iterations = 0
    while iterations < MAX_NEWTON_ITERATIONS:
        iterations += 1
        newton = None
        if df > 0.0:
            candidate = T - f/df
            if lo < candidate < hi and abs(