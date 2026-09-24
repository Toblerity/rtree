#!/bin/sh
set -xe

# Build a *static*, position-independent libspatialindex from a GitHub release
# into <project>/sidx-static, where CMakeLists.txt looks for it.  The pybind11
# extension links it in directly, so wheels carry no separate shared library.
VERSION=2.1.0
SHA256=86aa0925dd151ff9501a5965c4f8d7fb3dcd8accdc386a650dbdd62660399926

# where to copy resulting files
# this has to be run before `cd`-ing anywhere
install_prefix() {
  OURPWD=$PWD
  cd "$(dirname "$0")"
  cd ..
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
INSTALL_PREFIX=`install_prefix`/sidx-static
SL=`scriptloc`

rm -f $VERSION.zip
curl -LOSs --retry 5 --retry-max-time 120 https://github.com/libspatialindex/libspatialindex/archive/${VERSION}.zip

# check the file hash
if [ "$(uname)" = "Darwin" ]
then
    echo "${SHA256}  ${VERSION}.zip" | shasum -a 256 -c -
else
    echo "${SHA256}  ${VERSION}.zip" | sha256sum -c -
fi

rm -rf "libspatialindex-${VERSION}"
unzip -q $VERSION
cd libspatialindex-${VERSION}

mkdir build
cd build

printenv

if [ "$(uname)" = "Darwin" ]; then
    # One universal static library serves both the x86_64 and arm64 wheels.
    CMAKE_ARGS="-D CMAKE_OSX_ARCHITECTURES=x86_64;arm64"
fi

cmake ${CMAKE_ARGS} \
  -D CMAKE_BUILD_TYPE=Release \
  -D BUILD_SHARED_LIBS=OFF \
  -D CMAKE_POSITION_INDEPENDENT_CODE=ON \
  -D BUILD_TESTING=OFF \
  -D CMAKE_INSTALL_PREFIX=${INSTALL_PREFIX} \
  -D CMAKE_INSTALL_LIBDIR=lib \
  ..
make -j 4

# copy built libraries relative to path of this script
make install

ls -R ${INSTALL_PREFIX}/lib
ls -R ${INSTALL_PREFIX}/include
