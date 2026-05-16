#!/usr/bin/env python3
"""
make_pinyin_font.py — NanGuo Pinyin Font Builder Skill v2
=========================================================
Converts any CJK TTF font into a 6-variant Hanyu Pinyin ruby font.

Usage:
    python3 make_pinyin_font.py \\
        --font   NotoSansSC-Regular.ttf \\
        --name   "NanGuo Sans Pinyin" \\
        --author "Catus Felis" \\
        --url    https://catusf.github.io \\
        --out    ./output/

    # With FZKTPY KaiTi-style PUA glyphs:
    python3 make_pinyin_font.py \\
        --font       NotoSerifSC-Regular.ttf \\
        --name       "NanGuo Serif Pinyin" \\
        --pua-source FangZhengKaiTiPinYinZiKu-1.ttc \\
        --out        ./output/
"""
import argparse, json, os, re, sys, textwrap, tempfile
from pathlib import Path

from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib.tables._g_l_y_f import (
    Glyph, GlyphComponent, ROUND_XY_TO_GRID, ARGS_ARE_XY_VALUES)
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._n_a_m_e import NameRecord

SKILL_DIR  = Path(__file__).parent
DATA_DIR   = SKILL_DIR.parent / "data"
COMP_FLAGS = ROUND_XY_TO_GRID | ARGS_ARE_XY_VALUES   # 0x0006

# Geometry constants (FZKTPY-derived, scaled to any UPM)
RUBY_Y_F     = 0.852   # ruby baseline / UPM
RUBY_EM_F    = 0.320   # ruby zone height / UPM
ASCENT_F     = 1.400   # usWinAscent / UPM
REF_ASC_1000 = 833     # yMax of 'ǎ' at UPM=1000 (consistent scale reference)
MAX_OVFL_F   = 1.15    # allow 15% overflow for long syllables
# FZKTPY source geometry
FZ_UPM       = 256
FZ_CJK_ADV   = 256
FZ_RUBY_YMIN = 218
FZ_RUBY_H    = 90


# ── helpers ──────────────────────────────────────────────────────────────────

def _cmap12(font):
    for t in font['cmap'].tables:
        if t.platformID == 3 and t.format == 12:
            return t.cmap
    return {}

def _cmap4(font):
    for t in font['cmap'].tables:
        if t.platformID == 3 and t.platEncID == 1 and t.format == 4:
            return t.cmap
    return {}

def _set_name(tbl, nid, val, plat=3, enc=1, lang=0x0409):
    tbl.names = [r for r in tbl.names
                 if not (r.nameID == nid and r.platformID == plat)]
    rec = NameRecord()
    rec.nameID = nid; rec.platformID = plat
    rec.platEncID = enc; rec.langID = lang
    rec.string = val.encode('utf-16-be')
    tbl.names.append(rec)

def _make_comp(base_name, ruby_name):
    g = Glyph(); g.numberOfContours = -1
    c1 = GlyphComponent()
    c1.glyphName = base_name; c1.flags = COMP_FLAGS; c1.x = 0; c1.y = 0
    c2 = GlyphComponent()
    c2.glyphName = ruby_name; c2.flags = COMP_FLAGS; c2.x = 0; c2.y = 0
    g.components = [c1, c2]; return g


# ── Phase 1: detect font metrics ─────────────────────────────────────────────

def detect_metrics(font):
    upm     = font['head'].unitsPerEm
    ruby_y  = int(upm * RUBY_Y_F)
    ruby_em = int(upm * RUBY_EM_F)
    ascent  = int(upm * ASCENT_F)
    sTypo   = font['OS/2'].sTypoAscender
    cm12    = _cmap12(font)
    cjk_adv = upm
    for cp in [0x4E00, 0x4E2D, 0x5927]:
        gn = cm12.get(cp)
        if gn:
            cjk_adv = font['hmtx'].metrics[gn][0]; break
    return dict(upm=upm, ruby_y=ruby_y, ruby_em=ruby_em,
                ascent=ascent, sTypo=sTypo, cjk_adv=cjk_adv)


