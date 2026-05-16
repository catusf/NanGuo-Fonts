"""Build a wght-axis variable font per cmap variant.

Inputs (per variant i = 1..6):
  output/NanGuoSansPinyin-{i}.ttf      (master at wght=400)
  output/NanGuoSansPinyin-{i}-Bold.ttf (master at wght=700)

Output:
  output/NanGuoSansPinyin-{i}[wght].ttf

Variable-font compatibility requirements (fontTools.varLib will fail loudly
if any master breaks them):
  - identical glyph set and order
  - per glyph: same number of contours and same point count per contour
  - same component structure for composites
  - identical cmap (this is given since both masters are the same variant)

Usage:
  python scripts/build_variable.py                 # all 6 variants
  python scripts/build_variable.py --only 1        # smoke-test variant 1
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import traceback

from fontTools.designspaceLib import (
    DesignSpaceDocument, AxisDescriptor, SourceDescriptor)
from fontTools.ttLib import TTFont
from fontTools.varLib import build as build_vf

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
FAMILY = "NanGuoSansPinyin"

# Tables to strip from masters before merging.
#   BASE — Regular/Bold encode baseline coords in incompatible formats.
#   GPOS/GSUB/GDEF — OT layout tables differ between weights (Bold has more
#     kerning lookups). Not load-bearing for our font: the cmap maps each
#     codepoint directly to a composite glyph; no shaping/positioning runs.
STRIP_TABLES = ("BASE", "GPOS", "GSUB", "GDEF")


def _load_clean(path: pathlib.Path) -> TTFont:
    tt = TTFont(str(path))
    for tag in STRIP_TABLES:
        if tag in tt:
            del tt[tag]
    return tt


def build_one(variant: int) -> tuple[bool, str]:
    reg = OUT / f"{FAMILY}-{variant}.ttf"
    bld = OUT / f"{FAMILY}-{variant}-Bold.ttf"
    for p in (reg, bld):
        if not p.exists():
            return False, f"missing master: {p.name}"

    ds = DesignSpaceDocument()
    ax = AxisDescriptor()
    ax.name = "Weight"; ax.tag = "wght"
    ax.minimum = 400; ax.default = 400; ax.maximum = 700
    ds.addAxis(ax)
    for path, loc in [(reg, 400), (bld, 700)]:
        sd = SourceDescriptor()
        sd.font = _load_clean(path)
        sd.location = {"Weight": loc}
        ds.addSource(sd)

    try:
        vf, _, _ = build_vf(ds)
    except Exception as e:
        return False, f"varLib.build raised {type(e).__name__}: {e}"

    out_path = OUT / f"{FAMILY}-{variant}[wght].ttf"
    vf.save(str(out_path))
    return True, f"wrote {out_path.name} ({out_path.stat().st_size/1e6:.2f} MB)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, help="Build a single variant (1..6)")
    args = ap.parse_args()

    variants = [args.only] if args.only else list(range(1, 7))
    rc = 0
    for v in variants:
        print(f"[variant {v}]", end=" ", flush=True)
        ok, msg = build_one(v)
        print(msg)
        if not ok:
            rc = 1
            # On first failure during smoke test, dump traceback
            if args.only:
                traceback.print_exc()
    return rc


if __name__ == "__main__":
    sys.exit(main())
