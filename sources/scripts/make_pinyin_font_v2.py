#!/usr/bin/env python3
"""make_pinyin_font_v2.py — config-driven NanGuo Pinyin Font Builder.

Spec source of truth: ../Output_font_requirements.md
Tunable parameters:    ../config.json

What changed vs. v1:
- All numeric parameters sourced from config.json (no hardcoded geometry).
- post.formatType = 3.0 (Word/PowerPoint render-compatible).
- OS/2.fsSelection USE_TYPO_METRICS bit (7) set + REGULAR bit (6) set.
- Mac platform name[2] = "Regular" emitted on every variant.
- Variant fallback: single-reading hanzi resolve to variant-1's composite
  in all 6 variants (instead of bare base glyph stripped of ruby).
- vmtx fully synced with vhea for every new glyph.
- Non-pinyin-map hanzi removed from every cmap subtable (option 3).
- Deterministic glyph ordering.
- Full OS/2 + hhea metric application from config.
- name[10] Description, name[25] Variations PS prefix emitted.
- OS/2.achVendID, fsType, usWeightClass, usWidthClass applied from config.

CLI is identical to v1 plus an optional --config flag.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import textwrap
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._g_l_y_f import (
    ARGS_ARE_XY_VALUES, ROUND_XY_TO_GRID, Glyph, GlyphComponent,
)
from fontTools.ttLib.tables._n_a_m_e import NameRecord
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # sources/scripts/ -> sources/ -> project root
DATA_DIR = PROJECT_ROOT / "sources" / "data"
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"

COMP_FLAGS = ROUND_XY_TO_GRID | ARGS_ARE_XY_VALUES

# Reference yMax of the 'ǎ' glyph at UPM=1000 used by the Latin-compose path
# to scale ruby height. Kept as a constant because it describes Noto's
# physical glyph metrics, not a tunable.
REF_ASC_1000 = 833

# CJK ranges that get pruned from cmap if not in pinyin_map.json.
CJK_RANGES = (
    (0x3400, 0x4DBF),    # CJK Unified Ext A
    (0x4E00, 0x9FFF),    # CJK Unified
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x20000, 0x2FFFF),  # CJK Unified Ext B–F
    (0x30000, 0x3FFFF),  # CJK Unified Ext G+
)

# ── config loading + scaling ─────────────────────────────────────────────────

def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scale_to_upm(value_at_1000: float, upm: int, ref_upm: int = 1000) -> int:
    return int(round(value_at_1000 * upm / ref_upm))


def is_hanzi(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


# ── small TTF helpers ────────────────────────────────────────────────────────

def _cmap_subtable(font, plat: int, enc: int, fmt: int):
    for t in font["cmap"].tables:
        if t.platformID == plat and t.platEncID == enc and t.format == fmt:
            return t
    return None


def _cmap4(font):
    t = _cmap_subtable(font, 3, 1, 4)
    return t.cmap if t else None


def _cmap12(font):
    t = _cmap_subtable(font, 3, 10, 12)
    return t.cmap if t else {}


def _set_name(tbl, nid, val, plat=3, enc=1, lang=0x0409):
    tbl.names = [r for r in tbl.names
                 if not (r.nameID == nid and r.platformID == plat
                         and r.platEncID == enc and r.langID == lang)]
    rec = NameRecord()
    rec.nameID = nid
    rec.platformID = plat
    rec.platEncID = enc
    rec.langID = lang
    rec.string = val.encode("utf-16-be") if plat == 3 else val.encode("mac-roman", errors="replace")
    tbl.names.append(rec)


def _make_comp(base_name: str, ruby_name: str) -> Glyph:
    g = Glyph()
    g.numberOfContours = -1
    c1 = GlyphComponent()
    c1.glyphName = base_name
    c1.flags = COMP_FLAGS
    c1.x = 0
    c1.y = 0
    c2 = GlyphComponent()
    c2.glyphName = ruby_name
    c2.flags = COMP_FLAGS
    c2.x = 0
    c2.y = 0
    g.components = [c1, c2]
    return g


# ── Phase 1: detect metrics (config-driven) ──────────────────────────────────

def detect_subfamily(font) -> dict:
    """Read the source font's weight / subfamily so the output inherits them.

    Returns keys: subfamily ("Regular" | "Bold" | ...), weight_class (int),
    is_bold (True only when subfamily == "Bold"; SemiBold/ExtraBold/Black
    set usWeightClass but NOT the macStyle bold bit).
    """
    os2 = font["OS/2"]
    rec = font["name"].getName(2, 3, 1, 0x409)
    sf = str(rec).strip() if rec else ""
    if not sf:
        sf = "Bold" if os2.usWeightClass == 700 else "Regular"
    return {
        "subfamily": sf,
        "weight_class": int(os2.usWeightClass),
        "is_bold": sf == "Bold",
    }


def detect_metrics(font, cfg: dict) -> dict:
    upm = font["head"].unitsPerEm
    ruby_geo = cfg["ruby_geometry_at_upm_1000"]
    ruby_y = scale_to_upm(ruby_geo["baseline_y"], upm)
    ruby_em = scale_to_upm(ruby_geo["em"], upm)
    max_overflow_factor = float(ruby_geo.get("max_overflow_factor", 1.0))

    cm12 = _cmap12(font)
    cjk_adv = upm
    for cp in (0x4E00, 0x4E2D, 0x5927):
        gn = cm12.get(cp)
        if gn:
            cjk_adv = font["hmtx"].metrics[gn][0]
            break

    return dict(upm=upm, ruby_y=ruby_y, ruby_em=ruby_em, cjk_adv=cjk_adv,
                max_overflow_factor=max_overflow_factor)


# ── Phase 2A: compose PUA glyph from base font Latin ─────────────────────────

def _compose_from_latin(font, syllable: str, m: dict):
    cmap = font["cmap"].getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    info = []
    for ch in syllable:
        gn = cmap.get(ord(ch))
        if not gn:
            return None
        g = glyf[gn]
        adv = hmtx.metrics.get(gn, (m["cjk_adv"], 0))[0]
        if g.numberOfContours and g.numberOfContours > 0:
            g.recalcBounds(glyf)
            info.append((gn, g.xMin, g.yMin, g.xMax, g.yMax, adv))
        else:
            info.append((gn, 0, 0, 0, 0, adv))
    ref = int(REF_ASC_1000 * m["upm"] / 1000)
    scale_h = m["ruby_em"] / ref
    total_adv = sum(a for *_, a in info)
    scale_w = m["cjk_adv"] * m["max_overflow_factor"] / total_adv if total_adv else scale_h
    # Decouple axes: every syllable is drawn at the full vertical scale so
    # tone marks reach the same top across all glyphs; horizontal scale is
    # capped independently so wide syllables compress into the cell.
    scale_y = scale_h
    scale_x = min(scale_h, scale_w)
    x = (m["cjk_adv"] - total_adv * scale_x) / 2
    pen = TTGlyphPen(None)
    for gn, xMin, yMin, xMax, yMax, adv in info:
        g = glyf[gn]
        if g.numberOfContours and g.numberOfContours > 0:
            g.draw(TransformPen(pen, (scale_x, 0, 0, scale_y, x, m["ruby_y"])), glyf)
        x += adv * scale_x
    try:
        return pen.glyph(), m["cjk_adv"]
    except Exception:
        return None


# ── Phase 2: inject PUA glyphs ───────────────────────────────────────────────

def phase2_pua(font_path: str, inv: dict, m: dict, cfg: dict,
               warn: list[str]):
    print("[2] Generating PUA glyphs...")
    font = TTFont(font_path)
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    # Sort syllables for deterministic order.
    new_names: list[str] = []
    syl_to_pua: dict[str, str] = {}
    failed: list[str] = []
    total = len(inv)
    dot = max(1, total // 20)
    for i, syl in enumerate(sorted(inv.keys(), key=lambda s: inv[s]["pua"])):
        meta = inv[syl]
        if i % dot == 0:
            print(f"  [{i / total * 100:3.0f}%]", end="\r")
        gname = f"uni{meta['pua'].upper()}"
        result = _compose_from_latin(font, syl, m)
        if result is None:
            failed.append(syl)
            continue
        go, aw = result
        try:
            go.recalcBounds(glyf)
            lsb = go.xMin
        except Exception:
            lsb = 0
        glyf[gname] = go
        hmtx.metrics[gname] = (aw, lsb)
        new_names.append(gname)
        syl_to_pua[syl] = gname
    print(f"  [100%] {len(new_names)} built, {len(failed)} failed")
    if failed:
        warn.append(f"PUA build failed for {len(failed)} syllables: {failed[:5]}...")

    # Add PUA codepoints to fmt-4 cmap ONLY (for name synthesis on reload).
    # The fmt-12 (best) cmap deliberately stays empty for PUA codepoints
    # so that getBestCmap() reports zero PUA exposure per spec §4.
    cm4 = _cmap4(font)
    if cm4 is None:
        t4 = CmapSubtable.newSubtable(4)
        t4.platformID = 3
        t4.platEncID = 1
        t4.language = 0
        t4.cmap = {}
        font["cmap"].tables.append(t4)
        cm4 = t4.cmap
    for syl, gn in syl_to_pua.items():
        cm4[int(inv[syl]["pua"], 16)] = gn

    font["glyf"].glyphOrder = font.getGlyphOrder()
    font["maxp"].numGlyphs = len(font.getGlyphOrder())
    sync_vmtx_vhea(font, m)

    # Intermediate save MUST keep glyph names on disk so phase 3 can
    # reference them by name (post 3.0 would strip them).
    _force_intermediate_post_2(font)

    tmp = tempfile.mktemp(suffix="_pua.ttf")
    font.save(tmp)
    print(f"  Saved phase-2 font ({os.path.getsize(tmp) / 1e6:.1f}MB)")

    syl_map_path = tempfile.mktemp(suffix="_sylmap.json")
    Path(syl_map_path).write_text(json.dumps(syl_to_pua), encoding="utf-8")
    return tmp, syl_map_path


# ── Phase 3: build composite CJK glyphs ──────────────────────────────────────

def phase3_composites(font_path: str, syl_map_path: str, pmap: dict,
                      het: dict, m: dict, cfg: dict, warn: list[str]):
    print("[3] Building CJK composite glyphs...")
    font = TTFont(font_path)
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    cm12 = _cmap12(font)
    syl_to_pua = json.loads(Path(syl_map_path).read_text(encoding="utf-8"))
    variant_count = cfg["variants"]["count"]

    existing = set(font.getGlyphOrder())

    # Blank-variant target: the U+3000 (ideographic space) glyph if Noto
    # has it, else .notdef. Variants whose FZKTPY0N reading is absent map
    # the codepoint here — character is "skipped" in that variant, mimicking
    # FZKTPY's design. NEVER fall back to V1's ruby.
    blank_glyph = cm12.get(0x3000) or ".notdef"
    print(f"  Blank-variant target: {blank_glyph!r}")

    base_glyphs: dict[str, Glyph] = {}
    base_metrics: dict[str, tuple] = {}
    comp_glyphs: dict[str, Glyph] = {}
    comp_metrics: dict[str, tuple] = {}
    variant_map: dict[str, list[str]] = {}
    primary_updates: dict[str, tuple[str, str]] = {}
    seen_base: dict[str, str] = {}

    total = len(pmap)
    dot = max(1, total // 20)

    # Sort by codepoint for deterministic ordering.
    for idx, cp_hex in enumerate(sorted(pmap.keys(), key=lambda h: int(h, 16))):
        prim_syl = pmap[cp_hex]
        if idx % dot == 0:
            print(f"  [{idx / total * 100:3.0f}%]", end="\r")
        cp = int(cp_hex, 16)
        orig = cm12.get(cp)
        if not orig:
            continue
        g_orig = glyf.get(orig)
        if g_orig is None:
            continue

        if orig in seen_base:
            base_comp = seen_base[orig]
        else:
            base_comp = orig + ".pynbase"
            if base_comp in existing:
                base_comp = orig + ".pynbase2"
            seen_base[orig] = base_comp
            if base_comp not in base_glyphs:
                base_glyphs[base_comp] = copy.deepcopy(g_orig)
                base_metrics[base_comp] = hmtx.metrics.get(orig, (m["cjk_adv"], 0))

        # all_r is a length-variant_count list with None for variants
        # that have no FZKTPY reading (blank slots).
        all_r = het.get(cp_hex)
        if all_r is None:
            all_r = [prim_syl] + [None] * (variant_count - 1)
        all_r = list(all_r) + [None] * (variant_count - len(all_r))
        all_r = all_r[:variant_count]

        variants: list[str] = []
        # Within-char dedup: if a later variant repeats an earlier
        # variant's syllable, reuse that variant's glyph.
        syl_to_glyph: dict[str, str] = {}

        for k, syl in enumerate(all_r):
            if syl is None:
                # FZKTPY has no reading for this variant — blank slot.
                variants.append(blank_glyph)
                continue
            pua_name = syl_to_pua.get(syl)
            if pua_name is None:
                # Syllable known but no PUA glyph was built (rare;
                # logged as build warning). Skip to blank rather than
                # silently using V1's ruby.
                variants.append(blank_glyph)
                continue
            if syl in syl_to_glyph:
                variants.append(syl_to_glyph[syl])
                continue
            if k == 0:
                primary_updates[orig] = (base_comp, pua_name)
                syl_to_glyph[syl] = orig
                variants.append(orig)
            else:
                vname = f"{orig}.v{k + 1}"
                if vname not in comp_glyphs and vname not in existing:
                    comp_glyphs[vname] = _make_comp(base_comp, pua_name)
                    aw = hmtx.metrics.get(orig, (m["cjk_adv"], 0))[0]
                    comp_metrics[vname] = (aw, 0)
                syl_to_glyph[syl] = vname
                variants.append(vname)

        variant_map[cp_hex] = variants

    print(f"  [100%] {len(variant_map):,} entries")
    print(f"  base glyphs={len(base_glyphs)}  variants={len(comp_glyphs)}  "
          f"primary updates={len(primary_updates)}")

    # Commit base + variant glyphs deterministically.
    for gn in sorted(base_glyphs):
        glyf[gn] = base_glyphs[gn]
        hmtx.metrics[gn] = base_metrics[gn]
    for gn in sorted(comp_glyphs):
        glyf[gn] = comp_glyphs[gn]
        hmtx.metrics[gn] = comp_metrics[gn]

    for orig_name, (base_comp, pua_name) in primary_updates.items():
        glyf[orig_name] = _make_comp(base_comp, pua_name)

    font["glyf"].glyphOrder = font.getGlyphOrder()
    font["maxp"].numGlyphs = len(font.getGlyphOrder())
    sync_vmtx_vhea(font, m)
    _force_intermediate_post_2(font)

    tmp = tempfile.mktemp(suffix="_comp.ttf")
    font.save(tmp)
    print(f"  Saved phase-3 font ({os.path.getsize(tmp) / 1e6:.1f}MB)")

    vm_path = tempfile.mktemp(suffix="_varmap.json")
    Path(vm_path).write_text(json.dumps(variant_map), encoding="utf-8")
    return tmp, vm_path


# ── Helpers used in Phase 4 ──────────────────────────────────────────────────

def apply_os2_hhea_metrics(font, m: dict, cfg: dict, cfg_dict: dict):
    upm = m["upm"]
    M = cfg["metrics_at_upm_1000"]
    flags = cfg["os2_flags"]
    is_bold = bool(cfg_dict.get("is_bold"))
    weight_class = int(cfg_dict.get("weight_class", M["os2_weight_class"]))

    hhea = font["hhea"]
    hhea.ascent = scale_to_upm(M["hhea_ascent"], upm)
    hhea.descent = scale_to_upm(M["hhea_descent"], upm)
    hhea.lineGap = scale_to_upm(M["hhea_line_gap"], upm)

    os2 = font["OS/2"]
    os2.usWinAscent = scale_to_upm(M["os2_win_ascent"], upm)
    os2.usWinDescent = scale_to_upm(M["os2_win_descent"], upm)
    os2.sTypoAscender = scale_to_upm(M["os2_typo_ascender"], upm)
    os2.sTypoDescender = scale_to_upm(M["os2_typo_descender"], upm)
    os2.sTypoLineGap = scale_to_upm(M["os2_typo_line_gap"], upm)
    os2.usWeightClass = weight_class
    os2.usWidthClass = M["os2_width_class"]
    os2.fsType = flags["fs_type"]
    os2.achVendID = cfg["vendor"]["ach_vend_id"]

    fs = os2.fsSelection
    if flags["fs_selection_use_typo_metrics_bit_7"]:
        fs |= 0x80
    else:
        fs &= ~0x80
    fs &= ~(0x20 | 0x40)  # clear BOLD and REGULAR bits before setting one
    if is_bold:
        fs |= 0x20  # BOLD
    elif flags["fs_selection_regular_bit_6_for_regular_weight"] and weight_class == 400:
        fs |= 0x40  # REGULAR
    os2.fsSelection = fs

    head = font["head"]
    mac = head.macStyle
    mac &= ~0x03  # clear bold/italic bits
    if is_bold:
        mac |= 0x01  # bold
    head.macStyle = mac


def apply_post_format(font, cfg: dict):
    post = font["post"]
    post.formatType = float(cfg["post_table"]["format_type"])
    if hasattr(post, "extraNames"):
        post.extraNames = []
    if hasattr(post, "mapping"):
        post.mapping = {}
    if hasattr(post, "glyphOrder"):
        post.glyphOrder = None


def _force_intermediate_post_2(font):
    """Keep glyph names on disk for intermediate saves.

    Noto SC ships post.formatType=3.0 (no names on disk). If we save phase
    2/3 with that format, custom names (`uniXXXX.pynbase`, `.v2`, …) are
    stripped — on the next reload fontTools synthesizes generic
    `glyph%05d` names and the cmap entries that reference our custom
    names raise KeyError at compile time. Format 2.0 stores names
    verbatim. The final phase 4 save flips back to 3.0.
    """
    post = font["post"]
    post.formatType = 2.0
    if not hasattr(post, "extraNames"):
        post.extraNames = []
    if not hasattr(post, "mapping"):
        post.mapping = {}


def apply_name_table(font, cfg_dict: dict, variant_n: int):
    nm = cfg_dict["name"]
    ps_pfx = cfg_dict["ps_prefix"]
    subfamily = cfg_dict.get("subfamily", "Regular")
    ps_suffix = "" if subfamily == "Regular" else f"-{subfamily}"
    family = f"{nm} {variant_n}"
    ps = f"{ps_pfx}-{variant_n}{ps_suffix}"
    year = cfg_dict["year"]
    author = cfg_dict["author"]
    url = cfg_dict["url"]

    copyright_ = (
        f"Copyright {year} The {nm} Project Authors ({url}). "
        "Font data derived from Noto CJK fonts, Copyright 2014-2021 Google LLC."
    )
    lic_desc = (
        "This Font Software is licensed under the SIL Open Font License, "
        "Version 1.1. Available at: https://scripts.sil.org/OFL"
    )
    description = (
        f"{nm} embeds Hanyu Pinyin pronunciation guides above each Hanzi as "
        f"font-native ruby. Variant {variant_n} of {cfg_dict.get('variant_count', 6)}."
    )
    var_ps_prefix = cfg_dict.get("variations_ps_prefix", "NotoSansSC")

    tbl = font["name"]

    win_records = [
        (0, copyright_),
        (1, family),
        (2, subfamily),
        (3, f"{ps}:{year}"),
        (4, f"{family} {subfamily}"),
        (5, "Version 1.000"),
        (6, ps),
        (7, nm),
        (8, author),
        (9, author),
        (10, description),
        (11, url),
        (12, url),
        (13, lic_desc),
        (14, "https://scripts.sil.org/OFL"),
        (16, nm),
        (17, subfamily),
        (25, var_ps_prefix),
    ]
    for nid, val in win_records:
        if val:
            _set_name(tbl, nid, val, plat=3, enc=1, lang=0x0409)

    # Drop Mac platform records we are replacing, then re-add.
    mac_ids = (1, 2, 4, 6)
    tbl.names = [r for r in tbl.names if not (r.platformID == 1 and r.nameID in mac_ids)]
    mac_records = [(1, family), (2, subfamily), (4, f"{family} {subfamily}"), (6, ps)]
    for nid, val in mac_records:
        _set_name(tbl, nid, val, plat=1, enc=0, lang=0)


def sync_vmtx_vhea(font, m: dict):
    """Ensure vmtx has an entry for every glyph and vhea's count matches.

    Default advanceHeight = UPM, tsb = 0. Existing entries are preserved.
    Must be called before every save once new glyphs have been added,
    otherwise fontTools writes vmtx raw bytes that no longer match the
    grown glyph count and the reload trips TTLibError.
    """
    has_vhea = "vhea" in font.keys() or "vhea" in (font.reader.keys() if hasattr(font, "reader") else [])
    has_vmtx = "vmtx" in font.keys() or "vmtx" in (font.reader.keys() if hasattr(font, "reader") else [])
    if not (has_vhea and has_vmtx):
        return
    upm = m["upm"]
    try:
        vmtx = font["vmtx"]  # forces decompile against current vhea count
    except Exception:
        # Corrupted vmtx (count mismatch) — rebuild from scratch.
        from fontTools.ttLib import newTable
        vmtx = newTable("vmtx")
        vmtx.metrics = {}
        font["vmtx"] = vmtx
    order = font.getGlyphOrder()
    for gn in order:
        if gn not in vmtx.metrics:
            vmtx.metrics[gn] = (upm, 0)
    vhea = font["vhea"]
    # Use long-form for every glyph (4 bytes each). Eliminates the
    # short-form tail and the byte-count drift that plagued v1.
    if hasattr(vhea, "numberOfVMetrics"):
        vhea.numberOfVMetrics = len(order)
    if hasattr(vhea, "numOfLongVerMetrics"):
        vhea.numOfLongVerMetrics = len(order)


def strip_pua_from_best_cmap(font, cfg: dict):
    """Remove PUA codepoints from the fmt-12 (best) cmap subtables.

    Fmt-4 retains PUA entries so fontTools can synthesize uniXXXX glyph
    names on reload — this is what good/NanGuoPinyin-1.ttf does and what
    test_composites.py expects.
    """
    if cfg["cmap_coverage"]["expose_pua_in_cmap"]:
        return
    pua = cfg["pua_range"]
    lo = int(pua["start"], 16)
    hi = int(pua["end"], 16)
    for t in font["cmap"].tables:
        if t.format == 12 and hasattr(t, "cmap"):
            t.cmap = {cp: gn for cp, gn in t.cmap.items() if not (lo <= cp <= hi)}


def strip_unmapped_hanzi(font, pmap: dict):
    """Drop hanzi codepoints not in pinyin_map.json from every cmap subtable.

    Latin / Greek / Cyrillic / symbols are preserved; only CJK ranges are
    pruned. Glyphs themselves stay in glyf (per spec §8).
    """
    keep_cps = {int(h, 16) for h in pmap.keys()}
    for t in font["cmap"].tables:
        if not hasattr(t, "cmap") or not t.cmap:
            continue
        t.cmap = {
            cp: gn for cp, gn in t.cmap.items()
            if (not is_hanzi(cp)) or (cp in keep_cps)
        }


def assert_required_tables(font):
    spec_tables = {
        "BASE", "GDEF", "GPOS", "GSUB", "STAT", "cmap", "gasp", "glyf",
        "hhea", "head", "hmtx", "loca", "maxp", "name", "OS/2", "post",
        "prep", "vhea", "vmtx",
    }
    missing = spec_tables - set(font.keys())
    if missing:
        print(f"  WARNING: missing required tables: {sorted(missing)}", file=sys.stderr)
    forbidden = {"CFF ", "CFF2"} & set(font.keys())
    if forbidden:
        raise RuntimeError(f"output must be TrueType-only; found: {sorted(forbidden)}")


# ── Phase 4: build per-variant TTFs ──────────────────────────────────────────

def phase4_variants(font_path: str, vm_path: str, cfg_dict: dict, cfg: dict,
                    m: dict, pmap: dict, out_dir: str, warn: list[str]):
    print("[4] Exporting per-variant TTFs...")
    variant_map = json.loads(Path(vm_path).read_text(encoding="utf-8"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    variant_count = cfg["variants"]["count"]
    ps_pfx = cfg_dict["ps_prefix"]
    subfamily = cfg_dict.get("subfamily", "Regular")
    fname_suffix = "" if subfamily == "Regular" else f"-{subfamily}"
    cfg_dict["variant_count"] = variant_count

    for k in range(variant_count):
        n = k + 1
        font = TTFont(font_path)
        cm12 = _cmap12(font)

        # Remap cmap to variant-k glyph names.
        for t in font["cmap"].tables:
            if not hasattr(t, "cmap") or not t.cmap:
                continue
            for cp_hex, vnames in variant_map.items():
                cp = int(cp_hex, 16)
                if cp in t.cmap:
                    t.cmap[cp] = vnames[k]

        # Strip PUA from best cmap, strip non-pinyin hanzi everywhere.
        strip_pua_from_best_cmap(font, cfg)
        strip_unmapped_hanzi(font, pmap)

        # Apply OS/2, hhea, head metrics.
        apply_os2_hhea_metrics(font, m, cfg, cfg_dict)

        # Apply post format (3.0).
        apply_post_format(font, cfg)

        # Apply name table.
        apply_name_table(font, cfg_dict, n)

        # Sync vmtx with vhea.
        sync_vmtx_vhea(font, m)

        # Sanity-gate required tables.
        assert_required_tables(font)

        fname = out / f"{ps_pfx}-{n}{fname_suffix}.ttf"
        font.save(str(fname))
        print(f"  [{n}] {fname.name}  {fname.stat().st_size / 1e6:.1f}MB")

    _write_metadata(cfg_dict, cfg, out)
    _write_ofl(cfg_dict, out)
    _write_description(cfg_dict, out)
    print(f"  Metadata written -> {out}")


# ── Metadata sidecars ────────────────────────────────────────────────────────

def _write_metadata(cfg_dict: dict, cfg: dict, out: Path):
    nm = cfg_dict["name"]
    ps = cfg_dict["ps_prefix"]
    yr = cfg_dict["year"]
    auth = cfg_dict["author"]
    subfamily = cfg_dict.get("subfamily", "Regular")
    weight = int(cfg_dict.get("weight_class", 400))
    fname_suffix = "" if subfamily == "Regular" else f"-{subfamily}"
    ps_suffix = fname_suffix
    category = "SERIF" if "Serif" in nm else "SANS_SERIF"
    lines = [
        f'name: "{nm}"',
        f'designer: "{auth}"',
        'license: "OFL"',
        f'category: "{category}"',
        f'date_added: "{yr}-01-01"',
    ]
    for k in range(1, cfg["variants"]["count"] + 1):
        lines += [
            "fonts {",
            f'  name: "{nm} {k}"',
            '  style: "normal"',
            f"  weight: {weight}",
            f'  filename: "{ps}-{k}{fname_suffix}.ttf"',
            f'  post_script_name: "{ps}-{k}{ps_suffix}"',
            f'  full_name: "{nm} {k} {subfamily}"',
            f'  copyright: "Copyright {yr} {auth}"',
            "}",
        ]
    lines += ['subsets: "chinese-simplified"', 'subsets: "latin"', 'subsets: "latin-ext"']
    fname = "METADATA.pb" if subfamily == "Regular" else f"METADATA-{subfamily}.pb"
    (out / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ofl(cfg_dict: dict, out: Path):
    (out / "OFL.txt").write_text(
        textwrap.dedent(f"""\
        Copyright {cfg_dict['year']} The {cfg_dict['name']} Project Authors ({cfg_dict['url']})
        Font data derived from Noto CJK fonts, Copyright 2014-2021 Google LLC.

        This Font Software is licensed under the SIL Open Font License, Version 1.1.
        http://scripts.sil.org/OFL
        """),
        encoding="utf-8",
    )


def _write_description(cfg_dict: dict, out: Path):
    (out / "DESCRIPTION.en_us.html").write_text(
        textwrap.dedent(f"""\
        <p>{cfg_dict['name']} is a Simplified Chinese educational typeface that embeds
        Hanyu Pinyin pronunciation guides directly above each character as
        font-native ruby text — no HTML markup required. Based on Noto CJK.</p>
        <p>Six variants (1–6) show successive pronunciation readings for
        multi-pronunciation characters (多音字). Characters with only one reading
        show that reading in all variants.</p>
        """),
        encoding="utf-8",
    )


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--font", required=True)
    p.add_argument("--name", default="NanGuo Pinyin")
    p.add_argument("--author", default="Unknown")
    p.add_argument("--url", default="")
    p.add_argument("--out", default="./output")
    p.add_argument("--year", default="2026")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--variations-ps-prefix", default="",
                   help="value for name[25]; auto-detected from --name if empty")
    a = p.parse_args()

    cfg = load_config(Path(a.config))

    ps_prefix = re.sub(r"[^A-Za-z0-9]", "", a.name)
    var_ps = a.variations_ps_prefix
    if not var_ps:
        var_ps = "NotoSerifSC" if "Serif" in a.name else "NotoSansSC"

    src = TTFont(a.font)
    sf = detect_subfamily(src)

    cfg_dict = dict(
        name=a.name,
        author=a.author,
        url=a.url,
        ps_prefix=ps_prefix,
        year=a.year,
        variations_ps_prefix=var_ps,
        subfamily=sf["subfamily"],
        weight_class=sf["weight_class"],
        is_bold=sf["is_bold"],
    )

    print(f"\n{'=' * 58}")
    print(f" {a.name} {sf['subfamily']} Font Builder (v2)")
    print(f"{'=' * 58}")

    print("[1] Detecting font metrics...")
    m = detect_metrics(src, cfg)
    print(f"  UPM={m['upm']}  CJK_ADV={m['cjk_adv']}  "
          f"ruby_y={m['ruby_y']}  ruby_em={m['ruby_em']}  "
          f"subfamily={sf['subfamily']} (weight={sf['weight_class']})")

    with open(DATA_DIR / "pinyin_map.json", encoding="utf-8") as f:
        pmap = json.load(f)
    with open(DATA_DIR / "heteronym_map.json", encoding="utf-8") as f:
        het = json.load(f)
    with open(DATA_DIR / "syllable_inventory.json", encoding="utf-8") as f:
        inv = json.load(f)
    print(f"  {len(pmap):,} chars · {len(inv):,} syllables · {len(het):,} polyphones")

    warn: list[str] = []

    p2_path, syl_map = phase2_pua(a.font, inv, m, cfg, warn)
    p3_path, vm_path = phase3_composites(p2_path, syl_map, pmap, het, m, cfg, warn)
    phase4_variants(p3_path, vm_path, cfg_dict, cfg, m, pmap, a.out, warn)

    for tmpf in (p2_path, p3_path, syl_map, vm_path):
        try:
            os.unlink(tmpf)
        except OSError:
            pass

    if warn:
        print("\nBuild warnings:")
        for w in warn[:20]:
            print(f"  - {w}")
        if len(warn) > 20:
            print(f"  ... and {len(warn) - 20} more")

    fname_suffix = "" if sf["subfamily"] == "Regular" else f"-{sf['subfamily']}"
    print(f"\nDone -- {a.out}/")
    print(f"  {ps_prefix}-1{fname_suffix}.ttf  ..  {ps_prefix}-{cfg['variants']['count']}{fname_suffix}.ttf")


if __name__ == "__main__":
    main()
