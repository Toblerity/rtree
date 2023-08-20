"""
finder.py
------------

Locate `libspatialindex` shared library by any means necessary.
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys
from ctypes.util import find_library

# the current working directory of this file
_cwd = os.path.abspath(os.path.expanduser(os.path.dirname(__file__)))

# generate a bunch of candidate locations where the
# libspatialindex shared library *might* be hanging out
_candidates = [
    os.environ.get("SPATIALINDEX_C_LIBRARY", None),
    os.path.join(_cwd, "lib"),
    _cwd,
    "",
]


def load() -> ctypes.CDLL:
    """Load the `libspatialindex` shared library.

    :returns: Loaded shared library
    """
    if os.name == "nt":
        # check the platform architecture
        if "64" in platform.architecture()[0]:
            arch = "64"
        else:
            arch = "32"
        lib_name = f"spatialindex_c-{arch}.dll"

        # add search paths for conda installs
        if (
            os.path.exists(os.path.join(sys.prefix, "conda-meta"))
            or "conda" in sys.version
        ):
            _candidates.append(os.path.join(sys.prefix, "Library", "bin"))

        # get the current PATH
        oldenv = os.environ.get("PATH", "").strip().rstrip(";")
        # run through our list of candidate locations
        for path in _candidates:
            if not path or not os.path.exists(path):
                continue
            # temporarily add the path to the PATH environment variable
            # so Windows can find additional DLL dependencies.
            os.environ["PATH"] = ";".join([path, oldenv])
            try:
                rt = ctypes.cdll.LoadLibrary(os.path.join(path, lib_name))
                if rt is not None:
                    return rt
            except OSError:
                pass
            except BaseException as E:
                print(f"rtree.finder unexpected error: {E!s}")
            finally:
                os.environ["PATH"] = oldenv
        raise OSError(f"could not find or load {lib_name}")

    elif os.name == "posix":
        # posix includes both mac and linux
        # use the extension for the specific platform
        if platform.system() == "Darwin":
            # macos shared libraries are `.dylib`
            lib_name = "libspatialindex_c.dylib"
        else:
            import importlib.metadata

            # linux shared libraries are `.so`
            lib_name = "libspatialindex_c.so"

            # add path for binary wheel prepared with cibuildwheel/auditwheel
            try:
                pkg_files = importlib.metadata.files("rtree")
                for file in pkg_files:  # type: ignore
                    if (
                        file.parent.name == "Rtree.libs"
                        and file.stem.startswith("libspatialindex")
                        and ".so" in file.suffixes
                    ):
                        _candidates.insert(1, os.path.join(str(file.locate())))
                        break
            except importlib.metadata.PackageNotFoundError:
                pass

        # get the starting working directory
        cwd = os.getcwd()
        for cand in _candidates:
            if cand is None:
                continue
            elif os.path.isdir(cand):
                # if our candidate is a directory use best guess
                path = cand
                target = os.path.join(cand, lib_name)
            elif os.path.isfile(cand):
                # if candidate is just a file use that
                path = os.path.split(cand)[0]
                target = cand
            else:
                continue

            if not os.path.exists(target):
                continue

            try:
                # move to the location we're checking
                os.chdir(path)
                # try loading the target file candidate
                rt = ctypes.cdll.LoadLibrary(target)
                if rt is not None:
                    return rt
            except BaseException as E:
                print(f"rtree.finder ({target}) unexpected error: {E!s}")
            finally:
                os.chdir(cwd)

    try:
        # try loading library using LD path search
        path = find_library("spatialindex_c")
        if path is not None:
            return ctypes.cdll.LoadLibrary(path)

    except BaseException:
        pass

    raise OSError("Could not load libspatialindex_c library")
