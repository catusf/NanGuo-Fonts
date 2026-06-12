#!/usr/bin/env python3
"""make_ligatures_md.py — Generate ligatures_list.md from all_ligatures.json.

Usage:
    python make_ligatures_md.py [--input sources/data/all_ligatures.json] \
                                [--output sources/data/ligatures_list.md] \
                                [--cols 4]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

COLS = 4

CHAR_HEADER = "汉字/Chinese/Chữ Hán"
READING_HEADER = "标准=>实用读音 / Primary=>Practical Reading / Phiên âm chuẩn=>Thực tế"


def build_table(entries: list[dict], cols: int) -> list[str]:
    # Header row: COLS pairs of (char, reading) columns
    header_cells = [f" {CHAR_HEADER} | {READING_HEADER} "] * cols
    header_row = "|" + "|".join(header_cells) + "|"

    sep_cells = [" --- | --- "] * cols
    sep_row = "|" + "|".join(sep_cells) + "|"

    rows = [header_row, sep_row]

    for i in range(0, len(entries), cols):
        chunk = entries[i : i + cols]
        cells = []
        for e in chunk:
            char = e["simplified"]
            primary = e["primary_reading"]
            practical = e["practical_reading"]
            cells.append(f" {char} | {primary} → {practical} ")
        # Pad last row to full width
        while len(cells) < cols:
            cells.append("  |  ")
        rows.append("|" + "|".join(cells) + "|")

    return rows


def run(input_path: Path, output_path: Path, cols: int) -> None:
    entries: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))

    table_lines = build_table(entries, cols)

    lines = [
        "# Danh sách từ ghép/List of ligatures",
        "",
        f"Số lượng/Number: {len(entries)}",
        "",
        *table_lines,
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {output_path} ({len(entries)} entries)")


_HERE = Path(__file__).resolve().parent
_DATA = _HERE.parent / "data"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=_DATA / "all_ligatures.json",
                    help="Path to all_ligatures.json")
    ap.add_argument("--output", type=Path, default=_DATA / "ligatures_list.md",
                    help="Output path for ligatures_list.md")
    ap.add_argument("--cols", type=int, default=COLS, help="Entries per row (default: 4)")
    args = ap.parse_args()
    run(args.input, args.output, args.cols)


if __name__ == "__main__":
    main()
