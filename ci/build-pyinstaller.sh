#!/bin/bash

set -x
set -e

cat <<EOF > galacteek_win.py
import sys
import faulthandler
print("Starting galacteek ..")

faulthandler.enable(sys.stdout)

from galacteek.guientrypoint import *
start()
EOF

export PYTHONPATH=$GITHUB_WORKSPACE

unset VIRTUAL_ENV

#python -m venv venvpyins
#./venvpyins/Scripts/activate.bat

pip install "pyinstaller==4.0"
pip install pywin32

# Patch pyimod03_importers.py (to include source code with inspect)
#cp packaging/windows/pyimod03_importers.py venvpyins/Lib/site-packages/PyInstaller/loader
#ls venvpyins/Lib/site-packages
cp packaging/windows/pyimod03_importers.py \
    c:\\hostedtoolcache\\windows\\python\\3.7.9\\x64\\lib\\site-packages\\PyInstaller\\loader

echo "Installing wheel from: $1"

pip install wheel
#pip install $1

echo "Running pyinstaller"

cp packaging/windows/galacteek.spec .
pyinstaller galacteek.spec

echo "Success, moving bundle"

mv dist/galacteek.exe $BUNDLE_PATH
