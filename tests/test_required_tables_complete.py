"""All 20 spec-required tables must be present (and no CFF outlines).

Per Output_font_requirements.md §2: the output MUST contain BASE, GDEF,
GPOS, GSUB, STAT, cmap, gasp, glyf, hhea, head, hmtx, loca, maxp, name,
OS/2, post, prep, vhea, vmtx. `CFF`/`CFF2` MUST NOT be present.

`prep` is conditionally tolerated as missing — Noto SC ships without it.
The other 19 are hard requirements.
"""

from __future__ import annotations

HARD_REQUIRED = {
    "BASE", "GDEF", "GPOS", "GSUB", "STAT", "cmap", "gasp", "glyf",
    "hhea", "head", "hmtx", "loca", "maxp", "name", "OS/2", "post",
    "vhea", "vmtx",
}
OPTIONAL = {"prep"}
FORBIDDEN = {"CFF ", "CFF2"}


def test_hard_required_tables_present(ttfont):
    missing = HARD_REQUIRED - set(ttfont.keys())
    assert not missing, f"missing required tables: {sorted(missing)}"


def test_no_cff_outlines(ttfont):
    present = FORBIDDEN & set(ttfont.keys())
    assert not present, (
        f"output must be TrueType-only (glyf), found: {sorted(present)}"
    )
