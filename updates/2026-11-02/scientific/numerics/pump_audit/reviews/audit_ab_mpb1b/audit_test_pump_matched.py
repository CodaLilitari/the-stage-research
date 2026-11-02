# SPDX-License-Identifier: Apache-2.0
"""Discriminating audit tests for AB-MPB1B: pump contract, contrasts and Pareto logic.

Task pump-matched-audit-001 for The Stage. Author: Claude (Anthropic), bounded contributor
coordinated by Red for Richard Pemberton. Audited code: Coda (Codex Lily)'s pump.py/study.py
around the admitted AB-MPB1A kernel. Nothing in this file was executed by its author; every
expected value is copied from the frozen reports or derived by hand. Red's sandbox is the
first execution.

Standard library only, deterministic, no network, no file writes.

Run:
    python reviews/audit_ab_mpb1b/audit_test_pump_matched.py -v

Locating the frozen code (frozen files are read only, never modified or copied):
    AB_MPB1B_DIR    directory holding pump.py and admitted.py; default
                    <repo>/validation/ab_mpb1b resolved from this file, then cwd.
    AB_MPB1A_MODEL  path to the admitted A model.py. Used only if `import admitted` fails
                    (full A tree with manifest/receipts unavailable); a minimal shim exposing
                    just `A` is then installed. The shim does NOT verify the A hash pins;
                    ProvenanceTests hashes the kernel file instead. A_SOURCE records the loader.
    AB_MPB1B_EXPECT_PATCHED=1  skip the frozen-hash check when running against a pump.py copy
                    that carries pump_subnormal_guard.patch.

Reference numbers are six-decimal values from validation/ab_mpb1b/REPORT.md (30 s table, 10 s
example) and validation/ab_mpb1a/REPORT.md (nine primary rows); SIX_DECIMALS = 6e-7 covers
half-unit rounding plus float noise.
"""
from fractions import Fraction
from pathlib import Path
import hashlib
import importlib
import importlib.util
import math
import os
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent

FROZEN_SHA256 = {  # from the source bundle headers of task pump-matched-audit-001
    'pump.py': 'fac5e0e7bef316379e97aa4f46e6bac8c7c53c23c01dff997bbf947ab2be9a47',
    'admitted.py': 'ec9db5aef83cbf12f2ec152e3c32f7d715687a42cf6eba779c7f8dd48be8245b',
    'study.py': '7a2456aad19a711c603f82d3ae9c4cc3fb6f0fbd13bc17848e2814ed1763679f',
    'test_pump.py': 'afc0395be74f2a1d8db72880a5c154b9217c9ceec83bad9ec3259b8eb73631a4',
    'STUDY_DESIGN.json': '0a81942a27c40d20af63414ffbd1b58872f33da3783986819a3fc55057f55c75',
}
KERNEL_SHA256 = 'd05cdd81f64464091148570d2f8c78f668e4960ffb10ae137f1ee6ad2f63c172'


def _candidate_dirs():
    env = os.environ.get('AB_MPB1B_DIR')
    if env:
        yield Path(env).resolve()
    if len(HERE.parents) >= 2:
        yield HERE.parents[1] / 'validation' / 'ab_mpb1b'
    yield HERE
    yield Path.cwd()


def _load():
    seen = set()
    for directory in _candidate_dirs():
        if directory in seen or not (directory / 'pump.py').is_file():
            continue
        seen.add(directory)
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
        try:
            module = importlib.import_module('pump')
            return module, module.A, directory, 'admitted.py (A pins verified by the frozen loader)'
        except Exception as error:
            model_path = os.environ.get('AB_MPB1A_MODEL')
            if not model_path:
                raise RuntimeError('import pump failed: %r; set AB_MPB1A_MODEL to use the shim loader'
                                   % (error,)) from error
            for name in ('pump', 'admitted'):
                sys.modules.pop(name, None)
            spec = importlib.util.spec_from_file_location('_audit_mpb1a_model', model_path)
            kernel = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(kernel)
            shim = types.ModuleType('admitted')
            shim.A = kernel
            sys.modules['admitted'] = shim
            module = importlib.import_module('pump')
            return module, kernel, directory, 'shim loader (A pins NOT verified): ' + model_path
    raise RuntimeError('pump.py not found; set AB_MPB1B_DIR')


