
call conda activate test
set SIDX_VERSION=%1
REM conda install -c conda-forge compilers -y
REM
cd
cd ..

where python
python -c "import sys; print(sys.version)"
python -m pip install cmake ninja
python -c "from urllib.request import urlretrieve; urlretrieve('https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip', 'libspatialindex.zip')"
where python
python -m "zipfile" -e libspatialindex.zip libspatialindex

pushd "%~dp0"

cd libspatialindex\libspatialindex-%SIDX_VERSION%
mkdir build
cd build

set CC=cl.exe
set CXX=cl.exe
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja

popd
cd
mkdir rtree\lib
mkdir rtree\include
copy ".\libspatialindex\libspatialindex-%SIDX_VERSION%\build\bin\*.dll" .\rtree\lib
copy ".\libspatialindex\libspatialindex-%SIDX_VERSION%\include\*" .\rtree\include

python setup.py bdist_wheel
popd
