#!/usr/bin/env python
import os

from setuptools import setup
from setuptools.dist import Distribution
from setuptools.command.install import install
import itertools as it

from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
class bdist_wheel(_bdist_wheel):
    def finalize_options(self):
        _bdist_wheel.finalize_options(self)
        self.root_is_pure = False


# Get text from README.txt
with open('docs/source/README.txt', 'r') as fp:
    readme_text = fp.read()

# Get __version without importing
with open('rtree/__init__.py', 'r') as fp:
    # get and exec just the line which looks like "__version__ = '0.9.4'"
    exec(next(line for line in fp if '__version__' in line))


# Tested with wheel v0.29.0
class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name"""
    def has_ext_modules(foo):
        return True

class InstallPlatlib(install):
    def finalize_options(self):
        install.finalize_options(self)
        if self.distribution.has_ext_modules():
            self.install_lib = self.install_platlib

setup(
    name='Rtree',
    version=__version__,
    description='R-Tree spatial index for Python GIS',
    license='MIT',
    keywords='gis spatial index r-tree',
    author='Sean Gillies',
    author_email='sean.gillies@gmail.com',
    maintainer='Howard Butler',
    maintainer_email='howard@hobu.co',
    url='https://github.com/Toblerity/rtree',
    long_description=readme_text,
    packages=['rtree'],
    package_data={"rtree": ["lib/*", "include/**/*", "include/**/**/*" ]},
    zip_safe=False,
    include_package_data = True,
    distclass = BinaryDistribution,
    cmdclass={'bdist_wheel': bdist_wheel,'install': InstallPlatlib},
    classifiers=[
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