pump, A, PUMP_DIR, A_SOURCE = _load()

# ---------------------------------------------------------------- frozen design (STUDY_DESIGN.json)
DESIGN_CONFIG = dict(reservoir_volume=2.0, channel_volume=1.0, wall_volume=0.5, channel_cells=3,
                     return_volume=0.0, return_cells=0, flow=0.4, exchange=0.3, kon=0.5, koff=0.2,
                     sink=0.15)
# name, free concentration, site concentration, bound fraction, expected oxygen, expected sites
CONDITIONS = (
    ('no_sites', 0.8, 0, 0.0, 2.4, 0.0),
    ('sites_same_initial_free', 0.8, 1, 0.6666666666666666, 4.4, 3.0),
    ('sites_equal_initial_oxygen', 0.3403124237432849, 1, 0.45968757625671514, 2.4, 3.0),
)
NAMES = tuple(c[0] for c in CONDITIONS)
R0, RATIOS, TIMES, DT = 20.0, (1, 2, 4), (2, 10, 30), 0.01
D_CAP, P_CAP = 12.0, 3.2
EXPECTED_STEPS = {2: 200, 10: 1000, 30: 3000}
SIX_DECIMALS = 6e-7

# ---------------------------------------------------------------- report values (six decimals)
REPORT_30S = {  # (condition, R/R0): (distal wall concentration, consumed) -- AB-MPB1B REPORT.md
    ('no_sites', 1): (0.328213, 0.939771),
    ('no_sites', 2): (0.321792, 0.926991),
    ('no_sites', 4): (0.302033, 0.890206),
    ('sites_same_initial_free', 1): (0.383084, 1.013147),
    ('sites_same_initial_free', 2): (0.376882, 1.000954),
    ('sites_same_initial_free', 4): (0.359076, 0.967930),
    ('sites_equal_initial_oxygen', 1): (0.181702, 0.456848),
    ('sites_equal_initial_oxygen', 2): (0.179087, 0.451832),
    ('sites_equal_initial_oxygen', 4): (0.171987, 0.438967),
}
A_REPORT_R20 = {  # (condition, time): (distal, consumed, net wall transfer) -- AB-MPB1A REPORT.md
    ('no_sites', 2): (0.399149, 0.040684, 0.249305),
    ('no_sites', 10): (0.462459, 0.332798, 0.571990),
    ('no_sites', 30): (0.328213, 0.939771, 1.108979),
    ('sites_same_initial_free', 2): (0.407282, 0.041014, 0.252753),
    ('sites_same_initial_free', 10): (0.490747, 0.343969, 0.596428),
    ('sites_same_initial_free', 30): (0.383084, 1.013147, 1.209532),
    ('sites_equal_initial_oxygen', 2): (0.175650, 0.017542, 0.108534),
    ('sites_equal_initial_oxygen', 10): (0.218782, 0.150131, 0.262302),
    ('sites_equal_initial_oxygen', 30): (0.181702, 0.456848, 0.549747),
}
REPORT_10S_SAME_FREE_R80 = 0.439342
REPORT_10S_NO_SITES_R20 = 0.462459


# ---------------------------------------------------------------- helpers
def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def design_config():
    return A.Config(**DESIGN_CONFIG)


def initial_state(config, name):
    free, site, fraction = next(c[1:4] for c in CONDITIONS if c[0] == name)
    model = A.build(config)
    return model, A.uniform_state(model, free, site, fraction)


