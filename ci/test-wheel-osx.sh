#!/bin/bash

PYTHON="python$1"

$PYTHON -m pip install pytest numpy

for f in dist/*.whl
do

    $PYTHON -m pip install $f
done;

pytest
