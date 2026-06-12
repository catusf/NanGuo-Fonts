PYTHON   ?= python3
SOURCES  := sources
FONTS_H  := fonts/Heiti/ttf
FONTS_S  := fonts/Songti/ttf
TTC_H    := fonts/Heiti/ttc
TTC_S    := fonts/Songti/ttc

.PHONY: all fonts ligadata injectliga bundle samples tests clean

all: clean fonts ligadata injectliga bundle samples tests

# ── Build base TTF font files ────────────────────────────────────────────────
fonts:
	@echo "=== Building NanGuo Pinyin Fonts ==="
	cd $(SOURCES) && $(PYTHON) scripts/make_pinyin_font_v2.py \
	    --font Heiti/base-font/NotoSansSC-Regular.ttf \
	    --name "NanGuo Heiti Pinyin" --author "Catus Felis" \
	    --url "https://catusf.github.io" --out ../$(FONTS_H)
	cd $(SOURCES) && $(PYTHON) scripts/make_pinyin_font_v2.py \
	    --font Heiti/base-font/NotoSansSC-Bold.ttf \
	    --name "NanGuo Heiti Pinyin" --author "Catus Felis" \
	    --url "https://catusf.github.io" --out ../$(FONTS_H)
	cd $(SOURCES) && $(PYTHON) scripts/make_pinyin_font_v2.py \
	    --font Songti/base-font/NotoSerifSC-Regular.ttf \
	    --name "NanGuo Songti Pinyin" --author "Catus Felis" \
	    --url "https://catusf.github.io" --out ../$(FONTS_S)
	cd $(SOURCES) && $(PYTHON) scripts/make_pinyin_font_v2.py \
	    --font Songti/base-font/NotoSerifSC-Bold.ttf \
	    --name "NanGuo Songti Pinyin" --author "Catus Felis" \
	    --url "https://catusf.github.io" --out ../$(FONTS_S)
	cp OFL.txt $(FONTS_H)/OFL.txt
	cp OFL.txt $(FONTS_S)/OFL.txt

# ── Generate ligature data from HSK and CC-CEDICT ───────────────────────────
ligadata:
	@echo "=== Generating ligature data ==="
	cd $(SOURCES) && $(PYTHON) scripts/generate_hsk_ligatures.py \
	    --hsk       data/hsk_words.json \
	    --heteronym data/heteronym_map.json \
	    --output    data/hsk-ligatures.json
	cd $(SOURCES) && $(PYTHON) scripts/generate_cccedict_ligatures.py \
	    --heteronym data/heteronym_map.json \
	    --hsk       data/hsk_words.json \
	    --output    data/cccedict-ligatures.json
	cd $(SOURCES) && $(PYTHON) scripts/merge_ligatures.py \
	    --hsk      data/hsk-ligatures.json \
	    --cccedict data/cccedict-ligatures.json \
	    --output   data/all_ligatures.json

	cd $(SOURCES) && $(PYTHON) scripts/make_ligatures_md.py 

# ── Inject contextual reading ligatures into variant-1 fonts ─────────────────
injectliga:
	@echo "=== Injecting ligatures into variant-1 fonts ==="
	cd $(SOURCES) && for F in \
	    ../$(FONTS_H)/NanGuoHeitiPinyin-1.ttf \
	    ../$(FONTS_H)/NanGuoHeitiPinyin-1-Bold.ttf \
	    ../$(FONTS_S)/NanGuoSongtiPinyin-1.ttf \
	    ../$(FONTS_S)/NanGuoSongtiPinyin-1-Bold.ttf; do \
	    $(PYTHON) scripts/add_ligatures.py \
	        --font      "$$F" \
	        --combined  data/all_ligatures.json \
	        --syllables data/syllable_inventory.json; \
	done

# ── Bundle TTF variants into TTC collections ─────────────────────────────────
bundle:
	@echo "=== Bundling TTC collections ==="
	cd $(SOURCES) && $(PYTHON) scripts/bundle_ttc.py

# ── Build sample PDFs and PNG specimens ──────────────────────────────────────
samples:
	@echo "=== Building sample PDFs ==="
	cd $(SOURCES) && $(PYTHON) scripts/build_pdf.py
	@echo "=== Building specimen images ==="
	cd $(SOURCES) && $(PYTHON) scripts/build_specimen.py
	@echo "=== Building poem specimen ==="
	cd $(SOURCES) && $(PYTHON) scripts/build_poem_pdf.py

# ── Run test suite ────────────────────────────────────────────────────────────
tests:
	@echo "=== Running tests ==="
	$(PYTHON) tests/run_all.py

# ── Remove generated artifacts ────────────────────────────────────────────────
clean:
	rm -f $(FONTS_H)/*.ttf $(FONTS_S)/*.ttf
	rm -f $(TTC_H)/*.ttc  $(TTC_S)/*.ttc
	rm -f $(FONTS_H)/OFL.txt $(FONTS_S)/OFL.txt
	rm -f $(SOURCES)/data/hsk-ligatures.json \
	      $(SOURCES)/data/cccedict-ligatures.json \
	      $(SOURCES)/data/all_ligatures.json
	rm -f documentation/*.pdf documentation/*.png
