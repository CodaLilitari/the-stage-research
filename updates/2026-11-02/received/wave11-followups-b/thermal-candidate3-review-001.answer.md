# Review of candidate 3 (thermal-candidate3-review-001)

**Method statement.** Static reasoning only, over the verbatim bundle (candidate‑3 answer and diff, `test_candidate3.py`, Red's three receipts, the candidate‑2 source, the wave‑6 audit). I executed nothing and read no file beyond the bundle; every number below is hand arithmetic or a receipt I quote as Red's. Anything I could not check from the bundle is labelled **assumption**. The small tools at the end are unexecuted and will be judged by Red's run.

## 0. Findings at a glance

| # | Finding | Severity | Where |
|---|---|---|---|
| 1 | "8 FAIL + 3 ERROR" is a tally slip in the report prose; the author's own per‑test table and the test code both give 7 F + 4 E, which is exactly what Red saw (11/11 per‑test predictions matched). | report text only | §1 |
| 2 | Hunk E's `@@` header claims +26 lines, its body has +25; hence 956 → 1059 (+103), not +104. Harmless (`apply_patch.py` ignores headers), but a regenerated `diff -u` will not match the headers. | cosmetic | §2.4 |
| 3 | Report §2 says the sample's max amplification is ≈ 53–55; it omits the rear‑blocked group, where amp = 2·R_SA/R_HS + 1 ≈ 118 for H1 (assumption A1). Red's passing assertion brackets the true sample max in [≈118, 563). The guard margin remains > 3 decades. | report text only | §2.2 |
| 4 | The guard's safety margin against a worst‑case first‑order bound is ≈ 1.7–1.9×, not "≥ 2.6×". Adequate; factor 32 would be the conservative alternative with no in‑domain effect. Not required. | documentation | §2.1 |
| 5 | No new false rejection inside the declared domain from either the guard (True→None) or the h·A boundary (admit→ConfigError); both boundaries lie 4–5 (guard) and ≈ 300 (h·A) decades outside the sample ranges. | — | §2 |
| 6 | The a81199c6… vs 913bfd2c… difference is line endings (Windows text‑mode CRLF), not environment fields: the document contains none. Decisive test given. | provenance | §3 |
| 7 | No defect found in `candidate3/thermal_contract.py`; no diff to it is proposed. | — | §4 |

## 1. The 8F+3E vs 7F+4E "discrepancy"

Classification is fixed by the first statement that misbehaves on candidate 2, and `_Base.assert_config_error` turns "nothing raised" and "wrong exception type" into `self.fail` (FAIL), while attribute/key lookups of symbols that do not exist on candidate 2 raise (ERROR):

| test | first misbehaving statement on candidate 2 | outcome |
|---|---|---|
| CE1_cross_check_unavailable_not_false | `assertIsNone(False)` | FAIL |
| guard_threshold_tracks_agreement_tolerance | `assertIsNone(False)` (tol 1e‑9 leg) | FAIL |
| hA_underflow_to_zero_is_ConfigError_everywhere | `assert_config_error(validate_config)` → nothing raised | FAIL |
| CE3_subnormal_hA_rejected_not_reclassified | same | FAIL |
| hA_overflow_rejected | same | FAIL |
| h_range_bounds_checked_at_validation | same | FAIL |
| header_names_patch_base_hash | `assertIn(hash, text)` | FAIL |
| solution_reports_pivot_amplification | `sol["gauss_amplification"]` → KeyError | ERROR |
| sample_plan_never_triggers_guard | `sol["gauss_amplification"]` → KeyError (plan/resolve/assemble/solve all exist) | ERROR |
| h_zero_remains_absent_front_path_limit | `m.front_convective_resistance_K_W` → AttributeError | ERROR |
| validator_notes_and_messages | `m.VALIDATOR_NOTES` → AttributeError (precedes the film‑message assertion that would have been a FAIL) | ERROR |

7 FAIL + 4 ERROR + 3 controls ok, deterministic and environment‑independent. The author's §4 table lists precisely these 11 outcomes; only the headline in §5 (shell comment) and in "Summary for Red" mis‑adds them as 8 + 3. So nothing was mispredicted; correct the two headline strings (errata file below). Red's receipt also confirms the two controls that mattered: `test_candidate2_regressions_still_hold` passes on candidate 2 (so the F2a path still exits via `error:` there) and all three controls pass on candidate 3.

## 2. Guard threshold and h·A boundary: false rejections inside the declared domain?

### 2.1 What the guard computes, and where it fires
For the thermal matrix the pivot never swaps (a = G_HS + G_rej ≥ |c| = G_HS), `gauss_pivot_amplification` recomputes `fb = (c/a)*b` and `d2 = d − fb` with the same operations in the same order as `solve_2x2_gauss`, so `d2` is bit‑identical to the eliminator's; amp = (|d| + |fb|)/|d2| ≥ 1 since d, fb > 0 and d2 = d − fb. Closed forms (exact arithmetic):

- finite h, finite R_rej: d2 = G_SA + 1/(R_HS + R_rej), so amp ≤ 1 + 2·min(R_SA, R_HS + R_rej)/R_HS;
- h = 0: amp = 2·R_rej/R_HS + 1;
- rear blocked: f = −1 exactly, fb = G_HS, d2 = fl(G_HS + G_SA) − G_HS, amp = 2·R_SA/R_HS + 1.

With u = 2⁻⁵³ and factor 16, the guard fires iff amp ≥ tol/(16u) = 5.63·10⁵ for tol = 10⁻⁹, i.e. iff **both** exits are weaker than ≈ 2.8·10⁵·R_HS: for R_HS ≈ 0.14–0.5 K/W that is R_rej ≳ 4·10⁴–1.4·10⁵ K/W **and** R_SA ≳ the same (h ≲ 10⁻³ W/m²K at A = 0.01 m²). The sample's declared ranges (h ∈ [3, 15], R_rej ∈ [1, 10] K/W or blocked; the author's §2 claim of amp < ~500 for any h ≥ 3 is right) are four to five decades away. At h = 0 (documented limit) with H1, the guard starts at R_rej ≈ 0.218·5.63·10⁵/2 ≈ 6·10⁴ K/W (author: 5.6·10⁴ with R_HS = 0.2; same thing).

