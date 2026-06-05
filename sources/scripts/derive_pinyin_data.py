"""Derive the three JSONs that make_pinyin_font.py expects in data/.

Reads:
  data/fzktpy_cjk_composites.json     (sub-font 0 = primary reading per char)
  data/fzktpy_pua_syllable_map.json   (PUA hex -> syllable)

Writes:
  data/heteronym_map.json      cp_hex -> [primary, alt1, alt2, ...]
                               (primary anchored to FZKTPY; alts from pypinyin)
  data/syllable_inventory.json syllable -> {"pua": "EXXX"}
                               (FZKTPY assignments preserved; extras get fresh
                                PUAs in U+E000-U+F8FF)

Run: python scripts/derive_pinyin_data.py
"""
from __future__ import annotations

import json
import pathlib

from pypinyin import pinyin, Style

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PUA_MAX = 0xF8FF


def _strip0x(h: str) -> str:
    return h[2:] if h.startswith("0x") or h.startswith("0X") else h


def main() -> None:
    comps = json.loads(
        (DATA / "fzktpy_cjk_composites.json").read_text(encoding="utf-8"))
    syl_map = json.loads(
        (DATA / "fzktpy_pua_syllable_map.json").read_text(encoding="utf-8"))

    pua_to_syl: dict[str, str] = {
        _strip0x(k).upper(): v["syllable"] for k, v in syl_map.items()
    }

    primary: dict[str, str] = {}
    for cp_hex_pref, entry in comps["0"].items():
        cp_hex = _strip0x(cp_hex_pref).upper()
        pua_pref = entry.get("ruby_pua")
        if not pua_pref:
            continue
        syl = pua_to_syl.get(_strip0x(pua_pref).upper())
        if syl:
            primary[cp_hex] = syl

    het: dict[str, list[str]] = {}
    for cp_hex, prim_syl in primary.items():
        ch = chr(int(cp_hex, 16))
        readings = pinyin(ch, style=Style.TONE, heteronym=True)
        candidates = readings[0] if readings else [prim_syl]
        ordered = [prim_syl]
        seen = {prim_syl}
        for r in candidates:
            if r and r not in seen:
                ordered.append(r)
                seen.add(r)
        if len(ordered) > 1:
            het[ch] = ordered[:6]

    inv: dict[str, dict[str, str]] = {
        syl: {"pua": pua_hex} for pua_hex, syl in pua_to_syl.items()
    }

    used: set[int] = {int(v["pua"], 16) for v in inv.values()}
    extras = sorted({s for readings in het.values()
                       for s in readings if s not in inv})
    candidate = 0xE000
    for syl in extras:
        while candidate in used:
            candidate += 1
        if candidate > PUA_MAX:
            raise RuntimeError("BMP PUA range exhausted")
        inv[syl] = {"pua": f"{candidate:04X}"}
        used.add(candidate)
        candidate += 1

    (DATA / "heteronym_map.json").write_text(
        json.dumps(het, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "syllable_inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"heteronym_map:      {len(het):,} polyphones")
    print(f"syllable_inventory: {len(inv):,} syllables "
          f"({len(extras)} added beyond FZKTPY)")


if __name__ == "__main__":
    main()
