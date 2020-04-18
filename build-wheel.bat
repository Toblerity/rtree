
set SIDX_VERSION=%1
REM conda install -c conda-forge compilers -y
pip install cmake ninja
python -c "from urllib.request import urlretrieve; urlretrieve('https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip', 'libspatialindex.zip')"
where python
python -m "zipfile" -e libspatialindex.zip libspatialindex

pushd "%~dp0"

cd libspatialindex\libspatialindex-%SIDX_VERSION%
mkdir build
cd build

cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja

popd
cd
mkdir rtree\lib
copy ".\libspatialindex\libspatialindex-%SIDX_VERSION%\build\bin\*.dll" .\rtree\lib