# ── Phase 2A: compose PUA glyph from base font's Latin ───────────────────────

def _compose(font, syllable, m):
    cmap  = font['cmap'].getBestCmap()
    glyf  = font['glyf']
    hmtx  = font['hmtx']
    info  = []
    for ch in syllable:
        gn = cmap.get(ord(ch))
        if not gn: return None
        g  = glyf[gn]
        adv = hmtx.metrics.get(gn, (m['cjk_adv'], 0))[0]
        if g.numberOfContours and g.numberOfContours > 0:
            g.recalcBounds(glyf)
            info.append((gn, g.xMin, g.yMin, g.xMax, g.yMax, adv))
        else:
            info.append((gn, 0, 0, 0, 0, adv))
    ref = int(REF_ASC_1000 * m['upm'] / 1000)
    scale_h   = m['ruby_em'] / ref
    total_adv = sum(a for *_, a in info)
    scale_w   = m['cjk_adv'] * MAX_OVFL_F / total_adv if total_adv else scale_h
    scale     = min(scale_h, scale_w)
    x         = (m['cjk_adv'] - total_adv * scale) / 2
    pen       = TTGlyphPen(None)
    for gn, xMin, yMin, xMax, yMax, adv in info:
        g = glyf[gn]
        if g.numberOfContours and g.numberOfContours > 0:
            g.draw(TransformPen(pen, (scale,0,0,scale, x, m['ruby_y'])), glyf)
        x += adv * scale
    try:   return pen.glyph(), m['cjk_adv']
    except: return None


# ── Phase 2B: extract PUA glyphs from FZKTPY ─────────────────────────────────

def _extract_fzktpy(fzktpy_path, m):
    fz   = TTCollection(fzktpy_path).fonts[0]
    fzcm = next(t for t in fz['cmap'].tables
                if t.platformID==3 and t.platEncID==1)
    fzgl = fz['glyf']
    sx   = m['cjk_adv'] / FZ_CJK_ADV
    sy   = m['ruby_em']  / FZ_RUBY_H
    ty   = m['ruby_y']   - FZ_RUBY_YMIN * sy
    out  = {}
    for cp, gn in fzcm.cmap.items():
        if not (0xE000 <= cp <= 0xF8FF): continue
        g = fzgl.get(gn)
        if g is None or g.numberOfContours == 0: continue
        pen = TTGlyphPen(None)
        try:
            if g.numberOfContours == -1:
                for comp in g.components:
                    cg = fzgl.get(comp.glyphName)
                    if cg and cg.numberOfContours and cg.numberOfContours > 0:
                        cg.draw(TransformPen(pen, (sx,0,0,sy, 0,ty)), fzgl)
            else:
                g.draw(TransformPen(pen, (sx,0,0,sy, 0,ty)), fzgl)
            out[f"uni{cp:04X}"] = (pen.glyph(), m['cjk_adv'])
        except: pass
    print(f"  Extracted {len(out):,} PUA glyphs from FZKTPY")
    return out


# ── Phase 2: inject PUA glyphs, save → return path ───────────────────────────

