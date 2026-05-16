"""Every table must decompile without errors.

Catches the class of bug that produced the Word/PowerPoint non-rendering
issue: vhea declared more long vertical metrics than vmtx contained,
fontTools (and DirectWrite) bailed when accessing vmtx. The check is
trivial — touch each table tag with __getitem__ and let fontTools raise
on malformed binary.
"""

from __future__ import annotations

import pytest
from fontTools.ttLib import TTFont, TTLibError


def test_all_tables_decompile(ttf_path):
    """Force fontTools to fully decompile every table in the font."""
    tt = TTFont(str(ttf_path))
    failures: list[str] = []
    try:
        for tag in list(tt.reader.keys()):
            try:
                tt[tag]
            except TTLibError as exc:
                failures.append(f"{tag}: {exc}")
    finally:
        tt.close()
    assert not failures, "tables that failed to decompile:\n  " + "\n  ".join(failures)


def test_vmtx_matches_vhea(ttf_path):
    """If vhea/vmtx are present, their byte counts must agree."""
    import struct
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        if "vhea" not in tt.reader or "vmtx" not in tt.reader:
            pytest.skip("no vhea/vmtx (font is horizontal-only — fine)")
        raw_vhea = tt.reader["vhea"]
        raw_vmtx = tt.reader["vmtx"]
        num_glyphs = tt["maxp"].numGlyphs
        num_long = struct.unpack(">H", raw_vhea[34:36])[0]
        expected = 4 * num_long + 2 * (num_glyphs - num_long)
        actual = len(raw_vmtx)
        assert actual == expected, (
            f"vmtx size {actual} != expected {expected} "
            f"(numOfLongVerMetrics={num_long}, numGlyphs={num_glyphs})"
        )
    finally:
        tt.close()


def test_hmtx_matches_hhea(ttf_path):
    """Same sanity check for horizontal metrics."""
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        hhea = tt["hhea"]
        num_glyphs = tt["maxp"].numGlyphs
        num_long = hhea.numberOfHMetrics
        hmtx_entries = len(tt["hmtx"].metrics)
        assert hmtx_entries == num_glyphs, (
            f"hmtx entries {hmtx_entries} != numGlyphs {num_glyphs}"
        )
        assert 0 < num_long <= num_glyphs, (
            f"hhea.numberOfHMetrics={num_long} not in (0, {num_glyphs}]"
        )
    finally:
        tt.close()
