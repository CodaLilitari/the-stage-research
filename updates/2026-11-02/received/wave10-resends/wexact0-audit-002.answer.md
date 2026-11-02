# WEXACT0 audit — deliverable (Red / Claude, static analysis only)

Nothing below was executed by me. All numbers are hand/closed-form derivations from the verbatim sources; the test module is written to be run by Red. Where I predict a test outcome I say so.

Summary of outcome: the WEXACT0 closed form is correct, its implementation is numerically sound on the admitted domain (no cancellation defect, no edge-case defect that affects the frozen acceptance), and every reported number I could re-derive (the three mutant errors, both refinement ratios, both transient errors) is reproduced analytically to the digits shown. **No patch is required.** The audit does find (a) documented blind spots of the frozen case set — every frozen `t/dt` is an integer, every case has `V2 = 1/2`, and the only rate-informative transient is a single `(V1,V2,K)` triple — and (b) that the frozen suite cannot run any oracle-only test without the hash-pinned production tree. The new module below adds production-independent checks and adapter-level surrogate-mutation checks.

FILE: validation/wall_exchange_exact_audit/WEXACT0_AUDIT.md
```markdown
# WEXACT0 audit (task wexact0-audit-001)

SPDX-License-Identifier: CC-BY-4.0

Red (Claude, Anthropic) for Richard (Andrei) Pemberton, auditing WEXACT0 by Coda
(Codex Lily). Static analysis only: the auditor had no execution tools, ran no
code and read nothing beyond the six verbatim sources in the request (report,
acceptance, `wall_exchange_exact.py`, `finite_l0_adapter.py`,
`test_wall_exchange_exact.py`, `wall_exchange_cases.json`). The FINITE-L0
`reference.py` was NOT available; statements about it are inferred from the
adapter and the report's numbers and are labelled as such. This is numerical
analysis of a reduced linear model, not physiology, not a safety claim.

## 1. Re-derivation

Model (positive V1, V2; K >= 0):

    A1' = -K (A1/V1 - A2/V2),   A2' = -A1'.

(a) Conservation: (A1+A2)' = 0, so T = A1 + A2 = A10 + A20 for all t.
(b) Concentration difference d = A1/V1 - A2/V2:
    d' = A1'/V1 - A2'/V2 = -K d /V1 - K d /V2 = -lambda d,
    lambda = K (1/V1 + 1/V2) = K (V1+V2)/(V1 V2).  Hence d(t) = d(0) e^{-lambda t}.
(c) Equilibrium: d = 0 and A1 + A2 = T give Ceq = T/(V1+V2),
    E1 = T V1/(V1+V2), E2 = T V2/(V1+V2).
(d) Closed form: from A2 = T - A1, d = A1 (V1+V2)/(V1 V2) - T/V2, so
    A1 = E1 + (V1 V2/(V1+V2)) d.  With B := A10 - E1 = (V1 V2/(V1+V2)) d(0):
        A1(t) = E1 + B e^{-lambda t},   A2(t) = E2 - B e^{-lambda t}.
    Check: A1(0) = A10, A2(0) = T - A10 = A20; A1 + A2 = E1 + E2 = T.
    Uniqueness (linear constant-coefficient ODE) makes this THE solution.
(e) Limits.
    - Equal volumes V1 = V2 = V: E1 = E2 = T/2, B = (A10 - A20)/2, lambda = 2K/V.
    - Unequal volumes: the smaller compartment holds the smaller equilibrium
      amount; the same lambda is symmetric in (V1,V2).  Relabelling
      (V1,A10) <-> (V2,A20) swaps (E1,B) <-> (E2,-B) and leaves lambda fixed.
    - K = 0: lambda = 0, A1(t) = E1 + B = A10 for every t.
    - t = 0: A1 = A10.
    - t -> infinity: A1 -> E1, A2 -> E2 (volume-weighted equilibrium).
    - Small t: A1(t) = A10 - K d(0) t + O(t^2); initial slopes
      A1'(0) = -K(A10/V1 - A20/V2) = -lambda B, A2'(0) = +K(A10/V1 - A20/V2).
    - Monotone: A1(t) lies between A10 and E1 and |A1(t) - E1| decreases.
(f) Frozen fixture V1=1, V2=1/4, K=3/20, A10=2, A20=0: T=2, V1+V2=5/4,
    E1 = 2/(5/4) = 8/5, E2 = (1/2)/(5/4) = 2/5, B = 2 - 8/5 = 2/5,
    lambda = (3/20)(1 + 4) = 3/4.  Matches the acceptance and test 1.

Everything in `derive()` implements (c),(d) with Fractions; correct.

## 2. Closed-form reproduction of the reported numbers

forward_unequal: V1=2, V2=1/2, K=1/5, A10=3, A20=1/4, t=4.
T=13/4, E1=13/5=2.6, E2=13/20=0.65, B=2/5, lambda=1/2, lambda t=2.
A1(4) = 2.6 + 0.4 e^{-2} = 2.654134113..., A2(4) = 0.595865886...;
slopes (-1/5, +1/5).  reverse_unequal: T=5/2, E1=2, B=-3/2.

- wrong_volume mutant: A1' = -(K/V1)(A1 - A2) => E' = T/2 = 1.625,
  lambda' = 2K/V1 = 0.2; A1'(4) = 1.625 + 1.375 e^{-0.8} = 2.2428273257.
  |A1' - A1| = 0.4113067876 (exact ODE).  The report's 0.411306774 differs by
  1.4e-8, which is exactly the second-order step error of the mutant run
  (1.375 e^{-0.8} N z^3/6, N=2000, z=0.2*0.002: 1.32e-8).  Consistent.
- unbooked_clamp: A1 frozen at 3; A2' = K(A1/V1 - A2/V2) => A2 -> A10 V2/V1
  = 0.75, A2(4) = 0.75 - 0.5 e^{-1.6} = 0.6490517410; gain 0.3990517410
  (report 0.399051724; difference 1.7e-8 = step error).  Transient error
  = |3 - 2.654134113| = 0.345865887: report 0.345865887 exactly.
- sign_reversal: A2(t) = 0.65 - 0.4 e^{t/2} hits zero at t = 2 ln 1.625 =
  0.971 s < 4 s, so the negative-state guard must fire.  Consistent.
- Step error.  Any explicit two-stage second-order RK scheme has stability
  polynomial g(z) = 1 - z + z^2/2 with z = lambda*dt; ln g = -z + z^3/6 +
  z^4/8 + O(z^5), so after N steps the amplitude error is
  |B| e^{-lambda t} (N z^3/6 + N z^4/8).  forward_unequal (N=2000, z=0.001):
  0.4 * 0.1353353 * 3.3358e-7 = 1.8058e-8 (report 1.80582593e-08);
  reverse_unequal scales by |B|=1.5: 6.7718e-8 (report 6.77184284e-08).
  Refinement t=2, dt=0.4/0.2/0.1 (z=0.2/0.1/0.05, N=5/10/20):
  errors 0.4|g^N - e^{-1}| = 1.1442e-3, 2.6468e-4, 6.36e-5, ratios 4.323 and
  4.16 (report 4.32382954, 4.15593405).  Consistent.  Inference (labelled):
  FINITE-L0 steps the reduced operator with an explicit 2-stage RK2.

## 3. Implementation review: `wall_exchange_exact.py`

Validation `rational()`: bool rejected; `Fraction(str(value))` makes 'nan',
'inf', 'abc', None, tuples -> ValueError and '1/0' -> ZeroDivisionError ->
ValueError; negatives and zero volumes rejected; `amounts()` rejects negative
time.  All acceptance item 2 requirements hold.  Note (not a defect): floats
are parsed through `str()`, so `rational(0.1) == 1/10` (decimal
reinterpretation), while the adapter feeds the production `float(case)`.  The
difference (~1e-17 relative) is irrelevant at 1e-6 umol but worth knowing.

Exponential path: x = lambda*t is rounded once to 50 decimal digits
(relative 1e-50, moving e^{-x} by <= x e^{-x} 1e-50 <= 0.4e-50 absolute);
`Decimal.exp()` is correctly rounded; one product and one sum each add
<= 0.5e-50 relative; `float(Decimal)` goes through `str` and is correctly
rounded.  Total error bound for A1:
    |err| <= ~2.5e-50 (|E1| + |B|) + 0.5 ulp(A1).
Cancellation: A1 = E1 + B e^{-x} with B = -E1 when A10 = 0 (the long_time
case) gives A1 = E1 (1 - e^{-x}); the absolute bound above is unchanged but
the RELATIVE accuracy of the increment degrades to ~1e-50/x.  Exact
counterexample: V1=V2=1, A10=0, A20=1, K=1, t=1e-40 (x=2e-40): the true
increment is 1e-40 - 1e-80 and the oracle guarantees only ~1e-50 absolute,
i.e. up to ~1e-10 relative.  For every frozen case x >= 7e-4... in fact the
smallest nonzero frozen x is 2, so this is far outside the admitted use and
every frozen tolerance is absolute; NOT a defect.  Optional hardening
(not applied, would change the frozen hash): compute the increment as
B*(e^{-x}-1) via a Decimal series when x < 1e-20, or raise the working
precision to 50 + ceil(-log10 x).

Shortcut branch `time == 0 or rate == 0` returns exact rationals -> correct
(acceptance 5).  Long time: e^{-x} underflows gracefully in Decimal
(Underflow is not trapped by default); result is E1, E2.

Out-of-domain edge (documented, not patched): astronomically large inputs
behave inconsistently, e.g. A10 = 10^400 with K = 0 raises OverflowError from
`float(Fraction)` while K > 0 returns inf from `float(Decimal)`.  Irrelevant
to the admitted scale; a magnitude check in `rational()` would be the fix.

## 4. Adapter review (static; `reference.py` not seen)

Column sums are formed from `Fraction.from_float(rate)`, so "exact column
balance" means the represented floats sum to zero, as the report says.
`wrong_volume` scales both entries of column w by V2/V1, giving K/V1 in both
with opposite signs: balance preserved, outgoing denominator wrong, matching
acceptance item 7.  `sign_reversal` and `unbooked_clamp` implement items 8 and
9 as described.  `balance_error = fsum(final) - fsum(initial)` is the right
quantity.  All consistent with the closed-form predictions of section 2.

## 5. Can the twelve frozen tests distinguish plausible mutations?

Numbering T1..T12 follows the order in `test_wall_exchange_exact.py`.
"Visible" means the amount comparison exceeds amount_error_umol = 1e-6.

Production-side mutations (operator or solver wrong):

| Mutation | Caught by | Frozen cases where visible |
|---|---|---|
| K doubled | T4, T5, T8 | forward, reverse (0.4(e^-2 - e^-4)=0.0468; slope 0.2->0.4) |
| V1,V2 swapped | T4, T5, T6, T7, T8 | forward (2.654 vs 0.968), reverse (becomes stationary at 0.5 since 0.5/0.5 = 2/2), equal_concentrations (no longer stationary), long_time (E1 2/7 vs 12/7) |
| time x2 or x1/2 | T4, T8 | forward, reverse (0.0468 / 0.093); slopes unchanged |
| always one step short | T4 | forward 5.4e-5, reverse 2.0e-4 (both > 1e-6, forward < 1e-4) |
| silent floor(t/dt) landing | NONE | none: every frozen t/dt is an integer (2000, 2000, 60, 200, 4000, 0; 5, 10, 20) |
| 1/V2 confused with 4 V2 or the constant 2 | NONE | none: V2 = 1/2 in all six cases (also 1/V1 = V1/4 = 1/2 in the transient cases) |
| per-cell scaling of K with channel_cells | NONE (by design) | none: only channel_cells = 1 is admitted |

Exact counterexamples for the two blind spots:
- Landing: forward_unequal with dt = 0.003.  floor(4/0.003) = 1333 steps of
  0.003 s stop at 3.999 s; A1(3.999) - A1(4) = 0.4 e^{-2}(e^{0.0005} - 1)
  = 2.707e-5 umol > 1e-6, invisible to all frozen cases.
- V2 coincidence: a production evaluating the wall concentration as 4*V2*A2
  (or 2*A2) reproduces every frozen case; at V2 = 1 it would have
  lambda = K(1/V1 + 4) instead of K(1/V1 + 1).

Oracle-side mutations (wall_exchange_exact.py wrong):

| Mutation | Caught by |
|---|---|
| rate doubled | T1 (3/2 != 3/4), T4, T8 |
| E1/E2 swapped | T1 (2/5 != 8/5), T4, T8; T2 still passes because b1 = a10 - eq1 absorbs it |
| exp argument time-scaled in `amounts()` | T4, T8 ONLY |
| outputs of `amounts()` swapped | T4, T8 ONLY |

So the three named mutations are all distinguished, but the time dependence
of `amounts()` is validated only against the production run.  Structural
consequence: `test_wall_exchange_exact.py` imports `finite_l0_adapter` at
module level, which raises RuntimeError on a missing or re-hashed
`reference.py`; a production hash mismatch makes all twelve tests
unrunnable, including the pure-oracle ones (T1, T2, T3).

Sensitivity floors (forward_unequal): a relative conductance error delta
changes A1(4) by 0.4 e^{-2}(1 - e^{-2 delta}) ~ 0.1083 delta, so T4 sees
delta > 9.2e-6 while T5 (1e-14 on a 0.2 slope) sees delta > 5e-14.  T4 cannot
separate "K doubled" from "time doubled" (identical amounts for all t); T5 can.
long_time sees no rate mutation at all: K doubled changes A1(80) by
(12/7)(e^{-56} - e^{-112}) ~ 8e-25; time halved by (12/7)e^{-28} ~ 1.19e-12,
which is below the 2e-12 equilibrium tolerance by only 40%.

## 6. Findings

F1 (no defect). Derivation, coefficients, fixture, and every reproducible
   number in the report are correct and mutually consistent (sections 1-2).
F2 (no defect; limitation). Increment relative accuracy degrades for
   x = lambda t < ~1e-34 when A10 = 0 or A20 = 0; absolute error stays ~1e-50.
F3 (test weakness). T9 asserts only that the wrong_volume mutant's slopes
   differ from the production's; the independent slope criterion would show
   -K(A10 - A20)/V1 = -0.275 vs -0.2 (0.075 > 1e-4).  Added quantitatively.
F4 (blind spot). No non-integer t/dt case; a silent floor-landing solver
   passes.  Counterexample above.  Added as an adapter-level test.
F5 (blind spot). V2 = 1/2 everywhere, V1 > V2 everywhere, and only one
   rate-informative (V1,V2,K) triple = (2, 1/2, 1/5).  Added mirror
   (V1 < V2) and V2 = 1.25 cases at the adapter level.
F6 (structure). Oracle tests are coupled to the production import.  The new
   module runs its Part A without any production code.
F7 (out of domain). Overflow behaviour inconsistency for astronomically large
   inputs (section 3).  Not patched.
F8 (scope, by design). channel_cells-dependent errors are unobservable here;
   the report already states this limit.

## 7. Patches

None required for the frozen artefacts.  The optional hardening in sections 3
and 6 is described, not applied, because applying it would invalidate the
frozen hashes and require a re-freeze.

## 8. New tests: `test_wexact0_audit.py`

Part A (always runs, oracle only): exact ODE-residual identity in Fractions;
`amounts()` against an independent rational Taylor enclosure of exp (2 ulp +
rigorous Decimal-error slack), including the frozen cases, V1 < V2, generic
rationals, x = 2e-40, x = 50 and 60; finite-difference initial slopes;
equal-volume, zero-K, zero-time, long-time limits; relabelling symmetry;
conservation and monotone approach; extended validation; a machine-checked
detection table for eight analytic mutants against the frozen cases and
tolerances; the sensitivity floor; the K-doubled/time-doubled equivalence;
embedded-vs-file case drift check.
Part B (skipped unless `finite_l0_adapter` imports): surrogate mutations via
case parameters (K doubled, volumes swapped, t x2 and x1/2) must be rejected;
non-integer t/dt landing; mirror and V2 = 1.25 cases; frozen cases land on t;
wrong_volume slope rejection; production error consistent with RK2.
Predicted result: all Part A tests pass; Part B passes on the described
production (the landing test skips if the production refuses non-integer
ratios explicitly).  These are predictions, not observations.

## 9. Attribution

Richard Pemberton: direction and funding.  Coda (Codex Lily): WEXACT0 design,
implementation, verification and report (audited here).  Lilitari (Lily):
staged task design and licensing framework.  Red (Claude, Anthropic): this
audit and the new test module.  The request mentions earlier Claude Fable 5.1
contributions; none is identified in the six sources provided, so none is
credited for specific items here.  New code Apache-2.0, prose CC-BY-4.0.
```

