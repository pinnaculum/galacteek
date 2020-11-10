#!/bin/sh

set -x
set -e

cat <<EOF > galacteek.py
import sys
import faulthandler
print("Starting galacteek ..")

faulthandler.enable(sys.stdout)

from galacteek.guientrypoint import *
start()
EOF

#export PYTHONPATH=$PYTHONPATH:$TRAVIS_BUILD_DIR

PYINS_VENV=$TRAVIS_BUILD_DIR/venv-pyinstaller-build
python3 -m venv $PYINS_VENV

./$PYINS_VENV/Scripts/activate.bat
G_VERSION=$(grep '__version__' galacteek/__init__.py|sed -e "s/__version__ = '\(.*\)'$/\1/")

pip install "pyinstaller==0.4.0"

# Patch pyimod03_importers.py (to include source code with inspect)
cp packaging/windows/pyimod03_importers.py \
    $PYINS_VENV/Lib/site-packages/PyInstaller/loader

pip install wheel
pip install "$TRAVIS_BUILD_DIR"/dist/galacteek-${G_VERSION}-py3-none-any.whl

echo "Running pyinstaller"

pyinstaller packaging/windows/galacteek.spec