def endpoints(model, y, solved):
    n = model.n
    values = solved['result']['amounts']
    point = solved['pump']
    walls = [values[3 * n + j] / v for j, v in enumerate(model.wall_volumes)]
    return {'flow': point['flow_ml_s'], 'pressure': point['actual_pressure_kpa'],
            'power': point['actual_hydraulic_power_mw'], 'active': point['active_constraint'],
            'distal': walls[-1], 'minimum': min(walls), 'consumed': values[-1],
            'net': math.fsum(values[3 * n:]) - math.fsum(y[3 * n:]),
            'amounts': values, 'result': solved['result']}


_ROWS = {}


def rows():
    """The 27 frozen rows recomputed through pump.solve_pumped (the study.py code path)."""
    if not _ROWS:
        config = design_config()
        for name in NAMES:
            model, y = initial_state(config, name)
            for ratio in RATIOS:
                for duration in TIMES:
                    solved = pump.solve_pumped(config, y, duration, DT, R0 * ratio)
                    _ROWS[(name, ratio, duration)] = endpoints(model, y, solved)
    return _ROWS


_THROTTLED = {}


def throttled_rows():
    """R = R0 under caps (3 kPa, 3.2 mW): Q = 0.15, the flow the grid assigns to R = 4*R0."""
    if not _THROTTLED:
        config = design_config()
        caps = pump.PumpCaps(3.0, P_CAP)
        for name in NAMES:
            model, y = initial_state(config, name)
            for duration in TIMES:
                solved = pump.solve_pumped(config, y, duration, DT, R0, caps)
                _THROTTLED[(name, duration)] = endpoints(model, y, solved)
    return _THROTTLED


SENSES = ('max', 'max', 'min', 'min')  # pareto_receipt.json objectives, in order


def objectives(row, duration):
    return (row['distal'], row['consumed'], row['pressure'], row['power'] * duration)


def dominates(a, b, tol=1e-12):
    no_worse, strictly = True, False
    for x, y, sense in zip(a, b, SENSES):
        if sense == 'max':
            no_worse = no_worse and x >= y - tol
            strictly = strictly or x > y + tol
        else:
            no_worse = no_worse and x <= y + tol
            strictly = strictly or x < y - tol
    return no_worse and strictly


def nondominated(objective_by_key, tol=1e-12):
    return sorted(k for k in objective_by_key
                  if not any(dominates(objective_by_key[o], objective_by_key[k], tol)
                             for o in objective_by_key if o != k))


# ---------------------------------------------------------------- tests
class ProvenanceTests(unittest.TestCase):
    """The audited bytes must be the frozen ones from the source bundle."""

    def test_audited_pump_file_is_the_frozen_one(self):
        if os.environ.get('AB_MPB1B_EXPECT_PATCHED') == '1':
            self.skipTest('running against a patched pump.py copy by request')
        self.assertEqual(sha256_of(PUMP_DIR / 'pump.py'), FROZEN_SHA256['pump.py'])
        for name, digest in FROZEN_SHA256.items():
            path = PUMP_DIR / name
            if path.is_file():
                with self.subTest(file=name):
                    self.assertEqual(sha256_of(path), digest)

    def test_kernel_is_the_pinned_A_model(self):
        self.assertEqual(sha256_of(A.__file__), KERNEL_SHA256, 'loaded via ' + A_SOURCE)


