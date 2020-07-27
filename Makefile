
ICONS = \
	audio-x-generic \
	folder \
	media-playback-pause \
	media-playback-start \
	media-playback-stop \
	sampledrawer \
	tag

PNG_ICONS = $(foreach icon,$(ICONS),icons/48x48/$(icon).png)

all: resources.rcc

resources.rcc: resources.qrc $(PNG_ICONS)
	rcc -o "$@" --binary "$<"

icons/48x48/%.png: icons/scalable/%.svg
	mkdir -p icons/48x48
	convert -background none -geometry 48x48 "$<" "$@"
