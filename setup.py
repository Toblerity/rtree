#!/usr/bin/env python
from setuptools import setup
import rtree
import os

# Get text from README.txt
with open('docs/source/README.txt', 'r') as fp:
    readme_text = fp.read()


setup(
    name          = 'Rtree',
    version       = rtree.__version__,
    description   = 'R-Tree spatial index for Python GIS',
    license       = 'MIT',
    keywords      = 'gis spatial index r-tree',
    author        = 'Sean Gillies',
    author_email  = 'sean.gillies@gmail.com',
    maintainer        = 'Howard Butler',
    maintainer_email  = 'hobu@hobu.net',
    url   = 'http://toblerity.github.com/rtree/',
    long_description = readme_text,
    packages      = ['rtree'],
    install_requires = ['setuptools'],
    test_suite = 'tests.test_doctest',
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