class PumpAlgebraTests(unittest.TestCase):
    """Pump-contract checks without kernel integration (complements the frozen test_pump.py)."""

    def test_contract_table_row_r40_power_limited(self):
        """PUMP_CONTRACT.md table row R = 40 is not value-checked by the frozen tests."""
        got = pump.operating_point(40)
        self.assertAlmostEqual(got['flow_ml_s'], math.sqrt(0.08), delta=2e-14)
        self.assertAlmostEqual(got['actual_pressure_kpa'], math.sqrt(128), delta=2e-14)
        self.assertAlmostEqual(got['actual_hydraulic_power_mw'], 3.2, delta=2e-14)
        self.assertEqual(got['active_constraint'], 'power')

    def test_equal_caps_do_not_imply_equal_realized_power_or_pressure(self):
        """Only the two power-limited rows share realized power; no two rows share realized pressure."""
        pts = {r: pump.operating_point(r) for r in (20, 40, 80)}
        self.assertAlmostEqual(pts[20]['actual_hydraulic_power_mw'],
                               pts[40]['actual_hydraulic_power_mw'], delta=1e-14)
        self.assertAlmostEqual(pts[80]['actual_hydraulic_power_mw'], 1.8, delta=2e-14)  # 56.25 % of cap
        self.assertAlmostEqual(pts[20]['actual_pressure_kpa'], 8.0, delta=2e-14)        # 66.67 % of cap
        pressures = sorted(p['actual_pressure_kpa'] for p in pts.values())
        for low, high in zip(pressures, pressures[1:]):
            self.assertGreater(high - low, 0.6)
        # Flow ratio R=80 : R=20 is 0.375, neither the matched-power 0.5 nor the matched-pressure 0.25.
        self.assertAlmostEqual(pts[80]['flow_ml_s'] / pts[20]['flow_ml_s'], 0.375, delta=1e-14)
        self.assertAlmostEqual(math.sqrt(P_CAP / 80), 0.2, delta=1e-15)
        self.assertAlmostEqual(D_CAP / 20, 0.6, delta=1e-15)

    def test_realized_quantities_equal_their_caps_only_in_their_own_regime(self):
        """Power equals its cap iff R <= D^2/P; pressure equals its cap iff R >= D^2/P."""
        for d in (1.0, 12.0, 100.0):
            for p in (0.3, 3.2, 50.0):
                crossover = d * d / p
                for factor in (0.01, 0.1, 0.5, 0.9, 0.999, 1.001, 1.1, 2.0, 10.0, 100.0):
                    r = crossover * factor
                    got = pump.operating_point(r, pump.PumpCaps(d, p))
                    with self.subTest(d=d, p=p, r=r):
                        if factor < 1:
                            self.assertEqual(got['active_constraint'], 'power')
                            self.assertTrue(math.isclose(got['actual_hydraulic_power_mw'], p, rel_tol=3e-14))
                            self.assertLess(got['actual_pressure_kpa'], d * (1 - 1e-6))
                            self.assertTrue(math.isclose(got['actual_pressure_kpa'], math.sqrt(p * r),
                                                         rel_tol=1e-13))
                        else:
                            self.assertEqual(got['active_constraint'], 'pressure')
                            self.assertTrue(math.isclose(got['actual_pressure_kpa'], d, rel_tol=3e-14))
                            self.assertLess(got['actual_hydraulic_power_mw'], p * (1 - 1e-6))
                            self.assertTrue(math.isclose(got['actual_hydraulic_power_mw'], d * d / r,
                                                         rel_tol=1e-13))

    def test_both_label_survives_consistent_scaling(self):
        """Scaling (R, D, P) by k keeps R = D^2/P; the 'both' label must not depend on k."""
        for k in (1e-3, 0.1, 1.0, 10.0, 1e3, 1e6):
            got = pump.operating_point(45 * k, pump.PumpCaps(12 * k, 3.2 * k))
            with self.subTest(k=k):
                self.assertEqual(got['active_constraint'], 'both')
                self.assertTrue(math.isclose(got['flow_ml_s'], 4 / 15, rel_tol=3e-14))
                self.assertTrue(math.isclose(got['actual_pressure_kpa'], 12 * k, rel_tol=3e-14))
                self.assertTrue(math.isclose(got['actual_hydraulic_power_mw'], 3.2 * k, rel_tol=3e-14))

    def test_exact_rational_feasibility_binding_and_maximality(self):
        """Exact Fraction arithmetic on the returned float: both caps respected to 3e-14 relative, at
        least one binds to 3e-14, Q*(1+1e-12) violates a cap (Q is maximal), and the label matches the
        binding cap. Independent of sqrt and of the Decimal bisection in test_pump.py."""
        tol = Fraction(3, 10 ** 14)
        bump = 1 + Fraction(1, 10 ** 12)
        loose = Fraction(1, 10 ** 9)
        tight = Fraction(1, 10 ** 15)
        for r in (0.001, 1.0, 7.0, 20.0, 45.0, 80.0, 1000.0, 1e6):
            for d in (0.5, 1.0, 12.0, 1e4):
                for p in (1e-6, 0.3, 3.2, 50.0):
                    got = pump.operating_point(r, pump.PumpCaps(d, p))
                    R, D, P, Q = (Fraction(float(x)) for x in (r, d, p, got['flow_ml_s']))
                    with self.subTest(r=r, d=d, p=p):
                        self.assertGreater(Q, 0)
                        self.assertLessEqual(R * Q, D * (1 + tol))
                        self.assertLessEqual(R * Q * Q, P * (1 + tol))
                        self.assertTrue(R * Q >= D * (1 - tol) or R * Q * Q >= P * (1 - tol))
                        bumped = Q * bump
                        self.assertTrue(R * bumped > D or R * bumped * bumped > P)
                        pressure_gap = abs(R * Q / D - 1)
                        power_gap = abs(R * Q * Q / P - 1)
                        label = got['active_constraint']
                        if pressure_gap <= tol and power_gap > loose:
                            self.assertEqual(label, 'pressure')
                        elif power_gap <= tol and pressure_gap > loose:
                            self.assertEqual(label, 'power')
                        elif pressure_gap <= tight and power_gap <= tight:
                            self.assertEqual(label, 'both')

    def test_solve_pumped_replaces_only_flow(self):
        config = A.Config(**dict(DESIGN_CONFIG, flow=9.0, channel_cells=1))
        model = A.build(config)
        y = A.uniform_state(model)
        solved = pump.solve_pumped(config, y, 0, DT, 80)
        chosen = solved['configuration']
        self.assertEqual(chosen['flow'], solved['pump']['flow_ml_s'])
        self.assertAlmostEqual(chosen['flow'], 0.15, delta=2e-15)
        for key, value in DESIGN_CONFIG.items():
            if key not in ('flow', 'channel_cells'):
                self.assertEqual(chosen[key], value)
        self.assertEqual(chosen['channel_cells'], 1)
        self.assertEqual(solved['result']['amounts'], y)


