.PHONY: all fonts clean

all: fonts

fonts:
	cd sources && bash build.sh

clean:
	git clean -fdx
