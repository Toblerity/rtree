#!/bin/bash

python -m pip install pytest numpy

for f in dist/*.egg
do

    python -m pip install $f
done;

pytest
