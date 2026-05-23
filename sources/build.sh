#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "../.venv/bin/activate" ]; then
    source "../.venv/bin/activate"
fi

echo "=== Building NanGuo Pinyin Fonts ==="

echo "[1/4] Heiti Regular"
python scripts/make_pinyin_font_v2.py \
    --font   "Heiti/base-font/NotoSansSC-Regular.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "../fonts/Heiti/ttf"

echo "[2/4] Heiti Bold"
python scripts/make_pinyin_font_v2.py \
    --font   "Heiti/base-font/NotoSansSC-Bold.ttf" \
    --name   "NanGuo Heiti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "../fonts/Heiti/ttf"

echo "[3/4] Songti Regular"
python scripts/make_pinyin_font_v2.py \
    --font   "Songti/base-font/NotoSerifSC-Regular.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "../fonts/Songti/ttf"

echo "[4/4] Songti Bold"
python scripts/make_pinyin_font_v2.py \
    --font   "Songti/base-font/NotoSerifSC-Bold.ttf" \
    --name   "NanGuo Songti Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    "../fonts/Songti/ttf"

echo "=== Adding contextual reading ligatures to variant-1 fonts ==="
for FONT in \
    "../fonts/Heiti/ttf/NanGuoHeitiPinyin-1.ttf" \
    "../fonts/Heiti/ttf/NanGuoHeitiPinyin-1-Bold.ttf" \
    "../fonts/Songti/ttf/NanGuoSongtiPinyin-1.ttf" \
    "../fonts/Songti/ttf/NanGuoSongtiPinyin-1-Bold.ttf"; do
    python scripts/add_ligatures.py \
        --font     "$FONT" \
        --data     "data/duoyinzi_pattern_one.txt" \
        --heteronym "data/heteronym_map.json" \
        --syllables "data/syllable_inventory.json"
done

echo "=== Bundling TTC collections ==="
python scripts/bundle_ttc.py

echo "=== Refreshing OFL/METADATA/DESCRIPTION in font dirs ==="
cp ../OFL.txt ../fonts/Heiti/ttf/OFL.txt
cp ../OFL.txt ../fonts/Songti/ttf/OFL.txt

echo "=== Building sample PDFs ==="
python scripts/build_pdf.py

echo "=== Building specimen images ==="
python scripts/build_specimen.py

echo "=== Building poem specimen ==="
python scripts/build_poem_pdf.py

echo "=== Running tests ==="
python ../tests/run_all.py

echo "=== Done ==="
