"""Composite ruby must not extend beyond the CJK cell horizontally.

Long syllables like zhuāng/chuáng/shuāng would otherwise overlap the ruby
of adjacent characters. Controlled by config.json
ruby_geometry_at_upm_1000.max_overflow_factor (1.0 = no overflow).
"""

from __future__ import annotations

import json
import pathlib

import pytest
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Syllables known to be the widest in the inventory — if these fit, the
# rest of the catalogue fits.
WIDE_SYLLABLES = [
    "zhuāng", "zhuǎng", "zhuàng",
    "zhāng", "zhǎng", "zhàng",
    "chuāng", "chuáng", "chuǎng", "chuàng",
    "shuāng", "shuǎng", "shuàng",
    "qiāng", "qiáng", "qiǎng", "qiàng",
    "xiāng", "xiáng", "xiǎng", "xiàng",
]


@pytest.fixture(scope="module")
def syllable_inventory() -> dict:
    return json.loads((ROOT / "sources" / "data" / "syllable_inventory.json").read_text(encoding="utf-8"))


def _check_overflow(ttf_path, syllable_inventory, tolerance: int = 5):
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        glyf = tt["glyf"]
        cjk_adv = tt["hmtx"].metrics[tt.getBestCmap()[0x4E00]][0]
        offenders = []
        for syl in WIDE_SYLLABLES:
            meta = syllable_inventory.get(syl)
            if meta is None:
                continue
            gn = f"uni{meta['pua']}"
            try:
                g = glyf[gn]
            except KeyError:
                continue
            g.recalcBounds(glyf)
            if g.xMin < -tolerance or g.xMax > cjk_adv + tolerance:
                offenders.append(
                    f"{syl} (uni{meta['pua']}): xMin={g.xMin} xMax={g.xMax} cjk_adv={cjk_adv}"
                )
        assert not offenders, (
            "Ruby glyphs extend beyond the CJK cell — neighbor pinyin will overlap:\n  "
            + "\n  ".join(offenders)
        )
    finally:
        tt.close()


def test_sans_v1_wide_syllables_fit_in_cell(sans_ttfs, syllable_inventory):
    _check_overflow(sans_ttfs[0], syllable_inventory)


def test_serif_v1_wide_syllables_fit_in_cell(serif_ttfs, syllable_inventory):
    _check_overflow(serif_ttfs[0], syllable_inventory)
