#!/usr/bin/env python3
"""One-off build step: append the continuation block to the truncated first_leaf_oracle.py.

Usage: python oracle/splice_continuation.py <base.py> <continuation.txt>
Writes only to <base.py> (caller-supplied).  Refuses to run if the base file no
longer ends with the dangling '        for event' fragment (i.e. already spliced).
"""
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    base, cont = Path(sys.argv[1]), Path(sys.argv[2])
    text = base.read_text(encoding="utf-8")
    marker = "\n        for event"
    idx = text.rfind(marker)
    if idx < 0 or text[idx + 1:].strip() != "for event":
        raise SystemExit("Base file does not end with the truncated 'for event' line; already spliced?")
    base.write_text(text[:idx + 1] + cont.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"spliced {cont} into {base}")


if __name__ == "__main__":
    main()
