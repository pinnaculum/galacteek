#!/bin/bash

set -x
set -e

cat <<EOF > galacteek_win.py
import sys
import faulthandler
print("Starting galacteek ..")

faulthandler.enable(sys.stdout)

from galacteek.guientrypoint import start
start()
EOF

export PYTHONPATH=$GITHUB_WORKSPACE

unset VIRTUAL_ENV

pip install "pyinstaller==4.0"
pip install pywin32

# Patch pyimod03_importers.py (to include source code with inspect)
cp packaging/windows/pyimod03_importers.py \
    c:\\hostedtoolcache\\windows\\python\\3.7.9\\x64\\lib\\site-packages\\PyInstaller\\loader

echo "Running pyinstaller"

cp packaging/windows/galacteek_folder.spec .
pyinstaller galacteek_folder.spec

echo "Success, packaging folder"

# We have a chance to remove extra bloat here

pushd "dist/galacteek"

find PyQt5/Qt/translations -type f -not -iname "*en*" -a -not -iname "*es*" \
	-a -not -iname "*fr*" -exec rm {} \;

find PyQt5/Qt/qml/ -name *.qml -exec rm {} \;
find PyQt5/Qt/qml/ -name *.qmlc -exec rm {} \;
find PyQt5/Qt/qml/QtQuick -exec rm {} \;

popd

cp packaging/windows/galacteek-installer.nsi .

echo "Running makensis"
makensis -V2 galacteek-installer.nsi

echo "Success, moving installer"

mv Galacteek-Installer.exe $BUNDLE_EXTRA_PATH
