Red — adversarial review of the wave-9 study (author: a Claude instance; model: Lilitari's AB-LFR1; cross-check values: Muse Code; task text: Coda). Everything below is **static reasoning on the verbatim sources and Red's receipts**; I executed nothing. Hand estimates are labelled as such. Synthetic model-on-model only.

## 0. Verdict in one paragraph

The code is correct as far as I can check it (modes, amplitudes, impostor, projection theorem all verify algebraically; 12/12 tests and the REPORT cross-checks agree), but the 9/9 PASS is weakly informative: P3 is a theorem about arbitrary vectors; P1's "≤1e-6" half checks that e^{-25} is small; the three direct P6 cells are model-independent triplicates of "random.gauss is Gaussian"; the fourth P6 cell has no power to distinguish the two competing error predictions it was built to separate (the author's own `naive_prediction_also_within_tolerance: true` says so); P4a/P4b/P5a/P5b use tolerances 3–50× wider than the deviations the author's own asymptotics predict; and the predicates (k ≥ 10, 4·n_res ≤ n_max, family A only) carve out exactly the cells that would strain the loose forms. Two substantive findings: (i) P1's "≥ 0.05/k" conclusion is drawn from an *upper* bound, which is logically invalid as written — it is rescuable by an orthogonality argument I give below and test in N1c; (ii) the headline `eps_required` tables are Scenario K only; the study's own impostor shows that with γ free, any grid blind to the boundary layer is non-identifiable even in the full window, so the most-quoted numbers are the most favourable scenario. I supply three new predictions (N1–N3) plus three sharpened re-checks (S1–S3) as a separate module, so the executed baseline is untouched.

## 1. Are predictions tautological or too loose to fail?

| Pred | What the code actually tests | Verdict |
|---|---|---|
| **P1 (≤1e-6)** | `fast_mode_relative` returns `B·e^{-r_f t}` by construction; in the late window `r_f t ≥ r_f T/2 ≥ 25.4` for k ≥ 10, so the quantity is ≤ 0.02·e^{-25} ≈ 2e-13 (k=10) and underflows to exactly 0.0 for k ≥ 1000. Threshold 1e-6 is 7+ orders above the largest value. The k<10 exclusion removes the only case that fails (k=1: 3.3e-3). | **Tautological**; also a hidden predicate choice. |
| **P1 (≥0.05/k)** | Compares an *upper bound* on the nuisance-minimised separation to a lower threshold. "upper bound ≥ x" does not imply "true separation ≥ x". Observed coefficient 0.0861/k vs threshold 0.05/k (58%). | **Logic gap** (fixable, see §1.1); threshold loose. |
| **P2** | Follows from P5a (RMS_J ≈ (2r_fT)^{-1/2} ∝ k^{-1/2}) and RMS_c ≈ 0.13/k; ratio ≈ 2.4·√k (hand estimate; receipt: 23.7 at k=100). Only k=1 (3.30) is anywhere near 2. | Weak form of a scaling law; binding at one cell. |
| **P3** | `d_comp = ‖δ−δ̄𝟙‖ ≤ ‖δ‖` (Pythagoras) and `d_real = ‖Dδ‖²/‖DᵀDδ‖ ≤ ‖δ−δ̄𝟙‖` (Cauchy–Schwarz, using DᵀD𝟙=0). True for **every** real vector, independent of the model. `(1+1e-12)` slack removes rounding too. `worst_violation` is initialised at 0.0 so it reports max(0, actual) — uninformative. | **Tautological**; belongs only in unit tests (where it already is). |
| **P4a** | Ratios 0.99997/0.99982/1.00006 vs tolerance 0.05. The author's own expansion predicts O(1/k)=0.1% deviations. Redundant with `test_leading_order_endpoint_large_k`. | Too loose by ~50×. |
| **P4b** | Ratios 0.010015/0.010016 vs ≤0.03. "≤0.03" is satisfied by k^{-1.5} too; the stated claim "∝1/k²" is never tested. | Too loose by 3×; weaker than the claim. |
| **P5a** | ±30% window; receipt 1.126/1.015/0.986. Restricted to family A; B k=200 would give 0.910 (0.01175/0.01291, discretisation x=r_fT/n=0.18). k=1000 (A) falls in the gap between "4n_res ≤ n_max" and "n_res > n_max" (ratio 0.852). | Loose; predicate gap; family restriction. |
| **P5b** | ≤0.5 vs observed 0.117. A one-point model gives 3.695e-4 vs 3.700e-4 observed (hand estimate: RMS² ≈ (1+κ_d)²e^{-2x}/n + RMS_J(4)²). | Too loose by 4×. |
| **P5c** | Monotonicity of 4 numbers spanning 1.8→95, implied by k^{1/2} scaling. | Nearly vacuous. |
| **P6** | See §2. | Direct cells model-independent; computed-flux cell powerless. |

