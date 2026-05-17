.PHONY: all fonts poem clean

all: fonts poem

fonts:
	cd sources && bash build.sh

poem:
	python3 sources/scripts/build_poem_pdf.py
	cp samples/output/NanGuo_Poem_XiangSi.pdf documentation/
	cp samples/output/NanGuo_Poem_XiangSi.png documentation/

clean:
	git clean -fdx
