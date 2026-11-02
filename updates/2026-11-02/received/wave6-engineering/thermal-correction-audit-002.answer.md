# Second-pass audit — candidate 2 repair of `fixed/thermal_contract.py` (F1–F3)

**Method statement.** Everything below is static reasoning over the verbatim bundle (report, recovered audit, diff, repaired source, test file, review.py, sample plan, expected plan, three receipts). I executed nothing. Where I cite a receipt, that is Root's execution, not mine, and I say so. I did not read `thermal_reference.py`, `reference_results.json`, `fixed_results.json`, the original `thermal_contract.py`, or the first (failing) independent receipt; claims about them remain Root's.

---

## 1. Bounded admission verdict

**Admit as a bounded candidate repair.** The diff resolves F1, F2(a–c) and F3 exactly as the recovered audit specified (F3 via the enforcement option), introduces no change to any numeric, ordering, or serialization path, and therefore cannot alter any previously successful run's output — the 108-record identity Root reports is the expected static consequence, not a surprise. No material regression found. Admission is conditional on the bookkeeping items in §7 (one missing end-to-end regression; three provenance gaps), none of which blocks the code itself. Status remains as the report states: candidate pending targeted external audit; nothing empirical or physiological is claimed or implied.

---

## 2. Resolution check, finding by finding (static)

### F1 — Gauss cross-check crash on a solvable admitted input
**Diff:** wraps only `solve_2x2_gauss` in `try/except ZeroDivisionError → T_H_g = T_S_g = None`.

**Trace of the audit's minimal input** `solve_two_node(5.0, 0.0, 1e-17, 5.0, 0.1, 25, 25)`: det = 5e-17 > 0 (products of non-negatives, no cancellation) → closed form proceeds; a = fl(5+1e-17) = 5.0 because 1e-17 < ½ulp(5) = 2⁻⁵¹ ≈ 4.4e-16; f = −1 exactly; d₂ = 5 − 5 = 0.0 → the explicit raise → now caught → `None`. `semantic_checks` already maps `T_H_gauss is None` → `gauss_vs_closed_form_inverse = None`; `summarize` already treats `None` as non-failing; `_sanitize` passes `None` → JSON `null`. Downstream is consistent.

**Soundness of the fallback:** `solve_2x2_gauss` raises only at its two explicit sites. The first (`a == 0`) requires G_HS = G_rej = 0, which forces det = 0 and is unreachable after `det > 0`. Python float `* / + −` do not raise on overflow, so no other exception type can escape from Gauss. Because det is a sum of products of non-negative finite floats, `fl(det) > 0 ⇒ exact det > 0`; the fallback can therefore never mask a true singularity. Resolved.

**Residual (outside the exact correction, same mechanism):** the handler covers only the *exact* zero. Just above the threshold Gauss returns a wrong answer and the check reports `False` on a correct closed form (§6, CE-1).

### F2(a) — `1/(h·A)` ZeroDivisionError for admitted h = 5e-324
**Diff:** adds `ArithmeticError` to `main`'s catch. Trace: `5e-324 * 0.01` rounds to 0.0 (below 2⁻¹⁰⁷⁵) → `1.0/0.0` in `assemble_resistances` → ZeroDivisionError ⊂ ArithmeticError → `error: float division by zero`, return 1. All of `run_study`'s computation precedes `open(out_path, "x")`, so no file is created. Resolved at the CLI boundary as the audit's surgical fix prescribed. Two notes: the message is generic rather than configuration-flavoured; and a library caller of `run_study` still receives `ZeroDivisionError`, not `ConfigError` (§6, CE-3 shows the adjacent silent variant).

### F2(b) — >308-digit integer literal → `math.isfinite` OverflowError
**Diff:** `_finite` catches `OverflowError` → `False`. The boundary is exactly CPython's int→float conversion boundary (|n| ≥ 2¹⁰²⁴, including 2¹⁰²⁴−1 which rounds up), so every later `float()` on a validated value is safe. I checked every `float()` / arithmetic use of a config number in `resolve_parameters`, `build_shared_conditions`, `run_case`: each is preceded by a `_finite` check. Resolved.

### F2(c) — TypeError before `_require`
**Diff:** dict checks for the eight top sections; dict checks for `materials.{silicone_ref,polyimide_film_ref}` and `sources.{body,sensor}`; stacks must be dicts with `str` `stack_id`. The nested-section checks go slightly beyond the audit's snippet and are justified (`mat["k_W_mK"]` on a list would still have raised TypeError). I walked every subscript in `_validate_config`: after these checks, every access is either on a verified dict (KeyError → `ConfigError` via the existing wrapper), through `_finite` (type-safe for any JSON value), or through `_require_range` (checks `isinstance(list)` before indexing). `parse_R_rej` compares `value == "blocked"` then `_finite(value)`, both type-safe. I found no remaining TypeError path in validation. Resolved.

