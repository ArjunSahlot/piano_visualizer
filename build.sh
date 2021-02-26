#!/bin/bash

download_link=https://github.com/ArjunSahlot/piano_visualizer/archive/main.zip
temporary_dir=$(mktemp -d) \
&& curl -LO $download_link \
&& unzip -d $temporary_dir main.zip \
&& rm -rf main.zip \
&& mv $temporary_dir/piano_visualizer-main $1/piano_visualizer \
&& rm -rf $temporary_dir
echo -e "[0;32mSuccessfully downloaded to $1/piano_visualizer[0m"
