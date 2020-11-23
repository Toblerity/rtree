#!/bin/bash
set -xe

# A simple script to install libspatialindex from a Github Release
VERSION=1.9.3
SHA256=63a03bfb26aa65cf0159f925f6c3491b6ef79bc0e3db5a631d96772d6541187e


# where to copy resulting files
# this has to be run before `cd`-ing anywhere
gentarget() {
  OURPWD=$PWD
  cd "$(dirname "$0")"
  mkdir -p ../rtree/lib
  cd ../rtree/lib
  arr=$(pwd)
  cd "$OURPWD"
  echo $arr
}

scriptloc() {
  OURPWD=$PWD
  cd "$(dirname "$0")"
  arr=$(pwd)
  cd "$OURPWD"
  echo $arr
}
# note that we're doing this convoluted thing to get
# an absolute path so mac doesn't yell at us
TARGET=`gentarget`
SL=`scriptloc`

rm $VERSION.zip || true
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/$VERSION.zip

# check the file hash
echo "${SHA256}  ${VERSION}.zip" | sha256sum --check

rm -rf "libspatialindex-${VERSION}" || true
unzip $VERSION
cd libspatialindex-${VERSION}

mkdir build
cd build

cp "${SL}/CMakeLists.txt" ..

cmake -DCMAKE_BUILD_TYPE=Release ..
make -j 4

# copy built libraries relative to path of this script
# -d means copy links as links rather than duplicate files
# macos uses "bsd cp" and needs special handling
if [ "$(uname)" == "Darwin" ]; then
    cp bin/* $TARGET
else
    cp -d bin/* $TARGET
fi

ls $TARGET

cd ../..
rm -rf "libspatialindex-${VERSION}"