### 1.1 Rescuing P1's "≥" (the orthogonality argument used by N1c)
With γ calibrated, the equilibrium family in noise-weighted relative units is `a·(e_r, e_r)`. The finite-k slow mode is `(a_c, a_b)·e_s` with `a_b − a_c = α/Δ`. Decompose the data into symmetric `ā·e_s·(1,1)` and antisymmetric `(α/2Δ)·e_s·(1,−1)`. For *every* `(a, r)` the model lies in the pointwise-symmetric subspace, which is orthogonal to the antisymmetric part; hence the residual² = ‖symmetric misfit‖² + ‖antisymmetric‖² is minimised at `r = r_s, a = ā` and equals exactly the author's `a_star = mean` residual. So the γ-known impostor is **tight** (not merely an upper bound) when the fast mode is negligible — the "≥" is valid, but the text does not say so. N1c tests tightness numerically by profile minimisation; S1 tests the coefficient: `k·RMS → (α/(2(1+γ)))·rms_late(e_eq)` with ratio ∈ [0.98, 1] (hand: 0.990 at k=10 → 1.0000 at k=10⁴ for A; 0.998/1.000 for B; sign of the deviation follows from Δ > k(1+γ) and r_s < r_eq).

## 2. Monte Carlo (P6): seed/replicate dependence and a stronger test

1. **The direct cells (c, b, J) do not involve the model.** `s0 = Σ δ_i e_i ~ N(0, σ²‖δ‖²)`, threshold `‖δ‖²/2`, calibration `σ = ‖δ‖/3` ⇒ error = Φ(−1.5) for **any** δ. The three cells are three seeds of one RNG check. Analytically, the matched-filter statistic is exactly Gaussian, so MC can only catch an error in a *variance formula*; for the direct cells there is none to catch.
2. **The computed-flux cell has no power.** Receipt: `d_real = 0.0925`, `d_naive = 0.0124`, so both predictions are ≈0.5 (0.4816 vs 0.4975); the gap 0.016 is below the tolerance 0.0335 (1000 reps). If the code had used the naive variance as "truth", P6 would still PASS. Note also the *direction*: in this smooth-δ cell the naive analyst is **conservative** (under-reports the index by 7.5×); the theorem `d_real ≥ d_naive/√2` (tested in the unit tests) means a naive analyst can be anti-conservative by at most √2 in index — the §5 "mis-predicts the error rate" claim should say so.
3. **Seed/replicate dependence.** PASS is conditional on seeds 20261101–04; a priori ≈1.1% chance that a correct implementation FAILs one of four 3σ cells; the J cell sits at z = +2.0 (0.078 vs 0.0668, SE 0.0056). Tolerance ∝ reps^{-1/2}, so with 1000 reps any systematic bias below ≈1.7 percentage points is invisible. Determinism holds across CPython versions (Mersenne Twister + Box–Muller unchanged), modulo last-ulp libm differences that could move a single borderline count.
4. **Stronger test (implemented as N2).** (a) Calibrate the computed-flux cell at `d_real = 3` so `p_real = 0.0668` while `p_naive = Φ(−d_naive/2) ≈ 0.420` (hand, from receipt ratio 0.134): the two predictions are 20 tolerances apart, so the test can fail in either direction. (b) Test the **variance** of the statistic directly: empirical var/(σ²‖DᵀDδ‖²) ∈ 1 ± 3√(2/(N−1)) (±9.5% at N=2000), while the naive prediction is 55.6× larger (receipt indices squared) — this has essentially unit power. (c) Report z-scores over 5 fixed seeds with a predeclared family-wise bound (|z| ≤ 3.5). Not implemented but recommended: a KS test of the standardised statistic against N(0,1), or simply dropping the direct cells (they are analytic).

## 3. Hidden choices favouring the predicted outcomes

1. **Noise model: fixed per-sample σ at any sampling rate** ⇒ information grows without bound in n. That is why `eps_req` for J at n=16384 reads 1.21 at k=100 (a "121%-precision" flux sensor suffices). Under the author's own fixed-budget alternative (§2.6, n_ref=64) it is ≈0.076 — still 24× better than c (3.2e-3), so the *ordering* is robust but the absolute `@max` numbers are artefacts of the assumption and should be flagged in the narrative.
2. **σ_J = ε·J_scale** (quasi-steady flux) makes the t→0 layer an O(1) signal in noise units; that is the entire source of P2/P5. A declared choice, but every J conclusion is downstream of it.
3. **Scenario K only in the headline tables.** The impostor is applied only to the late window. The same construction shows (§4, N1b) that a full-window grid with first sample beyond ≈4 layer widths (x = r_fT/n ≥ 4; A k≥100 at n=64) retains < 1% of the Scenario-K separation when γ is free. The study's eps_req tables therefore describe the favourable scenario and the text never tabulates the unfavourable one.
4. **Predicates:** k ≥ 10 and late start T/2 jointly guarantee e^{-25}; P5a/P5b leave k=1000 in a gap; P5a is family-A-only where B k=200 is the stressing case; P2 threshold 2 vs minimum 3.3.
5. **MC calibration σ=‖δ‖/3** makes the direct cells shape-independent (point 2.1); the computed-flux σ was inherited from the b-calibration rather than set for power.
6. **Grid excludes t=0** — conservative for J (fine), neutral for c, b.
7. **`stiff_flux_diagnostic`** prints the REPORT's "direct" 0.7989 next to its own 0.7998; both are path-dependent rounding of an 8e-13 difference between O(3) numbers — any agreement or disagreement there is meaningless and should not be read as reproduction. No prediction depends on it (good).
8. **D\*** is a simple-vs-simple criterion; under Scenario N the test is composite and the midpoint-threshold error formula does not apply — the author says "indicator", which is fair, but "distinguishable" tables should say Scenario K explicitly.