def phase2_pua(font_path, inv, m, fzktpy_path=""):
    print("[2] Generating PUA glyphs...")
    font  = TTFont(font_path)
    glyf  = font['glyf']
    hmtx  = font['hmtx']

    # Load FZKTPY PUA glyphs + mapping (optional)
    fz_glyphs = {}; fz_syl_map = {}
    if fzktpy_path:
        fz_glyphs = _extract_fzktpy(fzktpy_path, m)
        mf = DATA_DIR / "fzktpy_pua_syllable_map.json"
        if mf.exists():
            raw = json.loads(mf.read_text(encoding='utf-8'))
            for pua_key, meta in raw.items():
                pua_hex = pua_key[2:] if pua_key.lower().startswith("0x") else pua_key
                gn = f"uni{pua_hex.upper()}"
                if gn in fz_glyphs:
                    fz_syl_map[meta["syllable"]] = gn

    new_names = []; syl_to_pua = {}; failed = []
    total = len(inv); dot = max(1, total//20)

    for i, (syl, meta) in enumerate(inv.items()):
        if i % dot == 0: print(f"  [{i/total*100:3.0f}%]", end='\r')
        gname = f"uni{meta['pua']}"
        pua_cp = int(meta['pua'], 16)
        result = None
        # Try FZKTPY first
        if syl in fz_syl_map:
            result = fz_glyphs.get(fz_syl_map[syl])
        # Fallback: compose from base Latin
        if result is None:
            result = _compose(font, syl, m)
        if result is None:
            failed.append(syl); continue
        go, aw = result
        try: go.recalcBounds(glyf); lsb = go.xMin
        except: lsb = 0
        glyf[gname] = go; hmtx.metrics[gname] = (aw, lsb)
        new_names.append(gname); syl_to_pua[syl] = gname
        # Add to cmap4
        cm4 = _cmap4(font)
        if cm4 is not None: cm4[pua_cp] = gname

    print(f"  [100%] {len(new_names)} built, {len(failed)} failed")
    # Add to cmap4 if not present
    if not any(t.platformID==3 and t.platEncID==1 and t.format==4
               for t in font['cmap'].tables):
        t4 = CmapSubtable.newSubtable(4)
        t4.platformID=3; t4.platEncID=1; t4.language=0; t4.cmap={}
        font['cmap'].tables.append(t4)
    cm4 = _cmap4(font)
    for syl, gn in syl_to_pua.items():
        cm4[int(inv[syl]['pua'],16)] = gn

    # Sync glyf internal order (glyf.__setitem__ auto-updates font.getGlyphOrder)
    font['glyf'].glyphOrder = font.getGlyphOrder()
    font['maxp'].numGlyphs  = len(font.getGlyphOrder())

    # Update ascent
    font['OS/2'].usWinAscent   = m['ascent']
    font['hhea'].ascent        = m['ascent']

    # Force post format 2 so glyph names are preserved on reload
    from fontTools.ttLib.tables._p_o_s_t import table__p_o_s_t as PostTable
    from fontTools.misc.psCharStrings import SimpleT2Decompiler
    post = font['post']
    post.formatType = 2.0
    if not hasattr(post, 'extraNames'): post.extraNames = []
    if not hasattr(post, 'mapping'):    post.mapping = {}

    tmp = tempfile.mktemp(suffix="_pua.ttf")
    font.save(tmp)
    print(f"  Saved phase-2 font ({os.path.getsize(tmp)/1e6:.1f}MB)")

    # Save syl_to_pua map as json for phase 3
    syl_map_path = tempfile.mktemp(suffix="_sylmap.json")
    Path(syl_map_path).write_text(json.dumps(syl_to_pua), encoding='utf-8')
    return tmp, syl_map_path


# ── Phase 3: build composite CJK glyphs, save → return path ─────────────────

def phase3_composites(font_path, syl_map_path, pmap, het, m):
    print("[3] Building CJK composite glyphs...")
    font   = TTFont(font_path)
    glyf   = font['glyf']
    hmtx   = font['hmtx']
    cm12   = _cmap12(font)
    syl_to_pua = json.loads(Path(syl_map_path).read_text(encoding='utf-8'))

    # Track which names are already in the font
    existing = set(font.getGlyphOrder())

    base_glyphs  = {}   # base_comp_name → Glyph (copy of original)
    base_metrics = {}
    comp_glyphs  = {}   # variant_name → Glyph (composite)
    comp_metrics = {}
    variant_map  = {}   # cp_hex → [gname_v1..v6]
    # glyph name → base_comp name (for primary composite in-place update)
    primary_updates = {}   # orig_name → (base_comp_name, pua_name)

    total=len(pmap); dot=max(1,total//20)
    seen_base = {}   # orig_name → base_comp_name (to handle shared glyphs)

    for idx, (cp_hex, prim_syl) in enumerate(pmap.items()):
        if idx % dot == 0: print(f"  [{idx/total*100:3.0f}%]", end='\r')
        cp   = int(cp_hex, 16)
        orig = cm12.get(cp)
        if not orig: continue

        g_orig = glyf.get(orig)
        if g_orig is None: continue

        # Determine base component name
        if orig in seen_base:
            base_comp = seen_base[orig]
        else:
            base_comp = orig + ".base"
            # Avoid conflict with existing glyphs
            if base_comp in existing:
                base_comp = orig + ".pynbase"
            seen_base[orig] = base_comp

            if base_comp not in base_glyphs and base_comp not in existing:
                import copy
                base_glyphs[base_comp]  = copy.deepcopy(g_orig)
                base_metrics[base_comp] = hmtx.metrics.get(orig,(m['cjk_adv'],0))

        # Build variant composites for all readings
        all_r    = het.get(cp_hex, [prim_syl])[:6]
        variants = []

        for k, syl in enumerate(all_r):
            pua_name = syl_to_pua.get(syl)
            if pua_name is None:
                variants.append(base_comp); continue

            if k == 0:
                # Primary: replace orig in-place (tracked separately)
                primary_updates[orig] = (base_comp, pua_name)
                variants.append(orig)
            else:
                vname = f"{orig}.v{k+1}"
                if vname not in comp_glyphs and vname not in existing:
                    comp_glyphs[vname]  = _make_comp(base_comp, pua_name)
                    aw = hmtx.metrics.get(orig,(m['cjk_adv'],0))[0]
                    comp_metrics[vname] = (aw, 0)
                variants.append(vname)

        while len(variants) < 6: variants.append(base_comp)
        variant_map[cp_hex] = variants

    print(f"  [100%] {len(variant_map):,} entries")
    print(f"  base glyphs={len(base_glyphs)}  variants={len(comp_glyphs)}  "
          f"primary updates={len(primary_updates)}")

    # Commit: add base + variant glyphs (auto-updates font.getGlyphOrder)
    for gn, g in {**base_glyphs, **comp_glyphs}.items():
        glyf[gn] = g
    for gn, met in {**base_metrics, **comp_metrics}.items():
        hmtx.metrics[gn] = met

    # Apply primary composites in-place (already in glyph order, no new entry)
    for orig_name, (base_comp, pua_name) in primary_updates.items():
        glyf[orig_name] = _make_comp(base_comp, pua_name)

    # Sync glyf internal order
    font['glyf'].glyphOrder = font.getGlyphOrder()
    font['maxp'].numGlyphs  = len(font.getGlyphOrder())

    # Force post format 2 so glyph names are preserved on reload
    post = font['post']
    post.formatType = 2.0
    if not hasattr(post, 'extraNames'): post.extraNames = []
    if not hasattr(post, 'mapping'):    post.mapping = {}

    tmp = tempfile.mktemp(suffix="_comp.ttf")
    font.save(tmp)
    print(f"  Saved phase-3 font ({os.path.getsize(tmp)/1e6:.1f}MB)")

    # Save variant_map
    vm_path = tempfile.mktemp(suffix="_varmap.json")
    Path(vm_path).write_text(json.dumps(variant_map), encoding='utf-8')
    return tmp, vm_path


# ── Phase 4: build 6 sub-font TTFs ───────────────────────────────────────────

def phase4_variants(font_path, vm_path, cfg_dict, m, out_dir):
    print("[4] Exporting 6 sub-font TTFs...")
    variant_map = json.loads(Path(vm_path).read_text(encoding='utf-8'))
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)

    COPYRIGHT = (
        f"Copyright {cfg_dict['year']} The {cfg_dict['name']} Project Authors "
        f"({cfg_dict['url']}). "
        "Font data derived from Noto CJK fonts, Copyright 2014-2021 Google LLC."
    )
    LIC_DESC = ("This Font Software is licensed under the SIL Open Font "
                "License, Version 1.1. Available at: https://scripts.sil.org/OFL")

    for k in range(6):
        font = TTFont(font_path)   # fresh load per variant
        cm12 = _cmap12(font)

        # Remap cmap
        for t in font['cmap'].tables:
            if not hasattr(t,'cmap') or not t.cmap: continue
            for cp_hex, variants in variant_map.items():
                cp = int(cp_hex, 16)
                if cp in t.cmap:
                    t.cmap[cp] = variants[k]

        # Metrics & flags
        font['OS/2'].usWinAscent   = m['ascent']
        font['OS/2'].sTypoAscender = m['sTypo']
        font['hhea'].ascent        = m['ascent']
        font['OS/2'].fsSelection  &= ~0x80   # USE_TYPO=OFF

        # Mac Roman cmap
        if not any(t.platformID==1 for t in font['cmap'].tables):
            best4 = _cmap4(font)
            mac4  = CmapSubtable.newSubtable(4)
            mac4.platformID=1; mac4.platEncID=0; mac4.language=0
            mac4.cmap = {cp:gn for cp,gn in best4.items() if 0x20<=cp<=0x01FF}
            font['cmap'].tables.append(mac4)

        # Names
        n      = k + 1
        nm     = cfg_dict['name']
        ps_pfx = cfg_dict['ps_prefix']
        family = f"{nm} {n}"; ps = f"{ps_pfx}-{n}"
        tbl    = font['name']
        for nid, val in [
            (0, COPYRIGHT), (1, family), (2, "Regular"),
            (3, f"{ps}:2025"), (4, family+" Regular"), (5, "Version 1.000"),
            (6, ps), (7, nm), (8, cfg_dict['author']),
            (9, cfg_dict['author']), (11, cfg_dict['url']), (12, cfg_dict['url']),
            (13, LIC_DESC), (14, "https://scripts.sil.org/OFL"),
            (16, family), (17, "Regular"),
        ]:
            _set_name(tbl, nid, val)
        tbl.names = [r for r in tbl.names
                     if r.platformID!=1 or r.nameID not in (1,4,6)]
        for nid, val in [(1,family),(4,family+" Regular"),(6,ps)]:
            r=NameRecord(); r.nameID=nid; r.platformID=1
            r.platEncID=0; r.langID=0
            try: r.string=val.encode('latin-1',errors='replace')
            except: r.string=val.encode('utf-8')
            tbl.names.append(r)

        # Final variant: switch post to format 3.0 — format 2.0 with the
        # build's uniXXXX.base glyph names trips DirectWrite's AGL validation
        # and breaks rendering in Word/PowerPoint. See tests/test_post_table.py.
        font['post'].formatType = 3.0

        fname = out / f"{ps_pfx}-{n}.ttf"
        font.save(str(fname))
        print(f"  [{n}] {fname.name}  {fname.stat().st_size/1e6:.1f}MB")

    _write_metadata(cfg_dict, out)
    _write_ofl(cfg_dict, out)
    _write_description(cfg_dict, out)
    print(f"  Metadata written -> {out}")


# ── Metadata ──────────────────────────────────────────────────────────────────

def _write_metadata(cfg, out):
    nm = cfg['name']; ps = cfg['ps_prefix']; yr = cfg['year']
    auth = cfg['author']
    lines = [f'name: "{nm}"', f'designer: "{auth}"',
             'license: "OFL"', 'category: "SANS_SERIF"',
             f'date_added: "{yr}-01-01"']
    for k in range(1,7):
        lines += ['fonts {', f'  name: "{nm} {k}"', '  style: "normal"',
                  '  weight: 400', f'  filename: "{ps}-{k}.ttf"',
                  f'  post_script_name: "{ps}-{k}"',
                  f'  full_name: "{nm} {k} Regular"',
                  f'  copyright: "Copyright {yr} {auth}"', '}']
    lines += ['subsets: "chinese-simplified"','subsets: "latin"','subsets: "latin-ext"']
    (Path(out)/"METADATA.pb").write_text('\n'.join(lines)+'\n', encoding='utf-8')

def _write_ofl(cfg, out):
    (Path(out)/"OFL.txt").write_text(textwrap.dedent(f"""\
        Copyright {cfg['year']} The {cfg['name']} Project Authors ({cfg['url']})
        Font data derived from Noto CJK fonts, Copyright 2014-2021 Google LLC.

        This Font Software is licensed under the SIL Open Font License, Version 1.1.
        http://scripts.sil.org/OFL
    """), encoding='utf-8')

def _write_description(cfg, out):
    (Path(out)/"DESCRIPTION.en_us.html").write_text(textwrap.dedent(f"""\
        <p>{cfg['name']} is a Simplified Chinese educational typeface that embeds
        Hanyu Pinyin pronunciation guides directly above each character as
        font-native ruby text — no HTML markup required. Based on Noto CJK.</p>
        <p>Six variants (1–6) show successive pronunciation readings for
        multi-pronunciation characters (多音字). Characters with only one reading
        show that reading in all variants; characters with no further reading in
        higher-numbered variants render as plain characters without annotation.</p>
    """), encoding='utf-8')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--font',       required=True)
    p.add_argument('--name',       default="NanGuo Pinyin")
    p.add_argument('--author',     default="Unknown")
    p.add_argument('--url',        default="")
    p.add_argument('--out',        default="./output")
    p.add_argument('--pua-source', default="")
    p.add_argument('--year',       default="2026")
    a = p.parse_args()

    ps_prefix = re.sub(r'[^A-Za-z0-9]', '', a.name)
    cfg = dict(name=a.name, author=a.author, url=a.url,
               ps_prefix=ps_prefix, year=a.year)

    print(f"\n{'='*58}")
    print(f" {a.name} Font Builder")
    print(f"{'='*58}")

    # Detect metrics from base font
    print("[1] Detecting font metrics...")
    m = detect_metrics(TTFont(a.font))
    print(f"  UPM={m['upm']}  CJK_ADV={m['cjk_adv']}  "
          f"ruby_y={m['ruby_y']}  ruby_em={m['ruby_em']}  "
          f"ascent={m['ascent']}")

    # Load pinyin data
    with open(DATA_DIR/"pinyin_map.json",        encoding='utf-8') as f: pmap=json.load(f)
    with open(DATA_DIR/"heteronym_map.json",     encoding='utf-8') as f: het=json.load(f)
    with open(DATA_DIR/"syllable_inventory.json",encoding='utf-8') as f: inv=json.load(f)
    print(f"  {len(pmap):,} chars · {len(inv):,} syllables · {len(het):,} polyphones")

    # Phase 2: PUA glyphs
    p2_path, syl_map = phase2_pua(a.font, inv, m, a.pua_source)

    # Phase 3: composites
    p3_path, vm_path = phase3_composites(p2_path, syl_map, pmap, het, m)

    # Phase 4: 6 sub-fonts
    phase4_variants(p3_path, vm_path, cfg, m, a.out)

    # Cleanup temps
    for f in [p2_path, p3_path, syl_map, vm_path]:
        try: os.unlink(f)
        except: pass

    print(f"\nDone -- {a.out}/")
    print(f"  {ps_prefix}-1.ttf  ..  {ps_prefix}-6.ttf")


if __name__ == '__main__':
    main()
