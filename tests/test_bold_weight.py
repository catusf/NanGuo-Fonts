"""Bold variants — verify weight + style bits are wired correctly.

For Word/Office to pair Bold with Regular under one family (Ctrl+B toggles
weight, not face), each Bold TTF must:
- Carry usWeightClass=700
- Set macStyle bold bit (0x01) and fsSelection BOLD (0x20)
- NOT set fsSelection REGULAR (0x40)
- Share name[1] / name[7] (family) with its Regular sibling
- Have name[2] = "Bold" and PostScript name ending in "-Bold"
"""

from __future__ import annotations

from fontTools.ttLib import TTFont

from tests.conftest import win_name


def _open(p):
    return TTFont(str(p), lazy=True)


def _check_bold_metadata(path):
    tt = _open(path)
    try:
        assert tt["OS/2"].usWeightClass == 700, (
            f"{path.name}: usWeightClass={tt['OS/2'].usWeightClass}, expected 700"
        )
        ms = tt["head"].macStyle
        fs = tt["OS/2"].fsSelection
        assert ms & 0x01, f"{path.name}: macStyle bold bit not set (0x{ms:04x})"
        assert fs & 0x20, f"{path.name}: fsSelection BOLD bit not set (0x{fs:04x})"
        assert not (fs & 0x40), (
            f"{path.name}: fsSelection REGULAR bit MUST NOT be set on a Bold (0x{fs:04x})"
        )
        assert win_name(tt, 2) == "Bold", f"{path.name}: name[2]={win_name(tt, 2)!r}"
        assert win_name(tt, 17) == "Bold", f"{path.name}: name[17]={win_name(tt, 17)!r}"
        assert win_name(tt, 6).endswith("-Bold"), (
            f"{path.name}: PostScript name {win_name(tt, 6)!r} missing -Bold suffix"
        )
    finally:
        tt.close()


def _check_pairs_share_family(regular_paths, bold_paths):
    """Regular variant N and Bold variant N must share name[1] (family) so
    Word treats them as one family with two weights."""
    for r, b in zip(regular_paths, bold_paths):
        tr, tb = _open(r), _open(b)
        try:
            fr, fb = win_name(tr, 1), win_name(tb, 1)
            assert fr == fb, (
                f"family name diverges: {r.name} → {fr!r}, {b.name} → {fb!r}"
            )
        finally:
            tr.close(); tb.close()


def test_sans_bold_metadata(sans_bold_ttfs):
    for p in sans_bold_ttfs:
        _check_bold_metadata(p)


def test_sans_bold_pairs_share_family(sans_ttfs, sans_bold_ttfs):
    _check_pairs_share_family(sans_ttfs, sans_bold_ttfs)


def test_serif_bold_metadata(serif_bold_ttfs):
    for p in serif_bold_ttfs:
        _check_bold_metadata(p)


def test_serif_bold_pairs_share_family(serif_ttfs, serif_bold_ttfs):
    _check_pairs_share_family(serif_ttfs, serif_bold_ttfs)