## 4. Additional predeclared predictions (can fail), with code and tests

Delivered as a **separate module** that re-runs `rs.run_study` and evaluates the additions, so the executed baseline files are unchanged (zero-diff). Hook, if wanted later: in `run_study`, after `results["predictions"] = ...`, add `results["review_additions"] = release_review_additions.evaluate_additions(results, grid_sizes, reps)`.

**N1 — Nuisance cost in the *full* window + tightness of the impostor.** (a) k ≥ 10, both families, n=64: `cb_gamma_known_bound / rms_known_cb ∈ [0.85, 0.95]` (hand: (α/2Δ)·rms(e_s)/RMS_cb ≈ 0.91 A, 0.93 B — calibrated γ costs ~10%). (b) cells with x = r_fT/n ≥ 4 at n=64: `cb_gamma_free_bound / rms_known_cb ≤ 1e-2` (hand: ≤2e-3 — γ free destroys identifiability on layer-blind grids even in the full window). (c) Profile least squares over the equilibrium rate r (LS amplitudes closed-form, 1-D golden-section search): `profile/bound ∈ [0.99, 1]` for every γ-known bound (late n=1024 and full n=64), and `∈ [0.95, 1]` for the γ-free bound on resolved grids (r_fT ≥ 100, bound ≥ 1e-6; hand: absorption ≈ 2.4/(r_fT) ≤ 1%). Fails if §1.1's orthogonality argument is wrong or if the equilibrium family can absorb the fast spike.

**N2 — MC with power** (§2.4): N2a error-rate agreement *and* rejection of the naive prediction; N2b variance agreement *and* naive/real variance ratio ≥ 10 (a smoothness claim about δ_b on layer-blind grids — it would be ≈2 at A k=10, n=64, which is excluded by x ≥ 4); N2c five seeds, |z| ≤ 3.5.

**N3 — Resolution law with discretisation, all k ≥ 10 cells, both families, all n (closes the P5 gap and covers B).** With `G(n) = (1/n)Σe^{-2r_f t_i}`, `H(n) = (1/n)Σe^{-r_f t_i}` (exact geometric sums), `F² = (1+κ_d)²G(n)`:
`0 ≤ RMS_J(n)² − F² ≤ 2|κ_d|(1+κ_d)H(n) + κ_d²`.
Derivation (static): δ_J = slow + fast exactly with fast = −(1+κ_d)e_f, slow = (1+κ_d)e_s − e_eq; slow(0)=κ_d<0 (γ>1), slow is monotone increasing and stays negative until the J blind spot T_J, so for T < T_J the cross term is ≥ 0 (lower bound) and |slow| ≤ |κ_d| (upper bound). Hand check at A k=10, n=16384: excess/F² ≈ 0.057 vs bound 0.064; at n=64: 3.93e-4 vs 4.49e-4. Fails if the sign/monotonicity analysis or the identity κ(1+γ)=1+κ_d is wrong. Predicate (κ_d<0, T<T_J) is evaluated in code; cells not meeting it are reported as skipped.

**S1–S3 (sharpened re-checks, tolerance only):** S1 P1-coefficient ∈ [0.98, 1]; S2 P4a as a convergence rate: `(ratio−1)(k=10⁴)/(ratio−1)(k=10³) ∈ [0.085, 0.115]` for c, b, J; S3 P4b blind-spot ratios ∈ [0.0095, 0.0105] for both decades (receipt: 0.010015, 0.010001).

Not implemented (listed): KS test of MC statistic; profile minimisation over all three nuisance parameters on a 3-D grid (the 1-D profile with closed-form amplitudes is exact for these linear-in-amplitude models, so this is not a gap); fixed-budget `eps_req` table; the late-window ordering prediction `RMS_c > max(RMS_b, RMS_J)` for k ≥ 10 (leading order predicts 3.2 : 2.2 : 1.8 for A at t=T) — a good fourth candidate for a later wave.

