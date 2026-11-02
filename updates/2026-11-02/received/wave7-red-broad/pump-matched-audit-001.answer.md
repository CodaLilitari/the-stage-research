# Audit of AB-MPB1B (task pump-matched-audit-001)

**Method and status.** Everything below is static reasoning over the verbatim sources in the bundle. I executed nothing and read no files beyond the bundle; every "predicted" result is a hand derivation under the assumptions listed at the end (IEEE-754 binary64 with correctly rounded `/` and `sqrt`, deterministic kernel). The test module and diagnostics script are the first things to run; Red's sandbox results should be compared with the predictions in §4.

Credits for the audited material: Coda (Codex Lily) authored PUMP_CONTRACT.md, ACCEPTANCE.md, pump.py, study.py, test_pump.py, REPORT.md and both coordinator reviews; Richard Pemberton directed, scoped and funded; Lilitari (Lily) supplied the matched-pumping research priority and transfer boundaries. The bundle contains no Fable-authored artifact (the coordinator review records a paid shared-contract audit that returned a refusal and no answer), so nothing here is attributed to Fable. This audit text and the new files are by Claude (Anthropic) via Red.

---

## 1. Pump contract: equations, units, "matched" definitions

**Units.** 1 kPa·mL/s = 10³ Pa · 10⁻⁶ m³/s = 10⁻³ W = 1 mW — the contract's identity is correct. With R in kPa·s/mL: D/R has units mL/s; sqrt(P/R) = sqrt((kPa·mL/s)/(kPa·s/mL)) = mL/s. ΔP = R·Q is kPa, Phyd = ΔP·Q is mW. All consistent.

**Equation.** Both constraints R·Q ≤ D and R·Q² ≤ P are monotone increasing in Q for R > 0, so the feasible set is the interval [0, min(D/R, sqrt(P/R))] and `Q = min(D/R, sqrt(P/R))` is exactly the maximal feasible flow. Crossover D/R = sqrt(P/R) ⇔ R = D²/P = 144/3.2 = 45. Table check by hand: R=20 → (0.4, 8, 3.2) power-limited; R=40 → (sqrt(0.08)=0.2828427, sqrt(128)=11.3137085, 3.2) power-limited; R=80 → (0.15, 12, 1.8) pressure-limited; R=45 → Q = 4/15, both. Scaling (R, D, P) → (kR, kD, kP) preserves Q and scales ΔP, Phyd by k. Zero caps → zero flow. All as stated in the contract, acceptance and report.

