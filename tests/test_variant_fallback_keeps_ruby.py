"""Single-reading hanzi: ruby in V1 only; V2..V6 fall back to bare hanzi.

When a character has no FZKTPY0N reading for variant N, V2..V6 map the
codepoint to the original bare-hanzi base glyph (the source font's
unaltered character contours) — NOT a fallback to V1's ruby, and NOT a
blank/ideographic-space glyph. The codepoint still renders as the
character, just without a pinyin ruby on top.

Curated single-reading hanzi: variant -1's cmap[cp] must resolve to a
2-component composite whose second component is PUA-named. Variants
-2..-6 must resolve cmap[cp] to a glyph that does NOT carry a PUA-named
ruby component (i.e., the bare hanzi).
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


def _variant_is_bare_hanzi(tt: TTFont, ch: str) -> tuple[bool, str]:
    """Variant N's cmap for `ch` resolves to a glyph that has no PUA-named ruby.

    The bare hanzi may be either a simple contour glyph or a composite of
    CJK radicals (Noto SC often builds hanzi from radical components).
    What it must NOT contain is a PUA-named component — that would mean
    V2..V6 still carries V1's ruby.
    """
    cmap = tt.getBestCmap()
    cp = ord(ch)
    target = cmap.get(cp)
    if target is None:
        return False, f"{ch} unmapped"
    g = tt["glyf"][target]
    if g.isComposite():
        for c in g.components:
            if _is_pua_name(c.glyphName):
                return False, (
                    f"{ch} -> {target!r} has PUA ruby component "
                    f"{c.glyphName!r} (expected bare hanzi)"
                )
    return True, ""


def _check_family(family_paths, single_reading_chars):
    v1_failures: list[str] = []
    bare_failures: list[str] = []

    for i, p in enumerate(family_paths):
        tt = TTFont(str(p), lazy=True)
        try:
            for ch in single_reading_chars:
                if i == 0:
                    ok, reason = _v1_has_pua_composite(tt, ch)
                    if not ok:
                        v1_failures.append(f"{p.name}: {reason}")
                else:
                    ok, reason = _variant_is_bare_hanzi(tt, ch)
                    if not ok:
                        bare_failures.append(f"{p.name}: {reason}")
        finally:
            tt.close()

    # Allow ≤5% noise on V1 composite check for edge cases where pypinyin
    # reports a single reading but the heteronym map built it as a heteronym.
    n = len(single_reading_chars)
    assert len(v1_failures) / n <= 0.05, (
        f"{len(v1_failures)}/{n} V1 single-reading hanzi missing PUA ruby; "
        f"first 5: {v1_failures[:5]}"
    )
    # Same tolerance for the bare-hanzi check on V2..V6.
    bare_total = n * (len(family_paths) - 1)
    assert len(bare_failures) / bare_total <= 0.05, (
        f"{len(bare_failures)}/{bare_total} V2..V6 single-reading hanzi "
        f"still carry PUA ruby; first 5: {bare_failures[:5]}"
    )


def test_sans_single_reading_v1_ruby_v2plus_bare(sans_ttfs, single_reading_chars):
    _check_family(sans_ttfs, single_reading_chars)


def test_serif_single_reading_v1_ruby_v2plus_bare(serif_ttfs, single_reading_chars):
    _check_family(serif_ttfs, single_reading_chars)
