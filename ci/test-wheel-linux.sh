#!/bin/bash

PYTHONROOT="/opt/python/%1"


$PYTHONROOT/bin/python -m pip install pytest numpy

for f in dist/*.whl
do

    $PYTHONROOT/bin/python -m pip install $f
done;

pytest
