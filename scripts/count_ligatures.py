"""Count GSUB liga ligatures in all NanGuo TTF fonts."""
import argparse
import pathlib
import sys

from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "fonts"

parser = argparse.ArgumentParser()
parser.add_argument("--only-v1", action="store_true", help="Only show variant-1 fonts")
args = parser.parse_args()


def count_liga(font: TTFont) -> int:
    """Return total number of ligature rules in all Type-4 GSUB lookups."""
    gsub = font.get("GSUB")
    if gsub is None:
        return 0
    table = gsub.table
    liga_lookup_indices: set[int] = set()
    for fr in table.FeatureList.FeatureRecord:
        if fr.FeatureTag == "liga":
            liga_lookup_indices.update(fr.Feature.LookupListIndex)

    total = 0
    for idx in liga_lookup_indices:
        lk = table.LookupList.Lookup[idx]
        # Type 4 = LigatureSubst; Type 7 = Extension (may wrap Type 4)
        subtables = []
        if lk.LookupType == 4:
            subtables = lk.SubTable
        elif lk.LookupType == 7:
            for st in lk.SubTable:
                st.ensureDecompiled()
                inner = st.ExtSubTable
                inner.ensureDecompiled()
                if inner.LookupType == 4:
                    subtables.append(inner)
        for st in subtables:
            st.ensureDecompiled()
            for lig_set in st.ligatures.values():
                total += len(lig_set)
    return total


glob = "*/ttf/NanGuo*Pinyin-1*.ttf" if args.only_v1 else "*/ttf/NanGuo*.ttf"
ttf_paths = sorted(FONTS_DIR.glob(glob))
if not ttf_paths:
    print("No TTF fonts found under fonts/*/ttf/")
    sys.exit(1)

family_totals: dict[str, int] = {}
print(f"{'Font':<45} {'Ligatures':>10}")
print("-" * 57)
for path in ttf_paths:
    with TTFont(str(path), lazy=True) as font:
        n = count_liga(font)
    family = path.parts[-3]  # e.g. Heiti or Songti
    family_totals[family] = family_totals.get(family, 0) + n
    print(f"{path.name:<45} {n:>10,}")

print("-" * 57)
for family, total in sorted(family_totals.items()):
    print(f"{'Total ' + family:<45} {total:>10,}")
print(f"{'Grand total':<45} {sum(family_totals.values()):>10,}")