FILE: release_review_additions.py
```python
"""release_review_additions.py -- adversarial-review additions for the AB-LFR1
release-observability synthetic study (The Stage, task release-observability-003).

Evaluates predeclared predictions N1-N3 and sharpened re-checks S1-S3 against a
fresh run of release_study.run_study().  Standard library only; deterministic;
writes only to a caller-supplied --out path.  Synthetic model-on-model study:
no empirical, biological or hardware claims.

Credit: model formulas Lilitari (AB-LFR1); baseline study and modules Claude
(Anthropic, wave-9 author); cross-check values Muse Code; task text Coda;
execution Red.  Review additions: Claude (Anthropic, reviewer instance), for
Richard (Andrei) Pemberton.  Nothing here was executed by its author.

Usage: python release_review_additions.py [--out additions.json] [--reps 1000] [--max-n 16384]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import release_model as rm
import release_study as rs

N2_SEEDS = (20261111, 20261112, 20261113, 20261114, 20261115)


# ------------------------------------------------------------------ helpers
def mean_exp_on_grid(rate: float, T: float, n: int) -> float:
    """(1/n) * sum_{i=1}^{n} exp(-rate * i*T/n), closed-form geometric sum."""
    if n < 1:
        raise ValueError("n must be >= 1")
    x = rate * T / n
    num = math.exp(-x) * (-math.expm1(-rate * T))
    den = -math.expm1(-x)
    return num / den / n


def relative_finite_data(p: rm.Params, m: rm.Modes, grid: Sequence[float]) -> Tuple[List[float], List[float]]:
    """Finite-k observables in noise-weighted relative units: c/c0 and b/(gamma c0)."""
    xc, xb = [], []
    for t in grid:
        c, b = rm.finite_state(p, t, m)
        xc.append(c / p.c0)
        xb.append(b / (p.gamma * p.c0))
    return xc, xb


def profile_residual_rms(xc: Sequence[float], xb: Sequence[float], grid: Sequence[float],
                         r: float, gamma_known: bool) -> float:
    """RMS (over 2n components) of the best least-squares equilibrium fit at decay rate r.
    gamma_known: one shared amplitude a*(e_r, e_r); else separate amplitudes (a_c e_r, a_b e_r)."""
    er = [math.exp(-r * t) for t in grid]
    see = math.fsum(e * e for e in er)
    if gamma_known:
        a = math.fsum((u + v) * e for u, v, e in zip(xc, xb, er)) / (2.0 * see)
        res2 = math.fsum((u - a * e) ** 2 + (v - a * e) ** 2 for u, v, e in zip(xc, xb, er))
    else:
        ac = math.fsum(u * e for u, e in zip(xc, er)) / see
        ab = math.fsum(v * e for v, e in zip(xb, er)) / see
        res2 = math.fsum((u - ac * e) ** 2 + (v - ab * e) ** 2 for u, v, e in zip(xc, xb, er))
    return math.sqrt(max(res2, 0.0) / (2 * len(grid)))


def profile_minimum(xc: Sequence[float], xb: Sequence[float], grid: Sequence[float], r_centre: float,
                    gamma_known: bool, span: float = 4.0, coarse: int = 25, iters: int = 40) -> Tuple[float, float]:
    """Minimise profile_residual_rms over r in [r_centre/span, r_centre*span]:
    coarse log grid, then golden-section refinement in the bracketing interval.
    Returns (minimum residual RMS, argmin r)."""
    lo, hi = math.log(r_centre / span), math.log(r_centre * span)
    xs = [lo + (hi - lo) * i / (coarse - 1) for i in range(coarse)]
    vals = [profile_residual_rms(xc, xb, grid, math.exp(x), gamma_known) for x in xs]
    i = min(range(coarse), key=lambda j: vals[j])
    best_val, best_x = vals[i], xs[i]
    a, b = xs[max(i - 1, 0)], xs[min(i + 1, coarse - 1)]
    g = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - g * (b - a), a + g * (b - a)
    fc = profile_residual_rms(xc, xb, grid, math.exp(c), gamma_known)
    fd = profile_residual_rms(xc, xb, grid, math.exp(d), gamma_known)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = profile_residual_rms(xc, xb, grid, math.exp(c), gamma_known)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = profile_residual_rms(xc, xb, grid, math.exp(d), gamma_known)
    for x, v in ((c, fc), (d, fd)):
        if v < best_val:
            best_val, best_x = v, x
    return best_val, math.exp(best_x)


def filter_geometry(delta_b: Sequence[float]) -> Tuple[float, float]:
    """(||D delta||^2, ||D^T D delta||^2) for the first-difference operator D."""
    n = len(delta_b)
    if n < 2:
        raise ValueError("need n >= 2")
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    dtd = [(w[j - 1] if j >= 1 else 0.0) - (w[j] if j <= n - 2 else 0.0) for j in range(n)]
    return nw2, math.fsum(x * x for x in dtd)


def naive_filter_stats(delta_b: Sequence[float], sigma: float, reps: int, seed: int) -> Tuple[float, float, float]:
    """Naive matched filter w = D delta on first differences of iid N(0, sigma^2) samples.
    Returns (empirical total error, sample variance of the noise statistic, its mean)."""
    rng = random.Random(seed)
    n = len(delta_b)
    w = [delta_b[i + 1] - delta_b[i] for i in range(n - 1)]
    nw2 = math.fsum(x * x for x in w)
    thresh = 0.5 * nw2
    err = 0
    draws: List[float] = []
    for _ in range(reps):
        for hyp in (0, 1):
            e = [rng.gauss(0.0, sigma) for _ in range(n)]
            s = math.fsum(w[i] * (e[i + 1] - e[i]) for i in range(n - 1))
            draws.append(s)
            stat = s + (nw2 if hyp == 1 else 0.0)
            if (hyp == 0 and stat > thresh) or (hyp == 1 and stat <= thresh):
                err += 1
    big_n = len(draws)
    mean = math.fsum(draws) / big_n
    var = math.fsum((s - mean) ** 2 for s in draws) / (big_n - 1)
    return err / (2 * reps), var, mean


# ------------------------------------------------------------------ N1
def evaluate_n1(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    n_mid = 64 if 64 in grid_sizes else n_max
    n_late = 1024 if 1024 in grid_sizes else n_max
    a_det: Dict[str, float] = {}
    b_det: Dict[str, dict] = {}
    c_det: Dict[str, dict] = {}
    a_ok = b_ok = c_ok = True
    for fname, fres in results["families"].items():
        prm = fres["params"]
        T = prm["T"]
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            tag = f"{fname}:{kstr}"
            p = rm.Params(prm["alpha"], k, prm["gamma"], prm["c0"])
            m = rm.modes(p)
            cell = kres["windows"]["full"][str(n_mid)]
            known_cb = cell["rms_known"]["cb"]
            gk = cell["rms_impostor_bound"]["cb_gamma_known"]
            gf = cell["rms_impostor_bound"]["cb_gamma_free"]
            ratio_k = gk / known_cb
            a_det[tag] = ratio_k
            a_ok = a_ok and 0.85 <= ratio_k <= 0.95
            x = m.r_f * T / n_mid
            if x >= 4.0:
                ratio_f = gf / known_cb
                b_det[tag] = {"x_first_sample_in_layer_widths": x, "ratio": ratio_f}
                b_ok = b_ok and ratio_f <= 1e-2
            # N1c: tightness of the author's bounds against a profile least-squares minimum
            grid = rs.time_grid(T, n_mid, 0.0)
            xc, xb = relative_finite_data(p, m, grid)
            prof, r_best = profile_minimum(xc, xb, grid, m.r_s, True)
            c_det[tag + ":gamma_known:full:n=%d" % n_mid] = {"profile_over_bound": prof / gk,
                                                             "r_best_over_r_s": r_best / m.r_s}
            c_ok = c_ok and 0.99 <= prof / gk <= 1.0 + 1e-9
            gk_late = kres["windows"]["late"][str(n_late)]["rms_impostor_bound"]["cb_gamma_known"]
            grid = rs.time_grid(T, n_late, rs.WINDOWS["late"])
            xc, xb = relative_finite_data(p, m, grid)
            prof, r_best = profile_minimum(xc, xb, grid, m.r_s, True)
            c_det[tag + ":gamma_known:late:n=%d" % n_late] = {"profile_over_bound": prof / gk_late,
                                                              "r_best_over_r_s": r_best / m.r_s}
            c_ok = c_ok and 0.99 <= prof / gk_late <= 1.0 + 1e-9
            gf_max = kres["windows"]["full"][str(n_max)]["rms_impostor_bound"]["cb_gamma_free"]
            if m.r_f * T >= 100.0 and gf_max >= 1e-6:
                grid = rs.time_grid(T, n_max, 0.0)
                xc, xb = relative_finite_data(p, m, grid)
                prof, r_best = profile_minimum(xc, xb, grid, m.r_s, False)
                c_det[tag + ":gamma_free:full:n=%d" % n_max] = {"profile_over_bound": prof / gf_max,
                                                                "r_best_over_r_s": r_best / m.r_s}
                c_ok = c_ok and 0.95 <= prof / gf_max <= 1.0 + 1e-9
    return [
        {"id": "N1a", "statement": "full window, n=%d, k>=10, both families: gamma-known joint impostor bound / "
                                   "known-parameter RMS_cb in [0.85, 0.95] (calibrated gamma costs ~10%%)" % n_mid,
         "passed": a_ok, "details": a_det},
        {"id": "N1b", "statement": "full window, n=%d, first sample >= 4 layer widths (x>=4): gamma-free joint "
                                   "impostor bound / known RMS_cb <= 1e-2 (layer-blind grids are non-identifiable "
                                   "with gamma free even in the full window)" % n_mid,
         "passed": b_ok, "details": b_det},
        {"id": "N1c", "statement": "profile least-squares minimum over the equilibrium rate / author's impostor "
                                   "bound in [0.99,1] (gamma known) and [0.95,1] (gamma free, resolved grids): "
                                   "the bounds are tight, so P1's '>=' is valid",
         "passed": c_ok, "details": c_det},
    ]


# ------------------------------------------------------------------ N2
def evaluate_n2(reps: int, seeds: Sequence[int] = N2_SEEDS) -> List[dict]:
    fam = rs.FAMILIES["A"]
    p = rm.Params(fam["alpha"], 100.0, fam["gamma"], fam["c0"])
    m = rm.modes(p)
    grid = rs.time_grid(fam["T"], 64, 0.0)
    delta = [rm.relative_differences(p, t, m)[1] for t in grid]
    nw2, ndtd2 = filter_geometry(delta)
    ndtd = math.sqrt(ndtd2)
    d_real_unit = nw2 / ndtd                  # realized index per unit sigma
    sigma = d_real_unit / 3.0                 # calibrate so that d_real = 3
    d_naive = math.sqrt(nw2) / (math.sqrt(2.0) * sigma)
    p_real, p_naive = rs.phi(-1.5), rs.phi(-d_naive / 2.0)
    var_pred_real = sigma * sigma * ndtd2
    var_ratio_naive_over_real = 2.0 * nw2 / ndtd2
    big_n = 2 * reps
    se_p = math.sqrt(p_real * (1.0 - p_real) / big_n)
    se_v = math.sqrt(2.0 / (big_n - 1))
    cells = []
    for seed in seeds:
        err, var, mean = naive_filter_stats(delta, sigma, reps, seed)
        vr = var / var_pred_real
        cells.append({"seed": seed, "empirical_error": err, "z_error": (err - p_real) / se_p,
                      "variance_ratio_to_realized_prediction": vr, "z_variance": (vr - 1.0) / se_v,
                      "mean_statistic_over_sigma": mean / sigma})
    prim = cells[0]
    a_ok = (abs(prim["empirical_error"] - p_real) <= 3.0 * se_p
            and abs(prim["empirical_error"] - p_naive) > 3.0 * se_p)
    b_ok = abs(prim["variance_ratio_to_realized_prediction"] - 1.0) <= 3.0 * se_v and var_ratio_naive_over_real >= 10.0
    c_ok = all(abs(cl["z_error"]) <= 3.5 and abs(cl["z_variance"]) <= 3.5 for cl in cells)
    common = {"cell": "A, k=100, n=64, full window, computed flux from b, naive filter",
              "sigma_relative": sigma, "index_realized": 3.0, "index_naive_reported": d_naive,
              "predicted_error_realized": p_real, "predicted_error_naive": p_naive,
              "tolerance_error": 3.0 * se_p, "tolerance_variance_ratio": 3.0 * se_v,
              "variance_ratio_naive_over_realized": var_ratio_naive_over_real}
    return [
        {"id": "N2a", "statement": "d_real=3 calibration: empirical error within 3 SE of Phi(-1.5) AND farther than "
                                   "3 SE from the naive prediction Phi(-d_naive/2)",
         "passed": a_ok, "details": dict(common, primary=prim)},
        {"id": "N2b", "statement": "sample variance of the naive statistic / sigma^2 ||D^T D delta||^2 within 3 SE of 1, "
                                   "and naive/realized variance ratio 2||D delta||^2/||D^T D delta||^2 >= 10",
         "passed": b_ok, "details": dict(common, primary=prim)},
        {"id": "N2c", "statement": "all %d seeds: |z_error| <= 3.5 and |z_variance| <= 3.5" % len(seeds),
         "passed": c_ok, "details": {"cells": cells}},
    ]


# ------------------------------------------------------------------ N3
def evaluate_n3(results: dict, grid_sizes: Sequence[int]) -> dict:
    det: Dict[str, object] = {}
    ok, checked = True, 0
    for fname, fres in results["families"].items():
        prm = fres["params"]
        T = prm["T"]
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            tag = f"{fname}:{kstr}"
            p = rm.Params(prm["alpha"], k, prm["gamma"], prm["c0"])
            m = rm.modes(p)
            kd = m.kappa_defect
            _, t_j = rm.blind_spot_times(p)
            if not (kd < 0.0 and t_j is not None and T < t_j):
                det[tag] = "skipped: sign predicate (kappa_defect<0 and T<T_J) not met"
                continue
            rows = {}
            for n in grid_sizes:
                rms2 = kres["windows"]["full"][str(n)]["rms_known"]["J"] ** 2
                f2 = (1.0 + kd) ** 2 * mean_exp_on_grid(2.0 * m.r_f, T, n)
                h = mean_exp_on_grid(m.r_f, T, n)
                upper = 2.0 * abs(kd) * (1.0 + kd) * h + kd * kd
                excess = rms2 - f2
                lo_ok = excess >= -1e-7 * f2
                hi_ok = excess <= upper + 1e-7 * f2
                rows[str(n)] = {"excess_over_F2": (excess / f2 if f2 > 0 else None),
                                "upper_over_F2": (upper / f2 if f2 > 0 else None),
                                "excess": excess, "upper": upper, "pass": lo_ok and hi_ok}
                ok = ok and lo_ok and hi_ok
                checked += 1
            det[tag] = rows
    return {"id": "N3", "statement": "k>=10, both families, all full-window grids: 0 <= RMS_J^2 - (1+kappa_d)^2 G(n) "
                                     "<= 2|kappa_d|(1+kappa_d) H(n) + kappa_d^2 with exact geometric sums G, H",
            "passed": ok and checked > 0, "details": det}


# ------------------------------------------------------------------ S1-S3
def evaluate_sharpened(results: dict, grid_sizes: Sequence[int]) -> List[dict]:
    n_max = max(grid_sizes)
    preds: List[dict] = []
    # S1: coefficient of the late-window gamma-known residual
    ok, det = True, {}
    for fname, fres in results["families"].items():
        prm = fres["params"]
        a, g, T = prm["alpha"], prm["gamma"], prm["T"]
        r_eq = a / (1.0 + g)
        rms_eq_late = math.sqrt(math.exp(-r_eq * T) * mean_exp_on_grid(2.0 * r_eq, T * (1.0 - rs.WINDOWS["late"]), n_max))
        pred = (a / (2.0 * (1.0 + g))) * rms_eq_late
        for kstr, kres in fres["per_k"].items():
            k = kres["k"]
            if k < 10.0:
                continue
            gk = kres["windows"]["late"][str(n_max)]["rms_impostor_bound"]["cb_gamma_known"]
            ratio = k * gk / pred
            det[f"{fname}:{kstr}"] = ratio
            ok = ok and 0.98 <= ratio <= 1.0 + 1e-9
    preds.append({"id": "S1", "statement": "late window: k * gamma-known bound / [alpha/(2(1+gamma)) * rms_late(e_eq)] in [0.98, 1]",
                  "passed": ok, "details": det})
    # S2: P4a as a convergence rate (deviation ratio between k=1e3 and k=1e4 ~ 0.1)
    ok, det = True, {}
    per_k = results["families"]["A"]["per_k"]
    k3, k4 = per_k.get("1000.0"), per_k.get("10000.0")
    if k3 and k4:
        for o in ("c", "b", "J"):
            r3 = k3["endpoint"]["ratio_exact_over_leading"][o]
            r4 = k4["endpoint"]["ratio_exact_over_leading"][o]
            if r3 is None or r4 is None or r3 == 1.0:
                ok, det[o] = False, None
                continue
            ratio = (r4 - 1.0) / (r3 - 1.0)
            det[o] = ratio
            ok = ok and 0.085 <= ratio <= 0.115
    else:
        ok = False
    preds.append({"id": "S2", "statement": "A, T=1: (exact/leading - 1) at k=1e4 divided by the same at k=1e3 in [0.085, 0.115] for c, b, J",
                  "passed": ok, "details": det})
    # S3: P4b as a 1/k^2 law with 5% window, both decades
    ok, det = True, {}
    for lo, hi in (("100.0", "1000.0"), ("1000.0", "10000.0")):
        kl, kh = per_k.get(lo), per_k.get(hi)
        if not (kl and kh):
            ok = False
            continue
        rc = abs(kh["blind_spots"]["dc_at_T_c"]) / abs(kl["blind_spots"]["dc_at_T_c"])
        rj = abs(kh["blind_spots"]["dJ_at_T_J"]) / abs(kl["blind_spots"]["dJ_at_T_J"])
        det[f"{lo}->{hi}"] = {"ratio_c": rc, "ratio_J": rj}
        ok = ok and 0.0095 <= rc <= 0.0105 and 0.0095 <= rj <= 0.0105
    preds.append({"id": "S3", "statement": "blind spots: |delta(10k)|/|delta(k)| in [0.0095, 0.0105] for c (T_c) and J (T_J), both decades",
                  "passed": ok, "details": det})
    return preds


def evaluate_additions(results: dict, grid_sizes: Sequence[int], reps: int) -> List[dict]:
    grid_sizes = sorted(set(int(n) for n in grid_sizes))
    preds: List[dict] = []
    preds.extend(evaluate_n1(results, grid_sizes))
    preds.extend(evaluate_n2(reps))
    preds.append(evaluate_n3(results, grid_sizes))
    preds.extend(evaluate_sharpened(results, grid_sizes))
    return preds


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write JSON (baseline predictions + additions) to this path")
    ap.add_argument("--reps", type=int, default=rs.MC_SPEC["reps"], help="MC replicates per hypothesis")
    ap.add_argument("--max-n", type=int, default=max(rs.GRID_SIZES), help="cap on grid sizes (quick runs)")
    args = ap.parse_args(argv)
    grids = [n for n in rs.GRID_SIZES if n <= args.max_n] or [1]
    results = rs.run_study(grids, args.reps)
    adds = evaluate_additions(results, grids, args.reps)
    w = sys.stdout.write
    w("=== Baseline predeclared predictions (release_study) ===\n")
    for pr in results["predictions"]:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
    w("\n=== Review additions (release-observability-003) ===\n")
    for pr in adds:
        w(f"{pr['id']:4s} {'PASS' if pr['passed'] else 'FAIL'}  {pr['statement']}\n")
        w(f"      details: {json.dumps(pr['details'], default=str)}\n")
    passed = sum(1 for pr in adds if pr["passed"])
    w(f"\n{passed}/{len(adds)} review additions passed.  Executed numbers supersede the reviewer's hand estimates.\n")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"baseline_predictions": results["predictions"], "review_additions": adds,
                       "grid_sizes": grids, "reps": args.reps, "n2_seeds": list(N2_SEEDS)},
                      fh, indent=1, sort_keys=True, default=str)
        w(f"\nwrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: test_release_review_additions.py
```python
"""Unit tests for release_review_additions.py (standard library only).
Run:  python -m unittest test_release_review_additions -v
"""
import json
import math
import unittest

