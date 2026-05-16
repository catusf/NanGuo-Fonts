#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

OUT="output"
DATA="data"
PUA="$DATA/FangZhengKaiTiPinYinZiKu-1.ttc"

echo "=== Building NanGuo Pinyin Fonts ==="

echo "[1/4] Heiti Regular"
python scripts/make_pinyin_font.py \
    --font   "$DATA/NotoSansSC-Regular.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"

echo "[2/4] Heiti Bold"
python scripts/make_pinyin_font.py \
    --font   "$DATA/NotoSansSC-Bold.ttf" \
    --name   "NanGuo Heiti Pinyin Bold" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "$OUT"
for i in 1 2 3 4 5 6; do
    mv "$OUT/NanGuoHeitiPinyinBold-${i}.ttf" "$OUT/NanGuoHeitiPinyin-${i}-Bold.ttf"
done

echo "[3/4] Songti Regular"
python scripts/make_pinyin_font.py \
    --font       "$DATA/NotoSerifSC-Regular.ttf" \
    --name       "NanGuo Songti Pinyin" \
    --author     "Catus Felis" \
    --url        "https://catusf.github.io" \
    --pua-source "$PUA" \
    --out        "$OUT"

echo "[4/4] Songti Bold"
python scripts/make_pinyin_font.py \
    --font       "$DATA/NotoSerifSC-Bold.ttf" \
    --name       "NanGuo Songti Pinyin Bold" \
    --author     "Catus Felis" \
    --url        "https://catusf.github.io" \
    --pua-source "$PUA" \
    --out        "$OUT"
for i in 1 2 3 4 5 6; do
    mv "$OUT/NanGuoSongtiPinyinBold-${i}.ttf" "$OUT/NanGuoSongtiPinyin-${i}-Bold.ttf"
done

echo "=== Bundling TTCs ==="
python scripts/bundle_ttc.py --out "$OUT"

echo "=== Copying to release/ ==="
mkdir -p release
cp "$OUT/NanGuoHeitiPinyin.ttc"  release/
cp "$OUT/NanGuoSongtiPinyin.ttc" release/

echo "=== Running tests ==="
python tests/run_all.py

echo "=== Done ==="
