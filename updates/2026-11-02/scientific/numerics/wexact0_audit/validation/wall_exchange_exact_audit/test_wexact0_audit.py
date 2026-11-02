# SPDX-License-Identifier: Apache-2.0
"""Audit tests for the WEXACT0 closed-form wall-exchange oracle (wexact0-audit-001/-003).

Written by Red (Claude, Anthropic) as a static audit of Coda's (Codex Lily)
WEXACT0.  The author had no execution tools and did not run this module; the
coordinator executes it.  Standard library only, deterministic, no file writes.

Revision wexact0-audit-003, after the coordinator's first execution (25 tests:
15 passed, 1 failed, 9 skipped):
  * test_rate_information_rests_on_a_single_parameter_triple used the predicate
    |B e^{-lambda t}| > 1e-6, which counted the K = 0 case (zero_conductance)
    as rate-informative although its offset B never decays.  The predicate is
    now the visible effect of doubling lambda, |B| e^{-x} (1 - e^{-x}) with
    x = lambda t.  Test-side error; the oracle was not involved (the test calls
    only the independent rational reference below).
  * Skip messages list the searched directories and the production reference
    path and hash that finite_l0_adapter needs.
  * Optional environment variables (none were consulted before):
      WEXACT0_SOURCE_DIR  os.pathsep-separated extra directories searched for
                          wall_exchange_exact.py, finite_l0_adapter.py and
                          wall_exchange_cases.json, e.g. the frozen
                          validation/wall_exchange_exact tree left in place so
                          that the adapter's relative reference path resolves.
      WEXACT0_STRICT      anything but '' or '0': a missing case file or
                          production adapter is a failure, not a skip.

Part A: production-independent checks of ``wall_exchange_exact`` (always run).
Part B: checks through ``finite_l0_adapter`` against the hash-pinned FINITE-L0
        reference; skipped when that import fails (no production tree).

Placement: beside ``wall_exchange_exact.py``, or in a sibling directory of
``validation/wall_exchange_exact`` (both resolved below), or anywhere with
WEXACT0_SOURCE_DIR pointing at the frozen directory.  Run from the directory
containing this file (``python -B -m unittest -v test_wexact0_audit``), by path
(``python -B -m unittest -v validation/wall_exchange_exact_audit/test_wexact0_audit.py``)
or directly (``python -B validation/wall_exchange_exact_audit/test_wexact0_audit.py``).
"""
from __future__ import annotations

import json
import math
import os
import sys
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
_DEFAULT_DIRS = (HERE, HERE.parent / 'wall_exchange_exact')
_EXTRA_DIRS = tuple(Path(entry).expanduser().resolve()
                    for entry in os.environ.get('WEXACT0_SOURCE_DIR', '').split(os.pathsep) if entry)
_SOURCE_DIRS = _EXTRA_DIRS + _DEFAULT_DIRS
STRICT = os.environ.get('WEXACT0_STRICT', '') not in ('', '0')
for _candidate in _DEFAULT_DIRS:
    if (_candidate / 'wall_exchange_exact.py').exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))
for _candidate in reversed(_EXTRA_DIRS):  # explicit directories win; the first listed ends up first
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import wall_exchange_exact as exact  # noqa: E402

# Pinned inside finite_l0_adapter.py; repeated here only for the diagnostic message.
REFERENCE_SHA256 = '5b5ba1dca3f182eb5f9e181c1bf514f9029ebfb88b4f14c726d40db6a3eebcc1'
SEARCHED = [str(d) for d in _SOURCE_DIRS]

try:
    import finite_l0_adapter as adapter  # noqa: E402
    ADAPTER_ERROR = None
except Exception as _exc:  # ModuleNotFoundError, FileNotFoundError, RuntimeError (hash), production import errors
    adapter = None
    ADAPTER_ERROR = (f'{_exc!r}; finite_l0_adapter.py must be importable from one of {SEARCHED} '
                     f'(a default directory is put on sys.path only if it also holds wall_exchange_exact.py; '
                     f'WEXACT0_SOURCE_DIR entries always are), and it needs '
                     f'<its directory>/../finite_inventory/revised_v1/reference.py with sha256 {REFERENCE_SHA256}')

