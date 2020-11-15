#!/bin/bash

set -x
set -e

cat <<EOF > galacteek_win.py
import sys
import faulthandler
print("Starting galacteek ..")

sys.argv.append('-d')
faulthandler.enable(sys.stdout)

from galacteek.guientrypoint import start
start()
EOF

export PYTHONPATH=$GITHUB_WORKSPACE

unset VIRTUAL_ENV

#python -m venv venvp
#./venvp/Scripts/activate.bat

pip install "pyinstaller==4.0"
pip install pywin32

# Patch pyimod03_importers.py (to include source code with inspect)
cp packaging/windows/pyimod03_importers.py \
    c:\\hostedtoolcache\\windows\\python\\3.7.9\\x64\\lib\\site-packages\\PyInstaller\\loader

#echo "Installing wheel from: $1"
#pip install wheel
#pip install $1

# Remove unnecessary stuff
pushd "venvg/Lib/site-packages"

rm -rf Cryptodome/SelfTest/*
rm -rf PyQt5/Qt/plugins/geoservices
rm -rf PyQt5/Qt/plugins/sceneparsers
rm -rf pyzbar/tests
rm -rf turtledemo
rm -rf tkinter
rm -rf lib2to3
rm -rf idlelib
rm -rf git/test
rm -rf ensurepip
rm -rf {setuptools,pip}

#find PyQt5/Qt/translations -type f -not -iname "*en*" -a -not -iname "*es*" \
#	-a -not -iname "*fr*" -exec rm {} \;

#rm -rf PyQt5/Qt/plugins/sqldrivers
#rm -rf PyQt5/Qt/lib/libQt5XmlPatterns*
#rm -rf PyQt5/Qt/lib/libQt5Designer*
#find PyQt5/Qt/qml/ -name *.qml -exec rm {} \;
#find PyQt5/Qt/qml/ -name *.qmlc -exec rm {} \;
#find PyQt5/Qt/qml/QtQuick -exec rm {} \;
#rm -rf PyQt5/Qt/qml/QtCharts/designer/images
#rm -rf PyQt5/Qt/qml/Qt/labs

popd

echo "Running pyinstaller"

cp packaging/windows/galacteek_exe.spec .
pyinstaller galacteek_exe.spec

echo "Success, moving bundle"

mv dist/galacteek.exe $BUNDLE_PATH

rm galacteek_win.py
