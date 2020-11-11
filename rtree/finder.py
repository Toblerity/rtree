"""
finder.py
------------

Locate `libspatialindex` shared library by any means necessary.
"""
import os
import sys
import platform
import ctypes

from ctypes.util import find_library

# the current working directory of this file
_cwd = os.path.abspath(os.path.expanduser(
    os.path.dirname(__file__)))


def load(return_path=False):

    full_path, lib_path, lib_name = None, None, None
    if os.name == 'nt':
        def _load_library(dllname, loadfunction, dllpaths=('', )):
            """Load a DLL via ctypes load function. Return None on failure.
            Try loading the DLL from the current package directory first,
            then from the Windows DLL search path.
            """
            for path in dllpaths:
                if not path or not os.path.exists(path):
                    continue
                # temporarily add the path to the PATH environment variable
                # so Windows can find additional DLL dependencies.
                try:
                    oldenv = os.environ['PATH']
                    os.environ['PATH'] = path + ';' + oldenv
                except KeyError:
                    oldenv = None
                try:
                    return loadfunction(os.path.join(
                        path, dllname)), os.path.join(path, dllname)
                except (WindowsError, OSError):
                    pass
                finally:
                    if path and oldenv is not None:
                        os.environ['PATH'] = oldenv
            return None, None

        if '64' in platform.architecture()[0]:
            arches = ('64', '32')
        else:
            arches = ('32', '64')

        rt = None
        for arch in arches:
            lib_name = 'spatialindex_c-{}.dll'.format(arch)
            # generate a bunch of candidate locations where the
            # libspatialindex DLL *might* be hanging out
            candidates = [os.environ.get('SPATIALINDEX_C_LIBRARY', None),
                          _cwd,
                          os.path.join(_cwd, 'lib'),
                          os.path.join(sys.prefix, "Library", "bin")]
            # run through our list of candidate locations
            rt, full_path = _load_library(
                lib_name, ctypes.cdll.LoadLibrary, candidates)
            if rt is not None:
                break

        if not rt:
            # try a bare call for funsies
            rt = _load_library(lib_name, ctypes.cdll.LoadLibrary)

        if not rt:
            raise OSError("could not find or load %s" % lib_name)

    elif os.name == 'posix':
        if 'SPATIALINDEX_C_LIBRARY' in os.environ:
            lib_name = os.environ['SPATIALINDEX_C_LIBRARY']

            rt = ctypes.CDLL(lib_name)
        else:
            try:
                # try loading libspatialindex from the wheel location
                # inside the package
                lib_path = os.path.abspath(os.path.join(
                    os.path.dirname(__file__), "lib"))
                old_dir = os.getcwd()
                os.chdir(lib_path)
                full_path = os.path.join(lib_path, "libspatialindex_c.so")
                rt = ctypes.cdll.LoadLibrary(full_path)

                # Switch back to the original working directory
                os.chdir(old_dir)
                if not rt:
                    raise OSError("%s not loaded" % full_path)
            except BaseException:
                lib_name = find_library('spatialindex_c')
                rt = ctypes.CDLL(lib_name)
                if not rt:
                    raise OSError("%s not loaded" % full_path)
        if not rt:
            raise OSError("Could not load libspatialindex_c library")

    else:
        raise OSError("Could not load libspatialindex_c library")

    if not return_path:
        return rt

    if full_path is not None and os.path.exists(full_path):
        final = full_path
    elif lib_path is not None and os.path.exists(lib_path):
        final = lib_path
    else:
        # try looking relative to ctypes import
        final = os.path.abspath(
            os.path.join(
                os.path.split(ctypes.__file__)[0], '../..', rt._name))
    if not os.path.isfile(final):
        try:
            # will throw an exception including the path
            rt['dummyproperty']
        except BaseException as E:
            # for the love of god, this is the only way I've found
            # to extract the shared library path easily
            exc = str(E)
            final = os.path.abspath(exc.split(':', 1)[0])

    return rt, final