**Hydraulic vs electrical.** Phyd = ΔP·Q is the power delivered to the fluid (equal to the loop's viscous dissipation R·Q² in steady state). No efficiency, shaft or electrical power appears anywhere in pump.py or study.py; the report's disclaimer is accurate. Modelling note only: an electrical-input cap P_el with efficiency η would give Q = min(D/R, sqrt(η·P_el/R)) and move the crossover to D²/(η·P_el), i.e. more rows become power-limited; that is correctly out of scope.

**Matched-cap definition and the key question — do equal caps imply equal actual power? No.** For each row exactly one cap is generically active:

| regime | condition | realized ΔP | realized Phyd |
|---|---|---|---|
| power-limited | R < D²/P | sqrt(P·R) < D | = P |
| pressure-limited | R > D²/P | = D | D²/R < P |

So realized power equals the common cap only for R ≤ 45 (R=20, 40 → 3.2 mW) and R=80 realizes 1.8 mW (56.25 % of the cap); realized pressure equals the cap only for R ≥ 45 (R=80 → 12 kPa) while R=20, 40 realize 8 and 11.31 kPa. In the frozen grid the only pair matched in *realized* power is (R=20, R=40); **no** pair is matched in realized pressure. "Matched" in AB-MPB1B therefore means "identical caps," and the contract and report say so correctly ("Equal caps do not mean equal realized pressure and power"). The consequences for the contrasts and the Pareto receipt are findings F1 and F2.

**pump.py implementation.** Correct against the contract: domain rejection via `A.number` (bool/str/None/negative/nonfinite, R=0 even with zero caps, huge ints via the OverflowError path), zero-cap branch, `min`, finite checks, flow override via `dataclasses.replace` (re-validates Config), unchanged duration/dt/state. Separate square roots only extend the overflow range (sqrt(P)/sqrt(R) can still overflow to inf when both ends of the range are used; then `q` is inf and is rejected — correct). The `'both'` label window (rel 4e-15 ≈ 18 ulp) is adequate: worst-case rounding separation of the two flows at an exact crossover is ≈ 3 ulp.

## 2. Study: contrast and Pareto logic

**study.py.** Row count 3×3×3 = 27, contrasts 6 (resistance-only) + 18 (within-R) + 12 (penalty) + 27 (A ablation) = 63 — matches the asserts. Pump quantities per row are condition-independent (they depend on R only). Within-R contrasts isolate initial inventory/partition at identical Q, ΔP, Phyd — clean. The resistance-only and penalty contrasts at R=80 compare a pressure-limited row with a power-limited baseline (F2). Net transfer = final wall + consumed − initial (initial wall and consumed are zero) — matches the contract. CSV/receipt writing uses `'x'` mode and `exist_ok=False` — immutability honoured. Two dependencies on the A receipt schema (`total_wall_transfer_umol` fallback, `initial_oxygen_umol`, hard-coded baseline flow `.4`) cannot be checked from the bundle (F6).

**pareto_receipt.json.** The generating script is not in the bundle; I can only check the receipt's conclusions against the reported 30 s endpoints and the pump algebra. For every group ΔP is ordered 8 < 11.31 < 12 and energy Phyd·T is tied for R=20/40 and lower for R=80. If distal and consumed decrease with R (true at 30 s per the report table; I test all nine groups), then R=40 is dominated by R=20 (worse or tied on all four objectives) and R=80 is nondominated **solely** because its energy is lower — and it is lower only because the pressure cap prevents it from using the power budget. The receipt's pattern [1,4]/[2] is therefore predetermined by the cap rule plus monotone transport and conveys no transport information (F1).

## 3. Findings ranked by severity

No High-severity finding. Nothing found changes any of the 27 saved rows or the 63 contrasts.

**F1 — Medium — Pareto nondominance of R/R0 = 4 is a throttling artifact of cap-saturated operation.**
Exact inputs: grid rows (R, D, P) = (20, 12, 3.2), (40, 12, 3.2), (80, 12, 3.2) → (Q, ΔP, Phyd) = (0.4, 8, 3.2), (0.2828427, 11.3137085, 3.2), (0.15, 12, 1.8); receipt objectives (max distal, max consumed, min ΔP, min Phyd·T), tolerance 1e-12. Off-grid witness `pump.operating_point(20, pump.PumpCaps(3.0, 3.2))` → (0.15, 3, 0.45): 3/20 and 12/80 are the same correctly rounded float 0.15, the kernel sees only `Config.flow`, so the trajectory is bit-identical to the R=80 row while ΔP (3 vs 12) and Phyd (0.45 vs 1.8) are strictly lower — it dominates the R=80 row on all four objectives in all nine groups (predicted; `test_grid_nondominance_of_R4_is_a_throttling_artifact`). Realized pressure and energy are constraint-determined, not decision variables, so treating them as objectives for rows that each run at their cap-maximal flow is a logic flaw. The coordinator review's sentence "R/R0=1 and 4 remain nondominated" is numerically reproducible (predicted) but should be qualified as implied by the pump rule plus monotone transport. REPORT.md does not use the Pareto result. Recommendation for a B.1 revision: drop the two pump-side objectives, or add matched-Q throttled references, and say explicitly that the grid pattern follows from the min rule.

**F2 — Medium — Contrasts involving R = 80 include a cap-regime switch; "resistance" is not isolated, and no realized-pressure-matched contrast exists.**
Exact inputs: `pump.operating_point(80)` → `active_constraint='pressure'`, Q = 0.15; matched-power flow would be sqrt(3.2/80) = 0.2 (flow ratio 0.5 to R=20), matched-pressure flow at R=20 would be 12/20 = 0.6 (ratio 0.25); realized ratio 0.15/0.4 = 0.375. The report's direction-change example (same-free R=80 vs no-sites R=20 distal: 10 s 0.439342 < 0.462459; 30 s 0.359076 > 0.328213) therefore combines +2.0 µmol inventory, the matched-power flow reduction and a further 25 % flow reduction from the pressure cap. The report's hedge covers inventory and the "assigned penalty" but not the regime switch, and study.py records `active_constraint` per row but does not tag contrasts with matched-realized-power/-pressure flags. Only (R=20, R=40) share realized power; no pair shares realized pressure (`test_equal_caps_do_not_imply_equal_realized_power_or_pressure`). Recommendation: add two booleans to each contrast entry (`matched_realized_power`, `matched_realized_pressure`) and rephrase the lead sentence to "the assigned-resistance/cap penalty can change the sign of a mixed contrast."

**F3 — Low — Contract gap at the edge of the float range: subnormal flow passes silently; realized power can be exactly 0 with positive flow; "at least one cap binds to 3e-14" fails.**
Exact input: `pump.operating_point(1e308, pump.PumpCaps(1e-10, 1e-300))`. Predicted (hand): pressure_flow = 1e-10/1e308 rounds to the subnormal 202402·2⁻¹⁰⁷⁴ ≈ 9.99998748e-319 (relative error ≈ −1.25e-6), power_flow = 1e-304, Q = the subnormal (accepted: finite and > 0), ΔP ≈ 1e-10·(1 − 1.25e-6) (feasible, but no cap binds within 3e-14), Phyd = ΔP·Q ≈ 1e-328 → underflows to 0.0. The contract promises rejection "rather than silently replaced by zero" and "rounding-level residuals"; the frozen tests check feasibility/binding only at the default caps. Irrelevant to the 27-row study (all its quantities are normal floats). Optional patch supplied (reject if min(Q, ΔP, Phyd) < `sys.float_info.min`); it does not alter any frozen test's outcome by static inspection. Probe: `ContractGapProbes.test_subnormal_operating_point_is_rejected_or_contract_consistent` — predicted to FAIL on the frozen pump.py and pass with the patch.

**F4 — Low — Test coverage gaps relative to the contract table and acceptance list.**
R=40 (the only row with irrational Q and ΔP in the frozen table) is never value-checked; `'both'` is checked at one point only; maximality of Q is tested only implicitly via the Decimal bisection; study.py asserts feasibility per row but not "at least one cap binds" (acceptance 9); `test_wrong_model_witnesses` evaluates arithmetic expressions rather than exercising an alternative implementation. Supplied: `test_contract_table_row_r40_power_limited`, `test_both_label_survives_consistent_scaling`, `test_exact_rational_feasibility_binding_and_maximality` (exact `Fraction` arithmetic, independent of `sqrt` and of the Decimal oracle, 128 cases), `test_realized_quantities_equal_their_caps_only_in_their_own_regime` (90 cases).

**F5 — Low/informational — "Reduces to A" is a 2e-14-tolerance statement, not bit identity.**
Exact input: `pump.operating_point(20)['flow_ml_s'] == 0.4`. Q(20) = sqrt(3.2)/sqrt(20) carries up to ~1.5 ulp of rounding and is probably not the float 0.4; the reported nonzero maximum difference 8.89e-16 is consistent with a 1-ulp flow difference propagated through 3000 steps (a bit-identical flow would give exactly 0). Not an error; the frozen test bound (2e-15 on flow, 2e-14 on state) is met. The diagnostics script records the exact ulp offset.

**F6 — Informational — Not verifiable from the bundle.** The Pareto script; FREEZE.json, IMPLEMENTATION_FREEZE.json, receipts/green.json, run_001 outputs; the A receipt row schema (`total_wall_transfer_umol`/`net_wall_transfer_umol`, `initial_oxygen_umol`, `flow_ml_s`; study.py uses `base.get('flow_ml_s', .4)` and would be more faithful reading `base['configuration']['flow']`); the pareto receipt's `input_receipt_sha256`; all run-time claims (1.194 s, 17 passing, 8.89e-16, residuals 1.16e-14/1.12e-14, 33 files unchanged). The test `test_r20_rows_reproduce_saved_A_rows_when_available` and the diagnostics key `a_row_keys` close part of this when the full A tree is present.

**F7 — Informational — Verified correct by static check.** Units and formula (§1); contract table and crossover; scaling invariance; zero-cap and domain handling; flow-only override; 27 rows / 63 contrasts; 17 test methods; initial conditions: f = kon·C/(koff + kon·C) = C/(0.4 + C), equal-total C solves C² + 0.6C − 0.32 = 0 → C = (−0.6 + sqrt(1.64))/2 = 0.3403124237432849, f = 0.45968757625671514, partitions 1.0209372712/1.3790627288 µmol, totals 2.4/4.4/2.4, 83.33 % inventory difference; R=20 column of the 30 s table equals the A report's nine primary rows; timestep: exit bound ≤ 7.8 s⁻¹ → 0.9/rate ≥ 0.115 s > 0.01 s, so steps are exactly 200/1000/3000 with h = 0.01 (`test_steps_and_timestep_match_design`).

**F8 — Informational — Modelling notes.** Within a group the energy objective Phyd·T is redundant with Phyd (T is constant). Linear resistance is a laminar assumption (with ΔP ∝ Q² the power branch would be Q = (P/K)^{1/3}); declared synthetic, no action. Efficiency note in §1.

## 4. Deliverables and predicted outcomes

Run from the repository root (frozen files are read, never written):

```
python reviews/audit_ab_mpb1b/audit_test_pump_matched.py -v
python reviews/audit_ab_mpb1b/audit_diagnostics.py [optional/output/path.json]
```

If the full A tree is unavailable, set `AB_MPB1A_MODEL=/path/to/ab_mpb1a/model.py` to use a shim loader (then A pins are not verified by the loader; `ProvenanceTests` still hashes the kernel). Predicted on the frozen files: 22 tests, 21 pass (1 of them skips only under the shim), **1 fails** — `ContractGapProbes.test_subnormal_operating_point_is_rejected_or_contract_consistent` (F3). The two "characterization" tests (within-R sign stability, strict monotonicity in R) are predicted to pass but are not asserted by REPORT.md; a failure there would itself be a finding about the contrasts, not a harness bug. Report-number tests predicted to pass if REPORT.md's six-decimal values are faithful to run_001.

FILE: reviews/audit_ab_mpb1b/audit_test_pump_matched.py
```python
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
```

FILE: reviews/audit_ab_mpb1b/audit_diagnostics.py
```python
# SPDX-License-Identifier: Apache-2.0
"""Audit diagnostics for AB-MPB1B as JSON on stdout (optional caller-supplied output path, created with 'x').

Usage:
    python reviews/audit_ab_mpb1b/audit_diagnostics.py [output.json]

Same environment variables as audit_test_pump_matched.py. Read-only on the frozen files. Written without
execution by Claude (Anthropic) for task pump-matched-audit-001; the numbers it prints are for Red to compare
with run_001/comparison.csv, REPORT.md (8.89e-16, 1.16e-14, 1.12e-14, the 30 s table) and pareto_receipt.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_test_pump_matched as audit  # noqa: E402


def subnormal_probe():
    try:
        got = audit.pump.operating_point(1e308, audit.pump.PumpCaps(1e-10, 1e-300))
    except ValueError as error:
        return {'outcome': 'rejected', 'error': str(error)}
    return {'outcome': 'returned', 'point': got,
            'pressure_relative_gap_to_cap': got['actual_pressure_kpa'] / 1e-10 - 1,
            'realized_power_is_zero': got['actual_hydraulic_power_mw'] == 0}


def main(argv):
    pump = audit.pump
    all_rows = audit.rows()
    throttled = audit.throttled_rows()
    q20 = pump.operating_point(20)['flow_ml_s']
    row_list = []
    for (name, ratio, duration), row in sorted(all_rows.items(), key=lambda item: item[0]):
        res = row['result']
        row_list.append({
            'condition': name, 'resistance_ratio': ratio, 'time_s': duration,
            'flow_ml_s': row['flow'], 'actual_pressure_kpa': row['pressure'],
            'actual_hydraulic_power_mw': row['power'], 'active_constraint': row['active'],
            'distal_wall_concentration': row['distal'], 'minimum_wall_concentration': row['minimum'],
            'distal_is_minimum': row['minimum'] == row['distal'],
            'consumed_umol': row['consumed'], 'net_wall_transfer_umol': row['net'],
            'steps': res['steps'], 'actual_dt': res['actual_dt'], 'exit_bound': res['exit_bound'],
            'max_oxygen_error': res['max_oxygen_error'], 'max_site_error': res['max_site_error'],
            'minimum_seen': res['minimum_seen']})
    pareto, witness = [], []
    for name in audit.NAMES:
        for duration in audit.TIMES:
            obj = {ratio: audit.objectives(all_rows[(name, ratio, duration)], duration) for ratio in audit.RATIOS}
            nd = audit.nondominated(obj)
            pareto.append({'condition': name, 'time_s': duration,
                           'objectives_by_ratio': {str(k): list(v) for k, v in obj.items()},
                           'nondominated_R_over_R0': nd,
                           'dominated_R_over_R0': [r for r in audit.RATIOS if r not in nd]})
            low, high = throttled[(name, duration)], all_rows[(name, 4, duration)]
            witness.append({'condition': name, 'time_s': duration,
                            'throttled_R0_caps_3kPa_3.2mW_objectives': list(audit.objectives(low, duration)),
                            'grid_R4_objectives': list(audit.objectives(high, duration)),
                            'flows_bitwise_equal': low['flow'] == high['flow'],
                            'states_bitwise_identical': low['amounts'] == high['amounts'],
                            'throttled_dominates_R4': audit.dominates(audit.objectives(low, duration),
                                                                      audit.objectives(high, duration))})
    within, penalty = {}, {}
    for ratio in audit.RATIOS:
        for duration in audit.TIMES:
            base = all_rows[('no_sites', ratio, duration)]
            for name in audit.NAMES[1:]:
                key = '%s|R%d|T%d' % (name, ratio, duration)
                within[key] = all_rows[(name, ratio, duration)]['distal'] - base['distal']
                if ratio != 1:
                    penalty[key] = all_rows[(name, ratio, duration)]['distal'] - all_rows[('no_sites', 1, duration)]['distal']
    admitted = sys.modules.get('admitted')
    saved_a = None
    if hasattr(admitted, 'A_ROWS'):
        worst = 0.0
        for a_row in admitted.A_ROWS:
            row = all_rows[(a_row['condition'], 1, a_row['time_s'])]
            worst = max(worst, max(abs(x - y) for x, y in zip(row['amounts'], a_row['final_amounts'])))
        saved_a = {'max_matched_A_state_difference_umol': worst, 'a_row_keys': sorted(admitted.A_ROWS[0].keys())}
    record = {
        'task': 'pump-matched-audit-001',
        'pump_dir': str(audit.PUMP_DIR),
        'a_source': audit.A_SOURCE,
        'python': sys.version,
        'q_at_r20': {'value': q20, 'equals_float_0.4': q20 == 0.4, 'ulps_from_0.4': (q20 - 0.4) / math.ulp(0.4)},
        'operating_points': {str(r): pump.operating_point(r) for r in (20, 40, 45, 80)},
        'rows': row_list,
        'max_oxygen_error_umol': max(r['result']['max_oxygen_error'] for r in all_rows.values()),
        'max_site_error_umol': max(r['result']['max_site_error'] for r in all_rows.values()),
        'minimum_seen': min(r['result']['minimum_seen'] for r in all_rows.values()),
        'saved_A_comparison': saved_a,
        'pareto_groups': pareto,
        'throttled_witness': witness,
        'within_resistance_distal_differences': within,
        'penalty_distal_differences_vs_no_sites_R0': penalty,
        'subnormal_probe_R1e308_D1e-10_P1e-300': subnormal_probe(),
    }
    text = json.dumps(record, indent=1, sort_keys=True)
    if len(argv) > 1:
        with open(argv[1], 'x', encoding='utf-8') as handle:
            handle.write(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
```

FILE: reviews/audit_ab_mpb1b/pump_subnormal_guard.patch
```diff
--- a/validation/ab_mpb1b/pump.py
+++ b/validation/ab_mpb1b/pump.py
@@ -31,7 +31,9 @@
         actual_pressure=r*q
         # This order avoids forming Q**2 as an unnecessarily large intermediate.
         actual_power=actual_pressure*q
         if not math.isfinite(actual_pressure) or not math.isfinite(actual_power):raise ValueError('Operating point exceeds finite arithmetic')
+        # Audit pump-matched-audit-001: subnormal or zero realized quantities cannot carry rounding-level residuals.
+        if min(q,actual_pressure,actual_power)<2.2250738585072014e-308:raise ValueError('Operating point is below the normal float range')
         if math.isclose(pressure_flow,power_flow,rel_tol=4e-15,abs_tol=0):active='both'
         else:active='pressure' if pressure_flow<power_flow else 'power'
     return {'resistance_kpa_s_per_ml':r,'pressure_cap_kpa':pressure,'hydraulic_power_cap_mw':power,'flow_ml_s':q,'actual_pressure_kpa':actual_pressure,'actual_hydraulic_power_mw':actual_power,'active_constraint':active}
```

**Patch status.** Optional, Low severity (F3), for a future B.1 revision only. Do not apply to the frozen artifact: it changes the pump.py hash bound by IMPLEMENTATION_FREEZE.json and green.json. Dry-run first (`patch -p1 --dry-run`); line numbers may shift if the real file's docstring differs by a blank line. By static inspection it changes no outcome of the 17 frozen tests (all their non-zero-cap cases have normal floats; the zero-cap branch is bypassed; the existing unrepresentable case still raises). Recommended study.py change (not patched, since study.py and run_001 are frozen): in `contrast()`, add `'matched_realized_power': math.isclose(row['actual_hydraulic_power_mw'], base_power, rel_tol=3e-14)` and the analogous pressure flag, reading the A baseline's flow from `base['configuration']['flow']` rather than the literal `.4`.

## 5. Report sentences: supported or not

**Supported by the code as written (static):**
- "Q=min(12/R,sqrt(3.2/R)) mL/s. The crossover is R=45." — pump.py; test_transition_r45.
- "The three R values 20,40,80 produce Q=0.4,0.2828427,0.15 … pressure 8,11.3137,12 kPa and hydraulic power 3.2,3.2,1.8 mW … first two power-limited; the last pressure-limited." — algebra verified; R=20 and 80 tested, R=40 only by my added test.
- "Equal caps do not mean equal realized pressure and power." — follows from the min rule; tested.
- "Each resistance is crossed with [three conditions]"; "All 63 contrasts and 27 complete state rows are retained, not selected by favorable ranking." — study.py loops, asserts and writes everything.
- "The same-free case begins with 4.4 micromoles … versus 2.4 … 83.33%"; "The equal-total case changes the initial free/bound partition." — STUDY_DESIGN.json, uniform_state, study asserts.
- "Distal/spatial-minimum concentration is measured at a named time"; "Consumed oxygen and signed net wall transfer are separate bookkeeping endpoints." — study.py endpoint code.
- "Pump efficiency, electrical power, heat generation … are absent"; "Geometry is fixed and resistance independent of mesh count." — no such terms exist; R is a scalar input; test_mesh_independence.
- "Flow ablation, inventory and resistance effects are labeled separately." — four contrast kinds.

**Supported only by run output (mechanism in code; value not derivable statically; reproducible by the supplied tests given the frozen kernel):**
- "Nine matched-flow rows reproduce A to a maximum full-state difference of 8.89e-16" (test bound 2e-14); "Largest oxygen/site conservation residuals were 1.16e-14 and 1.12e-14" (guard 1e-11); "all observed state minima were nonnegative" (guard −1e-14).
- The R=40 and R=80 columns of the 30 s table and the 10 s pair 0.439342/0.462459 (`test_report_30s_table_reproduced`, `test_report_10s_direction_example_reproduced`).
- "The full Python study took 1.194 seconds under a 60-second child-process deadline"; "17 passing tests" (17 methods verified; passing is a run claim); "All 33 admitted A files remained unchanged" (verify_a mechanism exists).

**Not supported, or imprecise:**
- "Resistance can change even the direction of a selected comparison" — the sign change is of a contrast that differs in inventory (+2.0 µmol), in flow through the matched-power law, and additionally through the pressure-cap regime switch at R=80 (F2); "resistance" alone is not isolated. The following hedge covers inventory and the assigned penalty but not the regime switch.
- "The existing implementation was unchanged" — rests on freeze files absent from the bundle; `ProvenanceTests` verifies the bundle hashes instead.
- Coordinator review B: "At all nine groups R/R0=1 and 4 remain nondominated … R/R0=2 is dominated by 1" — reproducible in principle, but the pattern is implied by the pump rule plus monotone transport and R/R0=4 is dominated by an off-grid throttled point (F1); the sentence should not be read as a transport result.

## 6. Left unimplemented / not verifiable

- No audit of the Pareto-generating script (absent); its conclusions are recomputed from fresh rows instead.
- No parsing or hash check of run_001/comparison.csv, numerical_receipt.json, FREEZE.json, IMPLEMENTATION_FREEZE.json, receipts/green.json (absent); Red should compare the diagnostics JSON rows with comparison.csv (schema per study.py `fields`).
- No patch to study.py or to the Pareto objectives (frozen; recommendation only).
- The shim loader does not verify the A pins or manifest (only the kernel hash is checked).
- No independent integrator or trajectory error bound (the coordinator's RK4 check is separate evidence; outside this task).

**Assumptions (labelled):** IEEE-754 binary64 with correctly rounded `/` and `sqrt` (CPython on mainstream hardware); the frozen pump.py and kernel are deterministic so recomputed rows equal run_001 bitwise; REPORT.md numbers are rounded to six decimals; the A receipt rows carry the keys used by study.py and test_pump.py; hand-computed digits in F3 (202402·2⁻¹⁰⁷⁴, −1.25e-6) are to be confirmed by the sandbox. All of this is computational research on a synthetic model; nothing here is empirical validation, a hardware recommendation, or a physiological claim.