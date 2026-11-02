# SITE0 revised_v1 — diagnosis of the three wave-10 audit failures (task `site0-repair-audit-003`)

**Author:** Claude (Anthropic) for Red (Claude). **Kernel under audit:** Coda's (Codex Lily) `revised_v1/site0.py` (sha256 `6daa39a…`). **Audited artefacts:** the wave-10 audit answer (mine, sha256 `e77ae1b…`), Red's two receipts (`_rerun_revised.txt`, `_study_mutants.out`) and the revised kernel, all verbatim above. Richard (Andrei) Pemberton directs the project; Lilitari (Lily) supplied the staged specification; earlier Claude Fable 5.1 contributions are as recorded in the project's attribution files (none appear in this bundle).

**Nature of this document:** static reasoning only. I executed nothing. Every numerical statement below is either (a) quoted from Red's receipts, marked *[executed]*, or (b) a hand trace of the quoted source code, marked *[static]*. Private computational research on a mathematical model; no physiology, no safety or empirical claims.

---

## 1. Verdict

**All three failures are on the test side. The revised kernel is correct on every failing witness; no kernel change is required.**

| # | Failing subtest *[executed]* | Classification | Root cause |
|---|---|---|---|
| 1 | `test_equilibrium_tiny_components…` at `(1,1,1,1,1e-200)`: kernel `equilibrium().free = 1e-100`, reference `9.99999999e-10` | **Test design error** (reference misused) | The test took `reference_state(…, 0, 1e9)` as "the equilibrium". For this witness the relaxation time is `1/(a·Δ) = 5·10⁹⁹ s`; `t = 10⁹ s` is 5·10⁹⁰ relaxation times too short. The reference correctly returned the *transient* `1/(1+10⁹)`. The kernel's `1e-100 = √(ρM)` is the correct equilibrium. |
| 2 | `test_extreme_scales…` at `(1e300,1e-300,1e-300,1e-300,1e300), b0=1e-300, t=1e300`: kernel `free = 1e-300`, reference `0.0` | **Test reference numerical defect** | My wave-10 reference used the naive root `f1 = (−p+disc)/2` with `p ≈ disc ≈ ρ = 10⁹⁰⁰`, `f1 = 10⁻³⁰⁰`: 1200 digits of cancellation at 400 digits → `f1 = 0` exactly → reference state `(0, 1e-300, 0)`, i.e. "nothing dissociates at koff = 10³⁰⁰ after 10³⁰⁰ s". Nonsense. Kernel `(1e-300, 0.0, 1e-300)` is exact to the last bit (§2.2). |
| 3 | `test_extreme_scales…` at `(1,1,1,1e-300,1), b0=0, t=1e300`: kernel `bound = 1e-300`, reference `0.0` | **Test reference numerical defect** | Same reference, different step: `disc = √(ρ²+4ρ) = 10³⁰⁰ + 2 − 2·10⁻³⁰⁰`; the `−2·10⁻³⁰⁰` term (which encodes `B_eq = 10⁻³⁰⁰`) sits 600 digits below the leading digit → lost at 400 digits → `f1 = 1` exactly, `bound = m − f1 = 0`. Kernel `(1.0, 1e-300, 1.0)` is exact (§2.3). |

None of the inputs is out of the kernel's admissible domain (finite nonnegative floats, `0 ≤ b0 ≤ min(M,S)`, finite `t ≥ 0`); only the *reference's* conditioning domain was exceeded. My wave-10 statement "for every witness used here the cancellation costs at most ~300 digits" was wrong for 2 of the 8 `EXTREMES` witnesses (actual: ≈1200 and ≈600 digits). I regret the error; the corrected module below replaces the silent assumption with explicit digit accounting that raises instead of returning garbage.

Also from the receipts: the mutant-blindness figure for the frozen suites, `(2 run, 0 failures, 2 errors)`, is an **import artefact** (`ModuleNotFoundError: test_site0`, `test_later_regression`), not a blindness measurement — the frozen suites were not next to the revised kernel. That run is **inconclusive** and must be repeated with the frozen files reachable (script revised in §4.3). The audit module's 16 failures under the mutant decompose as 15 genuine detections + 1 spurious (the failure-1 subtest, which fails identically with or without the mutant).

---

## 2. Hand traces *[static]* of the three witnesses through the quoted code

Notation: `a = kon/V`, `ρ = koff/a`, `Δ = √((M−S)² + 2ρ(M+S) + ρ²)`, 96-digit Decimal in the kernel, 400-digit in the reference.

### 2.1 Failure 1 — `(V,M,S,kon,koff) = (1,1,1,1,1e-200)`

Kernel `equilibrium()` → `_roots(1, 1, 1e-200)`: `d = √(4e-200 + 1e-400) = 2e-100·(1 + 1.25e-201) → 2E-100` at 96 digits; `cf = 1e-200 ≥ 0` → `free = 2ρm/(d+cf) = 2e-200/(2e-100 + 1e-200) = 1e-100·(1 − 5e-101) → 1E-100` → float `1e-100`. This is `Af_eq = √(ρM)` for equal inventories: **correct**, and the test's own direct assertion `assert_rel(…equilibrium().free_umol, 1e-100)` passed in the same run *[executed]*.

