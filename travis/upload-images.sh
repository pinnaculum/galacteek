#!/bin/bash

set -x

if [ ! -z $TRAVIS_BRANCH ] && [ "$TRAVIS_BRANCH" != "master" ] ; then
	export UPLOADTOOL_SUFFIX=$TRAVIS_BRANCH
fi

if [ "$TRAVIS_OS_NAME" = "linux" ]; then
	bash upload.sh AppImage/Galacteek*.AppImage
fi

if [ "$TRAVIS_OS_NAME" = "osx" ]; then
	bash upload.sh Galacteek*.dmg
fi
