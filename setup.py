#!/usr/bin/env python3
from pathlib import Path

from setuptools import setup
from setuptools.command.install import install
from setuptools.dist import Distribution
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

# current working directory of this setup.py file
_cwd = Path(__file__).resolve().parent


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
        Copy the shared libraries and header files into the wheel. Note that
        this will *only* check in `rtree/lib` and `include` rather than
        anywhere on the system so if you are building a wheel you *must* copy
        or symlink the `.so`/`.dll`/`.dylib` files into `rtree/lib` and
        `.h` into `rtree/include`.
        """
        install.finalize_options(self)
        if self.distribution.has_ext_modules():
            self.install_lib = self.install_platlib

        # source files to copy
        source_dir = _cwd / "rtree"

        # destination for the files in the build directory
        target_dir = Path(self.build_lib) / "rtree"

        # copy lib tree
        source_lib = source_dir / "lib"
        if source_lib.is_dir():
            target_lib = target_dir / "lib"
            self.copy_tree(str(source_lib), str(target_lib))

        # copy include tree
        source_include = source_dir / "include"
        if source_include.is_dir():
            target_include = target_dir / "include"
            self.copy_tree(str(source_include), str(target_include))


# See pyproject.toml for other project metadata
setup(
    name="rtree",
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel, "install": InstallPlatlib},
)
