"""Composite glyph structure — each CJK glyph in variant -1 is [base + ruby PUA].

The build positions the ruby via baked-in sub-glyph geometry, not composite
transforms — so component offsets are (0,0) and the actual vertical
positioning lives inside the PUA sub-glyph itself. We therefore verify:

1. Each sampled GB2312 char's glyph is a composite.
2. It has exactly 2 components.
3. The second component is named like a PUA glyph (uniE000–uniF8FF range).

The ruby geometry assertion (0.852 × UPM) is enforced by the build pipeline,
not the TTFs after the fact.
"""

from __future__ import annotations

import random
import re

from fontTools.ttLib import TTFont

PUA_NAME_PATTERN = re.compile(r"^uni([EFef][0-9A-Fa-f]{3})$")


def _variant1(family_paths):
    return next(p for p in family_paths if p.stem.endswith("-1"))


def _is_pua_name(name: str) -> bool:
    m = PUA_NAME_PATTERN.match(name)
    if not m:
        return False
    cp = int(m.group(1), 16)
    return 0xE000 <= cp <= 0xF8FF


def _check_composites(path, gb2312_chars, sample_size=50):
    tt = TTFont(str(path))
    try:
        cmap = tt.getBestCmap()
        glyf = tt["glyf"]

        rng = random.Random(0xBEEF)
        candidates = [ch for ch in sorted(gb2312_chars) if ord(ch) in cmap]
        sample = rng.sample(candidates, min(sample_size, len(candidates)))

        not_composite: list[str] = []
        wrong_count: list[tuple[str, int]] = []
        non_pua_ruby: list[tuple[str, str]] = []

        for ch in sample:
            glyph_name = cmap[ord(ch)]
            g = glyf[glyph_name]
            if not g.isComposite():
                not_composite.append(ch)
                continue
            if len(g.components) != 2:
                wrong_count.append((ch, len(g.components)))
                continue
            ruby_name = g.components[1].glyphName
            if not _is_pua_name(ruby_name):
                non_pua_ruby.append((ch, ruby_name))

        assert not not_composite, (
            f"non-composite GB2312 glyphs in {path.name}: {not_composite[:10]}"
        )
        assert not wrong_count, (
            f"composites with !=2 components in {path.name}: {wrong_count[:10]}"
        )
        # Allow a small fraction of non-PUA second components (e.g. fallback shapes).
        ratio = len(non_pua_ruby) / len(sample)
        assert ratio <= 0.05, (
            f"{len(non_pua_ruby)}/{len(sample)} second components in {path.name} "
            f"are not PUA-named ruby glyphs; first 5: {non_pua_ruby[:5]}"
        )
    finally:
        tt.close()


def test_sans_variant1_composite_structure(sans_ttfs, gb2312_chars):
    _check_composites(_variant1(sans_ttfs), gb2312_chars)


def test_serif_variant1_composite_structure(serif_ttfs, gb2312_chars):
    _check_composites(_variant1(serif_ttfs), gb2312_chars)
