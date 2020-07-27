

all: resources.rcc

resources.rcc: resources.qrc icons/48x48/sampledrawer.png
	rcc -o "$@" --binary "$<"

icons/48x48/%.png: icons/scalable/%.svg
	mkdir -p icons/48x48
	convert -background none -geometry 48x48 "$<" "$@"
