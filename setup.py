#!/usr/bin/env python3
import os

from setuptools import setup
from setuptools.command.install import install
from setuptools.dist import Distribution
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

# current working directory of this setup.py file
_cwd = os.path.abspath(os.path.split(__file__)[0])


class bdist_wheel(_bdist_wheel):  # type: ignore[misc]
    def finalize_options(self) -> None:
        _bdist_wheel.finalize_options(self)
        self.root_is_pure = False


class BinaryDistribution(Distribution):  # type: ignore[misc]
    """Distribution which always forces a binary package with platform name"""

    def has_ext_modules(foo) -> bool:
        return True


class InstallPlatlib(install):  # type: ignore[misc]
    def finalize_options(self) -> None:
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
        target_dir = os.path.join(self.build_lib, "rtree", "lib")
        # where are we checking for shared libraries
        source_dir = os.path.join(_cwd, "rtree", "lib")

        # what patterns represent shared libraries
        patterns = {"*.so", "libspatialindex*dylib", "*.dll"}

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
                os.path.join(source_dir, file_name), os.path.join(target_dir, file_name)
            )


# See pyproject.toml for other project metadata
setup(
    name="Rtree",
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel, "install": InstallPlatlib},
)
