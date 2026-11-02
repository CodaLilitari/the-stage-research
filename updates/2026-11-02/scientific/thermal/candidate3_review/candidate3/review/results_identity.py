#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Line-ending-aware identity receipt for two text/JSON files (candidate 3 review; Claude, Anthropic).

Usage:
  python3 results_identity.py A B [--out receipt.json] [--force]

For each file: size, newline census (CRLF / bare LF / bare CR), raw SHA-256, SHA-256 after
CRLF->LF normalisation, SHA-256 after LF->CRLF translation of the normalised bytes.  Two files
written by the same program on Windows (text mode, CRLF) and on POSIX (LF) have equal normalised
hashes and crossed raw/translated hashes.  If the normalised bytes differ and both parse as JSON,
the first differing JSON path is reported (content difference, not line endings).
Standard library only; deterministic; no network; writes only --out.
Exit 0 iff the normalised bytes are identical; 1 if they differ; 2 on usage/refusal errors.
"""
import argparse
import hashlib
import json
import os
import platform
import sys


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normalise_lf(data):
    return data.replace(b"\r\n", b"\n")


def translate_crlf(data_lf):
    return data_lf.replace(b"\n", b"\r\n")


def newline_census(data):
    crlf = data.count(b"\r\n")
    return {"crlf": crlf, "bare_lf": data.count(b"\n") - crlf, "bare_cr": data.count(b"\r") - crlf}


def describe(path):
    with open(path, "rb") as fh:
        data = fh.read()
    lf = normalise_lf(data)
    return ({"path": path, "size": len(data), "newlines": newline_census(data),
             "sha256_raw": sha256(data), "sha256_lf_normalised": sha256(lf),
             "sha256_crlf_translated": sha256(translate_crlf(lf))}, lf)


def first_json_difference(x, y, path=()):
    """(path, x_value, y_value) of the first difference between two parsed JSON values, else None."""
    if type(x) is not type(y):
        return path, x, y
    if isinstance(x, dict):
        if list(x) != list(y):
            return path, "<keys %s>" % (list(x)[:8],), "<keys %s>" % (list(y)[:8],)
        for k in x:
            d = first_json_difference(x[k], y[k], path + (k,))
            if d is not None:
                return d
        return None
    if isinstance(x, list):
        for i in range(min(len(x), len(y))):
            d = first_json_difference(x[i], y[i], path + (i,))
            if d is not None:
                return d
        if len(x) != len(y):
            return path, "<len %d>" % len(x), "<len %d>" % len(y)
        return None
    return None if x == y else (path, x, y)


def compare(path_a, path_b):
    da, lfa = describe(path_a)
    db, lfb = describe(path_b)
    receipt = {"tool": "results_identity.py (candidate 3 review)", "python": platform.python_version(),
               "platform": platform.platform(), "a": da, "b": db,
               "raw_identical": da["sha256_raw"] == db["sha256_raw"],
               "lf_normalised_identical": lfa == lfb,
               "a_crlf_translated_equals_b_raw": da["sha256_crlf_translated"] == db["sha256_raw"],
               "b_crlf_translated_equals_a_raw": db["sha256_crlf_translated"] == da["sha256_raw"]}
    if not receipt["lf_normalised_identical"]:
        try:
            ja, jb = json.loads(lfa.decode("utf-8")), json.loads(lfb.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            receipt["json"] = {"parsed": False, "error": str(exc)}
        else:
            diff = first_json_difference(ja, jb)
            receipt["json"] = {"parsed": True, "equal": diff is None,
                               "first_difference": None if diff is None else
                               {"path": list(diff[0]), "a": repr(diff[1])[:200], "b": repr(diff[2])[:200]}}
            if diff is None:
                receipt["json"]["note"] = "same JSON content; byte difference is whitespace/formatting only"
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description="line-ending-aware SHA-256 identity receipt for two files")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    for p in (args.a, args.b):
        if not os.path.isfile(p):
            sys.stderr.write("error: not a file: %r\n" % p)
            return 2
    receipt = compare(args.a, args.b)
    text = json.dumps(receipt, indent=1, sort_keys=True)
    if args.out:
        if os.path.exists(args.out) and not args.force:
            sys.stderr.write("error: refusing to overwrite existing %r (use --force)\n" % args.out)
            return 2
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    print(text)
    print("verdict: %s" % ("LF-normalised bytes identical" if receipt["lf_normalised_identical"]
                           else "bytes differ after line-ending normalisation"))
    return 0 if receipt["lf_normalised_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
