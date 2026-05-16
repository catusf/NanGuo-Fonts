"""The 6-variant scheme — shared Preferred Family, distinct PostScript suffixes.

The build uses the legacy 4-style workaround (variant lives in name[1],
name[2] stays "Regular") so we do not assert subfamily uniqueness. We DO
assert that name[7] (Preferred / Trademark family) is shared across the 6
variants, and that PostScript suffixes run -1 through -6.

We deliberately do NOT assert "non-heteronym chars map to the same glyph
across variants" — the build legitimately uses .base / .v2 / .vN suffixes
for many CJK chars regardless of pypinyin's heteronym ranking.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont

from tests.conftest import win_name


def _preferred_family(path):
    tt = TTFont(str(path), lazy=True)
    try:
        return win_name(tt, 7)
    finally:
        tt.close()


def _postscript(path):
    tt = TTFont(str(path), lazy=True)
    try:
        return win_name(tt, 6)
    finally:
        tt.close()


def _check_family_share(family_paths):
    fams = {_preferred_family(p) for p in family_paths}
    assert len(fams) == 1, f"name[7] preferred family differs across variants: {fams}"


def _check_postscript_suffixes(family_paths):
    ps = sorted(_postscript(p).rsplit("-", 1)[-1] for p in family_paths)
    assert ps == ["1", "2", "3", "4", "5", "6"], f"PostScript suffixes wrong: {ps}"


def _check_postscript_names_unique(family_paths):
    ps = [_postscript(p) for p in family_paths]
    assert len(set(ps)) == len(ps), f"PostScript names not unique across variants: {ps}"


def test_sans_share_preferred_family(sans_ttfs):
    _check_family_share(sans_ttfs)


def test_serif_share_preferred_family(serif_ttfs):
    _check_family_share(serif_ttfs)


def test_sans_postscript_suffixes(sans_ttfs):
    _check_postscript_suffixes(sans_ttfs)


def test_serif_postscript_suffixes(serif_ttfs):
    _check_postscript_suffixes(serif_ttfs)


def test_sans_postscript_names_unique(sans_ttfs):
    _check_postscript_names_unique(sans_ttfs)


def test_serif_postscript_names_unique(serif_ttfs):
    _check_postscript_names_unique(serif_ttfs)
