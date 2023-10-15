python -c "import sys; print(sys.version)"

set SIDX_VERSION=1.9.3

curl -OL "https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip"

tar xvf "%SIDX_VERSION%.zip"

REM unzip 1.9.3.zip
REM copy %~dp0\CMakeLists.txt libspatialindex-1.9.3\CMakeLists.txt
cd libspatialindex-%SIDX_VERSION%

mkdir build
cd build

pip install ninja

cmake -D CMAKE_BUILD_TYPE=Release -G Ninja ..

ninja

mkdir %~dp0\..\rtree\lib
copy bin\*.dll %~dp0\..\rtree\lib
rmdir /Q /S bin

dir %~dp0\..\rtree\
dir %~dp0\..\rtree\lib
