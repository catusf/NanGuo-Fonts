"""Compare FZKTPY-1 (from .ttc) with good/NanGuoPinyin-1.ttf.

Prints a side-by-side report of:
- header / OS/2 / hhea metrics
- name table records
- table list + sizes
- cmap structure
- glyph-count, PUA range usage
- a sample CJK glyph (composite structure) and a sample PUA ruby glyph
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from fontTools.ttLib import TTFont, TTCollection

# Force utf-8 on Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
TTC_PATH = ROOT / "data" / "FangZhengKaiTiPinYinZiKu-1.ttc"
GOOD_PATH = ROOT / "good" / "NanGuoPinyin-1.ttf"


def load_refdata_variant(idx: int = 0) -> TTFont:
    coll = TTCollection(str(TTC_PATH))
    return coll.fonts[idx]


def header_block(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


def fmt_pair(label: str, a, b, width: int = 28) -> str:
    return f"{label:<{width}} | {str(a):<22} | {str(b)}"


def describe_metrics(f: TTFont) -> dict:
    head = f["head"]
    hhea = f["hhea"]
    os2 = f["OS/2"]
    return {
        "unitsPerEm": head.unitsPerEm,
        "xMin/yMin": f"{head.xMin}/{head.yMin}",
        "xMax/yMax": f"{head.xMax}/{head.yMax}",
        "macStyle": bin(head.macStyle),
        "hhea.ascent": hhea.ascent,
        "hhea.descent": hhea.descent,
        "hhea.lineGap": hhea.lineGap,
        "OS/2.sTypoAscender": os2.sTypoAscender,
        "OS/2.sTypoDescender": os2.sTypoDescender,
        "OS/2.sTypoLineGap": os2.sTypoLineGap,
        "OS/2.usWinAscent": os2.usWinAscent,
        "OS/2.usWinDescent": os2.usWinDescent,
        "OS/2.fsSelection": bin(os2.fsSelection),
        "  USE_TYPO_METRICS(7)": bool(os2.fsSelection & (1 << 7)),
        "OS/2.usWeightClass": os2.usWeightClass,
        "OS/2.usWidthClass": os2.usWidthClass,
        "OS/2.fsType": os2.fsType,
        "OS/2.achVendID": getattr(os2, "achVendID", ""),
        "OS/2.panose.familyType": getattr(os2.panose, "bFamilyType", "?"),
    }


def describe_tables(f: TTFont) -> list[str]:
    return sorted(f.keys())


def describe_name(f: TTFont) -> list[tuple]:
    rows = []
    for r in f["name"].names:
        try:
            txt = r.toUnicode()
        except Exception:
            txt = repr(r.string)
        rows.append((r.nameID, r.platformID, r.platEncID, r.langID, txt))
    rows.sort()
    return rows


def describe_cmap(f: TTFont) -> dict:
    cmap = f["cmap"]
    out = {"subtables": []}
    for st in cmap.tables:
        out["subtables"].append(
            (st.platformID, st.platEncID, st.format, len(st.cmap))
        )
    best = cmap.getBestCmap() or {}
    cps = sorted(best.keys())
    out["best_cmap_size"] = len(cps)
    if cps:
        out["best_min_cp"] = f"U+{cps[0]:04X}"
        out["best_max_cp"] = f"U+{cps[-1]:04X}"
        pua = [c for c in cps if 0xE000 <= c <= 0xF8FF]
        cjk = [c for c in cps if 0x4E00 <= c <= 0x9FFF]
        ascii_lat = [c for c in cps if c < 0x80]
        out["count_ascii<0x80"] = len(ascii_lat)
        out["count_pua_BMP"] = len(pua)
        out["count_CJK_unified"] = len(cjk)
        if pua:
            out["pua_first_cps"] = ",".join(f"U+{c:04X}" for c in pua[:5])
            out["pua_last_cps"] = ",".join(f"U+{c:04X}" for c in pua[-5:])
    return out


def describe_glyf(f: TTFont) -> dict:
    out = {}
    out["numGlyphs"] = f["maxp"].numGlyphs
    out["has_glyf"] = "glyf" in f
    out["has_CFF "] = "CFF " in f
    out["has_CFF2"] = "CFF2" in f
    out["has_GSUB"] = "GSUB" in f
    out["has_GPOS"] = "GPOS" in f
    out["has_post"] = "post" in f
    if "post" in f:
        out["post.formatType"] = f["post"].formatType
    return out


def sample_composite(f: TTFont, sample_chars: str = "你好行家中") -> list[str]:
    """For each char in `sample_chars`, dump composite structure if present."""
    out = []
    cmap = f["cmap"].getBestCmap() or {}
    glyf = f["glyf"] if "glyf" in f else None
    if not glyf:
        return ["(no glyf table)"]
    for ch in sample_chars:
        cp = ord(ch)
        gname = cmap.get(cp)
        if not gname:
            out.append(f"  {ch} U+{cp:04X}  (not in cmap)")
            continue
        g = glyf[gname]
        if g.isComposite():
            parts = []
            for c in g.components:
                parts.append(c.glyphName)
            out.append(
                f"  {ch} U+{cp:04X}  glyph={gname}  composite, {len(g.components)} parts: {parts}"
            )
        else:
            n = g.numberOfContours if hasattr(g, "numberOfContours") else "?"
            out.append(f"  {ch} U+{cp:04X}  glyph={gname}  simple, contours={n}")
    return out


def list_pua_glyph_names(f: TTFont, limit: int = 20) -> list[str]:
    cmap = f["cmap"].getBestCmap() or {}
    pua_items = [
        (cp, gn) for cp, gn in cmap.items() if 0xE000 <= cp <= 0xF8FF
    ]
    pua_items.sort()
    return [f"  U+{cp:04X} -> {gn}" for cp, gn in pua_items[:limit]]


def main() -> int:
    if not TTC_PATH.exists():
        print(f"missing: {TTC_PATH}", file=sys.stderr)
        return 1
    if not GOOD_PATH.exists():
        print(f"missing: {GOOD_PATH}", file=sys.stderr)
        return 1

    fzk = load_refdata_variant(0)
    good = TTFont(str(GOOD_PATH))

    header_block("FILES")
    print(fmt_pair("path", "FZKTPY-1 (ttc[0])", str(GOOD_PATH.name)))

    header_block("HEAD / OS/2 / hhea METRICS")
    ma = describe_metrics(fzk)
    mb = describe_metrics(good)
    keys = list(ma.keys())
    for k in keys:
        print(fmt_pair(k, ma.get(k), mb.get(k)))

    header_block("TABLES PRESENT")
    ta = describe_tables(fzk)
    tb = describe_tables(good)
    only_a = sorted(set(ta) - set(tb))
    only_b = sorted(set(tb) - set(ta))
    common = sorted(set(ta) & set(tb))
    print(f"FZKTPY-1 tables ({len(ta)}): {ta}")
    print()
    print(f"NanGuoPinyin-1 tables ({len(tb)}): {tb}")
    print()
    print(f"Only in FZKTPY-1: {only_a}")
    print(f"Only in NanGuoPinyin-1: {only_b}")
    print(f"Common: {len(common)}")

    header_block("GLYF / OUTLINES")
    ga = describe_glyf(fzk)
    gb = describe_glyf(good)
    for k in ga.keys():
        print(fmt_pair(k, ga.get(k), gb.get(k)))

    header_block("NAME TABLE")
    print("FZKTPY-1:")
    for r in describe_name(fzk):
        nameID, plat, enc, lang, txt = r
        snippet = txt if len(txt) < 70 else (txt[:67] + "...")
        print(f"  id={nameID:<3} plat={plat} enc={enc} lang=0x{lang:04X}: {snippet!r}")
    print()
    print("NanGuoPinyin-1:")
    for r in describe_name(good):
        nameID, plat, enc, lang, txt = r
        snippet = txt if len(txt) < 70 else (txt[:67] + "...")
        print(f"  id={nameID:<3} plat={plat} enc={enc} lang=0x{lang:04X}: {snippet!r}")

    header_block("CMAP")
    ca = describe_cmap(fzk)
    cb = describe_cmap(good)
    print("FZKTPY-1:")
    for k, v in ca.items():
        print(f"  {k}: {v}")
    print()
    print("NanGuoPinyin-1:")
    for k, v in cb.items():
        print(f"  {k}: {v}")

    header_block("SAMPLE GLYPHS (composite structure for some CJK)")
    print("FZKTPY-1:")
    for line in sample_composite(fzk):
        print(line)
    print()
    print("NanGuoPinyin-1:")
    for line in sample_composite(good):
        print(line)

    header_block("FIRST 20 PUA -> GLYPH NAMES")
    print("FZKTPY-1:")
    for line in list_pua_glyph_names(fzk):
        print(line)
    print()
    print("NanGuoPinyin-1:")
    for line in list_pua_glyph_names(good):
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
