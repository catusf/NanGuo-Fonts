"""Rewrite embedded copyright year in TTF name table.

Updates name IDs 0 (copyright) and 3 (unique font identifier) by replacing
OLD_YEAR with NEW_YEAR everywhere they appear in the encoded record string.
Works across all platform/encoding rows for each ID. Other name records are
left untouched.

Usage:
  python scripts/update_ttf_year.py [--dir output] [--old 2025] [--new 2026]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from fontTools.ttLib import TTFont

NAME_IDS_WITH_YEAR = (0, 3)  # 0: Copyright, 3: Unique font identifier


def rewrite_one(path: pathlib.Path, old: str, new: str) -> int:
    tt = TTFont(str(path))
    changes = 0
    for rec in tt["name"].names:
        if rec.nameID not in NAME_IDS_WITH_YEAR:
            continue
        try:
            s = rec.toUnicode()
        except Exception:
            continue
        if old in s:
            rec.string = s.replace(old, new)
            changes += 1
    if changes:
        tt.save(str(path))
    tt.close()
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="output",
                    help="Directory containing the TTFs")
    ap.add_argument("--old", default="2025")
    ap.add_argument("--new", default="2026")
    args = ap.parse_args()

    root = pathlib.Path(args.dir)
    ttfs = sorted(root.glob("NanGuo*Pinyin-*.ttf"))
    if not ttfs:
        print(f"no TTFs found under {root}/", file=sys.stderr)
        return 1

    total = 0
    for p in ttfs:
        n = rewrite_one(p, args.old, args.new)
        marker = "ok " if n else "-- "
        print(f"  [{marker}] {p.name}  ({n} record(s) updated)")
        total += n
    print(f"\nRewrote {total} record(s) across {len(ttfs)} TTF(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
