"""OS/2.achVendID must match config.json → vendor.ach_vend_id.

Per Output_font_requirements.md §1: a 4-char vendor tag. The build script
should write this from config, not inherit silently from the Noto source.
"""

from __future__ import annotations

import json
import pathlib


def test_vendor_id_matches_config(ttfont):
    cfg_path = pathlib.Path(__file__).resolve().parent.parent / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    expected = cfg["vendor"]["ach_vend_id"]
    actual = ttfont["OS/2"].achVendID
    if isinstance(actual, bytes):
        actual = actual.decode("ascii", errors="replace")
    assert actual.strip("\x00 ") == expected, (
        f"OS/2.achVendID={actual!r} != expected {expected!r}"
    )
