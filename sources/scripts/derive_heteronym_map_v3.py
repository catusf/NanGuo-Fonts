#!/usr/bin/env python3
"""derive_heteronym_map_v3.py — Build heteronym_map_new.json from open data sources.

Reads (in priority order):
  1. data/hsk_words.json          — single-char entries (primary), multi-char (contextual)
  2. data/kHanyuPinlu.txt         — additional single-char readings
  3. pycccedict                   — broad fallback (~99.4% coverage)
  4. data/heteronym_map.json      — character set + last-resort for 40 uncovered chars

Writes (new files, existing files untouched):
  data/heteronym_map_new.json       — same 6764 char keys, values rebuilt from above
  data/syllable_inventory_new.json  — fresh syllable→PUA mapping (no seed from old file)

Neutral-tone rule:
  A neutral/light-tone reading (tone 5, no diacritic) goes into slot[5] (V6)
  if and only if it is NOT the primary reading (slot[0]).
  Toned alternates fill slots[1]–[4] (V2–V5) in collected order.
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from pycccedict.cccedict import CcCedict

SCRIPT_DIR = Path(__file__).resolve().parent
DATA = SCRIPT_DIR.parent / "data"

# ── tone conversion (copied from generate_cccedict_ligatures.py) ──────────────

_COMBINING_TONE = {
    "̄": "1",  # macron
    "́": "2",  # acute
    "̌": "3",  # caron
    "̀": "4",  # grave
}

_TONE_MARKS: dict[str, str] = {
    "a": "āáǎàa",
    "e": "ēéěèe",
    "i": "īíǐìi",
    "o": "ōóǒòo",
    "u": "ūúǔùu",
    "ü": "ǖǘǚǜü",
}


def tone_numbered_to_marked(syllable: str) -> str:
    """'ding1' → 'dīng', 'de5' → 'de', 'lu:3' → 'lǚ'."""
    if not syllable:
        return syllable
    syllable = syllable.lower()
    if syllable[-1].isdigit():
        tone = int(syllable[-1])
        base = syllable[:-1]
    else:
        tone = 5
        base = syllable
    base = base.replace("u:", "ü")
    if tone == 5:
        return base
    for v in ("a", "e"):
        if v in base:
            return base.replace(v, _TONE_MARKS[v][tone - 1], 1)
    if "ou" in base:
        return base.replace("o", _TONE_MARKS["o"][tone - 1], 1)
    for i in range(len(base) - 1, -1, -1):
        v = base[i]
        if v in _TONE_MARKS:
            return base[:i] + _TONE_MARKS[v][tone - 1] + base[i + 1:]
    return base


def is_neutral(syllable: str) -> bool:
    """Return True if syllable carries no tone diacritic (tone 5 / light tone)."""
    nfd = unicodedata.normalize("NFD", syllable)
    return not any(unicodedata.category(c) == "Mn" and c in _COMBINING_TONE for c in nfd)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ── source loaders ────────────────────────────────────────────────────────────

def load_hsk(path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return (single_char_readings, multi_char_readings) dicts.

    single_char_readings[ch] = ordered list of tone-marked readings from HSK forms.
    multi_char_readings[ch]  = set of contextual readings from multi-char HSK words.
    """
    words = json.loads(path.read_text(encoding="utf-8"))
    single: dict[str, list[str]] = {}
    multi: dict[str, set[str]] = defaultdict(set)

    for word in words:
        simplified = word["simplified"]
        forms = word.get("forms", [])

        if len(simplified) == 1:
            readings: list[str] = []
            seen: set[str] = set()
            for form in forms:
                r = nfc(form["transcriptions"]["pinyin"].strip())
                if r and r not in seen:
                    seen.add(r)
                    readings.append(r)
            if readings and simplified not in single:
                single[simplified] = readings
        else:
            # Extract per-character readings from multi-char words
            for form in forms:
                pinyin_str = form["transcriptions"]["pinyin"]
                parts = pinyin_str.split()
                if len(parts) == len(simplified):
                    for ch, syl in zip(simplified, parts):
                        multi[ch].add(nfc(syl.strip()))

    return single, {ch: list(v) for ch, v in multi.items()}


def load_pinlu(path: Path) -> dict[str, list[str]]:
    """Parse kHanyuPinlu.txt → {uppercase_hex: [tone-marked readings]}."""
    result: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cp_part, rest = line.split(":", 1)
            cp = cp_part.strip().replace("U+", "").upper()
            readings = [nfc(r.strip()) for r in rest.split("#")[0].split(",") if r.strip()]
            if readings:
                result[cp] = readings
    return result


def load_cccedict() -> dict[str, list[str]]:
    """Build {simplified_char: [tone-marked readings]} from CC-CEDICT single-char entries."""
    d = CcCedict()
    index: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for entry in d.get_entries():
        ch = entry.get("simplified", "")
        if len(ch) != 1:
            continue
        raw = entry.get("pinyin", "")
        marked = nfc(tone_numbered_to_marked(raw))
        if marked and marked not in seen[ch]:
            seen[ch].add(marked)
            index[ch].append(marked)
    return dict(index)


