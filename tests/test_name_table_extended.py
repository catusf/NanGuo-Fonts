"""Extended name table conformance beyond test_name_table.py.

Per Output_font_requirements.md §7: name IDs 10 (Description), 25
(Variations PostScript prefix), and the STAT axis-value records (IDs 256+)
must be present. name[25] is family-specific (NotoSansSC vs NotoSerifSC).
"""

from __future__ import annotations

from tests.conftest import win_name


def test_name_id_10_description_present(ttfont):
    val = win_name(ttfont, 10)
    assert val, "name[10] (Description) missing on Windows platform"


def test_name_id_25_variations_ps_prefix_present(ttfont):
    val = win_name(ttfont, 25)
    assert val, "name[25] (Variations PostScript prefix) missing"
    assert val in {"NotoSansSC", "NotoSerifSC"}, (
        f"name[25]={val!r} should be 'NotoSansSC' or 'NotoSerifSC'"
    )


def test_name_id_25_matches_family(ttf_path, ttfont):
    """Sans variants → NotoSansSC; Serif variants → NotoSerifSC."""
    val = win_name(ttfont, 25)
    family = "Serif" if "Serif" in ttf_path.stem else "Sans"
    expected = f"Noto{family}SC"
    assert val == expected, (
        f"{ttf_path.name}: name[25]={val!r} != expected {expected!r}"
    )


def test_stat_axis_value_records_present(ttfont):
    """At least one name record with ID >= 256 (STAT axis-value names)."""
    stat_ids = sorted({r.nameID for r in ttfont["name"].names if r.nameID >= 256})
    assert stat_ids, "no STAT axis-value name records (ID >= 256) found"