**Error‑bound audit.** I re‑derived the author's bound: fl(d2) carries ≈ u|d2| + u|d| + 3u|fb| (one rounding each in a, f, f·b, the subtraction; d's own formation counted in |d|), so rel. err(d2) ≤ u + 3u·amp; r2b and the back‑substitution add no cancellation when sources and boundaries are non‑negative, giving x_g within ≈ 3u·amp + 10u ≤ 13u·amp (author 11u·amp — same order). The closed form costs ≈ 8u (author 6u). `_close` fails only if |Δ| > tol·(1+|T_g|+|T|) ≈ 2·tol·|T|, i.e. if ≈ 19–21u·amp > 2·tol ⇒ amp > ≈ 0.10–0.12·tol/u, while the guard fires at amp ≥ 0.0625·tol/u. The margin is therefore ≈ **1.7–1.9×**, not "≥ 2.6×". It is a margin on a first‑order worst‑case bound that is never attained for this matrix (CE‑1 realises 0.126 relative error against u·amp = 1.25, i.e. ≈ 0.1·u·amp), so in practice a False cannot slip under the guard. Conversely, because the bound is a priori and conservative, the guard converts True → None roughly two to three decades *before* the check would actually fail (h = 0, H1: guard at R_rej ≈ 6·10⁴ K/W; actual False, per the wave‑6 estimate and the CE‑1 scaling, at ≈ 10⁶–10⁷ K/W). That band is a loss of a diagnostic, never of a number, and is far outside the declared domain. Mixed‑sign RHS cancellation is not covered by amp (author's documented caveat); inside the domain (T_amb = T_res = 25 °C, non‑negative loads) it does not arise, and the `1.0 +` floor in `_close` neutralises the only sign crossing a negative T_amb could create (T ≈ 0 °C).

**Merged‑node and singular branches.** `solve_two_node` returns no `gauss_amplification` key for `solved_merged_node_R_HS_zero`; `semantic_checks` uses `sol.get(...)` → None → the old branch, so that case is unchanged (T_H_gauss ≡ T_H, True). Singular results never reach `semantic_checks`. The F1 exact‑zero path keeps `None` (first branch). No regression.

### 2.2 Sample‑plan numbers (assumption A1: H1 = `_ref_stack`/`_ref_params`, consistent with v08 and the wave‑6 anchor R_HS = 0.217685, R_SA = 12.717685 K/W)
- A_nominal (R_rej = 2): d2 = 0.0786 + 1/2.2177 = 0.5296, amp ≈ (4.672 + 3.200)/0.530 ≈ 15.
- C_R_rej_hi (R_rej = 10): amp ≈ 9.17/0.1765 ≈ 52 — the author's "≈ 53".
- **B_rear_blocked (any load): amp = 2·12.717685/0.217685 + 1 ≈ 117.8**; E4 (blocked, h = 3, k_sil 0.18, r_c 0.002, +10 %): ≈ 132; thinner stacks are larger (amp ∝ R_SA/R_HS).
Red's receipt shows `assertLess(16·u·amp, 1e‑3·tol)` passing for all 108 cases, which bounds the sample max below 563; so the true max is in [≈118, 563), not ≈ 55. The worst guard ratio is < 10⁻³ and the author's conclusion ("nothing changes in the sample") stands; only the narrative number is wrong. `amp_scan.py` below prints the actual maximum and the case it occurs in.

### 2.3 The h·A boundary
`front_convective_resistance_K_W` raises only when h > 0 and h·A rounds to 0 (h·A < 2⁻¹⁰⁷⁵), is subnormal with 1/(h·A) = inf (h·A ≲ 5.56·10⁻³⁰⁹; Python's float division does not raise on overflow, so this path returns inf, which `isfinite` catches — consistent with Red's passing CE‑3 test), or overflows to inf (h·A > 1.797·10³⁰⁸). With A = 0.01 m² that is h ≲ 5.6·10⁻³⁰⁷ or unreachable from above (h finite ⇒ h·A ≤ 1.8·10³⁰⁶). For h > 0 in range the value is `float(h)*float(A)` then `1.0/hA`, bit‑identical to the old expression (float() is the identity on floats; int h converts identically). h = 0 and −0.0 return inf exactly as before. The validator calls use `g["area_m2"]` and the range bounds after both have been proven finite (and h ≥ 0, lower bound ≥ 0), so no new exception type can escape; the per‑condition call sits after the existing `p["h"] < 0.0` check. For library callers the helper additionally turns negative or NaN h into `ConfigError` (previously a silently negative/NaN R_conv or a downstream ValueError) — a tightening outside the domain; its message wording ("no finite positive R_conv") is slightly off for negative h, cosmetic. **No admitted in‑domain configuration is newly rejected**; the three narrowed regions are exactly the three defect regions (F2a, CE‑3, overflow mirror).

### 2.4 Diff hygiene
Line arithmetic per hunk body: +3, +32, +1, +4, **+25**, 0, +25, +3, +3, +5, +2 = +103, matching Red's "956 -> 1059". Hunk E's header says `+298,32`; it should be `+298,31`, and every later new‑side start is one too high. `apply_patch.py` matches context and ignores headers, so the applied file is correct; the regenerated `diff -u` will simply carry corrected headers. Note also that Red's base was CRLF (hash 160410e5… is therefore the hash of CRLF bytes, computed on Coda's side) while `apply_patch.py` wrote LF, so `diff -u fixed/… candidate3/…` shows every line changed unless run with `--strip-trailing-cr` (or on normalised copies). Candidate 3's hash 1de0ba9f… is reproducible on Windows with the same tool because it writes with `newline=""`.

