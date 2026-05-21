---
title: NanGuo Pinyin Font — Chinese characters with built-in phonetics
date: 2026-05-16
categories: [Utilities]
tags: [Chinese, fonts]
---

## A Chinese font with built-in pinyin

This is a special Simplified Chinese font family: every Hanzi already
carries its pinyin printed in small type above it. You just type Chinese
characters as usual — the pinyin appears automatically. No HTML `<ruby>`
tags required, no helper software needed.

There are two families:

- **NanGuo Heiti Pinyin** — square, sans-serif style.
- **NanGuo Songti Pinyin** — serif style, traditional appearance.

Both are based on Google's Noto fonts, so they render crisply on every
operating system.

## New: support for characters with multiple readings

Chinese has many **polyphonic characters** (多音字) — characters with more
than one pronunciation. For example **行**: read as *xíng* it means "to
go"; read as *háng* it means "row, line".

Each family ships **6 variants × 2 weights (regular + bold) = 12 font
files**:

- Variant `-1`: shows the most common reading.
- Variants `-2` through `-6`: show the alternate readings.

You can stack the variants in a CSS `font-family` declaration to switch
between readings — very handy for studying and teaching Chinese.

## One font — many languages

Beyond Chinese, the font supports many other scripts. You can write text
that mixes several languages **without switching fonts mid-document**:

- **European languages using Latin script** — English, French, German,
  Spanish, Portuguese, Italian… (full diacritics: á à ã â é ñ ü ç…).
- **Vietnamese** — full set of tone marks and vowels: ạ ả ấ ầ ẩ ẫ ậ ắ
  ằ ẳ ẵ ặ ế ề ể ễ ệ ố ồ ổ ỗ ộ ớ ờ ở ỡ ợ đ.
- **Cyrillic-script languages** — Russian, Ukrainian, Bulgarian…
  (Привет, Россия).

This lets language teachers use a single font to prepare bilingual
materials in Chinese–Vietnamese, Chinese–English, Chinese–Russian… and
the type stays consistent in style and weight throughout.

## Downloads

- **NanGuo Heiti Pinyin (sans):**
  [download zip](https://github.com/catusf/NanGuo-Fonts/raw/main/release/NanGuoHeitiPinyin-GoogleFonts.zip)
- **NanGuo Songti Pinyin (serif):**
  [download zip](https://github.com/catusf/NanGuo-Fonts/raw/main/release/NanGuoSongtiPinyin-GoogleFonts.zip)
- **Source code:**
  [github.com/catusf/NanGuo-Fonts](https://github.com/catusf/NanGuo-Fonts)

## Illustrations

<!-- Remember to copy these two PNG files from samples/output/ into the blog's assets folder -->

![NanGuo Pinyin — page 1](/assets/img/posts/NanGuo_Demo_p1.png)

![NanGuo Pinyin — page 2](/assets/img/posts/NanGuo_Demo_p2.png)

## Notes

The font covers the full **GB2312** character set (6,763 common Hanzi),
ships in regular and bold weights, and is released under the **OFL**
license (free for both personal and commercial use).
