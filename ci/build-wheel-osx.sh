#!/bin/bash


PYPREFIX=$(python -c "import sys; print(sys.prefix)")
python -c "import sys; print(sys.version)"
echo "PYPREFIX: " $PYPREFIX
python -m pip install cmake
python -m pip install delocate

PREFIX=$(pwd)

git clone https://github.com/libspatialindex/libspatialindex.git
cd libspatialindex
mkdir build; cd build
$PYPREFIX/bin/cmake -DCMAKE_INSTALL_PREFIX=$PREFIX/libspatialindex -DCMAKE_BUILD_TYPE=Release ..
NPROC=$($PYPREFIX/bin/python -c "import multiprocessing;print(multiprocessing.cpu_count())")
make -j $NPROC install

rm -rf build dist Rtree.egg-info/


cd $PREFIX
mkdir -p rtree/lib
mkdir -p rtree/include

cp -r $PREFIX/libspatialindex/lib/libspatialindex* rtree/lib
cp -r $PREFIX/include/spatialindex/* rtree/include

pwd
python setup.py bdist_wheel

delocate-wheel -w wheels -v dist/*.whl
