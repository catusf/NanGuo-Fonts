# Restructure NanGuo-Fonts to comply with Google Fonts upstream guide

## Context

The repo ships two Pinyin ruby font families (NanGuo Heiti Pinyin / Sans and NanGuo Songti Pinyin / Serif), each with 6 variants × 2 weights = 12 TTFs, plus a Google-Fonts-submission zip bundle in `release/`. The current layout (root-level `build.sh`, `output/`, `release/`, `good/`, `data/`, `scripts/`) was organised for local dev convenience and does not match the layout Google Fonts requires for [upstream repositories](https://googlefonts.github.io/gf-guide/upstream.html). That guide mandates a `fonts/`, `sources/`, `documentation/` skeleton plus a fixed set of root-level files (`AUTHORS.txt`, `CONTRIBUTORS.txt`, `OFL.txt` with full SIL OFL 1.1 body, `README.md` with at least one image, `requirements.txt`, `.gitignore`) and a one-command build.

This plan restructures the repo in place to match that contract, treats both families as a single monorepo split per-family under `fonts/<Family>/` and `sources/<Family>/`, drops derived artefacts that are easy to regenerate, and rewires `build.sh` + tests so the build is functionally green at the end. Submitting each family to Google Fonts is then a matter of opening a PR against `google/fonts` referencing this upstream.

## Decisions (already confirmed)

- **Monorepo, split by family** — both families share root-level files; per-family content lives under `fonts/<Family>/` and `sources/<Family>/`.
- **Delete dev cruft and obsolete reference files** — `good/`, `misc/`, logs, `_tmp_inspect.py`, `data/FangZhengKaiTiPinYinZiKu-1.ttc`, `release/`, `output/`, `.pytest_cache/`, `scripts/old/`, `scripts/compare_fonts_output.txt`.
- **Drop `release/`** — built TTFs land in `fonts/<Family>/ttf/`; the zip bundle becomes a GitHub Release artifact (out of scope).
- **Write full OFL + AUTHORS + CONTRIBUTORS from scratch.**
- **Base Noto TTFs split per family**: `sources/Heiti/base-font/Noto*SC-*.ttf`, `sources/Songti/base-font/Noto*SC-*.ttf`.
- **Generate fresh per-family specimen images** for `documentation/`.
- **Rewire `build.sh` and `tests/conftest.py`** in the same pass so the build is green.

## Target layout

```
NanGuo-Fonts/
├── AUTHORS.txt                       (NEW)
├── CONTRIBUTORS.txt                  (NEW)
├── OFL.txt                           (REWRITE — copyright header + full SIL OFL 1.1)
├── README.md                         (REWRITE — overview + specimen image)
├── requirements.txt                  (NEW — build deps: fonttools, pypinyin)
├── requirements-test.txt             (KEEP — adds fontbakery, pytest)
├── .gitignore                        (KEEP)
├── build.sh                          (UPDATE — write to fonts/<Family>/ttf/)
├── config.json                       (KEEP — build tunables)
├── pytest.ini                        (KEEP)
├── CLAUDE.md, Backlog.md             (KEEP — project meta)
│
├── documentation/                    (NEW)
│   ├── specimen-heiti.png
│   ├── specimen-songti.png
│   └── image-license.txt
│
├── fonts/
│   ├── Heiti/
│   │   ├── ttf/                      (NanGuoHeitiPinyin-{1..6}{,-Bold}.ttf)
│   │   ├── DESCRIPTION.en_us.html
│   │   └── METADATA.pb
│   └── Songti/
│       ├── ttf/                      (NanGuoSongtiPinyin-{1..6}{,-Bold}.ttf)
│       ├── DESCRIPTION.en_us.html
│       └── METADATA.pb
│
├── sources/
│   ├── Heiti/base-font/              (NotoSansSC-Regular.ttf, NotoSansSC-Bold.ttf)
│   ├── Songti/base-font/             (NotoSerifSC-Regular.ttf, NotoSerifSC-Bold.ttf)
│   ├── data/                         (pinyin_map.json, heteronym_map.json, syllable_inventory.json, refdata_*.json)
│   ├── scripts/                      (make_pinyin_font_v2.py, bundle_ttc.py, build_variable.py, derive_pinyin_data*.py, extract_refdata.py, fix_post_table.py, update_ttf_year.py, compare_fonts.py)
│   └── FONTLOG.txt
│
├── tests/                            (KEEP — conftest.py path-update only)
└── requirements/                     (KEEP — internal design notes; not Google's `requirements.txt`)
```

## Step-by-step

### 1. Create new root files

- `OFL.txt` — line 1 `Copyright 2026 The NanGuo Pinyin Project Authors (https://catusf.github.io)`, line 2 blank, then full SIL Open Font License v1.1 body (PREAMBLE through TERMINATION).
- `AUTHORS.txt` — seed with `Catus Felis <phanmanhdan@gmail.com>` (1 line per author).
- `CONTRIBUTORS.txt` — empty placeholder with a leading comment explaining the file's purpose.
- `requirements.txt` — pinned build deps (`fonttools>=4.50`, `pypinyin>=0.51`).
- `README.md` — replace the 1-line stub: project description, 6-variant heteronym scheme summary, install + build instructions (`pip install -r requirements.txt && ./build.sh`), embedded `documentation/specimen-heiti.png`, links to both families, license note.

### 2. Build the new tree

Move + delete in a single pass:

| From | To |
|---|---|
| `data/NotoSansSC-Regular.ttf`, `NotoSansSC-Bold.ttf` | `sources/Heiti/base-font/` |
| `data/NotoSerifSC-Regular.ttf`, `NotoSerifSC-Bold.ttf` | `sources/Songti/base-font/` |
| `data/pinyin_map.json`, `heteronym_map.json`, `syllable_inventory.json`, `refdata_*.json` | `sources/data/` |
| `data/FONTLOG.txt` | `sources/FONTLOG.txt` |
| `scripts/*.py` (except `old/`) | `sources/scripts/` |
| `release/METADATA-Heiti-Fonts.pb` | `fonts/Heiti/METADATA.pb` |
| `release/METADATA-Songti-Fonts.pb` | `fonts/Songti/METADATA.pb` |
| `release/DESCRIPTION-Heiti.en_us.html` | `fonts/Heiti/DESCRIPTION.en_us.html` |
| `release/DESCRIPTION-Songti.en_us.html` | `fonts/Songti/DESCRIPTION.en_us.html` |
| `output/NanGuoHeitiPinyin-*.ttf` | `fonts/Heiti/ttf/` |
| `output/NanGuoSongtiPinyin-*.ttf` | `fonts/Songti/ttf/` |

Delete: `output/`, `release/`, `good/`, `misc/`, `data/FangZhengKaiTiPinYinZiKu-1.ttc`, `data/DESCRIPTION.en_us.html`, `data/METADATA.pb`, `data/OFL.txt` (replaced at root), `_tmp_inspect.py`, `build_sans_v2.log`, `test_run_v2.log`, `.pytest_cache/`, `scripts/old/`, `scripts/compare_fonts_output.txt`, `scripts/__pycache__/`. After moves complete, remove the now-empty `data/` and `scripts/` dirs.

### 3. Update `build.sh`

Critical changes to `build.sh:13-46`:

- `DATA="data"` → per-family base font paths: `sources/Heiti/base-font/NotoSansSC-{Regular,Bold}.ttf` and `sources/Songti/base-font/NotoSerifSC-{Regular,Bold}.ttf`.
- `python scripts/make_pinyin_font_v2.py` → `python sources/scripts/make_pinyin_font_v2.py`.
- `--out "$OUT"` (currently `output`) → `--out "fonts/Heiti/ttf"` for Heiti steps, `--out "fonts/Songti/ttf"` for Songti steps. Confirm `make_pinyin_font_v2.py` accepts the parent dir; if not, add a post-step move.
- Drop the `=== Bundling TTCs ===` and `=== Copying to release/ ===` blocks (release/ is gone, TTCs are not part of GF upstream — they remain available locally via `sources/scripts/bundle_ttc.py` if a contributor wants them).
- Keep the `=== Running tests ===` step at the end.

If any script in `sources/scripts/` resolves paths relative to its own location (e.g. via `pathlib.Path(__file__).parent`), audit and fix in the same pass — the move from `scripts/` → `sources/scripts/` adds one directory level.

### 4. Update `tests/conftest.py:17-18`

Current single-folder discovery:
```python
TTF_DIR = (ROOT / "output") if (ROOT / "output").is_dir() else ROOT
```
Replace with per-family discovery so tests can be parametrised by family. Minimum viable change: aggregate `fonts/Heiti/ttf/*.ttf` and `fonts/Songti/ttf/*.ttf` into the existing TTF set. Audit `tests/test_fontbakery.py:47` and `tests/test_variants.py` for any hard-coded `output/` or `release/` paths and update.

### 5. Rebuild `documentation/` specimens

After step 3 produces fresh TTFs, render one specimen PNG per family using the existing demo PDF pipeline that produced `samples/output/NanGuo_Demo_p1.png` — point it at the new `fonts/<Family>/ttf/` and save to `documentation/specimen-{heiti,songti}.png`. Add `documentation/image-license.txt` stating the specimen images are CC-BY-4.0 (or whatever you prefer — flag this for review at execution time).

### 6. Verify

Run, in order, and require each to pass before declaring done:

1. `./build.sh` — exits 0; `fonts/Heiti/ttf/` and `fonts/Songti/ttf/` each contain 12 TTFs.
2. `python tests/run_all.py` — pytest exits 0 (with the existing `xfail` markers for `name[2]` and `USE_TYPO_METRICS` still flagged in `CLAUDE.md`).
3. `find . -maxdepth 2 -type f` — confirm the target layout matches the table in §"Target layout" exactly (no stray `output/`, `release/`, `good/`, `misc/`, `_tmp_*`, log files).
4. Spot-check `fonts/Heiti/METADATA.pb` and `fonts/Songti/METADATA.pb` open cleanly (e.g. `python -c "from google.protobuf import text_format; ..."` or `gftools` if available) and that `filename:` entries match the actual TTFs in the sibling `ttf/` dir.
5. Sanity: `git status` shows only the intended moves/creates/deletes; no accidental binary churn in unrelated files.

## Critical files

- `/workspaces/NanGuo-Fonts/build.sh` — rewire paths
- `/workspaces/NanGuo-Fonts/tests/conftest.py` — rewire `TTF_DIR`
- `/workspaces/NanGuo-Fonts/scripts/make_packages.py` — currently reads `release/`; either delete or update for the new layout (this plan deletes it since `release/` is going away)
- `/workspaces/NanGuo-Fonts/scripts/make_pinyin_font_v2.py` — audit for any `pathlib.Path(__file__).parent`-relative data lookups
- `/workspaces/NanGuo-Fonts/release/METADATA-Heiti-Fonts.pb`, `release/METADATA-Songti-Fonts.pb` — verbatim move to `fonts/<Family>/METADATA.pb`
- `/workspaces/NanGuo-Fonts/release/DESCRIPTION-Heiti.en_us.html`, `release/DESCRIPTION-Songti.en_us.html` — verbatim move

## Out of scope

- Fixing the two known `xfail`s (`name[2]` and `USE_TYPO_METRICS` bit) — tracked in `CLAUDE.md`, separate task.
- Splitting into two independent upstream repos (deferred per user choice).
- Generating variable fonts under `fonts/<Family>/variable/` — current build is static-only; the empty `variable/` dir is omitted rather than committed empty.
- Opening the actual PRs against `google/fonts`.
- Authoring `documentation/article/`, social assets, or extended specimens.