Reference `reference_state(1,1,1,1,1e-200, b0=0, t=1e9)`: `p = 1e-200`, `disc = 2e-100 + 2.5e-301`, `f1 ≈ 1e-100`, `f2 ≈ −1e-100`, `w = exp(−2e-91)`, `r0 = (1 − 1e-100)/(1 + 1e-100)`, denominator `1 − r0·w ≈ 2e-91 + 2e-100 = 2e-91·(1 + 1e-9)`, numerator `≈ 2e-100` → `free ≈ 1e-9/(1 + 1e-9) = 1/(1 + 10⁹) = 9.99999999000…e-10` → repr `9.99999999e-10`, exactly the receipt value. This is the correct transient: from `B0 = 0` with `ρ → 0` the free amount decays as `f0/(1 + a f0 t) = 1/(1 + 10⁹)` until `t ~ 1/(aΔ) = 5e99`. **The reference was right; the test asked it the wrong question.** (The other three parameter sets in that loop have `a·Δ ≥ 1`, so `t = 1e9` *is* beyond relaxation there — which is why only one subtest failed.)

### 2.2 Failure 2 — `(1e300, 1e-300, 1e-300, 1e-300, 1e300)`, `b0 = 1e-300`, `t = 1e300`

Kernel: `a = 1e-600`, `ρ = 1e900`, `f0 = e0 = 0`. `_roots`: `d = √(2·1e900·2e-300 + 1e1800) = 1e900·√(1 + 4e-1200) → 1E+900`; `bound = 2e-600/(2e-300 + 2e900) → 2e-600/2E+900 = 1E-1500`; `cf = ce = 1e900 ≥ 0` → `free = empty = 2e600/2e900 = 1E-300`. `_decay(a·d·t = 1e600)`: `w = exp(−1e600) = 0` (Decimal underflow, untrapped by default), `h = 1`. `q = (0 + 0 + 1e900 + 1e900)/2e900 = 1`; denominator `= 1`. Result `(1E-300, 1E-1500, 1E-300)` → floats **`(1e-300, 0.0, 1e-300)`** (the bound amount `1e-1500` underflows legitimately: it is below the smallest subnormal). Exact answer: `B_eq = MS/B₊ ∈ [1e-1500(1 − 4e-1200), 1e-1500]`, `a·Δ·t ≥ koff·t = 1e600` → fully relaxed. The kernel's floats are the correctly rounded exact values; the receipt confirms `free = 1e-300` and the 4-ulp conservation checks passed *[executed]*. This is also exactly the value predicted in my wave-10 finding F-6 — the test module contradicted its own audit's prediction because it trusted the naive reference instead of encoding F-6.

Reference: `p = 1e900`, `disc = √(1e1800 + 4e600) → 1E+900` at 400 digits (relative correction `2e-1200`), `f1 = (−1e900 + 1e900)/2 = 0`, `w = 0`, `r0 = 0`, `free = 0`, `bound = m − 0 = 1e-300`, `empty = 0` → `(0.0, 1e-300, 0.0)`. Garbage; needs ≥ 1220 digits for `f1` alone.

### 2.3 Failure 3 — `(1, 1, 1, 1e-300, 1)`, `b0 = 0`, `t = 1e300`

Kernel: `a = 1e-300`, `ρ = 1e300`, `f0 = e0 = 1`. `d = √(4e300 + 1e600) = 1e300·√(1 + 4e-300) → 1E+300` at 96 digits; `bound = 2/(2 + 2e300) → 2/2E+300 = 1E-300`; `cf = ce = 1e300` → `free = empty = 2e300/2e300 = 1`. `_decay(1e300)`: `w = 0`, `h = 1`. `q = (1 + 1 + 1e300 + 1e300)/2e300 = 1 + 1e-300 → 1`. Result `(1, 1E-300, 1)` → **`(1.0, 1e-300, 1.0)`**. Exact: `B_eq = 1/B₊`, `B₊ = (2 + ρ + Δ)/2 ∈ (ρ + 2 − 1e-300, ρ + 2)` → `B_eq = 1e-300·(1 − 2e-300 + …)` → nearest float `1e-300`; `Af_eq = E_eq = 1 − 1e-300` → `1.0`; relaxed since `aΔt ≥ 1e300`. Receipt confirms `bound = 1e-300`, `free` matched `1.0` to `1e-12`, conservation to 4 ulps *[executed]*.

Reference: `disc → 1e300 + 2` at 400 digits (the `−2e-300` term is 600 digits down), `f1 = (−1e300 + 1e300 + 2)/2 = 1`, `w = 0`, `r0 = 0`, `free = 1`, `bound = 1 − 1 = 0`, `empty = 1` → `(1.0, 0.0, 1.0)`. The information about `B_eq` is at relative level `MS/ρ² = 1e-600` inside `disc`; needs ≥ 620 digits.

### 2.4 General conditioning bound for the wave-10 (naive) reference *[static]*

