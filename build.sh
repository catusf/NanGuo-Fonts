#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

OUT="output"
DATA="data"

echo "=== Building NanGuo Pinyin Fonts ==="

echo "[1/4] Heiti Regular"
python scripts/make_pinyin_font_v2.py \
    --font   "$DATA/NotoSansSC-Regular.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"

echo "[2/4] Heiti Bold"
python scripts/make_pinyin_font_v2.py \
    --font   "$DATA/NotoSansSC-Bold.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"

echo "[3/4] Songti Regular"
python scripts/make_pinyin_font_v2.py \
    --font   "$DATA/NotoSerifSC-Regular.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"

echo "[4/4] Songti Bold"
python scripts/make_pinyin_font_v2.py \
    --font   "$DATA/NotoSerifSC-Bold.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"

echo "=== Bundling TTCs ==="
python scripts/bundle_ttc.py --out "$OUT"

echo "=== Copying to release/ ==="
mkdir -p release
cp "$OUT/NanGuoHeitiPinyin.ttc"  release/
cp "$OUT/NanGuoSongtiPinyin.ttc" release/

echo "=== Running tests ==="
python tests/run_all.py

echo "=== Done ==="
