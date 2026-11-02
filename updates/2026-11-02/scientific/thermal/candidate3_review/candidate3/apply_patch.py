#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply a unified diff by exact context matching; hunk line numbers (@@ ...) are ignored.

Usage:
  python3 apply_patch.py --patch candidate3.diff --base fixed/thermal_contract.py \
                         --out candidate3/thermal_contract.py [--force]

Each hunk's "old" text (context lines plus '-' lines) must occur exactly once at or after
the end of the previous hunk; otherwise the tool exits 1 and writes nothing.  Standard
library only; deterministic; no network; the only file written is --out (refused if it
exists, unless --force).  CRLF input is normalised to LF with a warning.  Prints the hunk
count, line counts and the SHA-256 of the written file as a receipt.
"""
import argparse
import hashlib
import os
import sys


def parse_hunks(text):
    hunks, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if cur is None and (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        if line.startswith("@@"):
            cur = {"old": [], "new": []}
            hunks.append(cur)
            continue
        if cur is None or line.startswith("\\"):      # preamble or "\ No newline at end of file"
            continue
        tag, body = (line[0], line[1:]) if line else (" ", "")
        if tag == " ":
            cur["old"].append(body)
            cur["new"].append(body)
        elif tag == "-":
            cur["old"].append(body)
        elif tag == "+":
            cur["new"].append(body)
        else:
            raise ValueError("unrecognised diff line: %r" % raw)
    if not hunks:
        raise ValueError("no hunks found in patch")
    return hunks


def apply_hunks(lines, hunks):
    out, pos = list(lines), 0
    for i, h in enumerate(hunks, 1):
        old, n = h["old"], len(h["old"])
        hits = [j for j in range(pos, len(out) - n + 1) if out[j:j + n] == old]
        if len(hits) != 1:
            raise ValueError("hunk %d: expected exactly one context match at/after line %d, found %d"
                             % (i, pos + 1, len(hits)))
        j = hits[0]
        out[j:j + n] = h["new"]
        pos = j + len(h["new"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="context-matching unified-diff applier")
    ap.add_argument("--patch", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    with open(args.patch, "r", encoding="utf-8", newline="") as fh:
        patch_text = fh.read()
    with open(args.base, "r", encoding="utf-8", newline="") as fh:
        base_text = fh.read()
    if "\r\n" in base_text:
        sys.stderr.write("warning: CRLF line endings in base normalised to LF\n")
        base_text = base_text.replace("\r\n", "\n")
    had_nl = base_text.endswith("\n")
    lines = base_text.split("\n")
    if had_nl:
        lines.pop()
    try:
        new_lines = apply_hunks(lines, parse_hunks(patch_text))
    except ValueError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    if os.path.exists(args.out) and not args.force:
        sys.stderr.write("error: refusing to overwrite existing %r (use --force)\n" % args.out)
        return 1
    data = "\n".join(new_lines) + ("\n" if had_nl else "")
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    print("applied %d hunk(s): %d -> %d lines; sha256(out) = %s"
          % (len(parse_hunks(patch_text)), len(lines), len(new_lines),
             hashlib.sha256(data.encode("utf-8")).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
