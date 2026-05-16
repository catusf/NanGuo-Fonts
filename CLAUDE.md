# NanGuoFonts

Pinyin ruby fonts for Simplified Chinese. Each Hanzi glyph is composited
with its Hanyu Pinyin pronunciation rendered above it as native font
geometry — no HTML `<ruby>` markup needed at render time.

## What's in this folder

Output drafts only. The build pipeline is described in `requirements/Make_pinyin_fonts_skills.md`
but the `scripts/make_pinyin_font.py` script and `_data/` JSON files are not checked in
here yet — they live wherever the skill is invoked from.

| File | Purpose |
|------|---------|
| `data/FangZhengKaiTiPinYinZiKu-1.ttc` | Historical reference font. Used by `sources/scripts/extract_refdata.py` to regenerate the JSON caches in `sources/data/`, but **no longer read by the build pipeline** (`build.sh`). |
| `data/NotoSansSC-Regular` | The input font file for glyphs. You need to put the pinyin on top of Chinese characters in this font, and create a new output font. |
| `good/NanGuoPinyin-1.ttf` | The reference output file that works properly. You need to refer to its structure for reference. |
| `requirements/Output_font_requirements.md` | **Authoritative structural spec** for output TTFs — derived from comparing FZKTPY01 with `good/NanGuoPinyin-1.ttf`. Consult this before changing `make_pinyin_font.py`. |
| `config.json` | Tunable numeric parameters (UPM-reference metrics, ruby geometry, PUA range, heteronym thresholds, variant count). Edit values here, not inline in the build script. Referenced throughout `requirements/Output_font_requirements.md`. |
| `requirements/Make_pinyin_fonts_skills.md` | The build recipe (inputs, CLI, pipeline phases) |
| `scripts/compare_fonts.py` | Generates the comparison report (input vs. reference output) that `requirements/Output_font_requirements.md` is based on. |
| `.venv/` | Python 3 venv — see `requirements-test.txt` for test deps |
| `requirements-test.txt` | Pinned test dependencies (fontTools, pypinyin, fontbakery, pytest) |
| `pytest.ini` | pytest configuration (testpaths, markers) |
| `tests/` | Quality & compatibility test suite — `python tests/run_all.py` |
| `test.py` | Throwaway scratch file, safe to ignore or replace |
| `scripts/make_pinyin_font.py` | The script to creat output font file. |

## The 6-variant scheme

Each family ships six TTFs that differ only in their cmap. Variant `-1` is
the **primary** reading; `-2` through `-6` carry **alternate readings** for
heteronyms (多音字 — characters with more than one pronunciation, e.g. 行
xíng / háng). The same character codepoint maps to a different
`base + pinyin-ruby` composite glyph in each variant.

Variant divergence is driven by `data/heteronym_map.json` — variant 1 carries
the primary reading from `data/pinyin_map.json`; variants 2–6 carry heteronym
alternates. The slot convention (six variants) was originally modeled on the
six FZKTPY sub-fonts, but the build no longer reads the .ttc at runtime.

