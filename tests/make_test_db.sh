#!/bin/bash -e

name="$1"

if [ -z "$1" ] ; then
	echo "Usage:" >&2
	echo "    $0 <fixture_name>" >&2
	exit 1
fi

tests_dir="$(dirname $(readlink -f $0))"
data_dir="$tests_dir/data"
dest_dir="$data_dir/$name"

if [ -e "$dest_dir" ] ; then
	echo "'$dest_dir' already exists!" >&2
	exit 1
fi

sampledrawer --data-dir "$dest_dir" --import "$data_dir/silence-1s.wav"
sampledrawer --data-dir "$dest_dir" --import "$data_dir/sine-440Hz-half_scale-1s.flac" --tag tag1
sampledrawer --data-dir "$dest_dir" --import "$data_dir/sine-440Hz-half_scale-1s.wav" --no-copy --tag tag1 --tag2
