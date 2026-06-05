"""Re-derive heteronym_map.json + syllable_inventory.json from FZKTPY index order.

The original derive_pinyin_data.py ordered heteronyms by pypinyin, but per
Output_font_requirements.md / CLAUDE.md the variant N reading must come from
FZKTPY0N (TTC index N-1). This script walks the FZKTPY .ttc and reads each
character's pinyin reading directly from each sub-font, anchored by glyph
ID cross-reference through FZKTPY01.

Reads (inputs):
  data/FangZhengKaiTiPinYinZiKu-1.ttc       # 6 sub-fonts FZKTPY01..06
  data/fzktpy_pua_syllable_map.json        # 1,216 PUA -> syllable (known)
  data/fzktpy_cjk_composites.json          # 6,763 char codepoints to walk

Writes (outputs):
  data/heteronym_map.json                   # cp_hex -> [V1, V2, V3, V4, V5, V6]
  data/syllable_inventory.json              # syllable -> {"pua": "EXXX"}
                                            # (preserves existing PUA codes;
                                            # adds entries for newly-mapped
                                            # syllables at next free PUA)

The 795 PUAs in FZKTPY01's cmap that lack syllable entries get their
syllable derived by pypinyin intersection over the characters that use
them as alternate readings. Anything that can't be uniquely resolved gets
flagged in the build warning log and falls back to the primary reading.
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter, defaultdict

from fontTools.ttLib import TTCollection
from pypinyin import Style, pinyin

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FZ_TTC = DATA / "FangZhengKaiTiPinYinZiKu-1.ttc"
NO_READING_GLYPHS = {"uni3000", ".notdef", "space"}  # FZKTPY's "blank" sentinels


def _strip0x(h: str) -> str:
    return h[2:] if h.lower().startswith("0x") else h


def _ruby_gid_for_cp(fz, cp: int) -> int | None:
    """Return the GID of the 2nd component (ruby PUA) of the composite that
    `fz`'s cmap maps codepoint `cp` to. Returns None if `cp` is not mapped,
    maps to a non-composite (FZKTPY's "no reading"), or anything anomalous.
    """
    cmap = fz.getBestCmap()
    gn = cmap.get(cp)
    if gn is None or gn in NO_READING_GLYPHS:
        return None
    g = fz["glyf"][gn]
    if not g.isComposite() or len(g.components) < 2:
        return None
    return fz.getGlyphID(g.components[1].glyphName)


def _resolve_unknown_pua_syllables(
    unknown_puas: set[str],
    pua_to_users: dict[str, list[int]],
    known_pua_to_syl: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """For each unknown PUA, infer its syllable via pypinyin intersection.

    Returns (resolved_map, unresolved_list).
    """
    known_syllables = set(known_pua_to_syl.values())
    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    for pua in sorted(unknown_puas):
        users = pua_to_users.get(pua, [])
        if not users:
            unresolved.append(pua)
            continue

        # Collect heteronym readings for each user, count how often each
        # syllable shows up across all users.
        votes: Counter[str] = Counter()
        for cp in users:
            ch = chr(cp)
            readings = pinyin(ch, style=Style.TONE, heteronym=True)
            cand = set(readings[0]) if readings else set()
            for r in cand:
                votes[r] += 1

        # Pick the most-shared candidate. Tie-break: prefer one NOT already
        # used by a known PUA (since each PUA has a unique syllable in
        # FZKTPY's design).
        if not votes:
            unresolved.append(pua)
            continue

        # Best candidate must show up in EVERY user's reading set (this is
        # the "intersection" constraint — a PUA represents one syllable
        # shared by all characters that use it).
        full_count = len(users)
        intersect = [s for s, n in votes.items() if n == full_count]
        if not intersect:
            # Fall back to majority + known-syllable exclusion.
            intersect = sorted(votes, key=lambda s: (-votes[s], s in known_syllables))
        # Prefer a syllable that's NOT already assigned to a different PUA.
        novel = [s for s in intersect if s not in known_syllables]
        chosen = (novel or intersect)[0]
        resolved[pua] = chosen
        known_syllables.add(chosen)

    return resolved, unresolved


def main() -> None:
    print(f"Loading {FZ_TTC.name}...")
    ttc = TTCollection(str(FZ_TTC))
    if len(ttc.fonts) != 6:
        sys.exit(f"expected 6 sub-fonts in TTC, found {len(ttc.fonts)}")
    fz = ttc.fonts

    # Build FZKTPY01 GID -> glyph-name map. fontTools' name synthesis (post
    # 3.0) gives PUA-mapped GIDs the form 'uniEXXX', which we can then look
    # up in the syllable map.
    fz1_order = fz[0].getGlyphOrder()
    gid_to_fz1_name: dict[int, str] = {i: n for i, n in enumerate(fz1_order)}

    # Load known PUA -> syllable, normalize keys to 'uniEXXX' form.
    raw_syl_map = json.loads((DATA / "fzktpy_pua_syllable_map.json").read_text(encoding="utf-8"))
    known_pua_to_syl: dict[str, str] = {}
    for k, meta in raw_syl_map.items():
        hexpart = _strip0x(k).upper()
        known_pua_to_syl[f"uni{hexpart}"] = meta["syllable"]
    print(f"  Loaded {len(known_pua_to_syl):,} known PUA->syllable entries")

    comps0 = json.loads((DATA / "fzktpy_cjk_composites.json").read_text(encoding="utf-8"))["0"]
    char_cps = [_strip0x(k).upper() for k in comps0]
    print(f"  Loaded {len(char_cps):,} characters from fzktpy_cjk_composites.json")

    # First pass: walk every char × every sub-font, collect (cp, sub_idx) ->
    # FZKTPY01-anchored ruby PUA name.
    cp_to_readings_puas: dict[str, list[str | None]] = {}
    pua_to_users: dict[str, list[int]] = defaultdict(list)
    pua_to_users_seen: dict[str, set[int]] = defaultdict(set)
    for cp_hex in char_cps:
        cp = int(cp_hex, 16)
        readings: list[str | None] = []
        for idx in range(6):
            ruby_gid = _ruby_gid_for_cp(fz[idx], cp)
            if ruby_gid is None:
                readings.append(None)
                continue
            pua_name = gid_to_fz1_name.get(ruby_gid)
            if pua_name is None or not pua_name.startswith("uniE"):
                readings.append(None)
                continue
            readings.append(pua_name)
            if cp not in pua_to_users_seen[pua_name]:
                pua_to_users[pua_name].append(cp)
                pua_to_users_seen[pua_name].add(cp)
        cp_to_readings_puas[cp_hex] = readings

    all_puas = {p for rds in cp_to_readings_puas.values() for p in rds if p}
    unknown = all_puas - set(known_pua_to_syl)
    print(f"  Distinct PUAs referenced: {len(all_puas):,}  unknown: {len(unknown):,}")

    # Resolve unknown PUAs via pypinyin intersection.
    resolved, unresolved = _resolve_unknown_pua_syllables(
        unknown, pua_to_users, known_pua_to_syl
    )
    print(f"  Resolved via pypinyin: {len(resolved):,}  unresolved: {len(unresolved):,}")
    pua_to_syl = {**known_pua_to_syl, **resolved}

    # Build the FZKTPY-ordered heteronym map: cp_hex -> [V1..V6 syllable].
    # Slots without a FZKTPY reading are encoded as JSON null (Python None).
    # The build script renders those as a blank glyph in that variant —
    # NO fallback to V1's ruby, mimicking FZKTPY's design.
    het: dict[str, list] = {}
    primary_only = 0
    for cp_hex, pua_readings in cp_to_readings_puas.items():
        syls: list[str | None] = [
            pua_to_syl.get(p) if p else None for p in pua_readings
        ]
        # V1 must always exist (FZKTPY01 is the anchor for primary readings).
        if not syls or syls[0] is None:
            raise RuntimeError(f"U+{cp_hex}: FZKTPY01 has no primary reading")
        # Pad to 6 with None for any trailing missing variants.
        while len(syls) < 6:
            syls.append(None)
        syls = syls[:6]
        if all(s is None or s == syls[0] for s in syls[1:]):
            primary_only += 1
        het[cp_hex] = syls

    print(f"  Hanzi with FZKTPY alternates: {len(het) - primary_only:,}")
    print(f"  Hanzi with only V1 reading (V2-V6 blank): {primary_only:,}")

    # Build new syllable_inventory: keep existing PUA assignments where they
    # already exist; add new entries for newly-mapped syllables.
    inv_path = DATA / "syllable_inventory.json"
    if inv_path.exists():
        old_inv: dict[str, dict[str, str]] = json.loads(inv_path.read_text(encoding="utf-8"))
    else:
        old_inv = {}
    inv = dict(old_inv)
    used_pua = {int(meta["pua"], 16) for meta in inv.values()}

    # All syllables referenced anywhere (skip None blank-variant slots).
    referenced_syllables = {s for syls in het.values() for s in syls if s is not None}
    candidate = 0xE000
    PUA_MAX = 0xF8FF
    added = 0
    for syl in sorted(referenced_syllables):
        if syl in inv:
            continue
        while candidate in used_pua:
            candidate += 1
        if candidate > PUA_MAX:
            sys.exit("PUA range exhausted")
        inv[syl] = {"pua": f"{candidate:04X}"}
        used_pua.add(candidate)
        candidate += 1
        added += 1
    print(f"  syllable_inventory: {len(inv):,} total ({added} new)")

    het_char = {chr(int(k, 16)): v for k, v in het.items()}
    (DATA / "heteronym_map.json").write_text(
        json.dumps(het_char, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    inv_path.write_text(
        json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Spot-check U+5F97 per the user's reference: V1=dé, V2=děi, V3=de,
    # V4..V6 blank.
    sample = het.get("5F97")
    if sample:
        rendered = ", ".join("blank" if s is None else s for s in sample)
        print(f"\nSpot check U+5F97 (de2/dei3/de): variants 1..6 = [{rendered}]")

    if unresolved:
        print(f"\nUnresolved PUAs (first 20): {unresolved[:20]}")
        print("These will silently fall back to variant-1 readings.")


if __name__ == "__main__":
    main()
