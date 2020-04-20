#!/bin/bash

#/opt/python/cp38-cp38

#python-root: ['cp36-cp36m','cp37-cp37m','cp38-cp38']

# 3.6, 3.7, 3.8
PYTHON_VERSION="$1"

if [[ "$PYTHON_VERSION" == "3.6" ]]; then
    PYTHONROOT="/opt/python/cp36-cp36m"
elif [[ "$PYTHON_VERSION" == "3.7" ]]; then
    PYTHONROOT="/opt/python/cp37-cp37m"
elif [[ "$PYTHON_VERSION" == "3.8" ]]; then
    PYTHONROOT="/opt/python/cp38-cp38"
fi

echo "PYTHONROOT: " $PYTHONROOT

$PYTHONROOT/bin/python -m pip install cmake

git clone https://github.com/libspatialindex/libspatialindex.git
cd libspatialindex
mkdir build; cd build
$PYTHONROOT/bin/cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
NPROC=$($PYTHONROOT/bin/python -c "import multiprocessing;print(multiprocessing.cpu_count())")
make -j $NPROC install

cd /src

rm -rf build dist Rtree.egg-info/


mkdir -p /src/rtree/lib
mkdir -p /src/rtree/include

cp -r /usr/lib/libspatialindex* /src/rtree/lib
cp -r /usr/local/lib/libcrypt*.so* /src/rtree/lib
cp -r /usr/include/spatialindex/* /src/rtree/include



$PYTHONROOT/bin/python setup.py bdist_wheel


for f in dist/*.whl
do
    auditwheel repair $f
done;
