# WEXACT0 audit — addendum 003 (review of the first execution receipt)

SPDX-License-Identifier: CC-BY-4.0

Red (Claude, Anthropic) for Richard (Andrei) Pemberton.  Companion to
WEXACT0_AUDIT.md (wexact0-audit-001/002), which is left as delivered; this file
records what the coordinator's execution showed, corrects the one wrong
prediction in its section 8, and closes the task.  I executed nothing; the
only observations are the two receipts quoted in the request.  Model-only
numerical analysis, not physiology, not a safety claim.

## 1. What the receipts show

Summary receipt (`_receipt_test_wexact0_audit.txt`): `...F.......s.....ssssssss`,
25 tests in 0.053 s, 15 passed, 1 failed, 9 skipped.  unittest orders classes
by `dir()` (alphabetical) and methods by name, so the string maps to:

| pos.  | result | test |
|-------|--------|------|
| 1-3   | pass   | FrozenCaseDiscriminationTests: amount_criterion..., analytic_mutants..., every_frozen_step_ratio... |
| 4     | FAIL   | FrozenCaseDiscriminationTests.test_rate_information_rests_on_a_single_parameter_triple |
| 5-6   | pass   | FrozenCaseDiscriminationTests: sensitivity_floor..., wrong_volume_mutant_slope... |
| 7-11  | pass   | OracleClosedFormTests: amounts_match_independent_rational_series, closed_form_is_an_exact_solution, compartment_relabelling_symmetry, equal_volume_limit, float_outputs_conserve... |
| 12    | skip   | OracleClosedFormTests.test_frozen_case_file_matches_embedded_copy |
| 13-17 | pass   | OracleClosedFormTests: initial_slope..., input_validation..., long_time_limit..., zero_conductance..., zero_time... |
| 18-25 | skip   | ProductionSurrogateMutationTests (all 8) |

(The mapping is derived, not observed; a verbose run confirms it.)  All ten
tests that call the oracle (`exact.derive` / `amounts`) passed.

Verbose receipt (`_receipt_verbose.txt`) is not a test result: `python -m
unittest test_wexact0_audit -v` was started from a working directory that does
not contain the module (`ModuleNotFoundError: No module named
'test_wexact0_audit'`).  Working invocations: `cd
validation/wall_exchange_exact_audit && python -B -m unittest -v
test_wexact0_audit`, or from the work root `python -B -m unittest -v
validation/wall_exchange_exact_audit/test_wexact0_audit.py`, or `python -B
validation/wall_exchange_exact_audit/test_wexact0_audit.py` (the module's
`__main__` uses verbosity 2).  The verbose output is what shows skip reasons.

## 2. The failure: wrong expectation in the audit test, not a WEXACT0 defect

Receipt: `Items in the first set but not the second: (Fraction(3, 1),
Fraction(1, 2), Fraction(0, 1))` — the `zero_conductance` triple.

The test's predicate was `|B e^{-lambda t}| > 1e-6`, computed with the module's
own rational `closed_form()` (the oracle is never called in this test).  For
zero_conductance: T = 9/10, E1 = (9/10)(3)/(7/2) = 27/35, B = 7/10 - 27/35 =
-1/14, lambda = 0, so `exp_neg_mid(0)` is exactly 1 and |B| = 1/14 > 1e-6.  The
case was counted as rate-informative although with K = 0 nothing depends on
time: doubling K, scaling t or mis-normalising a volume changes nothing (the
passing mutant table, `EXPECTED_DETECTION['doubled_conductance'] =
{forward_unequal, reverse_unequal}`, already says so).  The same predicate also
counted `zero_time` (t = 0, B = 2/5), masked only because its (V1,V2,K) triple
equals forward_unequal's.

Correct criterion: the visible effect of doubling lambda,
|B| e^{-x} (1 - e^{-x}) with x = lambda t.  Values on the frozen set:
forward 0.4 e^{-2}(1 - e^{-2}) = 0.0468; reverse 0.1755; equal_concentrations
0 (B = 0); long_time (12/7) e^{-56}(1 - e^{-56}) ~ 8e-25; zero_conductance 0;
zero_time 0.  Informative cases = {forward_unequal, reverse_unequal}, one
triple (2, 1/2, 1/5); every V2 = 1/2; every V1 > V2.  Finding F5 of the audit
is therefore unchanged; only the machine check of it was wrong.  Section 8's
prediction "all Part A tests pass" was wrong for this one test.

## 3. The nine skips, from the test code

* 1 skip — `test_frozen_case_file_matches_embedded_copy`: decorated
  `skipIf(SPEC is None)`; `SPEC_PATH` searches `wall_exchange_cases.json` in
  `_SOURCE_DIRS = (HERE, HERE.parent / 'wall_exchange_exact')`, i.e.
  `validation/wall_exchange_exact_audit/` and `validation/wall_exchange_exact/`.
  Neither held the file in Red's layout.  Consequence: none for Part A results
  (the embedded verbatim copy is used); only the drift check is lost.
  Enabling file: the frozen `wall_exchange_cases.json` in either directory.
  Caveat: the embedded copy's "sha256 34d4f0d4..." claim is from audit-002 and
  is not verifiable from this bundle (the JSON is not in it); if the real file
  carries extra keys, the drift test will fail for benign reasons — send me
  the file and the output.

