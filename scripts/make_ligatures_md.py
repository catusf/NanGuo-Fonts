#!/usr/bin/env python3
"""Generate a markdown table of ligatures from sources/data/all_ligatures.json."""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
INPUT = ROOT / "sources" / "data" / "all_ligatures.json"
OUTPUT = ROOT / "sources" / "data" / "ligatures_list.md"

COLS_PER_ROW = 4  # 4 words × 3 columns = 12 columns total

data = json.loads(INPUT.read_text(encoding="utf-8"))

lines = [
    "# Danh sách từ ghép/List of ligatures",
    "",
    f"Số lượng/Number: {len(data)}",
    "",
]

# Build header: 4 groups of (Chinese | Primary | Practical)
header_cells = ["Chinese", "Primary", "Practical"] * COLS_PER_ROW
separator_cells = ["---"] * (COLS_PER_ROW * 3)
lines.append("| " + " | ".join(header_cells) + " |")
lines.append("| " + " | ".join(separator_cells) + " |")

for i in range(0, len(data), COLS_PER_ROW):
    chunk = data[i : i + COLS_PER_ROW]
    cells = []
    for entry in chunk:
        cells += [entry["simplified"], entry["primary_reading"], entry["practical_reading"]]
    # Pad to full row width if last row is short
    while len(cells) < COLS_PER_ROW * 3:
        cells += ["", "", ""]
    lines.append("| " + " | ".join(cells) + " |")

OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Written {len(data)} entries to {OUTPUT}")
