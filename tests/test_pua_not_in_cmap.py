"""PUA codepoints must not be exposed in the best Unicode cmap.

Per Output_font_requirements.md §4–§5: the ruby PUA glyphs are internal-only.
Apps and shaping engines must see them through the composite mechanism, not
by typing PUA characters directly. We enforce on `getBestCmap()` (fmt-12
preferred), which is what apps actually consult. The legacy fmt-4 subtable
is allowed to retain PUA entries so fontTools can resynthesize the
`uniXXXX` glyph names on reload — matching the reference output.
"""

from __future__ import annotations

import pathlib

import yaml


def _load_pua_range() -> tuple[int, int]:
    cfg_path = pathlib.Path(__file__).resolve().parent.parent / "sources" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return int(cfg["pua_range"]["start"], 16), int(cfg["pua_range"]["end"], 16)


def test_no_pua_in_best_cmap(ttfont):
    lo, hi = _load_pua_range()
    best = ttfont.getBestCmap()
    exposed = sorted(cp for cp in best if lo <= cp <= hi)
    assert not exposed, (
        f"{len(exposed)} PUA codepoints exposed in best Unicode cmap; "
        f"first 5: {[hex(c) for c in exposed[:5]]}"
    )


def test_no_pua_in_fmt12_cmap(ttfont):
    lo, hi = _load_pua_range()
    for t in ttfont["cmap"].tables:
        if t.format != 12 or not getattr(t, "cmap", None):
            continue
        exposed = [cp for cp in t.cmap if lo <= cp <= hi]
        assert not exposed, (
            f"cmap subtable plat={t.platformID} fmt=12 leaks "
            f"{len(exposed)} PUA codepoints"
        )
