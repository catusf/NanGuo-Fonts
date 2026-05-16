"""Basic TTF structural integrity — opens, has glyf, sane UPM, Unicode cmap."""

from __future__ import annotations


def test_has_glyf_outlines(ttfont):
    assert "glyf" in ttfont, "expected TrueType outlines (glyf table)"
    assert "CFF " not in ttfont, "CFF outlines not supported by the build pipeline"
    assert "CFF2" not in ttfont, "CFF2 outlines not supported by the build pipeline"


def test_units_per_em(ttfont):
    upm = ttfont["head"].unitsPerEm
    assert upm in {1000, 1024, 2048}, f"unexpected unitsPerEm: {upm}"


def test_num_glyphs(ttfont):
    n = ttfont["maxp"].numGlyphs
    assert n > 6000, f"only {n} glyphs — GB2312 + ruby composites should produce many more"


def test_has_unicode_cmap_subtable(ttfont):
    has_unicode = any(
        (t.platformID == 3 and t.platEncID in (1, 10)) or t.platformID == 0
        for t in ttfont["cmap"].tables
    )
    assert has_unicode, "no Unicode cmap subtable found"


def test_required_tables_present(ttfont):
    required = {"head", "hhea", "maxp", "name", "OS/2", "cmap", "glyf", "loca", "post"}
    missing = required - set(ttfont.keys())
    assert not missing, f"missing required tables: {sorted(missing)}"
