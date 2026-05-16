"""Glyph ordering is deterministic — new glyphs appear in sorted order.

Per Output_font_requirements.md §8: "Glyph ordering: deterministic between
runs (sort by codepoint, then by component-glyph index) so identical
inputs produce byte-identical output where possible."

A full byte-identity check requires two builds and is too slow for CI;
instead we verify the structural invariant: within the new glyph
namespaces (.pynbase, .v2..vN, uniEXXX PUA), names appear in sorted
order in the font's glyph order.
"""

from __future__ import annotations

import re

PUA_PATTERN = re.compile(r"^uni([EF][0-9A-F]{3})$")
PYNBASE_PATTERN = re.compile(r"^uni([0-9A-F]{4,6})\.pynbase2?$")
VARIANT_PATTERN = re.compile(r"^uni([0-9A-F]{4,6})\.v([2-6])$")


def _filter_indices(order, pattern):
    return [(i, m.group(1)) for i, name in enumerate(order)
            for m in [pattern.match(name)] if m]


def _is_monotonic(values: list[str]) -> bool:
    return values == sorted(values)


def test_pua_glyphs_in_sorted_order(ttfont):
    order = ttfont.getGlyphOrder()
    pua = [m.group(1) for name in order
           for m in [PUA_PATTERN.match(name)] if m and 0xE000 <= int(m.group(1), 16) <= 0xE7DA]
    assert pua, "no PUA ruby glyphs found"
    assert _is_monotonic(pua), (
        f"PUA glyph names not in sorted order; first 5: {pua[:5]}, last 5: {pua[-5:]}"
    )


def test_pynbase_glyphs_in_sorted_order(ttfont):
    order = ttfont.getGlyphOrder()
    pyns = [m.group(1) for name in order
            for m in [PYNBASE_PATTERN.match(name)] if m]
    if not pyns:
        return  # variant-2..6 reuse primary, so .pynbase may be absent on some builds
    assert _is_monotonic(pyns), (
        f".pynbase glyph names not in sorted order; first 5: {pyns[:5]}"
    )


def test_variant_glyphs_per_index_in_sorted_order(ttfont):
    """Within each variant index (v2, v3, ...), names appear in sorted codepoint order."""
    order = ttfont.getGlyphOrder()
    per_v: dict[str, list[str]] = {}
    for name in order:
        m = VARIANT_PATTERN.match(name)
        if not m:
            continue
        per_v.setdefault(m.group(2), []).append(m.group(1))
    for v, cps in per_v.items():
        assert _is_monotonic(cps), (
            f".v{v} glyph names not in sorted order; first 5: {cps[:5]}"
        )