# Verbatim copy of the frozen case data (wall_exchange_cases.json, sha256 34d4f0d4...).
EMBEDDED_CASES = [
    {"id": "forward_unequal", "v1": "2", "v2": "0.5", "k": "0.2", "a10": "3", "a20": "0.25", "t": "4", "dt": "0.002"},
    {"id": "reverse_unequal", "v1": "2", "v2": "0.5", "k": "0.2", "a10": "0.5", "a20": "2", "t": "4", "dt": "0.002"},
    {"id": "zero_conductance", "v1": "3", "v2": "0.5", "k": "0", "a10": "0.7", "a20": "0.2", "t": "6", "dt": "0.1"},
    {"id": "equal_concentrations", "v1": "2", "v2": "0.5", "k": "0.2", "a10": "3", "a20": "0.75", "t": "8", "dt": "0.04"},
    {"id": "long_time", "v1": "3", "v2": "0.5", "k": "0.3", "a10": "0", "a20": "2", "t": "80", "dt": "0.02"},
    {"id": "zero_time", "v1": "2", "v2": "0.5", "k": "0.2", "a10": "3", "a20": "0.25", "t": "0", "dt": "0.1"},
]
EMBEDDED_TOL = {
    "amount_error_umol": 1e-6, "balance_error_umol": 2e-12, "slope_error_umol_per_s": 1e-14,
    "stationary_error_umol": 2e-12, "equilibrium_error_umol": 2e-12,
    "minimum_amount_umol": -1e-13, "mutant_error_floor_umol": 1e-4,
}

SPEC_PATH = next((d / 'wall_exchange_cases.json' for d in _SOURCE_DIRS
                  if (d / 'wall_exchange_cases.json').exists()), None)
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8')) if SPEC_PATH else None
CASES = {c['id']: c for c in (SPEC['cases'] if SPEC else EMBEDDED_CASES)}
TOL = dict(SPEC['tolerances']) if SPEC else dict(EMBEDDED_TOL)

# (v1, v2, a10, a20, k) parameter sets used by several Part A tests.
PARAMETER_SETS = [
    ('1', '1/4', '2', '0', '3/20'),           # frozen rational fixture
    ('2', '0.5', '3', '0.25', '0.2'),         # forward_unequal
    ('2', '0.5', '0.5', '2', '0.2'),          # reverse_unequal
    ('3', '0.5', '0', '2', '0.3'),            # long_time (A10 = 0: cancellation-prone form)
    ('1', '1', '1', '0', '1'),                # equal volumes
    ('0.5', '2', '0.25', '3', '0.2'),         # mirror of forward: V1 < V2
    ('7/3', '5/11', '13/9', '2/7', '3/13'),   # generic rationals
    ('2', '0.5', '3', '0.75', '0.2'),         # equal concentrations (B = 0)
    ('3', '0.5', '0.7', '0.2', '0'),          # zero conductance
]

# ----------------------------------------------------------------------------
# Independent rational reference (no Decimal, no production code)
# ----------------------------------------------------------------------------


@lru_cache(maxsize=None)
def exp_neg(x, digits=60):
    """Rational enclosure (lo, hi) of exp(-x) for Fraction x >= 0.

    Uses the positive Taylor series of exp(x) in exact Fractions.  Stops when the
    last term is below 10**-digits and n + 2 >= 2x, so the tail is bounded by
    2*term (consecutive-term ratio <= 1/2).  Enclosure width < 2*10**-digits.
    """
    x = F(x)
    if x < 0:
        raise ValueError('exp_neg expects a nonnegative argument')
    if x == 0:
        return F(1), F(1)
    threshold = F(1, 10 ** digits)
    term = F(1)
    total = F(1)
    n = 0
    while True:
        n += 1
        term = term * x / n
        total += term
        if term < threshold and F(n + 2) >= 2 * x:
            break
    upper_exp = total + 2 * term
    return 1 / upper_exp, 1 / total


def exp_neg_mid(x):
    lo, hi = exp_neg(F(x))
    return (lo + hi) / 2


def closed_form(v1, v2, a10, a20, k, t):
    """Independent re-derivation: (A1, A2, E1, B, lambda) as Fractions.

    exp(-lambda t) is replaced by the midpoint of a rational enclosure whose width
    is below 1e-59, far below double resolution for the magnitudes used here.
    """
    v1, v2, a10, a20, k, t = (F(str(q)) for q in (v1, v2, a10, a20, k, t))
    total = a10 + a20
    e1 = total * v1 / (v1 + v2)
    b = a10 - e1
    lam = k * (1 / v1 + 1 / v2)
    a1 = e1 + b * exp_neg_mid(lam * t)
    return a1, total - a1, e1, b, lam


def _two_state(e1, b, x, total):
    a1 = e1 + b * exp_neg_mid(x)
    return a1, total - a1


MUTANTS = ('doubled_conductance', 'time_doubled', 'time_halved', 'missing_last_step',
           'swapped_volumes', 'wrong_outgoing_volume', 'unbooked_clamp', 'sign_reversal')

