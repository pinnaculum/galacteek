#!/bin/bash
#
# Credits: from the great https://github.com/Pext/Pext
#

set -x
set -e

# use RAM disk if possible
if [ -d /dev/shm ]; then
    TEMP_BASE=/dev/shm
else
    TEMP_BASE=$GITHUB_WORKSPACE
fi

BUILD_DIR=$(mktemp -d "$TEMP_BASE/galacteek-MacOS-build-XXXXXX")

if [[ $GIT_BRANCH =~ ^v([0-9].[0-9].[0-9]{1,2}) ]] ; then
    echo "Using tag: $GIT_BRANCH"
    EVERSION=${BASH_REMATCH[1]}
    export DMG_FILENAME="Galacteek-${EVERSION}.dmg"
else
    if [ "$GIT_BRANCH" != "master" ]; then
        export DMG_FILENAME="Galacteek-${COMMIT_SHORT}.dmg"
    else
        export DMG_FILENAME="Galacteek-${G_VERSION}.dmg"
    fi
fi

echo "Building to DMG, path: $BUNDLE_PATH"

cleanup () {
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
    fi
}

trap cleanup EXIT

OLD_CWD="$(pwd)"

pushd "$BUILD_DIR"/

# install Miniconda
MINICONDA_DIST="Miniconda3-py37_4.8.3-MacOSX-x86_64.sh"
wget https://repo.anaconda.com/miniconda/${MINICONDA_DIST}
bash ${MINICONDA_DIST} -b -p $GITHUB_WORKSPACE/miniconda -f
rm ${MINICONDA_DIST}

export PATH="$GITHUB_WORKSPACE/miniconda/bin:$PATH"

# create conda env
conda create -n galacteek python=3.7 --yes
source activate galacteek

WHEEL="$OLD_CWD"/dist/galacteek-${G_VERSION}-py3-none-any.whl

# install dependencies
pip install wheel
pip install -r "$OLD_CWD"/requirements.txt
pip install $WHEEL
pip install $WHEEL'[markdown-extensions]'

# leave conda env
source deactivate

# create .app Framework
mkdir -p galacteek.app/Contents/
mkdir galacteek.app/Contents/MacOS galacteek.app/Contents/Resources galacteek.app/Contents/Resources/galacteek
cp "$OLD_CWD"/travis/Info.plist galacteek.app/Contents/Info.plist

# copy Miniconda env
cp -R $GITHUB_WORKSPACE/miniconda/envs/galacteek/* galacteek.app/Contents/Resources/

# copy icons
mkdir -p galacteek.app/Contents/Resources/share/icons
cp "$OLD_CWD"/share/icons/galacteek.icns galacteek.app/Contents/Resources/share/icons

# copy go-ipfs
mkdir -p galacteek.app/Contents/Resources/bin
cp $GITHUB_WORKSPACE/go-ipfs/ipfs-${GO_IPFS_VERSION} galacteek.app/Contents/Resources/bin
cp $GITHUB_WORKSPACE/fs-repo-migrations/fs-repo-migrations galacteek.app/Contents/Resources/bin

# copy tor
cp /usr/local/bin/tor galacteek.app/Contents/Resources/bin

# Copy notbit
cp $GITHUB_WORKSPACE/notbit/src/notbit galacteek.app/Contents/Resources/bin

pushd galacteek.app/Contents/Resources/bin
ln -s ipfs-${GO_IPFS_VERSION} ipfs
ln -s notbit notbit-keygen
ln -s notbit notbit-sendmail
popd

# Install libmagic and the magic db files
brew install libmagic --ignore-dependencies
cp -av /usr/local/Cellar/libmagic/*/lib/*.dylib galacteek.app/Contents/Resources/lib
cp -av /usr/local/Cellar/libmagic/*/share/misc galacteek.app/Contents/Resources/share/

cp -av ${GITHUB_WORKSPACE}/packaging/macos/zbar/*.dylib galacteek.app/Contents/Resources/lib
cp -av ${GITHUB_WORKSPACE}/packaging/macos/jpeg/*.dylib galacteek.app/Contents/Resources/lib

# create entry script for galacteek
cat > galacteek.app/Contents/MacOS/galacteek <<\EAT
#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export GALACTEEK_MAGIC_DBPATH="$DIR/../Resources/share/misc/magic.mgc"
export DYLD_FALLBACK_LIBRARY_PATH=$DYLD_FALLBACK_LIBRARY_PATH:$DIR/../Resources/lib
export PATH=$PATH:$DIR/../Resources/bin
$DIR/../Resources/bin/python $DIR/../Resources/bin/galacteek -d --from-dmg --no-ssl-verify
EAT

chmod a+x galacteek.app/Contents/MacOS/galacteek

# bloat deletion sequence
pushd galacteek.app/Contents/Resources
rm -rf pkgs
find . -type d -iname '__pycache__' -print0 | xargs -0 rm -r
rm -rf lib/python3.7/site-packages/Cryptodome/SelfTest/*
rm -rf lib/python3.7/site-packages/PyQt5/Qt/plugins/geoservices
rm -rf lib/python3.7/site-packages/PyQt5/Qt/plugins/sceneparsers
rm -rf lib/cmake/
rm -f bin/sqlite3*
rm -rf include/
rm -rf share/{info,man}
popd
popd

# Get the create-dmg repo
git clone https://github.com/andreyvit/create-dmg $GITHUB_WORKSPACE/create-dmg

# generate .dmg
$GITHUB_WORKSPACE/create-dmg/create-dmg --hdiutil-verbose --volname "galacteek-${G_VERSION}" \
    --volicon "${OLD_CWD}"/share/icons/galacteek.icns \
    --hide-extension galacteek.app $BUNDLE_PATH "$BUILD_DIR"/
