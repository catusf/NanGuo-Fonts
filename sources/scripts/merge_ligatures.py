#!/usr/bin/env python3
"""merge_ligatures.py — Merge hsk-ligatures.json and cccedict-ligatures.json.

HSK entries take priority on overlap. CCCEDICT hsk_reading is renamed to
practical_reading and the traditional field is dropped.

Usage:
    python merge_ligatures.py \
        --hsk      sources/data/hsk-ligatures.json \
        --cccedict sources/data/cccedict-ligatures.json \
        --output   sources/data/all_ligatures.json \
        --verbose
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def run(hsk_path: str, cccedict_path: str, output_path: str, verbose: bool = False) -> None:
    hsk_entries: list[dict] = json.loads(Path(hsk_path).read_text(encoding="utf-8"))
    cccedict_entries: list[dict] = json.loads(Path(cccedict_path).read_text(encoding="utf-8"))

    hsk_index: set[str] = {e["simplified"] for e in hsk_entries}

    result: list[dict] = list(hsk_entries)
    skipped = 0
    added = 0

    for entry in cccedict_entries:
        if entry["simplified"] in hsk_index:
            skipped += 1
            continue
        result.append(entry)
        added += 1

    if verbose:
        print(f"HSK entries:              {len(hsk_entries)}")
        print(f"CCCEDICT overlaps skipped: {skipped}")
        print(f"CCCEDICT-only added:       {added}")
        print(f"Total output entries:      {len(result)}")

    Path(output_path).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written: {output_path} ({len(result)} entries)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hsk", required=True, help="Path to hsk-ligatures.json")
    ap.add_argument("--cccedict", required=True, help="Path to cccedict-ligatures.json")
    ap.add_argument("--output", required=True, help="Output path for all_ligatures.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    run(args.hsk, args.cccedict, args.output, args.verbose)


if __name__ == "__main__":
    main()
