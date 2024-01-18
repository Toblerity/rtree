#!/usr/bin/env python3
import sys
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

        source_lib = source_dir / "lib"
        target_lib = target_dir / "lib"
        if source_lib.is_dir():
            # what patterns represent shared libraries for supported platforms
            if sys.platform.startswith("win"):
                lib_pattern = "*.dll"
            elif sys.platform.startswith("linux"):
                lib_pattern = "*.so*"
            elif sys.platform == "darwin":
                lib_pattern = "libspatialindex*dylib"
            else:
                raise ValueError(f"unhandled platform {sys.platform!r}")

            target_lib.mkdir(parents=True, exist_ok=True)
            for pth in source_lib.glob(lib_pattern):
                # if the source isn't a file skip it
                if not pth.is_file():
                    continue

                # copy the source file to the target directory
                self.copy_file(str(pth), str(target_lib / pth.name))

        source_include = source_dir / "include"
        target_include = target_dir / "include"
        if source_include.is_dir():
            for pth in source_include.rglob("*.h"):
                rpth = pth.relative_to(source_include)

                # copy the source file to the target directory
                target_subdir = target_include / rpth.parent
                target_subdir.mkdir(parents=True, exist_ok=True)
                self.copy_file(str(pth), str(target_subdir))


# See pyproject.toml for other project metadata
setup(
    name="Rtree",
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel, "install": InstallPlatlib},
)
