# Output Font Requirements

Authoritative structural spec for files produced by `scripts/make_pinyin_font.py`.
Derived by comparing the reference input `data/FangZhengKaiTiPinYinZiKu-1.ttc`
(`FZKTPY01`…`FZKTPY06`) with the known-good output `good/NanGuoPinyin-1.ttf`.

The build script is correct **only when every output TTF satisfies every
rule in this document**. The tests in `tests/` enforce a subset; the rest
must hold by construction in `make_pinyin_font.py`.

To regenerate the comparison report, run
`python scripts/compare_fonts.py > scripts/compare_fonts_output.txt`.

> **Tunable numeric parameters live in [`config.json`](./config.json)**
> (project root). Every concrete number in this spec — UPM, ascents,
> ruby baseline/em, PUA range, heteronym thresholds, etc. — is sourced
> from that file. Change the value there, not inline in
> `make_pinyin_font.py`, so future fine-tuning is centralized. All
> metric values in `config.json` are stated at the **1000-UPM reference
> grid**; the build script scales them linearly when the source font's
> UPM differs (e.g. `actual = round(value * source_upm / 1000)`).

---

## 1. Header / OS/2 / hhea metrics

All values below are stated at `unitsPerEm = 1000` (Noto Sans SC / Noto
Serif SC reference grid). The build script must scale them linearly
when the source font's UPM differs. **All numeric values are sourced
from `config.json` → `metrics_at_upm_1000`.**

| Field | config.json key | Notes |
|---|---|---|
| `head.unitsPerEm` | `upm_reference` (defaults to source UPM) | Inherited from source. |
| `hhea.ascent` | `metrics_at_upm_1000.hhea_ascent` | Extended to accommodate ruby above baseline. |
| `hhea.descent` | `metrics_at_upm_1000.hhea_descent` | |
| `hhea.lineGap` | `metrics_at_upm_1000.hhea_line_gap` | |
| `OS/2.usWinAscent` | `metrics_at_upm_1000.os2_win_ascent` | Must match `hhea.ascent` for Windows GDI. |
| `OS/2.usWinDescent` | `metrics_at_upm_1000.os2_win_descent` | Positive value. |
| `OS/2.sTypoAscender` | `metrics_at_upm_1000.os2_typo_ascender` | |
| `OS/2.sTypoDescender` | `metrics_at_upm_1000.os2_typo_descender` | |
| `OS/2.sTypoLineGap` | `metrics_at_upm_1000.os2_typo_line_gap` | |
| `OS/2.fsSelection` bit 7 (`USE_TYPO_METRICS`) | `os2_flags.fs_selection_use_typo_metrics_bit_7` | Without it, Windows GDI and macOS/Linux disagree on line height. Currently `xfail` in tests — fix to flip to enforced. |
| `OS/2.fsSelection` bit 6 (`REGULAR`) | `os2_flags.fs_selection_regular_bit_6_for_regular_weight` | Must agree with `head.macStyle`. |
| `OS/2.fsType` | `os2_flags.fs_type` | Free embedding (required for OFL fonts). |
| `OS/2.usWeightClass` | `metrics_at_upm_1000.os2_weight_class` | Matches Noto source. |
| `OS/2.usWidthClass` | `metrics_at_upm_1000.os2_width_class` | |
| `OS/2.panose` | (copied from source) | |
| `OS/2.achVendID` | `vendor.ach_vend_id` | 4-char vendor tag. |

### Ruby geometry

All values below come from `config.json` → `ruby_geometry_at_upm_1000`:

- Ruby baseline = `baseline_y`
- Ruby em (cap height of pinyin glyphs) = `em`
- Headroom above tallest ruby = `headroom_above_ruby` (= `os2_win_ascent − baseline_y − em` at the reference grid)
- Base hanzi occupies its original `0..upm_reference` box; ruby sits in `baseline_y..(baseline_y + em)`

Scale to actual UPM with `actual = round(value * source_upm / upm_reference)`.

---

## 2. Required tables

Output must contain **all 20** of these tables. Eight of them are
**missing from the FZKTPY reference** and must be carried over from the
Noto source (or synthesized):

```
BASE  GDEF  GPOS  GSUB  STAT  cmap  gasp  glyf
hhea  head  hmtx  loca  maxp  name  OS/2  post  prep  vhea  vmtx
```

Plus `GlyphOrder` (fontTools-internal, not a real table).

- `BASE`, `GDEF`, `GPOS`, `GSUB`, `STAT`, `gasp`, `vhea`, `vmtx` — copy
  from Noto source. They make the font behave correctly in Office,
  Google Fonts, and on macOS as a proper family member.
