.PHONY: all fonts clean

all: fonts poem

fonts:
	cd sources && bash build.sh


clean:
	git clean -fdx
