"""Name table conformance for Windows + Mac platforms.

The build uses the legacy 4-style workaround: the variant number lives in
name[1] (family), name[2] is always "Regular", and name[7] (Preferred /
Trademark) carries the shared canonical family ("NanGuo Sans Pinyin"). We
verify that and flag known Google Fonts gaps (Mac name[2] missing) as
xfail so they remain on the radar without blocking the suite.
"""

from __future__ import annotations

import pytest
from fontTools.ttLib import TTFont

from tests.conftest import win_name, mac_name

REQUIRED_WIN_IDS = (1, 2, 3, 4, 5, 6)
REQUIRED_MAC_IDS = (1, 2, 4, 6)


def test_windows_name_ids_present(ttfont):
    missing = [nid for nid in REQUIRED_WIN_IDS if not win_name(ttfont, nid)]
    assert not missing, f"missing Windows (plat=3,enc=1,lang=0x409) name IDs: {missing}"


def test_mac_name_ids_present(ttfont):
    """Per Output_font_requirements.md §7: Mac platform records for name
    IDs 1, 2, 4, 6 are required for Google Fonts and macOS Font Book.
    """
    missing = [nid for nid in REQUIRED_MAC_IDS if not mac_name(ttfont, nid)]
    assert not missing, f"missing Mac (plat=1,enc=0,lang=0) name IDs: {missing}"


def test_postscript_matches_filename_stem(ttf_path, ttfont):
    ps = win_name(ttfont, 6)
    assert ps == ttf_path.stem, f"PostScript name {ps!r} != filename stem {ttf_path.stem!r}"


def test_preferred_family_present(ttfont):
    """name[7] (Trademark / Preferred Family) carries the canonical shared family."""
    assert win_name(ttfont, 7), "name[7] (Preferred / Trademark family) missing"


def test_name_strings_clean(ttfont):
    bad: list[str] = []
    for rec in ttfont["name"].names:
        s = str(rec)
        if "\x00" in s or s != s.strip():
            bad.append(f"id={rec.nameID} plat={rec.platformID} value={s!r}")
    assert not bad, f"unclean name records: {bad}"


def _preferred_family(path):
    tt = TTFont(str(path), lazy=True)
    try:
        return win_name(tt, 7)
    finally:
        tt.close()


def test_sans_preferred_family_shared(sans_ttfs):
    fams = {_preferred_family(p) for p in sans_ttfs}
    assert len(fams) == 1, f"Sans preferred family (name[7]) diverges: {fams}"


def test_serif_preferred_family_shared(serif_ttfs):
    fams = {_preferred_family(p) for p in serif_ttfs}
    assert len(fams) == 1, f"Serif preferred family (name[7]) diverges: {fams}"
