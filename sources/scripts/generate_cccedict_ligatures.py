#!/usr/bin/env python3
"""generate_cccedict_ligatures.py — Generate ligature data from HSK + CCCEDICT.

Reads heteronym_map.json and compares each multi-character word's per-character
readings against the primary (variant-1) reading.  Words where at least one
character uses a non-primary reading are written to cccedict-ligatures.json.

Priority:
  1. hsk_words.json  — curated HSK-3.0 vocabulary with authoritative pinyin
  2. CCCEDICT (pycccedict) — broad coverage for remaining words

Usage:
    python generate_cccedict_ligatures.py \
        --heteronym  sources/data/heteronym_map.json \
        --hsk        hsk_words.json \
        --output     sources/data/cccedict-ligatures.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from pycccedict.cccedict import CcCedict


# ── tone conversion ───────────────────────────────────────────────────────────

_COMBINING_TONE = {
    "̄": "1",  # macron  → 1
    "́": "2",  # acute   → 2
    "̌": "3",  # caron   → 3
    "̀": "4",  # grave   → 4
}

_TONE_MARKS: dict[str, str] = {
    "a": "āáǎàa",
    "e": "ēéěèe",
    "i": "īíǐìi",
    "o": "ōóǒòo",
    "u": "ūúǔùu",
    "ü": "ǖǘǚǜü",  # ü: ǖǘǚǜü
}


def tone_marked_to_numbered(syllable: str) -> str:
    """'dīng' → 'ding1', 'de' → 'de5' (neutral)."""
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


def tone_numbered_to_marked(syllable: str) -> str:
    """'ding1' → 'dīng', 'de5' → 'de', 'lu:3' → 'lǚ'."""
    if not syllable:
        return syllable

    if syllable[-1].isdigit():
        tone = int(syllable[-1])
        base = syllable[:-1]
    else:
        tone = 5
        base = syllable

    # CC-CEDICT uses 'u:' for ü
    base = base.replace("u:", "ü")

    if tone == 5:
        return base

    # Rule 1: 'a' or 'e' always takes the mark
    for v in ("a", "e"):
        if v in base:
            return base.replace(v, _TONE_MARKS[v][tone - 1], 1)

    # Rule 2: 'ou' → 'o' takes the mark
    if "ou" in base:
        return base.replace("o", _TONE_MARKS["o"][tone - 1], 1)

    # Rule 3: last vowel takes the mark
    for i in range(len(base) - 1, -1, -1):
        v = base[i]
        if v in _TONE_MARKS:
            return base[:i] + _TONE_MARKS[v][tone - 1] + base[i + 1:]

    return base


# ── heteronym map ─────────────────────────────────────────────────────────────

def load_primary_readings(path: Path) -> dict[str, str]:
    """Return {char: tone_numbered_primary_reading} from heteronym_map slot 0."""
    data: dict[str, list] = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for ch, variants in data.items():
        primary_marked = variants[0]
        if primary_marked is not None:
            result[ch] = tone_marked_to_numbered(primary_marked)
    return result


# ── word analysis ─────────────────────────────────────────────────────────────

def _cmp_normalize(syl_num: str) -> str:
    """Normalize tone-numbered syllable for comparison.

    Handles CC-CEDICT 'u:' notation and precomposed 'ü' (NFC) by stripping the
    diaeresis via NFD decomposition, so 'lu:3', 'lü3', and 'lu3' all compare equal.
    """
    s = unicodedata.normalize("NFD", syl_num.replace("u:", "u"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s)


_ERHUA_RE = re.compile(r"^r(\d?)$")


def _normalize_erhua(syllables: list[str]) -> list[str]:
    """Convert standalone erhua 'r'/'r5' syllable to 'er'/'er5'."""
    return [_ERHUA_RE.sub(r"er\1", s) for s in syllables]


def analyze_word(
    simplified: str,
    numbered_syllables: list[str],
    primary_readings: dict[str, str],
) -> list[dict] | None:
    """Analyse a word's per-character readings against primary readings.

    Returns a list of character dicts if the word qualifies for a ligature
    (at least one in-map character's reading differs from primary), else None.

    Characters not in heteronym_map are included as-is (differs=False).
    """
    if len(simplified) < 2 or len(simplified) != len(numbered_syllables):
        return None

    chars: list[dict] = []
    any_in_map = False
    any_differs = False

    for ch, syl_num in zip(simplified, numbered_syllables):
        cp = ch
        primary_num = primary_readings.get(cp)

        if primary_num is None:
            chars.append({
                "char": ch,
                "codepoint": cp,
                "primary_reading": None,
                "contextual_reading": tone_numbered_to_marked(syl_num),
                "differs": False,
            })
            continue

        any_in_map = True
        differs = _cmp_normalize(syl_num) != primary_num

        if differs:
            any_differs = True

        chars.append({
            "char": ch,
            "codepoint": cp,
            "primary_reading": tone_numbered_to_marked(primary_num),
            "contextual_reading": tone_numbered_to_marked(syl_num),
            "differs": differs,
        })

    if not any_in_map or not any_differs:
        return None

    return chars


# ── flat-entry builder ────────────────────────────────────────────────────────

def _flatten(chars: list[dict], simplified: str, traditional: str, hsk_level: int) -> dict:
    """Convert a characters list to the flat ligature entry format."""
    primary_parts = [
        c["primary_reading"] if c["primary_reading"] is not None else c["contextual_reading"]
        for c in chars
    ]
    contextual_parts = [c["contextual_reading"] for c in chars]
    return {
        "simplified": simplified,
        "hsk_level": hsk_level,
        "primary_reading": " ".join(primary_parts),
        "practical_reading": " ".join(contextual_parts),
    }


# ── HSK source ────────────────────────────────────────────────────────────────

def load_hsk_words(raw: list[dict], primary_readings: dict[str, str]) -> list[dict]:
    """Return qualifying ligature entries from already-loaded hsk_words data."""
    entries: list[dict] = []

    for item in raw:
        simplified = item.get("simplified", "")
        if len(simplified) < 2:
            continue

        forms = item.get("forms", [])
        if not forms:
            continue

        numeric_str = forms[0].get("transcriptions", {}).get("numeric", "")
        if not numeric_str:
            continue

        traditional = forms[0].get("traditional", simplified)
        hsk_level = item.get("hsk_level", 0)

        numbered = _normalize_erhua([s.lower() for s in numeric_str.strip().split()])
        chars = analyze_word(simplified, numbered, primary_readings)
        if chars is not None:
            entries.append(_flatten(chars, simplified, traditional, hsk_level))

    return entries


# ── CCCEDICT source ───────────────────────────────────────────────────────────

def _is_all_cjk(word: str) -> bool:
    return all("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in word)


def load_cccedict_words(
    primary_readings: dict[str, str],
    seen: set[str],
) -> list[dict]:
    """Load CCCEDICT and return qualifying ligature entries not already in seen."""
    cc = CcCedict()
    entries: list[dict] = []

    for entry in cc.get_entries():
        simplified = entry.get("simplified", "")
        if len(simplified) < 2 or simplified in seen:
            continue

        if not _is_all_cjk(simplified):
            continue

        pinyin_str = entry.get("pinyin", "")
        if not pinyin_str:
            continue

        traditional = entry.get("traditional", simplified)

        numbered = _normalize_erhua([s.lower() for s in pinyin_str.strip().split()])
        chars = analyze_word(simplified, numbered, primary_readings)
        if chars is not None:
            seen.add(simplified)
            entries.append(_flatten(chars, simplified, traditional, 0))

    return entries


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--heteronym", type=Path, required=True,
                    help="Path to heteronym_map.json")
    ap.add_argument("--hsk", type=Path, required=True,
                    help="Path to hsk_words.json")
    ap.add_argument("--output", type=Path, required=True,
                    help="Output path for cccedict-ligatures.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not args.heteronym.exists():
        print(f"ERROR: {args.heteronym} not found", file=sys.stderr)
        return 1
    if not args.hsk.exists():
        print(f"ERROR: {args.hsk} not found", file=sys.stderr)
        return 1

    if args.verbose:
        print("Loading heteronym map...", file=sys.stderr)
    primary_readings = load_primary_readings(args.heteronym)
    if args.verbose:
        print(f"  {len(primary_readings)} characters with primary readings", file=sys.stderr)

    if args.verbose:
        print("Processing HSK words...", file=sys.stderr)
    hsk_data: list[dict] = json.loads(args.hsk.read_text(encoding="utf-8"))
    hsk_entries = load_hsk_words(hsk_data, primary_readings)
    # HSK is authoritative: exclude every HSK word from CEDICT so alternative
    # CEDICT entries (e.g. 结果 jie1 guo3) don't override the correct HSK reading.
    seen: set[str] = {e.get("simplified", "") for e in hsk_data if len(e.get("simplified", "")) >= 2}
    if args.verbose:
        print(f"  {len(hsk_entries)} HSK ligature entries", file=sys.stderr)

    if args.verbose:
        print("Processing CCCEDICT words...", file=sys.stderr)
    cc_entries = load_cccedict_words(primary_readings, seen)
    if args.verbose:
        print(f"  {len(cc_entries)} CCCEDICT ligature entries", file=sys.stderr)

    all_entries = hsk_entries + cc_entries
    if args.verbose:
        print(f"Total: {len(all_entries)} ligature entries", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(all_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(all_entries)} entries to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
