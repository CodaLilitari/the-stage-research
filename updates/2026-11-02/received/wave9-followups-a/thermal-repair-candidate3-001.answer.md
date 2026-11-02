# Candidate 3 — minimal patch on Coda's candidate‑2 `thermal_contract.py`

**Method statement.** Everything below is static reasoning over the verbatim bundle (candidate‑2 source, Coda's tests, Fable's audit, Red's follow‑up tests and receipt, sample plan). I executed nothing and read no file beyond the bundle. Line numbers in the diff were counted by hand against the supplied source (they are consistent with the three anchors in Coda's `REPAIR.diff`: `_finite` at 115, `r2 = …` at 373, `if args.cmd == "validate"` at 947); `apply_patch.py` applies by exact context matching and ignores them, so a miscount cannot corrupt the result. Expected test outcomes are static predictions; Red's execution decides.

Files below (extract mechanically; suggested location `fable_thermal/candidate3/`):

1. `candidate3/candidate3.diff` — the reviewable unified diff (11 hunks) against `fixed/thermal_contract.py`
2. `candidate3/apply_patch.py` — context‑matching applier (stdlib, writes only `--out`)
3. `candidate3/test_candidate3.py` — new unittest module (fails/errors on candidate 2, passes on candidate 3; prints a hash receipt)
4. `candidate3/provenance_receipt.py` — hash/receipt tool closing the audit's provenance items
5. `candidate3/test_tools.py` — unit tests for the two tools
6. `candidate3/REPORT_candidate3.md` — report (threshold justification, expected results, verification steps, credits, open items)

---