## 3. Why the results hash differs from Coda's, and how to confirm identity on Windows

`run_study` writes with `open(out_path, "w"/"x", encoding="utf-8")` — text mode, `newline=None` — so every `"\n"` that `json.dump(indent=1)` emits becomes `"\r\n"` on Windows and stays `"\n"` on Linux. The document itself contains **no environment field**: its keys are schema strings, fixed prose lists, `conditions`, `config_echo` (the *parsed* config, so CRLF in the input is irrelevant), `cases`, `summary`; no timestamp, path, hostname, Python version or platform. Floats are serialised with Python's shortest‑repr algorithm (identical since 3.1), the arithmetic is binary64 `+ − × ÷` only (correctly rounded on every mainstream 64‑bit platform; no transcendentals), dict order is insertion order, `ensure_ascii=True` escapes any non‑ASCII identically. Hence the content is platform‑invariant and the only byte difference is the line terminator. That both candidates differ "equally" fits: same content, same translation. (Assumptions A2/A4: 913bfd2c… is the raw hash of Coda's Windows file, a81199c6… the raw hash of Red's Linux file.)

**Decisive, falsifiable check (either side, stdlib only).** Red, now:
```
python3 candidate3/review/results_identity.py execution/c3_results.json execution/c3_results.json   # sanity: identical
python3 -c "import hashlib;d=open('execution/c3_results.json','rb').read();print(d.count(b'\n'),hashlib.sha256(d.replace(b'\n',b'\r\n')).hexdigest())"
```
Prediction: the second line prints the newline count L and **913bfd2c…**. Coda, on Windows, against `fixed_results.json`: the LF‑normalised hash must be **a81199c6…**, the CRLF count must equal L, and the file size must exceed Red's by L. When Coda has both files, `results_identity.py A B` records raw / LF‑normalised / CRLF‑translated hashes for both, the crossed equalities, and — if normalised bytes still differed — the first differing JSON path (which would indicate a content difference such as a different `sample_plan.json`; Red's receipt binds the plan at 25c31407…, Coda's green receipt should show the same). Recommendation for the manifest: record both the raw and the LF‑normalised SHA‑256 of every results file; keep `newline=""`/binary transfers for bundle files so that text‑file hashes (160410e5…, 72e10638…, 1de0ba9f…) survive a Windows checkout (`core.autocrlf=false`). Changing `run_study` to `newline="\n"` would make Windows bytes equal to Linux bytes in future but would also stop 913bfd2c… from being reproducible on Windows; I do not propose it for this candidate — it is not a defect, and the receipt tooling resolves it. One caveat for `provenance_receipt.py --drop-lines-compare`: it is byte‑wise, so mixed line endings between `before/` and `original/` would report non‑identical spuriously; normalise both first (or compare LF‑normalised hashes).

