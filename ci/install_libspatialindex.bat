python -c "import sys; print(sys.version)"

set SIDX_VERSION=2.0.0

curl -OL "https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip"

tar xvf "%SIDX_VERSION%.zip"

cd libspatialindex-%SIDX_VERSION%

mkdir build
cd build

pip install ninja

cmake -D CMAKE_BUILD_TYPE=Release -G Ninja ..

ninja

mkdir %~dp0\..\rtree\lib
copy bin\*.dll %~dp0\..\rtree\lib
xcopy /S ..\include\* %~dp0\..\rtree\include\
rmdir /Q /S bin

dir %~dp0\..\rtree\
dir %~dp0\..\rtree\lib
dir %~dp0\..\rtree\include
