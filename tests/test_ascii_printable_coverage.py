"""All 95 printable ASCII codepoints must be in the cmap.

Per Output_font_requirements.md §5: `cmap_coverage.ascii_printable_required`.
Without this, basic punctuation and Latin letters fall back to a system
font in tools that don't do good cascading (older Office releases, e-readers).
"""

from __future__ import annotations

PRINTABLE_ASCII = set(range(0x20, 0x7F))  # 0x20..0x7E inclusive, 95 codepoints


def test_ascii_printable_codepoints_present(ttfont):
    cmap = ttfont.getBestCmap()
    missing = sorted(PRINTABLE_ASCII - set(cmap.keys()))
    assert not missing, (
        f"{len(missing)} printable ASCII codepoints missing: "
        f"{[chr(cp) for cp in missing[:10]]}"
    )