import release_model as rm
import release_study as rs
import release_review_additions as ra


class TestHelpers(unittest.TestCase):
    def test_mean_exp_on_grid_matches_brute_force(self):
        for rate, T, n in ((5.83, 1.0, 7), (500.8, 1.0, 64), (50.0, 3.0, 1024), (0.4, 0.5, 16), (1e5, 1.0, 1)):
            brute = math.fsum(math.exp(-rate * i * T / n) for i in range(1, n + 1)) / n
            closed = ra.mean_exp_on_grid(rate, T, n)
            self.assertLessEqual(abs(closed - brute), 1e-12 * brute + 1e-300)
        with self.assertRaises(ValueError):
            ra.mean_exp_on_grid(1.0, 1.0, 0)

    def test_profile_fits_pure_equilibrium_exactly(self):
        grid = rs.time_grid(1.0, 32, 0.0)
        r = 0.2
        xc = [0.9 * math.exp(-r * t) for t in grid]
        xb = [0.9 * math.exp(-r * t) for t in grid]
        self.assertLess(ra.profile_residual_rms(xc, xb, grid, r, True), 1e-15)
        best, r_best = ra.profile_minimum(xc, xb, grid, 0.3, True)   # centre deliberately off
        self.assertLess(best, 1e-9)
        self.assertAlmostEqual(r_best / r, 1.0, delta=1e-4)
        xb2 = [0.7 * math.exp(-r * t) for t in grid]
        self.assertLess(ra.profile_residual_rms(xc, xb2, grid, r, False), 1e-15)
        self.assertGreater(ra.profile_residual_rms(xc, xb2, grid, r, True), 1e-3)

    def test_profile_minimum_never_above_author_bound(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        grid = rs.time_grid(1.0, 64, 0.0)
        arr = rs.evaluate_arrays(p, m, grid)
        bound_gk = rs.rms(arr["rc"] + arr["rb"])
        bound_gf = rs.rms(arr["fc"] + arr["fb"])
        xc, xb = ra.relative_finite_data(p, m, grid)
        prof_gk, _ = ra.profile_minimum(xc, xb, grid, m.r_s, True)
        prof_gf, _ = ra.profile_minimum(xc, xb, grid, m.r_s, False)
        self.assertLessEqual(prof_gk, bound_gk * (1.0 + 1e-9))
        self.assertLessEqual(prof_gf, bound_gf * (1.0 + 1e-9) + 1e-12)
        self.assertGreater(prof_gk, 0.5 * bound_gk)

    def test_filter_geometry_consistent_with_study_indices(self):
        p = rm.Params(1.0, 100.0, 4.0, 1.0)
        m = rm.modes(p)
        delta = [rm.relative_differences(p, t, m)[1] for t in rs.time_grid(1.0, 64, 0.0)]
        nw2, ndtd2 = ra.filter_geometry(delta)
        ci = rs.computed_flux_indices(delta)
        self.assertAlmostEqual(nw2 / math.sqrt(ndtd2) / ci["d_real"], 1.0, delta=1e-12)
        self.assertAlmostEqual(math.sqrt(nw2 / 2.0) / ci["d_naive"], 1.0, delta=1e-12)

    def test_naive_filter_stats_deterministic_and_variance_sane(self):
        delta = [1e-3 * (i / 15.0) ** 2 for i in range(16)]
        sigma = 1e-4
        a = ra.naive_filter_stats(delta, sigma, 200, 99)
        b = ra.naive_filter_stats(delta, sigma, 200, 99)
        self.assertEqual(a, b)
        nw2, ndtd2 = ra.filter_geometry(delta)
        self.assertGreater(2.0 * nw2 / ndtd2, 1.0)        # smooth delta: naive variance overstates
        var_ratio = a[1] / (sigma * sigma * ndtd2)
        self.assertLess(abs(var_ratio - 1.0), 0.5)         # 400 draws: SE ~ 7%
        self.assertTrue(0.0 <= a[0] <= 1.0)


class TestPipeline(unittest.TestCase):
    def test_quick_pipeline_produces_all_additions(self):
        grids = [1, 4, 16, 64]
        res = rs.run_study(grid_sizes=grids, reps=20)
        adds = ra.evaluate_additions(res, grids, reps=20)
        ids = [a["id"] for a in adds]
        for want in ("N1a", "N1b", "N1c", "N2a", "N2b", "N2c", "N3", "S1", "S2", "S3"):
            self.assertIn(want, ids)
        for a in adds:
            self.assertIn("passed", a)
            self.assertIn("details", a)
        json.dumps(adds, default=str)
        n3 = next(a for a in adds if a["id"] == "N3")
        self.assertIn("A:100.0", n3["details"])
        self.assertIsInstance(n3["details"]["A:100.0"], dict)


if __name__ == "__main__":
    unittest.main()
```

## 5. What Red should run and send back

```
python -m unittest test_release_review_additions -v
python release_review_additions.py --out additions.json        # expected ~15-30 s (profile searches at n=16384)
python release_review_additions.py --max-n 1024 --reps 200     # quick smoke run
```
Please return the unittest output, the full stdout, and `additions.json`. **Predeclared expectations (static, to be superseded by execution):** N1a ≈ 0.91 (A) / 0.93 (B); N1b ≤ 2e-3; N1c ≈ 1.000 (γ known), 0.995–0.998 (γ free); N2 p_emp ≈ 0.067 ± 0.006, var ratio 1 ± 0.03, naive/realized variance ratio 55.6, p_naive ≈ 0.42; N3 all cells pass with excess/F² ≈ 0.06 (A k=10, n_max) down to ≈5e-4 (k=10⁴); S1 0.990→1.000 (A), 0.998/1.000 (B); S2 ≈ 0.10 ± 0.01; S3 0.01002 and 0.01000. If N1c or N3 fail, the most likely cause is an error in my orthogonality/sign derivations (§1.1, §4), which is exactly what those predictions are meant to expose; if S2 fails for J only, suspect a small second-order coefficient rather than a model bug.

## 6. Limitations and what remains

- No execution by me; runtime estimate for the profile searches is a guess (≈4 cells × 65 evaluations × 16384 points).
- N1c uses a 1-D profile over the rate with closed-form least-squares amplitudes (exact for these amplitude-linear models); it does not search the fast-rate basin (irrelevant: that fit is worse by construction).
- Not implemented: KS/distribution test of the MC statistic; fixed-budget `eps_req` tables; the late-window observable-ordering prediction; non-Gaussian noise; Scenario-N composite-test error rates (the impostor residual remains an indicator, as in the baseline).
- Credit: model/formulas Lilitari; baseline study, code and tests the wave-9 Claude author; cross-checks Muse Code; task Coda; execution Red; this review Claude (Anthropic), for Richard (Andrei) Pemberton.