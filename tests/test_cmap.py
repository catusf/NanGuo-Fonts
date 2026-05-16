"""cmap coverage tests.

Verifies GB2312 hanzi coverage and that all 12 variants expose the same
codepoint set (variants must differ only in *which* glyph each codepoint
maps to, not whether it maps).
"""

from __future__ import annotations

import random

from fontTools.ttLib import TTFont


def test_gb2312_codepoints_covered(ttfont, gb2312_chars):
    cmap = ttfont.getBestCmap()
    covered_codepoints = {ord(c) for c in gb2312_chars}
    missing = covered_codepoints - set(cmap.keys())
    missing_chars = sorted(chr(cp) for cp in list(missing)[:10])
    assert not missing, (
        f"{len(missing)} GB2312 codepoints not mapped; first 10: {missing_chars}"
    )


def _assert_cmap_consistent_within_family(family_paths):
    """Within a family, all 6 variants must expose the exact same codepoint set.

    Sans and Serif legitimately differ (base fonts Noto Sans SC vs Noto Serif SC
    have slightly different CJK coverage), so we only assert within family.
    """
    sets: list[tuple[str, frozenset[int]]] = []
    for p in family_paths:
        tt = TTFont(str(p), lazy=True)
        try:
            sets.append((p.name, frozenset(tt.getBestCmap().keys())))
        finally:
            tt.close()
    base_name, base_set = sets[0]
    diffs: list[str] = []
    for name, s in sets[1:]:
        sym_diff = s ^ base_set
        if sym_diff:
            diffs.append(f"{name} vs {base_name}: {len(sym_diff)} codepoints differ")
    assert not diffs, "; ".join(diffs)


def test_sans_cmap_codepoint_set_identical_across_variants(sans_ttfs):
    _assert_cmap_consistent_within_family(sans_ttfs)


def test_serif_cmap_codepoint_set_identical_across_variants(serif_ttfs):
    _assert_cmap_consistent_within_family(serif_ttfs)


def _variant1_path(family_paths):
    for p in family_paths:
        if p.stem.endswith("-1"):
            return p
    raise AssertionError(f"no -1 variant in {family_paths}")


def _assert_variant1_cjk_composites(family_paths, gb2312_chars, sample_size=200):
    path = _variant1_path(family_paths)
    tt = TTFont(str(path))
    try:
        cmap = tt.getBestCmap()
        glyf = tt["glyf"]
        rng = random.Random(0xCAFE)
        sample = rng.sample(sorted(gb2312_chars), min(sample_size, len(gb2312_chars)))
        non_composite: list[str] = []
        for ch in sample:
            cp = ord(ch)
            if cp not in cmap:
                continue
            if not glyf[cmap[cp]].isComposite():
                non_composite.append(ch)
        ratio = len(non_composite) / len(sample)
        assert ratio < 0.05, (
            f"{len(non_composite)}/{len(sample)} sampled GB2312 glyphs in {path.name} "
            f"are NOT composites (ruby missing); first 10: {non_composite[:10]}"
        )
    finally:
        tt.close()


def test_sans_variant1_cjk_glyphs_are_composite(sans_ttfs, gb2312_chars):
    _assert_variant1_cjk_composites(sans_ttfs, gb2312_chars)


def test_serif_variant1_cjk_glyphs_are_composite(serif_ttfs, gb2312_chars):
    _assert_variant1_cjk_composites(serif_ttfs, gb2312_chars)