- `CFF`/`CFF2` — **must not be present**. Output is TrueType-only (`glyf`).
- `post.formatType` — **3.0** (no glyph names — saves ~200 KB and is what
  Google Fonts ships).

---

## 3. CJK composite structure

Every Hanzi codepoint in `cmap` must map to a glyph that is a **TrueType
composite with exactly two components**:

```
component 0:  base CJK glyph (from Noto source, no ruby)
component 1:  PUA syllable glyph (uniE000..uniE7DA range), positioned
              so its glyph box sits in the ruby band (y = 852..1172)
```

Sample (from `good/NanGuoPinyin-1.ttf`):

```
你 U+4F60  =  composite[glyph34064, uniE286]
行 U+884C  =  composite[glyph35173, uniE3F9]
中 U+4E2D  =  composite[glyph35737, uniE468]
```

The base component keeps the source font's original outline unchanged
(no scaling, no offset). The PUA component is referenced as-is; its own
outline already encodes the ruby's scale and vertical offset. This is
verified by `tests/test_composites.py`.

---

## 4. PUA ruby glyphs

PUA glyphs encode the rendered pinyin syllables (e.g. `nǐ`, `xíng`).

- **Glyph names**: range and format from `config.json` → `pua_range`
  (default `uniE000` … `uniE7DA`, naming `pua_range.glyph_name_format`).
- **Source**: either rendered from the base font's own Latin + combining
  diacritic glyphs (Sans variant) or imported from FZKTPY's PUA glyphs
  (Serif variant, for fuller syllable coverage).
- **Geometry**: scaled to `ruby_geometry_at_upm_1000.em` units (on
  UPM=1000), positioned so the baseline sits at
  `ruby_geometry_at_upm_1000.baseline_y`.
- **Existence in `glyf`**: required (composites reference them).
- **Existence in `cmap`**: **MUST NOT** be mapped. PUA glyphs are
  internal-only. Exposing them via cmap would let users type
  ``-and-up and see raw syllables, which is not a supported use
  case. The FZKTPY reference does expose them; the output font does not.

This is the **key cmap difference** between FZKTPY (2,011 PUA entries)
and `good/NanGuoPinyin-1.ttf` (0 PUA entries).

---

## 5. cmap

| Aspect | Requirement |
|---|---|
| Subtable set | At minimum `(3,1, format 4)` for Windows BMP and `(3,10, format 12)` for full UCS — Noto SC has codepoints above U+FFFF. Add `(0,3)`, `(0,4)`, `(1,0)` for macOS/legacy compatibility. |
| ASCII coverage | All 95 printable ASCII codepoints (`cmap_coverage.ascii_printable_required`). |
| CJK coverage | At least `cmap_coverage.min_cjk_coverage` (default `GB2312`, `cmap_coverage.min_cjk_count` = 6,763). The reference output covers the full CJK Unified block (~21K) by inheriting from Noto. |
| PUA in cmap | **0 entries** when `cmap_coverage.expose_pua_in_cmap` is `false` — see §4. |
| Cross-variant invariant | The cmap **codepoint set is identical** across variants `-1`…`-6` within a family. Only the **target glyph** (the composite chosen for a heteronym) changes. Verified by `tests/test_cmap.py`. |

---

## 6. The 6 variants

Each family ships `variants.count` TTFs (default 6: `-1` through `-6`).
They differ **only** in which composite a heteronym codepoint maps to.

- Variant `-N` takes its primary reading source from **FZKTPY0N**
  (TTC index = `variants.ttc_index_for_variant_n` evaluated at `N`).
- Variant `-1` covers all in-scope hanzi with the most common reading
  (≥ `variants.primary_reading_coverage_min` of heteronyms get their
  default pronunciation here).
- Filename suffix follows `variants.filename_suffix_format`.
- Higher variants swap in alternate readings for heteronyms; for
  non-heteronyms they reuse the `-1` composite.
- Cross-variant rules verified by tests:
  - Cmap codepoint set identical (`test_cmap.py`)
  - Variant `-2` glyph differs from `-1` for ≥
    `heteronym_divergence.variant_2_vs_1_min_ratio` of heteronyms
    (`test_heteronyms.py`)
  - PostScript names end in `-1`..`-6` and are unique
    (`test_variants.py`)
  - `name[7]` (Preferred Family) shared across all variants
    (`test_variants.py`)

---

## 7. `name` table

Required name IDs, all at platform 3 / encoding 1 / lang 0x0409 (Win
English). IDs 1, 4, 6 additionally need platform 1 (Mac Roman) records.

