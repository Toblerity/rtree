python -c "import sys; print(sys.version)"

// A simple script to install libspatialindex from a Github Release
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/1.9.3.zip

unzip 1.9.3.zip
cp %~dp0\CMakeLists.txt libspatialindex-1.9.3\CMakeLists.txt
cd libspatialindex-1.9.3

mkdir build
cd build

cmake -G Ninja -D CMAKE_BUILD_TYPE=Release ..
ninja


