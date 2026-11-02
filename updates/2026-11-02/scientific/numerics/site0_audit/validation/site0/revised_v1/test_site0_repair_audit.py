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
