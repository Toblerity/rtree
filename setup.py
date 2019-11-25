#!/usr/bin/env python
from setuptools import setup
import rtree
import os

import itertools as it

# Get text from README.txt
with open('docs/source/README.txt', 'r') as fp:
    readme_text = fp.read()

extras_require = {
    'test': ['pytest>=3', 'pytest-cov', 'numpy']
}

extras_require['all'] = list(set(it.chain(*extras_require.values())))

setup(
    name          = 'Rtree',
    version       = rtree.__version__,
    description   = 'R-Tree spatial index for Python GIS',
    license       = 'MIT',
    keywords      = 'gis spatial index r-tree',
    author        = 'Sean Gillies',
    author_email  = 'sean.gillies@gmail.com',
    maintainer        = 'Howard Butler',
    maintainer_email  = 'howard@hobu.co',
    url   = 'https://github.com/Toblerity/rtree',
    long_description = readme_text,
    packages      = ['rtree'],
    install_requires = ['setuptools'],
    extras_require = extras_require,
    tests_require = extras_require['test'],
    zip_safe = False,
    classifiers   = [
      'Development Status :: 5 - Production/Stable',
      'Intended Audience :: Developers',
      'Intended Audience :: Science/Research',
      'License :: OSI Approved :: MIT License',
      'Operating System :: OS Independent',
      'Programming Language :: C',
      'Programming Language :: C++',
      'Programming Language :: Python',
      'Topic :: Scientific/Engineering :: GIS',
      'Topic :: Database',
      ],
)
