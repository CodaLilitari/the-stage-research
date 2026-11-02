"""Re-run the executed checks of updates/2026-11-02 from the published layout.

Usage (from the update folder, in a disposable copy - several scripts write outputs next to themselves):
    python -B tools/reproduce_check.py [--long]
Standard library only. --long adds the 8-seed First Leaf harness (about 2-3 minutes).
Prints one line per step: name, exit code, seconds, unittest summary, and the outcome recorded on 2026-11-02.
"""
import os, re, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / 'scientific'
TMP = Path(tempfile.mkdtemp(prefix='stage-repro-'))
T, G, N = S / 'thermal', S / 'gateway', S / 'numerics'
STEPS = [  # (name, cwd, argv, extra PYTHONPATH entries, env, outcome recorded 2026-11-02)
 ('thermal fv1d tests', T / 'fv1d', ['-m', 'unittest', 'test_thermal_fv_transient'], [], {}, 'OK (28 tests)'),
 ('thermal radiation tests', T / 'radiation/validation/thermal_radiation', ['-m', 'unittest', 'test_thermal_radiation'], [T / 'radiation'], {}, 'OK (26 tests)'),
 ('thermal sensitivity tests', T / 'sensitivity/validation/thermal_sensitivity', ['-m', 'unittest', 'test_thermal_sensitivity', 'test_steady_closed_form', 'test_sampling'],
  [T / 'sensitivity', T / 'sensitivity/validation/thermal'], {'THERMAL_TRANSIENT_DIR': str(T / 'sensitivity')}, 'OK'),
 ('thermal peak-exact tests', T / 'peak_exact/validation/thermal_transient', ['-m', 'unittest', 'test_peak_exact'], [T / 'peak_exact'], {}, 'OK (17 tests)'),
 ('thermal layered oracle tests', T / 'layered_oracle/oracle', ['-m', 'unittest', 'test_layered_oracle'], [T / 'layered_oracle'], {}, 'OK (21 tests)'),
 ('thermal layered oracle cases', T / 'layered_oracle', ['oracle/layered_oracle.py', '--out', str(TMP / 'oracle.json')], [T / 'layered_oracle/oracle'], {}, '9 cases written'),
 ('thermal N-version cross-check tests', T / 'nversion/crosscheck', ['-m', 'unittest', 'test_nversion_crosscheck'], [], {}, 'OK (10 tests)'),
 ('thermal N-version cross-check (F2 fixed)', T / 'nversion/crosscheck',
  ['nversion_crosscheck.py', '--fv', str(T / 'fv1d/results/fv_suite.json'), '--oracle', str(TMP / 'oracle.json'),
   '--rad', str(T / 'radiation/results/rad_results.json'), '--steady', str(T / 'coda_dependencies/validation/thermal/reference_results.json'),
   '--lump2', str(T / 'coda_dependencies/validation/thermal_transient/study_results.json'), '--out', str(TMP / 'nv.json')], [], {}, 'OVERALL (judged tiers): PASS'),
 ('thermal hotspot 2-D tests', T / 'hotspot2d', ['-m', 'unittest', 'tests.test_hotspot2d'], [T / 'hotspot2d'], {}, 'OK (19 tests)'),
 ('thermal hotspot fix-003 convergence', T / 'hotspot2d', ['-m', 'unittest', 'tests.test_convergence_fix003'], [T / 'hotspot2d'], {}, 'FAILED (failures=2) - open issue'),
 ('thermal supervisor tests', T / 'supervisor/thermal_supervisor', ['-m', 'unittest', 'test_supervisor'], [T / 'supervisor'], {}, 'OK (30 tests, 1 skipped)'),
 ('thermal metamorphic suite, candidate 3', T / 'metamorphic', ['-m', 'unittest', 'tests.test_thermal_contract_metamorphic'], [T / 'metamorphic'],
  {'THERMAL_CONTRACT_PATH': str(T / 'metamorphic/thermal_contract_c3.py'), 'THERMAL_REFERENCE_PATH': str(T / 'metamorphic/thermal_reference.py')},
  'FAILED (failures=1, skipped=8) - open issue'),
 ('gateway integrated: 7 suites', G / 'integrated', ['-m', 'unittest', 'tests.test_gateway_conformance', 'tests.test_gateway_lifecycle', 'tests.test_relay_lifecycle',
  'tests.test_stage', 'tests.test_relay', 'tests.test_audit_first_leaf_v2', 'tests.test_gateway_regressions_v3'], [G / 'integrated/src'], {}, 'OK (128 tests, expected failures=4)'),
 ('gateway model checker tests', G / 'model_checker', ['-m', 'unittest', 'gateway_modelcheck.tests.test_checker'], [G / 'model_checker/src'], {}, 'OK'),
 ('First Leaf oracle tests', G / 'oracle_baseline/tests', ['-m', 'unittest', 'test_oracle'], [G / 'oracle_baseline/oracle', G / 'oracle_baseline/src', G / 'oracle_baseline'], {}, 'OK (32 tests, 2 skipped)'),
 ('SITE0 audit vs revised_v1', N / 'site0_audit/validation/site0/revised_v1', ['-m', 'unittest', 'test_site0_repair_audit'], [],
  {'SITE0_ORIGINAL_PATH': str(N / 'site0_audit/site0.py')}, 'FAILED (failures=2, errors=1) - extreme scales, open issue'),
 ('SITE0 mutant blindness', N / 'site0_audit/validation/site0/revised_v1', ['audit_mutant_blindness.py'], [],
  {'SITE0_ORIGINAL_PATH': str(N / 'site0_audit/site0.py'), 'SITE0_FROZEN_TESTS_DIR': str(N / 'site0_audit/frozen_suites')}, 'frozen suites BLIND; audit module catches the mutant'),
 ('WEXACT0 audit', N / 'wexact0_audit/validation/wall_exchange_exact_audit', ['-m', 'unittest', 'test_wexact0_audit'], [N / 'wexact0_audit/validation/wall_exchange_exact'],
  {'WEXACT0_SOURCE_DIR': str(N / 'wexact0_audit/validation/wall_exchange_exact')}, 'OK (25 tests)'),
 ('pump audit (patched pump)', N / 'pump_audit/reviews/audit_ab_mpb1b', ['-m', 'unittest', 'audit_test_pump_matched'], [],
  {'AB_MPB1B_DIR': str(N / 'pump_audit/validation/ab_mpb1b'), 'AB_MPB1A_MODEL': str(N / 'pump_audit/validation/ab_mpb1a/model.py'), 'AB_MPB1B_EXPECT_PATCHED': '1'},
  'OK (22 tests, 2 skipped)'),
 ('release-observability study tests', N / 'release_observability', ['-m', 'unittest', 'test_release_study', 'test_release_review_additions'], [], {}, 'OK'),
]
if '--long' in sys.argv:
    STEPS.append(('First Leaf harness, 8 seeds, local', G / 'oracle_baseline', ['oracle/fl_harness.py', '--mode', 'local', '--seed-first', '20001', '--seed-count', '8', '--out', str(TMP / 'fl.json')],
                  [G / 'oracle_baseline/oracle', G / 'oracle_baseline/src'], {}, 'public_oracle all 0.139; random 1.038'))
