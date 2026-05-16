"""OS/2 + hhea + head metric conformance.

Catches the silent regressions that cause Office line-height drift, ruby
clipping on Windows, and inconsistent face mapping across the 6 variants.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from fontTools.ttLib import TTFont

_CFG = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "config.json").read_text(
        encoding="utf-8"
    )
)
_RUBY_BASELINE = _CFG["ruby_geometry_at_upm_1000"]["baseline_y"]
_RUBY_EM = _CFG["ruby_geometry_at_upm_1000"]["em"]

FS_ITALIC = 0x01
FS_BOLD = 0x20
FS_REGULAR = 0x40
FS_USE_TYPO_METRICS = 0x80
MAC_BOLD = 0x01
MAC_ITALIC = 0x02


def test_fsselection_vs_macstyle_consistent(ttfont):
    fs = ttfont["OS/2"].fsSelection
    ms = ttfont["head"].macStyle
    assert bool(fs & FS_BOLD) == bool(ms & MAC_BOLD), "Bold bits disagree between OS/2 and head"
    assert bool(fs & FS_ITALIC) == bool(ms & MAC_ITALIC), "Italic bits disagree between OS/2 and head"


def test_use_typo_metrics_set(ttfont):
    """OS/2.fsSelection USE_TYPO_METRICS bit (7) must be set per
    Output_font_requirements.md §1 + config.json os2_flags. Without it,
    Windows GDI and macOS/Linux disagree on line height.
    """
    fs = ttfont["OS/2"].fsSelection
    assert fs & FS_USE_TYPO_METRICS, "USE_TYPO_METRICS bit not set"


def test_win_metrics_dont_clip(ttfont):
    os2 = ttfont["OS/2"]
    hhea = ttfont["hhea"]
    win_total = os2.usWinAscent + os2.usWinDescent
    hhea_total = hhea.ascent + abs(hhea.descent)
    assert win_total >= hhea_total, (
        f"usWinAscent+usWinDescent ({win_total}) < hhea total ({hhea_total}) — "
        "Windows will clip glyphs at the line box"
    )


def test_winascent_accommodates_ruby(ttfont):
    """usWinAscent must cover the ruby band (baseline_y + ruby_em from config).

    Drives off config so the line-height target can be tightened or relaxed
    without rewriting this test — the invariant is that the configured ascent
    leaves room for the ruby top, not a fixed multiple of UPM.
    """
    upm = ttfont["head"].unitsPerEm
    ruby_top_at_1000 = _RUBY_BASELINE + _RUBY_EM
    expected_min = round(ruby_top_at_1000 * upm / 1000 * 0.99)  # 1% tolerance
    actual = ttfont["OS/2"].usWinAscent
    assert actual >= expected_min, (
        f"usWinAscent {actual} < {expected_min} (baseline_y+em scaled to UPM, "
        "× 0.99) — ruby top will be clipped"
    )


def test_typo_metrics_sane(ttfont):
    """Typographic ascender − descender + line gap should fall in a plausible range.

    For ruby fonts the typographic ascender is extended to ~1.4×UPM, so the
    sum can legitimately exceed UPM. We assert only that it is within
    [0.5 × UPM, 2.0 × UPM] — a sanity bound, not a Google Fonts conformance.
    """
    os2 = ttfont["OS/2"]
    upm = ttfont["head"].unitsPerEm
    total = os2.sTypoAscender - os2.sTypoDescender + os2.sTypoLineGap
    assert 0.5 * upm <= total <= 2.0 * upm, f"typo metrics sum {total} outside [0.5, 2.0]×UPM"


def _weight(path):
    tt = TTFont(str(path), lazy=True)
    try:
        return tt["OS/2"].usWeightClass
    finally:
        tt.close()


def _width(path):
    tt = TTFont(str(path), lazy=True)
    try:
        return tt["OS/2"].usWidthClass
    finally:
        tt.close()


def test_weight_class_consistent_sans(sans_ttfs):
    weights = {_weight(p) for p in sans_ttfs}
    assert len(weights) == 1, f"Sans usWeightClass diverges across variants: {weights}"


def test_weight_class_consistent_serif(serif_ttfs):
    weights = {_weight(p) for p in serif_ttfs}
    assert len(weights) == 1, f"Serif usWeightClass diverges across variants: {weights}"


def test_width_class_consistent_sans(sans_ttfs):
    widths = {_width(p) for p in sans_ttfs}
    assert len(widths) == 1, f"Sans usWidthClass diverges: {widths}"


def test_width_class_consistent_serif(serif_ttfs):
    widths = {_width(p) for p in serif_ttfs}
    assert len(widths) == 1, f"Serif usWidthClass diverges: {widths}"
