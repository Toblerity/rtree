python -c "import sys; print(sys.version)"

// A simple script to install libspatialindex from a Github Release
curl -L -O https://github.com/libspatialindex/libspatialindex/archive/1.9.3.zip

unzip 1.9.3.zip
copy %~dp0\CMakeLists.txt libspatialindex-1.9.3\CMakeLists.txt
cd libspatialindex-1.9.3

mkdir build
cd build

cmake -D CMAKE_BUILD_TYPE=Release ..

"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\amd64\MSBuild.exe" spatialindex.sln

mkdir %~dp0\..\rtree\lib
copy bin\Debug\*.dll %~dp0\..\rtree\lib
rmdir /Q /S bin

dir %~dp0\..\rtree\
dir %~dp0\..\rtree\lib

