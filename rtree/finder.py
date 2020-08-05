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


def load():

    full_path, lib_path, lib_name = None, None, None
    if os.name == 'nt':

        def _load_library(dllname, loadfunction, dllpaths=('', )):
            """Load a DLL via ctypes load function. Return None on failure.
            Try loading the DLL from the current package directory first,
            then from the Windows DLL search path.
            """
            try:
                dllpaths = (os.path.abspath(os.path.dirname(__file__)),
                            ) + dllpaths
            except NameError:
                # no __file__ attribute on PyPy and some frozen distributions
                pass
            for path in dllpaths:
                if path:
                    # temporarily add the path to the PATH environment variable
                    # so Windows can find additional DLL dependencies.
                    try:
                        oldenv = os.environ['PATH']
                        os.environ['PATH'] = path + ';' + oldenv
                    except KeyError:
                        oldenv = None
                try:
                    return loadfunction(os.path.join(path, dllname))
                except (WindowsError, OSError):
                    pass
                finally:
                    if path and oldenv is not None:
                        os.environ['PATH'] = oldenv
            return None

        base_name = 'spatialindex_c'
        if '64' in platform.architecture()[0]:
            arch = '64'
        else:
            arch = '32'

        lib_name = '%s-%s.dll' % (base_name, arch)
        rt = None
        if 'SPATIALINDEX_C_LIBRARY' in os.environ:
            full_path = os.environ['SPATIALINDEX_C_LIBRARY']
            lib_path, lib_name = os.path.split(full_path)
            rt = _load_library(lib_name, ctypes.cdll.LoadLibrary, (lib_path,))
        # try wheel location
        if not rt:
            lib_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "lib"))
            full_path = os.path.join(lib_path, lib_name)
            rt = _load_library(lib_name, ctypes.cdll.LoadLibrary, (lib_path,))
        # try conda location
        if not rt:
            if 'conda' in sys.version:
                lib_path = os.path.join(sys.prefix, "Library", "bin")
                rt = _load_library(
                    lib_name, ctypes.cdll.LoadLibrary, (lib_path,))
                full_path = os.path.join(lib_path, lib_name)
        if not rt:
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

    if full_path is not None and os.path.exists(full_path):
        final = full_path
    elif lib_path is not None and os.path.exists(lib_path):
        final = lib_path
    else:
        try:
            # will throw an exception including the path :cry:
            rt['heyyy']
        except BaseException as E:
            # for the love of god, this is the only way I've found
            # to extract the shared library path easily
            exc = str(E)
            final = os.path.abspath(exc.split(':', 1)[0])

    return rt, final
