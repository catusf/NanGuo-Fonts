"""Shared fixtures for the NanGuoFonts test suite.

Lazy-opens TTFonts, derives the GB2312 hanzi set from Python's codec, and
builds a curated heteronym sample via pypinyin (skipped if pypinyin missing).
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterator

import pytest
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Build outputs live in output/ when present; fall back to project root.
TTF_DIR = (ROOT / "output") if (ROOT / "output").is_dir() else ROOT

# Filename forms:
#   Regular: NanGuoSansPinyin-1.ttf .. NanGuoSansPinyin-6.ttf
#   Bold:    NanGuoSansPinyin-1-Bold.ttf .. NanGuoSansPinyin-6-Bold.ttf
_REGULAR_RE = re.compile(r"^NanGuo(?P<fam>Sans|Serif)Pinyin-[1-6]\.ttf$")
_WEIGHT_RE = re.compile(r"^NanGuo(?P<fam>Sans|Serif)Pinyin-[1-6]-(?P<wt>[A-Za-z]+)\.ttf$")


def _exclude(p: pathlib.Path) -> bool:
    """Skip .fixed.ttf and .bak intermediates — only test canonical artifacts."""
    return ".fixed" in p.name or p.name.endswith(".bak")


def _all_ttfs() -> list[pathlib.Path]:
    return sorted(p for p in TTF_DIR.glob("NanGuo*Pinyin-*.ttf") if not _exclude(p))


def _family_ttfs(family: str, weight: str = "Regular") -> list[pathlib.Path]:
    """Return the 6 variants of `family` ('Sans' | 'Serif') at the given weight.

    Weight matching: 'Regular' → bare filenames (NanGuoSansPinyin-1.ttf); any
    other value → '-<weight>' suffix (NanGuoSansPinyin-1-Bold.ttf).
    """
    out: list[pathlib.Path] = []
    for p in TTF_DIR.glob(f"NanGuo{family}Pinyin-*.ttf"):
        if _exclude(p):
            continue
        if weight == "Regular":
            m = _REGULAR_RE.match(p.name)
            if m and m.group("fam") == family:
                out.append(p)
        else:
            m = _WEIGHT_RE.match(p.name)
            if m and m.group("fam") == family and m.group("wt") == weight:
                out.append(p)
    return sorted(out)


@pytest.fixture(scope="session")
def project_root() -> pathlib.Path:
    return ROOT


@pytest.fixture(scope="session")
def all_ttfs() -> list[pathlib.Path]:
    paths = _all_ttfs()
    if not paths:
        pytest.skip("no NanGuo*Pinyin-*.ttf found in project root")
    return paths


@pytest.fixture(scope="session")
def sans_ttfs() -> list[pathlib.Path]:
    paths = _family_ttfs("Sans")
    if len(paths) != 6:
        pytest.skip(f"expected 6 Sans Regular variants, found {len(paths)}")
    return paths


@pytest.fixture(scope="session")
def serif_ttfs() -> list[pathlib.Path]:
    paths = _family_ttfs("Serif")
    if len(paths) != 6:
        pytest.skip(f"expected 6 Serif Regular variants, found {len(paths)}")
    return paths


@pytest.fixture(scope="session")
def sans_bold_ttfs() -> list[pathlib.Path]:
    paths = _family_ttfs("Sans", "Bold")
    if len(paths) != 6:
        pytest.skip(f"expected 6 Sans Bold variants, found {len(paths)}")
    return paths


@pytest.fixture(scope="session")
def serif_bold_ttfs() -> list[pathlib.Path]:
    paths = _family_ttfs("Serif", "Bold")
    if len(paths) != 6:
        pytest.skip(f"expected 6 Serif Bold variants, found {len(paths)}")
    return paths


@pytest.fixture(params=_all_ttfs(), ids=lambda p: p.stem)
def ttf_path(request) -> pathlib.Path:
    return request.param


@pytest.fixture
def ttfont(ttf_path: pathlib.Path) -> Iterator[TTFont]:
    tt = TTFont(str(ttf_path), lazy=True)
    try:
        yield tt
    finally:
        tt.close()


@pytest.fixture(scope="session")
def gb2312_chars() -> set[str]:
    """Derive the 6,763 GB2312 Level-1+2 hanzi from Python's built-in codec."""
    chars: set[str] = set()
    for high in range(0xB0, 0xF8):
        for low in range(0xA1, 0xFF):
            try:
                ch = bytes([high, low]).decode("gb2312")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and 0x4E00 <= ord(ch) <= 0x9FFF:
                chars.add(ch)
    return chars


# A curated allowlist of well-known heteronyms in GB2312.
# Picked for unambiguous multi-reading status across pypinyin versions.
_KNOWN_HETERONYMS = (
    "行长重乐还都为觉朝着便差当得调度恶发分横号会奇切散少省说"
    "宿宁干传降空藏量好和恶应教参看种数中将"
)


@pytest.fixture(scope="session")
def heteronym_sample(gb2312_chars: set[str]) -> list[str]:
    """Chars present in GB2312 that pypinyin confirms have ≥2 readings."""
    pypinyin = pytest.importorskip("pypinyin")
    from pypinyin import Style

    sample: list[str] = []
    for ch in _KNOWN_HETERONYMS:
        if ch not in gb2312_chars:
            continue
        readings = pypinyin.pinyin(ch, heteronym=True, style=Style.NORMAL)
        if readings and len(readings[0]) >= 2 and ch not in sample:
            sample.append(ch)
    if not sample:
        pytest.skip("no usable heteronyms in curated list")
    return sample


def get_name(tt: TTFont, name_id: int, platform_id: int, plat_enc_id: int, lang_id: int) -> str | None:
    rec = tt["name"].getName(name_id, platform_id, plat_enc_id, lang_id)
    return str(rec) if rec is not None else None


def win_name(tt: TTFont, name_id: int) -> str | None:
    return get_name(tt, name_id, 3, 1, 0x409)


def mac_name(tt: TTFont, name_id: int) -> str | None:
    return get_name(tt, name_id, 1, 0, 0)