* 8 skips — the class decorator `@unittest.skipIf(adapter is None, ...)`
  marks each of the 8 methods skipped (hence 8 's', not 1).  `adapter` is None
  because `import finite_l0_adapter` raised inside `try/except Exception`.
  Resolution chain: a default directory is put on `sys.path` only if it
  contains `wall_exchange_exact.py`; `finite_l0_adapter.py` must sit in such a
  directory; at import the adapter computes `REFERENCE_PATH = <adapter
  dir>/../finite_inventory/revised_v1/reference.py`, reads it
  (`FileNotFoundError` if absent), compares SHA-256 with
  `5b5ba1dca3f182eb5f9e181c1bf514f9029ebfb88b4f14c726d40db6a3eebcc1`
  (`RuntimeError('Production reference no longer matches the frozen source')`
  on mismatch) and `exec_module`s the production (any import error of the
  production itself propagates; `reference.py` has never been in a bundle I
  saw, so its dependencies are unknown).  If the adapter is not found at all,
  the error is `ModuleNotFoundError("No module named 'finite_l0_adapter'")`.
  The skip message embeds the repr; it is visible only in a verbose run.
  Enabling files: `finite_l0_adapter.py` beside `wall_exchange_exact.py` in a
  searched directory (its frozen location `validation/wall_exchange_exact/` is
  the sibling default) AND `validation/finite_inventory/revised_v1/reference.py`
  byte-identical to the pinned hash.  Copying the adapter into the audit
  directory also works, because both directories are children of `validation/`
  and the reference path is relative to the adapter's own location.

* Environment variables: none is consulted by `wall_exchange_exact.py`,
  `finite_l0_adapter.py` or the audit module (no `os` import anywhere).  The
  only variable with an effect was Python's own `PYTHONPATH`, which can make
  the adapter importable from an arbitrary directory but does nothing for the
  JSON lookup.  The revised module adds two optional ones:
  `WEXACT0_SOURCE_DIR` (os.pathsep-separated directories searched for all three
  files and placed first on `sys.path`; pointing it at the frozen
  `validation/wall_exchange_exact` tree avoids copying anything) and
  `WEXACT0_STRICT` (non-empty, not '0': missing case file / adapter is a
  failure with the full diagnostic instead of a skip).

## 4. Fixes applied (test module only; frozen artefacts untouched)

1. `test_rate_information_rests_on_a_single_parameter_triple`: predicate
   replaced by |B| e^{-x}(1 - e^{-x}) > 1e-6; asserts the informative case ids
   {forward_unequal, reverse_unequal} and their equality with
   `EXPECTED_DETECTION['doubled_conductance']`, then the single triple, V2 =
   1/2 and V1 > V2 as before; docstring corrected.
2. `ADAPTER_ERROR` and the JSON skip message now list the searched directories
   and the required reference path/hash.
3. `WEXACT0_SOURCE_DIR` and `WEXACT0_STRICT` as described (the STRICT path uses
   `setUp` → `fail`, so per-test accounting is unchanged: still 25 tests).
4. Module docstring records the revision and the working run commands.

No change to `wall_exchange_exact.py`, `finite_l0_adapter.py`,
`test_wall_exchange_exact.py` or `wall_exchange_cases.json`.

## 5. Predicted results after the fix (not observed)

Same layout as Red's run: 25 tests, 16 passed, 0 failed, 9 skipped.  With the
frozen JSON present: 17 passed, 8 skipped.  With `WEXACT0_STRICT=1` in Red's
layout: 9 failures carrying the diagnostics (intended).  With the full frozen
tree and a hash-matching, stdlib-importable `reference.py`: all 25 run; Part B
predictions are those of WEXACT0_AUDIT.md section 8 (the landing test may skip
if the production refuses non-integer t/dt explicitly; the RK2 truncation test
rests on the inference that FINITE-L0 uses an explicit two-stage RK2).

## 6. Verdict on WEXACT0 as a reduced oracle

`wall_exchange_exact.py` is a correct, production-independent closed-form
oracle for the two-compartment linear exchange model on its admitted domain
(positive rational volumes, K >= 0, t >= 0): the closed form is an exact ODE
solution (Fraction identity), the float outputs agree with an independent
rational series to within 2 ulp plus a 1e-48(|E1|+|B|) slack across the frozen
cases and extreme arguments (lambda t = 2e-40 and 60), the zero-time, zero-rate
and long-time limits are exact, relabelling symmetry holds bit-for-bit, totals
are conserved and the approach to equilibrium is monotone, and input validation
rejects booleans, None, NaN/inf, negatives, zero volumes and malformed strings.
Ten direct oracle tests executed and passed; the one failure was in the audit's
own analysis of the frozen case set and never touched the oracle.  Documented,
out-of-domain limitations stand (F2 increment accuracy for lambda t < ~1e-34
with a zero initial amount; F7 overflow inconsistency for astronomically large
inputs; floats are reinterpreted through `str()`).  As a *reduced* oracle it
certifies only the one-cell, no-flow, no-binding exchange operator and the
integrator at the frozen (t, dt), with the case-set blind spots recorded in F4
and F5 (integer t/dt, V2 = 1/2, one rate-informative triple); the production
comparison (Part B) remains unexecuted in this run, so nothing new about
FINITE-L0 is established here.  Fit for purpose as a necessary check, not a
sufficient one.  No patch to the frozen artefacts is required or recommended.

## 7. Attribution

Richard Pemberton: direction and funding.  Coda (Codex Lily): WEXACT0 design,
implementation, verification and report (found correct).  Lilitari (Lily):
staged task design and licensing framework.  Red (Claude, Anthropic): the
audit-002 module — including the defective predicate corrected here — and this
addendum.  Red (coordinator): execution and receipts.  Earlier Claude Fable 5.1
contributions are mentioned in the request but none is identifiable in the
sources provided, so none is credited for a specific item.  Code Apache-2.0,
prose CC-BY-4.0.
