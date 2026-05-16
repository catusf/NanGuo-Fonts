"""post table format gate — the actual Word/PowerPoint rendering blocker.

The build script emits post format 2.0 with ~10,000 glyph names of the form
`uniXXXX.base`. The `uniXXXX` AGL prefix declares the glyph is the Unicode
codepoint U+XXXX, but those glyphs are *components* of composites that
cmap from a DIFFERENT codepoint (e.g. `uni2F00.base` is the base outline
for the composite that cmaps from U+4E00). DirectWrite applies stricter
AGL validation than legacy GDI: the font passes directory-load sanity
(appears in the font picker) but Word/PowerPoint refuse to draw glyphs.

The known-working reference good/NanGuoPinyin-1.ttf uses post format 3.0
(no glyph names stored on disk; fontTools synthesises them at load time)
and avoids the issue entirely.

Fix: in make_pinyin_font.py, set `tt["post"].formatType = 3.0` before
saving. This also drops ~460KB of useless table data per file.
"""

from __future__ import annotations

import re

import pytest
from fontTools.ttLib import TTFont

AGL_UNI_NAME = re.compile(r"^uni([0-9A-F]{4,6})($|\.)")


def test_post_format_is_renderer_safe(ttf_path):
    """post.formatType must be 3.0 (or 4.0) to render in Word/PowerPoint.

    Format 2.0 with the build's naming convention triggers DirectWrite's
    AGL validation and the font is rejected for rendering. See module
    docstring for full context.
    """
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        fmt = tt["post"].formatType
        assert fmt in (3.0, 4.0), (
            f"post.formatType={fmt}; expected 3.0 (or 4.0). "
            "Format 2.0 with the build's uniXXXX.base glyph names breaks "
            "Word/PowerPoint rendering. Fix in make_pinyin_font.py by "
            "setting tt['post'].formatType = 3.0 before save."
        )
    finally:
        tt.close()


def test_post_glyph_names_match_cmap_codepoint(ttf_path):
    """If post 2.0 IS used, no AGL `uniXXXX` prefix may disagree with the
    glyph's cmap codepoint. Skipped when post is already format 3.0/4.0.
    """
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        fmt = tt["post"].formatType
        if fmt not in (2.0,):
            pytest.skip(f"post format {fmt} — AGL-mismatch check not applicable")

        cmap = tt.getBestCmap()
        # Reverse: glyph_name -> set of codepoints that map to it
        glyph_to_cps: dict[str, set[int]] = {}
        for cp, gn in cmap.items():
            glyph_to_cps.setdefault(gn, set()).add(cp)

        mismatches: list[tuple[str, int]] = []
        for gn in tt.getGlyphOrder():
            m = AGL_UNI_NAME.match(gn)
            if not m:
                continue
            declared = int(m.group(1), 16)
            cps = glyph_to_cps.get(gn, set())
            if not cps:
                # uniXXXX-named glyph not in cmap — common for composite parts
                # like uniXXXX.base; declared codepoint never reached
                continue
            if declared not in cps:
                mismatches.append((gn, declared))

        assert not mismatches, (
            f"{len(mismatches)} glyphs have AGL uniXXXX prefix that disagrees "
            f"with their cmap codepoint; first 5: {mismatches[:5]}"
        )
    finally:
        tt.close()
