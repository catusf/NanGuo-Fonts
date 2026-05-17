#!/usr/bin/env python3
"""Generate NanGuo_Demo_Heiti.pdf and NanGuo_Demo_Songti.pdf from samples/sample_text.md.

Font name mapping:
    NanGuo Heiti  PinYin N -> fonts/Heiti/ttf/NanGuoHeitiPinyin-N.ttf
    NanGuo Songti PinYin N -> fonts/Songti/ttf/NanGuoSongtiPinyin-N.ttf
"""
from __future__ import annotations

import re
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
SAMPLE_MD = ROOT / "samples" / "sample_text.md"
SAMPLES_OUT = ROOT / "samples" / "output"

# Row height (mm) for Chinese rows rendered at 24pt — 1.6× spaced to fit on one page.
CHINESE_ROW_H = 15
LABEL_W = 58  # mm — font-name label column


# ── font helpers ──────────────────────────────────────────────────────────────

def _ttf_path(style: str, variant: int, bold: bool = False) -> pathlib.Path:
    suffix = "-Bold" if bold else ""
    return FONTS_DIR / style / "ttf" / f"NanGuo{style}Pinyin-{variant}{suffix}.ttf"


def _resolve(md_name: str, style: str) -> tuple[str, str, int]:
    """Extract a variant number from md_name and return (alias, style, variant)."""
    m = re.search(r"(\d+)", md_name)
    variant = int(m.group(1)) if m else 1
    return (f"NanGuo_{style}_v{variant}", style, variant)


# ── markdown parser ───────────────────────────────────────────────────────────

def parse_md(path: pathlib.Path) -> list[dict]:
    sections: list[dict] = []
    cur: dict | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if line.startswith("## "):
            cur = {"title": line[3:], "font_size": 12, "text_font": None, "items": []}
            sections.append(cur)
            continue

        if cur is None or not line:
            continue

        m = re.match(r"Font size:\s*(\d+)pt$", line)
        if m:
            cur["font_size"] = int(m.group(1))
            continue

        # Section-level font directive: "<font_name> font" (no colon, no 'Render')
        m = re.match(r"(.+?)\s+font$", line)
        if m and not line.startswith("Render"):
            cur["text_font"] = m.group(1).strip()
            continue

        # Render instruction: "Render in <font_name> font: <text>"
        m = re.match(r"Render in (.+?) font:\s+(.+)", line)
        if m:
            cur["items"].append({
                "type": "render",
                "font_name": m.group(1).strip(),
                "text": m.group(2).strip(),
            })
            continue

        # Multilingual line: "Label: text" or "Label:text"
        if ":" in line:
            label, _, text = line.partition(":")
            cur["items"].append({
                "type": "text",
                "label": label.strip(),
                "text": text.strip(),
            })

    return [s for s in sections if s["items"]]


# ── PDF builder ───────────────────────────────────────────────────────────────

def build(out_path: pathlib.Path, style: str) -> None:
    sections = parse_md(SAMPLE_MD)

    pdf = FPDF(format="A4", orientation="L")
    pdf.set_margins(8, 8, 8)
    pdf.set_auto_page_break(auto=True, margin=8)
    pdf.add_page()

    loaded: set[str] = set()

    def load(md_name: str) -> str:
        alias, s, variant = _resolve(md_name, style)
        if alias not in loaded:
            ttf = _ttf_path(s, variant)
            if not ttf.exists():
                raise FileNotFoundError(f"Font not found: {ttf}")
            pdf.add_font(alias, fname=str(ttf))
            loaded.add(alias)
        return alias

    default = load("variant 1")

    bold_alias = f"NanGuo{style}_Bold"
    if bold_alias not in loaded:
        bold_ttf = _ttf_path(style, 1, bold=True)
        if not bold_ttf.exists():
            raise FileNotFoundError(f"Bold font not found: {bold_ttf}")
        pdf.add_font(bold_alias, fname=str(bold_ttf))
        loaded.add(bold_alias)

    style_label = "黑体" if style == "Heiti" else "宋体"
    pdf.set_font(default, size=15)
    pdf.set_text_color(25, 25, 25)
    pdf.cell(0, 10, f"NanGuo Pinyin — Sample Text ({style} / {style_label}) / 南国拼音示例文字",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    for section in sections:
        font_size = section["font_size"]

        pdf.set_font(bold_alias, size=14)
        pdf.set_text_color(25, 25, 25)
        pdf.cell(0, 8, section["title"], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for item in section["items"]:

            if item["type"] == "render":
                alias = load(item["font_name"])
                _, _, variant = _resolve(item["font_name"], style)
                label = f"NanGuo {style} PinYin {variant}"

                pdf.set_font(default, size=7)
                pdf.set_text_color(120, 120, 120)
                pdf.cell(LABEL_W, CHINESE_ROW_H, label, align="R")

                pdf.set_font(alias, size=font_size)
                pdf.set_text_color(10, 10, 10)
                pdf.cell(0, CHINESE_ROW_H, "  " + item["text"],
                         new_x="LMARGIN", new_y="NEXT")

            elif item["type"] == "text":
                row_h = round(font_size * 25.4 / 72 * 1.6, 1)
                # Always use variant 1 of the current style for body text
                text_alias = load("variant 1")

                pdf.set_font(default, size=9)
                pdf.set_text_color(80, 80, 150)
                pdf.cell(30, row_h, item["label"] + ":")

                pdf.set_font(text_alias, size=font_size)
                pdf.set_text_color(10, 10, 10)
                pdf.cell(0, row_h, item["text"],
                         new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)
        pdf.set_draw_color(210, 210, 210)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(6)

    pdf.output(str(out_path))


# ── PNG export ────────────────────────────────────────────────────────────────

def pdf_to_png(pdf_path: pathlib.Path, dpi: int = 150) -> list[pathlib.Path]:
    """Render each page of pdf_path to a PNG next to the PDF. Returns written paths."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], check=True)
        import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    out_paths: list[pathlib.Path] = []
    stem = pdf_path.stem
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat)
        out = pdf_path.parent / f"{stem}.png"
        pix.save(str(out))
        out_paths.append(out)
    doc.close()
    return out_paths


def main() -> None:
    SAMPLES_OUT.mkdir(parents=True, exist_ok=True)
    doc_dir = ROOT / "documentation"
    doc_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading  {SAMPLE_MD.relative_to(ROOT)}")
    for style in ("Heiti", "Songti"):
        out = SAMPLES_OUT / f"NanGuo_Demo_{style}.pdf"
        print(f"Writing  {out.relative_to(ROOT)} ...", end=" ", flush=True)
        build(out, style)
        print(f"{out.stat().st_size // 1024} KB")
        pngs = pdf_to_png(out)
        for p in [out] + pngs:
            dest = doc_dir / p.name
            dest.write_bytes(p.read_bytes())
            print(f"  → {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
