"""Extract reference data from FangZhengKaiTiPinYinZiKu-1.ttc into _data/.

The TTC has 6 sub-fonts (FZKTPY01..06) representing six pinyin variants:

- Sub-font 0 (FZKTPY01): primary readings — every GB2312 CJK char is a
  composite of [base_outline_glyph, PUA_ruby_glyph]. The PUA glyph (named
  uniEXXX, codepoint U+E000–U+E7DA) renders the pinyin syllable visually.
- Sub-fonts 1–5: secondary..senary readings — heteronym alternates only.
  Composites use plain `glyphNNNNN` names for the ruby (not PUA-cmapped);
  non-heteronym chars map to uni3000 (space) to signal "no reading here".

UPM=256.

Outputs written to _data/:

  fzktpy_meta.json                 high-level structure of the TTC
  fzktpy_pua_glyphs.json           every PUA glyph with metrics (advance,
                                   LSB, bbox, numContours)
  fzktpy_cjk_composites.json       for each sub-font, CJK char ->
                                   composite components and offsets
  fzktpy_pua_syllable_map.json     PUA codepoint -> pinyin syllable
                                   (derived via pypinyin for chars that
                                   reference the PUA in sub-font 0)
  fzktpy_pua_syllable_conflicts.json  diagnostic: PUAs where chars
                                   referencing them disagree on the
                                   syllable per pypinyin (likely indicates
                                   pypinyin's primary differs from FZKTPY's,
                                   or a multi-reading PUA reused)

Run: python scripts/extract_fzktpy_data.py
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys
from collections import defaultdict

from fontTools.ttLib import TTCollection, TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _find_source() -> pathlib.Path:
    """Find FangZhengKaiTiPinYinZiKu-1.ttc — search common locations."""
    for candidate in (ROOT / "data" / "FangZhengKaiTiPinYinZiKu-1.ttc",
                      ROOT / "FangZhengKaiTiPinYinZiKu-1.ttc",
                      ROOT / "_data" / "FangZhengKaiTiPinYinZiKu-1.ttc"):
        if candidate.exists():
            return candidate
    raise SystemExit("FangZhengKaiTiPinYinZiKu-1.ttc not found in data/, _data/, or project root")


SOURCE = _find_source()

PUA_GLYPH_RE = re.compile(r"^uni([EF][0-9A-F]{3})$")
UNI_GLYPH_RE = re.compile(r"^uni([0-9A-F]{4,6})$")


def hex_key(cp: int) -> str:
    return f"0x{cp:04X}"


def glyph_metrics(tt: TTFont, glyph_name: str) -> dict:
    """Advance width, LSB, bbox, numContours for a given glyph."""
    hmtx = tt["hmtx"].metrics
    glyf = tt["glyf"]
    advance, lsb = hmtx.get(glyph_name, (0, 0))
    g = glyf[glyph_name]
    nc = g.numberOfContours
    if nc == 0:
        bbox = None
    else:
        try:
            bbox = {"xMin": g.xMin, "yMin": g.yMin, "xMax": g.xMax, "yMax": g.yMax}
        except AttributeError:
            bbox = None
    return {
        "glyph": glyph_name,
        "advance": advance,
        "lsb": lsb,
        "numContours": nc,
        "bbox": bbox,
    }


def composite_components(tt: TTFont, glyph_name: str) -> list[dict] | None:
    g = tt["glyf"][glyph_name]
    if not g.isComposite():
        return None
    return [
        {
            "name": c.glyphName,
            "x": int(getattr(c, "x", 0)),
            "y": int(getattr(c, "y", 0)),
            "flags": int(getattr(c, "flags", 0)),
        }
        for c in g.components
    ]


def main() -> int:
    DATA.mkdir(exist_ok=True)
    print(f"reading {SOURCE.relative_to(ROOT)} ...")
    ttc = TTCollection(str(SOURCE))
    n_sub = len(ttc.fonts)

    # --- meta + per-sub-font scan -----------------------------------------
    meta = {
        "source_file": SOURCE.name,
        "extracted_at": datetime.date.today().isoformat(),
        "extractor": "scripts/extract_fzktpy_data.py",
        "n_sub_fonts": n_sub,
        "sub_fonts": [],
    }

    pua_glyphs: dict[str, dict] = {}  # only from sub-font 0
    cjk_composites: dict[str, dict] = {str(i): {} for i in range(n_sub)}

    for sub_idx, tt in enumerate(ttc.fonts):
        name1 = tt["name"].getName(1, 3, 1, 0x409) or tt["name"].getName(1, 1, 0, 0)
        name1 = str(name1) if name1 else f"sub{sub_idx}"
        cmap = tt.getBestCmap()
        upm = tt["head"].unitsPerEm
        num_glyphs = tt["maxp"].numGlyphs

        pua_cps = [cp for cp in cmap if 0xE000 <= cp <= 0xF8FF]
        cjk_cps = [cp for cp in cmap if 0x4E00 <= cp <= 0x9FFF]

        meta["sub_fonts"].append({
            "index": sub_idx,
            "name": name1,
            "unitsPerEm": upm,
            "numGlyphs": num_glyphs,
            "cmapEntries": len(cmap),
            "puaEntries": len(pua_cps),
            "cjkEntries": len(cjk_cps),
        })

        # PUA glyph metrics: only sub-font 0 carries cmap'd PUA glyphs
        if sub_idx == 0:
            for cp in sorted(pua_cps):
                gname = cmap[cp]
                pua_glyphs[hex_key(cp)] = glyph_metrics(tt, gname)
            print(f"  sub{sub_idx} ({name1}): extracted {len(pua_glyphs)} PUA glyphs")

        # CJK composites: every sub-font's view of each GB2312 char.
        # Filter out maps to uni3000 (space) which means "no reading at this slot".
        per_sub = cjk_composites[str(sub_idx)]
        empty_count = 0
        for cp in sorted(cjk_cps):
            gname = cmap[cp]
            if gname == "uni3000":
                empty_count += 1
                continue
            comps = composite_components(tt, gname)
            entry = {"glyph": gname}
            if comps is not None:
                entry["components"] = comps
                # If the second component is a uniEXXX, surface the PUA codepoint
                # since it's the deliverable for the build script.
                if len(comps) >= 2:
                    m = PUA_GLYPH_RE.match(comps[1]["name"])
                    if m:
                        entry["ruby_pua"] = f"0x{m.group(1)}"
            per_sub[hex_key(cp)] = entry
        print(f"  sub{sub_idx} ({name1}): {len(per_sub)} composite CJK glyphs, "
              f"{empty_count} mapped to uni3000 (no reading)")

    # --- derive PUA -> syllable map via pypinyin --------------------------
    print()
    print("deriving PUA -> syllable map from sub-font 0 composites + pypinyin ...")
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        print("  WARN: pypinyin not installed; skipping syllable derivation", file=sys.stderr)
        pua_syllable_map: dict[str, dict] = {}
        conflicts: dict[str, dict] = {}
    else:
        pua_to_pairs: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for cp_hex, entry in cjk_composites["0"].items():
            ruby_pua = entry.get("ruby_pua")
            if not ruby_pua:
                continue
            cp = int(cp_hex, 16)
            ch = chr(cp)
            syl_list = pinyin(ch, style=Style.TONE, heteronym=False)
            if not syl_list or not syl_list[0]:
                continue
            syllable = syl_list[0][0]
            pua_to_pairs[ruby_pua].append((ch, syllable))

        pua_syllable_map = {}
        conflicts = {}
        for pua_hex, pairs in pua_to_pairs.items():
            syllables = sorted({s for _, s in pairs})
            chars = sorted({c for c, _ in pairs})
            if len(syllables) == 1:
                pua_syllable_map[pua_hex] = {
                    "syllable": syllables[0],
                    "character_count": len(chars),
                    "characters_sample": chars[:10],
                }
            else:
                # Pick the most common reading as the "best guess" and log conflict.
                from collections import Counter
                counter = Counter(s for _, s in pairs)
                best, best_n = counter.most_common(1)[0]
                pua_syllable_map[pua_hex] = {
                    "syllable": best,
                    "character_count": len(chars),
                    "characters_sample": chars[:10],
                    "ambiguous": True,
                }
                conflicts[pua_hex] = {
                    "best_guess": best,
                    "syllable_distribution": dict(counter),
                    "character_readings": [{"char": c, "pypinyin": s} for c, s in pairs[:30]],
                }
        print(f"  mapped {len(pua_syllable_map)} unique PUAs to syllables; "
              f"{len(conflicts)} ambiguous (pypinyin disagrees among chars)")

    # --- write outputs ----------------------------------------------------
    outputs = {
        "fzktpy_meta.json": meta,
        "fzktpy_pua_glyphs.json": {"upm": meta["sub_fonts"][0]["unitsPerEm"], "glyphs": pua_glyphs},
        "fzktpy_cjk_composites.json": cjk_composites,
        "fzktpy_pua_syllable_map.json": pua_syllable_map,
        "fzktpy_pua_syllable_conflicts.json": conflicts,
    }
    print()
    print("writing files:")
    for fname, data in outputs.items():
        path = DATA / fname
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"  {path.relative_to(ROOT)}  ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