# Mutants whose error, where visible at all, must also exceed the 1e-4 mutant floor.
GROSS_MUTANTS = tuple(m for m in MUTANTS if m != 'missing_last_step')

# Frozen cases on which each analytic mutant moves some amount by more than the
# frozen amount_error_umol (1e-6).  Derived in WEXACT0_AUDIT.md section 5.
EXPECTED_DETECTION = {
    'doubled_conductance': {'forward_unequal', 'reverse_unequal'},
    'time_doubled': {'forward_unequal', 'reverse_unequal'},
    'time_halved': {'forward_unequal', 'reverse_unequal'},
    'missing_last_step': {'forward_unequal', 'reverse_unequal'},
    'swapped_volumes': {'forward_unequal', 'reverse_unequal', 'equal_concentrations', 'long_time'},
    'wrong_outgoing_volume': {'forward_unequal', 'reverse_unequal', 'equal_concentrations', 'long_time'},
    'unbooked_clamp': {'forward_unequal', 'reverse_unequal', 'long_time'},
    'sign_reversal': {'forward_unequal', 'reverse_unequal', 'long_time'},
}


def mutant_closed_form(name, case):
    """Exact solution of the mutated reduced model for a frozen case (A1, A2)."""
    v1, v2, a10, a20, k, t, dt = (F(case[key]) for key in ('v1', 'v2', 'a10', 'a20', 'k', 't', 'dt'))
    total = a10 + a20
    e1 = total * v1 / (v1 + v2)
    lam = k * (1 / v1 + 1 / v2)
    if name == 'doubled_conductance':
        return _two_state(e1, a10 - e1, 2 * lam * t, total)
    if name == 'time_doubled':
        return _two_state(e1, a10 - e1, lam * 2 * t, total)
    if name == 'time_halved':
        return _two_state(e1, a10 - e1, lam * t / 2, total)
    if name == 'missing_last_step':
        return _two_state(e1, a10 - e1, lam * max(t - dt, F(0)), total)
    if name == 'swapped_volumes':
        e_swapped = total * v2 / (v1 + v2)
        return _two_state(e_swapped, a10 - e_swapped, lam * t, total)
    if name == 'wrong_outgoing_volume':
        return _two_state(total / 2, a10 - total / 2, 2 * k * t / v1, total)
    if name == 'unbooked_clamp':
        target = a10 * v2 / v1
        a2 = target - (target - a20) * exp_neg_mid(k * t / v2)
        return a10, a2
    if name == 'sign_reversal':
        growth = 1 / exp_neg_mid(lam * t)
        a1 = e1 + (a10 - e1) * growth
        return a1, total - a1
    raise ValueError(f'unknown analytic mutant {name!r}')


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def oracle_amounts(case, t=None):
    solution = exact.derive(case['v1'], case['v2'], case['a10'], case['a20'], case['k'])
    return solution.amounts(case['t'] if t is None else t)


def exact_slopes(case):
    flux = F(case['k']) * (F(case['a10']) / F(case['v1']) - F(case['a20']) / F(case['v2']))
    return (-float(flux), float(flux))


def max_err(actual, expected):
    return max(abs(a - b) for a, b in zip(actual, expected))


def decimal_string(fraction):
    """Exact plain decimal string for a Fraction with a 2^a 5^b denominator."""
    with localcontext() as ctx:
        ctx.prec = 60
        value = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    text = format(value, 'f')
    if F(text) != fraction:
        raise ValueError(f'{fraction} has no exact finite decimal representation')
    return text


def surrogate(case, **changes):
    new = dict(case)
    new['id'] = case['id'] + '+' + '+'.join(f'{key}={value}' for key, value in sorted(changes.items()))
    new.update(changes)
    return new


def float_tolerance(expected, actual, e1, b, ulps=2):
    """2 ulp plus the rigorous Decimal-path slack derived in the audit."""
    scale = max(abs(expected), abs(actual), 5e-324)
    slack = float((abs(e1) + abs(b)) * F(1, 10 ** 48))
    return ulps * math.ulp(scale) + slack


# ----------------------------------------------------------------------------
# Part A: oracle only
# ----------------------------------------------------------------------------