FILE: candidate3/candidate3.diff
```diff
--- fixed/thermal_contract.py
+++ candidate3/thermal_contract.py
@@ -1,4 +1,7 @@
 #!/usr/bin/env python3
 # Coda review R1, 2026-11-01: separate repair of the preserved Fable original.
 # Original SHA256: 9986a18f6f208cc1382fe4a7ffe1434584b96f4f1cb8da108d76970cb0114e0d
+# Candidate 3 (Claude, Anthropic; static patch for Red / Richard Pemberton, run stage-red-20261102):
+#   Gauss cross-check cancellation guard, h*A representability boundary, validator notes.  Not executed by author.
+# Candidate 2 SHA256 (patch base): 160410e5cecb4e2408f3b13e42ae5213f12d43216d725859afbfa1e6e4b3a06a
 """
@@ -94,5 +97,37 @@
 DEFAULT_CMP = {"outer_surface_C": 40.0, "internal_node_C": 60.0}
 DEFAULT_NUM = {"energy_abs_tol_W": 1e-10, "energy_rel_tol": 1e-10, "agreement_tol_K": 1e-9}
+
+# Unit roundoff u = 2^-53 of IEEE-754 binary64 (sys.float_info.epsilon is 2^-52).
+_UNIT_ROUNDOFF = sys.float_info.epsilon / 2.0
+# Gauss cross-check guard (candidate 3): gauss_pivot_amplification() bounds the relative
+# rounding error of the eliminated unknown by about 11 u * amplification for the thermal
+# matrix; 16 is the next power of two and leaves room for the closed form's own ~6 u.
+GAUSS_CHECK_ERROR_FACTOR = 16.0
+
+# Acceptance rules tightened after the first T0-HYP-1.0 release.  The schema version string
+# is deliberately unchanged (the output document echoes it and the frozen sample results must
+# stay byte-identical); a configuration that validated under an earlier program version but
+# violates a rule below is now rejected with a message naming the note.  Documentation only;
+# never written to the output document.
+VALIDATOR_NOTES = {
+    "film_equal_across_stacks": (
+        "candidate 2 (Coda): t_film_m must be equal across all stacks because the output "
+        "document lists 'film thickness' under held_equal_across_stacks_per_condition; before "
+        "that repair unequal films were accepted and the document's claim was unenforced (F3)."),
+    "front_conductance_representable": (
+        "candidate 3: for h_W_m2K > 0 (nominal, both assumed-range bounds and every resolved "
+        "condition) h*A must be a finite positive float with a finite reciprocal.  h*A rounding "
+        "to 0 (was ZeroDivisionError, F2a), to a subnormal whose reciprocal overflows (was a "
+        "silent 'front path absent' solution echoing the positive h, CE-3) or to inf (would give "
+        "R_conv = 0 exactly) is a configuration error.  h_W_m2K = 0 remains the documented "
+        "absent-front-path limit."),
+    "gauss_check_availability": (
+        "candidate 3: checks.gauss_vs_closed_form_inverse is null (unavailable), never a "
+        "spurious false, when the pivoted elimination raised (F1) or when its a-priori relative "
+        "rounding bound GAUSS_CHECK_ERROR_FACTOR * u * amplification is >= "
+        "numerics.agreement_tol_K, with amplification = (|d| + |f b|) / |d2| for the Schur "
+        "complement d2 = d - f b (CE-1).  Otherwise the check is computed exactly as before."),
+}
 
 
 class ConfigError(ValueError):
@@ -196,8 +231,9 @@
         for key in ("t_outer_silicone_m", "t_film_m", "t_inner_silicone_m"):
             _require(_finite(s[key]) and s[key] >= 0.0,
                      "stack %r: %s must be finite and >= 0" % (s["stack_id"], key))
     _require(len({s["t_film_m"] for s in stacks}) == 1,
-             "film thickness must be equal across stacks, as asserted by the study contract")
+             "film thickness must be equal across stacks, as asserted by the study contract "
+             "(validator note 'film_equal_across_stacks')")
 
     tp = cfg["thickness_perturbation"]
     _require(_finite(tp["fraction"]) and 0.0 <= tp["fraction"] < 1.0,
@@ -209,6 +245,10 @@
     _require(_finite(b["h_W_m2K"]) and b["h_W_m2K"] >= 0.0,
              "boundaries.h_W_m2K must be finite and >= 0 (0 = front path absent, limiting case only)")
     _require_range("boundaries.h_assumed_range_W_m2K", b["h_assumed_range_W_m2K"], lo_ok=0.0)
+    for where, h in (("boundaries.h_W_m2K", b["h_W_m2K"]),
+                     ("boundaries.h_assumed_range_W_m2K[0]", b["h_assumed_range_W_m2K"][0]),
+                     ("boundaries.h_assumed_range_W_m2K[1]", b["h_assumed_range_W_m2K"][1])):
+        front_convective_resistance_K_W(h, g["area_m2"], where)   # candidate 3: h*A representable
     parse_R_rej(b["R_rej_K_W"])
     _require_range("boundaries.R_rej_assumed_range_K_W", b["R_rej_assumed_range_K_W"], lo_ok=1e-12)
     _require(b["R_rej_blocked_token"] == BLOCKED,
@@ -258,6 +298,32 @@
     if R_K_W == 0.0:
         return math.inf
     return 1.0 / R_K_W          # 1.0 / inf == 0.0 exactly in IEEE arithmetic
+
+
+def front_convective_resistance_K_W(h_W_m2K, area_m2, where="h_W_m2K"):
+    """R_conv = 1/(h A) in K/W with the documented limit h = 0 -> inf (front path absent).
+
+    Configuration boundary (candidate 3): any positive h must give a finite positive R_conv.
+    Otherwise the program would silently reinterpret its input: h*A rounded to 0.0 raised
+    ZeroDivisionError (F2a); a subnormal h*A gave R_conv = inf and the case was solved as
+    "front path absent" while echoing the positive h (CE-3); an overflowed h*A would give
+    R_conv = 0.0 exactly.  All three raise ConfigError here, so library callers and the
+    command line meet the same boundary.  For h > 0 the arithmetic is exactly the former
+    1.0 / (h * A); negative h is rejected by the validator (and here, as unrepresentable).
+    """
+    h = float(h_W_m2K)
+    A = float(area_m2)
+    if h == 0.0:
+        return math.inf
+    hA = h * A
+    R_conv = (1.0 / hA) if hA != 0.0 else math.inf
+    if not (hA > 0.0 and math.isfinite(hA) and math.isfinite(R_conv)):
+        raise ConfigError(
+            "%s = %r with area_m2 = %r gives h*A = %r, which has no finite positive R_conv = "
+            "1/(h*A) in binary64; use exactly 0 for an absent front path "
+            "(validator note 'front_conductance_representable')" % (where, h_W_m2K, area_m2, hA))
+    return R_conv
 
 
 def assemble_resistances(stack, p):
@@ -271,7 +337,7 @@
     R_film = layer_resistance_K_W(t_f, p["k_film"], A)
     R_c_out = p["r_c_outer"] / A
     R_c_in = p["r_c_inner"] / A
-    R_conv = math.inf if p["h"] == 0.0 else 1.0 / (p["h"] * A)
+    R_conv = front_convective_resistance_K_W(p["h"], A)   # same arithmetic; rejects unrepresentable h*A
     R_rej = p["R_rej"]                          # float K/W or math.inf (blocked)
     R_HS = R_in + 0.5 * R_film + R_c_in         # internal: H -> S
     R_SA = 0.5 * R_film + R_c_out + R_out + R_conv   # internal conduction + environmental R_conv
@@ -303,6 +369,31 @@
     x2 = r2b / d2
     x1 = (r1 - b * x2) / a
     return x1, x2
+
+
+def gauss_pivot_amplification(a, b, c, d):
+    """Cancellation amplification of the single elimination step of solve_2x2_gauss.
+
+    After the same pivot choice the Schur complement is d2 = d - f b with f = c / a.  With
+    unit roundoff u, forming d2 from exact a, b, c, d commits at most about u |d2| + u (|d| +
+    3 |f b|) of absolute error (one rounding each in a, f, f b and the subtraction, with the
+    error of d's own formation counted in |d|), so the relative error of d2 and of the
+    eliminated unknown is at most about 3 u * amp + O(u), where
+        amp = (|d| + |f b|) / |d2|   (>= 1).
+    For the thermal matrix (a = G_HS + G_rej, b = c = -G_HS, d = G_HS + G_SA) the pivot never
+    swaps and d2 = G_SA + G_HS G_rej / (G_HS + G_rej) = det / a is formed as the difference of
+    two numbers close to G_HS whenever G_SA and G_rej are both small against G_HS: the exits
+    are then 'lost' in elimination although det > 0 exactly (CE-1).  Returns inf when the
+    computed d2 is 0.0 (the F1 case, where solve_2x2_gauss raises).  Diagnostic only: it
+    never enters any returned temperature or flux.
+    """
+    if abs(c) > abs(a):
+        a, b, c, d = c, d, a, b
+    fb = (c / a) * b
+    d2 = d - fb
+    if d2 == 0.0:
+        return math.inf
+    return (abs(d) + abs(fb)) / abs(d2)
 
 
 def classify_singular(G_HS, G_SA, G_rej, P_body, P_sensor):
@@ -342,6 +433,9 @@
     Unique solution iff det > 0, i.e. at most one conductance is zero (every node reaches
     a boundary).  Closed-form inverse and pivoted elimination are both returned so a
     caller can confirm agreement.  Blocked exits are exact zeros, never large numbers.
+    'gauss_amplification' (candidate 3) is the pivot-cancellation factor of that elimination
+    (see gauss_pivot_amplification); semantic_checks uses it to report the cross-check as
+    unavailable when its a-priori rounding bound reaches the agreement tolerance.
     """
     for name, G in (("G_HS", G_HS), ("G_SA", G_SA), ("G_rej", G_rej)):
         if math.isnan(G) or G < 0.0:
@@ -373,14 +467,17 @@
     r2 = P_sensor + G_SA * T_amb
     T_H = (d * r1 - b * r2) / det            # = ((G_HS+G_SA) r1 + G_HS r2) / det
     T_S = (-c * r1 + a * r2) / det           # = (G_HS r1 + (G_HS+G_rej) r2) / det
     try:
         T_H_g, T_S_g = solve_2x2_gauss(a, b, c, d, r1, r2)
+        amp = gauss_pivot_amplification(a, b, c, d)
     except ZeroDivisionError:
         # det > 0 above, but floating-point elimination can lose a tiny exit.
         # Keep the closed-form result and explicitly mark the check unavailable.
         T_H_g = T_S_g = None
+        amp = math.inf
     return {"status": "solved", "T_H": T_H, "T_S": T_S,
-            "T_H_gauss": T_H_g, "T_S_gauss": T_S_g, "det_W2_K2": det}
+            "T_H_gauss": T_H_g, "T_S_gauss": T_S_g, "det_W2_K2": det,
+            "gauss_amplification": amp}
 
 
 # ----------------------------------------------------------------------------
@@ -433,8 +530,13 @@
     checks["energy_balance_within_tolerance"] = res["energy_check_pass"]
     checks["sensor_flux_discontinuity_equals_P_sensor"] = _close(
         res["Q_front_W"] - res["Q_HS_W"], p["P_sensor"], tol)
-    if sol["T_H_gauss"] is None:
-        checks["gauss_vs_closed_form_inverse"] = None
+    amp = sol.get("gauss_amplification")          # None when no elimination was performed
+    if sol["T_H_gauss"] is None:
+        checks["gauss_vs_closed_form_inverse"] = None          # elimination raised (F1)
+    elif amp is not None and GAUSS_CHECK_ERROR_FACTOR * _UNIT_ROUNDOFF * amp >= tol:
+        # Cancellation guard (candidate 3): the elimination's a-priori rounding bound reaches
+        # the agreement tolerance, so a disagreement could not be charged to the closed form.
+        checks["gauss_vs_closed_form_inverse"] = None          # unavailable, not False (CE-1)
     else:
         checks["gauss_vs_closed_form_inverse"] = (_close(sol["T_H_gauss"], sol["T_H"], tol)
                                                   and _close(sol["T_S_gauss"], sol["T_S"], tol))
@@ -490,6 +592,8 @@
         raise ConfigError("condition %r: r_c and h must be >= 0" % cond.get("condition_id"))
     if p["t_scale_inner"] <= 0.0 or p["t_scale_outer"] <= 0.0:
         raise ConfigError("condition %r: thickness scale must be > 0" % cond.get("condition_id"))
+    front_convective_resistance_K_W(p["h"], p["area_m2"],           # candidate 3: h*A representable
+                                    "condition %r: h" % cond.get("condition_id"))
     return p
 
 
```

