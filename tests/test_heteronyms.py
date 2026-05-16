"""Heteronym divergence — variants -2..-6 must supply alternate readings.

For each character pypinyin confirms has ≥2 readings, variant -2's glyph
for that codepoint must differ from variant -1's. We require ≥70% of the
sample to diverge per CLAUDE.md's "~73% heteronym coverage by primary
reading" — the inverse is the actionable assertion.

We compare glyph IDs, not glyph names: with post.formatType=3.0 (required
by spec §2) fontTools synthesizes glyph names as `uniXXXX` from the lowest
codepoint that maps to each glyph. Two physically different glyphs can
both end up named `uniXXXX` if neither has a co-mapping codepoint, which
would make a name-based comparison falsely report "same". GIDs are the
underlying ground truth.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont


def _gid_map(path):
    """codepoint -> GID, the rendering-truth identifier."""
    tt = TTFont(str(path), lazy=True)
    try:
        cmap = tt.getBestCmap()
        return {cp: tt.getGlyphID(gn) for cp, gn in cmap.items()}
    finally:
        tt.close()


def _divergence_ratio(family_paths, heteronym_sample, variant_idx):
    """Fraction of sample chars whose GID in variant_idx differs from variant 1."""
    v1 = _gid_map(family_paths[0])  # -1
    vn = _gid_map(family_paths[variant_idx - 1])  # -N
    diff = 0
    counted = 0
    for ch in heteronym_sample:
        cp = ord(ch)
        if cp in v1 and cp in vn:
            counted += 1
            if v1[cp] != vn[cp]:
                diff += 1
    if not counted:
        return 0.0, 0, 0
    return diff / counted, diff, counted


def test_sans_variant2_diverges_from_variant1(sans_ttfs, heteronym_sample):
    ratio, diff, total = _divergence_ratio(sans_ttfs, heteronym_sample, 2)
    assert ratio >= 0.70, (
        f"Sans -2 vs -1 heteronym divergence {diff}/{total} ({ratio:.0%}) < 70% — "
        "alternate readings missing for too many heteronyms"
    )


def test_serif_variant2_diverges_from_variant1(serif_ttfs, heteronym_sample):
    ratio, diff, total = _divergence_ratio(serif_ttfs, heteronym_sample, 2)
    assert ratio >= 0.70, (
        f"Serif -2 vs -1 heteronym divergence {diff}/{total} ({ratio:.0%}) < 70%"
    )


def test_sans_higher_variants_provide_some_alternates(sans_ttfs, heteronym_sample):
    """At least variant -3 should still carry some alternates (not be a -1 clone)."""
    ratio, diff, total = _divergence_ratio(sans_ttfs, heteronym_sample, 3)
    assert diff > 0, f"Sans -3 has zero divergence from -1 on {total} heteronyms"


def test_serif_higher_variants_provide_some_alternates(serif_ttfs, heteronym_sample):
    ratio, diff, total = _divergence_ratio(serif_ttfs, heteronym_sample, 3)
    assert diff > 0, f"Serif -3 has zero divergence from -1 on {total} heteronyms"
