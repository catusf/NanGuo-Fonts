"""Bundle the NanGuoPinyin variants of one family into a single .ttc collection.

fontTools' TTCollection.save() shares byte-identical tables across sub-fonts.
Within one weight the 6 variants share glyf/loca/hmtx/post/etc. (only cmap
and name differ). Across weights (Regular vs Bold) the glyf differs, so the
combined collection holds two glyf payloads plus 12 small cmap+name pairs.

Default mode (no arguments) bundles each family's Regular + Bold weights
into a single .ttc per family:
    fonts/Heiti/ttc/NanGuoHeitiPinyin.ttc   (6 Regular + 6 Bold = 12 sub-fonts)
    fonts/Songti/ttc/NanGuoSongtiPinyin.ttc (6 Regular + 6 Bold = 12 sub-fonts)
"""
from __future__ import annotations

import argparse
import pathlib

from fontTools.ttLib import TTCollection, TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (family_name, subfamily_dir, [weight_suffixes])
DEFAULT_FAMILIES: list[tuple[str, str, list[str]]] = [
    ("NanGuoHeitiPinyin",  "Heiti",  ["", "-Bold"]),
    ("NanGuoSongtiPinyin", "Songti", ["", "-Bold"]),
]


def bundle(family: str, ttf_dir: pathlib.Path, suffixes: list[str],
           ttc_dir: pathlib.Path, ttc_name: str | None = None) -> pathlib.Path:
    ttf_paths = [
        ttf_dir / f"{family}-{i}{suffix}.ttf"
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

    ttc_dir.mkdir(parents=True, exist_ok=True)
    stem = ttc_name if ttc_name is not None else family
    ttc_path = ttc_dir / f"{stem}.ttc"
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
        help="Family name prefix, e.g. NanGuoHeitiPinyin. "
             "If omitted, all families in DEFAULT_FAMILIES are bundled.",
    )
    ap.add_argument(
        "--subdir", default=None,
        help="Subfamily directory under fonts/, e.g. Heiti. "
             "Required when --name is used.",
    )
    ap.add_argument(
        "--suffix", default="",
        help="Weight suffix, e.g. -Bold. Only used with --name.",
    )
    args = ap.parse_args()

    if args.name is not None:
        subdir = args.subdir or args.name
        ttf_dir = ROOT / "fonts" / subdir / "ttf"
        ttc_dir = ROOT / "fonts" / subdir / "ttc"
        bundle(args.name, ttf_dir, [args.suffix], ttc_dir)
        return

    print(f"Bundling .ttc collections into fonts/*/ttc/")
    for family, subdir, suffixes in DEFAULT_FAMILIES:
        ttf_dir = ROOT / "fonts" / subdir / "ttf"
        ttc_dir = ROOT / "fonts" / subdir / "ttc"
        bundle(family, ttf_dir, suffixes, ttc_dir)


if __name__ == "__main__":
    main()