FILE: candidate3/apply_patch.py
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply a unified diff by exact context matching; hunk line numbers (@@ ...) are ignored.

Usage:
  python3 apply_patch.py --patch candidate3.diff --base fixed/thermal_contract.py \
                         --out candidate3/thermal_contract.py [--force]

Each hunk's "old" text (context lines plus '-' lines) must occur exactly once at or after
the end of the previous hunk; otherwise the tool exits 1 and writes nothing.  Standard
library only; deterministic; no network; the only file written is --out (refused if it
exists, unless --force).  CRLF input is normalised to LF with a warning.  Prints the hunk
count, line counts and the SHA-256 of the written file as a receipt.
"""
import argparse
import hashlib
import os
import sys


def parse_hunks(text):
    hunks, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if cur is None and (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        if line.startswith("@@"):
            cur = {"old": [], "new": []}
            hunks.append(cur)
            continue
        if cur is None or line.startswith("\\"):      # preamble or "\ No newline at end of file"
            continue
        tag, body = (line[0], line[1:]) if line else (" ", "")
        if tag == " ":
            cur["old"].append(body)
            cur["new"].append(body)
        elif tag == "-":
            cur["old"].append(body)
        elif tag == "+":
            cur["new"].append(body)
        else:
            raise ValueError("unrecognised diff line: %r" % raw)
    if not hunks:
        raise ValueError("no hunks found in patch")
    return hunks


def apply_hunks(lines, hunks):
    out, pos = list(lines), 0
    for i, h in enumerate(hunks, 1):
        old, n = h["old"], len(h["old"])
        hits = [j for j in range(pos, len(out) - n + 1) if out[j:j + n] == old]
        if len(hits) != 1:
            raise ValueError("hunk %d: expected exactly one context match at/after line %d, found %d"
                             % (i, pos + 1, len(hits)))
        j = hits[0]
        out[j:j + n] = h["new"]
        pos = j + len(h["new"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="context-matching unified-diff applier")
    ap.add_argument("--patch", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    with open(args.patch, "r", encoding="utf-8", newline="") as fh:
        patch_text = fh.read()
    with open(args.base, "r", encoding="utf-8", newline="") as fh:
        base_text = fh.read()
    if "\r\n" in base_text:
        sys.stderr.write("warning: CRLF line endings in base normalised to LF\n")
        base_text = base_text.replace("\r\n", "\n")
    had_nl = base_text.endswith("\n")
    lines = base_text.split("\n")
    if had_nl:
        lines.pop()
    try:
        new_lines = apply_hunks(lines, parse_hunks(patch_text))
    except ValueError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    if os.path.exists(args.out) and not args.force:
        sys.stderr.write("error: refusing to overwrite existing %r (use --force)\n" % args.out)
        return 1
    data = "\n".join(new_lines) + ("\n" if had_nl else "")
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    print("applied %d hunk(s): %d -> %d lines; sha256(out) = %s"
          % (len(parse_hunks(patch_text)), len(lines), len(new_lines),
             hashlib.sha256(data.encode("utf-8")).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: candidate3/test_candidate3.py
```python
# SPDX-License-Identifier: Apache-2.0
"""Candidate 3 regression tests for thermal_contract.py (Claude, Anthropic; static author, not executed).

