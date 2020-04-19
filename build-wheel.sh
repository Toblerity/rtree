#!/bin/bash


/opt/python/cp38-cp38/bin/pip install cmake

git clone https://github.com/libspatialindex/libspatialindex.git
cd libspatialindex
mkdir build; cd build
/opt/python/cp38-cp38/bin/cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
NPROC=$(/opt/python/cp38-cp38/bin/python -c "import multiprocessing;print(multiprocessing.cpu_count())")
make -j $NPROC install

cd /src

rm -rf build dist Rtree.egg-info/


mkdir -p /src/rtree/lib
mkdir -p /src/rtree/include

cp -r /usr/lib/libspatialindex* /src/rtree/lib
cp -r /usr/local/lib/libcrypt*.so* /src/rtree/lib
cp -r /usr/include/spatialindex/* /src/rtree/include

/opt/python/cp36-cp36m/bin/python setup.py bdist_wheel
/opt/python/cp37-cp37m/bin/python setup.py bdist_wheel
/opt/python/cp38-cp38/bin/python setup.py bdist_wheel

for f in dist/*.whl
do

    auditwheel repair $f
done;