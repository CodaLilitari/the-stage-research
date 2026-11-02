# SPDX-License-Identifier: MIT
"""Self-tests for the GW-ASYNC0 model checker: seeded bugs must be found, traces must replay,
runs must be deterministic. Run: python -m unittest gateway_modelcheck.tests.test_checker"""
from __future__ import annotations

from dataclasses import replace
import unittest

from gateway_modelcheck import checker, model
from gateway_modelcheck.checker import (INV_NO_DOUBLE_DISPATCH, INV_NO_FALSE_OUTCOME,
                                        INV_RESTORE_REJECTS_INCONSISTENT, INV_STOP_LATCH,
                                        check, replay, report_json, state_violations)
from gateway_modelcheck.model import (EXPECTED_VIOLATIONS, INITIAL, TAMPER_KINDS, VARIANTS,
                                      Config, Gw, consistency_issues, successors)

BUG_DEPTH = 8
BASELINE_DEPTH = 9


class BaselineTests(unittest.TestCase):
    def test_clarified_baseline_has_no_violation(self):
        r = check(VARIANTS['clarified_baseline'], BASELINE_DEPTH, variant='clarified_baseline')
        self.assertFalse(r.truncated)
        self.assertEqual({}, r.counterexamples, checker.format_report(r))
        self.assertGreater(r.states_explored, 100)

    def test_relay_only_baseline_has_no_violation(self):
        r = check(VARIANTS['clarified_relay_only'], BASELINE_DEPTH, variant='clarified_relay_only')
        self.assertEqual({}, r.counterexamples, checker.format_report(r))

    def test_baseline_reaches_every_lifecycle_status(self):
        # Coverage sanity: the model must actually visit all six design states plus the two others.
        seen = set()
        frontier = [INITIAL]
        parent = {INITIAL}
        cfg = VARIANTS['clarified_baseline']
        for _ in range(BUG_DEPTH):
            nxt = []
            for s in frontier:
                for _label, t in successors(s, cfg):
                    for g in (t.mem, t.dur):
                        if g is not None:
                            seen.update(r[3] for r in g.receipts)
                    if t not in parent:
                        parent.add(t)
                        nxt.append(t)
            frontier = nxt
        for status in (model.ADMITTED, model.DISPATCHED, model.VERIFIED, model.FAILED,
                       model.CANCELLED, model.UNKNOWN, model.REJECTED, model.STOP_RECEIPT):
            self.assertIn(status, seen)


class SeededBugTests(unittest.TestCase):
    def test_each_seeded_bug_is_detected_under_its_expected_invariant(self):
        for name, cfg in sorted(VARIANTS.items()):
            if not name.startswith('bug_'):
                continue
            with self.subTest(variant=name):
                r = check(cfg, BUG_DEPTH, variant=name)
                for inv in EXPECTED_VIOLATIONS[name]:
                    self.assertIn(inv, r.counterexamples, checker.format_report(r))

    def test_as_written_readings_fail_as_predicted(self):
        for name in ('as_written_nondurable_dispatch_mark', 'as_written_blind_unknown_persist',
                     'as_written_reread_without_latch_merge', 'as_written_weak_restore_validation'):
            with self.subTest(variant=name):
                r = check(VARIANTS[name], BUG_DEPTH, variant=name)
                for inv in EXPECTED_VIOLATIONS[name]:
                    self.assertIn(inv, r.counterexamples, checker.format_report(r))

    def test_nondurable_mark_counterexample_is_a_crash_replay(self):
        r = check(VARIANTS['as_written_nondurable_dispatch_mark'], BUG_DEPTH)
        ce = r.counterexamples[INV_NO_DOUBLE_DISPATCH]
        self.assertLessEqual(ce.length, 8)
        self.assertIn('crash', ce.trace)
        self.assertEqual(2, sum(1 for l in ce.trace if l == 'mark_dispatched'))

    def test_blind_unknown_persist_rolls_back_a_committed_transition(self):
        r = check(VARIANTS['as_written_blind_unknown_persist'], BUG_DEPTH)
        ce = r.counterexamples[INV_NO_FALSE_OUTCOME]
        self.assertLessEqual(ce.length, 6)
        self.assertEqual('persist_unknown_blind', ce.trace[-1])
        self.assertIn('commit_ambiguous(replaced=True)', ce.trace)

    def test_latch_merge_finding_needs_api_interleaving(self):
        cfg = replace(VARIANTS['as_written_reread_without_latch_merge'], api_interleaving=False)
        r = check(cfg, BUG_DEPTH)
        self.assertNotIn(INV_STOP_LATCH, r.counterexamples)

    def test_weak_restore_accepts_a_dangling_active_identity(self):
        r = check(VARIANTS['as_written_weak_restore_validation'], 3)
        ce = r.counterexamples[INV_RESTORE_REJECTS_INCONSISTENT]
        self.assertEqual(2, ce.length)
        self.assertEqual('begin', ce.trace[-1])


class TraceAndDeterminismTests(unittest.TestCase):
    def test_every_reported_trace_replays_to_the_recorded_state(self):
        for name, cfg in sorted(VARIANTS.items()):
            r = check(cfg, BUG_DEPTH, variant=name)
            for inv, ce in r.counterexamples.items():
                with self.subTest(variant=name, invariant=inv):
                    final, viol = replay(cfg, ce.trace)
                    self.assertEqual(ce.final_digest, checker.state_digest(final))
                    self.assertIn(inv, {i for i, _ in viol})

    def test_runs_are_deterministic(self):
        a = report_json([check(VARIANTS[n], 6, variant=n) for n in sorted(VARIANTS)])
        b = report_json([check(VARIANTS[n], 6, variant=n) for n in sorted(VARIANTS)])
        self.assertEqual(a, b)

    def test_depth_bound_is_respected(self):
        r = check(VARIANTS['as_written_nondurable_dispatch_mark'], 5)
        self.assertNotIn(INV_NO_DOUBLE_DISPATCH, r.counterexamples)
        for ce in r.counterexamples.values():
            self.assertLessEqual(ce.length, 5)

    def test_state_cap_truncates(self):
        r = check(VARIANTS['clarified_baseline'], 12, max_states=50)
        self.assertTrue(r.truncated)
        self.assertLessEqual(r.states_explored, 50)


class ConsistencyPredicateTests(unittest.TestCase):
    def test_initial_state_is_consistent(self):
        self.assertEqual([], consistency_issues(Gw(), ()))

    def test_every_tamper_kind_is_inconsistent(self):
        for kind in TAMPER_KINDS:
            with self.subTest(kind=kind):
                t = model._tamper(INITIAL, kind)
                self.assertTrue(consistency_issues(t.dur, t.dur_sim))

    def test_full_restore_rejects_every_tamper_kind_without_loading(self):
        cfg = VARIANTS['clarified_baseline']
        for kind in TAMPER_KINDS:
            with self.subTest(kind=kind):
                final, viol = replay(cfg, ['tamper(%s)' % kind, 'begin'])
                self.assertEqual('rejected_state', final.phase)
                self.assertIsNone(final.mem)
                self.assertEqual([], viol)

    def test_state_violation_detects_false_verified(self):
        g = Gw(seq=1, tick=1, obs=1).put('a', 'move', 0, model.VERIFIED)
        s = replace(INITIAL, dur=g, dur_sim=())
        self.assertTrue(any(i == INV_NO_FALSE_OUTCOME for i, _ in state_violations(s)))


if __name__ == '__main__':
    unittest.main()
