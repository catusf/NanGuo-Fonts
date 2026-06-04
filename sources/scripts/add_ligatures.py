#!/usr/bin/env python3
"""add_ligatures.py — Add GSUB Type 4 ligature substitutions to variant-1 fonts.

Reads all_ligatures.json. For each multi-character word whose contextual
reading differs from the variant-1 primary reading at any character position,
this script:

  1. Creates a wide composite ligature glyph showing all characters in the
     word, with the target character rendered using the correct reading's
     ruby above it.
  2. Adds a GSUB Lookup Type 4 (Ligature Substitution) rule so renderers
     that enable the 'liga' feature automatically display the correct reading.

Usage:
    python add_ligatures.py --font <variant-1.ttf>
                            --combined sources/data/all_ligatures.json
                            --syllables sources/data/syllable_inventory.json
                            [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import LigatureSubstBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import (
    ARGS_ARE_XY_VALUES, ROUND_XY_TO_GRID, Glyph, GlyphComponent,
)

COMP_FLAGS = ROUND_XY_TO_GRID | ARGS_ARE_XY_VALUES


# ── Data loading ──────────────────────────────────────────────────────────────

def load_rules(combined_path: Path) -> list[dict]:
    """Parse all_ligatures.json into a flat list of rule records.

    Each record:
        char      : the single hanzi (str)
        char_cp   : its codepoint (int)
        char_idx  : position of this char within the word sequence
        v1        : tone-marked primary reading (syllable_inventory key)
        reading   : tone-marked contextual reading
        marked    : same as reading (tone-marked, for syllable_inventory lookup)
        sequences : single-element list containing the word's codepoint list
    """
    data: list[dict] = json.loads(combined_path.read_text(encoding="utf-8"))
    rules: list[dict] = []

    for entry in data:
        chars = list(entry["simplified"])
        primary_tokens = entry["primary_reading"].split()
        practical_tokens = entry["practical_reading"].split()

        if len(chars) != len(primary_tokens) or len(chars) != len(practical_tokens):
            continue

        seq = [ord(c) for c in chars]

        for i, (primary, practical) in enumerate(zip(primary_tokens, practical_tokens)):
            if primary == practical:
                continue
            rules.append({
                "char": chars[i],
                "char_cp": ord(chars[i]),
                "char_idx": i,
                "v1": primary,
                "reading": practical,
                "marked": practical,
                "sequences": [seq],
            })
            break  # one ligature glyph per word; first differing position wins

    return rules


# ── Glyph helpers ─────────────────────────────────────────────────────────────

def _get_base_component(font: TTFont, glyph_name: str) -> str:
    """Return the first component of a composite glyph (the bare hanzi strokes)."""
    g = font["glyf"][glyph_name]
    if g.numberOfContours == -1 and g.components:
        return g.components[0].glyphName
    return glyph_name


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
    if "vhea" not in font or "vmtx" not in font:
        return
    upm = font["head"].unitsPerEm
    vmtx = font["vmtx"]
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
    if not liga_rules:
        return

    builder = LigatureSubstBuilder(font, location=None)
    seen: set[tuple] = set()
    for input_gnames, liga_name in liga_rules:
        key = tuple(input_gnames)
        if key not in seen:
            seen.add(key)
            builder.ligatures[key] = liga_name

    lookup = builder.build()

    gsub = font["GSUB"].table
    if gsub.LookupList is None:
        gsub.LookupList = otTables.LookupList()
        gsub.LookupList.Lookup = []

    new_idx = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(lookup)

    if gsub.FeatureList is None:
        gsub.FeatureList = otTables.FeatureList()
        gsub.FeatureList.FeatureRecord = []

    liga_feat_idx = None
    for i, fr in enumerate(gsub.FeatureList.FeatureRecord):
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
        liga_feat_idx = len(gsub.FeatureList.FeatureRecord)
        gsub.FeatureList.FeatureRecord.append(fr)

    if gsub.ScriptList is None:
        dflt = otTables.DefaultLangSys()
        dflt.ReqFeatureIndex = 0xFFFF
        dflt.FeatureIndex = [liga_feat_idx]
        dflt.LookupOrder = None
        script = otTables.Script()
        script.DefaultLangSys = dflt
        script.LangSysRecord = []
        sr = otTables.ScriptRecord()
        sr.ScriptTag = "DFLT"
        sr.Script = script
        gsub.ScriptList = otTables.ScriptList()
        gsub.ScriptList.ScriptRecord = [sr]
    else:
        for sr in gsub.ScriptList.ScriptRecord:
            s = sr.Script
            if s.DefaultLangSys is not None:
                if liga_feat_idx not in s.DefaultLangSys.FeatureIndex:
                    s.DefaultLangSys.FeatureIndex.append(liga_feat_idx)
            for lr in s.LangSysRecord:
                if liga_feat_idx not in lr.LangSys.FeatureIndex:
                    lr.LangSys.FeatureIndex.append(liga_feat_idx)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(font_path: str, combined_path: str, syllable_path: str,
        dry_run: bool = False) -> None:

    inv: dict[str, dict] = json.loads(Path(syllable_path).read_text(encoding="utf-8"))
    all_rules = load_rules(Path(combined_path))

    font = TTFont(font_path)
    best_cmap: dict[int, str] = font["cmap"].getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    glyph_order: list[str] = list(font.getGlyphOrder())

    def adv(gname: str) -> int:
        return hmtx.metrics.get(gname, (1000, 0))[0]

    # ── Filter rules ──────────────────────────────────────────────────────────
    kept: list[dict] = []
    skipped_no_pua = 0
    skipped_missing_cmap = 0

    for rule in all_rules:
        pua_meta = inv.get(rule["marked"])
        if pua_meta is None:
            print(
                f"WARNING: no PUA glyph for reading \"{rule['marked']}\" "
                f"(char U+{rule['char_cp']:04X} {rule['char']}), skipping"
            )
            skipped_no_pua += 1
            continue

        valid_seqs = []
        for seq in rule["sequences"]:
            missing = [f"U+{cp:04X}" for cp in seq if best_cmap.get(cp) is None]
            if missing:
                skipped_missing_cmap += 1
            else:
                valid_seqs.append(seq)

        if valid_seqs:
            kept.append({**rule, "sequences": valid_seqs,
                         "pua_name": f"uni{pua_meta['pua'].upper()}"})

    print(
        f"Rules: total={len(all_rules)}  kept={len(kept)}  "
        f"no-pua={skipped_no_pua}  missing-cmap={skipped_missing_cmap}"
    )

    if dry_run:
        for r in kept:
            for seq in r["sequences"]:
                print(f"  {r['char']} {r['v1']!r}→{r['reading']!r}  "
                      f"seq={''.join(chr(c) for c in seq)!r}")
        return

    # ── Build new glyphs ──────────────────────────────────────────────────────
    new_glyphs: dict[str, Glyph] = {}
    new_metrics: dict[str, tuple[int, int]] = {}
    liga_rules: list[tuple[list[str], str]] = []
    seen_seqs: set[tuple] = set()

    for rule in kept:
        char_gname = best_cmap[rule["char_cp"]]
        pua_name = rule["pua_name"]
        base_gname = _get_base_component(font, char_gname)

        for seq in rule["sequences"]:
            seq_key = tuple(seq)
            if seq_key in seen_seqs:
                continue
            seen_seqs.add(seq_key)

            char_idx = rule.get("char_idx", seq.index(rule["char_cp"]))
            comps: list[tuple[str, int]] = []
            x = 0
            for i, cp in enumerate(seq):
                g_cp = best_cmap[cp]
                if i == char_idx:
                    comps.append((base_gname, x))
                    comps.append((pua_name, x))
                else:
                    comps.append((g_cp, x))
                x += adv(g_cp)

            liga_name = "_".join(f"uni{cp:04X}" for cp in seq) + ".liga"

            if liga_name not in new_glyphs and liga_name not in glyph_order:
                new_glyphs[liga_name] = _make_ligature_glyph(comps)
                new_metrics[liga_name] = (x, 0)

            input_gnames = [best_cmap[cp] for cp in seq]
            liga_rules.append((input_gnames, liga_name))

    print(f"New glyphs={len(new_glyphs)}  GSUB rules={len(liga_rules)}")

    # ── Inject into font ──────────────────────────────────────────────────────
    new_order = glyph_order + [n for n in new_glyphs if n not in glyph_order]
    font.setGlyphOrder(new_order)
    for name, g in new_glyphs.items():
        glyf[name] = g
    for name, m in new_metrics.items():
        hmtx.metrics[name] = m

    _add_liga_lookup(font, liga_rules)
    _sync_vmtx(font)

    font.save(font_path)
    print(f"Saved: {font_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--font", required=True, help="Path to variant-1 TTF to modify")
    ap.add_argument("--combined", required=True, help="Path to duoyinzi_combined.json")
    ap.add_argument("--syllables", required=True, help="Path to syllable_inventory.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print rules without modifying the font")
    args = ap.parse_args()
    run(args.font, args.combined, args.syllables, args.dry_run)


if __name__ == "__main__":
    main()
