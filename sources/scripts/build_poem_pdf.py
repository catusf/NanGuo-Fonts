#!/usr/bin/env python3
"""Render 相思 (Red Beans) by Wang Wei as a 3-column table PDF.

Traditional Chinese book (线装书) color scheme:
  - 宣纸 ivory background, 朱砂红 vermilion borders & title,
    dark-red header, alternating ivory rows, ink/indigo/forest text.

Output: samples/output/NanGuo_Poem_XiangSi.pdf and .png
"""
from __future__ import annotations

import math
import subprocess
import sys
import pathlib

try:
    from fpdf import FPDF
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "fpdf2"], check=True)
    from fpdf import FPDF  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONTS_DIR = ROOT / "fonts"
SAMPLES_OUT = ROOT / "samples" / "output"

POEM = [
    ("红豆生南国，", "Đậu đỏ mọc đất phương Nam,",     "Red beans grow in the southern lands,"),
    ("春来发几枝。", "Xuân về vươn mấy cành xanh.",     "Come spring, a few new branches bloom."),
    ("愿君多采撷，", "Mong người hái lấy thật nhiều,", "I hope you'll gather many handfuls —"),
    ("此物最相思。", "Vật này thương nhớ nhất đời.",    "Of all things, these most speak of longing."),
]

STYLE = "Songti"

# Traditional Chinese book color palette
IVORY      = (253, 248, 235)   # 宣纸 xuan paper
IVORY_ALT  = (246, 237, 213)   # alternating row — slightly deeper
VERMILION  = (193,  39,  45)   # 朱砂红 cinnabar red
DARK_RED   = (120,  15,  15)   # header fill
CREAM      = (253, 245, 215)   # header text
INK        = ( 20,  10,   5)   # Chinese text — near-black ink
INDIGO     = ( 30,  50, 140)   # Vietnamese — 靛蓝
FOREST     = ( 20,  85,  35)   # English — 竹绿
WARM_BROWN = (100,  65,  30)   # subtitle — 棕


def _ttf_path(variant: int) -> pathlib.Path:
    return FONTS_DIR / STYLE / "ttf" / f"NanGuo{STYLE}Pinyin-{variant}.ttf"


def pdf_to_png(pdf_path: pathlib.Path, dpi: int = 150) -> pathlib.Path:
    try:
        import fitz
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], check=True)
        import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    out = pdf_path.with_suffix(".png")
    pix.save(str(out))
    doc.close()
    return out


