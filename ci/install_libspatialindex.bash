#!/bin/bash
set -xe

# A simple script to install libspatialindex from a Github Release
VERSION=1.9.3
SHA256=63a03bfb26aa65cf0159f925f6c3491b6ef79bc0e3db5a631d96772d6541187e

# where to copy resulting files
# this has to be run before `cd`-ing anywhere
libtarget() {
  OURPWD=$PWD
  cd "$(dirname "$0")"
  mkdir -p ../rtree/lib
  cd ../rtree/lib
  arr=$(pwd)
  cd "$OURPWD"
  echo $arr
}

headertarget() {
  OURPWD=$PWD
  cd "$(dirname "$0")"
  mkdir -p ../rtree/include
  cd ../rtree/include
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
LIBTARGET=`libtarget`
HEADERTARGET=`headertarget`
SL=`scriptloc`

rm $VERSION.zip || true
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/$VERSION.zip

# check the file hash
echo "${SHA256}  ${VERSION}.zip" | sha256sum -c -

rm -rf "libspatialindex-${VERSION}" || true
unzip -q $VERSION
cd libspatialindex-${VERSION}

mkdir build
cd build

cp "${SL}/CMakeLists.txt" ..

printenv

if [ "$(uname)" == "Darwin" ]; then
    CMAKE_ARGS="-DCMAKE_OSX_ARCHITECTURES=${ARCHFLAGS##* }"
fi

cmake -DCMAKE_BUILD_TYPE=Release ${CMAKE_ARGS} ..
make -j 4

# copy built libraries relative to path of this script
# -d means copy links as links rather than duplicate files
# macos uses "bsd cp" and needs special handling
if [ "$(uname)" == "Darwin" ]; then
    # change the rpath in the dylib to point to the same directory
    install_name_tool -change @rpath/libspatialindex.6.dylib @loader_path/libspatialindex.dylib bin/libspatialindex_c.dylib
    # copy the dylib files to the target director
    cp bin/libspatialindex.dylib $LIBTARGET
    cp bin/libspatialindex_c.dylib $LIBTARGET
    cp -r ../include/* $HEADERTARGET
else
    cp -L bin/* $LIBTARGET
    cp -r ../include/* $HEADERTARGET
fi

ls $LIBTARGET
ls -R $HEADERTARGET
