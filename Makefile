PYTHON   ?= python3
SOURCES  := sources
FONTS_H  := fonts/Heiti/ttf
FONTS_S  := fonts/Songti/ttf

.PHONY: all fonts samples tests clean

all: fonts samples tests

# ── Build TTF/TTC font files ─────────────────────────────────────────────────
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
	@echo "=== Adding contextual reading ligatures ==="
	cd $(SOURCES) && for F in \
	    ../$(FONTS_H)/NanGuoHeitiPinyin-1.ttf \
	    ../$(FONTS_H)/NanGuoHeitiPinyin-1-Bold.ttf \
	    ../$(FONTS_S)/NanGuoSongtiPinyin-1.ttf \
	    ../$(FONTS_S)/NanGuoSongtiPinyin-1-Bold.ttf; do \
	    $(PYTHON) scripts/add_ligatures.py \
	        --font "$$F" \
	        --combined data/duoyinzi_combined.json \
	        --syllables data/syllable_inventory.json; \
	done
	@echo "=== Bundling TTC collections ==="
	cd $(SOURCES) && $(PYTHON) scripts/bundle_ttc.py
	cp OFL.txt $(FONTS_H)/OFL.txt
	cp OFL.txt $(FONTS_S)/OFL.txt

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

clean:
	git clean -fdx
