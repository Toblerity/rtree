"""
Locate `libspatialindex` shared library and header files.
"""
from __future__ import annotations

import ctypes
import importlib.metadata
import os
import platform
import sys
from ctypes.util import find_library
from pathlib import Path

_cwd = Path(__file__).parent
_sys_prefix = Path(sys.prefix)

# generate a bunch of candidate locations where the
# libspatialindex shared library *might* be hanging out
_candidates = []
if "SPATIALINDEX_C_LIBRARY" in os.environ:
    _candidates.append(Path(os.environ["SPATIALINDEX_C_LIBRARY"]))
_candidates += [_cwd / "lib", _cwd, Path("")]


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
        if (_sys_prefix / "conda-meta").exists() or "conda" in sys.version:
            _candidates.append(_sys_prefix / "Library" / "bin")

        # get the current PATH
        oldenv = os.environ.get("PATH", "").strip().rstrip(";")
        # run through our list of candidate locations
        for path in _candidates:
            if not path.exists():
                continue
            # temporarily add the path to the PATH environment variable
            # so Windows can find additional DLL dependencies.
            os.environ["PATH"] = ";".join([str(path), oldenv])
            try:
                rt = ctypes.cdll.LoadLibrary(str(path / lib_name))
                if rt is not None:
                    return rt
            except OSError:
                pass
            except BaseException as err:
                print(f"rtree.finder unexpected error: {err!s}", file=sys.stderr)
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
            # linux shared libraries are `.so`
            lib_name = "libspatialindex_c.so"

            # add path for binary wheel prepared with cibuildwheel/auditwheel
            try:
                pkg_files = importlib.metadata.files("rtree")
                if pkg_files is not None:
                    for file in pkg_files:  # type: ignore
                        if (
                            file.parent.name == "Rtree.libs"
                            and file.stem.startswith("libspatialindex")
                            and ".so" in file.suffixes
                        ):
                            _candidates.insert(1, Path(file.locate()))
                            break
            except importlib.metadata.PackageNotFoundError:
                pass

        # get the starting working directory
        cwd = os.getcwd()
        for cand in _candidates:
            if cand.is_dir():
                # if our candidate is a directory use best guess
                path = cand
                target = cand / lib_name
            elif cand.is_file():
                # if candidate is just a file use that
                path = cand.parent
                target = cand
            else:
                continue

            if not target.exists():
                continue

            try:
                # move to the location we're checking
                os.chdir(path)
                # try loading the target file candidate
                rt = ctypes.cdll.LoadLibrary(str(target))
                if rt is not None:
                    return rt
            except BaseException as err:
                print(
                    f"rtree.finder ({target}) unexpected error: {err!s}",
                    file=sys.stderr,
                )
            finally:
                os.chdir(cwd)

    try:
        # try loading library using LD path search
        pth = find_library("spatialindex_c")
        if pth is not None:
            return ctypes.cdll.LoadLibrary(pth)

    except BaseException:
        pass

    raise OSError("Could not load libspatialindex_c library")


def get_include() -> str:
    """Return the directory that contains the spatialindex \\*.h files.

    :returns: Path to include directory or "" if not found.
    """
    # check if was bundled with a binary wheel
    try:
        pkg_files = importlib.metadata.files("rtree")
        if pkg_files is not None:
            for path in pkg_files:  # type: ignore
                if path.name == "SpatialIndex.h":
                    return str(Path(path.locate()).parent.parent)
    except importlib.metadata.PackageNotFoundError:
        pass

    # look for this header file in a few directories
    path_to_spatialindex_h = Path("include/spatialindex/SpatialIndex.h")

    # check sys.prefix, e.g. conda's libspatialindex package
    if os.name == "nt":
        file = _sys_prefix / "Library" / path_to_spatialindex_h
    else:
        file = _sys_prefix / path_to_spatialindex_h
    if file.is_file():
        return str(file.parent.parent)

    # check if relative to lib
    libdir = Path(load()._name).parent
    file = libdir.parent / path_to_spatialindex_h
    if file.is_file():
        return str(file.parent.parent)

    # check system install
    file = Path("/usr") / path_to_spatialindex_h
    if file.is_file():
        return str(file.parent.parent)

    # not found
    return ""
