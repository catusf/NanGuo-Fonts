#!/usr/bin/env python3
"""generate_hsk_ligatures.py — Generate ligature data from HSK vocabulary.

Reads hsk_words.json and heteronym_map.json to extract multi-character words
where at least one character's reading differs from its primary (variant-1) reading.

The HSK approach has a key advantage: pinyin is already tone-marked in the data,
so no conversion algorithm is needed.

Usage:
    python generate_hsk_ligatures.py \
        --hsk hsk_words.json \
        --heteronym sources/data/heteronym_map.json \
        --output sources/data/hsk-ligatures.json \
        [--min-length 2] \
        [--verbose]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CharacterInfo:
    """Information about a character in an HSK word."""
    char: str
    codepoint: str
    primary_reading: str
    hsk_reading: str


def _char_to_hex_codepoint(char: str) -> str:
    """Convert a character to its Unicode hex codepoint (uppercase).
    
    Examples:
        '爱' -> '4E00'  (actually U+7231 but showing format)
        '得' -> '5F97'
    """
    return f"{ord(char):04X}"


def load_heteronym_map(path: Path) -> dict[str, list[str | None]]:
    """Load heteronym_map.json.
    
    Returns:
        Dict mapping hex codepoint (e.g. '89C9') to array of tone-marked pinyins.
        Position 0 is the primary (variant-1) reading.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def load_hsk_words(path: Path) -> list[dict]:
    """Load hsk_words.json.
    
    Returns:
        List of HSK entry dictionaries with structure:
        {
            "simplified": "爱",
            "traditional": "愛",
            "hsk_level": 1,
            "forms": [
                {
                    "transcriptions": {
                        "pinyin": "ài",      ← Tone-marked (ready to use!)
                        "numeric": "ai4"     ← Alternative format
                    },
                    ...
                }
            ]
        }
    """
    return json.loads(path.read_text(encoding="utf-8"))


def split_pinyin_string(pinyin_str: str) -> list[str] | None:
    """Split space-separated pinyin string into parts.
    
    Examples:
        'ài' -> ['ài']
        'bà ba' -> ['bà', 'ba']
        'bù kè qi' -> ['bù', 'kè', 'qi']
    
    Returns:
        List of pinyin syllables, or None if parsing fails
    """
    if not pinyin_str or not isinstance(pinyin_str, str):
        return None
    
    parts = pinyin_str.strip().split()
    return parts if parts else None


def analyze_hsk_word(
    word: str,
    pinyin_str: str,
    heteronym_map: dict[str, list[str | None]],
) -> list[CharacterInfo] | None:
    """Analyze an HSK word and its pinyin.
    
    Key difference from CCCEDICT: HSK pinyin is already tone-marked,
    so no conversion algorithm is needed!
    
    Returns:
        List of CharacterInfo objects, or None if word should be skipped.
        Skipped if:
        - Single character (no ligature needed)
        - Any character not in heteronym_map
        - Pinyin parsing fails or doesn't match character count
    """
    # Skip single characters
    if len(word) < 2:
        return None
    
    # Parse pinyin
    pinyin_parts = split_pinyin_string(pinyin_str)
    if not pinyin_parts or len(pinyin_parts) != len(word):
        return None
    
    characters_info: list[CharacterInfo] = []
    
    for char, pinyin_tone_marked in zip(word, pinyin_parts):
        codepoint_hex = _char_to_hex_codepoint(char)

        # Look up primary reading
        primary_variants = heteronym_map.get(char)
        if primary_variants is None:
            # Character not in heteronym_map; skip this word
            return None
        
        primary_reading = primary_variants[0]
        if primary_reading is None:
            # No primary reading defined; skip
            return None
        
        # HSK pinyin is already tone-marked - use directly!
        characters_info.append(CharacterInfo(
            char=char,
            codepoint=codepoint_hex,
            primary_reading=primary_reading,
            hsk_reading=pinyin_tone_marked,
        ))
    
    return characters_info


def has_heteronym_context(characters_info: list[CharacterInfo]) -> bool:
    """Check if any character in the word has a reading differing from primary.
    
    Returns True if ligature should be created (contextual != primary for at least one char).
    """
    for char_info in characters_info:
        if char_info.hsk_reading != char_info.primary_reading:
            return True
    return False


