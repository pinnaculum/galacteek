#!/bin/bash

sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.7 python3.7-venv python3.7-dev python3-pip
sudo apt-get install -y xvfb herbstluftwm libzbar0

python3.7 -m pip install pip
