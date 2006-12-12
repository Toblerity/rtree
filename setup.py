
from glob import glob
from setuptools import setup, Extension

_rtree = Extension('rtree._rtree',
                  sources=['rtree/_rtreemodule.cc', 'rtree/wrapper.cc',
                           'rtree/gispyspatialindex.cc'] \
                         +glob('spatialindex/tools/*.cc') \
                         +glob('spatialindex/storagemanager/*.cc') \
                         +glob('spatialindex/spatialindex/*.cc') \
                         +glob('spatialindex/rtree/*.cc') \
                         +glob('spatialindex/geometry/*.cc'),
                  include_dirs=['spatialindex/include']
                  )

setup(name          = 'Rtree',
      version       = '0.1.0',
      description   = 'R-tree spatial index for Python GIS',
      license       = 'GPL',
      keywords      = 'spatial index',
      author        = 'Sean Gillies',
      author_email  = 'sgillies@frii.com',
      maintainer    = 'Sean Gillies',
      maintainer_email  = 'sgillies@frii.com',
      url   = 'http://icon.stoa.org/trac/pleiades/wiki/RTreeSpatialIndex',
      packages      = ['rtree'],
      namespace_packages    = ['rtree'],
      ext_modules   = [_rtree],
      classifiers   = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: C',
        'Programming Language :: C++',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Database',
        ],
)