## 4. Verdict: **admit with conditions**

Candidate 3 resolves CE‑1 (spurious False → None under an explicit, tolerance‑tracking a‑priori bound), CE‑3 and F2a's library‑call inconsistency (one helper, one boundary, identical in‑domain arithmetic) and the overflow mirror, adds no numeric/ordering/serialisation change for accepted configurations (Red: results byte‑identical to candidate 2, `validate` identical, Coda's 8/8 pass), and its tests discriminate before/after exactly as claimed. I found **no defect in the code** and propose **no diff** to `thermal_contract.py`. Conditions (bookkeeping, none code):

1. Correct the report headline to 7 F + 4 E; note the hunk‑E header miscount; replace "max ≈ 53–55" by the measured sample maximum from `amp_scan.py` (expected ≈ 118 for H1 blocked or larger for thinner stacks, < 563) and the margin figure (≈ 1.7–1.9×). Errata file below.
2. Close the hash provenance with the LF‑normalised identity (both predictions in §3 must hold); record raw and normalised hashes.
3. Regenerate the authoritative diff with `--strip-trailing-cr`; record 1de0ba9f… as candidate 3 (LF) and note 160410e5… is over CRLF bytes.
4. Retire or invert Red's `test_CE3_subnormal_hA_silent` (assumption A3: exists as the author describes; it encodes the defect, rc must now be 1).
5. Optional: run Coda's `review.py` on a tree with `fixed/thermal_contract.py` replaced (expected 11/11 since the document is byte‑identical).

