#!/usr/bin/env python3
"""add_ligatures.py — Add GSUB Type 4 ligature substitutions to variant-1 fonts.

For each compound sequence in duoyinzi_pattern_one.txt whose contextual reading
differs from the current variant-1 reading (slot 0 of heteronym_map.json),
this script:
  1. Creates a wide composite ligature glyph showing all characters in the
     sequence, with the target character rendered using the correct reading's
     ruby above it.
  2. Adds a GSUB Lookup Type 4 (Ligature Substitution) rule so renderers that
     enable the 'liga' feature will automatically display the correct reading.

Usage:
    python add_ligatures.py --font <variant-1.ttf>
                            --data sources/data/duoyinzi_pattern_one.txt
                            --heteronym sources/data/heteronym_map.json
                            --syllables sources/data/syllable_inventory.json
                            [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import LigatureSubstBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import (
    ARGS_ARE_XY_VALUES, ROUND_XY_TO_GRID, Glyph, GlyphComponent,
)

COMP_FLAGS = ROUND_XY_TO_GRID | ARGS_ARE_XY_VALUES


# ── Parsing ──────────────────────────────────────────────────────────────────

def _safe_ascii(pinyin: str) -> str:
    """'chāi' → 'chai', 'hè' → 'he' (strip diacritics, keep ASCII)."""
    nfd = unicodedata.normalize("NFD", pinyin)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def parse_pattern_file(path: Path) -> list[dict]:
    """Return a list of rule records from duoyinzi_pattern_one.txt.

    Each record:
        char      : the single hanzi (str)
        char_cp   : its codepoint (int)
        reading   : the contextual pinyin (str, with tone marks)
        sequences : list of codepoint lists, each being the full sequence
                    (target char is somewhere in the list, ~ marks its position)
    """
    rules = []
    # Match: <n>, <char>, <reading>, [<patterns>]
    line_re = re.compile(r"^\d+,\s*(.),\s*([^\s,]+),\s*\[(.+)\]\s*$")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        char, reading, patterns_str = m.group(1), m.group(2), m.group(3)
        char_cp = ord(char)

        sequences: list[list[int]] = []
        for pat in patterns_str.split("|"):
            pat = pat.strip()
            if "~" not in pat:
                continue
            tilde = pat.index("~")
            prefix = [ord(c) for c in pat[:tilde]]
            suffix = [ord(c) for c in pat[tilde + 1:]]
            seq = prefix + [char_cp] + suffix
            if len(seq) >= 2:  # need at least 2 chars to form a ligature
                sequences.append(seq)

        if sequences:
            rules.append(
                {
                    "char": char,
                    "char_cp": char_cp,
                    "reading": reading,
                    "sequences": sequences,
                }
            )

    return rules


# ── Glyph helpers ─────────────────────────────────────────────────────────────

def _get_base_component(font: TTFont, glyph_name: str) -> str:
    """Return the first component of a composite glyph (the bare hanzi strokes).

    For variant-1 hanzi, glyph_name is a 2-component composite:
      [bare_strokes_glyph, PUA_ruby_glyph]
    We want the bare strokes so we can swap in a different PUA.
    """
    g = font["glyf"][glyph_name]
    if g.numberOfContours == -1 and g.components:
        return g.components[0].glyphName
    return glyph_name  # simple glyph — use as-is


def _make_ligature_glyph(components: list[tuple[str, int]]) -> Glyph:
    """Build a TrueType composite from [(glyph_name, x_offset), ...] pairs."""
    g = Glyph()
    g.numberOfContours = -1
    g.components = []
    for gname, x in components:
        c = GlyphComponent()
        c.glyphName = gname
        c.flags = COMP_FLAGS
        c.x = x
        c.y = 0
        g.components.append(c)
    return g


# ── vmtx sync ────────────────────────────────────────────────────────────────

def _sync_vmtx(font: TTFont) -> None:
    """Add vmtx entries for any glyph that lacks one, and fix vhea count.

    Mirrors the sync_vmtx_vhea() logic in make_pinyin_font_v2.py.
    """
    has_vhea = "vhea" in font
    has_vmtx = "vmtx" in font
    if not (has_vhea and has_vmtx):
        return
    upm = font["head"].unitsPerEm
    try:
        vmtx = font["vmtx"]
    except Exception:
        from fontTools.ttLib import newTable
        vmtx = newTable("vmtx")
        vmtx.metrics = {}
        font["vmtx"] = vmtx
    order = font.getGlyphOrder()
    for gn in order:
        if gn not in vmtx.metrics:
            vmtx.metrics[gn] = (upm, 0)
    vhea = font["vhea"]
    if hasattr(vhea, "numberOfVMetrics"):
        vhea.numberOfVMetrics = len(order)
    if hasattr(vhea, "numOfLongVerMetrics"):
        vhea.numOfLongVerMetrics = len(order)


# ── GSUB injection ────────────────────────────────────────────────────────────

def _add_liga_lookup(font: TTFont, liga_rules: list[tuple[list[str], str]]) -> None:
    """Inject a GSUB Type 4 Ligature lookup and wire it to the 'liga' feature.

    liga_rules: [(input_glyph_name_list, output_liga_glyph_name), ...]
    """
    if not liga_rules:
        return

    # Use fontTools' LigatureSubstBuilder which serialises correctly.
    builder = LigatureSubstBuilder(font, location=None)
    seen: set[tuple] = set()
    for input_gnames, liga_name in liga_rules:
        key = tuple(input_gnames)
        if key in seen:
            continue
        seen.add(key)
        builder.ligatures[tuple(input_gnames)] = liga_name

    lookup = builder.build()   # returns an otTables.Lookup (Type 4)

    gsub_table = font["GSUB"].table

    if gsub_table.LookupList is None:
        gsub_table.LookupList = otTables.LookupList()
        gsub_table.LookupList.Lookup = []

    new_idx = len(gsub_table.LookupList.Lookup)
    gsub_table.LookupList.Lookup.append(lookup)

    # Find or create the 'liga' FeatureRecord
    if gsub_table.FeatureList is None:
        gsub_table.FeatureList = otTables.FeatureList()
        gsub_table.FeatureList.FeatureRecord = []

    liga_feat_idx = None
    for i, fr in enumerate(gsub_table.FeatureList.FeatureRecord):
        if fr.FeatureTag == "liga":
            fr.Feature.LookupListIndex.append(new_idx)
            liga_feat_idx = i
            break

    if liga_feat_idx is None:
        feat = otTables.Feature()
        feat.FeatureParams = None
        feat.LookupListIndex = [new_idx]
        fr = otTables.FeatureRecord()
        fr.FeatureTag = "liga"
        fr.Feature = feat
        liga_feat_idx = len(gsub_table.FeatureList.FeatureRecord)
        gsub_table.FeatureList.FeatureRecord.append(fr)

    # Wire the feature into every script/language record
    if gsub_table.ScriptList is None:
        dflt_lang = otTables.DefaultLangSys()
        dflt_lang.ReqFeatureIndex = 0xFFFF
        dflt_lang.FeatureIndex = [liga_feat_idx]
        dflt_lang.LookupOrder = None
        script = otTables.Script()
        script.DefaultLangSys = dflt_lang
        script.LangSysRecord = []
        sr = otTables.ScriptRecord()
        sr.ScriptTag = "DFLT"
        sr.Script = script
        gsub_table.ScriptList = otTables.ScriptList()
        gsub_table.ScriptList.ScriptRecord = [sr]
    else:
        for sr in gsub_table.ScriptList.ScriptRecord:
            script = sr.Script
            if script.DefaultLangSys is not None:
                if liga_feat_idx not in script.DefaultLangSys.FeatureIndex:
                    script.DefaultLangSys.FeatureIndex.append(liga_feat_idx)
            for lr in script.LangSysRecord:
                if liga_feat_idx not in lr.LangSys.FeatureIndex:
                    lr.LangSys.FeatureIndex.append(liga_feat_idx)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(font_path: str, data_path: str, heteronym_path: str, syllable_path: str,
        dry_run: bool = False) -> None:

    het: dict[str, list] = json.loads(Path(heteronym_path).read_text(encoding="utf-8"))
    inv: dict[str, dict] = json.loads(Path(syllable_path).read_text(encoding="utf-8"))
    all_rules = parse_pattern_file(Path(data_path))

    font = TTFont(font_path)
    best_cmap: dict[int, str] = font["cmap"].getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    glyph_order: list[str] = list(font.getGlyphOrder())

    def adv(gname: str) -> int:
        return hmtx.metrics.get(gname, (1000, 0))[0]

    # ── Filter rules ──────────────────────────────────────────────────────────
    kept: list[dict] = []
    skipped_same = 0
    skipped_no_pua = 0
    skipped_missing_cmap = 0

    for rule in all_rules:
        cp_hex = f"{rule['char_cp']:04X}"
        v1_reading = (het.get(cp_hex) or [None])[0]
        ctx_reading = rule["reading"]

        if v1_reading == ctx_reading:
            skipped_same += 1
            continue

        pua_meta = inv.get(ctx_reading)
        if pua_meta is None:
            print(
                f"WARNING: no PUA glyph for reading \"{ctx_reading}\" "
                f"(char U+{cp_hex} {rule['char']}), skipping ligature"
            )
            skipped_no_pua += 1
            continue

        valid_seqs = []
        for seq in rule["sequences"]:
            missing = [f"U+{cp:04X}" for cp in seq if best_cmap.get(cp) is None]
            if missing:
                print(
                    f"  SKIP sequence {''.join(chr(c) for c in seq)}: "
                    f"chars not in cmap: {missing}"
                )
                skipped_missing_cmap += 1
            else:
                valid_seqs.append(seq)

        if valid_seqs:
            kept.append(
                {
                    **rule,
                    "sequences": valid_seqs,
                    "pua_name": f"uni{pua_meta['pua'].upper()}",
                }
            )

    print(
        f"Rules total={len(all_rules)}  kept={len(kept)}  "
        f"same-reading={skipped_same}  no-pua={skipped_no_pua}  "
        f"missing-cmap={skipped_missing_cmap}"
    )

    if dry_run:
        for r in kept:
            cp_hex = f"{r['char_cp']:04X}"
            v1 = (het.get(cp_hex) or [None])[0]
            for seq in r["sequences"]:
                seq_str = "".join(chr(c) for c in seq)
                print(
                    f"  {r['char']} U+{cp_hex} {v1!r} → {r['reading']!r}  "
                    f"seq={seq_str!r}"
                )
        return

    # ── Build new glyphs ──────────────────────────────────────────────────────
    new_glyphs: dict[str, Glyph] = {}
    new_metrics: dict[str, tuple[int, int]] = {}
    liga_rules: list[tuple[list[str], str]] = []
    seen_seqs: set[tuple] = set()
    conflicts: list[str] = []

    for rule in kept:
        char_gname = best_cmap[rule["char_cp"]]
        pua_name = rule["pua_name"]
        base_gname = _get_base_component(font, char_gname)

        for seq in rule["sequences"]:
            seq_key = tuple(seq)
            if seq_key in seen_seqs:
                conflicts.append("".join(chr(c) for c in seq))
                continue
            seen_seqs.add(seq_key)

            char_idx = seq.index(rule["char_cp"])

            # Build component list: [(glyph_name, x_offset), ...]
            comps: list[tuple[str, int]] = []
            x = 0
            for i, cp in enumerate(seq):
                g_cp = best_cmap[cp]
                if i == char_idx:
                    # Target char: bare base strokes + new PUA ruby
                    comps.append((base_gname, x))
                    comps.append((pua_name, x))   # PUA has baked-in vertical offset
                else:
                    # Context char: use its full composite (preserves its own ruby)
                    comps.append((g_cp, x))
                x += adv(g_cp)

            # Glyph name: uniXXXX_uniYYYY[_...].liga
            seq_part = "_".join(f"uni{cp:04X}" for cp in seq)
            liga_name = f"{seq_part}.liga"

            if liga_name not in new_glyphs and liga_name not in glyph_order:
                new_glyphs[liga_name] = _make_ligature_glyph(comps)
                new_metrics[liga_name] = (x, 0)

            input_gnames = [best_cmap[cp] for cp in seq]
            liga_rules.append((input_gnames, liga_name))

    if conflicts:
        print(f"  CONFLICTS (duplicate sequence, skipped): {conflicts}")

    print(f"New glyphs={len(new_glyphs)}  GSUB rules={len(liga_rules)}")

    # ── Inject glyphs into font ───────────────────────────────────────────────
    new_order = glyph_order + [n for n in new_glyphs if n not in glyph_order]
    font.setGlyphOrder(new_order)
    for name, g in new_glyphs.items():
        glyf[name] = g
    for name, m in new_metrics.items():
        hmtx.metrics[name] = m

    # ── Inject GSUB ligature lookup ───────────────────────────────────────────
    _add_liga_lookup(font, liga_rules)

    # ── Sync vmtx so every new glyph has a vertical metrics entry ─────────────
    _sync_vmtx(font)

    font.save(font_path)
    print(f"Saved: {font_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--font", required=True, help="Path to variant-1 TTF to modify")
    ap.add_argument("--data", required=True, help="Path to duoyinzi_pattern_one.txt")
    ap.add_argument("--heteronym", required=True, help="Path to heteronym_map.json")
    ap.add_argument("--syllables", required=True, help="Path to syllable_inventory.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print rules that would be added without modifying the font")
    args = ap.parse_args()
    run(args.font, args.data, args.heteronym, args.syllables, args.dry_run)


if __name__ == "__main__":
    main()
