"""Patch NanGuo*Pinyin TTFs so Word/PowerPoint can render them.

Diagnosis (via byte-level diff against good/NanGuoPinyin-1.ttf, the known-
working reference):

  * post table is format 2.0 with 10,305 glyph names containing dots like
    `uni554A.base`. The `uniXXXX` AGL prefix on these names does NOT match
    the codepoint they actually cmap from (e.g. U+4E00 cmaps to a glyph
    composed of `uni2F00.base`+ruby). The working reference uses post
    format 3.0 (no glyph names stored) which side-steps any AGL-strict
    validation that DirectWrite/Office may apply.

  * maxp.maxCompositePoints is under-reported (BAD=318 vs GOOD=430).
    Renderers that use this for buffer sizing can refuse to draw glyphs
    whose actual point count exceeds the declared maximum.

This script rewrites each NanGuo*Pinyin-*.ttf so post becomes format 3.0
and maxp is recomputed. Other tables are left untouched.

Usage:
    python scripts/fix_post_table.py [INPUT_DIR] [OUTPUT_DIR]

Defaults: INPUT_DIR=output, OUTPUT_DIR=output. By default each file is
rewritten with a .fixed.ttf suffix next to the original; pass --in-place
to overwrite originals (a .bak copy is made first).
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent


def strip_post_glyph_names(tt: TTFont) -> None:
    """Convert post table to format 3.0 (no glyph names stored)."""
    post = tt["post"]
    post.formatType = 3.0
    # Clear format-2.0 specific fields so fontTools writes a 32-byte header only.
    for attr in ("extraNames", "mapping", "glyphOrder"):
        if hasattr(post, attr):
            try:
                delattr(post, attr)
            except AttributeError:
                pass


def fix_typo_ascender(tt: TTFont) -> None:
    """Set OS/2.sTypoAscender high enough to clear the ruby (matches GOOD).

    GOOD has sTypoAscender=1315 at UPM=1000 (≈ 1.315 × UPM). BAD has 880,
    which is below the ruby's top edge. We push to 1.315 × UPM so any
    application that consults sTypoAscender for line layout has room for
    the ruby above the baseline.
    """
    os2 = tt["OS/2"]
    upm = tt["head"].unitsPerEm
    target = round(1.315 * upm)
    if os2.sTypoAscender < target:
        os2.sTypoAscender = target


def rename_family(tt: TTFont, suffix: str) -> None:
    """Append a suffix to family-name records so Windows treats this as a
    new font (bypasses the font cache that may be serving a stale, broken
    version under the same name)."""
    name = tt["name"]
    # name records to suffix: 1 (family), 4 (full name), 6 (PostScript), 7 (preferred),
    # 16 (typographic family), 17 (typographic subfamily — leave), 3 (unique ID)
    target_ids = {1, 4, 6, 7, 16}
    for rec in list(name.names):
        if rec.nameID not in target_ids:
            continue
        s = str(rec)
        if rec.nameID == 6:
            # PostScript name: no spaces, append clean
            new_s = s + suffix.replace(" ", "")
        else:
            new_s = s + " " + suffix
        rec.string = new_s.encode("utf-16-be") if rec.platformID == 3 else new_s.encode("mac-roman", errors="replace")


def recalc_maxp(tt: TTFont) -> None:
    """Force fontTools to recompute maxp from the actual glyf contents."""
    # Touching glyf with recalcBBoxes also triggers maxp recalc on save when
    # we set head.indexToLocFormat untouched; easier to compute explicitly.
    glyf = tt["glyf"]
    maxp = tt["maxp"]

    max_pts = 0
    max_ctrs = 0
    max_comp_pts = 0
    max_comp_ctrs = 0
    max_comp_elems = 0
    max_comp_depth = 0

    def composite_points_and_contours(g, depth):
        nonlocal max_comp_depth
        max_comp_depth = max(max_comp_depth, depth)
        total_pts = 0
        total_ctrs = 0
        for c in g.components:
            sub = glyf[c.glyphName]
            if sub.isComposite():
                p, ct = composite_points_and_contours(sub, depth + 1)
            else:
                p = len(sub.coordinates) if hasattr(sub, "coordinates") and sub.coordinates is not None else 0
                ct = sub.numberOfContours if sub.numberOfContours > 0 else 0
            total_pts += p
            total_ctrs += ct
        return total_pts, total_ctrs

    for gname in tt.getGlyphOrder():
        g = glyf[gname]
        if g.isComposite():
            n_elems = len(g.components)
            max_comp_elems = max(max_comp_elems, n_elems)
            pts, ctrs = composite_points_and_contours(g, 1)
            max_comp_pts = max(max_comp_pts, pts)
            max_comp_ctrs = max(max_comp_ctrs, ctrs)
        elif g.numberOfContours > 0:
            pts = len(g.coordinates) if hasattr(g, "coordinates") and g.coordinates is not None else 0
            max_pts = max(max_pts, pts)
            max_ctrs = max(max_ctrs, g.numberOfContours)

    maxp.maxPoints = max_pts
    maxp.maxContours = max_ctrs
    maxp.maxCompositePoints = max_comp_pts
    maxp.maxCompositeContours = max_comp_ctrs
    maxp.maxComponentElements = max_comp_elems
    maxp.maxComponentDepth = max(maxp.maxComponentDepth, max_comp_depth)


def strip_layout_tables(tt: TTFont) -> list[str]:
    """Drop GSUB+GPOS+GDEF+BASE+STAT. Returns list of removed tags.

    These tables encode glyph-ID-based lookups (substitutions, mark
    positioning, glyph classifications). When the build script preserves
    them from the source font verbatim but reorders the glyph table, the
    IDs point at the wrong glyphs and DirectWrite renders garbage (often
    invisible-mark behavior for what should be CJK characters).
    """
    removed: list[str] = []
    for tag in ("GSUB", "GPOS", "GDEF", "BASE", "STAT"):
        if tag in tt:
            del tt[tag]
            removed.append(tag)
        if tag in tt.reader.tables:
            del tt.reader.tables[tag]
            if tag not in removed:
                removed.append(tag)
    return removed


def fix_one(src: pathlib.Path, dst: pathlib.Path, rename_suffix: str | None = None,
            strip_layout: bool = False) -> dict:
    tt = TTFont(str(src))

    # Touch only the tables we plan to modify. Leave vhea/vmtx as raw bytes
    # because vmtx is corrupted (in both GOOD and BAD), and compiling vhea
    # triggers a recalc that re-reads vmtx and explodes. GOOD ships with the
    # same broken vmtx and renders in Word, so leaving the raw bytes alone
    # is safe.
    tt["post"]
    tt["maxp"]
    tt["OS/2"]
    tt["name"]
    tt["glyf"]  # needed for maxp recalc walks

    before = {
        "post.formatType": tt["post"].formatType,
        "post.size_estimate": len(tt.reader["post"]),
        "maxp.maxCompositePoints": tt["maxp"].maxCompositePoints,
        "OS/2.sTypoAscender": tt["OS/2"].sTypoAscender,
    }

    strip_post_glyph_names(tt)
    fix_typo_ascender(tt)
    recalc_maxp(tt)
    layout_removed: list[str] = []
    if strip_layout:
        layout_removed = strip_layout_tables(tt)
    if rename_suffix:
        rename_family(tt, rename_suffix)

    tt.save(str(dst))
    tt.close()

    # Re-open and report new state
    after_tt = TTFont(str(dst), lazy=True)
    after = {
        "post.formatType": after_tt["post"].formatType,
        "post.size_actual": len(after_tt.reader["post"]),
        "maxp.maxCompositePoints": after_tt["maxp"].maxCompositePoints,
        "OS/2.sTypoAscender": after_tt["OS/2"].sTypoAscender,
    }
    after_tt.close()
    return {"before": before, "after": after, "layout_removed": layout_removed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_dir", nargs="?", default="output", type=pathlib.Path)
    ap.add_argument("output_dir", nargs="?", default=None, type=pathlib.Path)
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite originals (saves a .bak first)")
    ap.add_argument("--rename", metavar="SUFFIX", default=None,
                    help="append SUFFIX to family/full/PostScript names. Use to "
                         "bypass Windows font cache (e.g. --rename Test2)")
    ap.add_argument("--strip-layout", action="store_true",
                    help="also drop GSUB+GPOS+GDEF (layout tables reference "
                         "source-font glyph IDs that no longer match after the "
                         "build's reordering — strip to test the hypothesis)")
    args = ap.parse_args()

    in_dir = (ROOT / args.input_dir) if not args.input_dir.is_absolute() else args.input_dir
    out_dir = args.output_dir if args.output_dir else in_dir
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ttfs = sorted(p for p in in_dir.glob("NanGuo*Pinyin-*.ttf") if ".fixed" not in p.name)
    if not ttfs:
        print(f"no NanGuo*Pinyin-*.ttf in {in_dir}", file=sys.stderr)
        return 1

    print(f"Input:  {in_dir}")
    print(f"Output: {out_dir}")
    print()

    for src in ttfs:
        if args.in_place:
            backup = src.with_suffix(".ttf.bak")
            if not backup.exists():
                shutil.copy2(src, backup)
            dst = src
        else:
            dst = out_dir / (src.stem + ".fixed.ttf")
        print(f"  fixing {src.name} -> {dst.name}")
        info = fix_one(src, dst, rename_suffix=args.rename, strip_layout=args.strip_layout)
        b, a = info["before"], info["after"]
        print(f"    post: format {b['post.formatType']} ({b['post.size_estimate']} B) "
              f"-> format {a['post.formatType']} ({a['post.size_actual']} B)")
        print(f"    maxp.maxCompositePoints: {b['maxp.maxCompositePoints']} -> {a['maxp.maxCompositePoints']}")
        print(f"    OS/2.sTypoAscender: {b['OS/2.sTypoAscender']} -> {a.get('OS/2.sTypoAscender', '?')}")
        if info["layout_removed"]:
            print(f"    layout tables removed: {info['layout_removed']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