Status after admission, as before: candidate repair of a hypothetical linear model; nothing measured, validated or safety‑relevant.

## 5. Files (unexecuted; stdlib only; deterministic; writes only `--out`)

FILE: candidate3/review/results_identity.py
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Line-ending-aware identity receipt for two text/JSON files (candidate 3 review; Claude, Anthropic).

Usage:
  python3 results_identity.py A B [--out receipt.json] [--force]

For each file: size, newline census (CRLF / bare LF / bare CR), raw SHA-256, SHA-256 after
CRLF->LF normalisation, SHA-256 after LF->CRLF translation of the normalised bytes.  Two files
written by the same program on Windows (text mode, CRLF) and on POSIX (LF) have equal normalised
hashes and crossed raw/translated hashes.  If the normalised bytes differ and both parse as JSON,
the first differing JSON path is reported (content difference, not line endings).
Standard library only; deterministic; no network; writes only --out.
Exit 0 iff the normalised bytes are identical; 1 if they differ; 2 on usage/refusal errors.
"""
import argparse
import hashlib
import json
import os
import platform
import sys


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normalise_lf(data):
    return data.replace(b"\r\n", b"\n")


def translate_crlf(data_lf):
    return data_lf.replace(b"\n", b"\r\n")


def newline_census(data):
    crlf = data.count(b"\r\n")
    return {"crlf": crlf, "bare_lf": data.count(b"\n") - crlf, "bare_cr": data.count(b"\r") - crlf}


def describe(path):
    with open(path, "rb") as fh:
        data = fh.read()
    lf = normalise_lf(data)
    return ({"path": path, "size": len(data), "newlines": newline_census(data),
             "sha256_raw": sha256(data), "sha256_lf_normalised": sha256(lf),
             "sha256_crlf_translated": sha256(translate_crlf(lf))}, lf)


def first_json_difference(x, y, path=()):
    """(path, x_value, y_value) of the first difference between two parsed JSON values, else None."""
    if type(x) is not type(y):
        return path, x, y
    if isinstance(x, dict):
        if list(x) != list(y):
            return path, "<keys %s>" % (list(x)[:8],), "<keys %s>" % (list(y)[:8],)
        for k in x:
            d = first_json_difference(x[k], y[k], path + (k,))
            if d is not None:
                return d
        return None
    if isinstance(x, list):
        for i in range(min(len(x), len(y))):
            d = first_json_difference(x[i], y[i], path + (i,))
            if d is not None:
                return d
        if len(x) != len(y):
            return path, "<len %d>" % len(x), "<len %d>" % len(y)
        return None
    return None if x == y else (path, x, y)


def compare(path_a, path_b):
    da, lfa = describe(path_a)
    db, lfb = describe(path_b)
    receipt = {"tool": "results_identity.py (candidate 3 review)", "python": platform.python_version(),
               "platform": platform.platform(), "a": da, "b": db,
               "raw_identical": da["sha256_raw"] == db["sha256_raw"],
               "lf_normalised_identical": lfa == lfb,
               "a_crlf_translated_equals_b_raw": da["sha256_crlf_translated"] == db["sha256_raw"],
               "b_crlf_translated_equals_a_raw": db["sha256_crlf_translated"] == da["sha256_raw"]}
    if not receipt["lf_normalised_identical"]:
        try:
            ja, jb = json.loads(lfa.decode("utf-8")), json.loads(lfb.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            receipt["json"] = {"parsed": False, "error": str(exc)}
        else:
            diff = first_json_difference(ja, jb)
            receipt["json"] = {"parsed": True, "equal": diff is None,
                               "first_difference": None if diff is None else
                               {"path": list(diff[0]), "a": repr(diff[1])[:200], "b": repr(diff[2])[:200]}}
            if diff is None:
                receipt["json"]["note"] = "same JSON content; byte difference is whitespace/formatting only"
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description="line-ending-aware SHA-256 identity receipt for two files")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    for p in (args.a, args.b):
        if not os.path.isfile(p):
            sys.stderr.write("error: not a file: %r\n" % p)
            return 2
    receipt = compare(args.a, args.b)
    text = json.dumps(receipt, indent=1, sort_keys=True)
    if args.out:
        if os.path.exists(args.out) and not args.force:
            sys.stderr.write("error: refusing to overwrite existing %r (use --force)\n" % args.out)
            return 2
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    print(text)
    print("verdict: %s" % ("LF-normalised bytes identical" if receipt["lf_normalised_identical"]
                           else "bytes differ after line-ending normalisation"))
    return 0 if receipt["lf_normalised_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

FILE: candidate3/review/test_results_identity.py
```python
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for results_identity.py (candidate 3 review tooling)."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("results_identity", str(HERE / "results_identity.py"))
ri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ri)

DOC = {"schema": "x", "summary": {"n": 2}, "cases": [{"id": "a", "T": 1.5}, {"id": "b", "T": 2.5}]}


class ResultsIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, text, crlf=False):
        data = text.encode("utf-8")
        if crlf:
            data = data.replace(b"\n", b"\r\n")
        p = self.dir / name
        p.write_bytes(data)
        return str(p)

    def test_line_ending_only_difference(self):
        text = json.dumps(DOC, indent=1)
        a = self._write("lf.json", text)
        b = self._write("crlf.json", text, crlf=True)
        r = ri.compare(a, b)
        n = text.count("\n")
        self.assertFalse(r["raw_identical"])
        self.assertTrue(r["lf_normalised_identical"])
        self.assertTrue(r["a_crlf_translated_equals_b_raw"])
        self.assertTrue(r["b_crlf_translated_equals_a_raw"])
        self.assertEqual(r["a"]["newlines"], {"crlf": 0, "bare_lf": n, "bare_cr": 0})
        self.assertEqual(r["b"]["newlines"], {"crlf": n, "bare_lf": 0, "bare_cr": 0})
        self.assertEqual(r["b"]["size"] - r["a"]["size"], n)
        self.assertNotIn("json", r)

    def test_content_difference_is_located(self):
        d2 = json.loads(json.dumps(DOC))
        d2["cases"][1]["T"] = 2.5000001
        a = self._write("a.json", json.dumps(DOC, indent=1))
        b = self._write("b.json", json.dumps(d2, indent=1), crlf=True)
        r = ri.compare(a, b)
        self.assertFalse(r["lf_normalised_identical"])
        self.assertTrue(r["json"]["parsed"])
        self.assertFalse(r["json"]["equal"])
        self.assertEqual(r["json"]["first_difference"]["path"], ["cases", 1, "T"])

    def test_first_json_difference_cases(self):
        self.assertIsNone(ri.first_json_difference(DOC, json.loads(json.dumps(DOC))))
        self.assertEqual(ri.first_json_difference([1, 2], [1, 2, 3])[0], (2,))
        self.assertEqual(ri.first_json_difference({"a": 1}, {"a": 1.0})[0], ("a",))   # int vs float
        self.assertEqual(ri.first_json_difference({"a": 1, "b": 2}, {"b": 2, "a": 1})[0], ())  # key order

    def test_main_exit_codes_and_out(self):
        text = json.dumps(DOC, indent=1)
        a = self._write("x.json", text)
        b = self._write("y.json", text, crlf=True)
        c = self._write("z.json", json.dumps({"schema": "other"}, indent=1))
        out = self.dir / "receipt.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ri.main([a, b, "--out", str(out)]), 0)
            self.assertEqual(ri.main([a, b, "--out", str(out)]), 2)          # refuses overwrite
            self.assertEqual(ri.main([a, b, "--out", str(out), "--force"]), 0)
            self.assertEqual(ri.main([a, c]), 1)
            self.assertEqual(ri.main([a, str(self.dir / "missing.json")]), 2)
        rec = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(rec["lf_normalised_identical"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

FILE: candidate3/review/amp_scan.py
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Gauss pivot amplification of every plan case (candidate 3 review; Claude, Anthropic; diagnostic only).

Usage:  python3 amp_scan.py [--top N]
  THERMAL_CANDIDATE    module to scan   (default ../thermal_contract.py = candidate3/thermal_contract.py)
  THERMAL_SAMPLE_PLAN  plan JSON        (default ../../original/sample_plan.json)
Prints the N largest amplifications with resistances and the guard ratio
GAUSS_CHECK_ERROR_FACTOR * u * amp / agreement_tol_K (the guard fires at ratio >= 1), the per-group
maxima and the overall min/max.  Also runs on candidate 2 (amplification recomputed locally with the
same arithmetic when the module does not report it).  Writes nothing.
"""
import argparse
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = Path(os.environ.get("THERMAL_CANDIDATE", str(HERE.parent / "thermal_contract.py"))).resolve()
PLAN = Path(os.environ.get("THERMAL_SAMPLE_PLAN",
                           str(HERE.parent.parent / "original" / "sample_plan.json"))).resolve()