FILE: validation/wall_exchange_exact_audit/test_wexact0_audit.py
```python
# SPDX-License-Identifier: Apache-2.0
"""Audit tests for the WEXACT0 closed-form wall-exchange oracle (wexact0-audit-001).

Written by Red (Claude, Anthropic) as a static audit of Coda's (Codex Lily)
WEXACT0.  The author had no execution tools and did not run this module; the
coordinator executes it.  Standard library only, deterministic, no file writes.

Part A: production-independent checks of ``wall_exchange_exact`` (always run).
Part B: checks through ``finite_l0_adapter`` against the hash-pinned FINITE-L0
        reference; skipped when that import fails (no production tree).

Placement: either beside ``wall_exchange_exact.py`` or in a sibling directory of
``validation/wall_exchange_exact`` (both resolved below).
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SOURCE_DIRS = (HERE, HERE.parent / 'wall_exchange_exact')
for _candidate in _SOURCE_DIRS:
    if (_candidate / 'wall_exchange_exact.py').exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import wall_exchange_exact as exact  # noqa: E402

try:
    import finite_l0_adapter as adapter  # noqa: E402
    ADAPTER_ERROR = None
except Exception as _exc:  # RuntimeError (hash), FileNotFoundError, ImportError
    adapter = None
    ADAPTER_ERROR = repr(_exc)

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

    @unittest.skipIf(SPEC is None, 'wall_exchange_cases.json not found; embedded copy used')
    def test_frozen_case_file_matches_embedded_copy(self):
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
        """Only cases whose transient is still above 1e-6 at t carry information
        about lambda; in the frozen set that is one (V1, V2, K) triple, and every
        case has V2 = 1/2 (so 1/V2 = 2 = 4 V2 coincidences are not excluded)."""
        informative = set()
        for case in CASES.values():
            a1, a2, e1, b, lam = closed_form(case['v1'], case['v2'], case['a10'], case['a20'], case['k'], case['t'])
            if abs(b * exp_neg_mid(lam * F(case['t']))) > F(1, 10 ** 6):
                informative.add((F(case['v1']), F(case['v2']), F(case['k'])))
        self.assertEqual(informative, {(F(2), F(1, 2), F(1, 5))})
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


@unittest.skipIf(adapter is None, f'finite_l0_adapter unavailable ({ADAPTER_ERROR})')
class ProductionSurrogateMutationTests(unittest.TestCase):
    """Surrogate mutations are expressed through case parameters, which is
    mathematically identical to the production using 2K, swapped volumes or a
    scaled time, without touching the hash-pinned source."""

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
```