# ── slot assignment ───────────────────────────────────────────────────────────

def build_slots(readings: list[str]) -> list[str | None]:
    """Assign readings to 6 variant slots following the neutral-tone rule.

    - slot[0]: primary (V1) — first reading regardless of tone
    - slots[1]–[4]: toned alternates in collected order (excluding primary)
    - slot[5]: first neutral reading, only if it differs from primary
    """
    if not readings:
        return [None] * 6

    primary = readings[0]
    toned_alts = [r for r in readings[1:] if not is_neutral(r)]
    neutral_alts = [r for r in readings[1:] if is_neutral(r)]

    slots: list[str | None] = [None] * 6
    slots[0] = primary

    for i, r in enumerate(toned_alts[:4]):
        slots[1 + i] = r

    if neutral_alts:
        slots[5] = neutral_alts[0]

    return slots


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading sources...")
    hsk_single, hsk_multi = load_hsk(DATA / "hsk_words.json")
    print(f"  HSK: {len(hsk_single)} single-char, {len(hsk_multi)} chars with multi-char readings")

    pinlu = load_pinlu(DATA / "kHanyuPinlu.txt")
    print(f"  kHanyuPinlu: {len(pinlu)} entries")

    print("  Loading CC-CEDICT (this may take a moment)...")
    cc = load_cccedict()
    print(f"  CC-CEDICT: {len(cc)} unique single chars")

    old_het: dict[str, list] = json.loads((DATA / "heteronym_map.json").read_text(encoding="utf-8"))
    print(f"  Existing heteronym_map: {len(old_het)} chars (for character set + fallback)")

    print("Building new heteronym_map...")
    new_het: dict[str, list[str | None]] = {}
    stats = {"hsk": 0, "pinlu": 0, "cc": 0, "fallback": 0, "multi_only": 0}
    neutral_in_v6 = 0

    for ch in old_het:
        pinlu_key = f"{ord(ch):04X}"
        readings: list[str] = []
        seen: set[str] = set()

        def add(r: str) -> None:
            r = nfc(r)
            if r and r not in seen:
                seen.add(r)
                readings.append(r)

        in_pinlu = bool(pinlu.get(pinlu_key))
        in_hsk = ch in hsk_single

        if in_pinlu:
            # kHanyuPinlu is frequency-ordered → determines V1
            for r in pinlu[pinlu_key]:
                add(r)
            # HSK single-char readings as additional variants
            for r in hsk_single.get(ch, []):
                add(r)
        elif in_hsk:
            # No kHanyuPinlu entry: use HSK ordering
            for r in hsk_single[ch]:
                add(r)

        # HSK multi-char contextual readings (additional variants)
        for r in hsk_multi.get(ch, []):
            add(r)

        # CC-CEDICT: fills chars not in kHanyuPinlu or HSK, adds extras
        for r in cc.get(ch, []):
            add(r)

        # Determine primary source for stats
        if in_pinlu:
            stats["pinlu"] += 1
        elif in_hsk:
            stats["hsk"] += 1
        elif cc.get(ch):
            stats["cc"] += 1
        else:
            stats["fallback"] += 1

        if not readings:
            # Last resort: keep V1 from existing map
            v1 = old_het[ch][0]
            if v1:
                add(v1)

        slots = build_slots(readings)
        new_het[ch] = slots

        if slots[5] is not None and is_neutral(slots[5]):
            neutral_in_v6 += 1

    print(f"  Source breakdown: HSK={stats['hsk']}, kHanyuPinlu={stats['pinlu']}, "
          f"CC-CEDICT={stats['cc']}, fallback={stats['fallback']}, multi-only={stats['multi_only']}")
    multi_reading = sum(1 for v in new_het.values() if any(x for x in v[1:] if x))
    print(f"  Total chars: {len(new_het)}, with multiple readings: {multi_reading}")
    print(f"  Neutral readings in V6 slot: {neutral_in_v6}")

    # Build fresh syllable inventory
    print("Building fresh syllable_inventory_new.json...")
    all_syllables: set[str] = set()
    for slots in new_het.values():
        for s in slots:
            if s:
                all_syllables.add(s)

    inv: dict[str, dict] = {}
    for i, syl in enumerate(sorted(all_syllables)):
        pua_cp = 0xE000 + i
        inv[syl] = {"pua": f"{pua_cp:04X}"}

    print(f"  Unique syllables: {len(inv)}, PUA range: E000–{0xE000 + len(inv) - 1:04X}")

    out_het = DATA / "heteronym_map_new.json"
    out_inv = DATA / "syllable_inventory_new.json"
    out_het.write_text(json.dumps(new_het, ensure_ascii=False, indent=2), encoding="utf-8")
    out_inv.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written: {out_het}")
    print(f"Written: {out_inv}")


if __name__ == "__main__":
    main()