class OracleClosedFormTests(unittest.TestCase):

    def test_closed_form_is_an_exact_solution_of_the_exchange_ode(self):
        """A1 = E1 + B r, A2 = E2 - B r with r = exp(-lambda t): the ODE residual
        -lambda B r + K(A1/V1 - A2/V2) must vanish identically in r, and the
        equilibrium concentrations must coincide.  Exact Fraction equality."""
        for params in PARAMETER_SETS:
            solution = exact.derive(*params)
            v1, v2, a10, a20, k = (F(p) for p in params)
            with self.subTest(params=params):
                self.assertEqual(solution.eq1 + solution.b1, a10)
                self.assertEqual(solution.eq2 + solution.b2, a20)
                self.assertEqual(solution.eq1 / v1, solution.eq2 / v2)
                self.assertEqual(solution.rate, k * (v1 + v2) / (v1 * v2))
                for r in (F(1), F(1, 2), F(3, 7), F(1, 10 ** 9), F(0)):
                    a1 = solution.eq1 + solution.b1 * r
                    a2 = solution.eq2 + solution.b2 * r
                    gradient_flux = k * (a1 / v1 - a2 / v2)
                    self.assertEqual(-solution.rate * solution.b1 * r, -gradient_flux)
                    self.assertEqual(-solution.rate * solution.b2 * r, gradient_flux)

    def test_amounts_match_independent_rational_series(self):
        """Decimal exp path vs exact rational Taylor enclosure, incl. the frozen
        cases, V1 < V2, generic rationals, x = 2e-40, x = 50 and x = 60."""
        checks = [(c['v1'], c['v2'], c['a10'], c['a20'], c['k'], c['t']) for c in CASES.values()]
        checks += [
            ('1', '1/4', '2', '0', '3/20', '1/2'),
            ('1', '1/4', '2', '0', '3/20', '4'),
            ('1', '1/4', '2', '0', '3/20', '40/3'),
            ('1', '1', '1', '0', '1', '1/2'),
            ('1', '1', '1', '0', '1', '3'),
            ('0.5', '2', '0.25', '3', '0.2', '4'),
            ('3', '0.5', '0', '2', '0.3', '1/1000'),
            ('3', '0.5', '0', '2', '0.3', '1/100000000000000000000'),
            ('1', '1', '0', '1', '1', '1/1' + '0' * 40),
            ('2', '0.5', '3', '0.25', '0.2', '100'),
            ('2', '0.5', '3', '0.25', '0.2', '120'),
            ('7/3', '5/11', '13/9', '2/7', '3/13', '17/5'),
        ]
        for params in checks:
            with self.subTest(params=params):
                a1, a2, e1, b, lam = closed_form(*params)
                lo, hi = exp_neg(lam * F(params[5]))
                self.assertLess(hi - lo, F(1, 10 ** 55))
                got = exact.derive(*params[:5]).amounts(params[5])
                for actual, expected in zip(got, (a1, a2)):
                    ex = float(expected)
                    self.assertLessEqual(abs(actual - ex), float_tolerance(ex, actual, e1, b),
                                         msg=f'actual={actual!r} expected={ex!r}')

    def test_initial_slope_recovered_from_amounts_by_finite_difference(self):
        """(A(h) - A(0))/h at h = 1e-6 s must match -+K(A10/V1 - A20/V2); the
        truncation term |B| lambda^2 h / 2 is below 2e-7 for every set here.
        A time-scaled exponent in amounts() would fail this without production."""
        h = F(1, 10 ** 6)
        for params in PARAMETER_SETS:
            solution = exact.derive(*params)
            v1, v2, a10, a20, k = (F(p) for p in params)
            flux = float(k * (a10 / v1 - a20 / v2))
            a1h, a2h = solution.amounts(h)
            a10f, a20f = solution.amounts(0)
            with self.subTest(params=params):
                self.assertLess(abs((a1h - a10f) / float(h) + flux), 1e-6)
                self.assertLess(abs((a2h - a20f) / float(h) - flux), 1e-6)

    def test_equal_volume_limit(self):
        for v, a10, a20, k in (('1', '1', '0', '1'), ('2.5', '0.3', '0.9', '0.7'), ('1/3', '2', '2', '5')):
            solution = exact.derive(v, v, a10, a20, k)
            total = F(a10) + F(a20)
            with self.subTest(v=v, a10=a10, a20=a20, k=k):
                self.assertEqual((solution.eq1, solution.eq2), (total / 2, total / 2))
                self.assertEqual(solution.b1, (F(a10) - F(a20)) / 2)
                self.assertEqual(solution.rate, 2 * F(k) / F(v))

    def test_zero_conductance_is_stationary_for_any_time(self):
        for params in (('3', '0.5', '0.7', '0.2', '0'), ('1', '1/4', '2', '0', '0'),
                       ('7/3', '5/11', '13/9', '2/7', '0')):
            solution = exact.derive(*params)
            initial = (float(F(params[2])), float(F(params[3])))
            with self.subTest(params=params):
                self.assertEqual(solution.rate, 0)
                for t in ('0', '1', '1000000', '1e30'):
                    self.assertEqual(solution.amounts(t), initial)

    def test_zero_time_returns_initial_amounts_exactly(self):
        for case in CASES.values():
            solution = exact.derive(case['v1'], case['v2'], case['a10'], case['a20'], case['k'])
            with self.subTest(case=case['id']):
                self.assertEqual(solution.amounts('0'), (float(F(case['a10'])), float(F(case['a20']))))
                self.assertEqual(solution.amounts(0), solution.amounts('0'))

    def test_long_time_limit_is_volume_weighted_equilibrium(self):
        """At x = lambda t = 400 the transient is ~1e-174; the floats must equal
        float(E1), float(E2) exactly (small-denominator rationals cannot sit within
        1e-50 of a double rounding boundary)."""
        for params in PARAMETER_SETS:
            solution = exact.derive(*params)
            if solution.rate == 0:
                continue
            t = F(400) / solution.rate
            with self.subTest(params=params):
                self.assertEqual(solution.amounts(t), (float(solution.eq1), float(solution.eq2)))

    def test_compartment_relabelling_symmetry(self):
        """Swapping (V1,A10) with (V2,A20) swaps the outputs bit-for-bit."""
        for params in PARAMETER_SETS:
            v1, v2, a10, a20, k = params
            forward = exact.derive(v1, v2, a10, a20, k)
            mirrored = exact.derive(v2, v1, a20, a10, k)
            with self.subTest(params=params):
                self.assertEqual((forward.eq1, forward.eq2, forward.b1, forward.b2, forward.rate),
                                 (mirrored.eq2, mirrored.eq1, mirrored.b2, mirrored.b1, mirrored.rate))
                for t in ('0', '1/3', '2', '50'):
                    self.assertEqual(forward.amounts(t), tuple(reversed(mirrored.amounts(t))))

    def test_float_outputs_conserve_total_and_approach_equilibrium_monotonically(self):
        for params in PARAMETER_SETS:
            solution = exact.derive(*params)
            total = float(solution.eq1 + solution.eq2)
            lo, hi = sorted((float(solution.eq1), float(solution.eq1 + solution.b1)))
            slack = math.ulp(max(hi, 5e-324))
            previous = None
            for t in ('0', '1/4', '1/2', '1', '2', '4', '8', '16'):
                a1, a2 = solution.amounts(t)
                with self.subTest(params=params, t=t):
                    self.assertLessEqual(abs((a1 + a2) - total), 4 * math.ulp(total) + 5e-324)
                    self.assertGreaterEqual(a1, lo - slack)
                    self.assertLessEqual(a1, hi + slack)
                    distance = abs(a1 - float(solution.eq1))
                    if previous is not None:
                        self.assertLessEqual(distance, previous + 2 * slack)
                    previous = distance

    def test_input_validation_beyond_frozen_cases(self):
        bad_parameter_sets = [
            (True, '1', '1', '0', '1'), (None, '1', '1', '0', '1'), ('1/0', '1', '1', '0', '1'),
            ('abc', '1', '1', '0', '1'), (float('nan'), '1', '1', '0', '1'),
            ('1', float('inf'), '1', '0', '1'), ('1', '1', '1', '0', '-1e-300'),
            ('1', '0', '1', '0', '1'), ((1,), '1', '1', '0', '1'),
        ]
        for args in bad_parameter_sets:
            with self.subTest(args=repr(args)):
                with self.assertRaises(ValueError):
                    exact.derive(*args)
        solution = exact.derive('1', '1', '1', '0', '1')
        for t in ('-1', -1e-300, float('nan'), float('inf'), True, None, '1/0'):
            with self.subTest(time=repr(t)):
                with self.assertRaises(ValueError):
                    solution.amounts(t)
        accepted = exact.derive(F(1, 4), Decimal('0.5'), 1, 0, '1e-3')
        self.assertEqual(accepted.rate, F(6, 1000))
        # Floats are reinterpreted through str(): decimal value, not binary value.
        self.assertEqual(exact.rational(0.1, 'x'), F(1, 10))
        self.assertNotEqual(F(0.1), F(1, 10))
        self.assertEqual(exact.rational(-0.0, 'x'), 0)

    @unittest.skipIf(SPEC is None and not STRICT,
                     f'wall_exchange_cases.json not found in {SEARCHED}; embedded copy used')
    def test_frozen_case_file_matches_embedded_copy(self):
        self.assertIsNotNone(SPEC_PATH,
                             f'WEXACT0_STRICT is set and wall_exchange_cases.json was not found in {SEARCHED}')
        self.assertEqual(SPEC['cases'], EMBEDDED_CASES)
        self.assertEqual(SPEC['tolerances'], EMBEDDED_TOL)


