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

# Install CMake
$PYTHONROOT/bin/python -m pip install cmake
# Clone libspatialindex
git clone https://github.com/libspatialindex/libspatialindex.git
# Build the source distribution
$PYTHONROOT/bin/python setup.py bdist_egg