def summary(txt, name=''):
    if 'harness' in name:
        v = re.findall(r'"all":\s*([0-9.]+)', txt)
        if len(v) >= 2: return f'public_oracle all {float(v[0]):.3f}; random all {float(v[1]):.3f}'
    if 'blindness' in name or 'cross-check (' in name or 'harness' in name or 'cases' in name:
        lines = [l for l in txt.strip().splitlines() if l.strip()]
        for pat in (r'OVERALL', r'frozen-suite blindness', r'"written"', r'public_oracle'):
            for l in reversed(lines):
                if re.search(pat, l): return l.strip()[:110]
    m = re.search(r'Ran (\d+) tests?', txt); f = re.search(r'FAILED \(([^)]*)\)', txt); ok = re.search(r'^OK( \([^)]*\))?\s*$', txt, re.M)
    if m: return f"ran={m.group(1)} " + (f'FAILED({f.group(1)})' if f else 'OK' + (ok.group(1) or '') if ok else '?')
    lines = [l for l in txt.strip().splitlines() if l.strip()]
    for pat in (r'OVERALL', r'frozen-suite blindness', r'"written"', r'"public_oracle"'):
        for l in reversed(lines):
            if re.search(pat, l): return l.strip()[:110]
    return lines[-1].strip()[:110] if lines else ''
print(f'reproduce_check from {ROOT.name}; python {sys.version.split()[0]}; temp outputs in a private temp dir')
for name, cwd, argv, extra, env, recorded in STEPS:
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join([str(cwd)] + [str(p) for p in extra])); e.update(env)
    t = time.time()
    try:
        r = subprocess.run([sys.executable, '-B'] + argv, cwd=cwd, env=e, capture_output=True, text=True, timeout=600); out = r.stderr + r.stdout; rc = r.returncode
    except subprocess.TimeoutExpired: out, rc = 'TIMEOUT', None
    print(f'{name:44s} exit={rc} {time.time()-t:6.1f}s | {summary(out, name)} | recorded: {recorded}', flush=True)