class FrozenCaseDiscriminationTests(unittest.TestCase):
    """Mutation adequacy of the frozen case set and tolerances, computed from the
    exact mutant solutions (no production code).  Machine-checks the blind-spot
    table in WEXACT0_AUDIT.md section 5."""

    def test_analytic_mutants_are_detected_exactly_where_predicted(self):
        for name in MUTANTS:
            detected = set()
            for case_id, case in CASES.items():
                a1, a2, *_ = closed_form(case['v1'], case['v2'], case['a10'], case['a20'], case['k'], case['t'])
                m1, m2 = mutant_closed_form(name, case)
                diff = float(max(abs(m1 - a1), abs(m2 - a2)))
                with self.subTest(mutant=name, case=case_id):
                    if diff > TOL['amount_error_umol']:
                        detected.add(case_id)
                        if name in GROSS_MUTANTS:
                            self.assertGreater(diff, TOL['mutant_error_floor_umol'])
                    elif case_id in ('zero_conductance', 'zero_time'):
                        self.assertEqual(diff, 0.0)
            with self.subTest(mutant=name):
                self.assertEqual(detected, EXPECTED_DETECTION[name])
                self.assertTrue(detected, 'every mutant must be visible on at least one frozen case')

    def test_rate_information_rests_on_a_single_parameter_triple(self):
        """A frozen case carries rate information only if a multiplicative change
        of lambda moves an amount by more than the 1e-6 amount tolerance.  The
        visible effect of doubling lambda is |B| e^{-x} (1 - e^{-x}), x = lambda t:
        it vanishes for K = 0 (zero_conductance), t = 0 (zero_time) and B = 0
        (equal_concentrations), is ~8e-25 for long_time, and 0.047 / 0.176 for
        forward_unequal / reverse_unequal.  So the informative cases are those two,
        one (V1, V2, K) triple, and every frozen case has V2 = 1/2 (1/V2 = 2 = 4 V2
        coincidences are not excluded).

        wexact0-audit-003: the earlier predicate |B e^{-x}| > 1e-6 wrongly counted
        the K = 0 case, whose non-decaying offset is not rate information (and
        silently the t = 0 case, masked by its triple coinciding with forward's).
        The oracle is not called here; this was a test-side error."""
        informative_cases = set()
        informative_triples = set()
        for case in CASES.values():
            a1, a2, e1, b, lam = closed_form(case['v1'], case['v2'], case['a10'], case['a20'], case['k'], case['t'])
            attenuation = exp_neg_mid(lam * F(case['t']))
            effect_of_doubled_rate = abs(b) * attenuation * (1 - attenuation)
            if effect_of_doubled_rate > F(1, 10 ** 6):
                informative_cases.add(case['id'])
                informative_triples.add((F(case['v1']), F(case['v2']), F(case['k'])))
        self.assertEqual(informative_cases, {'forward_unequal', 'reverse_unequal'})
        self.assertEqual(informative_cases, EXPECTED_DETECTION['doubled_conductance'])
        self.assertEqual(informative_triples, {(F(2), F(1, 2), F(1, 5))})
        self.assertTrue(all(F(case['v2']) == F(1, 2) for case in CASES.values()))
        self.assertTrue(all(F(case['v1']) > F(case['v2']) for case in CASES.values()))

    def test_every_frozen_step_ratio_is_an_integer(self):
        """Documents the landing blind spot: a solver that floors t/dt and stops
        at floor(t/dt)*dt is indistinguishable on the frozen cases."""
        for case in CASES.values():
            ratio = F(case['t']) / F(case['dt'])
            with self.subTest(case=case['id']):
                self.assertEqual(ratio.denominator, 1)
        for dt in ('0.4', '0.2', '0.1'):
            self.assertEqual((F(2) / F(dt)).denominator, 1)
        # Exact counterexample size: forward_unequal, dt = 0.003, stop at 3.999 s.
        c = CASES['forward_unequal']
        a1_full, *_ = closed_form(c['v1'], c['v2'], c['a10'], c['a20'], c['k'], c['t'])
        a1_short, *_ = closed_form(c['v1'], c['v2'], c['a10'], c['a20'], c['k'], F(3999, 1000))
        self.assertGreater(float(abs(a1_short - a1_full)), TOL['amount_error_umol'])

    def test_sensitivity_floor_of_amount_and_slope_criteria(self):
        """forward_unequal: a relative conductance error of 1e-5 is visible to the
        1e-6 amount criterion, 1e-6 is not; both are visible to the slope criterion."""
        c = CASES['forward_unequal']
        a1, a2, *_ = closed_form(c['v1'], c['v2'], c['a10'], c['a20'], c['k'], c['t'])
        gradient = F(c['a10']) / F(c['v1']) - F(c['a20']) / F(c['v2'])
        for relative, visible in ((F(1, 10 ** 5), True), (F(1, 10 ** 6), False)):
            k_perturbed = F(c['k']) * (1 + relative)
            m1, m2, *_ = closed_form(c['v1'], c['v2'], c['a10'], c['a20'], k_perturbed, c['t'])
            diff = float(max(abs(m1 - a1), abs(m2 - a2)))
            with self.subTest(relative_conductance_error=str(relative)):
                self.assertEqual(diff > TOL['amount_error_umol'], visible)
                slope_shift = float(relative * F(c['k']) * gradient)
                self.assertGreater(abs(slope_shift), TOL['slope_error_umol_per_s'])

    def test_amount_criterion_cannot_separate_doubled_conductance_from_doubled_time(self):
        for case in CASES.values():
            with self.subTest(case=case['id']):
                self.assertEqual(mutant_closed_form('doubled_conductance', case),
                                 mutant_closed_form('time_doubled', case))
        c = CASES['forward_unequal']
        slope = exact_slopes(c)[1]
        self.assertGreater(abs(2 * slope - slope), TOL['slope_error_umol_per_s'])

    def test_wrong_volume_mutant_slope_is_rejected_by_independent_slope(self):
        """Closed-form version of finding F3: the mutant initial slope is
        -K (A10 - A20)/V1 = -0.275 vs -0.2 for forward_unequal."""
        c = CASES['forward_unequal']
        v1, a10, a20, k = (F(c[key]) for key in ('v1', 'a10', 'a20', 'k'))
        mutant_slope = -float(k * (a10 - a20) / v1)
        self.assertEqual(mutant_slope, -0.275)
        self.assertGreater(abs(mutant_slope - exact_slopes(c)[0]), TOL['mutant_error_floor_umol'])


