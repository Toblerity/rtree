
from glob import glob
from setuptools import setup, Extension

_rtree = Extension('rtree._rtree',
                  sources=['rtree/_rtreemodule.cc',
                           'rtree/wrapper.cc', 'rtree/wrapper.h',
                           'rtree/gispyspatialindex.cc',
                           'rtree/gispyspatialindex.h']
                         +glob('spatialindex/tools/*.cc') \
                         +glob('spatialindex/tools/*.h') \
                         +glob('spatialindex/storagemanager/*.cc') \
                         +glob('spatialindex/storagemanager/*.h') \
                         +glob('spatialindex/spatialindex/*.cc') \
                         +glob('spatialindex/spatialindex/*.h') \
                         +glob('spatialindex/rtree/*.cc') \
                         +glob('spatialindex/rtree/*.h') \
                         +glob('spatialindex/geometry/*.cc'),
                         +glob('spatialindex/geometry/*.h'),
                  include_dirs=['spatialindex/include']
                  )

setup(name          = 'Rtree',
      version       = '0.1.0',
      description   = 'R-tree spatial index for Python GIS',
      license       = 'LGPL',
      keywords      = 'spatial index',
      author        = 'Sean Gillies',
      author_email  = 'sgillies@frii.com',
      maintainer    = 'Sean Gillies',
      maintainer_email  = 'sgillies@frii.com',
      url   = 'http://trac.gispython.org/projects/PCL/wiki/ArrTree',
      packages      = ['rtree'],
      ext_modules   = [_rtree],
      classifiers   = [
        'Development Status :: 3 - Alpha',
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

