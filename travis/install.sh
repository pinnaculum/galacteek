#!/bin/bash

set -x
set -e

GO_IPFS_VERSION=0.7.0
FS_MIGRATE_VERSION=1.6.4

PIP=pip3
PYTHONEX=python3

mkdir -p $HOME/bin

# Fetch and untar go-ipfs
if [ "$TRAVIS_OS_NAME" = "linux" ]; then
	PYTHONEX=python3.7
	wget https://dist.ipfs.io/go-ipfs/v${GO_IPFS_VERSION}/go-ipfs_v${GO_IPFS_VERSION}_linux-amd64.tar.gz
	tar -C $HOME -xzvf go-ipfs_v${GO_IPFS_VERSION}_linux-amd64.tar.gz

	wget https://dist.ipfs.io/fs-repo-migrations/v${FS_MIGRATE_VERSION}/fs-repo-migrations_v${FS_MIGRATE_VERSION}_linux-amd64.tar.gz
	tar -C $HOME -xzvf fs-repo-migrations_v${FS_MIGRATE_VERSION}_linux-amd64.tar.gz

	wget https://github.com/wasmerio/wasmer/releases/download/0.12.0/wasmer-linux-amd64.tar.gz
	tar -C $HOME -xzvf wasmer-linux-amd64.tar.gz

	export DISPLAY=":99.0"
	/sbin/start-stop-daemon --start --quiet --pidfile /tmp/custom_xvfb_99.pid --make-pidfile --background --exec /usr/bin/Xvfb -- :99 -screen 0 1920x1200x24 -ac +extension GLX +render -noreset
	sleep 3
	herbstluftwm &
	sleep 1
fi

if [ "$TRAVIS_OS_NAME" = "osx" ]; then
	wget https://dist.ipfs.io/go-ipfs/v${GO_IPFS_VERSION}/go-ipfs_v${GO_IPFS_VERSION}_darwin-amd64.tar.gz
	tar -C $HOME -xzvf go-ipfs_v${GO_IPFS_VERSION}_darwin-amd64.tar.gz

	wget https://dist.ipfs.io/fs-repo-migrations/v${FS_MIGRATE_VERSION}/fs-repo-migrations_v${FS_MIGRATE_VERSION}_darwin-amd64.tar.gz
	tar -C $HOME -xzvf fs-repo-migrations_v${FS_MIGRATE_VERSION}_darwin-amd64.tar.gz
fi

if [ "$TRAVIS_OS_NAME" = "windows" ]; then
	wget https://dist.ipfs.io/go-ipfs/v${GO_IPFS_VERSION}/go-ipfs_v${GO_IPFS_VERSION}_windows-amd64.zip
	unzip go-ipfs_v${GO_IPFS_VERSION}_windows-amd64.zip -d $HOME

	wget https://dist.ipfs.io/fs-repo-migrations/v${FS_MIGRATE_VERSION}/fs-repo-migrations_v${FS_MIGRATE_VERSION}_windows-amd64.zip
	unzip fs-repo-migrations_v${FS_MIGRATE_VERSION}_windows-amd64.zip -d $HOME
	PIP=pip
	PYTHONEX=python
fi


mv $HOME/go-ipfs/ipfs $HOME/bin
mv $HOME/fs-repo-migrations/fs-repo-migrations $HOME/bin

$HOME/bin/ipfs init

nohup $HOME/bin/ipfs daemon &

export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.7/dist-packages
export PATH=$PATH:$HOME/bin

$PYTHONEX -m venv venvg

if [ "$TRAVIS_OS_NAME" = "windows" ]; then
	./venvg/Scripts/activate.bat
    $PIP install pywin32
else
	source venvg/bin/activate
fi

$PIP install --upgrade pip
$PIP install wheel
$PIP install -r requirements.txt
$PIP install -r requirements-dev.txt

if [ "$TRAVIS_OS_NAME" != "windows" ]; then
    tox -e py37
fi

$PYTHONEX setup.py build build_docs install
$PYTHONEX setup.py sdist bdist_wheel
