"""Test that contextual reading ligatures are correctly embedded in variant-1 fonts.

Checks two representative words:
  了解 (liǎo jiě) — 了 is le in variant-1 by default; the liga lookup must
      substitute [了, 解] with a composite glyph that carries the liǎo PUA ruby.
  北京 (běi jīng)  — neither character is in duoyinzi_combined.json, so no
      ligature rule should ever be generated for this pair.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
_DATA = ROOT / "sources" / "data"

_V1_PATHS = sorted(
    p
    for d in (ROOT / "fonts").glob("*/ttf")
    for p in d.glob("NanGuo*Pinyin-1*.ttf")
)


@pytest.fixture(params=_V1_PATHS, ids=lambda p: p.stem, scope="module")
def v1_font(request: pytest.FixtureRequest) -> TTFont:
    tt = TTFont(str(request.param), lazy=True)
    yield tt
    tt.close()


def _our_liga_subtable(font: TTFont):
    """Return the LigatureSubst subtable added by add_ligatures.py.

    Our lookup is the last Type-4 lookup referenced by the 'liga' feature.
    Returns None if the font has no such lookup.
    """
    gsub = font["GSUB"].table
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag != "liga":
            continue
        for idx in reversed(fr.Feature.LookupListIndex):
            lk = gsub.LookupList.Lookup[idx]
            if lk.LookupType == 4:
                st = lk.SubTable[0]
                st.ensureDecompiled()
                return st
    return None


# ── 了解 ─────────────────────────────────────────────────────────────────────

def test_了解_ligature_rule_exists(v1_font: TTFont) -> None:
    """GSUB must have a liga rule replacing [了, 解] with a ligature glyph."""
    best = v1_font["cmap"].getBestCmap()
    le_glyph = best.get(0x4E86)    # 了
    jie_glyph = best.get(0x89E3)   # 解
    assert le_glyph, "了 (U+4E86) missing from cmap"
    assert jie_glyph, "解 (U+89E3) missing from cmap"

    st = _our_liga_subtable(v1_font)
    assert st is not None, "No NanGuo liga lookup found in variant-1 font"

    ligs = st.ligatures.get(le_glyph, [])
    match = next((lig for lig in ligs if lig.Component == [jie_glyph]), None)
    assert match is not None, (
        f"No ligature rule for 了解 (first={le_glyph!r}, rest=[{jie_glyph!r}])"
    )


def test_了解_ligature_uses_liao_ruby(v1_font: TTFont) -> None:
    """The 了解 ligature glyph must contain the liǎo PUA ruby component."""
    inv = json.loads((_DATA / "syllable_inventory.json").read_text(encoding="utf-8"))
    liao_pua = "uni" + inv["liǎo"]["pua"].upper()   # e.g. uniE356

    best = v1_font["cmap"].getBestCmap()
    le_glyph = best.get(0x4E86)
    jie_glyph = best.get(0x89E3)

    st = _our_liga_subtable(v1_font)
    assert st is not None

    ligs = st.ligatures.get(le_glyph, [])
    match = next((lig for lig in ligs if lig.Component == [jie_glyph]), None)
    assert match is not None, "No 了解 ligature rule (run test_了解_ligature_rule_exists first)"

    g = v1_font["glyf"][match.LigGlyph]
    assert g.numberOfContours == -1, f"{match.LigGlyph!r} is not a composite glyph"
    comp_names = {c.glyphName for c in g.components}
    assert liao_pua in comp_names, (
        f"了解 ligature {match.LigGlyph!r} components {comp_names!r} "
        f"do not include liǎo PUA {liao_pua!r}"
    )


def test_了解_ligature_glyph_width(v1_font: TTFont) -> None:
    """The 了解 ligature glyph must be twice the standard CJK advance width."""
    best = v1_font["cmap"].getBestCmap()
    le_glyph = best.get(0x4E86)
    jie_glyph = best.get(0x89E3)

    st = _our_liga_subtable(v1_font)
    assert st is not None

    ligs = st.ligatures.get(le_glyph, [])
    match = next((lig for lig in ligs if lig.Component == [jie_glyph]), None)
    assert match is not None

    cjk_adv = v1_font["hmtx"].metrics[le_glyph][0]
    liga_adv = v1_font["hmtx"].metrics[match.LigGlyph][0]
    assert liga_adv == 2 * cjk_adv, (
        f"了解 ligature advance {liga_adv} != 2 × {cjk_adv}"
    )


# ── 北京 ─────────────────────────────────────────────────────────────────────

def test_北京_chars_in_cmap(v1_font: TTFont) -> None:
    """北 and 京 must both be present in the variant-1 cmap."""
    best = v1_font["cmap"].getBestCmap()
    assert best.get(0x5317), "北 (U+5317) missing from cmap"
    assert best.get(0x4EAC), "京 (U+4EAC) missing from cmap"


def test_北京_no_spurious_ligature(v1_font: TTFont) -> None:
    """北京 — neither char is in duoyinzi_combined; no liga rule should exist."""
    best = v1_font["cmap"].getBestCmap()
    bei_glyph = best.get(0x5317)   # 北
    jing_glyph = best.get(0x4EAC)  # 京

    st = _our_liga_subtable(v1_font)
    assert st is not None

    ligs = st.ligatures.get(bei_glyph, [])
    spurious = next((lig for lig in ligs if lig.Component == [jing_glyph]), None)
    assert spurious is None, (
        f"Unexpected ligature rule found for 北京 → {spurious.LigGlyph!r}"
    )