Digits lost: `log₁₀(Δ/Af_eq)` in `f1` when `p ≥ 0` (≈ `2·log₁₀(ρ/√(ρM))` when `ρ ≫ M,S`), plus `log₁₀(M/B_eq) ≈ 2·log₁₀(ρ/√(MS))` in `bound = m − free`, plus `log₁₀(X_eq/X(t))` in the `r0` numerator for saturated starts at small `t`. At 400 digits the route is therefore trustworthy only for `ρ ≲ 10¹⁰⁰·√(MS)` and `Δ² ≲ 10³⁰⁰·ρ·min(M,S)` and moderate `X_eq/X(t)`. All 21 `EQUAL_/UNEQUAL_SATURATED` witnesses satisfy this (≤ 250 digits lost), the ordinary-regime cases trivially, and 6 of 8 `EXTREMES`; witnesses A and B (above) do not.

---

## 3. Which inputs the revised kernel can be trusted on

**Domain D (the kernel's admissible domain).** `volume_ml` a finite float `> 0`; `oxygen_umol, sites_umol, kon_ml_per_umol_s, koff_per_s` finite floats `≥ 0` (subnormals allowed); `bound0_umol` a finite float with `0 ≤ b0 ≤ min(M,S)` in decimal-repr values; `time_s` a finite float `≥ 0`. All other inputs raise `ValueError` by construction.

**Claim (static, §2.3 of the wave-10 audit; now spot-checked by execution at both ends of the float range).** For every input in D, each of the three returned amounts of `at()` is the float nearest to a number within `≈10⁻⁹²` relative of the exact solution `X(t)` of `B' = (kon/V)(M−B)(S−B) − koff·B` with parameters equal to the **shortest-repr decimal values** of the float inputs (`Decimal(str(x))`); i.e. it is the correctly rounded float or one of its two neighbours, uniformly in parameter scale, time, saturation, emptiness and rate ratios. `equilibrium()` likewise for the stable root. Conservation `free + bound = M`, `empty + bound = S` holds to a few ulps *after* float rounding (not exactly). Underflow of a true amount below ≈`2.5·10⁻³²⁴` returns `0.0` legitimately (observed: case A's bound). No intermediate can overflow the Decimal range (`|exponent| < 1900 ≪ 999999`) and no denominator can vanish on any branch (`w + q·h ≥ max(w, h/2) > 0`).

**Executed evidence (Red's receipts):** against revised_v1 the module's 13 tests comprise ≈ 60 witness evaluations; every kernel value compared to a *valid* reference or closed form agreed to the stated tolerances (2·10⁻¹⁴ relative for tiny components, 4 ulps for conservation), including: the saturated equal-inventory family at `koff = 3e-170, 7e-185, 1e-220, 1e-250, 1e-300` with non-unit `V, kon, M`; unequal inventories with one complement at `1e-200`/`1e-150`; `kon = 1e300`; `koff = 1e6`; subnormal inputs; `M = S = 1e308`; `t = 1e300` with `w = 0`; tiny-time series to 10⁻¹³. The two extreme witnesses that "failed" are shown above to be kernel-exact; the original kernel's defect was reproduced by the same module (`test_original_kernel_shows_defect` ok) *[executed]*.

**Conditions and caveats on the trust statement.**
1. It assumes the **default decimal context traps** at the call site (`Overflow`, `InvalidOperation`, `DivisionByZero` trapped; `Underflow`, `Subnormal`, `Inexact`, `Rounded`, `Clamped` untrapped). The kernel inherits the caller's thread-local context via `localcontext()`; a caller trapping `Underflow` would turn rapid relaxation (`w` underflowing to 0) into an exception — optional hardening B of the wave-10 audit removes this dependency.
2. The parameters solved for are the decimal values printed by `repr`, which differ from the binary values of the floats by up to `2⁻⁵³` relative. For 17-significant-digit literals this is the user's intent; it is not "the binary model".
3. Accuracy is relative to the *given* inputs. A float `bound0` that encodes a saturated state (`b0 == M`) carries no information about a previous tiny complement; chained evaluation through `bound_umol` therefore cannot preserve tiny complements (wave-10 F-7). This is an interface limitation of re-entry, not a kernel error.
4. `0.0` returned for a component means `< ≈2.5·10⁻³²⁴ µmol` in the model, not "exactly zero".
5. Trust is about the mathematical model's solution only. Nothing here is a physiological, empirical or safety statement.

**Still pending execution** (static predictions awaiting Red): the corrected module (§4) is predicted to pass 17/17 on revised_v1, including the two extreme witnesses against both the repaired reference and explicit asymptotic values.

---

## 4. Minimal fixes and deliverables

### 4.1 Fix list

| Fix | Where | Change |
|---|---|---|
| F-a | equilibrium test | Compare `equilibrium()` with `reference_equilibrium()` (stable roots at 400 digits) and with the transient evaluated at `1000 × 1/(a·Δ)` (relaxation-scaled), not at a fixed `1e9`. |
| F-b | `reference_state` | Replace the naive Af-Riccati algebra by Vieta-stabilised roots and the cancellation-free weighted-mean transient; the single remaining subtraction `B₊ − B0` is digit-accounted and the precision is doubled automatically (400 → ≤ 6400) when insufficient. Both extreme witnesses are then exact at 400 digits (trace in §2.2–2.3 carries over verbatim). |
| F-c | `reference_state_naive` | Keep the wave-10 route as an algebraically different cross-check, with explicit `_lost/_require` digit accounting that **raises** `ReferenceConditioningError` instead of returning garbage. New test asserts the two routes agree wherever the naive route is conditioned and that it rejects exactly the two huge-ρ witnesses. |
| F-d | new oracles independent of any root algebra | (i) exact rational-root witnesses: for `M = S = m`, `V = kon = 1`, `koff = m·y²/(1−y)` one has `Δ = koff + 2my`, `B₋ = m(1−y)`, `Af_eq = E_eq = m·y` exactly, and saturated/empty-start transients `(1−w)/(5+4w)`, `(5+4w)/(25−16w)` for `(1,1,1,1,0.05)`, `w = e^{−0.9}`; (ii) the asymptotic limits of §2.2–2.3 encoded as explicit expected tuples; (iii) the near-repeated-root transient `1/(1+10⁹)`. |
| F-e | mutant script | Discover the frozen suites (`../` or `$SITE0_FROZEN_TESTS_DIR`), import them explicitly, print which `site0` they bind to, and print **INCONCLUSIVE** instead of counts when they cannot be imported. |

### 4.2 Corrected audit module (full replacement of the wave-10 file)

Run from `validation/site0/revised_v1` (next to the revised `site0.py`):
`python -B -m unittest test_site0_repair_audit -v`

FILE: validation/site0/revised_v1/test_site0_repair_audit.py
```python
# SPDX-License-Identifier: Apache-2.0
# Provenance: Claude (Anthropic) for Red (Claude), tasks site0-repair-audit-001
# (wave 10) and site0-repair-audit-003 (wave 11), auditing Coda's (Codex Lily)
# SITE0 revised_v1 kernel.  Written statically (not executed by the author);
# Red executes.  Standard library only; deterministic; no network; no file
# writes.  All parameters are synthetic mathematical witnesses; no biological
# interpretation is implied.
"""Discriminating audit tests for SITE0 revised_v1 (closed-vessel finite sites).

Wave-11 revision.  Red's execution of the wave-10 module against revised_v1
showed three failures, all on the test side (task site0-repair-audit-003):
  * the equilibrium test compared equilibrium() with a transient at t = 1e9,
    which for (1,1,1,1,1e-200) is 5e90 relaxation times too short;
  * the naive Af-Riccati reference lost ~1200 / ~600 digits for the two
    EXTREMES witnesses with koff*V/kon >= 1e300*sqrt(M*S) and returned garbage.
Changes: reference_state() uses Vieta-stabilised roots and the weighted-mean
transient (its only subtraction, B_plus - B0, is digit-accounted and precision
is raised automatically); the wave-10 route is kept as reference_state_naive()
with explicit conditioning checks and cross-validated; the equilibrium test uses
the roots directly plus a relaxation-scaled time; exact rational-root witnesses,
asymptotic limits and a near-repeated-root transient add kernel-independent
oracles.  Tests that passed in wave 10 are unchanged.

Run from validation/site0/revised_v1 (next to the revised site0.py):
    python -B -m unittest test_site0_repair_audit -v
Optionally set SITE0_ORIGINAL_PATH to the original site0.py to enable the test
that demonstrates the original kernel's saturated-release defect.
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

REL = 2e-14             # relative tolerance for tiny components; abs_tol is 0
ORDINARY = 1e-13        # kernel vs reference in the ordinary regime
REFERENCE_DIGITS = 400
MAX_REFERENCE_DIGITS = 6400
GUARD_DIGITS = 60       # digits that must survive every accounted cancellation


class ReferenceConditioningError(ArithmeticError):
    """The reference's working precision cannot absorb a cancellation."""


def _decimals(*values):
    return tuple(Decimal(str(x)) for x in values)


def _lost(result, *operands):
    """Decimal digits cancelled when `result` was formed from `operands`
    (operands are passed for their magnitudes; include the magnitude of any
    intermediate whose absolute rounding error propagates into `result`)."""
    tops = [x.adjusted() for x in operands if x != 0]
    if not tops:
        return 0
    if result == 0:
        return math.inf
    return max(0, max(tops) - result.adjusted())


def _require(digits, lost, what):
    if lost + GUARD_DIGITS > digits:
        raise ReferenceConditioningError(
            '%s cancels %s digits at precision %d' % (what, lost, digits))


def _h_and_w(x):
    """(1 - exp(-x), exp(-x)) for Decimal x >= 0; alternating series below 1/2
    so that h keeps full relative accuracy for tiny x."""
    if x == 0:
        return Decimal(0), Decimal(1)
    if x < Decimal('0.5'):
        term = total = x
        n = 1
        while True:
            n += 1
            term = -term * x / n
            new_total = total + term
            if new_total == total:
                return total, 1 - total
            total = new_total
    w = (-x).exp()
    return 1 - w, w


def _reference_roots(m, s, rho):
    """Roots at the active precision.  Large roots by the sum form, small
    roots by Vieta's product (textbook stabilisation).  Requires m, s > 0."""
    delta = ((m - s) ** 2 + 2 * rho * (m + s) + rho * rho).sqrt()
    b_plus = (m + s + rho + delta) / 2
    b_minus = m * s / b_plus
    p_f = s - m + rho                       # Af^2 + p_f*Af - rho*m = 0
    f_eq = 2 * rho * m / (p_f + delta) if p_f > 0 else (delta - p_f) / 2
    p_e = m - s + rho                       # E^2 + p_e*E - rho*s = 0
    e_eq = 2 * rho * s / (p_e + delta) if p_e > 0 else (delta - p_e) / 2
    return b_plus, b_minus, f_eq, e_eq, delta


def _reference_state_at(digits, volume, oxygen, sites, kon, koff, bound0, time_s):
    with localcontext() as ctx:
        ctx.prec = digits
        v, m, s, kon_, koff_, b0, t = _decimals(volume, oxygen, sites, kon, koff,
                                                bound0, time_s)
        f0, e0 = m - b0, s - b0
        if t == 0 or min(m, s) == 0 or (kon_ == 0 and koff_ == 0):
            return float(f0), float(b0), float(e0)
        if kon_ == 0:
            h, w = _h_and_w(koff_ * t)
            return float(f0 + b0 * h), float(b0 * w), float(e0 + b0 * h)
        a = kon_ / v
        rho = koff_ / a
        b_plus, b_minus, f_eq, e_eq, delta = _reference_roots(m, s, rho)
        if delta == 0:                       # rho == 0 and m == s: repeated root
            advance = a * f0 * t
            return (float(f0 / (1 + advance)),
                    float((b0 + m * advance) / (1 + advance)),
                    float(e0 / (1 + advance)))
        # Q = (B_plus - B0)/Delta evaluated by the *deviation* route (the route
        # the original kernel used at 96 digits); the kernel's identity
        # Q = (f0+e0+rho+Delta)/(2 Delta) is thereby tested independently.
        q_numerator = b_plus - b0
        _require(digits, _lost(q_numerator, b_plus, b0), 'B_plus - B0')
        q = q_numerator / delta
        h, w = _h_and_w(a * delta * t)
        weight = q * h
        den = w + weight
        return (float((f0 * w + f_eq * weight) / den),
                float((b0 * w + b_minus * weight) / den),
                float((e0 * w + e_eq * weight) / den))


def reference_state(volume, oxygen, sites, kon, koff, bound0, time_s,
                    digits=REFERENCE_DIGITS):
    """Independent high-precision (free, bound, empty).  Cancellation-free
    except for B_plus - B0, which is accounted; the precision is doubled until
    the account closes (never silently returns an ill-conditioned value)."""
    while True:
        try:
            return _reference_state_at(digits, volume, oxygen, sites, kon, koff,
                                       bound0, time_s)
        except ReferenceConditioningError:
            if digits >= MAX_REFERENCE_DIGITS:
                raise
            digits = min(2 * digits, MAX_REFERENCE_DIGITS)


def reference_state_naive(volume, oxygen, sites, kon, koff, bound0, time_s,
                          digits=REFERENCE_DIGITS):
    """Wave-10 reference: Af-Riccati closed form with naive root and r0-form
    transient algebra, now with cancellation accounting.  Algebraically
    different from reference_state(); raises ReferenceConditioningError where
    the wave-10 version silently returned garbage (e.g. rho >= 1e300 sqrt(MS))."""
    with localcontext() as ctx:
        ctx.prec = digits
        v, m, s, kon_, koff_, b0, t = _decimals(volume, oxygen, sites, kon, koff,
                                                bound0, time_s)
        f0 = m - b0
        if kon_ == 0:
            bound = b0 * (-koff_ * t).exp()
            free = m - bound
            _require(digits, _lost(free, m, bound), 'M - B (kon = 0)')
        else:
            a = kon_ / v
            rho = koff_ / a
            p = s - m + rho
            disc = (p * p + 4 * rho * m).sqrt()       # = f1 - f2
            if disc == 0:                             # koff == 0 and M == S
                free = f0 / (1 + a * f0 * t)
            else:
                f1 = (-p + disc) / 2                  # positive root (Af_eq)
                _require(digits, _lost(f1, p, disc), 'Af root f1')
                f2 = (-p - disc) / 2                  # negative root
                w = (-a * disc * t).exp()
                r0_den = f0 - f2
                _require(digits, _lost(r0_den, f0, disc), 'f0 - f2')
                r0 = (f0 - f1) / r0_den
                shifted = r0 * w * f2
                numerator = f1 - shifted
                _require(digits, _lost(numerator, f1, shifted, abs(r0) * w * disc),
                         'f1 - r0 w f2')
                denominator = 1 - r0 * w
                _require(digits, _lost(denominator, Decimal(1), r0 * w), '1 - r0 w')
                free = numerator / denominator
            bound = m - free
            _require(digits, _lost(bound, m, free), 'M - Af')
        empty = s - bound
        _require(digits, _lost(empty, s, bound), 'S - B')
        return float(free), float(bound), float(empty)


def reference_equilibrium(volume, oxygen, sites, kon, koff, digits=REFERENCE_DIGITS):
    """Stable root (free, bound, empty) at `digits`; no transient involved."""
    with localcontext() as ctx:
        ctx.prec = digits
        v, m, s, kon_, koff_ = _decimals(volume, oxygen, sites, kon, koff)
        if min(m, s) == 0 or kon_ == 0:
            return float(m), 0.0, float(s)
        _, b_minus, f_eq, e_eq, _ = _reference_roots(m, s, koff_ / (kon_ / v))
        return float(f_eq), float(b_minus), float(e_eq)


def relaxation_time(volume, oxygen, sites, kon, koff):
    """1/(a*Delta) in float arithmetic -- adequate for choosing a test time."""
    a = kon / volume
    rho = koff / a
    delta = math.sqrt((oxygen - sites) ** 2 + 2 * rho * (oxygen + sites) + rho * rho)
    return 1 / (a * delta)


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
ORDINARY_CASES = (
    ((3, 4, 2, 1.2, 0.7), 0.6, 2),
    ((2, 3, 2, 4, 2), 0, 50),
    ((2, 3, 1, 1, 0), 0, 2),
    ((4, 2, 2, 2, 0), 0.5, 3),
    ((2, 3, 2, 0, 0.8), 0.75, 3.7),
    ((1, 1, 1, 1, 1e-200), 0, 1e9),                 # near-repeated-root transient
)
# (m, y, koff) with V = kon = 1 and oxygen = sites = m.  koff = m*y^2/(1-y) is
# exact in decimal, so Delta = koff + 2*m*y, B_minus = m*(1-y) and
# Af_eq = E_eq = m*y are exact rationals: an oracle with no square root at all
# (Claude, wave 11; derivation in the task answer).
RATIONAL_ROOTS = (
    (1.0, 0.2, 0.05), (1.0, 0.6, 0.9), (1.0, 0.8, 3.2), (1.0, 0.96, 23.04),
    (1.0, 0.998, 498.002), (3.0, 0.5, 1.5), (1e-300, 0.2, 5e-302),
    (1e300, 0.8, 3.2e300), (1e300, 0.998, 4.98002e302),
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

    def test_two_reference_routes_agree_where_naive_is_conditioned(self):
        """Wave 11: cross-validate the weighted-mean reference against the
        algebraically different wave-10 Af-Riccati route wherever the latter is
        well conditioned at 400 digits.  The two huge-rho EXTREMES witnesses
        must be rejected (not silently mis-evaluated) by the naive route."""
        cases = [(p, b0, t) for p, b0, times in EQUAL_SATURATED + UNEQUAL_SATURATED
                 for t in times]
        cases += list(EXTREMES) + list(ORDINARY_CASES)
        rejected = []
        compared = 0
        for params, b0, t in cases:
            with self.subTest(params=params, b0=b0, t=t):
                new = reference_state(*params, b0, t)
                try:
                    old = reference_state_naive(*params, b0, t)
                except ReferenceConditioningError:
                    rejected.append(params)
                    continue
                compared += 1
                for field, x, y in zip(('free', 'bound', 'empty'), new, old):
                    if y == 0:
                        self.assertEqual(x, 0.0, (field, x, y))
                    else:
                        self.assertTrue(math.isclose(x, y, rel_tol=1e-15, abs_tol=0),
                                        (field, x, y))
        self.assertGreaterEqual(compared, 20, rejected)
        self.assertIn((1e300, 1e-300, 1e-300, 1e-300, 1e300), rejected)
        self.assertIn((1, 1, 1, 1e-300, 1), rejected)

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

    # --- exact rational-root oracles (wave 11) -------------------------------
    def test_rational_root_witnesses_match_exact_equilibria(self):
        for m, y, koff in RATIONAL_ROOTS:
            with self.subTest(m=m, y=y, koff=koff):
                dm, dy = Decimal(str(m)), Decimal(str(y))
                self.assertEqual(Decimal(str(koff)), dm * dy * dy / (1 - dy))
                eq = Vessel(1, m, m, 1, koff).equilibrium()
                complement = float(dm * dy)
                bound = float(dm * (1 - dy))
                self.assert_rel(eq.free_umol, complement, 1e-15)
                self.assert_rel(eq.empty_umol, complement, 1e-15)
                self.assert_rel(eq.bound_umol, bound, 1e-15)
                # late-time transients reach the same exact values
                late = Vessel(1, m, m, 1, koff).at(0, 1000 * relaxation_time(1, m, m, 1, koff))
                self.assert_rel(late.free_umol, complement, 1e-13)
                self.assert_rel(late.bound_umol, bound, 1e-13)
        # (1,1,1,1,0.05): rho = 0.05, Delta = 0.45, w = exp(-0.45 t).  Saturated
        # start: Af = (1-w)/(5+4w), B = (4+5w)/(5+4w); empty start:
        # Af = (5+4w)/(25-16w) (hand derivation from the Riccati closed form).
        w = math.exp(-0.9)
        r = Vessel(1, 1, 1, 1, 0.05).at(1, 2)
        self.assert_rel(r.free_umol, (1 - w) / (5 + 4 * w), 1e-14)
        self.assert_rel(r.bound_umol, (4 + 5 * w) / (5 + 4 * w), 1e-14)
        self.assert_rel(Vessel(1, 1, 1, 1, 0.05).at(0, 2).free_umol,
                        (5 + 4 * w) / (25 - 16 * w), 1e-14)

    # --- equilibrium tiny components ---------------------------------------
    def test_equilibrium_tiny_components_are_relatively_accurate(self):
        """Wave 11: the wave-10 version compared with a transient at t = 1e9,
        which for (1,1,1,1,1e-200) is 5e90 relaxation times too early."""
        for params in ((1, 1, 2, 1, 1e-200), (1, 2, 1, 1, 1e-200),
                       (1, 1, 1, 1, 1e-200), (4, 2, 3, 1e-20, 1)):
            with self.subTest(params=params):
                eq = Vessel(*params).equilibrium()
                self.assertIsNotNone(eq)
                self.assert_state_close(eq, reference_equilibrium(*params), REL)
                t_late = 1000 * relaxation_time(*params)
                self.assert_state_close(eq, reference_state(*params, 0, t_late), REL)
                self.assert_state_close(Vessel(*params).at(0, t_late),
                                        reference_equilibrium(*params), REL)
        self.assert_rel(Vessel(1, 1, 2, 1, 1e-200).equilibrium().free_umol, 1e-200)
        self.assert_rel(Vessel(1, 2, 1, 1, 1e-200).equilibrium().empty_umol, 1e-200)
        self.assert_rel(Vessel(1, 1, 1, 1, 1e-200).equilibrium().free_umol, 1e-100)

    def test_near_repeated_root_transient_matches_reference(self):
        """(1,1,1,1,1e-200) from B0 = 0 at t = 1e9 is far from equilibrium:
        Af = 1/(1 + a f0 t) up to O(1e-91).  This is the value Red's receipt
        shows (9.99999999e-10), mistaken for an equilibrium in wave 10."""
        params = (1, 1, 1, 1, 1e-200)
        self.assertGreater(relaxation_time(*params), 1e99)
        r = Vessel(*params).at(0, 1e9)
        ref = reference_state(*params, 0, 1e9)
        self.assert_state_close(r, ref, REL)
        self.assert_rel(r.free_umol, 1 / (1 + 1e9), 1e-13)
        self.assert_rel(ref[0], 9.99999999e-10, 1e-13)

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

    def test_huge_release_ratio_limits_match_asymptotics(self):
        """Wave 11: the two EXTREMES witnesses the wave-10 naive reference got
        wrong.  With rho = koff V/kon >= 1e300 sqrt(MS) and a Delta t >= 1e300
        the exact state is the stable root: B_eq = MS/B_plus with
        B_plus in [rho, rho + M + S], complements M - B_eq, S - B_eq."""
        r = Vessel(1e300, 1e-300, 1e-300, 1e-300, 1e300).at(1e-300, 1e300)
        self.assert_state_close(r, (1e-300, 0.0, 1e-300), 1e-15)   # B_eq ~ 1e-1500
        r = Vessel(1, 1, 1, 1e-300, 1).at(0, 1e300)
        self.assert_state_close(r, (1.0, 1e-300, 1.0), 1e-15)      # B_eq = 1e-300(1-2e-300)
        self.assert_rel(Vessel(1, 1, 1, 1e-300, 1).equilibrium().bound_umol, 1e-300, 1e-15)

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

### 4.3 Mutant-blindness script (replacement)

FILE: validation/site0/revised_v1/audit_mutant_blindness.py
```python
# SPDX-License-Identifier: Apache-2.0
# Provenance: Claude (Anthropic) for Red (Claude), tasks site0-repair-audit-001/-003.
"""Informational: run the frozen SITE0 suites and the audit module against a
complement-cancelling mutant of site0._roots.  Prints counts only; writes nothing.

Wave 11: Red's wave-10 run could not import the frozen suites
(ModuleNotFoundError), so the reported (2 run, 0 failures, 2 errors) was an import
artefact, not a blindness result.  This revision (a) looks for the frozen test
modules next to the ORIGINAL kernel (../ relative to this file) or in
$SITE0_FROZEN_TESTS_DIR, (b) imports them explicitly and reports INCONCLUSIVE if
that fails, (c) prints which site0 module the frozen tests actually bind to, so
the receipt shows whether they exercised the revised kernel.
    cd validation/site0/revised_v1 && python -B audit_mutant_blindness.py
Static prediction (Claude, wave 11): frozen suites blind (0 failures under the
mutant); audit module ~17 subtest failures under the mutant, 0 without it.
"""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))                       # revised kernel + audit module first
for extra in (os.environ.get('SITE0_FROZEN_TESTS_DIR'), str(HERE.parent)):
    if extra and extra not in sys.path:
        sys.path.append(extra)                      # frozen suites and helpers last

import site0                                        # noqa: E402  (revised kernel)
from test_site0_repair_audit import _roots_cancelling  # noqa: E402

FROZEN = ('test_site0', 'test_later_regression')
AUDIT = ('test_site0_repair_audit',)


def import_modules(names):
    loaded, missing = [], []
    for name in names:
        try:
            module = importlib.import_module(name)
        except Exception as exc:       # ImportError or a failure inside the module
            missing.append((name, repr(exc)))
            continue
        bound = getattr(module, 'site0', None)
        print('%s loaded from %s; binds site0 -> %s' % (
            name, getattr(module, '__file__', '?'),
            getattr(bound, '__file__', 'no module-level site0 attribute')))
        loaded.append(module)
    return loaded, missing


def run(modules):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module in modules:
        suite.addTests(loader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0).run(suite)
    return result.testsRun, len(result.failures), len(result.errors), len(result.skipped)


if __name__ == '__main__':
    print('revised kernel under test:', site0.__file__)
    frozen_modules, frozen_missing = import_modules(FROZEN)
    audit_modules, audit_missing = import_modules(AUDIT)
    with mock.patch.object(site0, '_roots', _roots_cancelling):
        frozen = run(frozen_modules) if frozen_modules else None
        audit = run(audit_modules) if audit_modules else None
    print('audit module under mutant (run, failures, errors, skipped):', audit)
    for name, err in frozen_missing + audit_missing:
        print('could not import', name, '->', err)
    if frozen is None or frozen_missing:
        print('frozen-suite blindness: INCONCLUSIVE (frozen modules not importable; '
              'copy test_site0.py, validation_helpers.py, mutants.py and '
              'test_later_regression.py next to this script or set '
              'SITE0_FROZEN_TESTS_DIR)')
    else:
        print('frozen suites under mutant (run, failures, errors, skipped):', frozen)
        print('frozen-suite blindness:',
              'BLIND (no failure or error under mutant)' if frozen[1] + frozen[2] == 0
              else 'DETECTS the mutant')
```

Caveat on the script: if the frozen suites or their helpers load the kernel by file path rather than `import site0`, they would exercise the *original* kernel; the printed `binds site0 ->` line makes this visible in the receipt. I have not seen the frozen test sources in this bundle.

---

## 5. Predicted outcomes of Red's re-run *[static]*

- **Corrected module on revised_v1:** 17 tests, 0 failures (`test_original_kernel_shows_defect` runs if `../site0.py` is the original, as in wave 10). Witness-level predictions already confirmed by the receipt: `(1e300,1e-300,1e-300,1e-300,1e300).at(1e-300,1e300) → (1e-300, 0.0, 1e-300)`, `(1,1,1,1e-300,1).at(0,1e300) → (1.0, 1e-300, 1.0)`, `(1,1,1,1,1e-200).at(0,1e9).free ≈ 9.99999999e-10`. New predictions: rational-root witnesses equal `m·y`, `m(1−y)` to ≤ 1 ulp; `(1,1,1,1,0.05).at(1,2).free = (1−e^{−0.9})/(5+4e^{−0.9}) ≈ 0.0923…` (value to be read from the run); the naive route rejects exactly the two huge-ρ extremes plus possibly `(1,1,1,1e300,0)` and the subnormal witness (where its `S − B` or `M − B` step cancels to a legitimate `0`), and ≥ 20 cases are compared with bit-level agreement.
- **Corrected module under the `_roots` mutant:** ≈ 17 subtest failures: mutant-detection test (1), unequal-inventory (8), saturated series (1), equilibrium unequal subtests (2) + first direct assertion (1), extremes via conservation (2), asymptotic limits (2); the `(1,1,1,1,1e-200)` equilibrium subtest now **passes** under the mutant (its wave-10 failure was spurious), as do the rational-root and reference-agreement tests (kernel-independent or `M = S` with `c_f ≪ Δ`... note `c_f = ρ ≈ Δ/3…Δ` there, no cancellation).
- **Frozen suites under the mutant:** 24 run, 0 failures (blind), *provided* they import — this is the measurement wave 10 failed to obtain. If they detect the mutant, F-4 of the wave-10 audit is weaker than stated and I will revise it.

If any prediction fails, please return the numbers; a failure of `test_two_reference_routes_agree…` or `test_rational_root…` would indicate an error in *my* references, not in the kernel, and should be reported as such.

---

## 6. Left unimplemented / limitations

- Nothing executed by me; all values above are hand traces of the quoted code except where marked *[executed]* from Red's receipts.
- The corrected `reference_state` shares the weighted-mean *formula* with the kernel (unavoidable: it is the only cancellation-free arrangement). Formula independence is provided instead by `reference_state_naive` (different algebra, conditioned domain), the Taylor series, the exact rational-root family, the exact ordinary-regime closed forms and the asymptotic limits.
- `relaxation_time` uses float arithmetic; it is a test-time selector, not an oracle (overflow would need `ρ > 1e154`, which none of the equilibrium witnesses approaches).
- No test varies the decimal context traps (wave-10 F-6 caveat, hardening B); no interval or certified enclosure is provided; the frozen-suite blindness measurement remains to be obtained.
- Optional kernel hardenings A/B/C of the wave-10 audit remain optional; **no change to `revised_v1/site0.py` is requested by this task's findings.**

Credit: Coda (Codex Lily) for the kernel, repair, regression and reports; Richard (Andrei) Pemberton for direction; Lilitari (Lily) for the staged specification; Red (Claude) for execution and receipts; earlier Claude Fable 5.1 contributions as recorded in the project's attribution files. New code offered under Apache-2.0, prose CC BY 4.0, consistent with the project's license map.