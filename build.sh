#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "=== Building NanGuo Pinyin Fonts ==="

echo "[1/4] Heiti Regular"
python sources/scripts/make_pinyin_font_v2.py \
    --font   "sources/Heiti/base-font/NotoSansSC-Regular.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "fonts/Heiti/ttf"

echo "[2/4] Heiti Bold"
python sources/scripts/make_pinyin_font_v2.py \
    --font   "sources/Heiti/base-font/NotoSansSC-Bold.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "fonts/Heiti/ttf"

echo "[3/4] Songti Regular"
python sources/scripts/make_pinyin_font_v2.py \
    --font   "sources/Songti/base-font/NotoSerifSC-Regular.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "fonts/Songti/ttf"

echo "[4/4] Songti Bold"
python sources/scripts/make_pinyin_font_v2.py \
    --font   "sources/Songti/base-font/NotoSerifSC-Bold.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "fonts/Songti/ttf"

echo "=== Refreshing OFL/METADATA/DESCRIPTION in font dirs ==="
cp OFL.txt fonts/Heiti/ttf/OFL.txt
cp OFL.txt fonts/Songti/ttf/OFL.txt

echo "=== Running tests ==="
python tests/run_all.py

echo "=== Done ==="