THERMAL_CANDIDATE   path of the module under test (default ../fixed/thermal_contract.py)
THERMAL_SAMPLE_PLAN path of the sample plan      (default ../original/sample_plan.json)
THERMAL_TMP         optional parent directory for temporary files

Against candidate 2 every test in Candidate3MustFailBefore is expected to FAIL or ERROR and every
test in RegressionControls to pass; against candidate 3 all tests pass.  setUpModule prints a
receipt line binding the SHA-256 of the executed code, this file and the sample plan.
"""
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = Path(os.environ.get("THERMAL_CANDIDATE", str(HERE.parent / "fixed" / "thermal_contract.py"))).resolve()
PLAN = Path(os.environ.get("THERMAL_SAMPLE_PLAN", str(HERE.parent / "original" / "sample_plan.json"))).resolve()
TMP_PARENT = os.environ.get("THERMAL_TMP") or None
CANDIDATE_2_SHA256 = "160410e5cecb4e2408f3b13e42ae5213f12d43216d725859afbfa1e6e4b3a06a"

_spec = importlib.util.spec_from_file_location("thermal_under_test", str(CODE))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
BASE = json.loads(PLAN.read_text(encoding="utf-8"))


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setUpModule():
    print("\nreceipt: code=%s code_sha256=%s" % (CODE, _sha256(CODE)))
    print("receipt: test_sha256=%s sample_plan_sha256=%s python=%s"
          % (_sha256(__file__), _sha256(PLAN), sys.version.split()[0]))


def run_cli(cfg):
    """Run main(['run', ...]) on cfg in a temporary directory; return (rc, stderr, document or None)."""
    with tempfile.TemporaryDirectory(dir=TMP_PARENT) as tmp:
        inp, out = Path(tmp) / "in.json", Path(tmp) / "out.json"
        inp.write_text(json.dumps(cfg), encoding="utf-8")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = m.main(["run", "--config", str(inp), "--out", str(out)])
        doc = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        return rc, err.getvalue(), doc


def ce1_fixture():
    """Fable CE-1, executed by Red: closed form T_S = 5.100000000000024e15, Gauss 5.742e15 (+12.6 %)."""
    sol = m.solve_two_node(5.0, 0.0, 1e-15, 5.0, 0.1, 25.0, 25.0)
    R = {"R_HS_K_W": 0.2, "R_SA_K_W": math.inf, "R_rej_K_W": 1e15, "R_conv_K_W": math.inf}
    p = {"area_m2": 0.01, "P_body": 5.0, "P_sensor": 0.1, "T_amb": 25.0, "T_res": 25.0}
    res = m.reconstruct(sol, R, p, m.DEFAULT_CMP, m.DEFAULT_NUM)
    return sol, R, p, res


class _Base(unittest.TestCase):
    def assert_config_error(self, fn, *args, **kw):
        try:
            fn(*args, **kw)
        except m.ConfigError as exc:
            return str(exc)
        except Exception as exc:                      # wrong type is a failure, not an error
            self.fail("expected ConfigError, got %s: %s" % (type(exc).__name__, exc))
        self.fail("expected ConfigError, nothing was raised")


class Candidate3MustFailBefore(_Base):
    """Each test here is expected to fail or error against candidate 2 (reason in the docstring)."""

    def test_CE1_cross_check_unavailable_not_false(self):
        """before: checks['gauss_vs_closed_form_inverse'] is False on a correct closed form."""
        sol, R, p, res = ce1_fixture()
        self.assertEqual(sol["status"], "solved")
        self.assertAlmostEqual(sol["T_S"] / 5.1e15, 1.0, delta=1e-12)
        checks = m.semantic_checks(res, sol, R, p, 1e-9)
        self.assertIsNone(checks["gauss_vs_closed_form_inverse"])
        self.assertTrue(checks["energy_balance_within_tolerance"])

    def test_guard_threshold_tracks_agreement_tolerance(self):
        """before: the tol = 1e-9 and tol = 1.0 legs report False / True instead of None."""
        sol, R, p, res = ce1_fixture()
        # amplification ~ 1.1e16 -> a-priori bound 16 u amp ~ 20 K/K: unavailable below that, computed above.
        self.assertIsNone(m.semantic_checks(res, sol, R, p, 1e-9)["gauss_vs_closed_form_inverse"])
        self.assertIsNone(m.semantic_checks(res, sol, R, p, 1.0)["gauss_vs_closed_form_inverse"])
        self.assertIs(m.semantic_checks(res, sol, R, p, 1e3)["gauss_vs_closed_form_inverse"], True)

    def test_solution_reports_pivot_amplification(self):
        """before: KeyError 'gauss_amplification'."""
        sol = ce1_fixture()[0]
        self.assertGreater(sol["gauss_amplification"], 1e15)
        ctrl = m.solve_two_node(5.0, 0.5, 0.25, 5.0, 0.1, 25.0, 25.0)   # Coda's control: d2 ~ 0.738
        self.assertTrue(1.0 <= ctrl["gauss_amplification"] < 100.0, ctrl["gauss_amplification"])
        exact0 = m.solve_two_node(5.0, 0.0, 1e-17, 5.0, 0.1, 25.0, 25.0)  # F1: elimination raised
        self.assertIsNone(exact0["T_H_gauss"])
        self.assertEqual(exact0["gauss_amplification"], math.inf)

    def test_sample_plan_never_triggers_guard(self):
        """before: AttributeError / KeyError.  Static expectation: max amplification ~55 in the sample."""
        tol = BASE["numerics"]["agreement_tol_K"]
        n = 0
        for cond in m.build_shared_conditions(BASE):
            for stack in BASE["stacks"]:
                p = m.resolve_parameters(BASE, cond)
                R = m.assemble_resistances(stack, p)
                sol = m.solve_two_node(m.conductance_W_K(R["R_HS_K_W"]), m.conductance_W_K(R["R_SA_K_W"]),
                                       m.conductance_W_K(R["R_rej_K_W"]),
                                       p["P_body"], p["P_sensor"], p["T_amb"], p["T_res"])
                self.assertEqual(sol["status"], "solved")
                amp = sol["gauss_amplification"]
                self.assertTrue(1.0 <= amp < 1e3, amp)
                self.assertLess(m.GAUSS_CHECK_ERROR_FACTOR * m._UNIT_ROUNDOFF * amp, 1e-3 * tol)
                case = m.run_case(BASE, stack, cond)
                self.assertIs(case["checks"]["gauss_vs_closed_form_inverse"], True)
                n += 1
        self.assertEqual(n, 108)

    def test_hA_underflow_to_zero_is_ConfigError_everywhere(self):
        """before: validate_config admits h = 5e-324; resolve_parameters admits it; assembly raises
        ZeroDivisionError; CLI message is 'float division by zero' (Coda F2a fix) without h_W_m2K."""
        cfg = copy.deepcopy(BASE)
        cfg["boundaries"]["h_W_m2K"] = 5e-324
        msg = self.assert_config_error(m.validate_config, cfg)
        self.assertIn("boundaries.h_W_m2K", msg)
        self.assertIn("front_conductance_representable", msg)
        cond = {"condition_id": "x", "group": "g", "P_body": 5.0, "h": 5e-324}
        self.assertIn("condition 'x'", self.assert_config_error(m.resolve_parameters, BASE, cond))
        self.assert_config_error(m.assemble_resistances, m._ref_stack(), m._ref_params(h=5e-324))
        rc, err, doc = run_cli(cfg)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("error:"), err)
        self.assertIn("h_W_m2K", err)
        self.assertIsNone(doc)

    def test_CE3_subnormal_hA_rejected_not_reclassified(self):
        """before (Red receipt): rc 0, output written, case silently solved as front path absent."""
        cfg = copy.deepcopy(BASE)
        cfg["boundaries"]["h_W_m2K"] = 1e-320
        self.assertIn("front_conductance_representable", self.assert_config_error(m.validate_config, cfg))
        rc, err, doc = run_cli(cfg)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("error:"), err)
        self.assertIsNone(doc)

    def test_hA_overflow_rejected(self):
        """before: admitted; R_conv would be exactly 0.0 (h*A = inf)."""
        cfg = copy.deepcopy(BASE)
        cfg["geometry"]["area_m2"] = 1e300
        cfg["boundaries"]["h_W_m2K"] = 1e10
        self.assertIn("h*A = inf", self.assert_config_error(m.validate_config, cfg))
        self.assert_config_error(m.front_convective_resistance_K_W, 1e10, 1e300)

    def test_h_range_bounds_checked_at_validation(self):
        """before: a subnormal lower h range bound is admitted and runs the C_h_lo / D_h_lo conditions
        with R_conv = inf."""
        cfg = copy.deepcopy(BASE)
        cfg["boundaries"]["h_assumed_range_W_m2K"] = [1e-320, 15.0]
        self.assertIn("h_assumed_range_W_m2K[0]", self.assert_config_error(m.validate_config, cfg))

    def test_h_zero_remains_absent_front_path_limit(self):
        """before: AttributeError (helper absent).  Also asserts the in-domain arithmetic is unchanged."""
        self.assertEqual(m.front_convective_resistance_K_W(0.0, 0.01), math.inf)
        self.assertEqual(m.front_convective_resistance_K_W(8.0, 0.01), 1.0 / (8.0 * 0.01))
        self.assertEqual(m.front_convective_resistance_K_W(3, 1), 1.0 / 3.0)         # int inputs
        self.assertEqual(m.assemble_resistances(m._ref_stack(), m._ref_params(h=0.0))["R_conv_K_W"], math.inf)
        cfg = copy.deepcopy(BASE)
        cfg["boundaries"]["h_W_m2K"] = 0.0
        m.validate_config(cfg)                                                       # still admitted

    def test_validator_notes_and_messages(self):
        """before: AttributeError VALIDATOR_NOTES; film message has no note name."""
        for key in ("film_equal_across_stacks", "front_conductance_representable", "gauss_check_availability"):
            self.assertIn(key, m.VALIDATOR_NOTES)
            self.assertIsInstance(m.VALIDATOR_NOTES[key], str)
        self.assertIn("candidate 2", m.VALIDATOR_NOTES["film_equal_across_stacks"])
        cfg = copy.deepcopy(BASE)
        cfg["stacks"][1]["t_film_m"] = 1e-4
        self.assertIn("film_equal_across_stacks", self.assert_config_error(m.validate_config, cfg))
        self.assertEqual(m.SCHEMA_VERSION, "T0-HYP-1.0")                               # deliberately unchanged
        self.assertEqual(m.GAUSS_CHECK_ERROR_FACTOR * m._UNIT_ROUNDOFF, 16.0 * 2.0 ** -53)

    def test_header_names_patch_base_hash(self):
        """before: the candidate 2 file does not name its own hash."""
        text = CODE.read_text(encoding="utf-8")
        self.assertIn(CANDIDATE_2_SHA256, text)
        self.assertIn("Candidate 3", text)


class RegressionControls(_Base):
    """Expected to pass against candidate 2 and candidate 3 alike."""

    def test_sample_validates_runs_and_all_checks_hold(self):
        m.validate_config(copy.deepcopy(BASE))
        rc, err, doc = run_cli(copy.deepcopy(BASE))
        self.assertEqual(rc, 0, err)
        self.assertEqual(doc["summary"]["n_cases"], 108)
        self.assertEqual(doc["summary"]["n_solved"], 108)                 # static expectation (det > 0 everywhere)
        self.assertEqual(doc["summary"]["n_all_semantic_checks_pass"], 108)
        self.assertTrue(all(c["checks"]["gauss_vs_closed_form_inverse"] is True for c in doc["cases"]))

    def test_candidate2_regressions_still_hold(self):
        s = m.solve_two_node(5.0, 0.0, 1e-17, 5.0, 0.1, 25.0, 25.0)        # F1 exact-zero case
        self.assertEqual(s["status"], "solved")
        self.assertIsNone(s["T_H_gauss"])
        cfg = copy.deepcopy(BASE)
        cfg["stacks"][1]["t_film_m"] = 1e-4                               # F3 enforcement
        self.assert_config_error(m.validate_config, cfg)
        cfg = copy.deepcopy(BASE)
        cfg["boundaries"]["h_W_m2K"] = 5e-324                             # F2a clean CLI exit
        rc, err, doc = run_cli(cfg)
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("error:"))
        self.assertIsNone(doc)

    def test_well_conditioned_cross_check_is_computed_and_true(self):
        s = m.solve_two_node(5.0, 0.5, 0.25, 5.0, 0.1, 25.0, 25.0)
        self.assertIsNotNone(s["T_H_gauss"])
        self.assertAlmostEqual(s["T_H_gauss"], s["T_H"], delta=1e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

FILE: candidate3/provenance_receipt.py
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Hash receipt for the thermal repair bundle (candidate 3, audit item 7.2).

Usage:
  python3 provenance_receipt.py --out receipt.json [--force] PATH... \
      [--expect PATH=SHA256_OR_PREFIX]... [--drop-lines-compare A B 2,3]...

* Every PATH (a file) is recorded with size and SHA-256; missing files are recorded as such.
* --expect records whether the actual hash of PATH starts with the given hex string (full
  hashes or the 8-char prefixes quoted in the audit).
* --drop-lines-compare A B LINES records whether file A with the 1-based LINES removed is
  byte-identical to file B (tests the audit's inference that before/thermal_contract.py =
  pristine original + two header comment lines at lines 2-3).
Standard library only; no network; writes only --out.  Exit 1 if any expectation failed.
"""
import argparse
import hashlib
import json
import os
import platform
import sys


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def drop_lines(data, lines):
    parts = data.split(b"\n")                        # keeps a trailing b"" when data ends with newline
    return b"\n".join(p for i, p in enumerate(parts, 1) if i not in lines)


