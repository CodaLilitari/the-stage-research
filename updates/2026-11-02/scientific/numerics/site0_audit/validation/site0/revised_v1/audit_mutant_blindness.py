# SPDX-License-Identifier: Apache-2.0
# Provenance: Claude (Anthropic) for Red (Claude), tasks site0-repair-audit-001/-003.
"""Informational: run the frozen SITE0 suites and the audit module against a
complement-cancelling mutant of site0._roots.  Prints counts only; writes nothing.

Wave 11: Red's wave-10 run could not import the frozen suites
(ModuleNotFoundError), so the reported (2 run, 0 failures, 2 errors) was an import
artefact, not a blindness result.  This revision (a) looks for the frozen test
modules next to the ORIGINAL kernel (../ relative to this file) or in
$SITE0_FROZEN_TESTS_DIR, (b) imports them explicitly and reports INCONCLUSIVE if
that fails, (c) prints which site0 module the frozen tests actually bind to, so
the receipt shows whether they exercised the revised kernel.
    cd validation/site0/revised_v1 && python -B audit_mutant_blindness.py
Static prediction (Claude, wave 11): frozen suites blind (0 failures under the
mutant); audit module ~17 subtest failures under the mutant, 0 without it.
"""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))                       # revised kernel + audit module first
for extra in (os.environ.get('SITE0_FROZEN_TESTS_DIR'), str(HERE.parent)):
    if extra and extra not in sys.path:
        sys.path.append(extra)                      # frozen suites and helpers last

import site0                                        # noqa: E402  (revised kernel)
from test_site0_repair_audit import _roots_cancelling  # noqa: E402

FROZEN = ('test_site0', 'test_later_regression')
AUDIT = ('test_site0_repair_audit',)


def import_modules(names):
    loaded, missing = [], []
    for name in names:
        try:
            module = importlib.import_module(name)
        except Exception as exc:       # ImportError or a failure inside the module
            missing.append((name, repr(exc)))
            continue
        bound = getattr(module, 'site0', None)
        print('%s loaded from %s; binds site0 -> %s' % (
            name, getattr(module, '__file__', '?'),
            getattr(bound, '__file__', 'no module-level site0 attribute')))
        loaded.append(module)
    return loaded, missing


def run(modules):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module in modules:
        suite.addTests(loader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0).run(suite)
    return result.testsRun, len(result.failures), len(result.errors), len(result.skipped)


if __name__ == '__main__':
    print('revised kernel under test:', site0.__file__)
    frozen_modules, frozen_missing = import_modules(FROZEN)
    audit_modules, audit_missing = import_modules(AUDIT)
    with mock.patch.object(site0, '_roots', _roots_cancelling):
        frozen = run(frozen_modules) if frozen_modules else None
        audit = run(audit_modules) if audit_modules else None
    print('audit module under mutant (run, failures, errors, skipped):', audit)
    for name, err in frozen_missing + audit_missing:
        print('could not import', name, '->', err)
    if frozen is None or frozen_missing:
        print('frozen-suite blindness: INCONCLUSIVE (frozen modules not importable; '
              'copy test_site0.py, validation_helpers.py, mutants.py and '
              'test_later_regression.py next to this script or set '
              'SITE0_FROZEN_TESTS_DIR)')
    else:
        print('frozen suites under mutant (run, failures, errors, skipped):', frozen)
        print('frozen-suite blindness:',
              'BLIND (no failure or error under mutant)' if frozen[1] + frozen[2] == 0
              else 'DETECTS the mutant')
