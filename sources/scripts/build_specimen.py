#!/usr/bin/env python3
"""Build documentation/NanGuo_Specimen-Heiti.png and documentation/NanGuo_Specimen-Songti.png.

Each image is 1200×400 px:  large Chinese text (with embedded pinyin) in the
NanGuo font, a subtitle line, and a coloured bottom bar.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONTS_DIR = ROOT / "fonts"
DOC_DIR = ROOT / "documentation"

W, H = 1200, 400
BG = (255, 255, 255)
BAR_H = 14
MARGIN_X = 60
MARGIN_Y = 28
CHINESE_SIZE = 100
SUBTITLE_SIZE = 22

CHINESE_TEXT = "学习汉字很有趣"

SPECS = [
    {
        "style": "Heiti",
        "display": "NanGuo Heiti Pinyin",
        "ttf": FONTS_DIR / "Heiti" / "ttf" / "NanGuoHeitiPinyin-1.ttf",
        "bar": (70, 120, 180),
        "out": "NanGuo_Specimen-Heiti.png",
    },
    {
        "style": "Songti",
        "display": "NanGuo Songti Pinyin",
        "ttf": FONTS_DIR / "Songti" / "ttf" / "NanGuoSongtiPinyin-1.ttf",
        "bar": (180, 100, 50),
        "out": "NanGuo_Specimen-Songti.png",
    },
]


def build_Specimen(spec: dict) -> pathlib.Path:
    zh_font = ImageFont.truetype(str(spec["ttf"]), size=CHINESE_SIZE)
    sub_font = ImageFont.truetype(str(spec["ttf"]), size=SUBTITLE_SIZE)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Chinese text — NanGuo glyphs include embedded pinyin above each character
    zh_bbox = draw.textbbox((0, 0), CHINESE_TEXT, font=zh_font)
    zh_h = zh_bbox[3] - zh_bbox[1]
    draw.text((MARGIN_X, MARGIN_Y), CHINESE_TEXT, font=zh_font, fill=(20, 20, 20))

    # Subtitle
    subtitle = f"{spec['display']}  ·  Regular & Bold  ·  6 Pinyin Variants"
    sub_y = MARGIN_Y + zh_h + 18
    draw.text((MARGIN_X, sub_y), subtitle, font=sub_font, fill=(110, 110, 110))

    # Bottom bar
    draw.rectangle([0, H - BAR_H, W, H], fill=spec["bar"])

    out = DOC_DIR / spec["out"]
    img.save(str(out), optimize=True)
    return out


def main() -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        print(f"Building documentation/{spec['out']} ...", end=" ", flush=True)
        out = build_Specimen(spec)
        print(f"{out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