### F3 — unenforced "film thickness held equal" claim
**Diff:** `len({s["t_film_m"] for s in stacks}) == 1`, placed after the thickness `_finite` checks so every element is a hashable number. `0 == 0.0` and `-0.0 == 0.0` hash-equal, so mixed int/float equal values pass. Sample (all `0.00005`) passes. Resolved by enforcement; the document's hardcoded invariant is now guaranteed for any document the program can write.

---

## 3. Regression analysis (static)

| Change | Effect on previously successful runs | Effect on accepted domain |
|---|---|---|
| `_finite` OverflowError | none (floats never raise) | rejects ints ≥ 2¹⁰²⁴ (previously a traceback) |
| section / nested / stack type checks | none for well-formed configs; only changes *which* error is reported first when a section is missing (sections are now touched before geometry details) | rejects malformed types (previously traceback) |
| film equality | none for the sample | **intentional narrowing**: unequal-film configs that previously ran now `ConfigError` |
| Gauss try/except | none — handler fires only where the old code crashed | adds `null` as a possible `gauss_vs_closed_form_inverse` value for `solved` cases |
| `ArithmeticError` in `main` | none | tracebacks become `error:` lines |

Hence: for every config that succeeded before and still validates, the output document is byte-identical (same Python/platform). The report's `fixed_results.json` hash is therefore *expected*; I did not verify it. Independent review `test_36_by_3…` passing on that file (receipt `independent2`) corroborates its content against the exact-rational reference, not its identity with the previous file.

Non-material design notes (not defects): (i) `None` now conflates "not applicable" (divider check when a path is absent) with "unavailable because elimination lost the exit"; (ii) `SCHEMA_VERSION` stays `T0-HYP-1.0` while acceptance tightened — a config valid under 1.0 (unequal films) is now rejected by a program announcing 1.0; a note in the validator message or schema notes suffices.

---

## 4. Tests and receipts — what they do and do not establish

**New regression file (hash 22528f69…), read line by line.** Eight methods; `assert_rejected_config` correctly converts *wrong* exception types into failures (so "zero errors" is expected, not evidence of anything extra). Each assertion matches my static trace: F1 unit case (ratios to 5.1e17 within 1e-12 — true answer 5.1e17+25, relative deviation 5e-17; float closed form accurate to ~1e-16); eight top sections; four nested sections; three bad stack shapes; `10**399` (400 digits, below the 4300-digit `int()` limit so it reaches `_finite` as intended); h = 5e-324 through `main` with stderr prefix and no output file (the `h_assumed_range` edit is harmless and redundant — no nominal-in-range rule exists for h); unequal film; and a well-conditioned control (`solve_two_node(5,.5,.25,…)`: det = 3.875, d₂ = det/a = 0.738, Gauss and closed form agree to ~1e-15).

**Red receipt (Root).** 19 failures = 1+1+4+1+3+8+1, zero errors, control ok — arithmetically consistent with the file's subTest structure. Traceback line numbers (`_finite` 116, area 162, `mat = m[key]` 166, `ids =` 183) match the diff's *before* numbering exactly, which requires the before-file to carry the same three header lines as the after-file. **Provenance gap:** red `code_sha256 = ce6d2fe1…` ≠ the "Original SHA256 9986a18f…" stated in the repaired file's header. Most plausibly before = original + two header comment lines, but the bundle does not close that link; the claim "19 failures against the frozen old code" is supported only by inference.

**Green receipt (Root).** 8/8, same test hash as red, `code_sha256` = repaired file hash 160410e5… ✓.

**Independent receipt (Root).** 11/11 on 160410e5…. Its `test_sha256` field records the *regression* file hash (22528f69…), not review.py's (c57d20f8…), so the receipt does not bind the exact review script executed; "without changing the review script" rests on the report. The first (failing) receipt and the built-in 13/13 `validate` run are described but not in this bundle.

**review.py itself** (read): `exact_case` assembles R_HS/R_SA from config + condition in `Fraction` and calls `thermal_reference.steady` (not supplied); it hardcodes T_amb = T_res = 25 (true for the sample). None of its 11 tests touches the diffed code paths except that `run_study(original/sample_plan.json)` must still validate under the tightened rules — it does (all sections objects, all films equal). `test_original_12_frozen_rows…` is only non-circular if `reference_results.json` is the original fixture, as the report states; unverifiable here.