class ReportNumbersTests(unittest.TestCase):
    """Recompute the 27 frozen rows through pump.solve_pumped and compare with the reports. pump.py and
    the A kernel are deterministic, so these rows are the study's rows (assumption: same float semantics)."""

    def test_initial_inventories_and_partition_match_design(self):
        config = design_config()
        for name, free, site, fraction, oxygen, sites in CONDITIONS:
            model, y = initial_state(config, name)
            got_oxygen, got_sites = A.inventories(model, y)
            with self.subTest(condition=name):
                self.assertAlmostEqual(got_oxygen, oxygen, delta=1e-13)
                self.assertAlmostEqual(got_sites, sites, delta=1e-13)
                if site:  # local binding equilibrium: f = kon*C/(koff + kon*C) with kon=0.5, koff=0.2
                    self.assertAlmostEqual(fraction, free / (0.4 + free), delta=1e-14)

    def test_steps_and_timestep_match_design(self):
        """Exit bound <= 7.8/s gives 0.9/rate >= 0.115 s > 0.01 s: no automatic restriction, h = 0.01."""
        for (name, ratio, duration), row in rows().items():
            res = row['result']
            with self.subTest(condition=name, ratio=ratio, time=duration):
                self.assertEqual(res['steps'], EXPECTED_STEPS[duration])
                self.assertEqual(res['actual_dt'], DT)
                self.assertLess(res['max_oxygen_error'], 1e-11)
                self.assertLess(res['max_site_error'], 1e-11)
                self.assertGreaterEqual(res['minimum_seen'], -1e-14)

    def test_r20_rows_match_A_report_six_decimals(self):
        for (name, duration), (distal, consumed, net) in A_REPORT_R20.items():
            row = rows()[(name, 1, duration)]
            with self.subTest(condition=name, time=duration):
                self.assertAlmostEqual(row['flow'], 0.4, delta=2e-15)
                self.assertAlmostEqual(row['distal'], distal, delta=SIX_DECIMALS)
                self.assertAlmostEqual(row['consumed'], consumed, delta=SIX_DECIMALS)
                self.assertAlmostEqual(row['net'], net, delta=SIX_DECIMALS)
                self.assertEqual(row['minimum'], row['distal'])

    def test_r20_rows_reproduce_saved_A_rows_when_available(self):
        admitted = sys.modules.get('admitted')
        if not hasattr(admitted, 'A_ROWS'):
            self.skipTest('shim loader in use; saved A rows unavailable')
        worst = 0.0
        for a_row in admitted.A_ROWS:
            row = rows()[(a_row['condition'], 1, a_row['time_s'])]
            worst = max(worst, max(abs(x - y) for x, y in zip(row['amounts'], a_row['final_amounts'])))
        self.assertLessEqual(worst, 2e-14)

    def test_report_30s_table_reproduced(self):
        for (name, ratio), (distal, consumed) in REPORT_30S.items():
            row = rows()[(name, ratio, 30)]
            with self.subTest(condition=name, ratio=ratio):
                self.assertAlmostEqual(row['distal'], distal, delta=SIX_DECIMALS)
                self.assertAlmostEqual(row['consumed'], consumed, delta=SIX_DECIMALS)

    def test_report_10s_direction_example_reproduced(self):
        r = rows()
        self.assertAlmostEqual(r[('sites_same_initial_free', 4, 10)]['distal'],
                               REPORT_10S_SAME_FREE_R80, delta=SIX_DECIMALS)
        self.assertAlmostEqual(r[('no_sites', 1, 10)]['distal'], REPORT_10S_NO_SITES_R20, delta=SIX_DECIMALS)
        self.assertLess(r[('sites_same_initial_free', 4, 10)]['distal'], r[('no_sites', 1, 10)]['distal'])
        self.assertGreater(r[('sites_same_initial_free', 4, 30)]['distal'], r[('no_sites', 1, 30)]['distal'])

    def test_pump_quantities_identical_across_conditions(self):
        keys = ('flow', 'pressure', 'power', 'active')
        for ratio in RATIOS:
            for duration in TIMES:
                values = {tuple(rows()[(name, ratio, duration)][k] for k in keys) for name in NAMES}
                with self.subTest(ratio=ratio, time=duration):
                    self.assertEqual(len(values), 1)


