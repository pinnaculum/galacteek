#!/bin/bash

set -x
set -e

export PYTHONPATH=$GITHUB_WORKSPACE

unset VIRTUAL_ENV

pip install -U pip
# pip install "pyinstaller==4.2"
pip install "pyinstaller==4.10"
pip install pywin32

# Patch pyimod03_importers.py (to include source code with inspect)
cp packaging/windows/pyinstaller4.10/pyimod03_importers.py \
    c:\\hostedtoolcache\\windows\\python\\3.7.9\\x64\\lib\\site-packages\\PyInstaller\\loader

# Copy tor and the dlls
cp -r /c/ProgramData/chocolatey/lib/tor/tools/Tor/*  packaging/windows/tor

cp packaging/windows/galacteek_win.py .
cp packaging/windows/galacteek_folder.spec .

# Custom mgc
wget -O packaging/windows/magic.mgc \
    https://gitlab.com/galacteek/file/-/releases/continuous-galacteek/downloads/magic.mgc

echo "Running pyinstaller"

pyinstaller galacteek_folder.spec

echo "Success, packaging folder"

# We have a chance to remove extra bloat here

# pushd "dist/galacteek"
# find PyQt5/Qt/translations -type f -not -iname "*en*" -a -not -iname "*es*" \
# 	-a -not -iname "*fr*" -exec rm {} \;

# find PyQt5/Qt/qml/ -name *.qml -exec rm {} \;
# find PyQt5/Qt/qml/ -name *.qmlc -exec rm {} \;
# find PyQt5/Qt/qml/QtQuick -exec rm {} \;
# popd

cp packaging/windows/galacteek-installer.nsi .

echo "Running makensis"
makensis -V2 galacteek-installer.nsi

echo "Success, moving installer"

mv Galacteek-Installer.exe $BUNDLE_PATH