**Gaps relative to the audit's proposed regressions:** R1's config-level run (h = 0, R_rej = 1e17 → 108 records, B group unsolved, `null` check propagating to JSON) and R1's `reconstruct` assertions are not in the suite; only the unit call is. The `null`-through-`summarize`/`_sanitize` path is therefore untested end to end. Suggested test in §7.

---

## 5. Expected plan — independent re-derivation

From `build_shared_conditions` + sample config values (loads [1,5,10], f = 0.1, k_sil [0.18,0.35], k_film [0.12,0.25], r_c [0,0.002], h [3,15], R_rej [1,10]): A 3 + B 3 + C 13 (5 pairs + 2 bias + sensor-off) + D 8 + E 7 + F 2 = **36**, ids via `"%g"` (`P1`, `P5`, `P10`), override sets and `-f = -0.1` all match the 36 supplied entries; integer-vs-float literals (`1` vs `1.0`, `0` vs `0.0`) compare equal under dict `==`. The file is consistent with config and documented plan structure. It cannot by content alone prove independence from the generator's own output (it would look identical either way); its value is as a frozen drift guard, which is legitimate.

---

## 6. Independently derived limits and counterexamples

Notation: G = 1/R; ε = 2⁻⁵³. For this matrix the pivot test `|c| > |a|` is never true (a = G_HS + G_rej ≥ G_HS = |c|), so "partial pivoting" never engages; the Schur complement is exactly d₂ = G_SA + G_HS·G_rej/(G_HS+G_rej) = G_SA + 1/(R_HS + R_rej), computed as a difference of two numbers ≈ G_HS. Relative error of the Gauss result ≈ c·ε·G_HS/d₂ ≈ c·ε·(R_SA‖R_rej)/R_HS, c ∈ [1, 4].

- **Exact-zero (F1, now `None`):** needs both G_SA and G_rej below ½ulp(G_HS) (so a = d = G_HS, f = −1). For R_HS = 0.2: R_rej > ≈2.3e15 K/W with h = 0. Sample: never (h ≥ 3).
- **Spurious `False` (adjacent, CE-1):** check fails when c·ε·(R_SA‖R_rej)/R_HS ≳ 2e-9, i.e. (R_SA‖R_rej)/R_HS ≳ ~1e7 — for the reference stack, h = 0 and R_rej ≳ a few 1e6 K/W. **Sample margin:** (R_SA‖R_rej)/R_HS ≤ ~36/0.14 ≈ 260 → Gauss error ~3e-14, five orders below `agreement_tol_K`. This independently supports the audit's "no cancellation in the sample" verdict for the *check* as well as the closed form.
- **h·A underflow:** h·A < 2⁻¹⁰⁷⁵ (A = 0.01: h ≲ 2.5e-322) → ZeroDivisionError (F2a, now clean exit); 4.9e-324 ≤ h·A ≲ 5.6e-309 → `1/(hA)` overflows to `inf` silently (CE-3).
- **Anchor (my own recomputation, not inherited):** H1 nominal 5 W: R_HS = 0.217685, R_SA = 12.717685, Q_front = 10.2217685/14.93537 = 0.684400 W, T_S = 33.704, T_outer = 33.555, T_H = 33.831 °C; rear-blocked 5 W: T_outer 88.75, T_H 90.9486 °C — agree with v08 and the audit to 4–5 s.f.

**CE-1 (bit-level traced, high confidence; outside this correction):** `solve_two_node(5.0, 0.0, 1e-15, 5.0, 0.1, 25.0, 25.0)` (h = 0, R_rej = 1e15 K/W, R_HS = 0.2). Closed form: T_H = T_S ≈ 5.1e15 (exact 5.1e15 + 25; relative error ~1e-16). Gauss: a = 5 + 2⁻⁵⁰; f = −(1 − 2⁻⁵²); f·b = 5 − 2⁻⁵⁰; d₂ = 2⁻⁵⁰ ≈ 8.88e-16 versus exact ≈ 1.0e-15; T_S_gauss ≈ 5.1/8.88e-16 ≈ 5.74e15 (+12.6 %). `semantic_checks(...)["gauss_vs_closed_form_inverse"] == False` on a correct result; `n_all_semantic_checks_pass` under-counts. Order-of-magnitude (needs execution to confirm): the same `False` already at `G_rej = 1e-8` (R_rej = 1e8 K/W, h = 0). Mitigation options: declare the check unavailable when `d2 <= 64*eps*abs(d)` (cancellation detected), or document the regime. Not a wrong primary number; not sample-relevant.

