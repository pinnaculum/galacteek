#!/bin/bash

PIP=pip3
PYTHONEX=python3

mkdir -p $HOME/bin

if [ "$TRAVIS_OS_NAME" = "linux" ]; then
	PYTHONEX=python3.6
	wget https://dist.ipfs.io/go-ipfs/v0.4.21/go-ipfs_v0.4.21_linux-amd64.tar.gz
	tar -C $HOME -xzvf go-ipfs_v0.4.21_linux-amd64.tar.gz
fi

if [ "$TRAVIS_OS_NAME" = "osx" ]; then
	wget https://dist.ipfs.io/go-ipfs/v0.4.21/go-ipfs_v0.4.21_darwin-amd64.tar.gz
	tar -C $HOME -xzvf go-ipfs_v0.4.21_darwin-amd64.tar.gz
fi

mv $HOME/go-ipfs/ipfs $HOME/bin

export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.6/dist-packages
export PATH=$PATH:$HOME/bin

$PYTHONEX -m venv venvg
source venvg/bin/activate

$PIP install -r requirements.txt
$PIP install -r requirements-dev.txt

$PYTHONEX setup.py build install
$PYTHONEX setup.py sdist bdist_wheel

tox -v