U = sys.float_info.epsilon / 2.0


def local_amplification(G_HS, G_SA, G_rej):
    """Same arithmetic as candidate 3's gauss_pivot_amplification for the thermal matrix (no pivot swap)."""
    a, b, c, d = G_HS + G_rej, -G_HS, -G_HS, G_HS + G_SA
    fb = (c / a) * b
    d2 = d - fb
    return math.inf if d2 == 0.0 else (abs(d) + abs(fb)) / abs(d2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="pivot amplification scan of a plan")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("thermal_under_scan", str(CODE))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    cfg = json.loads(PLAN.read_text(encoding="utf-8"))
    m.validate_config(cfg)
    tol = cfg["numerics"]["agreement_tol_K"]
    factor = getattr(m, "GAUSS_CHECK_ERROR_FACTOR", 16.0)
    rows = []
    for cond in m.build_shared_conditions(cfg):
        for stack in cfg["stacks"]:
            p = m.resolve_parameters(cfg, cond)
            R = m.assemble_resistances(stack, p)
            G = [m.conductance_W_K(R[k]) for k in ("R_HS_K_W", "R_SA_K_W", "R_rej_K_W")]
            sol = m.solve_two_node(G[0], G[1], G[2], p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
            if sol["status"] != "solved":
                continue
            amp = sol.get("gauss_amplification")
            if amp is None:
                amp = local_amplification(G[0], G[1], G[2])
            rows.append((amp, "%s__%s" % (stack["stack_id"], cond["condition_id"]), cond["group"],
                         R["R_HS_K_W"], R["R_SA_K_W"], R["R_rej_K_W"]))
    print("module %s\nplan   %s" % (CODE, PLAN))
    if not rows:
        print("no solved cases")
        return 0
    rows.sort(key=lambda r: (-r[0], r[1]))
    print("%-40s %-28s %10s %10s %10s %10s %12s" % ("case_id", "group", "amp", "R_HS", "R_SA", "R_rej",
                                                     "guard_ratio"))
    for amp, cid, grp, rhs, rsa, rrej in rows[:args.top]:
        print("%-40s %-28s %10.4g %10.5g %10.5g %10.5g %12.3e" % (cid, grp, amp, rhs, rsa, rrej,
                                                                   factor * U * amp / tol))
    groups = {}
    for amp, cid, grp, _rhs, _rsa, _rrej in rows:
        if amp > groups.get(grp, (-1.0, ""))[0]:
            groups[grp] = (amp, cid)
    for grp in sorted(groups):
        print("group max %-28s %10.4g  (%s)" % (grp, groups[grp][0], groups[grp][1]))
    print("solved cases %d; amp min %.4g max %.4g; max guard ratio %.3e (fires at >= 1); "
          "u = %r factor = %r tol = %r" % (len(rows), rows[-1][0], rows[0][0],
                                            factor * U * rows[0][0] / tol, U, factor, tol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: candidate3/review/ERRATA_candidate3.md
```markdown
# Errata to REPORT_candidate3.md (review thermal-candidate3-review-001; Claude, Anthropic; static)

1. §5 shell comment and "Summary for Red": "8 FAIL + 3 ERROR" -> "7 FAIL + 4 ERROR". The §4
   per-test table was already 7 F + 4 E and matches Red's receipt test by test.
2. candidate3.diff hunk E header "@@ -258,6 +298,32 @@" overstates the body by one line (+25,
   not +26); net change is +103 lines (956 -> 1059, Red's receipt). Applied file is correct;
   regenerate the diff with `diff -u --strip-trailing-cr` (base file is CRLF).
3. §2 "all 108 cases have amp ~ 9..55 (max ~ 53 at C_R_rej_hi/E2 for H1)": omits the rear-blocked
   group, where amp = 2 R_SA/R_HS + 1 ~ 118 for H1 (and E4 ~ 132; thinner stacks larger). Red's
   passing assertion bounds the sample maximum below 563; run review/amp_scan.py for the value.
   Conclusion unchanged: max guard ratio < 1e-3.
4. §2 "margin >= 2.6x": against the stated first-order worst-case bounds the margin is ~1.7-1.9x
   (guard at amp = 0.0625 tol/u; rounding-induced False needs amp > ~0.10-0.12 tol/u).
5. §5 "expect 913bfd2c..." for the Linux results hash: that hash is of Coda's Windows (CRLF) file;
   on Linux expect a81199c6... raw and 913bfd2c... after LF->CRLF translation (review/results_identity.py).
```

## 6. Left open / assumptions / credit

- **Not implemented:** no change to `thermal_contract.py` (no defect found); no `newline="\n"` change to `run_study` (discussed, deliberately not proposed); no grid scan outside the sample plan (the closed forms in §2.1 cover it analytically).
- **Assumptions:** A1 H1 geometry/nominals equal `_ref_stack`/`_ref_params` (sample plan not in my bundle); A2/A4 913bfd2c… and a81199c6… are raw hashes of files written directly by the program on Windows and Linux respectively; A3 Red's `test_fable_followup.py::test_CE3_subnormal_hA_silent` exists as the candidate‑3 author described it.
- **Receipts only Red/Coda can attach:** the two hash predictions in §3; `amp_scan.py` output; regenerated diff; `review.py` 11/11 on a candidate‑3 tree.
- **Credit:** original implementation and recovered audit, Claude Fable 5.1; candidate 2, harness and receipts, Coda (Codex Lily) directed by Richard Pemberton; second‑pass audit (CE‑1…CE‑4), Claude Fable 5.1; candidate 3 design, diff, tests and tools, Claude (Anthropic, wave 9, static); execution of all receipts, Red; this independent review and the three review tools, Claude (Anthropic), static only. Licensing as the bundle states (code Apache‑2.0, prose CC‑BY‑4.0 where applicable). Private computational research on a hypothetical linear model; nothing here is a measurement, validation, hardware recommendation or safety statement.