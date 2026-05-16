"""Single-reading hanzi: ruby in V1 only; V2..V6 are blank (FZKTPY-style).

Per user spec: when a character has no FZKTPY0N reading for variant N, v2
maps the codepoint to the U+3000 (ideographic space) glyph — NOT a fallback
to V1's ruby. This mimics FZKTPY's actual design where variants 4..6 of a
single-reading character render literally blank.

Curated single-reading hanzi: variant -1's cmap[cp] must resolve to a
2-component composite whose second component is PUA-named. Variants
-2..-6 must resolve cmap[cp] to the SAME glyph as cmap[U+3000] (the
blank ideographic-space glyph).
"""

from __future__ import annotations

import re

import pytest
from fontTools.ttLib import TTFont

PUA_NAME_PATTERN = re.compile(r"^uni([EFef][0-9A-Fa-f]{3})$")


def _is_pua_name(name: str) -> bool:
    m = PUA_NAME_PATTERN.match(name)
    if not m:
        return False
    cp = int(m.group(1), 16)
    return 0xE000 <= cp <= 0xF8FF


@pytest.fixture(scope="module")
def single_reading_chars(gb2312_chars):
    pypinyin = pytest.importorskip("pypinyin")
    from pypinyin import Style

    out: list[str] = []
    # A modest curated set of common single-reading hanzi.
    candidates = "我你他她它们的了是在有不和这那一二三四五六七八九十百千万亿"
    for ch in candidates:
        if ch not in gb2312_chars:
            continue
        readings = pypinyin.pinyin(ch, heteronym=True, style=Style.NORMAL)
        if readings and len(readings[0]) == 1:
            out.append(ch)
    if not out:
        pytest.skip("no usable single-reading hanzi from curated list")
    return out


def _v1_has_pua_composite(tt: TTFont, ch: str) -> tuple[bool, str]:
    cmap = tt.getBestCmap()
    cp = ord(ch)
    if cp not in cmap:
        return False, f"{ch} not in cmap"
    g = tt["glyf"][cmap[cp]]
    if not g.isComposite():
        return False, f"{ch} -> {cmap[cp]!r} not composite"
    if len(g.components) != 2:
        return False, f"{ch} -> {cmap[cp]!r} has {len(g.components)} components"
    ruby = g.components[1].glyphName
    if not _is_pua_name(ruby):
        return False, f"{ch} -> {cmap[cp]!r} 2nd component {ruby!r} not PUA"
    return True, ""


def _variant_is_blank(tt: TTFont, ch: str, blank_glyph: str) -> tuple[bool, str]:
    """Variant N's cmap for `ch` resolves to the U+3000 glyph (blank)."""
    cmap = tt.getBestCmap()
    cp = ord(ch)
    target = cmap.get(cp)
    if target is None:
        return False, f"{ch} unmapped (should map to blank, not be absent)"
    if target != blank_glyph:
        return False, f"{ch} -> {target!r}, expected blank {blank_glyph!r}"
    return True, ""


def _check_family(family_paths, single_reading_chars):
    # Determine the blank-glyph name from variant -1 (cmap[U+3000]).
    v1 = TTFont(str(family_paths[0]), lazy=True)
    try:
        blank_glyph = v1.getBestCmap().get(0x3000)
    finally:
        v1.close()
    assert blank_glyph, "variant -1 has no U+3000 mapping; cannot determine blank target"

    v1_failures: list[str] = []
    blank_failures: list[str] = []

    for i, p in enumerate(family_paths):
        tt = TTFont(str(p), lazy=True)
        try:
            for ch in single_reading_chars:
                if i == 0:
                    ok, reason = _v1_has_pua_composite(tt, ch)
                    if not ok:
                        v1_failures.append(f"{p.name}: {reason}")
                else:
                    ok, reason = _variant_is_blank(tt, ch, blank_glyph)
                    if not ok:
                        blank_failures.append(f"{p.name}: {reason}")
        finally:
            tt.close()

    # Allow ≤5% noise on V1 composite check for edge cases where pypinyin
    # reports a single reading but FZKTPY built it as a heteronym.
    n = len(single_reading_chars)
    assert len(v1_failures) / n <= 0.05, (
        f"{len(v1_failures)}/{n} V1 single-reading hanzi missing PUA ruby; "
        f"first 5: {v1_failures[:5]}"
    )
    # Same tolerance for blank check.
    blank_total = n * (len(family_paths) - 1)
    assert len(blank_failures) / blank_total <= 0.05, (
        f"{len(blank_failures)}/{blank_total} V2..V6 single-reading hanzi "
        f"NOT mapped to blank; first 5: {blank_failures[:5]}"
    )


def test_sans_single_reading_v1_ruby_v2plus_blank(sans_ttfs, single_reading_chars):
    _check_family(sans_ttfs, single_reading_chars)


def test_serif_single_reading_v1_ruby_v2plus_blank(serif_ttfs, single_reading_chars):
    _check_family(serif_ttfs, single_reading_chars)
