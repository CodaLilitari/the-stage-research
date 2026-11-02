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
