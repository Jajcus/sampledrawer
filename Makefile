
ICONS = \
	audio-x-generic \
	folder \
	media-playback-pause \
	media-playback-start \
	media-playback-stop \
	sampledrawer \
	tag

SVG_ICONS = $(foreach icon,$(ICONS),icons/$(icon).svg)

all: sample_drawer/gui/resources.rcc

sample_drawer/gui/resources.rcc: resources.qrc $(SVG_ICONS)
	rcc -o "$@" --binary "$<"

icons/%.png: icons/%.svg
	convert -background none -geometry 48x48 "$<" "$@"