## Notes for Red

**How to run.** Place the two files in `validation/wall_exchange_exact_audit/` (sibling of `wall_exchange_exact/`), or drop the test file beside `wall_exchange_exact.py`; then `python -B -m unittest test_wexact0_audit -v`. In a sandbox containing only `wall_exchange_exact.py` and this module, Part A (17 tests) runs and Part B is skipped with the adapter's import error in the skip message; the JSON drift test skips if the case file is absent (the embedded copy is then used).

**Predicted results (not observed).** All Part A tests pass against the verbatim oracle. Part B should pass on the production described by the report; `test_non_integer_step_ratio_lands_on_requested_time` skips if the production explicitly refuses non-integer `t/dt`, and `test_production_error_matches_explicit_second_order_truncation` assumes an explicit two-stage RK2 (the report's four reproduced error figures support that inference, but it is an inference). If any Part A assertion fails, the most likely causes are my tolerance bookkeeping in `float_tolerance` or the exact-equality long-time test, not the oracle; please send me the actual output and I will correct.

**Patches.** None. No defect was found in `wall_exchange_exact.py` or the adapter on the admitted domain; the frozen artefacts should stay as hashed. Optional hardening (increment-form evaluation for `lambda*t < 1e-20`; magnitude check in `rational()`) is described in the audit file and deliberately not applied.

**Not implemented / remaining.** (1) Nothing was executed; all outcomes above are predictions. (2) The `missing_last_step` and floor-landing mutations are represented analytically or via `dt` substitution, not by injecting into the solver, because `reference.py` was not in the bundle and is hash-pinned. (3) No test of `channel_cells > 1` scaling — outside WEXACT0's admission by design. (4) No Claude Fable 5.1 item could be identified in the six sources provided, so none is credited specifically; if Red has that attribution, it should be added to section 9 of the audit file.

**Credits.** Richard Pemberton (direction, funding); Coda / Codex Lily (WEXACT0 derivation, implementation, verification, report — the object of this audit, found correct); Lilitari / Lily (staged task design, licensing framework); Red / Claude (this audit and test module). New code Apache-2.0, prose CC-BY-4.0, consistent with the project's split.