def generate_hsk_ligatures(
    hsk_data: list[dict],
    heteronym_map: dict[str, list[str | None]],
    min_length: int = 2,
    verbose: bool = False,
) -> list[dict]:
    """Generate ligature entries from HSK vocabulary.
    
    Args:
        hsk_data: Loaded hsk_words.json
        heteronym_map: Loaded heteronym_map.json
        min_length: Minimum word length to consider
        verbose: Print progress and statistics
    
    Returns:
        List of ligature entry dicts.
    """
    ligatures: list[dict] = []
    skipped_single_char = 0
    skipped_missing_chars = 0
    skipped_no_context_diff = 0
    skipped_pinyin_mismatch = 0
    
    if verbose:
        print(f"Processing {len(hsk_data)} HSK entries...", file=sys.stderr)
    
    for idx, entry in enumerate(hsk_data):
        if verbose and (idx + 1) % 2000 == 0:
            print(f"  {idx + 1}/{len(hsk_data)}", file=sys.stderr)
        
        simplified = entry.get("simplified", "")
        traditional = entry.get("traditional", simplified)
        hsk_level = entry.get("hsk_level", 0)
        
        if not simplified:
            continue
        
        if len(simplified) < min_length:
            skipped_single_char += 1
            continue
        
        # Always use only the first form; later forms are alternate readings
        # that may differ only in tone neutralization or have different context.
        forms = entry.get("forms", [])
        if not forms:
            continue

        transcriptions = forms[0].get("transcriptions", {})
        pinyin_str = transcriptions.get("pinyin")

        if not pinyin_str:
            skipped_pinyin_mismatch += 1
            continue

        # Analyze this word
        characters_info = analyze_hsk_word(simplified, pinyin_str, heteronym_map)
        if characters_info is None:
            skipped_missing_chars += 1
            continue

        # Check if any character has contextual reading different from primary
        if not has_heteronym_context(characters_info):
            skipped_no_context_diff += 1
            continue

        # This word qualifies for ligature
        ligature_entry = {
            "simplified": simplified,
            "hsk_level": hsk_level,
            "primary_reading": " ".join(ci.primary_reading for ci in characters_info),
            "practical_reading": " ".join(ci.hsk_reading for ci in characters_info),
        }
        ligatures.append(ligature_entry)
    
    if verbose:
        print(f"\nResults:", file=sys.stderr)
        print(f"  Found: {len(ligatures)} ligature entries", file=sys.stderr)
        print(f"  Skipped (single char): {skipped_single_char}", file=sys.stderr)
        print(f"  Skipped (missing in heteronym_map): {skipped_missing_chars}", file=sys.stderr)
        print(f"  Skipped (no pinyin): {skipped_pinyin_mismatch}", file=sys.stderr)
        print(f"  Skipped (no context difference): {skipped_no_context_diff}", file=sys.stderr)
    
    return ligatures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate ligature data from HSK vocabulary."
    )
    parser.add_argument(
        "--hsk",
        type=Path,
        required=True,
        help="Path to hsk_words.json",
    )
    parser.add_argument(
        "--heteronym",
        type=Path,
        required=True,
        help="Path to heteronym_map.json (sources/data/heteronym_map.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for hsk-ligatures.json",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=2,
        help="Minimum word length to consider (default: 2)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress and statistics",
    )
    
    args = parser.parse_args()
    
    # Load input files
    if not args.hsk.exists():
        print(f"ERROR: {args.hsk} not found", file=sys.stderr)
        return 1
    if not args.heteronym.exists():
        print(f"ERROR: {args.heteronym} not found", file=sys.stderr)
        return 1
    
    if args.verbose:
        print(f"Loading {args.hsk}...", file=sys.stderr)
    
    hsk_data = load_hsk_words(args.hsk)
    if args.verbose:
        print(f"  Loaded {len(hsk_data)} HSK entries", file=sys.stderr)
    
    if args.verbose:
        print(f"Loading {args.heteronym}...", file=sys.stderr)
    
    heteronym_map = load_heteronym_map(args.heteronym)
    if args.verbose:
        print(f"  Loaded {len(heteronym_map)} characters", file=sys.stderr)
    
    # Generate ligatures
    ligatures = generate_hsk_ligatures(
        hsk_data,
        heteronym_map,
        min_length=args.min_length,
        verbose=args.verbose,
    )
    
    # Save output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_json = json.dumps(ligatures, ensure_ascii=False, indent=2)
    args.output.write_text(output_json, encoding="utf-8")
    
    if args.verbose:
        print(f"Wrote {len(ligatures)} entries to {args.output}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
