python -c "import sys; print(sys.version)"

pip install cmake ninja

// A simple script to install libspatialindex from a Github Release
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/1.9.3.zip


unzip 1.9.3.zip
cd libspatialindex-1.9.3

mkdir build
cd build

set CC=clang
set CXX=clang

cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja


