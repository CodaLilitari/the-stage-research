# Candidate 3 — report (Claude, Anthropic; static, not executed)

Patch base: Coda's candidate 2, `fixed/thermal_contract.py`, SHA-256
160410e5cecb4e2408f3b13e42ae5213f12d43216d725859afbfa1e6e4b3a06a. Eleven hunks; no numeric,
ordering, serialization or validate-mode output path changes for any configuration that
candidate 2 accepted and candidate 3 still accepts. Private computational research on a
hypothetical linear model; nothing measured, validated or safety-relevant.

## 1. What the patch does

| Item | Change | Where |
|---|---|---|
| (1) cancellation guard | `solve_two_node` records `gauss_amplification = (|d|+|f b|)/|d2|` (inf when elimination raised); `semantic_checks` reports `gauss_vs_closed_form_inverse = None` when `16·u·amp >= agreement_tol_K` (u = 2^-53). Raw Gauss values stay in the solution dict. | new `gauss_pivot_amplification`, hunks G1–G3, H |
| (2) h·A boundary | New `front_convective_resistance_K_W(h, A, where)`: `h == 0 -> inf` (documented limit); for h > 0 requires h·A finite, > 0, with finite reciprocal, else `ConfigError` naming the field. Used by `assemble_resistances` (identical arithmetic), by `resolve_parameters` per condition, and by `_validate_config` for the nominal h and both range bounds. Covers F2a (h·A → 0), CE‑3 (subnormal h·A → R_conv = inf) and the mirror overflow (h·A = inf → R_conv = 0). | hunks D, E, F, I |
| (3) validator note | `VALIDATOR_NOTES` constant (film rule from candidate 2, the new h·A rule, the Gauss availability rule); the film and h·A error messages name their note. `SCHEMA_VERSION` deliberately unchanged (echoed in output). | hunks B, C |
| (4) provenance | File header names the patch base hash and author; `test_candidate3.py` prints code/test/sample hashes as a receipt; `provenance_receipt.py` hashes the bundle, checks expectations (full hashes or audit prefixes) and mechanically tests the inference "before = original + header lines 2–3". | hunk A; tools |

Not changed (deliberately): `solve_2x2_gauss`, closed-form expressions, `reconstruct`, plan,
`run_study`, `_sanitize`, `summarize`, validate-mode tests and their printed text, CLI
message format (audit item 7.3 remains optional), schema version.

## 2. Threshold justification (static IEEE‑754 reasoning)

For the thermal matrix the pivot never swaps (a = G_HS+G_rej ≥ |c| = G_HS). The Schur
complement d2 = d − f·b equals det/a = G_SA + G_HS·G_rej/(G_HS+G_rej) exactly but is computed
as a difference of two numbers near G_HS. Counting one rounding each in a, f, f·b, the
subtraction and d's own formation, |fl(d2) − d2| ≤ u(|d2| + |d| + 3|f·b|), so the relative
error of d2 — and of the eliminated unknown x2 = r2b/d2 — is ≤ u + 3u·amp with
amp = (|d|+|f·b|)/|d2| ≥ 1. Adding ≤ 3u for r2b, u for the division and ≤ 3u for back
substitution (no sign mixing in the sources/boundaries), the Gauss result's relative error is
≲ 3u·amp + 8u ≤ 11u·amp. The check `_close` passes iff |ΔT| ≤ tol·(1+|T_g|+|T|) ≥ 2·tol·|T|;
with the closed form itself accurate to ~6u, rounding alone cannot produce `False` whenever
16u·amp < tol (margin ≥ 2.6×). Conversely, when 16u·amp ≥ tol a `False` cannot be charged to the
closed form, so the check is reported unavailable. The threshold is therefore tied to the
tolerance in force rather than fixed (Fable's `64u·|d|` would still report `False` across the
band d2/|d| ∈ (7e‑15, ~1e‑6), e.g. h = 0, R_rej = 1e8 K/W).

Consequences: sample plan — all 108 cases have amp ≈ 9…55 (max ≈ 53 at C_R_rej_hi/E2 for H1), so
16u·amp ≈ 1e‑13 ≪ 1e‑9 and nothing changes. For any h ≥ 3 W/m²K in the sample ranges amp stays
< ~500 even for R_rej → ∞ (blocked). With h = 0 and the reference stack the guard starts to
fire at R_rej ≳ 5.6e4 K/W (amp ≈ 10/G_rej ≥ 5.6e5). CE‑1 (amp ≈ 1.1e16 → bound ≈ 20): None for
tol < 20, computed and True for tol = 1e3. Caveat (documented, not fixed): cancellation in the
right-hand side with mixed-sign sources/boundaries is not covered by `amp`; CE‑2 (bit-identical
T_H, T_S in the exact-zero regime) is unchanged.

## 3. Bit-identity argument for the 108-case sample

* `R_conv`: for h > 0, `float(h)*float(A)` is the same product as `p["h"]*A` (float() is the
  identity on floats) and `1.0/hA` the same division; for h = 0 both return `math.inf`. The
  extra `hA != 0.0` branch only matters when the old code raised.
* The extra helper calls in validation and `resolve_parameters` are pure and their results
  are discarded.
* `gauss_amplification` is added to the internal solution dict only; `run_case` copies named
  keys, so the document schema is untouched. The guard never fires in the sample (§2), so
  `checks` values are unchanged.
* Validate mode: no new prints and no new self-check; 13/13 text identical.

## 4. Expected test outcomes (static predictions)

`test_candidate3.py` against candidate 2 (`THERMAL_CANDIDATE=fixed/thermal_contract.py`):

| test | expected before | reason |
|---|---|---|
| `test_CE1_cross_check_unavailable_not_false` | FAIL | check is `False` (Red receipt) |
| `test_guard_threshold_tracks_agreement_tolerance` | FAIL | tol 1e‑9 leg `False`, tol 1.0 leg `True`, neither `None` |
| `test_solution_reports_pivot_amplification` | ERROR | `KeyError 'gauss_amplification'` |
| `test_sample_plan_never_triggers_guard` | ERROR | KeyError / AttributeError |
| `test_hA_underflow_to_zero_is_ConfigError_everywhere` | FAIL | `validate_config` admits h = 5e‑324 |
| `test_CE3_subnormal_hA_rejected_not_reclassified` | FAIL | admitted; rc 0 (Red receipt) |
| `test_hA_overflow_rejected` | FAIL | admitted |
| `test_h_range_bounds_checked_at_validation` | FAIL | admitted |
| `test_h_zero_remains_absent_front_path_limit` | ERROR | helper absent |
| `test_validator_notes_and_messages` | ERROR | `VALIDATOR_NOTES` absent |
| `test_header_names_patch_base_hash` | FAIL | hash not in file |
| `RegressionControls.*` (3 tests) | pass | unchanged behaviour |

Against candidate 3: 14/14 pass. Coda's `test_audit.py`: 8/8 still pass (F2a test now sees the
`ConfigError` message, still `error:`-prefixed, rc 1, no file). Red's `test_fable_followup.py`:
`test_h_zero_huge_R_rej_runs_end_to_end` passes (statuses, n_solved 99 and the `None` at
A_nominal_P5 are unaffected); `test_CE1_spurious_false_gauss_check` passes (raw Gauss values
retained in `solve_two_node`); **`test_CE3_subnormal_hA_silent` is expected to FAIL by design**
(rc is now 1) — it encoded the defect and should be inverted or retired. `review.py`: 11/11
expected (output byte-identical).

## 5. How Red should apply and verify

