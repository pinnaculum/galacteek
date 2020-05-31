#!/bin/bash

sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo add-apt-repository -y ppa:longsleep/golang-backports

sudo apt-get update
sudo apt-get install -y python3.7 python3.7-venv python3.7-dev python3-pip
sudo apt-get install -y dzen2 libxkbcommon-x11-0 xvfb herbstluftwm libzbar0
sudo apt-get install -y libpulse-mainloop-glib0 libpulse0

sudo apt-get remove -y golang-1.11-go

sudo apt install golang-1.14

python3.7 -m pip install pip
