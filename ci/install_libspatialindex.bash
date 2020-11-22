#!/bin/bash
set -xe

# A simple script to install libspatialindex from a Github Release
VERSION=1.9.3
SHA256=63a03bfb26aa65cf0159f925f6c3491b6ef79bc0e3db5a631d96772d6541187e

# where to copy resulting files
# this has to be run before `cd`-ing anywhere
# if the script has been passed a target location use it
if [ -z "$1" ]; then
    # target is empty string so copy relative to this file
    # note that this does not work on macos for unknowable reasons
    TARGET=`dirname "$(readlink -f "$0")"`/../rtree/lib/
else
    # target is the passed argment
    TARGET=$1
fi

# make directory for shared libraries if it doesn't exist
mkdir -p $TARGET


rm $VERSION.zip || true
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/$VERSION.zip

# check the file hash
echo "${SHA256}  ${VERSION}.zip" | sha256sum --check

rm -rf "libspatialindex-${VERSION}" || true
unzip $VERSION
cd libspatialindex-${VERSION}

mkdir build
cd build

cmake ..
make -j 4

# copy built libraries relative to path of this script
# -d means copy links as links rather than duplicate files
# macos uses "bsd cp" and needs special handling
if [ "$(uname)" == "Darwin" ]; then
    cp bin/libspatialindex.dylib $TARGET
    cp bin/libspatialindex_c.dylib $TARGET
else
    cp -d bin/* $TARGET
fi


cd ../..
rm -rf "libspatialindex-${VERSION}"
