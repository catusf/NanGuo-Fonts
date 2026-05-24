"""render_ligature_confirm.py — Render 10 ligature pairs to a PNG grid.

For each word, shows side-by-side:
  LEFT  — individual characters (liga OFF) → variant-1 default reading
  RIGHT — ligature-shaped (liga ON)        → corrected contextual reading

Usage:
    python sources/scripts/render_ligature_confirm.py
    python sources/scripts/render_ligature_confirm.py --out my_check.png
    python sources/scripts/render_ligature_confirm.py --font fonts/Songti/ttf/NanGuoSongtiPinyin-1.ttf
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uharfbuzz as hb
import freetype
from PIL import Image, ImageDraw, ImageFont as PILFont

ROOT = Path(__file__).resolve().parent.parent.parent

# ── Words to demonstrate ───────────────────────────────────────────────────────
# (word, correction_label)
DEMOS = [
    ("了解",   "了: le → liǎo"),
    ("觉得",   "觉: jiào → jué"),
    ("高兴",   "兴: xīng → xìng"),
    ("银行",   "行: xíng → háng"),
    ("重新",   "重: zhòng → chóng"),
    ("差别",   "差: chà → chā"),
    ("认为",   "为: wèi → wéi"),
    ("长期",   "长: zhǎng → cháng"),
    ("出差",   "差: chà → chāi"),
    ("便宜",   "便: biàn → pián"),
]

# ── Layout constants ───────────────────────────────────────────────────────────
PT_SIZE   = 40        # CJK body size in points
DPI       = 96
PAD       = 20        # padding around each cell
ROW_GAP   = 12       # vertical gap between rows
ARROW     = "  →  "
BG        = (255, 255, 255)
FG        = (20, 20, 20)
LABEL_COL = (80, 80, 160)


# ── Renderer ───────────────────────────────────────────────────────────────────

class GlyphRenderer:
    def __init__(self, font_path: str) -> None:
        self.ft = freetype.Face(font_path)
        self.ft.set_char_size(PT_SIZE * 64, 0, DPI, 0)

        blob = hb.Blob.from_file_path(font_path)
        face = hb.Face(blob)
        self.hb_font = hb.Font(face)
        scale = int(PT_SIZE * DPI / 72 * 64)
        self.hb_font.scale = (scale, scale)

        self.ascender  = self.ft.size.ascender  >> 6
        self.descender = -(self.ft.size.descender >> 6)
        self.row_height = self.ascender + self.descender

    def _render_glyph_to_img(self, gid: int, img: Image.Image,
                              x_pen: int, x_off: int, y_off: int) -> None:
        self.ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
        bm = self.ft.glyph.bitmap
        if bm.width == 0 or bm.rows == 0:
            return
        bl = self.ft.glyph.bitmap_left
        bt = self.ft.glyph.bitmap_top
        glyph_img = Image.frombytes("L", (bm.width, bm.rows), bytes(bm.buffer))
        dst_x = x_pen + x_off + bl
        dst_y = y_off + self.ascender - bt
        # Paste using glyph as mask (inverted: 0=black ink)
        mask = glyph_img
        ink = Image.new("RGBA", glyph_img.size, FG + (255,))
        # Composite: only where mask is non-zero
        alpha = glyph_img  # 0=transparent, 255=opaque
        img.paste(ink, (dst_x, dst_y), alpha)

    def render_text(self, text: str, use_liga: bool) -> Image.Image:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"liga": use_liga})

        infos     = buf.glyph_infos
        positions = buf.glyph_positions

        total_w = max(1, sum(p.x_advance for p in positions) // 64)
        img = Image.new("RGBA", (total_w, self.row_height), (255, 255, 255, 255))

        x_pen = 0
        for info, pos in zip(infos, positions):
            self._render_glyph_to_img(
                info.codepoint, img,
                x_pen,
                pos.x_offset // 64,
                pos.y_offset // 64,
            )
            x_pen += pos.x_advance // 64

        return img


# ── Build grid image ───────────────────────────────────────────────────────────

def build_grid(renderer: GlyphRenderer, label_font: PILFont) -> Image.Image:
    rows: list[tuple[Image.Image, Image.Image, str]] = []
    for word, label in DEMOS:
        no_liga = renderer.render_text(word, use_liga=False)
        with_liga = renderer.render_text(word, use_liga=True)
        rows.append((no_liga, with_liga, label))

    # Measure arrow text width using a dummy draw
    dummy = Image.new("RGBA", (1, 1))
    ddraw = ImageDraw.Draw(dummy)
    arrow_bbox = ddraw.textbbox((0, 0), ARROW, font=label_font)
    arrow_w = arrow_bbox[2] - arrow_bbox[0]
    arrow_h = arrow_bbox[3] - arrow_bbox[1]

    label_max_w = max(
        ddraw.textbbox((0, 0), lbl, font=label_font)[2]
        for _, _, lbl in rows
    )

    row_h    = renderer.row_height
    cell_h   = row_h + PAD * 2
    no_w     = max(r[0].width for r in rows)
    liga_w   = max(r[1].width for r in rows)
    total_w  = PAD + no_w + arrow_w + liga_w + PAD * 2 + label_max_w + PAD
    total_h  = cell_h * len(rows) + ROW_GAP * (len(rows) - 1) + PAD * 2

    grid = Image.new("RGBA", (total_w, total_h), BG + (255,))
    draw = ImageDraw.Draw(grid)

    y = PAD
    for i, (no_liga_img, liga_img, label) in enumerate(rows):
        # Left: no-ligature (variant-1 default)
        grid.paste(no_liga_img, (PAD, y), no_liga_img)

        # Arrow
        ax = PAD + no_w + (arrow_w - arrow_w) // 2
        ay = y + (row_h - arrow_h) // 2
        draw.text((ax, ay), ARROW, font=label_font, fill=FG)

        # Right: with ligature (corrected reading)
        lx = PAD + no_w + arrow_w
        grid.paste(liga_img, (lx, y), liga_img)

        # Label
        label_x = lx + liga_w + PAD
        label_y = y + (row_h - arrow_h) // 2
        draw.text((label_x, label_y), label, font=label_font, fill=LABEL_COL)

        # Separator line
        if i < len(rows) - 1:
            line_y = y + cell_h + ROW_GAP // 2
            draw.line([(PAD, line_y), (total_w - PAD, line_y)],
                      fill=(220, 220, 220), width=1)

        y += cell_h + ROW_GAP

    # Convert to RGB for saving as PNG
    bg = Image.new("RGB", grid.size, BG)
    bg.paste(grid, mask=grid.split()[3])
    return bg


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--font",
        default=str(ROOT / "fonts/Heiti/ttf/NanGuoHeitiPinyin-1.ttf"),
        help="Path to variant-1 TTF",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "documentation/ligature_confirm_10.png"),
        help="Output PNG path",
    )
    args = ap.parse_args()

    renderer = GlyphRenderer(args.font)

    # Use a simple system monospace font for the arrow/label text
    try:
        label_font = PILFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except OSError:
        label_font = PILFont.load_default()

    img = build_grid(renderer, label_font)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"Saved: {out}  ({img.width}×{img.height})")


if __name__ == "__main__":
    main()
