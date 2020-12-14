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

# current working directory of this setup.py file
_cwd = os.path.abspath(os.path.split(__file__)[0])


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
        """
        Copy the shared libraries into the wheel. Note that this
        will *only* check in `rtree/lib` rather than anywhere on
        the system so if you are building a wheel you *must* copy or
        symlink the `.so`/`.dll`/`.dylib` files into `rtree/lib`.
        """
        # use for checking extension types
        from fnmatch import fnmatch

        install.finalize_options(self)
        if self.distribution.has_ext_modules():
            self.install_lib = self.install_platlib
        # now copy over libspatialindex
        # get the location of the shared library on the filesystem

        # where we're putting the shared library in the build directory
        target_dir = os.path.join(self.build_lib, 'rtree', 'lib')
        # where are we checking for shared libraries
        source_dir = os.path.join(_cwd, 'rtree', 'lib')

        # what patterns represent shared libraries
        patterns = {'*.so',
                    'libspatialindex*dylib',
                    '*.dll'}

        if not os.path.isdir(source_dir):
            # no copying of binary parts to library
            # this is so `pip install .` works even
            # if `rtree/lib` isn't populated
            return

        for file_name in os.listdir(source_dir):
            # make sure file name is lower case
            check = file_name.lower()
            # use filename pattern matching to see if it is
            # a shared library format file
            if not any(fnmatch(check, p) for p in patterns):
                continue

            # if the source isn't a file skip it
            if not os.path.isfile(os.path.join(source_dir, file_name)):
                continue

            # make build directory if it doesn't exist yet
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)

            # copy the source file to the target directory
            self.copy_file(
                os.path.join(source_dir, file_name),
                os.path.join(target_dir, file_name))


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
    package_data={"rtree": ['lib']},
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
