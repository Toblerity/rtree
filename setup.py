
from glob import glob
from setuptools import setup


# Get text from README.txt
readme_text = file('docs/source/README.txt', 'rb').read()


import os

if os.name == 'nt':
    data_files=[('DLLs',[r'D:\buildkit\spatialindex\spatialindex1.dll',
                         r'D:\buildkit\spatialindex\spatialindex1_c.dll',]),]
else:
    data_files = None
    
setup(name          = 'Rtree',
      version       = '0.6.0',
      description   = 'R-Tree spatial index for Python GIS',
      license       = 'LGPL',
      keywords      = 'gis spatial index',
      author        = 'Sean Gillies',
      author_email  = 'sgillies@frii.com',
      maintainer        = 'Sean Gillies',
      maintainer_email  = 'sgillies@frii.com',
      url   = 'http://trac.gispython.org/lab/wiki/Rtree',
      long_description = readme_text,
      packages      = ['rtree'],
      install_requires = ['setuptools'],
      test_suite = 'tests.test_suite',
      data_files = data_files,
      zip_safe = False,
      classifiers   = [
        'Development Status :: 4 - Beta',
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

