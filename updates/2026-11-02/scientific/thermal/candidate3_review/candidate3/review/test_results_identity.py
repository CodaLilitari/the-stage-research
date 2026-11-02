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