# ----------------------------------------------------------------------------
# Part B: through the adapter against the hash-pinned production reference
# ----------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _frozen_result(name):
    return adapter.run_case(CASES[name])


@unittest.skipIf(adapter is None and not STRICT, f'finite_l0_adapter unavailable ({ADAPTER_ERROR})')
class ProductionSurrogateMutationTests(unittest.TestCase):
    """Surrogate mutations are expressed through case parameters, which is
    mathematically identical to the production using 2K, swapped volumes or a
    scaled time, without touching the hash-pinned source."""

    def setUp(self):
        if adapter is None:
            self.fail(f'WEXACT0_STRICT is set and finite_l0_adapter is unavailable ({ADAPTER_ERROR})')

    def _assert_rejected(self, record, case, check_slopes):
        self.assertIsNone(record['exception'], record['exception'])
        self.assertGreater(max_err(record['amounts'], oracle_amounts(case)), TOL['mutant_error_floor_umol'])
        if check_slopes:
            self.assertGreater(max_err(record['initial_slopes'], exact_slopes(case)), TOL['mutant_error_floor_umol'])

    def test_surrogate_doubled_conductance_is_rejected(self):
        for name in ('forward_unequal', 'reverse_unequal'):
            c = CASES[name]
            with self.subTest(case=name):
                record = adapter.run_case(surrogate(c, k=decimal_string(2 * F(c['k']))))
                self._assert_rejected(record, c, check_slopes=True)

    def test_surrogate_swapped_volumes_is_rejected(self):
        for name in ('forward_unequal', 'reverse_unequal', 'long_time', 'equal_concentrations'):
            c = CASES[name]
            with self.subTest(case=name):
                record = adapter.run_case(surrogate(c, v1=c['v2'], v2=c['v1']))
                self._assert_rejected(record, c, check_slopes=name != 'long_time')

    def test_surrogate_time_scaling_is_rejected_by_amounts_only(self):
        for name in ('forward_unequal', 'reverse_unequal'):
            c = CASES[name]
            for factor in (F(2), F(1, 2)):
                with self.subTest(case=name, factor=str(factor)):
                    record = adapter.run_case(surrogate(c, t=decimal_string(F(c['t']) * factor)))
                    self._assert_rejected(record, c, check_slopes=False)
                    self.assertLess(max_err(record['initial_slopes'], exact_slopes(c)),
                                    TOL['slope_error_umol_per_s'])

    def test_non_integer_step_ratio_lands_on_requested_time(self):
        """Finding F4.  A silent floor(t/dt) landing would err by ~2.7e-5 umol at
        dt = 0.003.  An explicit refusal (recorded exception) is acceptable and is
        reported as a skip; a silent wrong landing fails."""
        c = CASES['forward_unequal']
        for dt in ('0.003', '0.0011'):
            with self.subTest(dt=dt):
                record = adapter.run_case(surrogate(c, dt=dt))
                if record['exception'] is not None:
                    self.skipTest(f'production refuses non-integer t/dt explicitly: {record["exception"]}')
                self.assertLess(max_err(record['amounts'], oracle_amounts(c)), TOL['amount_error_umol'],
                                msg=f"steps={record['steps']} actual_dt={record['actual_dt']}")

    def test_frozen_cases_land_on_requested_time(self):
        for name, c in CASES.items():
            record = _frozen_result(name)
            if record['steps'] is None or record['actual_dt'] is None:
                continue
            with self.subTest(case=name):
                self.assertLessEqual(abs(record['steps'] * record['actual_dt'] - float(F(c['t']))), 1e-9)

    def test_mirror_and_non_special_volume_cases_match_oracle(self):
        """Finding F5: V1 < V2 and V2 != 1/2 are absent from the frozen set."""
        extra_cases = [
            {"id": "mirror_forward", "v1": "0.5", "v2": "2", "k": "0.2", "a10": "0.25", "a20": "3", "t": "4", "dt": "0.002"},
            {"id": "v2_not_half", "v1": "2", "v2": "1.25", "k": "0.2", "a10": "3", "a20": "0.25", "t": "4", "dt": "0.002"},
            {"id": "generic_volumes", "v1": "1.5", "v2": "0.75", "k": "0.35", "a10": "1.2", "a20": "0.9", "t": "3", "dt": "0.001"},
        ]
        for c in extra_cases:
            with self.subTest(case=c['id']):
                record = adapter.run_case(c)
                self.assertIsNone(record['exception'], record['exception'])
                self.assertLess(max_err(record['amounts'], oracle_amounts(c)), TOL['amount_error_umol'])
                self.assertLess(max_err(record['initial_slopes'], exact_slopes(c)), TOL['slope_error_umol_per_s'])
                self.assertLess(abs(record['balance_error']), TOL['balance_error_umol'])
                self.assertGreaterEqual(record['minimum_seen'], TOL['minimum_amount_umol'])
                self.assertEqual(record['other_amounts'], [0.0] * len(record['other_amounts']))
                self.assertTrue(record['exact_column_balance'])

    def test_wrong_volume_mutant_slope_rejected_quantitatively(self):
        """Strengthens frozen T9, which only asserts the slopes differ."""
        c = CASES['forward_unequal']
        record = adapter.run_case(c, mutation='wrong_volume')
        v1, a10, a20, k = (F(c[key]) for key in ('v1', 'a10', 'a20', 'k'))
        predicted = float(k * (a10 - a20) / v1)
        self.assertLess(abs(record['initial_slopes'][0] + predicted), 1e-12)
        self.assertLess(abs(record['initial_slopes'][1] - predicted), 1e-12)
        self.assertGreater(max_err(record['initial_slopes'], exact_slopes(c)), TOL['mutant_error_floor_umol'])

    def test_production_error_matches_explicit_second_order_truncation(self):
        """The report's 1.80582593e-08 equals |B| e^{-lambda t} (N z^3/6 + N z^4/8)
        for an explicit two-stage RK2 (stability polynomial 1 - z + z^2/2).
        This checks the production's forward_unequal error against that prediction."""
        c = CASES['forward_unequal']
        record = _frozen_result('forward_unequal')
        self.assertIsNone(record['exception'], record['exception'])
        if record['steps'] is None or not record['steps']:
            self.skipTest('production did not report a step count')
        a1, a2, e1, b, lam = closed_form(c['v1'], c['v2'], c['a10'], c['a20'], c['k'], c['t'])
        t = float(F(c['t']))
        steps = int(record['steps'])
        dt = float(record['actual_dt']) if record['actual_dt'] is not None else t / steps
        z = float(lam) * dt
        g = 1.0 - z + z * z / 2.0
        predicted = abs(float(b)) * abs(g ** steps - math.exp(-float(lam) * t))
        actual = abs(record['amounts'][0] - float(a1))
        self.assertGreater(predicted, 1e-9)
        self.assertLess(abs(actual / predicted - 1.0), 0.25,
                        msg=f'actual={actual!r} predicted={predicted!r} steps={steps} dt={dt!r}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