class ContrastAndParetoTests(unittest.TestCase):
    """Logic of the study contrasts and of pareto_receipt.json, recomputed (the Pareto script is absent)."""

    def test_within_resistance_contrast_signs_do_not_flip(self):
        """Characterization (not asserted by REPORT.md): at equal R and time, same-free > no-sites and
        equal-total < no-sites on all three endpoints, as in A. A failure is a finding, not a harness bug."""
        for ratio in RATIOS:
            for duration in TIMES:
                base = rows()[('no_sites', ratio, duration)]
                same = rows()[('sites_same_initial_free', ratio, duration)]
                equal = rows()[('sites_equal_initial_oxygen', ratio, duration)]
                with self.subTest(ratio=ratio, time=duration):
                    for key in ('distal', 'consumed', 'net'):
                        self.assertGreater(same[key], base[key])
                        self.assertLess(equal[key], base[key])

    def test_penalty_contrast_sign_change_same_free_R80(self):
        """REPORT.md: same-free R=80 minus no-sites R=20 distal is negative at 10 s and positive at 30 s."""
        r = rows()
        diffs = {t: r[('sites_same_initial_free', 4, t)]['distal'] - r[('no_sites', 1, t)]['distal']
                 for t in TIMES}
        self.assertLess(diffs[10], 0)
        self.assertGreater(diffs[30], 0)

    def test_transport_endpoints_strictly_decrease_with_resistance(self):
        """Characterization: distal, consumed and net fall as R rises in every (condition, time) group.
        With the cap rule this alone predetermines the receipt's Pareto pattern."""
        for name in NAMES:
            for duration in TIMES:
                seq = [rows()[(name, ratio, duration)] for ratio in RATIOS]
                with self.subTest(condition=name, time=duration):
                    for key in ('distal', 'consumed', 'net'):
                        for a, b in zip(seq, seq[1:]):
                            self.assertGreater(a[key], b[key])

    def test_pareto_receipt_pattern_reproduced(self):
        """pareto_receipt.json: {1,4} nondominated, 2 dominated by 1, tolerance 1e-12, all nine groups."""
        for name in NAMES:
            for duration in TIMES:
                obj = {ratio: objectives(rows()[(name, ratio, duration)], duration) for ratio in RATIOS}
                with self.subTest(condition=name, time=duration):
                    self.assertEqual(nondominated(obj), [1, 4])
                    self.assertTrue(dominates(obj[1], obj[2]))
                    self.assertFalse(dominates(obj[1], obj[4]))
                    self.assertFalse(dominates(obj[4], obj[1]))

    def test_grid_nondominance_of_R4_is_a_throttling_artifact(self):
        """R=R0 under caps (3 kPa, 3.2 mW) yields Q=0.15 exactly as R=4*R0 does under (12, 3.2). The kernel
        sees only Q, so transport is identical while pressure (3 vs 12) and power (0.45 vs 1.8) are lower:
        the off-grid point dominates the R=4*R0 row on all four receipt objectives in every group."""
        for name in NAMES:
            for duration in TIMES:
                high = rows()[(name, 4, duration)]
                low = throttled_rows()[(name, duration)]
                with self.subTest(condition=name, time=duration):
                    self.assertEqual(low['flow'], high['flow'])
                    self.assertEqual(low['amounts'], high['amounts'])
                    self.assertEqual(low['active'], 'pressure')
                    self.assertAlmostEqual(low['pressure'], 3.0, delta=2e-14)
                    self.assertAlmostEqual(low['power'], 0.45, delta=2e-14)
                    self.assertTrue(dominates(objectives(low, duration), objectives(high, duration)))


