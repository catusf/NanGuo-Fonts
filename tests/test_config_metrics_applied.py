"""Every metric declared in config.json → metrics_at_upm_1000 must land on
the font, scaled linearly to the font's UPM.

This is the contract that lets reviewers tune values centrally in
config.json without touching the build script. A ±2-unit tolerance covers
the integer rounding in `int(round(v * upm / 1000))`.
"""

from __future__ import annotations

import pathlib

import yaml

import pytest


TOL = 2  # accept 1-unit rounding jitter on either side


def _cfg():
    p = pathlib.Path(__file__).resolve().parent.parent / "sources" / "config.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _expected(value_at_1000: float, upm: int) -> int:
    return int(round(value_at_1000 * upm / 1000))


def _check(actual: int, expected: int, label: str):
    assert abs(actual - expected) <= TOL, (
        f"{label}: actual={actual}, expected={expected} (±{TOL})"
    )


def test_hhea_metrics_match_config(ttfont):
    cfg = _cfg()
    M = cfg["metrics_at_upm_1000"]
    upm = ttfont["head"].unitsPerEm
    hhea = ttfont["hhea"]
    _check(hhea.ascent, _expected(M["hhea_ascent"], upm), "hhea.ascent")
    _check(hhea.descent, _expected(M["hhea_descent"], upm), "hhea.descent")
    _check(hhea.lineGap, _expected(M["hhea_line_gap"], upm), "hhea.lineGap")


def test_os2_win_metrics_match_config(ttfont):
    cfg = _cfg()
    M = cfg["metrics_at_upm_1000"]
    upm = ttfont["head"].unitsPerEm
    os2 = ttfont["OS/2"]
    _check(os2.usWinAscent, _expected(M["os2_win_ascent"], upm), "usWinAscent")
    _check(os2.usWinDescent, _expected(M["os2_win_descent"], upm), "usWinDescent")


def test_os2_typo_metrics_match_config(ttfont):
    cfg = _cfg()
    M = cfg["metrics_at_upm_1000"]
    upm = ttfont["head"].unitsPerEm
    os2 = ttfont["OS/2"]
    _check(os2.sTypoAscender, _expected(M["os2_typo_ascender"], upm), "sTypoAscender")
    _check(os2.sTypoDescender, _expected(M["os2_typo_descender"], upm), "sTypoDescender")
    _check(os2.sTypoLineGap, _expected(M["os2_typo_line_gap"], upm), "sTypoLineGap")


def test_os2_classes_match_config(ttfont):
    """Width class comes from config; weight class is per-subfamily.

    Regular → 400, Bold → 700. The build script reads usWeightClass and
    name[2] from the source font (Noto), so the assertion mirrors that.
    """
    cfg = _cfg()
    M = cfg["metrics_at_upm_1000"]
    os2 = ttfont["OS/2"]

    sf_rec = ttfont["name"].getName(2, 3, 1, 0x409)
    subfamily = str(sf_rec).strip() if sf_rec else "Regular"
    expected_weight = {"Regular": 400, "Bold": 700}.get(subfamily, M["os2_weight_class"])
    assert os2.usWeightClass == expected_weight, (
        f"usWeightClass={os2.usWeightClass} != {expected_weight} for subfamily {subfamily!r}"
    )
    assert os2.usWidthClass == M["os2_width_class"], (
        f"usWidthClass={os2.usWidthClass} != {M['os2_width_class']}"
    )


def test_os2_fsType_matches_config(ttfont):
    cfg = _cfg()
    assert ttfont["OS/2"].fsType == cfg["os2_flags"]["fs_type"], (
        f"fsType={ttfont['OS/2'].fsType} != {cfg['os2_flags']['fs_type']}"
    )
