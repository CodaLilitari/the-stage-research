# SPDX-License-Identifier: MIT
"""CLI: run the GW-ASYNC0 design check for one or all variants.

Writes a JSON report only to the caller-supplied --output path; prints a text summary.
Example: python -m gateway_modelcheck.run_check --variant all --depth 12 --output report.json
"""
from __future__ import annotations

import argparse
import sys

from .checker import check, format_report, report_json
from .model import EXPECTED_VIOLATIONS, VARIANTS


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', default='all', help='variant name or "all"')
    p.add_argument('--depth', type=int, default=12)
    p.add_argument('--max-states', type=int, default=200000)
    p.add_argument('--output', default=None, help='path for the JSON report (only file written)')
    args = p.parse_args(argv)
    names = sorted(VARIANTS) if args.variant == 'all' else [args.variant]
    reports = []
    mismatches = 0
    for name in names:
        if name not in VARIANTS:
            print('unknown variant %r; known: %s' % (name, ', '.join(sorted(VARIANTS))))
            return 2
        r = check(VARIANTS[name], args.depth, args.max_states, variant=name)
        reports.append(r)
        print(format_report(r))
        expected = EXPECTED_VIOLATIONS.get(name, set())
        got = set(r.counterexamples)
        if expected and not expected <= got:
            mismatches += 1
            print('  PREDICTION MISMATCH: expected %s not found' % sorted(expected - got))
        if not expected and got:
            mismatches += 1
            print('  PREDICTION MISMATCH: unexpected violations %s' % sorted(got))
        print()
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report_json(reports) + '\n')
        print('report written to %s' % args.output)
    print('prediction mismatches: %d' % mismatches)
    return 0 if mismatches == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
