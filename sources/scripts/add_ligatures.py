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
import unicodedata
from pathlib import Path

from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import LigatureSubstBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import (
    ARGS_ARE_XY_VALUES, ROUND_XY_TO_GRID, Glyph, GlyphComponent,
)
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen

COMP_FLAGS = ROUND_XY_TO_GRID | ARGS_ARE_XY_VALUES


# ── Data loading ──────────────────────────────────────────────────────────────

def load_rules(combined_path: Path) -> list[dict]:
    """Parse all_ligatures.json into one record per word.

    Each record:
        seq      : list of codepoints for the full word
        sequences: [seq] (single-element list for compat)
        changes  : list of {char_idx, char, char_cp, v1, marked} for every
                   position whose practical reading differs from primary.
                   All positions are captured so a single ligature composite
                   can show every corrected ruby in the word (e.g. 觉得:
                   both 觉 jiào→jué AND 得 dé→de in one glyph).
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
        changes = [
            {"char_idx": i, "char": chars[i], "char_cp": ord(chars[i]),
             "v1": primary, "marked": practical}
            for i, (primary, practical) in enumerate(zip(primary_tokens, practical_tokens))
            if primary != practical
        ]
        if changes:
            rules.append({"seq": seq, "sequences": [seq], "changes": changes})

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


# ── Neutral-tone ruby synthesis ───────────────────────────────────────────────

# Ruby zone geometry derived from existing PUA glyphs (e.g. uniE253):
# advance=1000, content x=186..815 (629 wide), y=959..1299 (340 tall).
_RUBY_BASELINE      = 959
_RUBY_RIGHT         = 815
_RUBY_LEFT          = 186
_RUBY_HEIGHT        = 340   # toned PUA: 1299 - 959 (tone 2/4 with accent)
_RUBY_NEUTRAL_HEIGHT = 311  # neutral-tone PUA: 1270 - 959 (no diacritic above)
_RUBY_ADV           = 1000


def _make_neutral_ruby_glyph(font: TTFont, syllable: str) -> Glyph | None:
    """Synthesize a ruby glyph for a neutral-tone syllable from Latin letters.

    Scales the individual letter outlines to fit the ruby zone and centers
    them horizontally within the cell, matching the geometry of PUA glyphs
    copied from the reference font.
    """
    cmap = font["cmap"].getBestCmap()
    glyf_table = font["glyf"]
    hmtx = font["hmtx"]

    letters: list[tuple[str, Glyph, int]] = []
    for ch in syllable:
        gname = cmap.get(ord(ch))
        if not gname:
            return None
        g = glyf_table[gname]
        if g.numberOfContours <= 0:
            return None
        letters.append((gname, g, hmtx.metrics[gname][0]))

    if not letters:
        return None

    total_adv = sum(adv for _, _, adv in letters)
    # Use xMax of tallest letter (ascenders only; ignore descenders for scale)
    max_h = max(g.yMax for _, g, _ in letters)
    if max_h <= 0:
        return None

    # Primary constraint: match the neutral-tone ruby height (311 u — capheight
    # of neutral PUA glyphs like "ba", "bei"; toned PUA reach 340 via diacritics).
    # Secondary constraint: letters must not overflow the 1000-unit advance.
    scale = min(_RUBY_NEUTRAL_HEIGHT / max_h, _RUBY_ADV / total_adv)

    # Center the text horizontally in the 1000-unit cell
    scaled_w = total_adv * scale
    x = round((_RUBY_ADV - scaled_w) / 2)

    pen = TTGlyphPen(None)
    for gname, g, adv in letters:
        # Translate so letter baseline (y=0) aligns to _RUBY_BASELINE
        tf = (scale, 0, 0, scale, x, _RUBY_BASELINE)
        g.draw(TransformPen(pen, tf), glyf_table)
        x += adv * scale

    return pen.glyph()


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

    def _bare(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn")

    bare_to_pua: dict[str, dict] = {}
    for key, val in inv.items():
        bare_to_pua.setdefault(_bare(key), val)

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
    # Synthesised neutral-tone ruby glyphs: name → (Glyph, metrics)
    neutral_rubies: dict[str, tuple[Glyph, tuple[int, int]]] = {}

    def _resolve_pua(marked: str, char: str, char_cp: int) -> str | None:
        """Return a pua glyph name for `marked`, or None to skip the word."""
        pua_meta = inv.get(marked)
        if pua_meta is None and _bare(marked) != marked:
            pua_meta = bare_to_pua.get(_bare(marked))
            if pua_meta is not None:
                inv[marked] = pua_meta
        if pua_meta is not None:
            return f"uni{pua_meta['pua'].upper()}"
        if _bare(marked) != marked:
            # Toned reading with no PUA at all.
            print(f"WARNING: no PUA glyph for reading \"{marked}\" "
                  f"(char U+{char_cp:04X} {char}), skipping")
            return None
        # Bare (neutral-tone) syllable: synthesise a ruby glyph on demand.
        ruby_name = f"ruby.{marked}"
        if ruby_name not in neutral_rubies:
            g = _make_neutral_ruby_glyph(font, marked)
            if g is None:
                print(f"WARNING: cannot synthesise ruby for \"{marked}\" "
                      f"(char U+{char_cp:04X} {char}), skipping")
                return None
            neutral_rubies[ruby_name] = (g, (_RUBY_ADV, 0))
        return ruby_name

    for rule in all_rules:
        # Resolve PUA glyph name for every changed character in the word.
        resolved: list[tuple[int, str]] = []  # (char_idx, pua_name)
        skip = False
        for ch in rule["changes"]:
            pua_name = _resolve_pua(ch["marked"], ch["char"], ch["char_cp"])
            if pua_name is None:
                skipped_no_pua += 1
                skip = True
                break
            resolved.append((ch["char_idx"], pua_name))
        if skip:
            continue

        valid_seqs = []
        for seq in rule["sequences"]:
            missing = [f"U+{cp:04X}" for cp in seq if best_cmap.get(cp) is None]
            if missing:
                skipped_missing_cmap += 1
            else:
                valid_seqs.append(seq)

        if valid_seqs:
            kept.append({**rule, "sequences": valid_seqs, "resolved": resolved})

    print(
        f"Rules: total={len(all_rules)}  kept={len(kept)}  "
        f"no-pua={skipped_no_pua}  missing-cmap={skipped_missing_cmap}"
    )

    if dry_run:
        for r in kept:
            for seq in r["sequences"]:
                changes_str = ", ".join(
                    f"{ch['char']} {ch['v1']!r}→{ch['marked']!r}"
                    for ch in r["changes"]
                )
                print(f"  {''.join(chr(c) for c in seq)!r}  [{changes_str}]")
        return

    # ── Build new glyphs ──────────────────────────────────────────────────────
    new_glyphs: dict[str, Glyph] = {}
    new_metrics: dict[str, tuple[int, int]] = {}
    liga_rules: list[tuple[list[str], str]] = []
    seen_seqs: set[tuple] = set()

    for rule in kept:
        # Map char_idx → pua_name for every changed position in this word.
        change_map: dict[int, str] = dict(rule["resolved"])

        for seq in rule["sequences"]:
            seq_key = tuple(seq)
            if seq_key in seen_seqs:
                continue
            seen_seqs.add(seq_key)

            comps: list[tuple[str, int]] = []
            x = 0
            for i, cp in enumerate(seq):
                g_cp = best_cmap[cp]
                if i in change_map:
                    base_gname = _get_base_component(font, g_cp)
                    comps.append((base_gname, x))
                    comps.append((change_map[i], x))
                else:
                    comps.append((g_cp, x))
                x += adv(g_cp)

            liga_name = "_".join(f"uni{cp:04X}" for cp in seq) + ".liga"

            if liga_name not in new_glyphs and liga_name not in glyph_order:
                new_glyphs[liga_name] = _make_ligature_glyph(comps)
                new_metrics[liga_name] = (x, 0)

            input_gnames = [best_cmap[cp] for cp in seq]
            liga_rules.append((input_gnames, liga_name))

    print(f"New glyphs={len(new_glyphs)}  neutral rubies={len(neutral_rubies)}  GSUB rules={len(liga_rules)}")

    # ── Inject into font ──────────────────────────────────────────────────────
    all_new_glyphs = {**{n: g for n, (g, _) in neutral_rubies.items()}, **new_glyphs}
    all_new_metrics = {**{n: m for n, (_, m) in neutral_rubies.items()}, **new_metrics}
    new_order = glyph_order + [n for n in all_new_glyphs if n not in glyph_order]
    font.setGlyphOrder(new_order)
    for name, g in all_new_glyphs.items():
        glyf[name] = g
    for name, m in all_new_metrics.items():
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
