#!/bin/bash

PIP=pip3
PYTHONEX=python3

if [ "$TRAVIS_OS_NAME" = "linux" ]; then
	PYTHONEX=python3.6
fi

$PYTHONEX -m venv venvg
source venvg/bin/activate

$PIP install -r requirements.txt
$PIP install -r requirements-dev.txt

export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.6/dist-packages

flake8 galacteek

$PYTHONEX setup.py build install
$PYTHONEX setup.py sdist bdist_wheel
