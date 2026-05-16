# Drop the FangZhengKaiTi PinYin .ttc dependency from the build pipeline

## Context

Until now the Serif (Songti) builds in `build.sh` passed
`--pua-source data/FangZhengKaiTiPinYinZiKu-1.ttc` to the build script, which
caused `_extract_fzktpy()` in `scripts/make_pinyin_font*.py` to open the .ttc
and pull ~2,011 PUA syllable outlines from FangZheng KaiTi PinYin's sub-font 0.
The Sans (Heiti) builds already skipped this and composed every pinyin
syllable from the base font's own Latin letters via `_compose_from_latin()`.

The user wants Serif to behave identically to Sans — every syllable composed
from the base font's Latin glyphs (`NotoSerifSC-Regular.ttf` /
`NotoSerifSC-Bold.ttf`). After this change, **`build.sh` no longer reads
`FangZhengKaiTiPinYinZiKu-1.ttc` at all**.

`data/FangZhengKaiTiPinYinZiKu-1.ttc` stays in the repo (user-confirmed). It
is still referenced by the one-shot extractor `scripts/extract_fzktpy_data.py`
for cache regeneration, but that's outside the build pipeline.

Visual consequence: Serif pinyin ruby glyphs will switch from KaiTi
calligraphic outlines to Noto Serif SC's Latin letters, matching the Sans
look-and-feel.

---

## Files to Modify

### `build.sh`
- Delete `PUA="$DATA/FangZhengKaiTiPinYinZiKu-1.ttc"` (line 13).
- Drop `--pua-source "$PUA" \` from the Songti Regular block.
- Drop `--pua-source "$PUA" \` from the Songti Bold block.

Songti and Heiti invocations become symmetric (only `--font` differs).

### `scripts/make_pinyin_font.py` and `scripts/make_pinyin_font_v2.py`

Both scripts share the same FZKTPY structure. In each:

- Remove the `--pua-source` CLI argument.
- Drop the `a.pua_source` / `a.pua-source` argument from the `phase2_pua(...)` call.
- Remove the `fzktpy_path` parameter from `phase2_pua`'s signature.
- Delete the `fz_glyphs` / `fz_syl_map` block and the surrounding
  `if fzktpy_path:` guard. The syllable loop calls `_compose_from_latin`
  unconditionally.
- Delete `_extract_fzktpy()` entirely (no remaining callers).
- Remove now-unused imports/constants if they were only used by
  `_extract_fzktpy` (typically `TTCollection`, `TransformPen`, `FZ_CJK_ADV`,
  `FZ_RUBY_H`, `FZ_RUBY_YMIN`, `is_pua_bmp`). Verify by `grep` before
  deleting each.

### `CLAUDE.md`
- Quick-reference: drop `--pua-source FangZhengKaiTiPinYinZiKu-1.ttc \`
  from the Serif example and update its comment to indicate the ruby is
  Latin-composed.
- Update the data/ table row for `FangZhengKaiTiPinYinZiKu-1.ttc` to note
  it is no longer a build input — it's kept only as source data for the
  JSON cache extractor.
- Rewrite the outdated paragraph ("For the output_font_variant_1.ttf, take
  the cmap from reference font FZKTPY01 …") — variant divergence comes from
  `data/heteronym_map.json`, not from FZKTPY sub-fonts.

### `Backlog.md`
- Mark the FZKTPY-cleanup item as `[X]`.

---

## Files NOT Modified

- `data/FangZhengKaiTiPinYinZiKu-1.ttc` — kept (user-confirmed).
- `data/fzktpy_*.json` caches — kept; `fzktpy_pua_syllable_map.json` becomes
  unused by the build but is still produced by `extract_fzktpy_data.py`.
  Removing them is out of scope.
- `scripts/extract_fzktpy_data.py`, `scripts/derive_pinyin_data*.py`,
  `scripts/compare_fonts.py` — outside the build pipeline; they still
  reference the .ttc for cache regeneration / diffing.

---

## Verification

```bash
# 1. build.sh no longer references the .ttc
grep -n FangZhengKaiTi build.sh        # expect: (no output)

# 2. Build scripts no longer touch the .ttc
grep -nE "fzktpy|FZKTPY|pua.source|_extract_fzktpy" \
    scripts/make_pinyin_font.py scripts/make_pinyin_font_v2.py
# expect: (no output)

# 3. Full clean build with the .ttc temporarily hidden, proving
#    the pipeline is genuinely independent of it
mv data/FangZhengKaiTiPinYinZiKu-1.ttc data/FangZhengKaiTiPinYinZiKu-1.ttc.hidden
./build.sh                              # must complete all 4 weights + TTC bundling
mv data/FangZhengKaiTiPinYinZiKu-1.ttc.hidden data/FangZhengKaiTiPinYinZiKu-1.ttc

# 4. Test suite still passes
python tests/run_all.py

# 5. Spot-check Serif output visually
python3 build_pdf.py                    # produces samples/output/NanGuo_Demo.pdf
```

### Pass criteria
- `./build.sh` completes with the .ttc hidden.
- `tests/run_all.py` passes (existing `xfail` items remain as-is or convert cleanly).
- Songti ruby glyphs look like Noto Serif SC Latin letters above each Hanzi —
  matching the Sans builds' typographic style.
- `output/NanGuoSongtiPinyin*.ttf` (or `NanGuoSerifPinyin*.ttf` after the
  in-flight rename merges) are produced with the same glyph count and cmap
  coverage as before; only PUA glyph outlines differ.
