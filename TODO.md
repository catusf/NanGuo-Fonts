
- [ ] Uses CCCE Dict entirely for ligatures data (skip HSK list)
- [ ] Redesign the reference PUA for pinyin glyphs: needs sources/data/heteronym_map.json or not?
- [ ] Remove build.sh
- [ ] Add code to download base fonts automatically

# Summary
Core goal: stop depending on heteronym_map.json (derived from the proprietary FZKTPY reference font) and use heteronym_map_new.json built from open data.

## Data pipeline cleanup

- derive_heteronym_map_v3.py — rewrites the character set source: instead of seeding from the old heteronym_map.json, it now enumerates all 6763 CJK characters directly from the GB2312 standard. Also drops the "last resort: keep V1 from existing map" fallback.
- heteronym_map_new.json — the rebuilt output of the above.
- syllable_inventory_new.json — fresh syllable→PUA mapping rebuilt alongside.
- pinyin_map_differences.json — deleted (comparison artifact, no longer needed).


## Reference migration across scripts

- make_pinyin_font_v2.py, generate_hsk_ligatures.py, generate_cccedict_ligatures.py, check_hsk_readings.py — all updated to read heteronym_map_new.json instead of heteronym_map.json.


## Dead code removal

- extract_fzktpy_data.py — deleted (extracted data from the proprietary FZKTPY font; no longer needed).
- derive_pinyin_data.py, derive_pinyin_data_v2.py — deleted (obsolete precursors to derive_heteronym_map_v3.py).
- build.sh — deleted (replaced by the Makefile).


## New additions

- make_ligatures_md.py (new) — generates ligatures_list.md from all_ligatures.json with the trilingual column headers.
- Makefile — adds the make_ligatures_md.py step to the ligadata target and ligatures_list.md to clean.
- hsk_3.0.csv (untracked) — new HSK 3.0 source data file.


## Rebuilt artifacts

Heiti and Songti TTC font collections and documentation PDFs/PNGs — regenerated with the new data.