#!/bin/bash


python -m pip install pytest numpy

for f in dist/*.whl
do

    python -m pip install $f
done;

pytest
