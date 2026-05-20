# Pinyin Font Builder Skill

## What it does
Converts any CJK TrueType/OpenType font into a 6-variant Pinyin ruby font
where each Chinese character displays its Hanyu Pinyin pronunciation above it
as a native font glyph — no HTML `<ruby>` tags needed.

## Trigger
Use this skill when the user asks to:
- "Tạo pinyin font từ font X"
- "Build a pinyin/ruby font"  
- "Add pinyin annotation to font"
- "Convert [any CJK font] to pinyin font"

## Usage

```bash
python3 make_pinyin_font.py \
    --font   NotoSansSC-Regular.ttf \
    --name   "NanGuo Sans Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    ./output/
```

With FZKTPY KaiTi-style PUA glyphs (more complete syllable coverage):

```bash
python3 make_pinyin_font.py \
    --font       NotoSerifSC-Regular.ttf \
    --name       "NanGuo Serif Pinyin" \
    --author     "Catus Felis" \
    --url        "https://catusf.github.io" \
    --pua-source FangZhengKaiTiPinYinZiKu-1.ttc \
    --out        ./output/
```

## Output
```
output/
├── NanGuoSansPinyin-1.ttf   ← primary pronunciation
├── NanGuoSansPinyin-2.ttf   ← secondary (alternate readings)
├── NanGuoSansPinyin-3.ttf
├── NanGuoSansPinyin-4.ttf
├── NanGuoSansPinyin-5.ttf
├── NanGuoSansPinyin-6.ttf
├── METADATA.pb
├── OFL.txt
└── DESCRIPTION.en_us.html
```

## Font requirements
- **Format**: TTF (glyf table). OTF is auto-converted.
- **Must contain**: CJK Unified Ideographs + Latin Extended (pinyin diacritics)
- **Tested with**: Noto Sans SC, Noto Serif SC

## Pipeline phases
| Phase | Description |
|-------|-------------|
| 1 | Detect font UPM, CJK advance width, compute ruby geometry |
| 2 | Generate 1,349+ PUA syllable glyphs (from base font's Latin letters OR from FZKTPY) |
| 3 | Build 6,763 composite CJK glyphs: `[base + PUA_ruby]` |
| 4 | Build 6 variant sub-fonts with different cmap assignments per pronunciation |
| 5 | Export 6×TTF + METADATA.pb + OFL.txt + DESCRIPTION.en_us.html |

## Ruby geometry (auto-scaled to any UPM)
| Parameter | Formula | Example (UPM=1000) |
|-----------|---------|-------------------|
| `ruby_y` | 0.852 × UPM | 852 |
| `ruby_em` | 0.320 × UPM | 320 |
| `new_ascent` | 1.400 × UPM | 1400 |

## Data files (in `_data/`)
| File | Description |
|------|-------------|
| `heteronym_map.json` | GB2312 chars → 6-slot reading array (slot 0 = primary, 1–5 = heteronym alternates) |
| `syllable_inventory.json` | 1,349 unique syllables → PUA codepoints |
| `refdata_pua_syllable_map.json` | FZKTPY PUA → syllable mapping (1,618 entries) |

## Dependencies
```bash
pip install fonttools pypinyin
```
