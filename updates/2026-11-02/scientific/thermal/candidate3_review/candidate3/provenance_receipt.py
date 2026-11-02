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