def build_receipt(paths, expects, compares):
    receipt = {"tool": "provenance_receipt.py (candidate 3)", "python": platform.python_version(),
               "platform": platform.platform(), "files": {}, "expectations": [], "drop_lines_compare": []}
    for p in paths:
        if os.path.isfile(p):
            data = read(p)
            receipt["files"][p] = {"size": len(data), "sha256": sha256_bytes(data)}
        else:
            receipt["files"][p] = {"missing": True}
    ok = True
    for e in expects:
        path, _, expected = e.partition("=")
        expected = expected.lower()
        actual = receipt["files"].get(path, {}).get("sha256")
        if actual is None and os.path.isfile(path):
            actual = sha256_bytes(read(path))
        status = "missing" if actual is None else ("match" if actual.startswith(expected) else "MISMATCH")
        ok = ok and status == "match"
        receipt["expectations"].append({"path": path, "expected_prefix": expected, "actual": actual,
                                        "status": status})
    for a, b, lines in compares:
        entry = {"a": a, "b": b, "dropped_lines_of_a": lines}
        if os.path.isfile(a) and os.path.isfile(b):
            drop = {int(x) for x in lines.split(",") if x.strip()}
            da, db = drop_lines(read(a), drop), read(b)
            entry.update({"identical": da == db, "sha256_a_dropped": sha256_bytes(da), "sha256_b": sha256_bytes(db)})
            if da != db:
                la, lb = da.split(b"\n"), db.split(b"\n")
                first = next((i for i, (x, y) in enumerate(zip(la, lb), 1) if x != y), min(len(la), len(lb)) + 1)
                entry["first_differing_line_after_drop"] = first
        else:
            entry["identical"] = None
            entry["missing"] = [p for p in (a, b) if not os.path.isfile(p)]
        receipt["drop_lines_compare"].append(entry)
    return receipt, ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="SHA-256 receipt with expectations and header-strip comparison")
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--expect", action="append", default=[], metavar="PATH=HEX")
    ap.add_argument("--drop-lines-compare", action="append", nargs=3, default=[], metavar=("A", "B", "LINES"))
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    receipt, ok = build_receipt(args.paths, args.expect, args.drop_lines_compare)
    if os.path.exists(args.out) and not args.force:
        sys.stderr.write("error: refusing to overwrite existing %r (use --force)\n" % args.out)
        return 1
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({k: receipt[k] for k in ("expectations", "drop_lines_compare")}, indent=1, sort_keys=True))
    print("wrote %s (%s)" % (args.out, "all expectations met" if ok else "EXPECTATION FAILURE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

FILE: candidate3/test_tools.py
```python
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for apply_patch.py and provenance_receipt.py (candidate 3 tooling)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, str(HERE / (name + ".py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ap = load("apply_patch")
pr = load("provenance_receipt")

BASE = ["a", "b", "c", "", "d", "e", "f", "g", "h"]
# Deliberately wrong @@ numbers; a blank context line appears once as " " and once as "".
PATCH = ("--- x\n+++ y\n@@ -100,3 +200,4 @@\n a\n b\n+B2\n c\n@@ -1,5 +1,5 @@\n \n d\n-e\n+E\n f\n")


class ApplyPatchTests(unittest.TestCase):
    def test_applies_by_context_ignoring_line_numbers(self):
        hunks = ap.parse_hunks(PATCH)
        self.assertEqual(len(hunks), 2)
        self.assertEqual(ap.apply_hunks(BASE, hunks), ["a", "b", "B2", "c", "", "d", "E", "f", "g", "h"])

    def test_rejects_ambiguous_or_missing_context(self):
        hunks = ap.parse_hunks("@@ -1 +1 @@\n-zzz\n+yyy\n")
        with self.assertRaises(ValueError):
            ap.apply_hunks(BASE, hunks)
        hunks = ap.parse_hunks("@@ -1 +1 @@\n-g\n+G\n")
        with self.assertRaises(ValueError):
            ap.apply_hunks(["g", "g"], hunks)

    def test_main_writes_out_and_preserves_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, patch, out = Path(tmp) / "base.txt", Path(tmp) / "p.diff", Path(tmp) / "out.txt"
            base.write_text("\n".join(BASE) + "\n", encoding="utf-8")
            patch.write_text(PATCH, encoding="utf-8")
            self.assertEqual(ap.main(["--patch", str(patch), "--base", str(base), "--out", str(out)]), 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "a\nb\nB2\nc\n\nd\nE\nf\ng\nh\n")
            self.assertEqual(ap.main(["--patch", str(patch), "--base", str(base), "--out", str(out)]), 1)


class ProvenanceReceiptTests(unittest.TestCase):
    def test_drop_lines_and_expectations(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.py", Path(tmp) / "b.py"
            b.write_text("#!/usr/bin/env python3\nx = 1\n", encoding="utf-8")
            a.write_text("#!/usr/bin/env python3\n# h1\n# h2\nx = 1\n", encoding="utf-8")
            sha_b = pr.sha256_bytes(b.read_bytes())
            receipt, ok = pr.build_receipt([str(a), str(b), str(Path(tmp) / "none")],
                                           ["%s=%s" % (b, sha_b[:8]), "%s=deadbeef" % a],
                                           [(str(a), str(b), "2,3")])
            self.assertFalse(ok)
            self.assertEqual([e["status"] for e in receipt["expectations"]], ["match", "MISMATCH"])
            self.assertTrue(receipt["drop_lines_compare"][0]["identical"])
            self.assertTrue(receipt["files"][str(Path(tmp) / "none")]["missing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

FILE: candidate3/REPORT_candidate3.md
```markdown
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

```sh
cd fable_thermal
python3 candidate3/apply_patch.py --patch candidate3/candidate3.diff \
        --base fixed/thermal_contract.py --out candidate3/thermal_contract.py
diff -u fixed/thermal_contract.py candidate3/thermal_contract.py > candidate3/candidate3.regenerated.diff
# (regenerated diff should differ from candidate3.diff at most in @@ numbers/header paths)
python3 -m unittest -v candidate3.test_tools
THERMAL_CANDIDATE=fixed/thermal_contract.py      python3 -m unittest -v candidate3.test_candidate3   # expect 8 FAIL + 3 ERROR + 3 ok
THERMAL_CANDIDATE=candidate3/thermal_contract.py python3 -m unittest -v candidate3.test_candidate3   # expect 14 ok
python3 fixed/thermal_contract.py      run --config original/sample_plan.json --out execution/c2_results.json > execution/c2_stdout.txt
python3 candidate3/thermal_contract.py run --config original/sample_plan.json --out execution/c3_results.json > execution/c3_stdout.txt
cmp execution/c2_results.json execution/c3_results.json && cmp execution/c2_stdout.txt execution/c3_stdout.txt
sha256sum execution/c3_results.json      # expect 913bfd2c44d0e04a44d8f45ad455982221b7582fb4624ed0883365e539c7730e (Coda's fixed_results.json)
python3 fixed/thermal_contract.py validate > execution/c2_validate.txt; python3 candidate3/thermal_contract.py validate > execution/c3_validate.txt
cmp execution/c2_validate.txt execution/c3_validate.txt
python3 candidate3/provenance_receipt.py --out candidate3/receipt_hashes.json \
   original/thermal_contract.py before/thermal_contract.py fixed/thermal_contract.py candidate3/thermal_contract.py \
   test_audit.py review.py candidate3/test_candidate3.py candidate3/candidate3.diff \
   --expect fixed/thermal_contract.py=160410e5cecb4e2408f3b13e42ae5213f12d43216d725859afbfa1e6e4b3a06a \
   --expect test_audit.py=22528f69ecc198b0e88c2c5da5505d85aa09e3c8e61553c01254d9ae6cc8d3ae \
   --expect original/thermal_contract.py=9986a18f6f208cc1382fe4a7ffe1434584b96f4f1cb8da108d76970cb0114e0d \
   --expect before/thermal_contract.py=ce6d2fe1 --expect review.py=c57d20f8 \
   --drop-lines-compare before/thermal_contract.py original/thermal_contract.py 2,3
```
Adjust the `original/`, `before/`, `review.py` paths to the actual layout (not in my bundle).
Running Coda's `test_audit.py` against candidate 3 requires a tree copy with
`fixed/thermal_contract.py` replaced, since it hardcodes that path.

## 6. Left open / not implemented

* Receipts only Red can attach: the validate 13/13 receipt, the first failing independent
  receipt, and the regenerated diff + hash of `candidate3/thermal_contract.py`.
* Audit 7.3 (exception type in CLI message), schema version bump, `v14` self-check for the new
  rules (would change validate-mode text), RHS-cancellation guard, CE‑2 — deferred.
* Line numbers in `candidate3.diff` were hand-counted; `apply_patch.py` does not rely on them.

## 7. Credit

Original implementation and recovered static audit: Claude Fable 5.1. Candidate 2 repair,
harness, receipts, report: Coda (Codex Lily), directed by Richard Pemberton. Second-pass audit
(F1–F3 confirmation, CE‑1…CE‑4, the guard and ConfigError suggestions): Claude Fable 5.1.
Execution of all receipts: Red. Candidate 3 design, diff, tests and tools: Claude (Anthropic),
static only. Licensing as the bundle states (code Apache‑2.0, prose CC‑BY‑4.0 where applicable).
```

---

## Summary for Red

- **Apply:** `apply_patch.py` (context-matched; 11 hunks). Regenerate the authoritative diff with `diff -u`.
- **Byte identity:** `cmp` the candidate‑2 and candidate‑3 runs of `original/sample_plan.json` in the same sandbox and check the 913bfd2c… hash; also `cmp` the `validate` outputs. §3 of the report gives the static argument.
- **Tests:** `test_candidate3.py` — against candidate 2 expect 8 FAIL + 3 ERROR (listed) + 3 controls ok; against candidate 3 expect 14/14. Coda 8/8 and Red's follow‑up should pass except `test_CE3_subnormal_hA_silent`, which must now fail (rc 1) by design.
- **Provenance:** run `provenance_receipt.py` with the paths/expectations in §5; it closes the ce6d2fe1/9986a18f link mechanically and binds `review.py`'s hash. Receipts I cannot produce are listed in §6.