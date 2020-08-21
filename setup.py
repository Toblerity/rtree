#!/usr/bin/env python
import os
import sys

from setuptools import setup
from setuptools.dist import Distribution
from setuptools.command.install import install

from wheel.bdist_wheel import bdist_wheel as _bdist_wheel


# Get text from README.txt
with open('docs/source/README.txt', 'r') as fp:
    readme_text = fp.read()

# Get __version without importing
with open('rtree/__init__.py', 'r') as fp:
    # get and exec just the line which looks like "__version__ = '0.9.4'"
    exec(next(line for line in fp if '__version__' in line))


def shared_path():
    """
    Get the location of the libspatialindex shared library.

    Returns
    ---------
    rt_path : str
      Location of `libspatialindex_c.so.4`
    """

    # the location of `finder.py`, which has the logic to load
    # the shared library and also has no imports outside of stdlib
    path = os.path.abspath(
        os.path.join(os.path.split(__file__)[0], 'rtree/finder.py'))
    # load the module from the path on Python 2 or 3
    if sys.version_info.major >= 3:
        # python >= 3.5
        import importlib.util
        spec = importlib.util.spec_from_file_location("finder", path)
        finder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(finder)
    else:
        # python 2
        import imp
        finder = imp.load_source('finder', path)
    # actually load the shared module to get it's location
    rt_path = finder.load(return_path=True)[1]
    return rt_path


class bdist_wheel(_bdist_wheel):
    def finalize_options(self):
        _bdist_wheel.finalize_options(self)
        self.root_is_pure = False


class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name"""
    def has_ext_modules(foo):
        return True


class InstallPlatlib(install):
    def finalize_options(self):
        install.finalize_options(self)
        if self.distribution.has_ext_modules():
            self.install_lib = self.install_platlib
        # now copy over libspatialindex
        # get the location of the shared library on the filesystem
        source = shared_path()

        # only try to copy file if we found it successfully
        if os.path.exists(source):
            # where we're putting the shared library in the build directory
            target_dir = os.path.join(
                self.build_lib,
                'rtree')
            if not os.path.isdir(target_dir):
                # make build directory if it doesn't exist yet
                os.makedirs(os.path.split(target)[0])
            # copy the source file to the target directory
            target = os.path.join(
                target_dir, os.path.split(source)[1])
            self.copy_file(source, target)


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
    package_data={"rtree": ["lib/*", "include/**/*", "include/**/**/*"]},
    zip_safe=False,
    include_package_data=True,
    distclass=BinaryDistribution,
    cmdclass={'bdist_wheel': bdist_wheel, 'install': InstallPlatlib},
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
