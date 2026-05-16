"""Bundle the NanGuoPinyin variants of one family into a single .ttc collection.

fontTools' TTCollection.save() shares byte-identical tables across sub-fonts.
Within one weight the 6 variants share glyf/loca/hmtx/post/etc. (only cmap
and name differ). Across weights (Regular vs Bold) the glyf differs, so the
combined collection holds two glyf payloads plus 12 small cmap+name pairs.

Default mode (no arguments) bundles each family's Regular + Bold weights
into a single .ttc per family:
    NanGuoSansPinyin.ttc       (6 Regular + 6 Bold = 12 sub-fonts)
    NanGuoSerifPinyin.ttc      (6 Regular + 6 Bold = 12 sub-fonts)

To bundle a single weight on its own, pass --name (and optionally --suffix):
    python scripts/bundle_ttc.py --name NanGuoSerifPinyin --suffix -Bold
"""
from __future__ import annotations

import argparse
import pathlib

from fontTools.ttLib import TTCollection, TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Each entry is (family_name, [weight_suffixes_in_order]).
DEFAULT_FAMILIES: list[tuple[str, list[str]]] = [
    ("NanGuoHeitiPinyin", ["", "-Bold"]),
    ("NanGuoSongtiPinyin", ["", "-Bold"]),
]


def bundle(family: str, suffixes: list[str], out_dir: pathlib.Path,
           ttc_name: str | None = None) -> pathlib.Path:
    """Bundle 6 variants per weight (across `suffixes`) into one .ttc.

    The output is `{family}{first-suffix}.ttc` by default; pass `ttc_name`
    to override (without the .ttc extension).
    """
    ttf_paths = [
        out_dir / f"{family}-{i}{suffix}.ttf"
        for suffix in suffixes
        for i in range(1, 7)
    ]
    missing = [p for p in ttf_paths if not p.exists()]
    if missing:
        raise SystemExit(
            f"missing inputs: {', '.join(p.name for p in missing)}"
        )

    fonts = [TTFont(str(p)) for p in ttf_paths]
    ttc = TTCollection()
    ttc.fonts = fonts

    stem = ttc_name if ttc_name is not None else f"{family}{suffixes[0]}"
    ttc_path = out_dir / f"{stem}.ttc"
    ttc.save(str(ttc_path))

    total_ttf = sum(p.stat().st_size for p in ttf_paths)
    ttc_size = ttc_path.stat().st_size
    print(
        f"  {ttc_path.name:30s}  {ttc_size/1e6:6.2f} MB  "
        f"({len(fonts)} sub-fonts, sum {total_ttf/1e6:.2f} MB, "
        f"{(1 - ttc_size/total_ttf)*100:.1f}% smaller)"
    )
    return ttc_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--name", default=None,
        help="PostScript prefix matching the -1..-6 TTF stems. "
             "If omitted, every family in DEFAULT_FAMILIES is bundled with "
             "all its weights combined into one .ttc per family.",
    )
    ap.add_argument(
        "--suffix", default="",
        help="Suffix after the variant number, e.g. '-Bold' "
             "for files named NanGuoSansPinyin-1-Bold.ttf. "
             "Only used with --name (single-weight bundle).",
    )
    ap.add_argument(
        "--out", default=str(ROOT / "output"),
        help="Directory holding the input TTFs and receiving the .ttc",
    )
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out)
    print(f"Bundling .ttc collections in {out_dir}/")

    if args.name is not None:
        bundle(args.name, [args.suffix], out_dir)
        return

    for family, suffixes in DEFAULT_FAMILIES:
        bundle(family, suffixes, out_dir, ttc_name=family)


if __name__ == "__main__":
    main()
