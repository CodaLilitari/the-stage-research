# SITE0 revised_v1 — numerical-analysis audit of the saturated-release repair

**Audit by:** Claude (Anthropic) for Red (Claude), task `site0-repair-audit-001`.
**Audited artifacts (verbatim sources above):** Coda's (Codex Lily) original `site0.py` (sha256 `f04aa8e…`), `revised_v1/site0.py` (sha256 `6daa39a…`), `source-changes.patch`, `test_site0.py`, `test_later_regression.py`, `LATER_REGRESSION.md`, the two REPORTs, the coordinator review and the revised independent probe. Lilitari (Lily) supplied the staged specification; Richard Pemberton directs the project.
**Nature of this document:** static reasoning only. I executed nothing and read no files beyond the verbatim bundle. Every numerical value below is a hand/analytic prediction labelled as such; Red's sandbox run is the arbiter. This is private computational research on a mathematical model, not empirical or safety validation.

---

## 1. Verdict in one paragraph

The revised_v1 repair is mathematically exact and numerically complete for the generic transient path: `q = (f0+e0+rho+d)/(2d)` equals `(B₊−B₀)/d`, is ≥ ½ on the whole admissible domain, and makes every returned amount a positively-weighted mean of nonnegative, relatively-accurate quantities. From this a *uniform relative* forward-error bound follows (≈10⁻⁹² before the final float rounding), with no condition number and no dependence on parameter scale, time, saturation, emptiness, or tiny/large rates. Conservation and positivity hold to float rounding. No numerical patch is required. The findings are about (i) an exact characterisation of the original defect region (it is confined to `B0 == M == S` exactly with `koff·V/(kon·M)` below ≈10⁻¹⁶⁴, and the frozen regression's round-number `koff` values made it even harder to trigger), and (ii) test-coverage gaps: the frozen 24 tests cannot detect a regression in the sibling cancellation-free formulas for the free/empty equilibrium complements when `M ≠ S`, never check `equilibrium()`'s tiny components, and never check extreme parameter scales. A discriminating unittest module, an informational mutant-blindness script, and one optional hardening patch are delivered.

---

## 2. Derivation

### 2.1 Model and roots
`B' = a(M−B)(S−B) − koff·B`, `a = kon/V > 0`, `ρ = koff/a ≥ 0`. Then `B' = a(B−B₋)(B−B₊)` with

- `Δ = d = √((M−S)² + 2ρ(M+S) + ρ²) = B₊ − B₋` (sum of nonnegative terms under the root: relatively accurate at any magnitude of `Δ`, including `Δ ≪ M`);
- `B₋ = 2MS/(M+S+ρ+Δ)` (physical), `B₊ = (M+S+ρ+Δ)/2 ≥ max(M,S) ≥ B₀`;
- complements: `Af_eq = M − B₋ = (Δ − c_f)/2`, `c_f = S−M+ρ`; and since `Δ² − c_f² = 4ρM`, also `Af_eq = 2ρM/(Δ + c_f)`. The code uses the quotient form when `c_f ≥ 0` (cancellation would occur in `Δ − c_f`) and the sum form `(Δ + |c_f|)/2` when `c_f < 0`. `E_eq` is symmetric with `c_e = M−S+ρ`. Both denominators are ≥ `Δ > 0`; the absolute error of `c_f` is ≤ u·(|S−M|+ρ) ≤ 2u·Δ (because `Δ ≥ max(|M−S|, ρ)`), so `Δ + c_f` is relatively accurate. **Verified: the complement formulas in `_roots` are cancellation-free.**

### 2.2 Transient as a weighted mean
Separation of variables: `(B−B₋)/(B−B₊) = r₀·w`, `w = e^{−aΔt}`, `r₀ = (B₀−B₋)/(B₀−B₊)`. Writing `x₀ = B₀−B₋` and `h = 1−w`, solving gives `B(t) = B₋ + x₀·w·Δ/(Δ − x₀h)`. Putting `Q = (Δ−x₀)/Δ = (B₊−B₀)/Δ`:

  `X(t) = (X₀·w + X_eq·Q·h)/(w + Q·h)` for `X ∈ {Af, B, E}` (identical denominator; the identity for `Af`, `E` follows from `Af = M−B`, `E = S−B`).

Because `B₊ − B₀ = (M−B₀ + S−B₀ + ρ + Δ)/2`,

  **`Q = (Af₀ + E₀ + ρ + Δ)/(2Δ) ≥ ½`,**

which is exactly the revised expression. Equality `Q = ½` requires `Af₀ = E₀ = ρ = 0`, i.e. `B₀ = M = S`, `koff = 0`, which the code routes to the repeated-root branch; so on the generic path `Q > ½` and `w + Qh ≥ max(w, h/2) > 0`. The guard `if q < 0` is therefore unreachable (Finding F-8).

### 2.3 Forward error bound (revised kernel, generic path)
Let `u = 5·10⁻⁹⁶` (unit roundoff at 96 digits). Static operation counts give relative errors: inputs `Af₀, E₀, B₀` exact or ≤ u (the differences `M−B₀`, `S−B₀` of ≤17-digit decimals are exact unless exponents differ by > ~79 decades, in which case the error is ≤ u relative); `ρ` ≤ 2u; `Δ` ≤ ~5u; `B₋, Af_eq, E_eq` ≤ ~8u; `Q` ≤ ~8u; `x = aΔt` ≤ ~7u. For `h`: Taylor branch (`x < 0.01`), alternating series with partial sums ≤ x, ≤ ~50u; exp branch, `h ≥ 1−e^{−0.01}` so ≤ ~110u. For `w`: relative ≤ 7ux + u, and its weight share is ≤ e^{−x}, so its contribution to the mean is ≤ 4u absolute against a denominator ≥ ½·h ≥ 0.005 — ≤ 800u. Every remaining operation is a sum/product/quotient of nonnegative terms, so errors add without amplification:

  **|X̂ − X| ≤ K·u·X with K ≲ 10³, i.e. relative error < 10⁻⁹² uniformly over the admissible domain**, for all three amounts including tiny ones, for all `t ≥ 0`. The returned float is then within `2⁻⁵³ + 10⁻⁹²` relative of the exact solution of the (decimal-valued) model — the correctly rounded float or its neighbour.

Corollary (labelled static claim): the bound does not depend on the 96-digit precision except through `u`; the revised formulation would be ≈10⁻²⁵-relative-accurate at the default 28 digits. The extended precision is now a margin, not a necessity.

Special branches are also positive-weighted: `kon = 0` (`f0 + b0·h`, `b0·w`, `e0 + b0·h`); repeated root (`f0/(1+adv)`, `(b0 + m·adv)/(1+adv)`); `ρ = 0, M ≠ S` (exact roots). The same bound applies.

### 2.4 Error of the original formulation (for the record)
`Q_orig = 1 − (B₀ − B̂₋)/Δ` has absolute error `|B̂₋−B₋|/Δ ≤ u·B₋/Δ`, hence relative error ≤ `2u·B₋/(Af₀+E₀+ρ+Δ)`, **unbounded** as the state approaches saturated, equal-inventory, tiny-release. Since any two distinct floats differ by ≥ 2⁻⁵³ relatively, `Af₀+E₀ ≥ 10⁻¹⁶·M` unless `B₀ == M == S` exactly, and `Δ ≥ |M−S| ≥ 10⁻¹⁶·M` unless `M == S` exactly. So the defect is confined to the face `B₀ == M == S`, where the worst-case relative error of `Q` is ≈ `u·√(M/ρ)`: it exceeds the 2·10⁻¹⁴ test tolerance for `ρ/M ≲ 6·10⁻¹⁶⁴` and becomes O(1) (factor 2 in `Af`, `E`) once `Δ < u·M`, i.e. `ρ/M ≲ 6·10⁻¹⁹²`. The error ratio versus time is `2(w+½h)/(w+h)`: → 2 as `t → 0`, → 1 as `t → ∞`. Absolute error ≤ `Af_eq·Qh ≈ 10⁻¹⁰⁰–10⁻²⁰⁰` µmol, which is why absolute inventory tolerances (3·10⁻¹³) never saw it; the 1,350-grid (`ρ ≥ 0.15`) is correctly reported as float-identical.

**Important nuance for test sensitivity:** when `M = 1` and `koff` is an exact power of ten, `√ρ` is a power of ten and `B̂₋ = round₉₆(1 − √ρ + ρ/2 …)` has *actual* rounding error ≈ ρ/2 (not the worst case u), so the original is accidentally exact there down to `Δ ≈ 10⁻⁹⁶` (`koff ≈ 10⁻¹⁹²`). That is why `koff = 10⁻⁴⁰, 10⁻¹⁰⁰` passed and only `10⁻²⁰⁰` failed. A non-round `koff` such as `3·10⁻¹⁷⁰` is predicted to fail the original by ≈3·10⁻¹² relative. The frozen regression therefore has a narrow trigger band for the exact defect it targets.

---

## 3. Findings (all static predictions; exact inputs given)

| # | Finding | Exact inputs / predicted values | Status |
|---|---|---|---|
| F-1 | Revised `q` identity and nonnegativity verified; uniform relative bound (§2.3). Conservation `Af+B = M`, `E+B = S` to ≤ ~2 ulp in float; positivity structural; `B ≤ min(M,S)` cannot be exceeded after float rounding. | e.g. `Vessel(1,1,1,1,1e-200).at(1,1)` → free = empty ≈ `1e-200·(1−e⁻¹)…` wait, M=S case: ≈ `1e-200` (tanh regime, see test), bound = 1.0 exactly | Repair correct; **no numerical patch needed** |
| F-2 | Original defect region is exactly `B0 == M == S` with `koff·V/(kon·M) ≲ 10⁻¹⁶⁴`; factor-2 for ≲10⁻¹⁹²; vanishes as `w → 0`. Round-number `koff` masks it (§2.4). | Original predicted ≈2× too large: `Vessel(1,1,1,1,1e-250).at(1,t)` for `t ∈ {1e-50, 1, 1e50}` (true free = `1e-300, 1e-250, 1e-200`); exact at `t = 1e200` (free = `1e-125`). `Vessel(2,3,3,0.5,1e-220).at(3,0.7)` true free = `2.1e-220`, original ≈ `4.2e-220`. Non-round `koff = 3e-170`: original error ≈ `3e-12` relative (not factor 2). | Characterisation; drives new witnesses |
| F-3 | Frozen `test_later_regression` discriminates the original at a single value (`koff = 1e-200`) and only at round `koff`; its `independent_free_state` hard-codes `V = kon = M = 1`. | — | Coverage gap; new tests add 3 scales, non-round `koff`, different `V, kon, M` |
| F-4 | No frozen test checks tiny **free/empty** components at relative tolerance when `M ≠ S`; the cancellation-free complement formulas in `_roots` are untested. A mutant computing `Af_eq = (Δ−c_f)/2` unconditionally is predicted to pass all 24 frozen tests (including the later regression, where `M = S` keeps `Δ ≫ c_f`). | Witness `Vessel(1,1,2,1,1e-200).at(1,1)`: true free ≈ `6.321205588285577e-201` (= `1e-200·(1−e⁻¹)` to 1e-200 relative), bound = empty = 1.0; mutant predicted free = `0.0`. Mirror `Vessel(1,2,1,1,1e-200).at(1,1)`: empty ≈ `6.3212e-201`. | Coverage gap; mutant test + script delivered |
| F-5 | `equilibrium()` tiny components never checked at relative tolerance. | `Vessel(1,1,2,1,1e-200).equilibrium()` → free ≈ `1e-200`, bound = 1.0, empty = 1.0; `Vessel(1,1,1,1,1e-200).equilibrium()` → free = empty ≈ `1e-100`. | Coverage gap; tests delivered |
| F-6 | Domain extremes: Decimal range (Emax/Emin = ±999999) comfortably holds every intermediate (worst `ρ² ≈ 10¹⁸⁷⁸`, `aΔt ≈ 10¹²⁴⁷`); `exp` of huge negative argument underflows to 0 with untrapped signals; float conversion cannot overflow (amounts ≤ `max(M,S)`) and may underflow to `0.0` legitimately. | `Vessel(1e300,1e-300,1e-300,1e-300,1e300).at(1e-300,1e300)` → `(1e-300, 0.0, 1e-300)`; `Vessel(1,1e308,1e308,1,1).at(0,1)` → `(1e154, 1e308, 1e154)`; `Vessel(1,1,1,1e300,1).at(0,1)` → free = `1e-150`; denormal inputs `Vessel(5e-324,…).at(0,5e-324)` → `(5e-324, 0.0, 5e-324)`. | No defect found; tests delivered. **Caveat:** `localcontext()` inherits the caller's traps/rounding; a caller trapping `Underflow` would turn rapid release into an exception (optional hardening, §6) |
| F-7 | Interface limitation (not a contract violation): `at(bound0, t)` re-enters through a float `bound0`, so `f0 = M − B0` loses all near-saturation information; chained evaluation cannot preserve relative accuracy of tiny complements. Relevant to the future coupled solver, which should carry the *smaller* complement (free or empty) as state or call an entry point accepting it. | `v = Vessel(1,1,1,1,1e-200)`: `v.at(1,0.5).free ≈ 5e-201`, but `v.at(v.at(1,0.3).bound_umol, 0.2).free = v.at(1.0,0.2).free ≈ 2e-201`. | Observation; documented by a test |
| F-8 | `if q < 0` is unreachable (`q ≥ ½`). Harmless. | — | Optional patch A |
| F-9 | Revised REPORT/LATER_REGRESSION statements checked: the identity, nonnegativity, "root formulas unchanged", the 384-digit reference and its RED/GREEN narrative are all consistent with the sources. The claim "not certified over every parameter scale" can now be strengthened to the uniform relative bound of §2.3 (static derivation; execution still needed to confirm no implementation slip at extremes). | — | Documentation suggestion |

---

## 4. Discriminating tests

Place next to `validation/site0/revised_v1/site0.py` and run `python -B -m unittest test_site0_repair_audit -v`. Predicted outcome on revised_v1: all tests pass except that `test_original_kernel_shows_defect` is **skipped** unless the original `site0.py` is reachable (`../site0.py` or `SITE0_ORIGINAL_PATH`), in which case it should pass by demonstrating the original's error.

FILE: validation/site0/revised_v1/test_site0_repair_audit.py
```python
# SPDX-License-Identifier: Apache-2.0
# Provenance: Claude (Anthropic) for Red (Claude), task site0-repair-audit-001,
# auditing Coda's (Codex Lily) SITE0 revised_v1 kernel.  Written statically
# (not executed by the author).  Standard library only; deterministic; no
# network; no file writes.  All parameters are synthetic mathematical
# witnesses; no biological interpretation is implied.
"""Discriminating audit tests for SITE0 revised_v1 (closed-vessel finite sites).

Run from validation/site0/revised_v1 (next to the revised site0.py):
    python -B -m unittest test_site0_repair_audit -v
Optionally set SITE0_ORIGINAL_PATH to the original site0.py to enable the
test that demonstrates the original kernel's saturated-release defect.

References are independent of the kernel:
  (1) the free-oxygen Riccati closed form Af' = koff*(M-Af) - (kon/V)*Af*(Af+S-M)
      evaluated at 400 Decimal digits with deliberately naive algebra; for every
      witness used here the cancellation costs at most ~300 digits;
  (2) second-order Taylor series at tiny times;
  (3) exact limits (float identities, conservation to a few ulps).
"""
import importlib.util
import math
import os
import unittest
from decimal import Decimal, localcontext
from pathlib import Path
from unittest import mock

import site0
from site0 import Vessel

REL = 2e-14          # relative tolerance for tiny components; abs_tol is 0
ORDINARY = 1e-13     # kernel vs reference in the ordinary regime
REFERENCE_DIGITS = 400


def reference_state(volume, oxygen, sites, kon, koff, bound0, time_s):
    """Independent high-precision (free, bound, empty) via the Af-Riccati form."""
    with localcontext() as ctx:
        ctx.prec = REFERENCE_DIGITS
        v, m, s, kon_, koff_, b0, t = (Decimal(str(x)) for x in
                                       (volume, oxygen, sites, kon, koff,
                                        bound0, time_s))
        f0 = m - b0
        if kon_ == 0:
            bound = b0 * (-koff_ * t).exp()
            free = m - bound
        else:
            a = kon_ / v
            rho = koff_ / a
            p = s - m + rho
            disc = (p * p + 4 * rho * m).sqrt()      # = F1 - F2
            if disc == 0:                            # koff == 0 and M == S
                free = f0 / (1 + a * f0 * t)
            else:
                f1 = (-p + disc) / 2                 # positive root (Af_eq)
                f2 = (-p - disc) / 2                 # negative root
                w = (-a * disc * t).exp()
                r0 = (f0 - f1) / (f0 - f2)
                free = (f1 - r0 * w * f2) / (1 - r0 * w)
            bound = m - free
        empty = s - bound
        return float(free), float(bound), float(empty)


def saturated_free_series(volume, oxygen, sites, kon, koff, time_s):
    """Two-term Taylor series of Af(t) from Af(0)=0, i.e. B0 = M <= S."""
    a = kon / volume
    return koff * oxygen * time_s * (1 - (koff + a * (sites - oxygen)) * time_s / 2)


def empty_start_bound_series(volume, oxygen, sites, kon, koff, time_s):
    """Two-term Taylor series of B(t) from B0 = 0."""
    a = kon / volume
    return a * oxygen * sites * time_s * (1 - (a * (oxygen + sites) + koff) * time_s / 2)


def within_ulps(total, target, n=4):
    if target == 0:
        return total == 0
    return abs(total - target) <= n * math.ulp(target)


def _roots_cancelling(m, s, rho):
    """Mutant: equilibrium complements by naive subtraction (hypothetical regression)."""
    if rho == 0:
        bound = min(m, s)
        return bound, m - bound, s - bound, abs(m - s)
    d = ((m - s) ** 2 + 2 * rho * (m + s) + rho * rho).sqrt()
    bound = 2 * m * s / (m + s + rho + d)
    return bound, (d - (s - m + rho)) / 2, (d - (m - s + rho)) / 2, d


def load_original():
    """Locate the original (pre-revision) kernel, identified by its q expression."""
    candidates = []
    env = os.environ.get('SITE0_ORIGINAL_PATH')
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parent.parent / 'site0.py')
    for path in candidates:
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        if 'q = 1-(b0-beq)/d' not in text:
            continue
        spec = importlib.util.spec_from_file_location('site0_original_audit', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, path
    return None, None


ORIGINAL, ORIGINAL_PATH = load_original()

# (volume, oxygen, sites, kon, koff), bound0, times.  Saturated equal
# inventories with tiny release: the original defect family at several scales.
EQUAL_SATURATED = (
    ((1, 1, 1, 1, 1e-250), 1, (1e-50, 1, 1e50, 1e200)),
    ((1, 1, 1, 1, 1e-300), 1, (1, 1e100)),
    ((2, 3, 3, 0.5, 1e-220), 3, (1e-30, 0.7, 1e80)),
    ((1, 1, 1, 1, 3e-170), 1, (1e-6, 1)),          # non-round koff
    ((1, 1, 1, 1, 7e-185), 1, (1e-6, 1)),          # non-round koff
)
# Saturated unequal inventories: one complement tiny, the other O(1).
UNEQUAL_SATURATED = (
    ((1, 1, 2, 1, 1e-200), 1, (1e-8, 1, 1e3)),      # oxygen-limited, free tiny
    ((1, 2, 1, 1, 1e-200), 1, (1e-8, 1, 1e3)),      # site-limited, empty tiny
    ((4, 2, 3, 1, 1e-150), 2, (0.5, 3)),            # a = 0.25, rho = 4e-150
)
# Extreme admissible scales; no exception, conservation, interval, reference.
EXTREMES = (
    ((1e300, 1e-300, 1e-300, 1e-300, 1e300), 1e-300, 1e300),
    ((5e-324, 5e-324, 5e-324, 5e-324, 5e-324), 0, 5e-324),
    ((1, 1e308, 1e308, 1, 1), 0, 1),
    ((1, 1, 1, 1e300, 0), 0, 1e300),
    ((1, 1, 1, 0, 1e300), 1, 1e300),
    ((1e-300, 1, 1, 1, 1e-200), 1, 1e-100),
    ((1, 3, 1, 1e300, 1e-300), 0, 1e-300),
    ((1, 1, 1, 1e-300, 1), 0, 1e300),
)


class RepairAudit(unittest.TestCase):

    def assert_rel(self, actual, expected, rel=REL, note=None):
        self.assertGreater(expected, 0, (note, expected))
        self.assertTrue(math.isclose(actual, expected, rel_tol=rel, abs_tol=0),
                        (note, actual, expected,
                         actual / expected if expected else None))

    def assert_state_close(self, result, expected, rel, note=None):
        for actual, want, field in zip(
                (result.free_umol, result.bound_umol, result.empty_umol),
                expected, ('free', 'bound', 'empty')):
            if want == 0:
                self.assertEqual(actual, 0.0, (note, field, actual))
            else:
                self.assert_rel(actual, want, rel, (note, field))

    def assert_physical(self, params, result):
        _, m, s, _, _ = params
        self.assertGreaterEqual(min(result.free_umol, result.bound_umol,
                                    result.empty_umol), 0)
        self.assertLessEqual(result.bound_umol, min(m, s))
        self.assertTrue(within_ulps(result.free_umol + result.bound_umol, m),
                        (params, result))
        self.assertTrue(within_ulps(result.empty_umol + result.bound_umol, s),
                        (params, result))

    # --- reference validation -------------------------------------------
    def test_reference_matches_kernel_and_closed_forms_in_ordinary_regime(self):
        cases = (((3, 4, 2, 1.2, 0.7), 0.6, 2, None),
                 ((2, 3, 2, 4, 2), 0, 50, (math.sqrt(3), 3 - math.sqrt(3), math.sqrt(3) - 1)),
                 ((2, 3, 1, 1, 0), 0, 2, None),
                 ((4, 2, 2, 2, 0), 0.5, 3, (6 / 13, 20 / 13, 6 / 13)),
                 ((2, 3, 2, 0, 0.8), 0.75, 3.7, None))
        for params, b0, t, closed in cases:
            with self.subTest(params=params, b0=b0, t=t):
                ref = reference_state(*params, b0, t)
                self.assert_state_close(Vessel(*params).at(b0, t), ref, ORDINARY, 'kernel')
                if closed is not None:
                    for r, c in zip(ref, closed):
                        self.assert_rel(r, c, ORDINARY, 'closed form')
        b = 3 * (1 - math.exp(-2)) / (3 - math.exp(-2))
        self.assert_rel(reference_state(2, 3, 1, 1, 0, 0, 2)[1], b, ORDINARY)
        self.assert_rel(reference_state(2, 3, 2, 0, 0.8, 0.75, 3.7)[1],
                        0.75 * math.exp(-0.8 * 3.7), ORDINARY)

    # --- the repaired defect family at several scales ---------------------
    def test_equal_inventory_saturated_tiny_release_across_scales(self):
        for params, b0, times in EQUAL_SATURATED:
            for t in times:
                with self.subTest(params=params, t=t):
                    r = Vessel(*params).at(b0, t)
                    free, bound, empty = reference_state(*params, b0, t)
                    self.assert_rel(r.free_umol, free)
                    self.assert_rel(r.empty_umol, empty)
                    self.assertEqual(r.bound_umol, float(b0))
                    self.assert_physical(params, r)

    def test_unequal_inventory_saturated_tiny_release(self):
        for params, b0, times in UNEQUAL_SATURATED:
            for t in times:
                with self.subTest(params=params, t=t):
                    r = Vessel(*params).at(b0, t)
                    self.assert_state_close(r, reference_state(*params, b0, t), REL)
                    self.assert_physical(params, r)

    # --- series references (independent of any root algebra) --------------
    def test_saturated_tiny_time_matches_second_order_series(self):
        for params in ((1, 1, 2, 1, 1e-200), (1, 1, 1, 1, 1e-250), (2, 3, 3, 0.5, 1e-220)):
            with self.subTest(params=params):
                v, m, s, kon, koff = params
                t = 1e-8
                r = Vessel(*params).at(m, t)
                self.assert_rel(r.free_umol, saturated_free_series(*params, t), 1e-13)

    def test_empty_start_tiny_time_large_koff_matches_series(self):
        params, t = (1, 1, 1, 1, 1e6), 1e-14
        r = Vessel(*params).at(0, t)
        self.assert_rel(r.bound_umol, empty_start_bound_series(*params, t), 1e-13)

    # --- equilibrium tiny components ---------------------------------------
    def test_equilibrium_tiny_components_are_relatively_accurate(self):
        for params in ((1, 1, 2, 1, 1e-200), (1, 2, 1, 1, 1e-200),
                       (1, 1, 1, 1, 1e-200), (4, 2, 3, 1e-20, 1)):
            with self.subTest(params=params):
                eq = Vessel(*params).equilibrium()
                self.assertIsNotNone(eq)
                # huge time drives the reference to its stable root
                self.assert_state_close(eq, reference_state(*params, 0, 1e9), REL)
        self.assert_rel(Vessel(1, 1, 2, 1, 1e-200).equilibrium().free_umol, 1e-200)
        self.assert_rel(Vessel(1, 2, 1, 1, 1e-200).equilibrium().empty_umol, 1e-200)
        self.assert_rel(Vessel(1, 1, 1, 1, 1e-200).equilibrium().free_umol, 1e-100)

    # --- large-rate limits --------------------------------------------------
    def test_large_rate_limits_are_relatively_accurate(self):
        r = Vessel(2, 3, 2, 1, 1e6).at(1, 1)
        self.assert_state_close(r, reference_state(2, 3, 2, 1, 1e6, 1, 1), REL)
        r = Vessel(1, 1, 1, 1e300, 1).at(0, 1)
        self.assert_rel(r.free_umol, 1e-150)
        self.assert_rel(r.empty_umol, 1e-150)
        self.assertEqual(r.bound_umol, 1.0)

    # --- extreme scales ---------------------------------------------------
    def test_extreme_scales_conserve_and_stay_in_interval(self):
        for params, b0, t in EXTREMES:
            with self.subTest(params=params, b0=b0, t=t):
                r = Vessel(*params).at(b0, t)
                self.assert_physical(params, r)
                self.assert_state_close(r, reference_state(*params, b0, t), 1e-12)

    def test_saturated_bound_returns_exact_inventory_float(self):
        self.assertEqual(Vessel(1, 1, 1, 1, 1e-200).at(1, 1).bound_umol, 1.0)
        self.assertEqual(Vessel(2, 3, 1, 1, 0).at(0, 1e12).bound_umol, 1.0)
        r = Vessel(1, 1, 2, 1, 1e-200).at(1, 1)
        self.assertEqual((r.bound_umol, r.empty_umol), (1.0, 1.0))

    # --- regression-detection power -------------------------------------
    def test_cancelling_complement_mutant_is_detected_by_unequal_witness(self):
        expected = reference_state(1, 1, 2, 1, 1e-200, 1, 1)[0]
        with mock.patch.object(site0, '_roots', _roots_cancelling):
            mutant_free = Vessel(1, 1, 2, 1, 1e-200).at(1, 1).free_umol
        self.assertFalse(math.isclose(mutant_free, expected, rel_tol=REL, abs_tol=0),
                         (mutant_free, expected))
        self.assert_rel(Vessel(1, 1, 2, 1, 1e-200).at(1, 1).free_umol, expected)

    def test_frozen_witnesses_are_predicted_blind_to_complement_mutant(self):
        """Documents coverage gap F-4; a failure here means the frozen suite is
        less blind than statically predicted (useful information, not a kernel
        defect)."""
        with mock.patch.object(site0, '_roots', _roots_cancelling):
            frozen = Vessel(1, 1, 1, 1, 1e-200).at(1, 1)
            rapid = Vessel(2, 3, 2, 1, 1e6).at(1, 1)
        expected = reference_state(1, 1, 1, 1, 1e-200, 1, 1)[0]
        self.assertTrue(math.isclose(frozen.free_umol, expected, rel_tol=REL, abs_tol=0))
        self.assertLess(rapid.bound_umol, 3e-6)
        self.assertGreater(rapid.free_umol, 2.999997)

    @unittest.skipUnless(ORIGINAL is not None,
                         'original site0.py not found; set SITE0_ORIGINAL_PATH')
    def test_original_kernel_shows_defect(self):
        doubled = 0
        exceeded = 0
        for params, b0, times in EQUAL_SATURATED:
            v, m, s, kon, koff = params
            a = kon / v
            d = math.sqrt(2 * (koff / a) * (m + s))     # ~Delta for M == S
            for t in times:
                with self.subTest(params=params, t=t):
                    free = ORIGINAL.Vessel(*params).at(b0, t).free_umol
                    expected = reference_state(*params, b0, t)[0]
                    ratio = free / expected
                    if koff <= 1e-220 and a * d * t < 1e-20:
                        # Delta << 10^-96 M: Beq rounds to M, q_orig = 1 -> factor 2
                        self.assertTrue(math.isclose(ratio, 2, rel_tol=1e-9), ratio)
                        doubled += 1
                    elif koff <= 1e-220:
                        # w == 0 regime: the original is exact there
                        self.assertTrue(math.isclose(ratio, 1, rel_tol=REL), ratio)
                    elif not math.isclose(ratio, 1, rel_tol=REL):
                        exceeded += 1
        self.assertGreater(doubled, 0)
        # Non-round koff (3e-170, 7e-185): worst-case q error ~1e-12 relative;
        # at least one of the four subcases is predicted to exceed 2e-14.
        self.assertGreater(exceeded, 0)

    # --- interface observation F-7 -------------------------------------
    def test_float_bound_reentry_cannot_carry_saturated_information(self):
        v = Vessel(1, 1, 1, 1, 1e-200)
        direct = v.at(1, 0.5).free_umol
        step = v.at(1, 0.3)
        chained = v.at(step.bound_umol, 0.2).free_umol
        self.assertEqual(step.bound_umol, 1.0)
        self.assert_rel(direct, 5e-201, 1e-12)
        self.assert_rel(chained, 2e-201, 1e-12)


if __name__ == '__main__':
    unittest.main()
```

Notes on predicted values inside the tests (static): for `M = S`, `Af(t) ≈ √(ρM)·tanh(a√(ρM)·t)`, hence `≈ koff·M·t` for `t ≪ 1/(a√(ρM))` and `≈ √(ρM)` beyond; for `M < S` saturated, `Af(t) ≈ (ρM/(S−M))·(1−e^{−a(S−M)t})` (≈ `1e-200·(1−e^{−t})` for the `(1,1,2,1,1e-200)` witness). `assert_physical` uses a 4-ulp conservation tolerance, ~10⁴× tighter than the frozen 3·10⁻¹³.

FILE: validation/site0/revised_v1/audit_mutant_blindness.py
```python
# SPDX-License-Identifier: Apache-2.0
# Provenance: Claude (Anthropic) for Red (Claude), task site0-repair-audit-001.
"""Informational: run the frozen SITE0 suites and the audit module against a
complement-cancelling mutant of site0._roots.  Prints counts only; writes
nothing.  Run from validation/site0/revised_v1 with the copied frozen
test_site0.py, validation_helpers.py, mutants.py and test_later_regression.py:
    python -B audit_mutant_blindness.py
Static prediction: frozen suites 24 run / 0 failures under the mutant
(blind); audit module shows failures in the unequal-inventory, equilibrium
and mutant-detection tests (detected).
"""
import sys
import unittest
from unittest import mock

import site0
from test_site0_repair_audit import _roots_cancelling


def run(names):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        try:
            suite.addTests(loader.loadTestsFromName(name))
        except Exception as exc:  # missing frozen helper files, etc.
            print('could not load', name, '->', repr(exc))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0).run(suite)
    return result.testsRun, len(result.failures), len(result.errors), len(result.skipped)


if __name__ == '__main__':
    with mock.patch.object(site0, '_roots', _roots_cancelling):
        frozen = run(['test_site0', 'test_later_regression'])
        audit = run(['test_site0_repair_audit'])
    print('frozen suites under mutant (run, failures, errors, skipped):', frozen)
    print('audit module under mutant (run, failures, errors, skipped):', audit)
```

---

## 5. Would the frozen tests detect a regression? (summary)

| Hypothetical regression | Frozen 24 tests | New audit module |
|---|---|---|
| Revert `q` to `1−(b0−beq)/d` | Caught, but only by `koff = 1e-200` (one of nine subcases); round `koff` values are accidentally benign for the original down to `koff ≈ 1e-192` | Caught at 3 scales, non-round `koff`, different `V, kon, M` |
| Naive `Af_eq = (Δ−c_f)/2`, `E_eq = (Δ−c_e)/2` (sibling cancellation) | **Not caught** (prediction; `M = S` witnesses keep `Δ ≫ c_f`; grid uses 3e-13 absolute) | Caught (`test_cancelling_complement_mutant…`, unequal-inventory and equilibrium tests) |
| Drop Taylor branch in `_decay` | Caught (`test_tiny_time…`) | Also caught |
| Drop repeated-root branch | Caught (DivisionByZero / equal-root case) | Also caught |
| Reduce working precision | Not detectable by either (and need not be: §2.3 corollary) | — |
| Extreme-scale exception (e.g. trapped Underflow in caller context) | Not covered | Partially covered (`EXTREMES`), default context only |

---

## 6. Patches

**Numerical correctness: none required.** The following are optional hardening for a *new* `revised_v2` candidate; frozen artifacts must not be edited in place.

FILE: validation/site0/revised_v1/optional-hardening-guard.patch
```
--- revised_v1/site0.py
+++ revised_v2/site0.py
@@ -120,7 +120,8 @@
             q = (f0+e0+rho+d)/(2*d)
             equilibrium_weight = q*h
             denominator = w+equilibrium_weight
-            if q < 0 or denominator <= 0:
+            # q = (Bplus-B0)/d >= 1/2 exactly; 0.49 leaves rounding margin.
+            if q < Decimal('0.49') or denominator <= 0:
                 raise ArithmeticError('Invalid analytical interpolation weights')
             return _amounts((f0*w+feq*equilibrium_weight)/denominator,
                             (b0*w+beq*equilibrium_weight)/denominator,
```
(The hunk header line number is approximate; apply with fuzz or by hand — it is a one-line edit plus a comment.)

Optional hardening B (described, not diffed): make the kernel independent of the caller's thread-local decimal context by replacing both `with localcontext() as context: context.prec = 96` blocks with `with localcontext(Context(prec=96)) as context:` (importing `Context`). This fixes traps/rounding to `DefaultContext` values regardless of caller state (F-6 caveat). Behaviour under the default context is unchanged.

Optional documentation C: in `revised_v1/REPORT.md` and the module docstring, the "not certified over every scale" statement can be supplemented by the §2.3 result: every returned amount is within `2⁻⁵³ + 10⁻⁹²` relative of the exact decimal-input solution, uniformly over the admissible domain — pending Red's confirmation of the extreme-scale tests.

---

## 7. Left unimplemented / limitations of this audit

- Nothing was executed; every "predicted" value and the mutant-blindness claim await Red's sandbox run. If `test_frozen_witnesses_are_predicted_blind…` or the `exceeded > 0` assertion in `test_original_kernel_shows_defect` fails, that indicates my static prediction of actual (not worst-case) rounding error was off, not a kernel defect — please report the numbers for correction.
- The 400-digit reference uses the Af-Riccati form with naive algebra; it is well-conditioned for the listed witnesses (≤ ~300 digits lost) but is not a general-purpose reference for arbitrary inputs.
- No test varies the decimal context traps (F-6 caveat); no interval arithmetic or certified enclosure is provided.
- The coupled-solver recommendation in F-7 is a modelling-interface observation only.

Credit: Coda (Codex Lily) for the kernel, repair, regression and reports; Richard (Andrei) Pemberton for direction; Lilitari (Lily) for the staged specification; earlier Claude Fable 5.1 contributions as recorded in the project's ATTRIBUTION.md (none appear in this bundle's sources). New code here is offered under Apache-2.0, prose CC BY 4.0, consistent with the project's license map.