Typical use: stack the variants in CSS `font-family` fallback, or let the
reader toggle between them when a character has multiple readings. Variant
`-1` alone covers ~73% of the heteronym set with the most common reading
(per `heteronym_map.json` in the skill's data files).

## Rebuilding the fonts

The full procedure is in `requirements/Make_pinyin_fonts_skills.md`. Quick reference:

```bash
# Sans (uses base font's own Latin letters for ruby glyphs)
python make_pinyin_font.py \
    --font   NotoSansSC-Regular.ttf \
    --name   "NanGuo Sans Pinyin" \
    --author "Catus Felis" \
    --url    "https://catusf.github.io" \
    --out    ./output/

# Serif (same Latin-composed ruby path as Sans)
python make_pinyin_font.py \
    --font       NotoSerifSC-Regular.ttf \
    --name       "NanGuo Serif Pinyin" \
    --author     "Catus Felis" \
    --url        "https://catusf.github.io" \
    --out        ./output/
```

Activate the venv and install test deps once:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-test.txt
```

The build pipeline itself (`make_pinyin_font.py`) needs at minimum
`fonttools` and `pypinyin`, both of which are pulled in by the test
requirements above.

## Output font requirements

The full structural spec the output TTFs must satisfy — metrics, required
tables, composite shape, PUA conventions, cmap, name table, the 6-variant
contract, and a quick build-script checklist — is in
[`requirements/Output_font_requirements.md`](./requirements/Output_font_requirements.md). It is
derived from comparing the FZKTPY input with `good/NanGuoPinyin-1.ttf`
and supersedes any conflicting hint elsewhere in this file. **Read it
before editing `scripts/make_pinyin_font.py`.**

## Source font requirements

- TrueType outlines (`glyf` table). OTF is auto-converted by the script.
- Must cover CJK Unified Ideographs **and** Latin Extended, Latin Extended Additional, tin Extended-A, tin Extended-B, mbining Diacritical Marksor pinyin diacritics like ā ē ǐ ǔ ǘ). 
- Tested with Noto Sans SC and Noto Serif SC.
- Copy all the glyphs from the source fonts. Modify chinese characters same as in the refereneced font.

## Ruby geometry

Auto-scaled to the source font's UPM. For UPM=1000: ruby baseline at y=852,
ruby em=320, ascent extended to 1400. Formulas are in the skill doc.

## Quality & compatibility checks

Every rebuild must pass these before the TTFs are considered ready to ship.
Tests live alongside the build script and are **required to run on every
font update** — treat a failing check as a build failure, not a warning.

Target platforms / consumers:

| Target | What to verify |
|--------|----------------|
| Windows | Installs via right-click → Install; renders correctly in Notepad, WordPad, Edge, and the Settings → Fonts preview. `name` table IDs 1/2/4/6 well-formed; no GDI fallback to Tahoma. |
| Microsoft Office | Word, PowerPoint, Excel pick up all six variants as distinct family members; ruby composites render at common sizes (10/12/16/24/36 pt); no missing-glyph boxes for the GB2312 set. |
| macOS | Installs via Font Book without validation errors; renders in TextEdit, Pages, Safari; the six variants appear as separate faces, not collapsed into one family. |
| Linux | `fc-cache -fv` picks them up; renders in GNOME Text Editor / LibreOffice / Firefox under fontconfig + FreeType; hinting doesn't smear the ruby at body sizes. |
| Google Fonts | Passes [Font Bakery](https://github.com/fonttools/fontbakery) `googlefonts` profile cleanly, including `METADATA.pb`, `OFL.txt`, and `DESCRIPTION.en_us.html` lints. |

### Running the suite

```powershell
.\.venv\Scripts\Activate.ps1
python tests\run_all.py
```

The suite lives in `tests/` and runs via pytest. It must be re-run after
every `make_pinyin_font.py` invocation — treat any unexpected failure as a
build regression.

### What the suite covers

| Module | Checks |
|---|---|
| `test_structure.py` | TTF opens, has `glyf` (not CFF), UPM in {1000,1024,2048}, required tables present |
| `test_name_table.py` | name IDs 1–7 on Windows; Mac platform IDs 1/2/4/6; PostScript matches filename; shared `name[7]` across variants |
| `test_metrics.py` | OS/2 fsSelection ⇄ head.macStyle consistency, USE_TYPO_METRICS bit, Win ascent accommodates ruby, consistent `usWeightClass`/`usWidthClass` |
| `test_cmap.py` | GB2312 hanzi fully covered; cmap codepoint set identical across the 6 variants within each family |
| `test_composites.py` | Variant `-1` CJK glyphs are 2-component composites with a PUA-named ruby sub-glyph |
| `test_variants.py` | Sans/Serif share `name[7]` (Preferred Family); PostScript suffixes are `-1`..`-6` and unique |
| `test_heteronyms.py` | For pypinyin-confirmed heteronyms, variant `-2` glyph differs from `-1` (≥70%); higher variants still provide some divergence |
| `test_fontbakery.py` | Runs `fontbakery check-googlefonts` per family, fails on any FAIL/ERROR |

### Known build-pipeline gaps (currently `xfail`)

The suite currently expects these to fail because the build script produces
them — fix in `make_pinyin_font.py` and the `xfail` markers will flip to
`XPASS` (which is `strict=True`, so it becomes an enforced regression):

- **Mac platform `name[2]` (subfamily) missing** — Google Fonts and macOS
  Font Book want it. All 12 TTFs.
- **OS/2.fsSelection `USE_TYPO_METRICS` bit (7) not set** — without it
  Windows GDI and Mac/Linux disagree on line height. All 12 TTFs.

### Fontbakery on Windows / Python 3.14

The `googlefonts` profile transitively requires `shaperglot` (a Rust wheel).
If you're on Python 3.14 + Windows without Visual Studio Build Tools,
`pip install fontbakery[googlefonts]` will fail to compile it. The
fontbakery test will then **skip** with a clear message. Either install
Build Tools, drop to Python 3.13 (prebuilt wheels exist), or run the
fontbakery gate on a Linux/Mac CI runner.

## Things to keep in mind when editing here

- These TTFs are **build artifacts**. Don't hand-edit them; regenerate via
  the skill instead.
- The character coverage target is GB2312 (6,763 chars). Anything outside
  that set will render as the base CJK glyph with no ruby.
- Renaming the TTFs breaks the family/variant grouping the OS uses to pick
  the right font — keep the `-{1..6}` suffix scheme.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Git

- Before implement any feature, create a new feat/Name_of_feature branch, before fix a code, create fix/Broken_feature_name

- After done, ask me to rebase to `main` branch


---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## Folder contents

- This folder contains the original web app in RealChart to view a family tree of a GEDCOM input file, and I want to replicate its functions

- The ged_tools sub folder contain the output Family Chart Viewer app.

- The output app do not need to replicate the original app UI, but the function should be complete.

## Git

- Before implement any feature, you MUST update the `main` branch, then create a new feat/Name_of_feature branch
- After done, ask me to rebase to `main` branch

## Tests

- All the test scripts should reside in the `tests` folder.
- Run `npm test` to run all the test scripts.
- Each test script should be self-contained and should not depend on any external state.
- Each test script should be run in a clean environment.
- When possible, run the end user test scripts in Playwright to verify the UI works as expected.
- After each feature implementation, run the end user test scripts in tests/test-*.js to verify the UI works as expected.
- If the test fails, fix the test script and run it again.

# Backlog

The remaining issues need fixing are listed in @Backlog.md

