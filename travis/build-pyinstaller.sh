#!/bin/sh

cat <<EOF > galacteek.py
from galacteek.guientrypoint import *
start()
EOF

export PYTHONPATH=$PYTHONPATH:$TRAVIS_BUILD_DIR

./venvg/Scripts/activate.bat

ls $TRAVIS_BUILD_DIR

pyinstaller --paths "C:\Python37\Lib\site-packages\PyQt5\Qt\bin" \
	--paths "C:\Python37\Lib\site-packages" \
	--paths "C:\Python37\Lib" \
	--paths "C:\Python37" \
	--paths $TRAVIS_BUILD_DIR \
    --add-binary "$TRAVIS_BUILD_DIR/packaging/windows/libmagic/libmagic-1.dll:." \
    --add-binary "$TRAVIS_BUILD_DIR/packaging/windows/libmagic/libgnurx-0.dll:." \
    --add-binary "$TRAVIS_BUILD_DIR/packaging/windows/zbar/libzbar64-0.dll:." \
	--onefile \
	--hidden-import PyQt5 \
	--hidden-import galacteek \
	galacteek.py

ls dist