| ID | Content | Per-variant? |
|---:|---|:-:|
| 0 | Copyright string | shared |
| 1 | Family — e.g. `NanGuo Pinyin 1` (legacy, includes variant number) | per |
| 2 | Subfamily — `Regular` | shared |
| 3 | Unique font identifier — `NanGuoPinyin-1:2026` | per |
| 4 | Full name — `NanGuo Pinyin 1 Regular` | per |
| 5 | Version — `Version 1.000` | shared |
| 6 | PostScript name — `NanGuoPinyin-1` (must match filename, no spaces) | per |
| 7 | **Preferred Family** — `NanGuo Pinyin` (no variant number; shared across all 6 variants of a family) | shared |
| 8 | Manufacturer | shared |
| 9 | Designer | shared |
| 10 | Description | shared |
| 11 | Vendor URL | shared |
| 12 | Designer URL | shared |
| 13 | License — full OFL text | shared |
| 14 | License URL — `https://scripts.sil.org/OFL` | shared |
| 16 | Typographic Family — same as ID 7 | shared |
| 17 | Typographic Subfamily — `Regular` | shared |
| 25 | Variations PostScript prefix — `NotoSansSC` (or `NotoSerifSC`) | shared |
| 257, 265–274 | STAT axis value records (`Weight`, `Thin`, `ExtraLight`, …, `Black`) | shared |

### Known gap (currently `xfail`)

**Mac platform `name[2]` (subfamily) is missing** on all 12 TTFs of the
reference output. Google Fonts and macOS Font Book want it. Fixing
`make_pinyin_font.py` to emit `(platformID=1, platEncID=0, langID=0,
nameID=2)` = `"Regular"` will flip `tests/test_name_table.py` from xfail
to enforced.

---

## 8. Glyph inventory

- **Numerous Noto glyphs are preserved** (Latin, Greek, Cyrillic,
  combining marks, symbols, etc.). The output keeps Noto's full glyph
  set — only the CJK glyphs are *replaced* with composites. The
  reference output has ~42K glyphs total.
- **PUA syllables added**: ~2,000 glyphs in the `uniE000+` range.
- **Glyph ordering**: deterministic between runs (sort by codepoint, then
  by component-glyph index) so identical inputs produce byte-identical
  output where possible.

---

## 9. Validation gates (must all pass)

Run from project root, with the venv activated:

```powershell
.\.venv\Scripts\Activate.ps1
python tests\run_all.py
```

The suite enforces structure, name table, metrics, cmap, composite shape,
cross-variant consistency, heteronym divergence, and (when shaperglot is
installable) `fontbakery check-googlefonts`. See the CLAUDE.md "What the
suite covers" table for per-module detail.

**Treat any unexpected failure as a build regression**, not a warning.

---

## 10. Quick checklist for `make_pinyin_font.py`

When modifying the build script, walk this list before considering a
change done. All numbers below are read from `config.json` — do not
hardcode them in the script.

- [ ] Load `config.json` once at start; pass the parsed dict through
      the build pipeline. Compute UPM-scaled values from `upm_reference`
      and the source font's actual UPM.
- [ ] Start from Noto source; keep all non-CJK glyphs and tables (`BASE`,
      `GDEF`, `GPOS`, `GSUB`, `STAT`, `gasp`, `vhea`, `vmtx`) intact.
- [ ] Generate or import PUA ruby glyphs in the `pua_range`, scaled to
      `ruby_geometry_at_upm_1000.em` on the UPM=1000 grid.
- [ ] Replace each in-scope Hanzi with a composite of
      `composite.components_per_hanzi` parts: `[base, PUA-ruby]`.
- [ ] Do **not** add PUA codepoints to cmap (when
      `cmap_coverage.expose_pua_in_cmap` is `false`).
- [ ] Apply all `metrics_at_upm_1000` values, scaled.
- [ ] Set `OS/2.fsSelection` bit 7 per
      `os2_flags.fs_selection_use_typo_metrics_bit_7` — fixes xfail.
- [ ] Emit full `name` table including ID 7 (shared across variants),
      IDs 16/17, ID 25, STAT axis records, and Mac platform ID 2 —
      fixes the second xfail.
- [ ] Per-variant: filename follows `variants.filename_suffix_format`;
      name IDs 1/3/4/6 include the variant suffix; ID 7 does NOT.
- [ ] `post.formatType` = `post_table.format_type`; no `CFF`/`CFF2`.
- [ ] `python tests\run_all.py` passes.
