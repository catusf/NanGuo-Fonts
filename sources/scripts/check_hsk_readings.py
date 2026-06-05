"""Compare HSK 3.0 word readings against variant-1 primary readings.

Parses the Pinyin column of hsk30.csv and compares each character's
contextual reading against slot 0 of heteronym_map.json (variant-1 default).
Reports all cases where the HSK reading differs from the font's primary reading.

Usage:
    python sources/scripts/check_hsk_readings.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "sources" / "data"

# ── syllable inventory (from pypinyin) ───────────────────────────────────────

def _build_syllable_set() -> set[str]:
    from pypinyin.core import PINYIN_DICT  # type: ignore[import]

    def _strip(s: str) -> str:
        nfd = unicodedata.normalize("NFD", s)
        return "".join(c for c in nfd if unicodedata.category(c) != "Mn")

    syls: set[str] = set()
    for v in PINYIN_DICT.values():
        for s in v.split(","):
            syls.add(_strip(s.strip()))
    return syls


_SYLLABLES: set[str] = _build_syllable_set()

# ── tone conversion ───────────────────────────────────────────────────────────

_COMBINING_TONE = {
    "̄": "1",  # macron  → 1
    "́": "2",  # acute   → 2
    "̌": "3",  # caron   → 3
    "̀": "4",  # grave   → 4
}


def tone_marked_to_numbered(syllable: str) -> str:
    """ài → ai4, māo → mao1, zi (no mark) → zi5 (neutral)."""
    nfd = unicodedata.normalize("NFD", syllable.lower())
    tone = "5"
    base: list[str] = []
    for ch in nfd:
        if unicodedata.category(ch) == "Mn":
            t = _COMBINING_TONE.get(ch)
            if t:
                tone = t
        else:
            base.append(ch)
    return unicodedata.normalize("NFC", "".join(base)) + tone


# ── pinyin syllable splitter ──────────────────────────────────────────────────

def _split_base(base_str: str, n: int) -> list[str] | None:
    """DP: split no-tone base pinyin string into exactly n valid syllables."""
    memo: dict[tuple[int, int], list[list[str]] | None] = {}

    def go(pos: int, remaining: int) -> list[list[str]] | None:
        if remaining == 0:
            return [[]] if pos == len(base_str) else None
        if pos >= len(base_str):
            return None
        key = (pos, remaining)
        if key in memo:
            return memo[key]
        result = None
        for length in range(len(base_str) - pos, 0, -1):  # longest match first
            candidate = base_str[pos : pos + length]
            if candidate in _SYLLABLES:
                rest = go(pos + length, remaining - 1)
                if rest is not None:
                    result = [[candidate] + r for r in rest]
                    break
        memo[key] = result
        return result

    solutions = go(0, n)
    return solutions[0] if solutions else None


def split_pinyin(pinyin_str: str, n: int) -> list[str] | None:
    """Split a tone-marked pinyin string into exactly n syllables.

    Returns None if clean splitting into n parts is not possible.
    """
    # Remove apostrophes and spaces; lowercase
    s = re.sub(r"['\s]", "", pinyin_str.strip().lower())
    if not s:
        return None

    # Separate base characters from combining tone marks
    nfd = unicodedata.normalize("NFD", s)
    base_chars: list[str] = []
    tone_at: dict[int, str] = {}
    for ch in nfd:
        if unicodedata.category(ch) == "Mn":
            if base_chars:
                tone_at[len(base_chars) - 1] = tone_at.get(len(base_chars) - 1, "") + ch
        else:
            base_chars.append(ch)
    base_str = "".join(base_chars)

    base_syls = _split_base(base_str, n)
    if base_syls is None:
        return None

    # Re-attach tone marks to their original vowel positions
    result: list[str] = []
    pos = 0
    for syl in base_syls:
        syl_chars: list[str] = []
        for i, ch in enumerate(syl):
            combined = ch + tone_at.get(pos + i, "")
            syl_chars.append(unicodedata.normalize("NFC", combined))
        result.append("".join(syl_chars))
        pos += len(syl)
    return result


# ── load reference data ───────────────────────────────────────────────────────

def load_v1_map() -> dict[int, str]:
    """Return {codepoint: tone_numbered_primary_reading} from heteronym_map slot 0."""
    raw = json.loads((DATA / "heteronym_map.json").read_text(encoding="utf-8"))
    return {
        ord(k): tone_marked_to_numbered(v[0])
        for k, v in raw.items()
        if v[0]
    }


# ── parse HSK CSV ─────────────────────────────────────────────────────────────

_SKIP_RE = re.compile(r"[（(1-9|]")


def parse_hsk(path: pathlib.Path) -> tuple[list[tuple[str, list[str]]], int]:
    """Return ([(word, [tone_numbered_syllable, ...])], skipped_count)."""
    results: list[tuple[str, list[str]]] = []
    skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            simp = row["Simplified"].split("|")[0]
            csv_pinyin = row["Pinyin"].split("|")[0]
            if _SKIP_RE.search(simp) or _SKIP_RE.search(csv_pinyin):
                continue
            if len(simp) < 2:
                continue
            syllables = split_pinyin(csv_pinyin, len(simp))
            if syllables is None:
                skipped += 1
                continue
            numbered = [tone_marked_to_numbered(s) for s in syllables]
            results.append((simp, numbered))
    return results, skipped


# ── compare ───────────────────────────────────────────────────────────────────

def find_mismatches(
    hsk_words: list[tuple[str, list[str]]],
    v1_map: dict[int, str],
) -> list[dict]:
    mismatches: list[dict] = []
    for word, syllables in hsk_words:
        for i, (char, syl) in enumerate(zip(word, syllables)):
            cp = ord(char)
            if cp not in v1_map:
                continue
            v1_reading = v1_map[cp]
            if syl != v1_reading:
                mismatches.append(
                    {
                        "char": char,
                        "cp": cp,
                        "word": word,
                        "position": i,
                        "hsk_reading": syl,
                        "v1_reading": v1_reading,
                    }
                )
    mismatches.sort(key=lambda r: (r["cp"], r["word"]))
    return mismatches


# ── report ────────────────────────────────────────────────────────────────────

def main() -> None:
    v1_map = load_v1_map()
    hsk_words, skipped = parse_hsk(DATA / "hsk30.csv")

    print(f"HSK 3.0 multi-char words parsed : {len(hsk_words)}  (skipped {skipped})")

    mismatches = find_mismatches(hsk_words, v1_map)
    print(f"Mismatches found                : {len(mismatches)}")

    by_char: dict[str, list[dict]] = {}
    for m in mismatches:
        by_char.setdefault(m["char"], []).append(m)

    print(f"Characters with mismatches      : {len(by_char)}")
    print("=" * 64)

    for char, records in sorted(by_char.items(), key=lambda kv: ord(kv[0])):
        v1 = records[0]["v1_reading"]
        hsk_readings = sorted({r["hsk_reading"] for r in records})
        print(
            f"\n{char}  U+{ord(char):04X}  variant-1={v1!r}  "
            f"HSK readings={hsk_readings}"
        )
        for r in records:
            print(f"  [{r['position']}] {r['word']}  HSK={r['hsk_reading']!r}")


if __name__ == "__main__":
    main()