def build(out_path: pathlib.Path) -> None:
    pdf = FPDF(format="A4", orientation="L")   # landscape: 297×210 mm
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=False, margin=12)
    pdf.add_page()

    ttf = _ttf_path(1)
    if not ttf.exists():
        raise FileNotFoundError(f"Font not found: {ttf}")
    alias = f"NanGuo_{STYLE}_v1"
    pdf.add_font(alias, fname=str(ttf))
    base = alias

    # ── Page background — 宣纸 ivory ──────────────────────────────────────────
    pdf.set_fill_color(*IVORY)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    # ── Title — 相思 in vermilion ─────────────────────────────────────────────
    pdf.set_font(base, size=34)
    pdf.set_text_color(*VERMILION)
    pdf.set_xy(pdf.l_margin, 13)
    pdf.cell(0, 14, "相思", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(base, size=11)
    pdf.set_text_color(*WARM_BROWN)
    pdf.cell(0, 6, "王维 · 唐    Wang Wei · Tang Dynasty",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Column geometry ───────────────────────────────────────────────────────
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin   # ≈ 267 mm
    col_zh = usable_w * 0.28
    col_vi = usable_w * 0.306   # 15% narrower than original 0.36
    col_en = usable_w * 0.414   # absorbs the difference

    zh_size   = 30
    body_size = 12
    body_lh   = body_size * 25.4 / 72 * 1.5   # mm per body line
    pad       = 4.0
    row_h     = zh_size * 25.4 / 72 * 2.2     # ≈ 28 mm

    def n_lines(text: str, col_w: float) -> int:
        pdf.set_font(base, size=body_size)
        return max(1, math.ceil(pdf.get_string_width(text) / (col_w - 2 * pad)))

    # ── Header row — dark red fill, cream text ────────────────────────────────
    hdr_h = 8.5
    hdr_y = pdf.get_y()
    pdf.set_fill_color(*DARK_RED)
    pdf.rect(pdf.l_margin, hdr_y, usable_w, hdr_h, style="F")

    pdf.set_font(base, size=10)
    pdf.set_text_color(*CREAM)
    pdf.set_xy(pdf.l_margin, hdr_y)
    pdf.cell(col_zh, hdr_h, "汉语 Chinese", align="C")
    pdf.cell(col_vi, hdr_h, "Tiếng Việt",  align="C")
    pdf.cell(col_en, hdr_h, "English",      align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Alternating row fills ─────────────────────────────────────────────────
    table_top = pdf.get_y()
    total_h   = row_h * len(POEM)

    for i in range(len(POEM)):
        pdf.set_fill_color(*(IVORY if i % 2 == 0 else IVORY_ALT))
        pdf.rect(pdf.l_margin, table_top + i * row_h, usable_w, row_h, style="F")

    # ── Table borders — vermilion, 70% thinner ───────────────────────────────
    pdf.set_draw_color(*VERMILION)

    # Outer box spanning header + data rows
    pdf.set_line_width(0.39)
    pdf.rect(pdf.l_margin, hdr_y, usable_w, hdr_h + total_h)

    # Vertical column dividers
    pdf.set_line_width(0.18)
    x1 = pdf.l_margin + col_zh
    x2 = x1 + col_vi
    for x in (x1, x2):
        pdf.line(x, hdr_y, x, hdr_y + hdr_h + total_h)

    # Horizontal dividers
    pdf.set_line_width(0.24)
    pdf.line(pdf.l_margin, table_top, pdf.l_margin + usable_w, table_top)
    pdf.set_line_width(0.10)
    for r in range(1, len(POEM)):
        y = table_top + row_h * r
        pdf.line(pdf.l_margin, y, pdf.l_margin + usable_w, y)

    # ── Poem rows ─────────────────────────────────────────────────────────────
    # Chinese ruby annotations extend above the glyph, so shift text down
    # so the visual centre of the glyph aligns with the row centre.
    zh_offset = 4.0   # mm

    for i, (zh, vi, en) in enumerate(POEM):
        y_row = table_top + i * row_h

        # Chinese — pushed down to compensate for ruby overhead
        pdf.set_font(base, size=zh_size)
        pdf.set_text_color(*INK)
        pdf.set_xy(pdf.l_margin, y_row + zh_offset)
        pdf.cell(col_zh, row_h - zh_offset, zh, align="C")

        # Vietnamese — indigo, vertically centred
        nl = n_lines(vi, col_vi)
        y_text = y_row + (row_h - nl * body_lh) / 2
        pdf.set_font(base, size=body_size)
        pdf.set_text_color(*INDIGO)
        pdf.set_xy(pdf.l_margin + col_zh + pad, y_text)
        pdf.multi_cell(col_vi - 2 * pad, body_lh, vi, align="L")

        # English — forest green, vertically centred
        nl = n_lines(en, col_en)
        y_text = y_row + (row_h - nl * body_lh) / 2
        pdf.set_font(base, size=body_size)
        pdf.set_text_color(*FOREST)
        pdf.set_xy(pdf.l_margin + col_zh + col_vi + pad, y_text)
        pdf.multi_cell(col_en - 2 * pad, body_lh, en, align="L")

    pdf.output(str(out_path))
    print(f"  Written: {out_path.relative_to(ROOT)} ({out_path.stat().st_size // 1024} KB)")


def main() -> None:
    SAMPLES_OUT.mkdir(parents=True, exist_ok=True)
    out = SAMPLES_OUT / "NanGuo_Poem_XiangSi.pdf"
    print("Building poem PDF (Songti, landscape) ...")
    build(out)
    png = pdf_to_png(out)
    print(f"  PNG:     {png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
