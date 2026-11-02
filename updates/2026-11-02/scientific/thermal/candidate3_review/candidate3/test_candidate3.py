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