class ContractGapProbes(unittest.TestCase):
    """Edge-of-float probes of PUMP_CONTRACT.md promises. Static prediction (unexecuted): the frozen pump.py
    FAILS test_subnormal_operating_point_is_rejected_or_contract_consistent; pump_subnormal_guard.patch makes
    it pass. Irrelevant to the 27-row study, whose quantities are all normal floats."""

    def test_subnormal_operating_point_is_rejected_or_contract_consistent(self):
        r, d, p = 1e308, 1e-10, 1e-300  # D/R ~ 1e-318 is subnormal: ~2.5e-6 relative precision
        try:
            got = pump.operating_point(r, pump.PumpCaps(d, p))
        except ValueError:
            return  # contract-consistent rejection
        self.assertGreater(got['flow_ml_s'], 0)
        self.assertGreater(got['actual_hydraulic_power_mw'], 0,
                           'positive flow with silently zero realized power: %r' % (got,))
        binds = (math.isclose(got['actual_pressure_kpa'], d, rel_tol=3e-14)
                 or math.isclose(got['actual_hydraulic_power_mw'], p, rel_tol=3e-14))
        self.assertTrue(binds, 'no cap binds within 3e-14 relative: %r' % (got,))

    def test_existing_unrepresentable_guard_still_rejects(self):
        with self.assertRaises(ValueError):
            pump.operating_point(1e308, pump.PumpCaps(5e-324, 1))


if __name__ == '__main__':
    unittest.main()