**CE-2 (adjacent, expected, outside):** in the F1 regime every *difference-based* diagnostic degenerates: for the audit's R1 config (h = 0, R_rej = 1e17) and `A_nominal_P5`, a = d = G_HS makes the closed-form expressions for T_H and T_S identical bit for bit, so Q_HS = 0 and `sensor_flux_discontinuity_equals_P_sensor` reads `False` (0 vs 0.1 W) while energy and pareto checks pass. At |T| ≈ 5e17 °C the 0.02 K sensor rise is 3 ulps below representability; the Q's are correct. The audit's R1(config) claim (108 records, B group `no_finite_steady_state_both_exits_absent_net_source_nonzero`, 99 solved) holds statically; any added test should not assert all checks pass there.

**CE-3 (adjacent to F2a, outside):** `h_W_m2K: 1e-320` with A = 0.01: h·A = 1e-322 (subnormal, ≠ 0) → `R_conv = inf`, `G_SA = 0`, the case is solved as "front path absent" and the document echoes `h_W_m2K: 1e-320` beside `R_conv_K_W: "inf"` with no error. Physically indistinguishable from absent; interface-wise a silent reclassification. A `ConfigError` on `h*A == 0.0 or not isfinite(1/(h*A))` would fold F2(a) and this into the configuration boundary and also fix the library-call inconsistency.

**CE-4 (verified consistent, no action):** `area_m2 = 2**1023` is admitted (≈9e307); R_SA becomes subnormal, `G_SA = inf`, `solve_two_node` raises the existing `ValueError("R_SA = 0 … outside the study domain")`, caught cleanly. The huge-int boundary and the existing domain guards compose correctly.

---

## 7. Actionable items (none blocks admission)

1. **Add the end-to-end F1 regression** (exercises `None → null`, `summarize`, B-group classification):
```python
def test_h_zero_huge_R_rej_runs_end_to_end(self):
    cfg=copy.deepcopy(BASE); cfg['boundaries']['h_W_m2K']=0.0; cfg['boundaries']['R_rej_K_W']=1e17
    with tempfile.TemporaryDirectory(dir=ROOT/'execution') as tmp:
        inp=Path(tmp)/'in.json'; out=Path(tmp)/'out.json'; inp.write_text(json.dumps(cfg))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(['run','--config',str(inp),'--out',str(out)]),0)
        doc=json.loads(out.read_text()); self.assertEqual(len(doc['cases']),108)
        self.assertEqual(doc['summary']['n_solved'],99)
        for c in doc['cases']:
            if c['group']=='B_rear_blocked':
                self.assertEqual(c['status'],'no_finite_steady_state_both_exits_absent_net_source_nonzero')
            elif c['condition_id']=='A_nominal_P5':
                self.assertEqual(c['status'],'solved'); self.assertIsNone(c['checks']['gauss_vs_closed_form_inverse'])
                self.assertTrue(c['energy_check_pass'])
```
   (Static expectation: passes; do not assert `n_all_semantic_checks_pass`, see CE-2.)
2. **Provenance closure:** record sha256(before/thermal_contract.py) = ce6d2fe1… and its diff against the pristine original (9986a18f…); make the independent receipt bind review.py's hash (c57d20f8…); attach the `validate` 13/13 receipt and the first failing independent receipt to the bundle.
3. **Message quality (optional):** `sys.stderr.write("error: %s: %s\n" % (type(exc).__name__, exc))` so masked internal arithmetic bugs remain diagnosable; or raise `ConfigError` on `h*A` underflow/overflow (also resolves CE-3 and the library-call inconsistency).
4. **Documentation:** note the tightened film rule (or a schema-notes line) and the Gauss-check reliability regime from §6; optionally the `d2` cancellation guard.

---

## 8. Credit and limitations

Original implementation and the recovered static audit: Claude Fable 5.1. Repair, new harness, receipts and prose: Coda (Codex Lily), with Richard Pemberton directing. Root executed the tests; Fable and this review did not. Everything here is reasoning over supplied text plus IEEE-754 arithmetic by hand; the receipts are consistent with that reasoning but are not my verification, and the exact-reference module, fixture files, results file and manifest hashes were not available to me. This is private computational review of a hypothetical linear model: no measurement, no validation, no safety or physiological content.