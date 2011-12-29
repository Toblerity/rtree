
from glob import glob
from setuptools import setup

import rtree

# Get text from README.txt
readme_text = file('docs/source/README.txt', 'rb').read()

import os

if os.name == 'nt':
    data_files=[('DLLs',[r'D:\libspatialindex\bin\spatialindex.dll',
                         r'D:\libspatialindex\bin\spatialindex_c.dll',]),]
else:
    data_files = None
    
setup(name          = 'Rtree',
      version       = rtree.__version__,
      description   = 'R-Tree spatial index for Python GIS',
      license       = 'LGPL',
      keywords      = 'gis spatial index r-tree',
      author        = 'Sean Gillies',
      author_email  = 'sean.gillies@gmail.com',
      maintainer        = 'Howard Butler',
      maintainer_email  = 'hobu@hobu.net',
      url   = 'http://toblerity.github.com/rtree/',
      long_description = readme_text,
      packages      = ['rtree'],
      install_requires = ['setuptools'],
      test_suite = 'tests.test_suite',
      data_files = data_files,
      zip_safe = False,
      classifiers   = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Programming Language :: C',
        'Programming Language :: C++',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Database',
        ],
)

