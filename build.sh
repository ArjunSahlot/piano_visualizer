#!/bin/bash

download_link=https://github.com/ArjunSahlot/piano_visualizer/archive/main.zip
temporary_dir=$(mktemp -d)
echo "Checking if curl is installed"
if [ $(dpkg-query -W -f='${Status}' curl3 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo -e "\033[0;31mcurl is not installed\033[0m"
  echo "Installing curl..."
  sudo apt install -y curl;
  echo -e "\033[0;32mcurl was successfully installed\033[0m"
else
  echo -e "\033[0;32mcurl is already installed\033[0m"
fi
curl -LO $download_link \
&& unzip -d $temporary_dir main.zip \
&& rm -rf main.zip \
&& mv $temporary_dir/piano_visualizer-main $1/piano_visualizer \
&& rm -rf $temporary_dir
echo -e "\033[0;32mSuccessfully downloaded to $1/piano_visualizer\033[0m"
echo "Checking if pip is installed"
if [ $(dpkg-query -W -f='${Status}' pip3 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo -e "\033[0;31mpip is not installed\033[0m"
  echo "Installing pip..."
  sudo apt install -y python3-pip;
  echo -e "\033[0;32mpip was successfully installed\033[0m"
else
  echo -e "\033[0;32mpip is already installed\033[0m"
fi
echo "Installing requirements"
cd $1/piano_visualizer
pip3 install -r requirements.txt
echo "\033[0;32mDone!\033[0m"
